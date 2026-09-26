"""One monitor run: fail-over check → gather official items once → schedule → codes → save."""

from __future__ import annotations

import asyncio
import logging
import os
import time
from dataclasses import dataclass, field

import aiohttp

from . import __version__, codeposter, schedule
from .config import Game, Settings, active_games, load_games, load_overrides
from .discord import WebhookClient
from .http import BOT_UA, Fetcher, Probe
from .models import Item
from .sources import countdown, hoyolab, kuro, launcher, newspage
from .sources.codes import CodeSources
from .sources.twitter import XClient
from .state import State
from .textutil import version_key

log = logging.getLogger("gamexpress")


@dataclass
class Ctx:
    settings: Settings
    games: list[Game]
    state: State
    fetcher: Fetcher
    webhook: WebhookClient
    x: XClient
    code_sources: CodeSources
    overrides: dict
    now: int
    versions: dict = field(default_factory=dict)
    items: dict[str, list[Item]] = field(default_factory=dict)
    reachable: dict[str, bool] = field(default_factory=dict)   # did ANY source answer for this game?
    report: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    active: bool = True
    elapsed: float = 0.0
    estimates: dict = field(default_factory=dict)   # game key -> countdown-site estimate
    media: dict = field(default_factory=dict)       # game key -> version -> program announcement


async def gather_versions(ctx: Ctx) -> None:
    need_hyp = any(g.launcher.get("type") == "hoyoplay" for g in ctx.games)
    need_kuro = any(g.launcher.get("type") == "kuro" for g in ctx.games)

    async def none() -> dict:
        return {}
    hyp, kr = await asyncio.gather(launcher.hoyoplay_versions(ctx.fetcher) if need_hyp else none(),
                                   kuro.launcher_versions(ctx.fetcher) if need_kuro else none())
    for g in ctx.games:
        t = g.launcher.get("type")
        if t == "hoyoplay" and g.launcher.get("game_id") in hyp:
            ctx.versions[g.key] = hyp[g.launcher["game_id"]]
        elif t == "kuro" and kr:
            ctx.versions[g.key] = kr


async def _gather_game(ctx: Ctx, g: Game, since: int) -> None:
    want = schedule.wants(g)
    probe = Probe(ctx.fetcher)              # counts THIS game's answers while games run in parallel
    parts = await asyncio.gather(hoyolab.fetch_items(probe, g, want, since),
                                 kuro.fetch_items(probe, g, want, since),
                                 ctx.x.items(g, want, since))
    items: list[Item] = [it for part in parts for it in part]
    ctx.items[g.key] = items
    ctx.reachable[g.key] = probe.ok > 0 or any(a.lower() in ctx.x.reachable for a in g.x_accounts)
    icons = ctx.state.data.setdefault("icons", {})
    fresh = next((ctx.x.avatars[a.lower()] for a in g.x_accounts if a.lower() in ctx.x.avatars), None)
    if fresh and icons.get(g.key) != fresh:
        icons[g.key] = fresh
    g.icon = icons.get(g.key) or g.icon
    log.info("[%s] %d official item(s) matched in the last %dh (live %s, pre-install %s)", g.key,
             len(items), ctx.settings.lookback_hours, ctx.versions.get(g.key, {}).get("live") or "?",
             ctx.versions.get(g.key, {}).get("pre") or "—")


async def gather_estimates(ctx: Ctx) -> None:
    """Ask the countdown sites — only for games that still miss a program / maintenance time,
    and only when the schedule feature is on (COUNTDOWN_ESTIMATES=0 switches it off)."""
    if "schedule" not in ctx.settings.features or not ctx.settings.countdown_estimates:
        return
    keys = [g.key for g in ctx.games if schedule.needs_estimate(ctx.state, g.key, ctx.now)]
    if not keys:
        return
    got = await asyncio.gather(*(countdown.fetch_game(ctx.fetcher, k, ctx.now) for k in keys))
    for key, est in zip(keys, got):
        if est:
            ctx.estimates[key] = est
            log.info("[%s] countdown estimate: %s", key, est)


