"""Independent fourth feature: Pre-Load Started and Maintenance Started announcements.

Design guarantees:
  * Disabled by default (`MAINTENANCE_ENABLED=0`), with per-game opt-in (`MAINTENANCE_GAMES`),
    per-game webhooks (`DISCORD_WEBHOOK_MAINTENANCE_<GAME>`), and per-game pings
    (`PING_MAINTENANCE_<GAME>`).
  * Works with or without schedule, codes, or news enabled, keeping the existing 5-minute
    `cron-job.org` cadence unchanged.
  * Precedence: official notices/launcher signals > explicit `config/overrides.json` entries
    > documented cadence predictions (for games with a corroborated `Cadence`; never invented
    for HNA or unknown maintenance end times).
  * Separate preload and maintenance state records per `(game, version)` with silent seeding
    on first enable / upgrade so historical settled versions never repost.
  * Structured version-verified media selection with priority:
      1. Matching-version launch video
      2. Matching-version launch artwork / WebP
      3. Matching-version official X / HoYoLAB Special Program artwork
      4. Omit gallery cleanly
  * Launch media is locked against later Phase II background changes, preserves signed query
    parameters (such as WuWa `auth_key=...`), handles expiry safely, and allows bounded
    silent late-media completion via webhook `PATCH` edit without re-pinging.
"""

from __future__ import annotations

import asyncio
import copy
import json
import logging
import re
from datetime import datetime, timezone
from urllib.parse import parse_qs, urlsplit

from . import schedule
from .cards import maintenance_payload
from .config import CONFIG_DIR, Game
from .discord import webhook_fingerprint
from .http import Probe
from .media import twimg_orig, upgrade
from .sources import hoyolab, kuro, launcher
from .state import stable_hash
from .textutil import find_version, version_key

log = logging.getLogger("gamexpress.maintenance")

ACTIVE_WINDOW_S = 12 * 3600           # deliver announcements within 12h of milestone start
LATE_MEDIA_EDIT_WINDOW_S = 6 * 3600   # bounded silent late-media completion window
LAUNCH_MEDIA_MAX_AFTER_S = 7 * 86400  # >7d after maintenance start belongs to mid-patch / Phase II
LAUNCH_MEDIA_MAX_BEFORE_S = 14 * 86400

_CDN_DATE_RE = re.compile(r"/(20\d{2})[/-](0[1-9]|1[0-2])[/-](0[1-9]|[12]\d|3[01])/")
_VIDEO_EXT_RE = re.compile(r"\.(?:mp4|webm)(?:[?#]|$)", re.I)


def _program_pins() -> dict:
    path = CONFIG_DIR / "program_announcements.json"
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _asset_upload_ts(url: str) -> int | None:
    """Extract embedded UTC date timestamp `/YYYY/MM/DD/` from CDN paths when present."""
    m = _CDN_DATE_RE.search(url or "")
    if not m:
        return None
    try:
        dt = datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)), 12, 0, tzinfo=timezone.utc)
        return int(dt.timestamp())
    except ValueError:
        return None


def _auth_key_expiry(url: str) -> int | None:
    """Parse `<unix_expiry>-...` from Kuro/CDN `auth_key` query parameter without stripping it."""
    if not url or "auth_key=" not in url:
        return None
    params = parse_qs(urlsplit(url).query, keep_blank_values=True)
    raw_list = params.get("auth_key") or []
    if not raw_list:
        return None
    head = raw_list[0].split("-", 1)[0].strip()
    if head.isdigit() and len(head) >= 9:
        return int(head)
    return None


def _same_asset_identity(url_a: str, url_b: str) -> bool:
    """True when two URLs refer to the exact same host + object path (e.g. renewed `auth_key`)."""
    pa, pb = urlsplit(url_a or ""), urlsplit(url_b or "")
    return bool(
        pa.scheme == pb.scheme
        and (pa.hostname or "").lower() == (pb.hostname or "").lower()
        and pa.path == pb.path
    )


def _is_video_url(url: str) -> bool:
    return bool(_VIDEO_EXT_RE.search(url or ""))


