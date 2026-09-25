"""Redemption-code poster.

Accuracy gate (a code is posted only when ONE of these is true):
  * it comes from an OFFICIAL source — HoYoLAB livestream module, an official tweet /
    HoYoLAB post that explicitly lists redemption codes;
  * hoyo-codes.seria.moe reports it as redeem-validated (status OK);
  * at least CODES_MIN_SOURCES (default 2) independent community sources agree
    (ennead / fandom wiki / PromoGacha). Single-source codes wait as 'pending'
    (up to 14 days) until a second source confirms them.
First run for a game = silent seed (existing codes are recorded, not posted).
"""

from __future__ import annotations

import logging

from .cards import codes_payloads
from .config import Game
from .discord import webhook_fingerprint
from .models import CodeHit
from .sources.codes import extract_codes_from_text

log = logging.getLogger("gamexpress.codes")

REWARD_PREFERENCE = ("seria", "ennead", "hoyolab", "codehub", "fandom", "x")
OFFICIAL = {"hoyolab", "x"}
PENDING_DAYS = 14
LAST_SEEN_GRANULARITY = 12 * 3600


def official_hits_from_items(items) -> list[CodeHit]:
    hits: list[CodeHit] = []
    for it in items:
        if not it.official:
            continue
        for code in extract_codes_from_text(it.full):
            hits.append(CodeHit(code, "x" if it.source == "x" else "hoyolab", None, verified=True, url=it.url))
    return hits


def group_hits(hits: list[CodeHit]) -> dict[str, dict]:
    grouped: dict[str, dict] = {}
    for h in hits:
        g = grouped.setdefault(h.code, {"sources": set(), "verified": False, "rewards": {}, "urls": []})
        g["sources"].add(h.source)
        g["verified"] = g["verified"] or h.verified
        if h.rewards:
            g["rewards"].setdefault(h.source, h.rewards)
        if h.url:
            g["urls"].append(h.url)
    for g in grouped.values():
        g["best_rewards"] = next((g["rewards"][s] for s in REWARD_PREFERENCE if s in g["rewards"]), None)
    return grouped


def passes_gate(info: dict, min_sources: int) -> bool:
    if info["verified"] or info["sources"] & OFFICIAL:
        return True
    return len(info["sources"]) >= min_sources


async def run(ctx) -> None:
    s, now = ctx.settings, ctx.now
    for game in ctx.games:
        specs = [x for x in game.codes.get("sources", []) if x]
        if not specs:
            continue
        hits: list[CodeHit] = []
        reachable = 0
        for spec in specs:
            if spec == "x":
                continue
            res = await ctx.code_sources.fetch(spec)
            if res is None:
                continue
            reachable += 1
            hits.extend(res)
        official = official_hits_from_items(ctx.items.get(game.key, []))
        hits.extend(official)
        if not reachable and not official:
            ctx.warnings.append(f"{game.short}: every code source was unreachable this run")
            continue
        grouped = group_hits(hits)
        records = ctx.state.code_records(game.key)
        bootstrapped = ctx.state.is_bootstrapped("codes", game.key)
        min_sources = int(game.codes.get("min_sources") or s.codes_min_sources)
        to_post: list[dict] = []
        for code, info in sorted(grouped.items()):
            rec = records.get(code)
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
            if passes_gate(info, min_sources):
                to_post.append({"code": code, "rewards": info["best_rewards"],
                                "sources": sorted(info["sources"])})
                records[code] = {**(rec or {}), "status": "posting", "first_seen": (rec or {}).get("first_seen", now),
                                 "last_seen": now, "sources": sorted(info["sources"]),
                                 "rewards": info["best_rewards"]}
            elif not rec:
                records[code] = {"status": "pending", "first_seen": now, "last_seen": now,
                                 "sources": sorted(info["sources"]), "rewards": info["best_rewards"]}
                ctx.report.append(f"⏳ {game.short} {code}: pending (only {', '.join(sorted(info['sources']))})")
        # expire stale pending codes
        for rec in list(records.values()):
            if rec.get("status") == "pending" and now - int(rec.get("first_seen") or now) > PENDING_DAYS * 86400:
                rec["status"] = "rejected"
        if not bootstrapped:
            ctx.state.mark_bootstrapped("codes", game.key)
            if not s.bootstrap_post:
                seeded = sum(1 for r in records.values() if r.get("status") == "seeded")
                ctx.report.append(f"🌱 {game.short}: seeded {seeded} existing codes silently (first run)")
        if not to_post:
            continue
        await _post(ctx, game, to_post, records)


async def _post(ctx, game: Game, codes: list[dict], records: dict) -> None:
    s = ctx.settings
    webhook = s.webhook("codes", game.key)
    if not webhook:
        for c in codes:
            records[c["code"]]["status"] = "pending"
        ctx.report.append(f"⚠️ {game.short}: {len(codes)} new code(s) but no DISCORD_WEBHOOK_CODES configured")
        return
    ping = s.ping("codes", game.key)
    payloads = codes_payloads(game, codes, s, ping, ctx.now)
    chunk_size = 10
    for i, payload in enumerate(payloads):
        chunk = codes[i * chunk_size:(i + 1) * chunk_size]
        res = await ctx.webhook.send(webhook, payload)
        for c in chunk:
            rec = records[c["code"]]
            if res.ok:
                rec.update({"status": "posted", "posted_at": ctx.now, "message_id": res.message_id,
                            "webhook_fp": webhook_fingerprint(webhook)})
            else:
                rec["status"] = "pending"     # retried next run
        if res.ok:
            ctx.report.append(f"🎁 {game.short}: posted {len(chunk)} code(s): {', '.join(c['code'] for c in chunk)}")
        else:
            ctx.errors.append(f"{game.short}: code post failed ({res.status}) {res.error}")
