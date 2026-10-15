"""Tiny resilient HTTP layer: timeouts, retries with backoff, per-source health log."""

from __future__ import annotations

import asyncio
import json
import logging
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import aiohttp

log = logging.getLogger("gamexpress.http")

BROWSER_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/128.0 Safari/537.36")
# No version in the User-Agent, on purpose. It used to include the old "/1.1" suffix — a
# hand-maintained number that stopped being maintained the day `__version__` was retired in
# favour of build_id() (see __init__.py), so it sat frozen, announcing something to every site
# the monitor touches that had not been true for a long time. A bare product token is valid
# (RFC 9110: the "/version" part is optional) and can never go stale. The contact URL is the
# half that actually matters to anyone reading a log. Same string in sources/codes.py and
# sources/twitter.py.
BOT_UA = "Game-Express (+https://github.com/uesu/Game-Express)"
MAX_PARALLEL = 12          # polite global cap on simultaneous requests (all games fetch in parallel)
MAX_BYTES = 8 * 1024 * 1024
"""Hard cap on one response body (8 MiB).

Almost everything this monitor reads belongs to a third party nobody here controls: 16
community nitter mirrors, wikis, code APIs. A hostile or simply broken host can answer with
an endless stream, and `resp.text()` would buffer all of it until the runner runs out of
memory or the job hits its timeout. Reading a bounded number of bytes turns that into one
ordinary source failure instead. The largest real body seen in production is ~1.3 MB.
"""
CHUNK_BYTES = 64 * 1024
"""Read size per iteration while streaming a body (see get_text)."""

MAX_EVENTS = 500

DISCORD_WEBHOOK_URL_RE = re.compile(
    r"(https?://(?:(?:ptb|canary)\.)?discord(?:app)?\.com/api(?:/v\d+)?/webhooks/)"
    r"\d+/[\w-]+",
    re.IGNORECASE,
)
ENCODED_DISCORD_WEBHOOK_RE = re.compile(
    r"(https?%3A%2F%2F(?:(?:ptb|canary)\.)?discord(?:app)?\.com%2Fapi(?:%2Fv\d+)?%2Fwebhooks%2F)"
    r"\d+%2F[\w%-]+",
    re.IGNORECASE,
)
GITHUB_TOKEN_RE = re.compile(
    r"\b(?:ghp_[A-Za-z0-9]{20,}|ghs_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})\b"
)
URL_IN_TEXT_RE = re.compile(r"https?://[^\s\"'<>)\]]+")
AUTH_BEARER_RE = re.compile(
    r"\b(Bearer|Bot|Basic)\s+[A-Za-z0-9._~+/=-]{4,}",
    re.IGNORECASE,
)
QUERY_SECRET_TEXT_RE = re.compile(
    r"([?&](?:key|token|sig|secret|auth|password|webhook|api_key|access_token|signature|client_secret)=)"
    r"[^&#\s\"'<>)\]]+",
    re.IGNORECASE,
)
ENCODED_QUERY_SECRET_RE = re.compile(
    r"((?:%3F|%26)(?:key|token|sig|secret|auth|password|webhook|api_key|access_token|signature|client_secret)%3D)"
    r"[^%&#\s\"'<>)\]]+",
    re.IGNORECASE,
)

SENSITIVE_QUERY_KEYS = frozenset(
    {
        "key",
        "token",
        "sig",
        "secret",
        "auth",
        "password",
        "webhook",
        "api_key",
        "apikey",
        "access_token",
        "signature",
        "client_secret",
    }
)
SENSITIVE_HEADERS = frozenset(
    {
        "authorization",
        "proxy-authorization",
        "cookie",
        "set-cookie",
        "x-api-key",
        "x-auth-token",
    }
)

TRANSPORT_STATUSES = frozenset(
    {
        "http_ok",
        "http_status",
        "not_modified",
        "timeout",
        "network_error",
        "invalid_json",
        "empty_body",
        "rate_limited",
    }
)
SOURCE_STATUSES = frozenset(
    {
        "selected",
        "usable_empty",
        "transport_ok_zero_items",
        "parse_empty",
        "filtered_out",
        "fallback_used",
        "source_failed",
        "not_modified",
    }
)


