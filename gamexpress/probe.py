"""Debug ONE real schedule post: what the fetch found, and what the card would show.

    python -m gamexpress probe starrail:4.6      (Actions: mode=live + the `probe` input)

It answers the question the HSR 4.6 card got wrong — which announcement did we link, and whose
picture is that? — so for one game+version it prints:

  1. THE LOOKBACK WINDOW   every official post the run saw, and which of them matched the
                           version. This is what built the card you already have.
  2. WHAT IS STORED        the card as it stands right now: its link, its source, its picture
                           and its times.
  3. THE PROGRAM LOOKUP    the news page first, then HoYoLAB — tab by tab, with the air time
                           parsed out of the article text and EVERY image it found, ranked and
                           explained. Same code a real run uses (runner.find_program).
  4. THE FINISHED CARD     what the merge would change, then the card JSON (paste it into
                           discohook.app) plus Discord's limit check.

Read-only by construction: it never posts, never edits a message and never writes the state
file — it only reads it, which is how it can show you the card you already have.
"""

from __future__ import annotations

import copy
import json
import logging
import time

import aiohttp

from . import schedule
from .cards import schedule_payload, validate_payload
from .config import load_games, load_overrides, load_settings
from .discord import WebhookClient
from .http import BOT_UA, Fetcher
from .media import rank, why
from .runner import Ctx, _gather_game, find_program, gather_versions
from .sources.codes import CodeSources
from .sources.twitter import XClient
from .state import State
from .textutil import version_key
from .timeparse import discord_ts

log = logging.getLogger("gamexpress.probe")
RULE = "─" * 78


def parse_target(raw: str, games: dict) -> tuple[str, str]:
    """'starrail:4.6' -> ('starrail', '4.6');  'starrail' -> ('starrail', '') = newest tracked.
    Raises ValueError with a message that is worth printing."""
    raw = (raw or "").strip()
    if not raw:
        raise ValueError("nothing to probe — use game:version, e.g. starrail:4.6")
    key, _, ver = raw.partition(":")
    key = key.strip().lower()
    if key not in games:
        raise ValueError(f"unknown game '{key.strip()}' (use one of: {', '.join(games)})")
    return key, ver.strip()


def candidate_lines(images: list[str] | None) -> list[str]:
    """Every image the lookup found, in the order the card will use them, and why."""
    ranked = rank(images)
    if not ranked:
        return ["    (none — the card would show no picture at all)"]
    return [f"    {'→' if i == 1 else ' '} {i}. {u}\n         {why(u)}"
            + ("   ← the card shows this one" if i == 1 else "")
            for i, u in enumerate(ranked, 1)]


def changes(before: dict, after: dict) -> list[str]:
    """'key: old → new' for every card field the program lookup would change."""
    out = [f"    {k}: {before.get(k)!r}  →  {after.get(k)!r}"
           for k in sorted(set(before) | set(after)) if before.get(k) != after.get(k)]
    return out or ["    (nothing — the card already shows this announcement)"]


def _ts(value) -> str:
    return f"{discord_ts(int(value), 'F')} or {discord_ts(int(value), 'R')}   (raw {int(value)})" \
        if value else "—"