def _is_launch_window_compatible(
    url: str,
    *,
    now: int,
    preinstall_ts: int | None,
    maint_start_ts: int | None,
    explicit_version_link: bool = False,
) -> bool:
    """Reject stale prior-patch backgrounds and Phase II mid-patch background swaps."""
    upload_ts = _asset_upload_ts(url)
    anchor_early = preinstall_ts or maint_start_ts
    anchor_maint = maint_start_ts or preinstall_ts
    if upload_ts is not None:
        if anchor_maint and upload_ts > anchor_maint + LAUNCH_MEDIA_MAX_AFTER_S:
            return False
        if anchor_early and upload_ts < anchor_early - LAUNCH_MEDIA_MAX_BEFORE_S:
            return False
    elif not explicit_version_link and maint_start_ts and now > maint_start_ts + LAUNCH_MEDIA_MAX_AFTER_S:
        return False
    return True


async def _verify_url(fetcher, url: str, now: int) -> bool:
    """Validate URL safety, signed-query non-expiry, and bounded CDN preflight."""
    if not url or not url.startswith(("https://", "http://")):
        return False
    exp = _auth_key_expiry(url)
    if exp is not None and exp <= now:
        return False
    verify = getattr(fetcher, "verify_media", None)
    if callable(verify):
        return bool(await verify(url))
    return True


def _repost_matches(repost: str, game_key: str, version: str, kind: str) -> bool:
    """Support explicit operator `REPOST` targets (`zzz:3.3`, `zzz:3.3:preload`, `all`)."""
    if not repost:
        return False
    tokens = {tok.strip().lower() for tok in repost.split(",") if tok.strip()}
    gk = game_key.lower()
    ver = version.lower()
    return bool(
        tokens & {
            "all",
            gk,
            f"{gk}:{ver}",
            f"{gk}:{ver}:{kind}",
        }
    )


