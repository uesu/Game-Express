"""Redemption-code poster.

Accuracy gate (a code is posted only when ONE of these is true):
  * it comes from an OFFICIAL source — HoYoLAB livestream module, an official tweet /
    HoYoLAB / Kuro post that explicitly lists redemption codes;
  * a redeem-VALIDATOR reports it working (hoyo-codes.seria.moe status OK, or the daily
    Hum-Bao list) and no validator reports it expired;
  * at least CODES_MIN_SOURCES (default 2) community sources from DIFFERENT families
    agree (Open Gacha Codes + api.ennead.cc count as ONE family — same author/pipeline)
    and none of them lists the code as expired.
Single-source / disputed codes wait as 'pending' (up to 14 days) until confirmed.
First run for a game = silent seed (existing codes are recorded, not posted).

Posted cards stay accurate: when every source that still mentions a posted code lists
it as EXPIRED, the original message is edited silently — the code is struck through and
its Redeem button removed (CODES_MARK_EXPIRED, default on).
"""

from __future__ import annotations

import asyncio
import logging

from .cards import codes_card, codes_payloads, mark_test
from .config import Game
from .discord import webhook_fingerprint
from .models import CodeHit
from .sources.codes import VALIDATORS, extract_codes_from_text, family

log = logging.getLogger("gamexpress.codes")

REWARD_PREFERENCE = ("seria", "ennead", "ogc", "hoyolab", "codehub", "wuthering.gg", "fandom", "humbao",
                     "x", "kuro")
OFFICIAL = {"hoyolab", "x", "kuro"}
PENDING_DAYS = 14
LAST_SEEN_GRANULARITY = 12 * 3600


def official_hits_from_items(items) -> list[CodeHit]:
    hits: list[CodeHit] = []
    for it in items:
        if not it.official:
            continue
        src = it.source if it.source in OFFICIAL else "hoyolab"
        for code in extract_codes_from_text(it.full):
            hits.append(CodeHit(code, src, None, verified=True, url=it.url))
    return hits


def group_hits(hits: list[CodeHit]) -> dict[str, dict]:
    """code -> {sources (active), families, expired_by, verified, best_rewards, urls}"""
    grouped: dict[str, dict] = {}
    for h in hits:
        g = grouped.setdefault(h.code, {"sources": set(), "expired_by": set(), "verified": False,
                                        "rewards": {}, "urls": []})
        if h.expired:
            g["expired_by"].add(h.source)
            continue
        g["sources"].add(h.source)
        g["verified"] = g["verified"] or h.verified
        if h.rewards:
            g["rewards"].setdefault(h.source, h.rewards)
        if h.url:
            g["urls"].append(h.url)
    for g in grouped.values():
        g["families"] = {family(s) for s in g["sources"]}
        g["best_rewards"] = next((g["rewards"][s] for s in REWARD_PREFERENCE if s in g["rewards"]), None)
    return grouped


def gate(info: dict, min_sources: int) -> tuple[bool, str]:
    """(post?, reason)."""
    if info["sources"] & OFFICIAL:
        return True, "official"
    if info["verified"] and not (info["expired_by"] & VALIDATORS):
        return True, "redeem-validated"
    if info["expired_by"]:
        return False, f"listed as expired by {', '.join(sorted(info['expired_by']))}"
    if len(info["families"]) >= min_sources:
        return True, f"{len(info['families'])} independent sources"
    return False, f"only {', '.join(sorted(info['sources']))}"


def passes_gate(info: dict, min_sources: int) -> bool:          # kept for callers / tests
    return gate(info, min_sources)[0]


async def prefetch(ctx) -> dict[str, list[CodeHit] | None]:
    """Every code source of every game, fetched concurrently (each spec once)."""
    specs = sorted({x for g in ctx.games for x in g.codes.get("sources", []) if x and x != "x"})
    results = await asyncio.gather(*(ctx.code_sources.fetch(sp) for sp in specs))
    return dict(zip(specs, results))


