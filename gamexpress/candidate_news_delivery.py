"""Fail-closed delivery primitives for the three inactive candidate news sources.

NOT registered in the production runner. The checkpoint callback MUST durably commit
state to the authoritative store before returning True. A local temp-file save alone
is not such a checkpoint for an ephemeral Actions runner. No webhook URL is stored.
"""
from __future__ import annotations

import copy
import hashlib
import json
import re
from datetime import UTC, datetime
from urllib.parse import parse_qsl, urlsplit

from .cards import validate_payload
from .discord import webhook_fingerprint
from .sources import nte_candidate, silverpalace
from .state import stable_hash

SOURCES = frozenset(("nte", "endfield", "silverpalace"))
MAX_IDS = 10000
_ID = re.compile(r"[0-9]{1,32}\Z")
_HASH = re.compile(r"[a-f0-9]{16}\Z")
_SIGNATURE = re.compile(r"[a-f0-9]{64}\Z")
_PATH = re.compile(r"/api(?:/v[0-9]+)?/webhooks/[0-9]{1,32}/[A-Za-z0-9_-]{16,256}\Z")


class DeliveryHold(ValueError):
    """Unsafe, ambiguous or unpersisted delivery; caller must stop and inspect."""


def destination(settings, source):
    """Return the dedicated webhook and its non-secret fingerprint, or no destination."""
    if source not in SOURCES:
        return None
    name, url = settings.webhook_source("news", source)
    if name != "DISCORD_WEBHOOK_NEWS_" + source.upper() or not isinstance(url, str):
        return None
    try:
        p = urlsplit(url)
        query = parse_qsl(p.query, keep_blank_values=True, strict_parsing=True) if p.query else []
        if (p.scheme != "https" or p.hostname not in ("discord.com", "discordapp.com")
                or p.username or p.password or p.port not in (None, 443) or p.fragment
                or not _PATH.fullmatch(p.path) or len(query) > 1
                or any(k != "thread_id" or not re.fullmatch(r"[0-9]{1,32}", v) for k, v in query)):
            return None
    except ValueError:
        return None
    return url, stable_hash([webhook_fingerprint(url), p.query])


def _row(source, raw):
    if not isinstance(raw, dict):
        raise DeliveryHold("invalid listing row")
    expected = {"id", "title", "ts"} if source == "endfield" else {"id", "title", "date"}
    if source == "nte":
        expected.add("url")
    if set(raw) != expected:
        raise DeliveryHold("invalid listing row fields")
    cid, title = raw.get("id"), raw.get("title")
    if (not isinstance(cid, str) or not _ID.fullmatch(cid) or not isinstance(title, str)
            or not title.strip() or len(title) > 512):
        raise DeliveryHold("invalid listing identity")
    if source == "endfield":
        if type(raw["ts"]) is not int or not 0 < raw["ts"] <= 253402300799:
            raise DeliveryHold("invalid publication time")
    elif not silverpalace._valid_date(raw["date"]):
        raise DeliveryHold("invalid displayed day")
    if source == "nte":
        url = raw["url"]
        prefix = "https://nte.perfectworld.com"
        if not isinstance(url, str) or not url.startswith(prefix + "/"):
            raise DeliveryHold("invalid NTE article URL")
        match = nte_candidate._PATH.fullmatch(url[len(prefix):])
        if not match or match.group(1) != cid:
            raise DeliveryHold("invalid NTE article path")
    return copy.deepcopy(raw)


def _order(source, row):
    return (row["ts"] if source == "endfield" else row["date"], int(row["id"]), row["id"])


