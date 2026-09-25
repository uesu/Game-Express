"""Command line entry point:  python -m gamexpress <command> [options]

  run         one monitor pass (GitHub Actions uses this)            [default]
  loop        run forever every LOOP_MINUTES (VPS / Docker, no bot token needed)
  bot         Discord bot with /codes /schedule /status + the monitor loop
  test-card   post the sample cards (your 4 reference cards + a codes card)
  preview     write sample payload JSON to previews/ (paste into Discohook)
  validate    check config/games.json + env and print the resolved routing
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
from .cards import codes_payloads, schedule_payload, validate_payload
from .config import ROOT, load_games, load_settings, parse_ping
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


def sample_payloads(kind: str = "all", game: str = "") -> list[tuple[str, str, dict]]:
    """[(feature, name, payload)] for every sample card."""
    settings = load_settings()
    games = load_games()
    out = []
    if kind in ("all", "schedule"):
        for key, data in SCHEDULE_SAMPLES.items():
            if key in games and (not game or game == key):
                out.append(("schedule", f"schedule_{key}",
                            schedule_payload(games[key], data, settings, settings.ping("schedule", key))))
    if kind in ("all", "codes"):
        for key, codes in CODE_SAMPLES.items():
            if key in games and (not game or game == key):
                for i, p in enumerate(codes_payloads(games[key], codes, settings,
                                                     settings.ping("codes", key), int(time.time()))):
                    out.append(("codes", f"codes_{key}{'_' + str(i + 1) if i else ''}", p))
    return out


async def cmd_test_card(args) -> int:
    import aiohttp
    from .discord import WebhookClient
    settings = load_settings()
    rc = 0
    async with aiohttp.ClientSession() as session:
        client = WebhookClient(session, dry_run=settings.dry_run or args.dry_run)
        for feature, name, payload in sample_payloads(args.kind, args.game):
            key = name.split("_", 1)[1].split("_")[0]
            url = settings.webhook(feature, key)
            if not url:
                print(f"[{name}] no webhook for {feature}/{key} — printing payload instead")
                print(json.dumps(payload, ensure_ascii=False, indent=2)[:3000])
                continue
            res = await client.send(url, payload)
            print(f"[{name}] {'OK' if res.ok else 'FAILED'} {res.status} {res.error}")
            rc |= 0 if res.ok else 1
    return rc


def cmd_preview(args) -> int:
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    for _feature, name, payload in sample_payloads(args.kind, args.game):
        problems = validate_payload(payload)
        (out / f"{name}.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"{name}.json  {'OK' if not problems else 'PROBLEMS: ' + '; '.join(problems)}")
    print(f"\nWrote {out}/ — paste a file's JSON into https://discohook.app (Components V2) to preview.")
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
    for g in games.values():
        sched_hook = "✓" if settings.webhook("schedule", g.key) else "—"
        codes_hook = "✓" if settings.webhook("codes", g.key) else "—"
        sp = settings.ping("schedule", g.key).text or "no ping"
        cp = settings.ping("codes", g.key).text or "no ping"
        print(f"  {'✓' if g.enabled else '·'} {g.key:9} {g.name:22} schedule[{sched_hook} {sp}] "
              f"codes[{codes_hook} {cp}] X={','.join(g.x_accounts) or '—'} "
              f"codes_sources={len(g.codes.get('sources', []))}")
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
    print("config OK" if ok else "config has problems (see '!' lines)")
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
                   choices=["run", "loop", "bot", "test-card", "preview", "validate"])
    p.add_argument("--dry-run", action="store_true", help="build + log cards, never post")
    p.add_argument("--only", choices=["schedule", "codes"], help="run one feature")
    p.add_argument("--game", default="", help="restrict to one game key (e.g. starrail)")
    p.add_argument("--repost", default="", help="force a NEW post for game:version (e.g. genshin:7.2)")
    p.add_argument("--kind", default="all", choices=["all", "schedule", "codes"], help="test-card / preview")
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
    if args.command == "loop":
        return asyncio.run(cmd_loop(args))
    if args.command == "bot":
        from .bot import run_bot
        return run_bot()
    return asyncio.run(cmd_run(args))


if __name__ == "__main__":
    sys.exit(main())
