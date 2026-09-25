"""Tiny resilient HTTP layer: timeouts, retries with backoff, per-source health log."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field

import aiohttp

log = logging.getLogger("gamexpress.http")

BROWSER_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/128.0 Safari/537.36")
BOT_UA = "Game-Express/1.0 (+https://github.com/uesu/Game-Express)"


@dataclass
class SourceHealth:
    ok: int = 0
    fail: int = 0
    last_error: str = ""
    last_ok_ts: int = 0


@dataclass
class Fetcher:
    session: aiohttp.ClientSession
    timeout: int = 20
    health: dict[str, SourceHealth] = field(default_factory=dict)

    def _mark(self, source: str, ok: bool, err: str = "") -> None:
        h = self.health.setdefault(source, SourceHealth())
        if ok:
            h.ok += 1
            h.last_ok_ts = int(time.time())
        else:
            h.fail += 1
            h.last_error = err[:200]

    async def get_text(self, url: str, *, source: str, headers: dict | None = None,
                       params: dict | None = None, retries: int = 2,
                       ok_statuses: tuple[int, ...] = (200,)) -> str | None:
        hdrs = {"User-Agent": BROWSER_UA, "Accept": "*/*"}
        if headers:
            hdrs.update(headers)
        delay = 1.5
        last = ""
        for attempt in range(retries + 1):
            try:
                async with self.session.get(url, headers=hdrs, params=params,
                                            timeout=aiohttp.ClientTimeout(total=self.timeout)) as r:
                    if r.status in ok_statuses:
                        body = await r.text(errors="replace")
                        self._mark(source, True)
                        return body
                    last = f"HTTP {r.status}"
                    if r.status in (400, 401, 403, 404, 410):
                        break  # permanent for this run — don't hammer
            except (aiohttp.ClientError, asyncio.TimeoutError, UnicodeDecodeError) as e:
                last = f"{type(e).__name__}: {e}"
            if attempt < retries:
                await asyncio.sleep(delay)
                delay *= 2
        log.info("[%s] %s -> %s", source, url.split("?")[0], last)
        self._mark(source, False, last)
        return None

    async def get_json(self, url: str, *, source: str, headers: dict | None = None,
                       params: dict | None = None, retries: int = 2):
        body = await self.get_text(url, source=source, headers=headers, params=params, retries=retries)
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
            log.info("[%s] invalid JSON from %s", source, url.split("?")[0])
            return None

    def summary(self) -> str:
        parts = []
        for name, h in sorted(self.health.items()):
            parts.append(f"{name}: {h.ok} ok / {h.fail} fail" + (f" ({h.last_error})" if h.fail and not h.ok else ""))
        return "; ".join(parts) if parts else "no requests"