def resolve_version_plans(
    game: Game,
    schedule_records: dict,
    items: list,
    versions_info: dict,
    game_overrides: dict,
    now: int,
) -> dict[str, dict]:
    """Build resolved timing plans `{version: plan}` strictly obeying precedence:

      1. Official notices / first-party launcher state
      2. Explicit `config/overrides.json` entries (including holiday shifts)
      3. Documented `Cadence` predictions (never invented for HNA or unknown end times)
    """
    plans: dict[str, dict] = {}
    by_version: dict[str, list] = {}
    for it in items or []:
        ver = find_version(f"{it.title}\n{it.text}")
        if ver:
            by_version.setdefault(ver, []).append(it)

    candidate_versions: set[str] = set()
    for ver in (schedule_records or {}):
        if version_key(ver) != (0, 0):
            candidate_versions.add(ver)
    for ver in by_version:
        if version_key(ver) != (0, 0):
            candidate_versions.add(ver)
    for ver in (game_overrides or {}):
        if not str(ver).startswith("_") and isinstance(game_overrides[ver], dict) and version_key(ver) != (0, 0):
            candidate_versions.add(str(ver))
    for field_name in ("live", "pre"):
        ver = (versions_info or {}).get(field_name)
        if ver and version_key(ver) != (0, 0):
            candidate_versions.add(str(ver))

    lead_h = schedule.observed_lead_h(schedule_records) if game.cadence is not None else None

    for ver in sorted(candidate_versions, key=version_key):
        existing_rec = copy.deepcopy((schedule_records or {}).get(ver) or {})
        ov = copy.deepcopy((game_overrides or {}).get(ver) or {})
        ver_items = by_version.get(ver, [])

        raw_prev_data = existing_rec.get("data") if isinstance(existing_rec.get("data"), dict) else {}
        raw_prev_prov = existing_rec.get("prov") if isinstance(existing_rec.get("prov"), dict) else {}
        raw_prev_est = set(raw_prev_data.get("estimated") or [])
        official_seed_data: dict = {}
        official_seed_prov: dict = {}
        for k_field in ("preinstall_ts", "maint_start_ts", "maint_end_ts", "images", "version"):
            rank_val = (raw_prev_prov.get(k_field) or [0])[0]
            if k_field in ("images", "version") and raw_prev_data.get(k_field):
                official_seed_data[k_field] = copy.deepcopy(raw_prev_data[k_field])
            elif k_field not in raw_prev_est and 40 <= rank_val < 100 and raw_prev_data.get(k_field):
                official_seed_data[k_field] = raw_prev_data[k_field]
                official_seed_prov[k_field] = list(raw_prev_prov[k_field])
        official_rec = {"data": official_seed_data, "prov": official_seed_prov}

        # Merge official items ONLY onto official provenance so prior rank-100 overrides can never
        # shadow a newly published official notice, and estimates remain cleanly separated.
        ver_extracts = [schedule.extract(game, it) for it in ver_items]
        merged_official = schedule.merge(
            game, ver, ver_extracts, official_rec, {}, {}, now, [], lead_h=lead_h
        )
        est_fields = set(merged_official.get("estimated") or [])
        prov = official_rec.get("prov") or {}

        pre_ts: int | None = None
        pre_est = False
        pre_src = ""
        start_ts: int | None = None
        end_ts: int | None = None
        maint_est = False
        maint_src = ""

        # 1. Official values (rank >= 40 / non-estimated from official posts).
        raw_pre = merged_official.get("preinstall_ts")
        if raw_pre and "preinstall_ts" not in est_fields and prov.get("preinstall_ts", [50])[0] >= 40:
            pre_ts = int(raw_pre)

        raw_start = merged_official.get("maint_start_ts")
        if raw_start and "maint_start_ts" not in est_fields and prov.get("maint_start_ts", [50])[0] >= 40:
            start_ts = int(raw_start)
            raw_end = merged_official.get("maint_end_ts")
            if raw_end and "maint_end_ts" not in est_fields and int(raw_end) > start_ts:
                end_ts = int(raw_end)

        # Official live launcher pre-download branch proves preload has begun right now if no
        # earlier official pre-install timestamp was published in text.
        if pre_ts is None and (versions_info or {}).get("pre") == ver:
            pre_ts = now

        # 2. Explicit overrides (beat cadence predictions; Official wins when higher rank,
        #    while explicit overrides fill missing fields or shift unannounced dates such as holidays).
        if isinstance(ov, dict) and ov:
            if pre_ts is None and ov.get("preinstall_ts"):
                pre_ts = int(ov["preinstall_ts"])
                pre_est = False
            if start_ts is None and ov.get("maint_start_ts"):
                start_ts = int(ov["maint_start_ts"])
                maint_est = False
                if ov.get("maint_end_ts"):
                    end_ts = int(ov["maint_end_ts"])
                elif ov.get("maint_hours"):
                    end_ts = int(start_ts + float(ov["maint_hours"]) * 3600)
                else:
                    # Unknown maintenance end time in override must never be invented.
                    end_ts = None
            elif start_ts is not None and end_ts is None:
                if ov.get("maint_end_ts"):
                    end_ts = int(ov["maint_end_ts"])
                elif ov.get("maint_hours"):
                    end_ts = int(start_ts + float(ov["maint_hours"]) * 3600)

        # 3. Documented cadence fallback for preload when maintenance start is known and game has cadence.
        if (
            pre_ts is None
            and start_ts is not None
            and game.cadence is not None
            and raw_pre
            and "preinstall_ts" in est_fields
        ):
            pre_ts = int(raw_pre)
            pre_est = True
            pre_src = "version cadence"

        plans[ver] = {
            "version": ver,
            "preinstall_ts": pre_ts,
            "preinstall_estimated": pre_est,
            "preinstall_source": pre_src,
            "maint_start_ts": start_ts,
            "maint_end_ts": end_ts if (end_ts and start_ts and end_ts > start_ts) else None,
            "maint_estimated": maint_est,
            "maint_source": maint_src,
            "schedule_images": list(merged_official.get("images") or []),
            "override": ov if isinstance(ov, dict) else {},
        }

    # 4. Full cycle prediction (`predict_cycle`) for the upcoming version when no official/override
    #    record exists yet — evaluated at `now - ACTIVE_WINDOW_S` so a cycle whose milestone just
    #    crossed `now` is not rolled +42d past the active trigger window.
    if game.cadence is not None:
        guess = schedule.predict_cycle(
            game, schedule_records, max(1, now - ACTIVE_WINDOW_S), lead_h=lead_h
        )
        if guess and guess.get("version"):
            gver = str(guess["version"])
            ov = copy.deepcopy((game_overrides or {}).get(gver) or {})
            existing = plans.get(gver)
            if existing is None:
                plans[gver] = {
                    "version": gver,
                    "preinstall_ts": int(guess["preinstall_ts"]) if guess.get("preinstall_ts") else None,
                    "preinstall_estimated": True,
                    "preinstall_source": "version cadence",
                    "maint_start_ts": int(guess["maint_start_ts"]) if guess.get("maint_start_ts") else None,
                    "maint_end_ts": int(guess["maint_end_ts"]) if guess.get("maint_end_ts") else None,
                    "maint_estimated": True,
                    "maint_source": "version cadence",
                    "schedule_images": [],
                    "override": ov if isinstance(ov, dict) else {},
                }
            else:
                if existing["preinstall_ts"] is None and "preinstall_ts" not in ov and guess.get("preinstall_ts"):
                    existing["preinstall_ts"] = int(guess["preinstall_ts"])
                    existing["preinstall_estimated"] = True
                    existing["preinstall_source"] = "version cadence"
                if existing["maint_start_ts"] is None and "maint_start_ts" not in ov and guess.get("maint_start_ts"):
                    existing["maint_start_ts"] = int(guess["maint_start_ts"])
                    existing["maint_end_ts"] = int(guess["maint_end_ts"]) if guess.get("maint_end_ts") else None
                    existing["maint_estimated"] = True
                    existing["maint_source"] = "version cadence"

    return plans


