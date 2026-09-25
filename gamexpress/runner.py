"""One monitor run: fail-over check → gather official items once → schedule → codes → save."""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass, field

import aiohttp

from . import __version__, codeposter, schedule
from .config import Game, Settings, active_games, load_games, load_overrides
from .discord import WebhookClient
from .http import BOT_UA, Fetcher
from .models import Item
from .sources import hoyolab, kuro, launcher
from .sources.codes import CodeSources
from .sources.twitter import XClient
from .state import State

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


async def gather_versions(ctx: Ctx) -> None:
    need_hyp = any(g.launcher.get("type") == "hoyoplay" for g in ctx.games)
    need_kuro = any(g.launcher.get("type") == "kuro" for g in ctx.games)
    hyp = await launcher.hoyoplay_versions(ctx.fetcher) if need_hyp else {}
    kr = await kuro.launcher_versions(ctx.fetcher) if need_kuro else {}
    for g in ctx.games:
        t = g.launcher.get("type")
        if t == "hoyoplay" and g.launcher.get("game_id") in hyp:
            ctx.versions[g.key] = hyp[g.launcher["game_id"]]
        elif t == "kuro" and kr:
            ctx.versions[g.key] = kr


async def gather_items(ctx: Ctx) -> None:
    since = ctx.now - ctx.settings.lookback_hours * 3600
    for g in ctx.games:
        want = schedule.wants(g)
        ok_before = sum(h.ok for h in ctx.fetcher.health.values())
        items: list[Item] = []
        items += await hoyolab.fetch_items(ctx.fetcher, g, want, since)
        items += await kuro.fetch_items(ctx.fetcher, g, want, since)
        items += await ctx.x.items(g, want, since)
        ctx.items[g.key] = items
        ctx.reachable[g.key] = sum(h.ok for h in ctx.fetcher.health.values()) > ok_before
        icons = ctx.state.data.setdefault("icons", {})
        fresh = next((ctx.x.avatars[a.lower()] for a in g.x_accounts if a.lower() in ctx.x.avatars), None)
        if fresh and icons.get(g.key) != fresh:
            icons[g.key] = fresh
        g.icon = icons.get(g.key) or g.icon
        log.info("[%s] %d official item(s) matched in the last %dh (live %s, pre-install %s)", g.key,
                 len(items), ctx.settings.lookback_hours, ctx.versions.get(g.key, {}).get("live") or "?",
                 ctx.versions.get(g.key, {}).get("pre") or "—")


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
        fetcher = Fetcher(session, timeout=settings.http_timeout)
        ctx = Ctx(settings=settings, games=active_games(games_all, settings), state=state, fetcher=fetcher,
                  webhook=WebhookClient(session, dry_run=settings.dry_run), x=XClient(fetcher, settings),
                  code_sources=CodeSources(fetcher), overrides=overrides, now=int(time.time()))
        await failover_check(ctx)
        features = settings.features if ctx.active else set()
        if features and ctx.games:
            await gather_versions(ctx)
            await gather_items(ctx)
            if "schedule" in features:
                await schedule.run(ctx)
            if "codes" in features:
                await codeposter.run(ctx)
        if not features:
            ctx.report.append("⏸️ no active features this run (ENABLED_FEATURES=none or passive standby)")
        if ctx.active and features and not ctx.errors and not settings.dry_run:
            state.heartbeat(settings.instance_name, __version__, settings.heartbeat_min, ctx.now)
        state.prune(ctx.now)
        if not settings.dry_run:
            if state.save():
                log.info("state saved -> %s", settings.state_path)
        log.info("sources: %s", fetcher.summary())
        write_summary(ctx)
        return ctx
    finally:
        if own_session:
            await session.close()


def write_summary(ctx: Ctx) -> None:
    lines = [f"### Game-Express {__version__} — {ctx.settings.instance_name} ({ctx.settings.instance_role})"]
    lines += [f"- {r}" for r in ctx.report] or ["- nothing new (no matching announcements / codes)"]
    for w in ctx.warnings:
        lines.append(f"- ⚠️ {w}")
        print(f"::warning::{w}")
    for e in ctx.errors:
        lines.append(f"- ❌ {e}")
        print(f"::error::{e}")
    lines.append(f"- sources: {ctx.fetcher.summary()}")
    text = "\n".join(lines)
    log.info("\n%s", text)
    path = os.getenv("GITHUB_STEP_SUMMARY")
    if path:
        try:
            with open(path, "a", encoding="utf-8") as fh:
                fh.write(text + "\n")
        except OSError:
            pass