async def probe(target: str, settings=None) -> int:
    settings = settings or load_settings()
    games = load_games()
    try:
        key, ver = parse_target(target, games)
    except ValueError as exc:
        print(f"✗ probe: {exc}")
        return 2
    g = games[key]
    state = State.load(settings.state_path)                      # READ ONLY — never saved
    records = state.schedule_records(key)
    if not ver:
        tracked = sorted(records, key=version_key)
        if not tracked:
            print(f"✗ probe: {key} has no tracked version yet — pass one, e.g. {key}:4.6")
            return 2
        ver = tracked[-1]
        print(f"(no version given — using the newest tracked: {key}:{ver})")

    session = aiohttp.ClientSession(headers={"User-Agent": BOT_UA})
    try:
        fetcher = Fetcher(session, timeout=settings.http_timeout)
        ctx = Ctx(settings=settings, games=[g], state=state, fetcher=fetcher,
                  webhook=WebhookClient(session, dry_run=True), x=XClient(fetcher, settings),
                  code_sources=CodeSources(fetcher), overrides=load_overrides(),
                  now=int(time.time()))
        await gather_versions(ctx)
        await _gather_game(ctx, g, ctx.now - settings.lookback_hours * 3600)
        items = ctx.items.get(key, [])
        extracts = [e for e in (schedule.extract(g, it) for it in items) if e]
        live = ctx.versions.get(key, {})

        print(RULE)
        print(f"PROBE  {g.name} ({key}) {ver}")
        print(f"live {live.get('live') or '?'} · pre-install {live.get('pre') or '—'} · "
              f"lookback {settings.lookback_hours}h · state {settings.state_path}")

        # ── 1. what the lookback window saw ────────────────────────────────────────────
        print(f"\n1 · WHAT THE LAST {settings.lookback_hours}h SAW  ({len(items)} official item(s))")
        if not items:
            print("    nothing — no source answered, so the card you have was built earlier")
        for e in sorted(extracts, key=lambda x: x.item.published_ts):
            mark = "✓" if e.version == ver else " "
            print(f"  {mark} [{e.kind:11}] {e.version or '?':6} {e.item.source:8} {e.item.title[:70]}")
            print(f"        {e.item.url}")
        for it in items:
            if not any(e.item is it for e in extracts):
                print(f"    [not an announcement] {it.source:8} {it.title[:70]}\n        {it.url}")

        # ── 2. what is stored for this version ─────────────────────────────────────────
        rec = records.get(ver) or {}
        d = rec.get("data") or {}
        print(f"\n2 · WHAT IS STORED FOR {key}:{ver}  (status: {rec.get('status') or 'not tracked'})")
        if not d:
            print("    nothing stored yet — this version has never been seen in an official post")
        else:
            print(f"    title      {d.get('version_name') or g.name} {ver}")
            print(f"    title_url  {d.get('title_url') or '—'}")
            print(f"    source     {d.get('source_url') or '—'}   ({d.get('source_label') or '—'})")
            print(f"    key art    {d.get('media_from') or 'not from a program lookup'}")
            print(f"    air time   {_ts(d.get('program_ts'))}")
            print(f"    maint      {_ts(d.get('maint_start_ts'))}")
            for i, u in enumerate(d.get("images") or ([d["image"]] if d.get("image") else []), 1):
                print(f"    image {i}    {u}")

        # ── 3. the program lookup a real run would do ──────────────────────────────────
        print(f"\n3 · THE PROGRAM LOOKUP for {key}:{ver}")
        trace: list[str] = []
        hit = await find_program(ctx.fetcher, g, ver, ctx.now, trace=trace)
        for line in trace:
            print(f"    {line}")
        if not hit:
            print("    ✗ no program announcement found by EITHER source — the card keeps what it has")
        else:
            print(f"    ✓ {hit.get('source') or 'Official News'}: {hit.get('title')}")
            print(f"      link       {hit['url']}")
            print(f"      video      {hit.get('youtube') or '—'}")
            print(f"      air time   {_ts(hit.get('program_ts'))}")
            print(f"      text       {(hit.get('text') or '')[:280]}…")
            print("      images found, best first:")
            for line in candidate_lines(hit.get("images")):
                print(line)

        # ── 4. the card this would produce ─────────────────────────────────────────────
        print(f"\n4 · THE CARD for {key}:{ver}")
        rec_copy = copy.deepcopy(rec) or {"status": "new", "first_seen": ctx.now}
        before = dict(rec_copy.get("data") or {})
        notes: list[str] = []
        mine = [e for e in extracts if e.version == ver]
        after = schedule.merge(g, ver, mine, rec_copy, (ctx.overrides.get(key) or {}).get(ver, {}),
                               live, ctx.now, notes, None, hit)
        for line in changes(before, after):
            print(line)
        for n in notes:
            print(f"    note: {n}")
        payload = schedule_payload(g, after, settings, settings.ping("schedule", key))
        problems = validate_payload(payload)
        print(f"    card: {len(problems) and 'PROBLEMS: ' + '; '.join(problems) or 'within Discord limits ✓'}")
        print(json.dumps(payload, indent=2, ensure_ascii=False))

        print(f"\nsources: {ctx.fetcher.summary()}")
        print(f"read-only: nothing was posted or edited, and {settings.state_path} was NOT written")
        return 0
    finally:
        await session.close()