async def resolve_launch_media(
    ctx,
    game: Game,
    version: str,
    plan: dict,
    version_state: dict,
    *,
    basic_info: dict[str, list[dict]],
    program_pins: dict,
) -> tuple[int, str | None]:
    """Select and verify media strictly following Section 6 priority and locking rules:

      Priority 1: Matching-version launch video
      Priority 2: Matching-version launch artwork / WebP
      Priority 3: Matching-version official X / HoYoLAB Special Program artwork
      Priority 4: Omit gallery (`(4, None)`)
    """
    now = ctx.now
    pre_ts = plan.get("preinstall_ts")
    start_ts = plan.get("maint_start_ts")
    ov = plan.get("override") or {}
    vinfo = ctx.versions.get(game.key) or {}
    lock = version_state.setdefault("launch_media", {})

    launcher_matches = (vinfo.get("pre") == version) or (vinfo.get("live") == version)

    # Gather structured fresh candidates WITHOUT overwriting an already-locked asset yet.
    fresh_videos: list[tuple[str, bool]] = []
    fresh_artworks: list[tuple[str, bool]] = []

    if ov.get("launch_video"):
        fresh_videos.append((str(ov["launch_video"]).strip(), True))
    if ov.get("launch_image"):
        fresh_artworks.append((str(ov["launch_image"]).strip(), True))

    if game.launcher.get("type") == "hoyoplay":
        gid = str(game.launcher.get("game_id") or "")
        for entry in basic_info.get(gid) or []:
            links = entry.get("links") or []
            link_versions = [find_version(u) for u in links if find_version(u)]
            if link_versions and version not in link_versions:
                continue
            explicit_match = version in link_versions
            if not explicit_match and not launcher_matches:
                continue
            vid = entry.get("video") or ""
            if vid and _is_launch_window_compatible(
                vid,
                now=now,
                preinstall_ts=pre_ts,
                maint_start_ts=start_ts,
                explicit_version_link=explicit_match,
            ):
                fresh_videos.append((vid, explicit_match))
            art = entry.get("background") or ""
            if art and _is_launch_window_compatible(
                art,
                now=now,
                preinstall_ts=pre_ts,
                maint_start_ts=start_ts,
                explicit_version_link=explicit_match,
            ):
                fresh_artworks.append((art, explicit_match))
    elif game.launcher.get("type") == "kuro":
        for slot_key in ("pre_media", "live_media"):
            slot = vinfo.get(slot_key)
            if not isinstance(slot, dict) or slot.get("version") != version:
                continue
            vid = slot.get("video") or ""
            if vid and _is_launch_window_compatible(
                vid, now=now, preinstall_ts=pre_ts, maint_start_ts=start_ts
            ):
                fresh_videos.append((vid, False))
            art = slot.get("artwork") or ""
            if art and _is_launch_window_compatible(
                art, now=now, preinstall_ts=pre_ts, maint_start_ts=start_ts
            ):
                fresh_artworks.append((art, False))

    # --- Priority 1: Matching-version launch video (locked launch video takes strict precedence) ---
    locked_video = str(lock.get("video") or "").strip()
    if locked_video:
        if await _verify_url(ctx.fetcher, locked_video, now):
            return 1, locked_video
        # Locked video expired (e.g. short-lived WuWa `auth_key`): ONLY accept a renewed token
        # for the EXACT SAME verified asset path within the launch window — never a different patch's file.
        for cand_url, _ in fresh_videos:
            if _same_asset_identity(cand_url, locked_video) and await _verify_url(ctx.fetcher, cand_url, now):
                lock["video"] = cand_url
                lock["renewed_at"] = now
                return 1, cand_url
    elif not lock.get("locked"):
        for cand_url, _ in fresh_videos:
            if await _verify_url(ctx.fetcher, cand_url, now):
                lock["video"] = cand_url
                if not lock.get("artwork"):
                    for art_url, _ in fresh_artworks:
                        if await _verify_url(ctx.fetcher, art_url, now):
                            lock["artwork"] = art_url
                            break
                lock["locked"] = True
                lock["locked_at"] = now
                return 1, cand_url

    # --- Priority 2: Matching-version launch artwork / WebP ---
    locked_art = str(lock.get("artwork") or "").strip()
    if locked_art:
        if await _verify_url(ctx.fetcher, locked_art, now):
            return 2, locked_art
        for cand_url, _ in fresh_artworks:
            if _same_asset_identity(cand_url, locked_art) and await _verify_url(ctx.fetcher, cand_url, now):
                lock["artwork"] = cand_url
                lock["renewed_at"] = now
                return 2, cand_url
    elif not lock.get("locked"):
        for cand_url, _ in fresh_artworks:
            if await _verify_url(ctx.fetcher, cand_url, now):
                lock["artwork"] = cand_url
                lock["locked"] = True
                lock["locked_at"] = now
                return 2, cand_url

    # --- Priority 3: Matching-version official X / HoYoLAB Special Program artwork ---
    program_candidates: list[str] = []
    pinned_entry = ((program_pins.get(game.key) or {}).get(version) or {})
    if isinstance(pinned_entry, dict) and pinned_entry.get("image"):
        program_candidates.append(twimg_orig(str(pinned_entry["image"]).strip()))
    for img in plan.get("schedule_images") or []:
        if img and not _is_video_url(img):
            program_candidates.append(upgrade(str(img).strip()))
    if not program_candidates and callable(getattr(ctx.fetcher, "get_json", None)):
        from .runner import find_program

        hit = await find_program(ctx, game, version)
        if hit:
            for img in hit.get("images") or []:
                if img and not _is_video_url(img):
                    program_candidates.append(upgrade(str(img).strip()))

    seen_prog: set[str] = set()
    for prog_url in program_candidates:
        if not prog_url or prog_url in seen_prog:
            continue
        seen_prog.add(prog_url)
        if await _verify_url(ctx.fetcher, prog_url, now):
            return 3, prog_url

    # --- Priority 4: Omit gallery ---
    return 4, None