def _validate(state, source, route):
    if (source not in SOURCES or not isinstance(route, str) or not _HASH.fullmatch(route)
            or not isinstance(state, dict) or set(state) != {"version", "source", "route", "pending", "posted", "partial"}
            or type(state["version"]) is not int or state["version"] != 1
            or state["source"] != source or state["route"] != route
            or not isinstance(state["pending"], list) or not isinstance(state["posted"], dict)):
        raise DeliveryHold("invalid state or destination changed")
    rows = [_row(source, row) for row in state["pending"]]
    pending_ids = [row["id"] for row in rows]
    posted = state["posted"]
    if (len(rows) + len(posted) > MAX_IDS or len(set(pending_ids)) != len(rows)
            or set(pending_ids) & set(posted)):
        raise DeliveryHold("duplicate or excessive IDs")
    for cid, rec in posted.items():
        if (not isinstance(cid, str) or not _ID.fullmatch(cid) or not isinstance(rec, dict)
                or set(rec) != {"messages", "signature"} or not isinstance(rec["signature"], str) or not _SIGNATURE.fullmatch(rec["signature"])
                or not isinstance(rec["messages"], list) or not rec["messages"]
                or any(not isinstance(mid, str) or not _ID.fullmatch(mid) for mid in rec["messages"])
                or len(set(rec["messages"])) != len(rec["messages"])):
            raise DeliveryHold("invalid posted record")
    partial = state["partial"]
    if partial is not None and (
                not isinstance(partial, dict) or set(partial) != {"id", "signature", "pages", "messages", "inflight"}
                or not rows or partial["id"] != rows[0]["id"]
                or not isinstance(partial["signature"], str) or not _SIGNATURE.fullmatch(partial["signature"])
                or type(partial["pages"]) is not int or not 1 <= partial["pages"] <= 120
                or not isinstance(partial["messages"], list) or len(partial["messages"]) > partial["pages"]
                or any(not isinstance(mid, str) or not _ID.fullmatch(mid) for mid in partial["messages"])
                or len(set(partial["messages"])) != len(partial["messages"])
                or type(partial["inflight"]) is not bool
                or (partial["inflight"] and len(partial["messages"]) >= partial["pages"])):
        raise DeliveryHold("invalid partial delivery")
    tail = rows[1:] if partial else rows
    if tail != sorted(tail, key=lambda row: _order(source, row)):
        raise DeliveryHold("pending items are out of order")
    return copy.deepcopy(state)


def ingest(source, route, current, snapshot):
    """Queue a verified complete snapshot; preserve all posted IDs and incomplete pages."""
    if source not in SOURCES or not isinstance(route, str) or not _HASH.fullmatch(route):
        raise DeliveryHold("invalid route")
    if not isinstance(snapshot, list) or not snapshot or len(snapshot) > MAX_IDS:
        raise DeliveryHold("complete snapshot required")
    rows = [_row(source, value) for value in snapshot]
    ids = [row["id"] for row in rows]
    if len(ids) != len(set(ids)):
        raise DeliveryHold("duplicate snapshot IDs")
    if current is None:
        return {"version": 1, "source": source, "route": route, "pending": sorted(rows, key=lambda r: _order(source, r)),
                "posted": {}, "partial": None}
    state = _validate(current, source, route)
    known = set(state["posted"]) | {row["id"] for row in state["pending"]}
    state["pending"].extend(row for row in rows if row["id"] not in known)
    if len(state["pending"]) + len(state["posted"]) > MAX_IDS:
        raise DeliveryHold("ID capacity exceeded")
    # An already-started multi-page article must finish before newly discovered backdated rows.
    prefix = state["pending"][:1] if state["partial"] else []
    remaining = state["pending"][len(prefix):]
    state["pending"] = prefix + sorted(remaining, key=lambda r: _order(source, r))
    return state