async def run(ctx) -> None:
    s, now = ctx.settings, ctx.now
    table = await prefetch(ctx)
    for game in ctx.games:
        specs = [x for x in game.codes.get("sources", []) if x]
        if not specs:
            continue
        hits: list[CodeHit] = []
        reachable = 0
        for spec in specs:
            res = table.get(spec) if spec != "x" else None
            if res is None:
                continue
            reachable += 1
            hits.extend(res)
        official = official_hits_from_items(ctx.items.get(game.key, []))
        hits.extend(official)
        if not reachable and not official:
            if any(x != "x" for x in specs):
                ctx.warnings.append(f"{game.short}: every code source was unreachable this run")
            continue
        grouped = group_hits(hits)
        records = ctx.state.code_records(game.key)
        bootstrapped = ctx.state.is_bootstrapped("codes", game.key)
        min_sources = int(game.codes.get("min_sources") or s.codes_min_sources)
        to_post: list[dict] = []
        newly_expired: set[str] = set()
        for code, info in sorted(grouped.items()):
            rec = records.get(code)
            if not info["sources"]:
                # nobody lists it as active any more — only expiry bookkeeping for posted codes
                if (rec and rec.get("status") == "posted" and info["expired_by"] and not rec.get("expired_at")
                        and s.codes_mark_expired):
                    rec["expired_at"] = now
                    newly_expired.add(code)
                continue
            if rec:
                if now - int(rec.get("last_seen") or 0) > LAST_SEEN_GRANULARITY:
                    rec["last_seen"] = now          # coarse on purpose: no commit-per-run churn
                rec["sources"] = sorted(set(rec.get("sources", [])) | info["sources"])
                if info["best_rewards"] and not rec.get("rewards"):
                    rec["rewards"] = info["best_rewards"]
                if rec.get("status") not in ("pending", "posting"):   # posted / seeded / rejected
                    continue
            elif not bootstrapped and not s.bootstrap_post:
                records[code] = {"status": "seeded", "first_seen": now, "last_seen": now,
                                 "sources": sorted(info["sources"]), "rewards": info["best_rewards"]}
                continue
            ok, why = gate(info, min_sources)
            if ok:
                to_post.append({"code": code, "rewards": info["best_rewards"], "sources": sorted(info["sources"])})
                records[code] = {**(rec or {}), "status": "posting", "first_seen": (rec or {}).get("first_seen", now),
                                 "last_seen": now, "sources": sorted(info["sources"]),
                                 "rewards": info["best_rewards"], "gate": why}
            elif not rec:
                records[code] = {"status": "pending", "first_seen": now, "last_seen": now,
                                 "sources": sorted(info["sources"]), "rewards": info["best_rewards"]}
                ctx.report.append(f"⏳ {game.short} {code}: pending ({why})")
        # expire stale pending codes
        for rec in list(records.values()):
            if rec.get("status") == "pending" and now - int(rec.get("first_seen") or now) > PENDING_DAYS * 86400:
                rec["status"] = "rejected"
        if not bootstrapped:
            ctx.state.mark_bootstrapped("codes", game.key)
            if not s.bootstrap_post:
                seeded = sum(1 for r in records.values() if r.get("status") == "seeded")
                ctx.report.append(f"🌱 {game.short}: seeded {seeded} existing codes silently (first run)")
        if newly_expired:
            await _mark_expired(ctx, game, records, newly_expired)
        if to_post:
            await _post(ctx, game, to_post, records)


async def _post(ctx, game: Game, codes: list[dict], records: dict) -> None:
    s = ctx.settings
    webhook = s.webhook("codes", game.key)
    if not webhook:
        for c in codes:
            records[c["code"]]["status"] = "pending"
        ctx.report.append(f"⚠️ {game.short}: {len(codes)} new code(s) waiting — add the secret "
                          f"{s.expected_webhook_names('codes', game.key)}")
        return
    ping = s.ping("codes", game.key)
    payloads = codes_payloads(game, codes, s, ping, ctx.now)
    chunk_size = 10
    for i, payload in enumerate(payloads):
        chunk = codes[i * chunk_size:(i + 1) * chunk_size]
        if s.test_mode:
            payload = mark_test(payload)
        res = await ctx.webhook.send(webhook, payload)
        for c in chunk:
            rec = records[c["code"]]
            if res.ok:
                rec.update({"status": "posted", "posted_at": ctx.now, "message_id": res.message_id,
                            "webhook_fp": webhook_fingerprint(webhook),
                            "msg_codes": [x["code"] for x in chunk], "msg_part": [i + 1, len(payloads)]})
            else:
                rec["status"] = "pending"     # retried next run
        if res.ok:
            ctx.report.append(f"🎁 {game.short}: posted {len(chunk)} code(s): {', '.join(c['code'] for c in chunk)}")
        else:
            ctx.errors.append(f"{game.short}: code post failed ({res.status}) {res.error}")


async def _mark_expired(ctx, game: Game, records: dict, newly_expired: set[str]) -> None:
    """Silently edit each posted message that contains a newly expired code."""
    s = ctx.settings
    webhook = s.webhook("codes", game.key)
    by_msg: dict[str, list[str]] = {}
    for code in sorted(newly_expired):
        mid = records[code].get("message_id")
        if mid:
            by_msg.setdefault(str(mid), []).append(code)
    for mid, dead in by_msg.items():
        first = records[dead[0]]
        if not webhook or webhook_fingerprint(webhook) != first.get("webhook_fp"):
            ctx.report.append(f"ℹ️ {game.short}: {', '.join(dead)} expired — the card was posted through another "
                              "webhook, so it can't be edited from here")
            continue
        order = first.get("msg_codes") or sorted(c for c, r in records.items() if str(r.get("message_id")) == mid)
        chunk = []
        for code in order:
            r = records.get(code) or {}
            chunk.append({"code": code, "rewards": r.get("rewards"), "sources": r.get("sources", []),
                          "expired": bool(r.get("expired_at"))})
        part = tuple(first.get("msg_part") or (1, 1))
        payload = codes_card(game, chunk, s, s.ping("codes", game.key), int(first.get("posted_at") or ctx.now), part)
        res = await ctx.webhook.edit(webhook, mid, payload)
        if res.ok:
            ctx.report.append(f"🧊 {game.short}: marked expired on the posted card: {', '.join(dead)}")
        else:
            ctx.warnings.append(f"{game.short}: could not edit the code card {mid} ({res.status}) {res.error}")