async def _ensure_inputs_for_games(ctx, target_games: list[Game]) -> None:
    """Gather ONLY the launcher + official announcement inputs needed by `target_games`.

    When `schedule` or `codes` already gathered them earlier in the same run, reuses
    `ctx.versions` and `ctx.items` with zero duplicate requests. In maintenance-only
    mode, avoids all unrelated sources (`CodeSources`, countdown sites, banner feeds,
    wikis, calendars, and unconfigured games).
    """
    missing_ver_hyp = any(
        g.launcher.get("type") == "hoyoplay" and g.key not in ctx.versions for g in target_games
    )
    missing_ver_kuro = any(
        g.launcher.get("type") == "kuro" and g.key not in ctx.versions for g in target_games
    )
    if missing_ver_hyp or missing_ver_kuro:
        async def _empty() -> dict:
            return {}

        hyp, kr = await asyncio.gather(
            launcher.hoyoplay_versions(ctx.fetcher) if missing_ver_hyp else _empty(),
            kuro.launcher_versions(ctx.fetcher) if missing_ver_kuro else _empty(),
        )
        for g in target_games:
            t = g.launcher.get("type")
            if t == "hoyoplay" and g.launcher.get("game_id") in hyp:
                ctx.versions[g.key] = hyp[g.launcher["game_id"]]
            elif t == "kuro" and kr:
                ctx.versions[g.key] = kr

    since = ctx.now - ctx.settings.lookback_hours * 3600
    missing_item_games = [g for g in target_games if g.key not in ctx.items]
    if missing_item_games:
        async def _collect_one(g: Game) -> None:
            want = schedule.wants(g)
            probe = Probe(ctx.fetcher)
            parts = await asyncio.gather(
                hoyolab.fetch_items(probe, g, want, since),
                kuro.fetch_items(probe, g, want, since),
                ctx.x.items(g, want, since) if getattr(ctx, "x", None) is not None else asyncio.sleep(0, result=[]),
            )
            ctx.items[g.key] = [it for part in parts for it in part]

        await asyncio.gather(*(_collect_one(g) for g in missing_item_games))


