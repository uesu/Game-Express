"""Command line entry point:  python -m gamexpress <command> [options]

  run             one monitor pass (GitHub Actions uses this)            [default]
  test-card       post the sample cards (your 4 reference cards + one codes card per game),
                  labelled 🧪 TEST; no ping unless --ping
  check-webhooks  send ONE small "✅ connected" card to every configured webhook, listing
                  which game/feature cards that channel will receive
  preview         write previews/index.html (Discord-like view of every sample card) + JSON
  validate        check config/games.json + env and print the resolved routing
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
import time
from pathlib import Path

from . import build_id
from .cards import IS_COMPONENTS_V2, codes_payloads, container, mark_test, schedule_payload, text, validate_payload
from .config import ROOT, Ping, game_is_on, load_games, load_settings, parse_ping
from .samples import CODE_SAMPLES, SCHEDULE_SAMPLES

log = logging.getLogger("gamexpress")


def _setup_logging(level: str) -> None:
    logging.basicConfig(level=getattr(logging, level, logging.INFO),
                        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s", datefmt="%H:%M:%S")


def _load_dotenv() -> None:
    try:
        from dotenv import load_dotenv
        load_dotenv(ROOT / ".env", override=False)
    except ImportError:
        pass


def sample_payloads(kind: str = "all", game: str = "", *, mark: bool = False,
                    ping: bool = True, unlaunched: bool = False) -> list[tuple[str, str, dict]]:
    """[(feature, name, payload)] for every sample card. mark=True labels them 🧪 TEST;
    ping=False strips the role ping (test posts should not notify a whole role);
    unlaunched=True keeps ONLY the games that are not RELEASED yet ("released": false in
    games.json) — a game that is not out has no real code to fetch, so its card and its channel
    can only be checked with example data. Note this is independent of `enabled`: a pre-release
    game is still monitored for its announcements, it just has nothing real to redeem yet."""
    settings = load_settings()
    games = load_games()
    out = []

    def _ping(feature: str, key: str) -> Ping:
        return settings.ping(feature, key) if ping else Ping()

    if kind in ("all", "schedule"):
        for key, data in SCHEDULE_SAMPLES.items():
            if key in games and (not game or game == key):
                out.append(("schedule", f"schedule_{key}",
                            schedule_payload(games[key], data, settings, _ping("schedule", key))))
    if kind in ("all", "codes"):
        for key, codes in CODE_SAMPLES.items():
            if key not in games or (game and game != key):
                continue
            if unlaunched and games[key].released:
                continue                     # live games get their REAL codes from the real run
            for i, p in enumerate(codes_payloads(games[key], codes, settings,
                                                 _ping("codes", key), int(time.time()))):
                out.append(("codes", f"codes_{key}{'_' + str(i + 1) if i else ''}", p))
    if kind == "news":
        from .cards import news_payloads
        from .models import Item

        for key in ("genshin", "starrail", "zzz", "wuwa", "hna"):
            if game and key != game:
                continue
            item = Item("kuro" if key == "wuwa" else "hoyolab", key, "sample", "https://example.com/news",
                        "OFFLINE SAMPLE — official news layout", "", 1792281600,
                        article_blocks=[{"kind": "text", "text": "Sample full article text. This is not a real announcement."},
                                        {"kind": "image", "url": "https://example.com/sample.gif"},
                                        {"kind": "text", "text": "More article text after the sample media."}],
                        author="Official source (sample)")
            for i, payload in enumerate(news_payloads(games[key], item)):
                out.append(("news", f"news_{key}_{i + 1}", payload))
    if kind == "maintenance":
        from .cards import maintenance_payload

        sample_versions = {
            "genshin": ("7.2", 1793570400, 1793725200, 1793743200),
            "starrail": ("4.7", 1794013200, 1794157200, 1794175200),
            "zzz": ("3.3", 1792382400, 1792533600, 1792551600),
            "wuwa": ("3.7", 1790560800, 1790712000, 1790737200),
            "hna": ("1.0", 1795000000, 1795140000, None),
        }
        for key, (ver, pre_ts, start_ts, end_ts) in sample_versions.items():
            if game and key != game:
                continue
            media = "https://example.com/sample-launch.mp4" if key != "hna" else None
            out.append((
                "maintenance",
                f"maintenance_{key}_preload",
                maintenance_payload(
                    games[key], ver, "preload", start_ts=pre_ts,
                    ping=_ping("maintenance", key), media_url=media,
                ),
            ))
            out.append((
                "maintenance",
                f"maintenance_{key}_start",
                maintenance_payload(
                    games[key], ver, "maintenance", start_ts=start_ts, end_ts=end_ts,
                    ping=_ping("maintenance", key), media_url=media,
                ),
            ))
    if mark:
        out = [(f, n, mark_test(p)) for f, n, p in out]
    return out


async def cmd_test_card(args) -> int:
    import aiohttp

    from .discord import WebhookClient
    settings = load_settings()
    if args.kind in ("news", "maintenance"):
        print(f"{args.kind.title()} samples are preview-only; use preview --kind {args.kind}. No messages sent.")
        return 0
    rc = 0
    async with aiohttp.ClientSession() as session:
        client = WebhookClient(session, dry_run=settings.dry_run or args.dry_run)
        for feature, name, payload in sample_payloads(args.kind, args.game, mark=True, ping=args.ping,
                                                      unlaunched=args.unlaunched):
            key = name.split("_", 1)[1].split("_")[0]
            secret, url = settings.webhook_source(feature, key)
            if not url:
                print(f"[{name}] no webhook for {feature}/{key} (add {settings.expected_webhook_names(feature, key)})"
                      " — printing the payload instead")
                print(json.dumps(payload, ensure_ascii=False, indent=2)[:3000])
                continue
            res = await client.send(url, payload)
            print(f"[{name}] -> {secret}: {'OK' if res.ok else 'FAILED'} {res.status} {res.error}")
            rc |= 0 if res.ok else 1
    return rc


async def cmd_check_webhooks(args) -> int:
    """One small V2 card per UNIQUE webhook, listing every game/feature routed to it."""
    import aiohttp

    from .discord import WEBHOOK_RE, WebhookClient
    settings = load_settings()
    games = load_games()
    feats = [f for f in ("schedule", "codes") if args.kind in ("all", f)]
    targets = [g for g in games.values() if not args.game or g.key == args.game]
    routes: dict[str, dict] = {}
    missing: list[str] = []
    for f in feats:
        for g in targets:
            secret, url = settings.webhook_source(f, g.key)
            if not url:
                if game_is_on(g, settings):
                    missing.append(f"{f}/{g.key} -> add {settings.expected_webhook_names(f, g.key)}")
                continue
            r = routes.setdefault(url, {"secrets": set(), "routes": []})
            r["secrets"].add(secret)
            r["routes"].append((f, g))
    rc = 0
    async with aiohttp.ClientSession() as session:
        client = WebhookClient(session, dry_run=settings.dry_run or args.dry_run)
        for url, r in routes.items():
            names = ", ".join(sorted(r["secrets"]))
            if not WEBHOOK_RE.match(url):
                print(f"! {names}: this value is not a Discord webhook URL "
                      "(expected https://discord.com/api/webhooks/<id>/<token>) — re-copy it")
                rc = 1
                continue
            lines = []
            for f, g in r["routes"]:
                p = settings.ping(f, g.key)
                state = "" if game_is_on(g, settings) else " · *prepared (off)*"
                lines.append(f"✦ **{f.title()}** · {g.name}{state} — ping: {p.text or 'no ping'}")
            card = container([
                text("### ✅ Game-Express webhook check"),
                text("This channel is connected and will receive:\n" + "\n".join(lines)),
                text(f"-# secret: {names} • sent by the monitor's test bench • nobody was pinged"),
            ], 0x57F287)
            payload = {"flags": IS_COMPONENTS_V2, "allowed_mentions": {"parse": []}, "components": [card]}
            res = await client.send(url, payload)
            print(f"[{names}] {len(r['routes'])} route(s): {'OK' if res.ok else 'FAILED'} {res.status} {res.error}")
            rc |= 0 if res.ok else 1
    for m in missing:
        print(f"  · no webhook: {m}")
    if not routes:
        print("No webhook configured at all — add DISCORD_WEBHOOK_SCHEDULE / DISCORD_WEBHOOK_CODES (or per game).")
        rc = 1
    return rc


def cmd_preview(args) -> int:
    from .preview_html import render_page
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    cards = []
    for feature, name, payload in sample_payloads(args.kind, args.game):
        problems = validate_payload(payload)
        (out / f"{name}.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"{name}.json  {'OK' if not problems else 'PROBLEMS: ' + '; '.join(problems)}")
        group = {
            "schedule": "Schedule cards",
            "codes": "Code cards",
            "news": "Official news samples",
            "maintenance": "Pre-Load & Maintenance samples",
        }[feature]
        cards.append((group, name, payload))
    if args.kind in ("all", "codes") and (not args.game or args.game == "starrail"):
        # how a posted card looks after the automatic silent edit once a code has expired
        settings, games = load_settings(), load_games()
        codes = [dict(c, expired=(i == 0)) for i, c in enumerate(CODE_SAMPLES["starrail"])]
        payload = codes_payloads(games["starrail"], codes, settings, settings.ping("codes", "starrail"),
                                 int(time.time()) - 3 * 86400)[0]
        (out / "codes_starrail_after_expiry.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2),
                                                              encoding="utf-8")
        cards.append(("Code card after a code expired (silent edit, no ping)", "codes_starrail_after_expiry",
                      payload))
    (out / "index.html").write_text(render_page(cards), encoding="utf-8")
    print(f"\nWrote {out}/index.html — open it in a browser for a Discord-like preview, or paste a JSON "
          "file into https://discohook.app (Components V2).")
    return 0


def cmd_speculate(args) -> int:
    """Show what the bot would predict for each game's next version, and why.

    Read-only: it posts nothing, edits nothing and writes no state. It is the way to check a
    prediction against reality before trusting it on a live card.
    """
    from datetime import datetime, timezone

    from .schedule import observed_starts, predict_cycle
    from .state import State
    settings, games = load_settings(), load_games()
    state = State.load(settings.state_path)
    now = int(args.now) if getattr(args, "now", 0) else int(time.time())
    conf_mark = {"high": "●●●", "medium": "●●○", "low": "●○○"}
    rows = 0
    print(f"Speculated cycles at {datetime.fromtimestamp(now, timezone.utc):%Y-%m-%d %H:%M} UTC — "
          "estimates only, every one is replaced by the official notice.\n")
    for g in games.values():
        if args.game and g.key != args.game:
            continue
        if g.cadence is None:
            continue
        records = state.schedule_records(g.key)
        guess = predict_cycle(g, records, now)
        if not guess:
            print(f"{g.short:5} {g.name:22} no prediction (no anchor, or the next cycle is "
                  "outside the 120-day horizon)")
            continue
        rows += 1
        tz = g.cadence.tz

        def fmt(ts, tz=tz) -> str:
            return datetime.fromtimestamp(ts, tz).strftime("%a %d %b %Y %H:%M") if ts else "—"

        label = guess["version"] or "?"
        if guess["version_alt"]:
            label += f" (or {guess['version_alt']} if the major rolls over)"
        learned = (f"learned from {guess['observed']} real notices"
                   if guess["learned"] else
                   f"shipped cold-start value ({guess['observed']} real notice(s) on file, "
                   f"{2 - guess['observed']} more needed to learn)")
        print(f"{g.short:5} {g.name} {label}")
        print(f"      confidence {conf_mark.get(guess['confidence'], '?')} {guess['confidence']:6} "
              f"| cadence {guess['cadence_days']:g}d, {learned}")
        print(f"      anchored on the last real maintenance {fmt(guess['anchor_ts'])}")
        print(f"      {g.program_label:17} {fmt(guess['program_ts'])}")
        print(f"      {'Pre-install':17} {fmt(guess['preinstall_ts'])}")
        print(f"      {'Maintenance':17} {fmt(guess['maint_start_ts'])} → "
              f"{fmt(guess['maint_end_ts'])}  (all times UTC+8)")
        if args.verbose:
            starts = observed_starts(records)
            seen = [datetime.fromtimestamp(ts, tz).strftime("%Y-%m-%d") for _v, ts in starts]
            print(f"      real maintenance dates on file: {', '.join(seen) or 'none'}")
        print()
    if not rows:
        print("Nothing to predict. Add a 'cadence' block to a game in config/games.json.")
    return 0


def cmd_validate(_args) -> int:
    settings = load_settings()
    games = load_games()
    print(f"Game-Express {build_id()} | features={sorted(settings.features) or 'NONE'} | "
          f"instance={settings.instance_name} ({settings.instance_role}) | dry_run={settings.dry_run}")
    print(f"peer_state_url={'set' if settings.peer_state_url else '—'} | X={'on' if settings.x_enabled else 'off'} "
          f"| nitter instances={len(settings.nitter_instances)} | token={'set' if settings.nitter_token else '—'}")
    print(f"news={'on' if 'news' in settings.features else 'off'} | news games={','.join(sorted(settings.news_games))} "
          f"| article count cap=none "
          f"| timestamps={'on' if settings.news_timestamps else 'off'} "
          f"| expand full={'on' if settings.news_expand_full else 'off'} "
          f"| group long strips={'on' if settings.news_group_long_strips else 'off'} | dedicated destinations only")
    print(f"maintenance={'on' if 'maintenance' in settings.features else 'off'} "
          f"| maintenance games={','.join(sorted(settings.maintenance_games)) or 'none'} | dedicated destinations only")
    print("emoji: " + ", ".join(f"{k}={'✓' if v else '—'}" for k, v in settings.emoji.items()))
    ok = True
    from .discord import WEBHOOK_RE, webhook_fingerprint
    for g in games.values():
        on = game_is_on(g, settings)
        cols = []
        for feature in ("schedule", "codes", "news", "maintenance"):
            secret, url = settings.webhook_source(feature, g.key)
            hook = f"✓ {secret}" if url else "— none"
            if url and not WEBHOOK_RE.match(url):
                hook = f"✗ {secret} is not a webhook URL"
                ok = False
            mirror = ""
            msecret, murl = (
                settings.mirror_webhook_source(feature, g.key)
                if feature not in ("news", "maintenance")
                else ("", None)
            )
            if murl and not WEBHOOK_RE.match(murl):
                mirror = f" | ✗ {msecret} is not a webhook URL"
                ok = False
            elif murl and url and webhook_fingerprint(murl) == webhook_fingerprint(url):
                mirror = f" | ⚠ {msecret} is the same channel as {secret} — no copy sent"
            elif murl:
                mirror = f" | 🪞 also {msecret}"
            ping_text = settings.ping(feature, g.key).text if feature != "news" else ""
            cols.append(f"{feature}[{hook} | {ping_text or 'no ping'}{mirror}]")
        flag = "✓" if on else "·"
        note = "" if on else (f" (off; auto-on {g.auto_enable_on})" if g.auto_enable_on else " (off)")
        print(f"  {flag} {g.key:9} {g.name:22}{note}\n      {cols[0]}\n      {cols[1]}\n      {cols[2]}\n      {cols[3]}\n"
              f"      X={','.join(g.x_accounts) or '—'} code_sources={','.join(g.codes.get('sources', [])) or '—'} "
              f"4★/phase={g.four_star_count or 'count not set (set four_star_count at launch)'}")
    valid_bools = {"1", "true", "yes", "on", "y", "0", "false", "no", "off", "n"}
    for name in (
        "NEWS_ENABLED",
        "NEWS_TIMESTAMPS",
        "NEWS_EXPAND_FULL",
        "NEWS_GROUP_LONG_STRIPS",
        "MAINTENANCE_ENABLED",
    ):
        raw_val = str(settings.env.get(name, "") or "").strip()
        if raw_val and raw_val.lower() not in valid_bools:
            print(f"  ! {name}={raw_val!r} is not a recognized boolean ('0'/'1', 'false'/'true')")
            ok = False
    for name, gset in (("NEWS_GAMES", settings.news_games), ("MAINTENANCE_GAMES", settings.maintenance_games)):
        unknown = sorted(k for k in gset if k not in games)
        if unknown:
            print(f"  ! {name} contains unknown game key(s): {', '.join(unknown)}")
            ok = False
    ping_env_names = ["PING_ROLE_ID", "PING_SCHEDULE", "PING_CODES", "PING_MAINTENANCE"]
    for g in games.values():
        for slug_name in settings._game_slugs(g.key):
            ping_env_names.append(f"PING_MAINTENANCE_{slug_name}")
    for name in ping_env_names:
        v = str(settings.env.get(name, "") or "")
        if v and parse_ping(v) is not None and not parse_ping(v) and v.lower() not in ("none", "off", "no", "false", "0", "-"):
            print(f"  ! {name}={v!r} has no valid role id (expected digits, 'everyone', 'here' or 'none')")
            ok = False
    for check_kind in ("all", "news", "maintenance"):
        for _f, name, payload in sample_payloads(check_kind):
            problems = validate_payload(payload)
            if problems:
                ok = False
                print(f"  ! sample {name}: {'; '.join(problems)}")
    print("config OK" if ok else "config has problems (see the '!' / '✗' lines)")
    return 0 if ok else 1


def cmd_benchmark(args) -> int:
    """Reproducible offline micro-benchmark for disabled bypass, timestamp scanning,
    human vs Discord epoch formatting, and expanded long-article pagination."""
    import platform
    import statistics
    from datetime import datetime, timezone

    from .cards import news_payloads
    from .models import Item
    from .news_timestamps import convert_news_timestamps

    games = load_games()
    iters = max(20, int(getattr(args, "iterations", 200) or 200))

    short_body = (
        "Dear Proxies,\n"
        "Version 3.3 Pre-Installation begins on September 30, 12:00 (server time) — "
        "October 20, 14:59 (server time).\n"
        "Special Program airs September 12, 2026, 08:00 (UTC-4). "
        "Event window: From June 22, 2026 12:00 (UTC+8) to July 3, 2026 23:59 (UTC+8).\n"
        "Reference link: https://hoyo.link/example and inline code `2026/10/21 06:00 (UTC+8)`."
    )
    long_body = ("\n\n".join([short_body] * 36))
    short_item = Item(
        "hoyolab", "zzz", "bench-short", "https://www.hoyolab.com/article/46863847",
        "Version 3.3 Event & Pre-Download Details", "", 1790650000,
        article_blocks=[
            {"kind": "text", "text": short_body},
            {"kind": "image", "url": "https://upload-os-bbs.hoyolab.com/bench-lead.jpg"},
        ],
        author="Zenless Zone Zero",
    )
    long_blocks = []
    for idx in range(18):
        long_blocks.append({"kind": "text", "text": (short_body + "\n\n") * 2})
        long_blocks.append({"kind": "image", "url": f"https://hw-media-cdn-mingchao.kurogame.com/object/{idx}.gif"})
    long_item = Item(
        "kuro", "wuwa", "bench-long", "https://wutheringwaves.kurogames.com/en/main/news/detail/5571",
        "Version 3.7 Patch Notes & Adjustments", "", 1791000000,
        article_blocks=long_blocks,
        author="Kuro Games",
    )

    # Verify deterministic disabled-path exact equality before timing.
    assert convert_news_timestamps(long_body, published_ts=1790650000, enabled=False) is long_body
    base_short = news_payloads(games["zzz"], short_item)
    assert news_payloads(games["zzz"], short_item, timestamps=False, expand_full=False) == base_short
    base_long = news_payloads(games["wuwa"], long_item)
    assert news_payloads(games["wuwa"], long_item, timestamps=False, expand_full=False) == base_long
    expanded_long = news_payloads(games["wuwa"], long_item, timestamps=False, expand_full=True)
    assert len(base_long) == 1 and len(expanded_long) > 2

    epochs = [1789214400 + i * 3600 for i in range(16)]
    utc8 = timezone.utc

    def _measure(label: str, fn) -> dict:
        samples_us: list[float] = []
        fn()  # warmup
        for _ in range(iters):
            t0 = time.perf_counter_ns()
            fn()
            samples_us.append((time.perf_counter_ns() - t0) / 1000.0)
        samples_us.sort()
        p95 = samples_us[min(len(samples_us) - 1, int(len(samples_us) * 0.95))]
        return {
            "case": label,
            "iterations": iters,
            "median_us": round(statistics.median(samples_us), 2),
            "mean_us": round(statistics.mean(samples_us), 2),
            "p95_us": round(p95, 2),
        }

    results = [
        _measure("token_format_16_epochs", lambda: [f"<t:{ts}:f>" for ts in epochs]),
        _measure(
            "human_strftime_16_epochs",
            lambda: [datetime.fromtimestamp(ts, utc8).strftime("%b %d, %Y %H:%M UTC") for ts in epochs],
        ),
        _measure(
            f"timestamp_scan_disabled_{len(long_body)}c",
            lambda: convert_news_timestamps(long_body, published_ts=1790650000, enabled=False),
        ),
        _measure(
            f"timestamp_scan_enabled_short_{len(short_body)}c",
            lambda: convert_news_timestamps(short_body, published_ts=1790650000, enabled=True),
        ),
        _measure(
            f"timestamp_scan_enabled_long_{len(long_body)}c",
            lambda: convert_news_timestamps(long_body, published_ts=1790650000, enabled=True),
        ),
        _measure(
            "short_news_render_default_off",
            lambda: news_payloads(games["zzz"], short_item, timestamps=False, expand_full=False),
        ),
        _measure(
            "short_news_render_timestamps_on",
            lambda: news_payloads(games["zzz"], short_item, timestamps=True, expand_full=False),
        ),
        _measure(
            f"long_news_render_expand_off_1msg_{sum(len(b.get('text', '')) for b in long_blocks)}c",
            lambda: news_payloads(games["wuwa"], long_item, timestamps=False, expand_full=False),
        ),
        _measure(
            f"long_news_render_expand_on_{len(expanded_long)}pages_{sum(len(b.get('text', '')) for b in long_blocks)}c",
            lambda: news_payloads(games["wuwa"], long_item, timestamps=False, expand_full=True),
        ),
        _measure(
            f"long_news_render_both_on_{len(expanded_long)}pages",
            lambda: news_payloads(games["wuwa"], long_item, timestamps=True, expand_full=True),
        ),
    ]
    base_short = news_payloads(games["zzz"], short_item, timestamps=False, expand_full=False)
    default_short = news_payloads(games["zzz"], short_item)
    default_long = news_payloads(games["wuwa"], long_item)

    def _media_urls(payloads: list[dict]) -> list[str]:
        seen: list[str] = []
        for p in payloads:
            for co in p.get("components") or []:
                for child in co.get("components") or []:
                    if child.get("type") == 12:
                        for item_obj in child.get("items") or []:
                            u = (item_obj.get("media") or {}).get("url") or ""
                            if u and u not in seen:
                                seen.append(u)
        return seen

    request_counts = {
        "short_default_off": {
            "payloads": len(base_short),
            "distinct_media_preflights": len(_media_urls(base_short)),
            "webhook_posts": len(base_short),
            "min_pacing_s": round(max(0, len(base_short) - 1) * 1.2, 2),
        },
        "long_expand_off": {
            "payloads": len(base_long),
            "distinct_media_preflights": len(_media_urls(base_long)),
            "webhook_posts": len(base_long),
            "min_pacing_s": round(max(0, len(base_long) - 1) * 1.2, 2),
        },
        "long_expand_on": {
            "payloads": len(expanded_long),
            "distinct_media_preflights": len(_media_urls(expanded_long)),
            "webhook_posts": len(expanded_long),
            "min_pacing_s": round(max(0, len(expanded_long) - 1) * 1.2, 2),
        },
    }

    report = {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "short_input_chars": len(short_body),
        "long_input_chars": sum(len(b.get("text", "")) for b in long_blocks),
        "long_inline_media": sum(1 for b in long_blocks if b["kind"] == "image"),
        "default_long_messages": len(base_long),
        "expanded_long_messages": len(expanded_long),
        "disabled_output_equal": (base_short == default_short and base_long == default_long),
        "request_counts": request_counts,
        "benchmarks": results,
    }
    if getattr(args, "json", False):
        print(json.dumps(report, indent=2))
        return 0
    print(f"Environment: Python {report['python']} on {report['platform']}")
    print(
        f"Fixtures: short={report['short_input_chars']} chars | "
        f"long={report['long_input_chars']} chars + {report['long_inline_media']} media items "
        f"(default={report['default_long_messages']} msg -> expanded={report['expanded_long_messages']} pages | "
        f"disabled_output_equal={report['disabled_output_equal']})"
    )
    print(
        f"Deterministic counts: "
        f"short={request_counts['short_default_off']['payloads']} msg / "
        f"{request_counts['short_default_off']['distinct_media_preflights']} media GET / "
        f"{request_counts['short_default_off']['webhook_posts']} POST | "
        f"long(off)={request_counts['long_expand_off']['payloads']} msg / "
        f"{request_counts['long_expand_off']['distinct_media_preflights']} media GET / "
        f"{request_counts['long_expand_off']['webhook_posts']} POST | "
        f"long(on)={request_counts['long_expand_on']['payloads']} msgs / "
        f"{request_counts['long_expand_on']['distinct_media_preflights']} media GETs / "
        f"{request_counts['long_expand_on']['webhook_posts']} POSTs (+{request_counts['long_expand_on']['min_pacing_s']:.1f}s min pacing)"
    )
    print(f"{'Benchmark case':52} {'iters':>6} {'median µs':>11} {'mean µs':>11} {'p95 µs':>11}")
    print("-" * 95)
    for row in results:
        print(
            f"{row['case']:52} {row['iterations']:6d} "
            f"{row['median_us']:11.2f} {row['mean_us']:11.2f} {row['p95_us']:11.2f}"
        )
    return 0


async def cmd_run(_args) -> int:
    from .runner import run_once
    ctx = await run_once(load_settings())
    return 1 if ctx.errors else 0


def main(argv: list[str] | None = None) -> int:
    _load_dotenv()
    p = argparse.ArgumentParser(prog="python -m gamexpress", description="Game-Express monitor")
    p.add_argument("command", nargs="?", default="run",
                   choices=["run", "test-card", "check-webhooks", "preview", "speculate", "validate", "benchmark"])
    p.add_argument("--dry-run", action="store_true", help="build + log cards, never post")
    p.add_argument("--only", choices=["schedule", "codes", "news", "maintenance"], help="run one feature")
    p.add_argument("--game", default="", help="restrict to one game key (e.g. starrail)")
    p.add_argument("--repost", default="", help="force a NEW post for game:version (e.g. genshin:7.2)")
    p.add_argument("--kind", default="all", choices=["all", "schedule", "codes", "news", "maintenance"],
                   help="test-card / check-webhooks / preview")
    p.add_argument("--ping", action="store_true", help="test-card: include your role ping (default: no ping)")
    p.add_argument("--unlaunched", action="store_true",
                   help="test-card: only the games that are not live yet — example data, because "
                        "there is no real announcement to fetch for them")
    p.add_argument("--out", default="previews", help="preview output folder")
    p.add_argument("--verbose", action="store_true", help="speculate: also list the observed history")
    p.add_argument("--now", type=int, default=0,
                   help="speculate: pretend it is this unix time (for checking a past prediction)")
    p.add_argument("--iterations", type=int, default=200, help="benchmark: timed repetitions per case")
    p.add_argument("--json", action="store_true", help="benchmark: output machine-readable JSON")
    args = p.parse_args(argv)
    if args.dry_run:
        os.environ["DRY_RUN"] = "1"
    if args.only:
        os.environ["ONLY"] = args.only
    if args.game:
        os.environ["GAME"] = args.game
    if args.repost:
        os.environ["REPOST"] = args.repost
    _setup_logging(os.getenv("LOG_LEVEL", "INFO").upper())
    if args.command == "preview":
        return cmd_preview(args)
    if args.command == "speculate":
        return cmd_speculate(args)
    if args.command == "validate":
        return cmd_validate(args)
    if args.command == "benchmark":
        return cmd_benchmark(args)
    if args.command == "test-card":
        return asyncio.run(cmd_test_card(args))
    if args.command == "check-webhooks":
        return asyncio.run(cmd_check_webhooks(args))
    return asyncio.run(cmd_run(args))


if __name__ == "__main__":
    sys.exit(main())
