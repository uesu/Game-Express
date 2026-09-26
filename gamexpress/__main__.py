"""Command line entry point:  python -m gamexpress <command> [options]

  run             one monitor pass (GitHub Actions uses this)            [default]
  loop            run forever every LOOP_MINUTES (VPS / Docker, no bot token needed)
  bot             Discord bot with /codes /schedule /status + the monitor loop
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

from . import __version__
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
    unlaunched=True keeps ONLY the games that are not live yet (ENABLE_GAMES off) — a game with
    no announcement of its own has no real code to fetch, so its card and its channel can only
    be checked with example data."""
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
            if unlaunched and games[key].enabled:
                continue                     # live games get their REAL codes from the real run
            for i, p in enumerate(codes_payloads(games[key], codes, settings,
                                                 _ping("codes", key), int(time.time()))):
                out.append(("codes", f"codes_{key}{'_' + str(i + 1) if i else ''}", p))
    if mark:
        out = [(f, n, mark_test(p)) for f, n, p in out]
    return out


async def cmd_test_card(args) -> int:
    import aiohttp

    from .discord import WebhookClient
    settings = load_settings()
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
        group = "Schedule cards" if feature == "schedule" else "Code cards"
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


def cmd_validate(_args) -> int:
    settings = load_settings()
    games = load_games()
    print(f"Game-Express {__version__} | features={sorted(settings.features) or 'NONE'} | "
          f"instance={settings.instance_name} ({settings.instance_role}) | dry_run={settings.dry_run}")
    print(f"peer_state_url={'set' if settings.peer_state_url else '—'} | X={'on' if settings.x_enabled else 'off'} "
          f"| nitter instances={len(settings.nitter_instances)} | token={'set' if settings.nitter_token else '—'}")
    print("emoji: " + ", ".join(f"{k}={'✓' if v else '—'}" for k, v in settings.emoji.items()))
    ok = True
    from .discord import WEBHOOK_RE
    for g in games.values():
        on = game_is_on(g, settings)
        cols = []
        for feature in ("schedule", "codes"):
            secret, url = settings.webhook_source(feature, g.key)
            hook = f"✓ {secret}" if url else "— none"
            if url and not WEBHOOK_RE.match(url):
                hook = f"✗ {secret} is not a webhook URL"
                ok = False
            cols.append(f"{feature}[{hook} | {settings.ping(feature, g.key).text or 'no ping'}]")
        flag = "✓" if on else "·"
        note = "" if on else (f" (off; auto-on {g.auto_enable_on})" if g.auto_enable_on else " (off)")
        print(f"  {flag} {g.key:9} {g.name:22}{note}\n      {cols[0]}\n      {cols[1]}\n"
              f"      X={','.join(g.x_accounts) or '—'} code_sources={','.join(g.codes.get('sources', [])) or '—'} "
              f"4★/phase={g.four_star_count or 'count not set (set four_star_count at launch)'}")
    for name in ("PING_ROLE_ID", "PING_SCHEDULE", "PING_CODES"):
        v = str(settings.env.get(name, "") or "")
        if v and parse_ping(v) is not None and not parse_ping(v) and v.lower() not in ("none", "off", "no", "false", "0", "-"):
            print(f"  ! {name}={v!r} has no valid role id (expected digits, 'everyone', 'here' or 'none')")
            ok = False
    for _f, name, payload in sample_payloads():
        problems = validate_payload(payload)
        if problems:
            ok = False
            print(f"  ! sample {name}: {'; '.join(problems)}")
    print("config OK" if ok else "config has problems (see the '!' / '✗' lines)")
    return 0 if ok else 1


async def cmd_run(_args) -> int:
    from .runner import run_once
    ctx = await run_once(load_settings())
    return 1 if ctx.errors else 0


async def cmd_loop(args) -> int:
    from .runner import run_once
    from .web import STATUS, start_health_server
    minutes = max(5, int(args.minutes or os.getenv("LOOP_MINUTES", "10")))
    await start_health_server()
    log.info("loop mode: running every %d min", minutes)
    while True:
        try:
            ctx = await run_once(load_settings())
            STATUS.update({"last_run": int(time.time()), "last_report": ctx.report[-10:]})
        except Exception:  # keep the loop alive
            log.exception("run failed")
        await asyncio.sleep(minutes * 60)


def main(argv: list[str] | None = None) -> int:
    _load_dotenv()
    p = argparse.ArgumentParser(prog="python -m gamexpress", description="Game-Express monitor")
    p.add_argument("command", nargs="?", default="run",
                   choices=["run", "loop", "bot", "test-card", "check-webhooks", "preview", "validate"])
    p.add_argument("--dry-run", action="store_true", help="build + log cards, never post")
    p.add_argument("--only", choices=["schedule", "codes"], help="run one feature")
    p.add_argument("--game", default="", help="restrict to one game key (e.g. starrail)")
    p.add_argument("--repost", default="", help="force a NEW post for game:version (e.g. genshin:7.2)")
    p.add_argument("--kind", default="all", choices=["all", "schedule", "codes"],
                   help="test-card / check-webhooks / preview")
    p.add_argument("--ping", action="store_true", help="test-card: include your role ping (default: no ping)")
    p.add_argument("--unlaunched", action="store_true",
                   help="test-card: only the games that are not live yet — example data, because "
                        "there is no real announcement to fetch for them")
    p.add_argument("--out", default="previews", help="preview output folder")
    p.add_argument("--minutes", default="", help="loop interval (default LOOP_MINUTES or 10)")
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
    if args.command == "validate":
        return cmd_validate(args)
    if args.command == "test-card":
        return asyncio.run(cmd_test_card(args))
    if args.command == "check-webhooks":
        return asyncio.run(cmd_check_webhooks(args))
    if args.command == "loop":
        return asyncio.run(cmd_loop(args))
    if args.command == "bot":
        from .bot import run_bot
        return run_bot()
    return asyncio.run(cmd_run(args))


if __name__ == "__main__":
    sys.exit(main())