async def deliver_oldest(state, source, route, *, as_of, checkpoint, render, send):
    """Deliver at most one article, persisting intent BEFORE each one-shot POST.

    A restart with `inflight` is held for human reconciliation. A payload signature
    mismatch also holds. Each successful message ID is checkpointed before continuing.
    Both the checkpoint and the sender must be supplied by the future integration.
    """
    state = _validate(state, source, route)
    if not state["pending"]:
        return state
    if state["partial"] and state["partial"]["inflight"]:
        raise DeliveryHold("ambiguous in-flight page requires reconciliation")
    if type(as_of) is not int or not 0 < as_of <= 253402300799:
        raise DeliveryHold("valid observation time required")
    row = state["pending"][0]
    # Day-only feeds have no publisher time zone. UTC calendar-day gating is
    # deliberately conservative; it does not invent an instant for the card.
    today = datetime.fromtimestamp(as_of, UTC).date().isoformat()
    if (source == "endfield" and row["ts"] > as_of) or (source != "endfield" and row["date"] > today):
        raise DeliveryHold("future-dated article held")

    async def persist():
        try:
            saved = await checkpoint(copy.deepcopy(state))
        except Exception as exc:  # noqa: BLE001
            raise DeliveryHold("checkpoint failed; no further sends") from exc
        if saved is not True:
            raise DeliveryHold("checkpoint not confirmed; no further sends")

    # Persist the entire initial/backdated queue before any irreversible send.
    await persist()
    payloads = await render(copy.deepcopy(row))
    if not isinstance(payloads, list) or not 1 <= len(payloads) <= 120 or any(not isinstance(p, dict) or validate_payload(p) for p in payloads):
        raise DeliveryHold("invalid rendered pages")
    signature = hashlib.sha256(json.dumps(payloads, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    partial = state["partial"]
    if partial and (partial["signature"] != signature or partial["pages"] != len(payloads)):
        raise DeliveryHold("partial article changed; reconciliation required")
    if partial is None:
        partial = {"id": row["id"], "signature": signature, "pages": len(payloads), "messages": [], "inflight": False}
        state["partial"] = partial
        await persist()
    for payload in payloads[len(partial["messages"]):]:
        partial["inflight"] = True
        await persist()
        try:
            result = await send(payload)
        except Exception as exc:  # noqa: BLE001
            raise DeliveryHold("POST outcome ambiguous; inspect before resuming") from exc
        mid = getattr(result, "message_id", None)
        if (not getattr(result, "ok", False) or getattr(result, "ambiguous", False)
                or not isinstance(mid, str) or not _ID.fullmatch(mid) or mid in partial["messages"]):
            raise DeliveryHold("POST not confirmed; inspect before resuming")
        partial["messages"].append(mid)
        partial["inflight"] = False
        await persist()
    state["posted"][row["id"]] = {"messages": list(partial["messages"]), "signature": signature}
    state["pending"].pop(0)
    state["partial"] = None
    await persist()
    return state


def candidate_game(source):
    """Local news-only descriptors; do not opt games into other features."""
    from .config import Game

    names = {"nte": ("Neverness to Everness", "NTE"), "endfield": ("Arknights: Endfield", "Endfield"),
             "silverpalace": ("Silver Palace", "Silver Palace")}
    if source not in names:
        raise DeliveryHold("unknown candidate source")
    name, short = names[source]
    return Game(key=source, name=name, short=short, enabled=False, color=14922399)


async def discover(fetcher, source):
    """Return a complete checked listing or None; this does not persist a baseline."""
    from .sources import endfield

    game = candidate_game(source)
    if source == "nte":
        return await nte_candidate.snapshot(fetcher)
    if source == "endfield":
        return await endfield.snapshot(fetcher, game)
    return await silverpalace.snapshot(fetcher)


async def render_candidate(fetcher, settings, source, row):
    """Fetch official detail, apply scoped fallback, validate and preflight all media."""
    from .cards import news_payloads
    from .media import group_news_media, news_media_available
    from .sources import endfield
    from .sources.candidate_thumbnail import with_verified_fallback

    row = _row(source, row)
    game = candidate_game(source)
    source_module = {"nte": nte_candidate, "endfield": endfield, "silverpalace": silverpalace}[source]
    item = await source_module.news_article(fetcher, game, row)
    if item is None or item.source != source or item.game != source or item.id != row["id"]:
        raise DeliveryHold("official article unavailable or mismatched")
    item = await with_verified_fallback(fetcher, item)
    pages = news_payloads(game, item, timestamps=settings.news_timestamps,
                          expand_full=settings.news_expand_full, max_pages=settings.news_expand_max_pages,
                          max_chars=settings.news_expand_max_chars, max_media=settings.news_expand_max_media)
    if (not pages or len(pages) > 120 or any(validate_payload(page) for page in pages)
            or not await news_media_available(fetcher, pages, max_urls=settings.news_expand_max_media)):
        raise DeliveryHold("article media preflight or payload validation failed")
    pages = await group_news_media(fetcher, pages, enabled=settings.news_group_long_strips,
                                   max_urls=settings.news_expand_max_media)
    if any(validate_payload(page) for page in pages):
        raise DeliveryHold("grouped article payload invalid")
    return pages