async def find_program(fetcher, g: Game, ver: str, now: int) -> dict | None:
    """THE program lookup, in one place: the official news page first (it archives every
    announcement and carries the key art), then the HoYoLAB news list, which is paged back past
    the lookback window.

    -> {'url','title','images','youtube','text','ts','program_ts','source'} or None."""
    hit = await newspage.fetch_program(fetcher, g, ver, now)
    if not hit and getattr(g, "program_feeds", None):
        hit = await newspage.fetch_program_feed(fetcher, g, ver, now)
    if not hit:
        hit = await hoyolab.find_program(fetcher, g, ver)
    if not hit:
        return None
    # the air time comes from the article's own text, through the same extractor that
    # every other official post goes through — no separate date parsing here
    item = Item(source="hoyolab", game=g.key, id=ver, url=hit["url"], title=hit.get("title") or "",
                text=hit.get("text") or "", published_ts=hit.get("ts") or now,
                images=list(hit.get("images") or []))
    fields = schedule.extract_program(g, item)
    hit["program_ts"] = fields.get("program_ts")
    hit["youtube"] = hit.get("youtube") or fields.get("youtube_video")
    hit["images"] = hit.get("images") or fields.get("images") or []
    return hit


async def gather_program_media(ctx: Ctx) -> None:
    """Find the program announcement for every current version whose card would otherwise show
    somebody else's post. Versions come from this run as well as from state, so a first run and
    every test run (whose state starts empty) still performs the lookup."""
    if "schedule" not in ctx.settings.features or not ctx.settings.program_media:
        return
    jobs: list[tuple[Game, str]] = []
    for g in ctx.games:
        records = ctx.state.schedule_records(g.key) or {}
        by_version = schedule.version_extracts(ctx, g)
        todo = [v for v in by_version
                if schedule.needs_program_lookup(by_version[v], records.get(v, {}), ctx.now)]
        for ver, rec in records.items():
            if ver not in by_version and schedule.needs_program_lookup([], rec, ctx.now):
                todo.append(ver)
        jobs += [(g, v) for v in sorted(set(todo), key=version_key)]
    if not jobs:
        return
    hits = await asyncio.gather(*(find_program(ctx.fetcher, g, ver, ctx.now) for g, ver in jobs))
    for (g, ver), hit in zip(jobs, hits):
        if hit:
            ctx.media.setdefault(g.key, {})[ver] = hit
    for key in {g.key for g, _ in jobs}:
        found = ctx.media.get(key) or {}
        if found:
            log.info("[%s] program announcement found for %s", key, ", ".join(sorted(found)))
        else:
            log.info("[%s] no program announcement found on the official news page, its feed "
                     "mirror or HoYoLAB — the card keeps its current link", key)


async def gather_items(ctx: Ctx) -> None:
    """Every game is gathered concurrently (HoYoLAB lists + full posts, Kuro, X timelines),
    capped by the Fetcher's global request limit."""
    since = ctx.now - ctx.settings.lookback_hours * 3600
    await asyncio.gather(*(_gather_game(ctx, g, since) for g in ctx.games))


async def failover_check(ctx: Ctx) -> None:
    s = ctx.settings
    if not s.peer_state_url:
        if s.instance_role == "standby":
            ctx.active = False
            ctx.report.append("💤 standby without PEER_STATE_URL — passive (set ENABLED_FEATURES / role to activate)")
        return
    peer = await ctx.fetcher.get_json(s.peer_state_url, source="peer-state",
                                      headers={"Cache-Control": "no-cache"}, retries=1)
    if isinstance(peer, dict):
        n = ctx.state.merge_peer(peer)
        if n:
            ctx.report.append(f"🔄 imported {n} posted key(s) from the peer instance")
    if s.instance_role != "standby":
        return
    if not isinstance(peer, dict):
        ctx.active = False
        ctx.report.append("💤 standby: peer state unreachable — staying passive (never risks a double post)")
        return
    hb = peer.get("heartbeat") or {}
    last = int(hb.get("last_success") or 0)
    age_min = (ctx.now - last) / 60 if last else 10 ** 9
    # never fail over faster than 2.5x the primary's own heartbeat interval
    threshold = max(s.failover_after_min, int(2.5 * int(hb.get("every_min") or 0)))
    if age_min < threshold:
        ctx.active = False
        ctx.report.append(f"💤 standby: primary healthy (heartbeat {age_min:.0f} min ago) — passive")
    else:
        ctx.report.append(f"🚨 FAIL-OVER: primary heartbeat is {age_min:.0f} min old (> {threshold}) "
                          f"— this standby is now posting")


