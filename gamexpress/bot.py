"""Optional Discord bot mode (for free 24/7 hosts — see docs/HOSTING.md).

  python -m gamexpress bot        (needs DISCORD_BOT_TOKEN; pip install -r requirements-bot.txt)

* Runs the SAME monitor every LOOP_MINUTES (posting through your webhooks, same cards).
* Slash commands (public replies, Components V2 — identical look to the auto posts):
    /codes <game>     active codes known to the bot, with Redeem buttons
    /schedule <game>  the latest tracked version-schedule card
    /status           instance role, last run, source health
Interaction replies are sent as raw payloads (type 4 + IS_COMPONENTS_V2) through
discord.py's HTTP client, so the exact same card builders are reused.
"""

# NOTE: no `from __future__ import annotations` here on purpose — discord.py evaluates the
# slash-command annotations at runtime, and discord/app_commands are imported lazily
# inside run_bot() so GitHub Actions never needs discord.py installed.
import asyncio
import logging
import os
import time

from .cards import IS_COMPONENTS_V2, codes_payloads, notice_payload, schedule_payload
from .config import Ping, game_is_on, load_games, load_settings
from .state import State
from .textutil import version_key
from .web import STATUS, start_health_server

log = logging.getLogger("gamexpress.bot")


def _latest_schedule(state: State, game_key: str) -> dict | None:
    recs = state.data.get("schedule", {}).get(game_key, {})
    if not recs:
        return None
    ver = sorted(recs, key=version_key)[-1]
    return recs[ver].get("data")


def _active_codes(state: State, game_key: str, now: int) -> list[dict]:
    recs = state.data.get("codes", {}).get(game_key, {})
    fresh = [(c, r) for c, r in recs.items()
             if r.get("status") in ("posted", "seeded") and now - int(r.get("last_seen") or 0) < 2 * 86400]
    fresh.sort(key=lambda cr: -int(cr[1].get("first_seen") or 0))
    return [{"code": c, "rewards": r.get("rewards"), "sources": r.get("sources", [])} for c, r in fresh[:10]]


def run_bot() -> int:
    try:
        import discord
        from discord import app_commands
        from discord.http import Route
    except ImportError:
        print("discord.py is not installed — run: pip install -r requirements-bot.txt")
        return 2
    token = os.getenv("DISCORD_BOT_TOKEN", "").strip()
    if not token:
        print("DISCORD_BOT_TOKEN is not set (see docs/HOSTING.md → 'Create the bot')")
        return 2

    settings = load_settings()
    games = load_games()
    choices = [app_commands.Choice(name=g.name, value=g.key) for g in games.values()
               if game_is_on(g, settings)][:25]     # ENABLE_GAMES / auto_enable_on count too
    intents = discord.Intents.none()
    client = discord.Client(intents=intents)
    tree = app_commands.CommandTree(client)

    async def reply(interaction: "discord.Interaction", payload: dict) -> None:
        data = {k: v for k, v in payload.items() if k in ("components", "flags", "allowed_mentions")}
        data["flags"] = IS_COMPONENTS_V2
        data["allowed_mentions"] = {"parse": []}      # slash replies never ping
        route = Route("POST", "/interactions/{interaction_id}/{interaction_token}/callback",
                      interaction_id=interaction.id, interaction_token=interaction.token)
        await client.http.request(route, json={"type": 4, "data": data})

    @tree.command(name="codes", description="Active redemption codes (with Redeem buttons)")
    @app_commands.choices(game=choices)
    async def codes_cmd(interaction: discord.Interaction, game: app_commands.Choice[str]):
        g = games[game.value]
        state = State.load(settings.state_path)
        codes = _active_codes(state, g.key, int(time.time()))
        if not codes:
            await reply(interaction, notice_payload(f"{g.name} codes", "No active codes are known right now.", g.color))
            return
        await reply(interaction, codes_payloads(g, codes, settings, Ping(), int(time.time()))[0])

    @tree.command(name="schedule", description="Latest version schedule card")
    @app_commands.choices(game=choices)
    async def schedule_cmd(interaction: discord.Interaction, game: app_commands.Choice[str]):
        g = games[game.value]
        data = _latest_schedule(State.load(settings.state_path), g.key)
        if not data:
            await reply(interaction, notice_payload(f"{g.name} schedule", "No version schedule tracked yet.", g.color))
            return
        await reply(interaction, schedule_payload(g, data, settings, Ping()))

    @tree.command(name="status", description="Game-Express status")
    async def status_cmd(interaction: discord.Interaction):
        last = STATUS.get("last_run")
        body = (f"Instance: **{settings.instance_name}** ({settings.instance_role})\n"
                f"Features: {', '.join(sorted(settings.features)) or 'none'}\n"
                f"Last run: {f'<t:{last}:R>' if last else 'not yet'}\n"
                + "\n".join(f"- {r}" for r in STATUS.get("last_report", [])[-6:]))
        await reply(interaction, notice_payload("Game-Express status", body))

    async def monitor_loop():
        from .runner import run_once
        minutes = max(5, int(os.getenv("LOOP_MINUTES", "10")))
        await client.wait_until_ready()
        while not client.is_closed():
            try:
                ctx = await run_once(load_settings())
                STATUS.update({"last_run": int(time.time()), "last_report": ctx.report[-10:]})
            except Exception:
                log.exception("monitor run failed")
            await asyncio.sleep(minutes * 60)

    @client.event
    async def setup_hook():
        await start_health_server()
        await tree.sync()
        asyncio.create_task(monitor_loop())
        log.info("slash commands synced; monitor loop started")

    client.run(token, log_handler=None)
    return 0