def redact_url(url: str, worker_url: str = "") -> str:
    """Redact webhook tokens, URL userinfo, sensitive query params, and worker path tokens."""
    if not url:
        return ""
    raw = DISCORD_WEBHOOK_URL_RE.sub(r"\1<redacted>", str(url))
    try:
        parts = urlsplit(raw)
    except ValueError:
        return QUERY_SECRET_TEXT_RE.sub(r"\1<redacted>", raw)

    if not parts.scheme or not parts.netloc:
        return QUERY_SECRET_TEXT_RE.sub(r"\1<redacted>", raw)

    netloc = parts.netloc
    if "@" in netloc:
        _, hostpart = netloc.rsplit("@", 1)
        netloc = f"<redacted>@{hostpart}"

    path = parts.path
    if worker_url:
        try:
            w_parts = urlsplit(worker_url)
            w_host = w_parts.netloc.rsplit("@", 1)[-1].lower()
            cur_host = netloc.rsplit("@", 1)[-1].lower()
            if w_host and cur_host == w_host and path not in ("", "/"):
                path = "/<redacted>"
        except ValueError:
            pass

    query = parts.query
    if query:
        pairs = parse_qsl(query, keep_blank_values=True)
        redacted_pairs: list[tuple[str, str]] = []
        changed = False
        for k, v in pairs:
            if k.lower() in SENSITIVE_QUERY_KEYS or any(
                s in k.lower() for s in ("token", "secret", "password", "sig", "auth", "key", "webhook")
            ):
                redacted_pairs.append((k, "<redacted>"))
                changed = True
            else:
                redacted_pairs.append((k, v))
        if changed:
            query = urlencode(redacted_pairs)
            query = query.replace("%3Credacted%3E", "<redacted>")

    return urlunsplit((parts.scheme, netloc, path, query, ""))


def redact_headers(headers: Mapping[str, Any] | None, worker_url: str = "") -> dict[str, str]:
    """Return a copy of HTTP headers with auth, cookie, and token headers redacted."""
    if not headers:
        return {}
    out: dict[str, str] = {}
    for k, v in headers.items():
        key_str = str(k)
        if key_str.lower() in SENSITIVE_HEADERS or any(
            s in key_str.lower() for s in ("token", "secret", "auth", "cookie", "key", "password")
        ):
            out[key_str] = "<redacted>"
        else:
            out[key_str] = redact_text(str(v), worker_url=worker_url)
    return out


def redact_text(text: str, worker_url: str = "") -> str:
    """Redact webhook URLs, userinfo URLs, query credentials, and auth tokens in free text."""
    if not text:
        return ""
    out = DISCORD_WEBHOOK_URL_RE.sub(r"\1<redacted>", str(text))
    out = ENCODED_DISCORD_WEBHOOK_RE.sub(r"\1<redacted>", out)
    out = GITHUB_TOKEN_RE.sub("<redacted>", out)
    out = URL_IN_TEXT_RE.sub(lambda m: redact_url(m.group(0), worker_url=worker_url), out)
    out = QUERY_SECRET_TEXT_RE.sub(r"\1<redacted>", out)
    out = ENCODED_QUERY_SECRET_RE.sub(r"\1<redacted>", out)
    out = AUTH_BEARER_RE.sub(r"\1 <redacted>", out)
    return out


def redact_value(value: Any, worker_url: str = "") -> Any:
    """Recursively redact URLs, headers, and secret tokens inside structured data."""
    if isinstance(value, str):
        return redact_text(value, worker_url=worker_url)
    if isinstance(value, Mapping):
        out: dict[str, Any] = {}
        for k, v in value.items():
            ks = str(k)
            if ks.lower() in SENSITIVE_HEADERS or ks.lower() in SENSITIVE_QUERY_KEYS:
                out[ks] = "<redacted>"
            else:
                out[ks] = redact_value(v, worker_url=worker_url)
        return out
    if isinstance(value, list):
        return [redact_value(x, worker_url=worker_url) for x in value]
    if isinstance(value, tuple):
        return [redact_value(x, worker_url=worker_url) for x in value]
    return value


def classify_transport_status(
    *,
    status_code: int | None = None,
    error: str = "",
    empty_body: bool = False,
    invalid_json: bool = False,
    not_modified: bool = False,
) -> str:
    """Classify an HTTP transport outcome into one of the canonical transport status codes."""
    if not_modified or status_code == 304:
        return "not_modified"
    if invalid_json:
        return "invalid_json"
    if status_code == 429:
        return "rate_limited"
    if status_code is not None and status_code >= 400:
        return "http_status"
    err_lower = (error or "").lower()
    if "timeout" in err_lower or "timed out" in err_lower:
        return "timeout"
    if error:
        if error.startswith("HTTP "):
            code_str = error.split(" ", 1)[1].strip()
            if code_str == "304":
                return "not_modified"
            if code_str == "429":
                return "rate_limited"
            return "http_status"
        if "invalid json" in err_lower:
            return "invalid_json"
        return "network_error"
    if empty_body:
        return "empty_body"
    return "http_ok"