async def run_once(settings: Settings, games_all: dict[str, Game] | None = None,
                   overrides: dict | None = None, session: aiohttp.ClientSession | None = None) -> Ctx:
    games_all = games_all if games_all is not None else load_games()
    overrides = overrides if overrides is not None else load_overrides()
    state = State.load(settings.state_path)
    own_session = session is None
    session = session or aiohttp.ClientSession(headers={"User-Agent": BOT_UA})
    try:
        started = time.monotonic()
        fetcher = Fetcher(session, timeout=settings.http_timeout)
        ctx = Ctx(settings=settings, games=active_games(games_all, settings), state=state, fetcher=fetcher,
                  webhook=WebhookClient(session, dry_run=settings.dry_run), x=XClient(fetcher, settings),
                  code_sources=CodeSources(fetcher), overrides=overrides, now=int(time.time()))
        await failover_check(ctx)
        features = settings.features if ctx.active else set()
        if features and ctx.games:
            await gather_versions(ctx)
            await gather_items(ctx)
            await asyncio.gather(gather_program_media(ctx), gather_estimates(ctx))
            for g in ctx.games:
                if not ctx.reachable.get(g.key, True):
                    ctx.warnings.append(f"{g.short}: no announcement source answered this run — the next run "
                                        f"re-reads the last {settings.lookback_hours}h, so nothing is missed")
            if "schedule" in features:
                await schedule.run(ctx)
            if "codes" in features:
                await codeposter.run(ctx)
        if not features:
            ctx.report.append("⏸️ no active features this run (ENABLED_FEATURES=none or passive standby)")
        ephemeral = settings.dry_run or settings.test_mode
        if ctx.active and features and not ctx.errors and not ephemeral:
            state.heartbeat(settings.instance_name, __version__, settings.heartbeat_min, ctx.now)
        state.prune(ctx.now)
        if not ephemeral:
            if state.save():
                log.info("state saved -> %s", settings.state_path)
        elif settings.test_mode:
            ctx.report.insert(0, "🧪 TEST MODE — cards are marked TEST, the state file is NOT saved")
        log.info("sources: %s", fetcher.summary())
        ctx.elapsed = time.monotonic() - started
        write_summary(ctx)
        return ctx
    finally:
        if own_session:
            await session.close()


def write_summary(ctx: Ctx) -> None:
    lines = [f"### Game-Express {__version__} — {ctx.settings.instance_name} ({ctx.settings.instance_role})"]
    if ctx.settings.dry_run:
        lines.append("> **DRY RUN** — nothing was posted or saved; \"posted\" below means *would post*. "
                     "The full card JSON is in the job log (paste it into discohook.app to see it).")
    elif ctx.settings.test_mode:
        lines.append("> **TEST MODE** — cards are labelled 🧪 TEST and the state file is not saved.")
    lines += [f"- {r}" for r in ctx.report] or ["- nothing new (no matching announcements / codes)"]
    for w in ctx.warnings:
        lines.append(f"- ⚠️ {w}")
        print(f"::warning::{w}")
    for e in ctx.errors:
        lines.append(f"- ❌ {e}")
        print(f"::error::{e}")
    lines.append(f"- sources: {ctx.fetcher.summary()}")
    if ctx.elapsed:
        lines.append(f"- ⏱️ run took {ctx.elapsed:.1f}s")
    text = "\n".join(lines)
    log.info("\n%s", text)
    path = os.getenv("GITHUB_STEP_SUMMARY")
    if path:
        try:
            with open(path, "a", encoding="utf-8") as fh:
                fh.write(text + "\n")
        except OSError:
            pass
