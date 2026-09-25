"""Optional health endpoint for hosts that need an HTTP port (Render / Koyeb / uptime pings).
Starts only when the PORT environment variable is set."""

from __future__ import annotations

import logging
import os
import time

from aiohttp import web

from . import __version__

log = logging.getLogger("gamexpress.web")
STATUS: dict = {"started": int(time.time()), "last_run": None, "last_report": [], "version": __version__}


async def _health(_request: web.Request) -> web.Response:
    return web.json_response({"ok": True, **STATUS})


async def start_health_server() -> web.AppRunner | None:
    port = os.getenv("PORT")
    if not port:
        return None
    app = web.Application()
    app.router.add_get("/", _health)
    app.router.add_get("/healthz", _health)
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", int(port)).start()
    log.info("health endpoint listening on 0.0.0.0:%s (/healthz)", port)
    return runner
