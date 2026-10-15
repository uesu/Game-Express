"""One monitor run: fail-over check → gather official items once → schedule → codes → save."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import pathlib
import platform
import time
from dataclasses import dataclass, field
from typing import Any

import aiohttp

from . import build_id, codeposter, schedule
from .config import Game, Settings, active_games, load_games, load_overrides
from .discord import WebhookClient, webhook_fingerprint
from .http import (
    BOT_UA,
    Fetcher,
    Probe,
    redact_text,
    redact_url,
    redact_value,
)
from .models import Item
from .sources import bannerfeed, countdown, hoyolab, kuro, launcher, newspage
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
    banners: dict = field(default_factory=dict)     # game key -> list of 5★ rate-up banners
    state_load_status: str = "loaded_local"
    state_save_status: str = "unchanged_local"
    execution_result: str = "success"
    started_at: int = 0
    finished_at: int = 0


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
    x_out = ctx.x.game_outcomes.get(g.key, {})
    parsed_total = int(x_out.get("parsed_count", 0)) + len(parts[0]) + len(parts[1])
    usable_total = int(x_out.get("usable_count", 0)) + len(parts[0]) + len(parts[1])
    ctx.fetcher.record_source_outcome(
        source="official_feeds",
        lane="announcements",
        game=g.key,
        transport_status="http_ok" if ctx.reachable[g.key] else "network_error",
        parsed_count=max(parsed_total, len(items)),
        usable_count=max(usable_total, len(items)),
        selected_count=len(items),
        fallback_used=bool(x_out.get("fallback_used", False)),
        reason="" if ctx.reachable[g.key] else "no_announcement_source_answered",
    )
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


async def gather_banners(ctx: Ctx) -> None:
    """Fetch the community banner feed (ertezy.github.io/Kitsudock-data/hub.json) — one request
    per run for all games. Refused when older than 14 days, and BANNER_FEED=0 switches it off."""
    if "schedule" not in ctx.settings.features or not ctx.settings.banner_feed:
        return
    try:
        ctx.banners = await bannerfeed.fetch_banners(ctx.fetcher, ctx.now)
    except Exception as e:
        log.warning("gather_banners failed: %s", e)


async def find_program(ctx, g: Game, ver: str) -> dict | None:
    """THE program lookup, in one place, X first.

    X is the primary source because it is the only one that reliably carries BOTH halves of what
    the card needs — the announcement's own URL and its key art at `?name=orig`. Every source
    below it is a backup, in the order it proved itself:

      1. X           config/program_announcements.json -> fxtwitter by id (a seeded id resolves
                     weeks later), else the nitter timeline (nitter.cf first). This is what fixed
                     the 2026-09-27 run, where all three HoYoverse games got "no program
                     announcement found" and WW linked a lore article instead.
      2. HoYoLAB     the official news list, paged back past the lookback window. Good text and
                     timestamps; its image list is often a small article cover.
      3. news page   the official site's news index, which archives every announcement.
      4. feed mirror its RSS/Atom mirror (Kuro's site is a JS build the scraper cannot read).

    -> {'url','title','images','youtube','text','ts','program_ts','source'} or None."""
    now = ctx.now
    source_url = ""
    item: Item | None = None
    if getattr(ctx, "x", None) is not None and ctx.settings.x_enabled:
        item = await ctx.x.program_tweet(g, ver)
    hit: dict | None = None
    if item:
        source_url = item.url
        hit = {"url": item.url, "title": "", "images": list(item.images or []),
               "youtube": "", "text": item.text, "ts": item.published_ts or now, "source": "x"}
    if not hit:
        hit = await hoyolab.find_program(ctx.fetcher, g, ver)
    if not hit:
        hit = await newspage.fetch_program(ctx.fetcher, g, ver, now)
    if not hit and getattr(g, "program_feeds", None):
        hit = await newspage.fetch_program_feed(ctx.fetcher, g, ver, now)
    if not hit:
        return None
    # the air time comes from the article's own text, through the same extractor that
    # every other official post goes through — no separate date parsing here
    found = Item(source=hit.get("source") or "hoyolab", game=g.key, id=ver,
                 url=source_url or hit["url"], title=hit.get("title") or "",
                 text=hit.get("text") or "", published_ts=hit.get("ts") or now,
                 images=list(hit.get("images") or []))
    fields = schedule.extract_program(g, found)
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
                if schedule.needs_program_lookup(by_version[v], records.get(v, {}), ctx.now, g.key)]
        for ver, rec in records.items():
            if ver not in by_version and schedule.needs_program_lookup([], rec, ctx.now, g.key):
                todo.append(ver)
        jobs += [(g, v) for v in sorted(set(todo), key=version_key)]
        # Cards the lookup cannot help, said once. A version whose announcement never arrived
        # and whose tweet id is not cached is otherwise unreachable: it keeps the notice's
        # cover and link for ever, the lookup no longer runs, and the summary shows a card
        # that looks merely stale. That is the Genshin 7.1 state minus the cache — the one
        # thing the operator can fix, and only if somebody tells them.
        for ver, rec in records.items():
            reason = schedule.announcement_gap(rec, g.key, ctx.now)
            if not reason:
                rec.pop("announce_gap", None)      # repaired, or never needed one
            elif rec.get("announce_gap") != reason:
                rec["announce_gap"] = reason
                ctx.report.append(f"🩹 {g.short} {ver}: {reason}")
    if not jobs:
        return
    hits = await asyncio.gather(*(find_program(ctx, g, ver) for g, ver in jobs))
    for (g, ver), hit in zip(jobs, hits):
        if hit:
            ctx.media.setdefault(g.key, {})[ver] = hit
    wanted: dict[str, list[str]] = {}
    shorts = {}
    for g, ver in jobs:
        wanted.setdefault(g.key, []).append(ver)
        shorts[g.key] = g.short
    for key, vers in wanted.items():
        found = ctx.media.get(key) or {}
        if found:
            log.info("[%s] program announcement found for %s (source: %s)", key,
                     ", ".join(sorted(found)),
                     ", ".join(sorted({(found[v].get("source") or "?") for v in found})))
        else:
            log.info("[%s] no program announcement found on X, HoYoLAB, the official news page "
                     "or its feed mirror — the card keeps its current link", key)
        missed = [v for v in vers if v not in found]
        if missed:
            # A lookup only runs for a version that needs one, so this is never chatter: it is
            # the other half of the "announcement found" line. Without it, a card with no air
            # time and no link looks like a rendering bug, when what happened is that every
            # source was asked and none answered. It stops by itself -- the moment one answers,
            # media_from is set and needs_program_lookup() returns False for good.
            ctx.report.append(f"🔍 {shorts[key]} {', '.join(sorted(missed))}: no Special Program "
                              f"announcement found (X, HoYoLAB, official news page) — the card "
                              f"keeps its current link; the lookup runs again next run")


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
            if ctx.state_load_status == "fresh_bootstrap":
                ctx.state_load_status = "recovered_from_peer"
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


def _instrument_webhook(webhook: WebhookClient) -> None:
    """Attach redacted delivery telemetry to `webhook.deliveries` without altering `webhook.sent`."""
    deliveries: list[dict[str, Any]] = []
    webhook.deliveries = deliveries  # type: ignore[attr-defined]
    orig_send = webhook.send
    orig_edit = webhook.edit

    def _record_delivery(method: str, webhook_url: str, res: Any, fallback_id: str = "", err_str: str = "") -> None:
        try:
            if isinstance(res, bool):
                ok = res
                status = 200 if ok else 0
                msg_id = fallback_id
                err = err_str
            elif isinstance(res, dict):
                ok = bool(res.get("ok", True))
                status = int(res.get("status", 200 if ok else 0))
                msg_id = str(res.get("message_id") or fallback_id or "")
                err = str(res.get("error") or err_str or "")
            elif res is not None:
                ok = bool(getattr(res, "ok", False))
                status = int(getattr(res, "status", 0) or 0)
                msg_id = str(getattr(res, "message_id", None) or fallback_id or "")
                err = str(getattr(res, "error", "") or err_str or "")
            else:
                ok = False
                status = 0
                msg_id = fallback_id
                err = err_str
            deliveries.append(
                {
                    "method": method,
                    "target": redact_url(webhook_url),
                    "fingerprint": webhook_fingerprint(webhook_url),
                    "ok": ok,
                    "status": status,
                    "message_id": msg_id or None,
                    "error": redact_text(err)[:160] if err else "",
                }
            )
        except Exception:
            pass

    async def _tracked_send(webhook_url: str, payload: dict):
        try:
            res = await orig_send(webhook_url, payload)
        except Exception as exc:
            _record_delivery("POST", webhook_url, None, err_str=f"{type(exc).__name__}: {exc}")
            raise
        _record_delivery("POST", webhook_url, res)
        return res

    async def _tracked_edit(webhook_url: str, message_id: str, payload: dict):
        try:
            res = await orig_edit(webhook_url, message_id, payload)
        except Exception as exc:
            _record_delivery("PATCH", webhook_url, None, fallback_id=message_id, err_str=f"{type(exc).__name__}: {exc}")
            raise
        _record_delivery("PATCH", webhook_url, res, fallback_id=message_id)
        return res

    webhook.send = _tracked_send  # type: ignore[method-assign]
    webhook.edit = _tracked_edit  # type: ignore[method-assign]


async def run_once(settings: Settings, games_all: dict[str, Game] | None = None,
                   overrides: dict | None = None, session: aiohttp.ClientSession | None = None) -> Ctx:
    games_all = games_all if games_all is not None else load_games()
    overrides = overrides if overrides is not None else load_overrides()
    had_local = settings.state_path.exists()
    state = State.load(settings.state_path)
    has_records = bool(
        state.data.get("bootstrapped")
        or state.data.get("schedule")
        or state.data.get("codes")
    )
    initial_load_status = "loaded_local" if (had_local and has_records) else "fresh_bootstrap"
    own_session = session is None
    session = session or aiohttp.ClientSession(headers={"User-Agent": BOT_UA})
    ctx: Ctx | None = None
    started = time.monotonic()
    started_wall = int(time.time())
    try:
        fetcher = Fetcher(session, timeout=settings.http_timeout)
        webhook = WebhookClient(session, dry_run=settings.dry_run)
        _instrument_webhook(webhook)
        ctx = Ctx(settings=settings, games=active_games(games_all, settings), state=state, fetcher=fetcher,
                  webhook=webhook, x=XClient(fetcher, settings),
                  code_sources=CodeSources(fetcher), overrides=overrides, now=started_wall,
                  state_load_status=initial_load_status, started_at=started_wall)
        await failover_check(ctx)
        features = settings.features if ctx.active else set()
        if features and ctx.games:
            await gather_versions(ctx)
            await gather_items(ctx)
            await asyncio.gather(gather_program_media(ctx), gather_estimates(ctx), gather_banners(ctx))
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
            state.heartbeat(settings.instance_name, settings.heartbeat_min, ctx.now)
        state.prune(ctx.now)
        if not ephemeral:
            try:
                saved = state.save()
            except Exception as save_exc:
                ctx.state_save_status = "failed_local"
                ctx.execution_result = "failed"
                ctx.errors.append(f"state save failed: {type(save_exc).__name__}: {save_exc}")
                raise
            if saved:
                ctx.state_save_status = "saved_local"
                log.info("state saved -> %s", settings.state_path)
            else:
                ctx.state_save_status = "unchanged_local"
        elif settings.test_mode:
            ctx.state_save_status = "unchanged_local"
            ctx.report.insert(0, "🧪 TEST MODE — every card below is a NEW message marked TEST, built "
                                 "from this run's live data. No live card was edited, no copy was "
                                 "touched and the state file was NOT saved. Delete the test cards "
                                 "when you are done")
        ctx.execution_result = "partial" if ctx.errors else "success"
        log.info("sources: %s", fetcher.summary())
        ctx.elapsed = time.monotonic() - started
        ctx.finished_at = int(time.time())
        write_summary(ctx)
        return ctx
    except Exception as exc:
        if ctx is not None:
            try:
                ctx.execution_result = "failed"
                if ctx.state_save_status == "unchanged_local" and not (settings.dry_run or settings.test_mode):
                    ctx.state_save_status = "not_reached"
                err_msg = f"{type(exc).__name__}: {exc}"
                if err_msg not in ctx.errors and f"state save failed: {err_msg}" not in ctx.errors:
                    ctx.errors.append(err_msg)
                ctx.elapsed = time.monotonic() - started
                ctx.finished_at = int(time.time())
                write_run_report(ctx)
            except Exception:
                pass
        raise
    finally:
        if own_session:
            await session.close()


def build_run_report(ctx: Ctx) -> dict[str, Any]:
    """Build a bounded, redacted JSON report for `.github/scripts/render_run_summary.py`."""
    s = ctx.settings
    deliveries: list[dict[str, Any]] = list(getattr(ctx.webhook, "deliveries", []))
    posted_count = sum(1 for d in deliveries if d.get("method") == "POST" and d.get("ok"))
    patched_count = sum(1 for d in deliveries if d.get("method") == "PATCH" and d.get("ok"))
    failed_deliveries = sum(1 for d in deliveries if not d.get("ok"))

    if not deliveries and ctx.webhook.sent:
        posted_count = sum(1 for d in ctx.webhook.sent if d.get("method") == "POST")
        patched_count = sum(1 for d in ctx.webhook.sent if d.get("method") == "PATCH")

    source_outcomes = list(ctx.fetcher.source_outcomes)
    for g in ctx.games:
        if g.key in ctx.x.game_outcomes:
            source_outcomes.append(ctx.x.game_outcomes[g.key])
    for probe_out in ctx.x.probe_outcomes[:60]:
        source_outcomes.append(probe_out)

    health_summary = {
        name: {"ok": h.ok, "fail": h.fail, "last_error": redact_text(h.last_error)}
        for name, h in sorted(ctx.fetcher.health.items())
    }

    mode = "test" if s.test_mode else ("dry_run" if s.dry_run else "live")
    only_val = ",".join(sorted(s.features)) if s.features else "none"
    game_val = ",".join(sorted(s.games_filter)) if s.games_filter else "all"
    repost_val = str(s.repost or "")

    raw_report = {
        "schema_version": 1,
        "code_sha": build_id(),
        "python_version": platform.python_version(),
        "runner_image": os.environ.get("GAMEXPRESS_RUNNER_IMAGE", platform.platform()),
        "lock_sha256": os.environ.get("GAMEXPRESS_LOCK_SHA256", ""),
        "setup_duration_s": round(float(os.environ.get("GAMEXPRESS_SETUP_DURATION_S", "0") or 0), 2),
        "instance_name": s.instance_name,
        "instance_role": s.instance_role,
        "mode": mode,
        "only": only_val,
        "game": game_val,
        "repost": repost_val,
        "test_mode": bool(s.test_mode),
        "dry_run": bool(s.dry_run),
        "no_ping": bool(s.no_ping),
        "active": bool(ctx.active),
        "execution_result": ctx.execution_result,
        "started_at": ctx.started_at or ctx.now,
        "finished_at": ctx.finished_at or int(time.time()),
        "duration_s": round(float(ctx.elapsed), 2),
        "state": {
            "load_status": ctx.state_load_status,
            "save_status": ctx.state_save_status,
            "local_save_outcome": ctx.state_save_status,
            "path": str(s.state_path),
        },
        "cards": {
            "posted": posted_count,
            "patched": patched_count,
            "failed": failed_deliveries,
        },
        "report_lines": [redact_text(r) for r in ctx.report],
        "warnings": [redact_text(w) for w in ctx.warnings],
        "errors": [redact_text(e) for e in ctx.errors],
        "sources_summary": redact_text(ctx.fetcher.summary()),
        "source_health": health_summary,
        "source_outcomes": source_outcomes[:120],
        "transport_events": list(ctx.fetcher.events[:120]),
        "webhook_deliveries": deliveries[:100],
    }
    return redact_value(raw_report)


def write_run_report(ctx: Ctx, report_path: str | pathlib.Path | None = None) -> dict[str, Any]:
    """Write the redacted run report JSON to `GAMEXPRESS_RUN_REPORT` when configured."""
    report = build_run_report(ctx)
    target = pathlib.Path(report_path) if report_path else (
        pathlib.Path(os.environ["GAMEXPRESS_RUN_REPORT"])
        if os.environ.get("GAMEXPRESS_RUN_REPORT")
        else None
    )
    if target is not None:
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            runs: list[dict[str, Any]] = []
            if target.is_file():
                try:
                    existing = json.loads(target.read_text(encoding="utf-8"))
                    if isinstance(existing, dict) and isinstance(existing.get("runs"), list):
                        runs = list(existing["runs"])
                except (OSError, json.JSONDecodeError):
                    runs = []
            runs.append(report)
            envelope = dict(report)
            envelope["runs"] = runs
            target.write_text(
                json.dumps(envelope, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
                encoding="utf-8",
            )
        except OSError as exc:
            log.warning("failed to write run report to %s: %s", target, redact_text(str(exc)))
    return report


def write_summary(ctx: Ctx) -> None:
    write_run_report(ctx)
    lines = [f"### Game-Express {build_id()} — {ctx.settings.instance_name} ({ctx.settings.instance_role})"]
    if ctx.settings.dry_run:
        lines.append("> **DRY RUN** — nothing was posted or saved; \"posted\" below means *would post*. "
                     "The full card JSON is in the job log (paste it into discohook.app to see it).")
    elif ctx.settings.test_mode:
        lines.append("> **TEST MODE** — real data, throwaway cards. Every card is a NEW message "
                     "labelled 🧪 TEST, posted from the sources this run actually fetched; live cards "
                     "and their copies are never edited and the state file is not saved. "
                     "Delete the test cards afterwards.")
    lines += [f"- {redact_text(r)}" for r in ctx.report] or ["- nothing new (no matching announcements / codes)"]
    for w in ctx.warnings:
        safe_w = redact_text(w)
        lines.append(f"- ⚠️ {safe_w}")
        print(f"::warning::{safe_w}")
    for e in ctx.errors:
        safe_e = redact_text(e)
        lines.append(f"- ❌ {safe_e}")
        print(f"::error::{safe_e}")
    lines.append(f"- sources: {redact_text(ctx.fetcher.summary())}")
    if ctx.elapsed:
        lines.append(f"- ⏱️ run took {ctx.elapsed:.1f}s")
    text = "\n".join(lines)
    log.info("\n%s", text)
    path = os.getenv("GITHUB_STEP_SUMMARY")
    if path and not os.getenv("GAMEXPRESS_RUN_REPORT"):
        try:
            with open(path, "a", encoding="utf-8") as fh:
                fh.write(text + "\n")
        except OSError:
            pass