def summarize_source_outcome(
    *,
    source: str,
    transport_status: str,
    parsed_count: int = 0,
    usable_count: int = 0,
    selected_count: int = 0,
    fallback_used: bool = False,
    parse_empty: bool = False,
    reason: str = "",
    game: str = "",
    lane: str = "",
) -> dict[str, Any]:
    """Build a canonical source outcome record distinguishing transport from content usability."""
    t_status = transport_status if transport_status in TRANSPORT_STATUSES else "network_error"
    parsed = max(0, int(parsed_count))
    usable = max(0, int(usable_count))
    selected = max(0, int(selected_count))
    short_reason = redact_text(reason)

    if t_status == "not_modified":
        final_status = "not_modified"
        short_reason = short_reason or "http_304_not_modified"
    elif t_status != "http_ok":
        if fallback_used and usable > 0:
            final_status = "fallback_used"
            short_reason = short_reason or f"primary_{t_status}_fallback_succeeded"
        else:
            final_status = "source_failed"
            short_reason = short_reason or t_status
    elif parse_empty:
        final_status = "parse_empty"
        short_reason = short_reason or "http_200_parse_empty"
    elif parsed == 0:
        final_status = "transport_ok_zero_items"
        short_reason = short_reason or "http_200_zero_items"
    elif usable == 0:
        final_status = "filtered_out"
        short_reason = short_reason or "all_parsed_items_filtered_out"
    elif fallback_used:
        final_status = "fallback_used"
        short_reason = short_reason or "secondary_source_answered"
    elif selected > 0:
        final_status = "selected"
    else:
        final_status = "usable_empty"
        short_reason = short_reason or "no_matching_items_for_window"

    return {
        "source": source,
        "lane": lane,
        "game": game,
        "transport_status": t_status,
        "parsed_count": parsed,
        "usable_count": usable,
        "selected_count": selected,
        "fallback_used": bool(fallback_used),
        "status": final_status,
        "reason": short_reason,
    }


@dataclass
class SourceHealth:
    ok: int = 0
    fail: int = 0
    last_error: str = ""