async def run(ctx) -> None:
    """Execute one maintenance-announcement pass across opted-in games."""
    if "maintenance" not in ctx.settings.features or not ctx.active:
        return
    if ctx.settings.test_mode:
        ctx.warnings.append(
            "Maintenance test-mode posting is disabled; use preview --kind maintenance or run --only maintenance --dry-run"
        )
        return

    ctx.state.prune_maintenance()
    for key, record in (ctx.state.data.get("maintenance") or {}).items():
        if key not in ctx.settings.maintenance_games:
            record["paused"] = True

    routed_games: list[tuple[Game, str, str]] = []
    for game in ctx.games:
        if game.key not in ctx.settings.maintenance_games:
            continue
        hook = ctx.settings.webhook("maintenance", game.key)
        if not hook:
            ctx.warnings.append(f"{game.short} maintenance: missing dedicated webhook; no request or bootstrap")
            continue
        fp = stable_hash([webhook_fingerprint(hook), hook.partition("?")[2]])
        existing = (ctx.state.data.get("maintenance") or {}).get(game.key) or {}
        if existing.get("route") and existing["route"] != fp:
            ctx.warnings.append(
                f"{game.short} maintenance: destination changed; review maintenance state before resuming"
            )
            continue
        routed_games.append((game, hook, fp))

    if not routed_games:
        return

    await _ensure_inputs_for_games(ctx, [g for g, _, _ in routed_games])

    ephemeral = ctx.settings.dry_run or ctx.settings.test_mode
    program_pins = _program_pins()
    basic_info: dict[str, list[dict]] | None = None

    async def get_basic_info() -> dict[str, list[dict]]:
        nonlocal basic_info
        if basic_info is None:
            basic_info = await launcher.hoyoplay_basic_info(ctx.fetcher)
        return basic_info

    for game, hook, fp in routed_games:
        sched_records = ctx.state.data.get("schedule", {}).get(game.key, {})
        plans = resolve_version_plans(
            game,
            sched_records,
            ctx.items.get(game.key, []),
            ctx.versions.get(game.key, {}),
            (ctx.overrides or {}).get(game.key, {}),
            ctx.now,
        )
        record = ctx.state.maintenance_record(game.key)
        versions_state = record.setdefault("versions", {})

        # Silent baseline / upgrade migration: mark every historical version & already-elapsed
        # milestone as `seeded` without posting or pinging, leaving future milestones active.
        if "seeded_at" not in record or record.get("paused"):
            record.update(seeded_at=ctx.now, route=fp, paused=False)
            for ver, plan in plans.items():
                vstate = versions_state.setdefault(ver, {})
                for kind, field_name in (("preload", "preinstall_ts"), ("maintenance", "maint_start_ts")):
                    if kind in vstate:
                        continue
                    ev_ts = plan.get(field_name)
                    if ev_ts is not None:
                        if ev_ts <= ctx.now:
                            vstate[kind] = {"status": "seeded", "ts": int(ev_ts)}
                    elif (
                        (ctx.versions.get(game.key) or {}).get("live") == ver
                        or (kind == "preload" and (ctx.versions.get(game.key) or {}).get("pre") == ver)
                    ):
                        vstate[kind] = {"status": "seeded", "ts": ctx.now}
            ctx.report.append(f"🌱 {game.short} maintenance: silent baseline; settled milestones not reposted")
            if not ctx.settings.repost:
                continue

        record.setdefault("route", fp)
        seeded_at = int(record.get("seeded_at") or 0)
        ping = ctx.settings.ping("maintenance", game.key)

        for ver, plan in sorted(plans.items(), key=lambda pair: version_key(pair[0])):
            vstate = versions_state.setdefault(ver, {})
            milestones = (
                ("preload", plan.get("preinstall_ts"), None, bool(plan.get("preinstall_estimated")), plan.get("preinstall_source") or ""),
                ("maintenance", plan.get("maint_start_ts"), plan.get("maint_end_ts"), bool(plan.get("maint_estimated")), plan.get("maint_source") or ""),
            )
            for kind, start_ts, end_ts, is_est, est_src in milestones:
                force = _repost_matches(ctx.settings.repost, game.key, ver, kind)
                entry = vstate.get(kind)

                if entry and not force:
                    status = entry.get("status")
                    if status == "ambiguous":
                        ctx.warnings.append(
                            f"{game.short} {ver} {kind}: held due to prior ambiguous webhook outcome"
                        )
                        continue
                    if status in ("posted", "seeded"):
                        # Bounded silent late-media completion without re-pinging: only while inside
                        # LATE_MEDIA_EDIT_WINDOW_S and only when initial post had fallback/omitted media.
                        posted_at = int(entry.get("posted_at") or 0)
                        cur_tier = int(entry.get("media_tier") or 4)
                        msg_id = entry.get("message_id")
                        if (
                            status == "posted"
                            and msg_id
                            and cur_tier > 1
                            and 0 <= ctx.now - posted_at <= LATE_MEDIA_EDIT_WINDOW_S
                        ):
                            binfo = await get_basic_info() if game.launcher.get("type") == "hoyoplay" else {}
                            new_tier, new_url = await resolve_launch_media(
                                ctx, game, ver, plan, vstate, basic_info=binfo, program_pins=program_pins
                            )
                            if new_url and new_tier < cur_tier:
                                edit_card = maintenance_payload(
                                    game,
                                    ver,
                                    kind,
                                    start_ts=int(entry.get("ts") or start_ts or ctx.now),
                                    end_ts=end_ts if kind == "maintenance" else None,
                                    ping=ping,
                                    media_url=new_url,
                                    estimated=is_est,
                                    estimate_source=est_src,
                                    silent=True,
                                )
                                res = await ctx.webhook.edit(hook, msg_id, edit_card)
                                if res.ok:
                                    entry["media_tier"] = new_tier
                                    entry["media_url"] = new_url
                                    entry["edited_at"] = ctx.now
                                    if not ephemeral:
                                        ctx.state.save()
                                    ctx.report.append(
                                        f"🖼️ {game.short} {ver} {kind}: updated late media silently (tier {cur_tier}->{new_tier})"
                                    )
                        continue

                if start_ts is None:
                    continue
                due = force or (seeded_at < start_ts <= ctx.now and ctx.now - start_ts <= ACTIVE_WINDOW_S)
                if not due:
                    continue

                binfo = await get_basic_info() if game.launcher.get("type") == "hoyoplay" else {}
                media_tier, media_url = await resolve_launch_media(
                    ctx, game, ver, plan, vstate, basic_info=binfo, program_pins=program_pins
                )
                payload = maintenance_payload(
                    game,
                    ver,
                    kind,
                    start_ts=int(start_ts),
                    end_ts=int(end_ts) if (kind == "maintenance" and end_ts) else None,
                    ping=ping,
                    media_url=media_url,
                    estimated=is_est,
                    estimate_source=est_src,
                )
                result = await ctx.webhook.send(hook, payload)
                if result.ambiguous or (result.ok and not result.message_id):
                    vstate[kind] = {
                        "status": "ambiguous",
                        "ts": int(start_ts),
                        "attempted_at": ctx.now,
                    }
                    if not ephemeral:
                        ctx.state.save()
                    ctx.warnings.append(
                        f"{game.short} {ver} {kind}: ambiguous webhook outcome; held to prevent duplicate ping/post"
                    )
                    continue
                if not result.ok:
                    ctx.warnings.append(
                        f"{game.short} {ver} {kind}: Discord delivery failed ({result.status}); retry next run"
                    )
                    continue

                vstate[kind] = {
                    "status": "posted",
                    "message_id": result.message_id,
                    "ts": int(start_ts),
                    "posted_at": ctx.now,
                    "media_tier": media_tier,
                    "media_url": media_url or "",
                }
                if not ephemeral:
                    ctx.state.save()
                ctx.report.append(
                    f"🛠️ {game.short} {ver}: posted {'Pre-Load Started' if kind == 'preload' else 'Maintenance Started'}"
                )