@dataclass
class Fetcher:
    session: aiohttp.ClientSession
    timeout: int = 20
    health: dict[str, SourceHealth] = field(default_factory=dict)
    parallel: int = MAX_PARALLEL
    _sem: asyncio.Semaphore | None = field(default=None, repr=False)
    events: list[dict[str, Any]] = field(default_factory=list, repr=False)
    source_outcomes: list[dict[str, Any]] = field(default_factory=list, repr=False)

    def _gate(self) -> asyncio.Semaphore:
        if self._sem is None:
            self._sem = asyncio.Semaphore(self.parallel)
        return self._sem

    def _mark(self, source: str, ok: bool, err: str = "") -> None:
        h = self.health.setdefault(source, SourceHealth())
        if ok:
            h.ok += 1
        else:
            h.fail += 1
            h.last_error = redact_text(err)[:200]

    def _record_event(
        self,
        *,
        source: str,
        url: str,
        transport_status: str,
        status_code: int | None = None,
        byte_len: int = 0,
        reason: str = "",
    ) -> None:
        if len(self.events) >= MAX_EVENTS:
            return
        safe_url = redact_url(url)
        host = urlsplit(safe_url).netloc or safe_url[:40]
        self.events.append(
            {
                "source": source,
                "url": safe_url,
                "host": host,
                "transport_status": transport_status,
                "status_code": status_code,
                "bytes": byte_len,
                "reason": redact_text(reason)[:160],
            }
        )

    def record_source_outcome(self, **kwargs: Any) -> dict[str, Any]:
        outcome = summarize_source_outcome(**kwargs)
        self.source_outcomes.append(outcome)
        return outcome

    def last_event_for(self, url_prefix: str, source: str = "") -> dict[str, Any] | None:
        """Return the most recent transport event matching `url_prefix` (and optional `source`)."""
        safe_prefix = redact_url(url_prefix)
        for ev in reversed(self.events):
            if source and ev.get("source") != source:
                continue
            ev_url = str(ev.get("url") or "")
            if ev_url == safe_prefix or ev_url.startswith(safe_prefix):
                return ev
        return None

    async def get_text(self, url: str, *, source: str, headers: dict | None = None,
                       params: dict | None = None, retries: int = 2,
                       ok_statuses: tuple[int, ...] = (200,), timeout: float | None = None) -> str | None:
        hdrs = {"User-Agent": BROWSER_UA, "Accept": "*/*"}
        if headers:
            hdrs.update(headers)
        delay = 1.5
        last = ""
        last_status: int | None = None
        for attempt in range(retries + 1):
            try:
                async with self._gate(), self.session.get(url, headers=hdrs, params=params,
                                            timeout=aiohttp.ClientTimeout(total=timeout or self.timeout)) as r:
                    last_status = r.status
                    if r.status in ok_statuses:
                        # read in chunks, NOT `content.read(MAX_BYTES + 1)`: aiohttp's read(n)
                        # returns whatever is buffered RIGHT NOW (up to n), so a body that
                        # arrives in several TCP reads came back truncated — a valid feed then
                        # failed as "invalid JSON" / "0 entries". Loop until EOF or the cap.
                        raw = bytearray()
                        oversize = False
                        async for part in r.content.iter_chunked(CHUNK_BYTES):
                            raw += part
                            if len(raw) > MAX_BYTES:
                                oversize = True
                                break
                        if oversize:
                            last = f"response larger than {MAX_BYTES // (1024 * 1024)} MiB"
                            break   # a source this broken will not fix itself on a retry
                        body = bytes(raw).decode(r.charset or "utf-8", errors="replace")
                        self._mark(source, True)
                        t_status = classify_transport_status(
                            status_code=r.status,
                            empty_body=(len(body.strip()) == 0),
                        )
                        self._record_event(
                            source=source,
                            url=url,
                            transport_status=t_status,
                            status_code=r.status,
                            byte_len=len(raw),
                        )
                        return body
                    last = f"HTTP {r.status}"
                    if r.status in (400, 401, 403, 404, 410):
                        break  # permanent for this run — don't hammer
            except (aiohttp.ClientError, asyncio.TimeoutError, UnicodeDecodeError) as e:
                last = f"{type(e).__name__}: {e}"
            if attempt < retries:
                await asyncio.sleep(delay)
                delay *= 2
        safe_url = redact_url(url.split("?")[0])
        safe_last = redact_text(last)
        log.info("[%s] %s -> %s", source, safe_url, safe_last)
        self._mark(source, False, safe_last)
        t_status = classify_transport_status(status_code=last_status, error=safe_last)
        self._record_event(
            source=source,
            url=url,
            transport_status=t_status,
            status_code=last_status,
            reason=safe_last,
        )
        return None

    async def get_json(self, url: str, *, source: str, headers: dict | None = None,
                       params: dict | None = None, retries: int = 2, timeout: float | None = None):
        body = await self.get_text(url, source=source, headers=headers, params=params, retries=retries,
                                   timeout=timeout)
        if body is None:
            return None
        try:
            return json.loads(body)
        except json.JSONDecodeError:
            # some mirrors prepend comments/BOMs
            start = min([i for i in (body.find("{"), body.find("[")) if i >= 0], default=-1)
            if start > 0:
                try:
                    return json.loads(body[start:])
                except json.JSONDecodeError:
                    pass
            self._mark(source, False, "invalid JSON")
            safe_url = redact_url(url.split("?")[0])
            log.info("[%s] invalid JSON from %s", source, safe_url)
            self._record_event(
                source=source,
                url=url,
                transport_status="invalid_json",
                status_code=200,
                byte_len=len(body),
                reason="invalid JSON",
            )
            return None

    def summary(self) -> str:
        parts = []
        hosts_by_source: dict[str, set[str]] = {}
        for ev in self.events:
            src = str(ev.get("source") or "")
            host = str(ev.get("host") or "")
            if src and host:
                hosts_by_source.setdefault(src, set()).add(host)
        for name, h in sorted(self.health.items()):
            host_cnt = len(hosts_by_source.get(name, set()))
            host_sfx = f" [{host_cnt} host(s)]" if host_cnt else ""
            err_sfx = f" ({h.last_error})" if h.fail and not h.ok else ""
            parts.append(f"{name}: {h.ok} http_200 / {h.fail} transport_fail{host_sfx}{err_sfx}")
        return "; ".join(parts) if parts else "no requests"


class Probe:
    """Wraps the shared Fetcher for ONE game so 'did any of this game's sources answer?'
    stays correct while every game is gathered concurrently."""

    def __init__(self, inner) -> None:
        self.inner = inner
        self.ok = 0

    async def get_text(self, *a, **k):
        r = await self.inner.get_text(*a, **k)
        if r is not None:
            self.ok += 1
        return r

    async def get_json(self, *a, **k):
        r = await self.inner.get_json(*a, **k)
        if r is not None:
            self.ok += 1
        return r

    def __getattr__(self, name):          # health / summary / session … pass through
        return getattr(self.inner, name)
