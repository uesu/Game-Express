"""Temporary live-source release probe: synthetic Git repository, never Discord."""
from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import aiohttp

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from gamexpress import candidate_news_delivery as delivery  # noqa: E402
from gamexpress import candidate_news_runner as runner  # noqa: E402
from gamexpress.config import load_settings  # noqa: E402
from gamexpress.http import BOT_UA, Fetcher  # noqa: E402
from gamexpress.news_animation import multipart_form  # noqa: E402

BRANCH = "arena/98b5f4e1-game-express"
HOOKS = {"nte": "https://discord.com/api/webhooks/111111111111111111/aaaaaaaaaaaaaaaaaaaa",
         "endfield": "https://discord.com/api/webhooks/222222222222222222/bbbbbbbbbbbbbbbbbbbb",
         "silverpalace": "https://discord.com/api/webhooks/333333333333333333/cccccccccccccccccccc"}


def git(cwd, *args):
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, check=True, timeout=30).stdout


async def main():
    if (os.environ.get("GITHUB_REPOSITORY") != "uesu/Game-Express"
            or os.environ.get("GITHUB_REF") != f"refs/heads/{BRANCH}"
            or os.environ.get("GITHUB_EVENT_NAME") != "workflow_dispatch"
            or not runner.CANDIDATE_NEWS_READY):
        raise ValueError("wrong probe context or release switch is off")
    env = {"ENABLED_FEATURES": "news", "NEWS_GAMES": ",".join(sorted(HOOKS)),
           "NEWS_CANDIDATES_BACKFILL": "1", "NO_PING": "1"}
    env.update({f"DISCORD_WEBHOOK_NEWS_{name.upper()}": url for name, url in HOOKS.items()})
    settings = load_settings(env)
    with tempfile.TemporaryDirectory(prefix="candidate-release-probe-") as tmp:
        base = Path(tmp)
        remote, repo = base / "remote.git", base / "repo"
        repo.mkdir()
        git(base, "init", "--bare", str(remote))
        git(repo, "init", "-b", BRANCH)
        git(repo, "config", "user.name", "Synthetic probe")
        git(repo, "config", "user.email", "probe@example.invalid")
        (repo / "state").mkdir()
        records = {}
        for source in HOOKS:
            route = delivery.destination(settings, source)[1]
            records[source] = {"version": 1, "source": source, "route": route, "pending": [],
                               "posted": {}, "partial": None}
        (repo / "state/candidate_news.json").write_text(json.dumps({"schema": 1, "candidate_news": records}), encoding="utf-8")
        git(repo, "add", "state")
        git(repo, "commit", "-m", "synthetic first-install records")
        git(repo, "remote", "add", "origin", str(remote))
        git(repo, "push", "origin", f"HEAD:refs/heads/{BRANCH}")
        sends = []

        async def fake_send(session, conf, source, payload, *, files=None):
            saved = json.loads(git(base, "--git-dir", str(remote), "show",
                                   f"refs/heads/{BRANCH}:state/candidate_news.json"))
            partial = saved["candidate_news"][source]["partial"]
            if not partial or not partial["inflight"]:
                raise ValueError("intent not persisted before synthetic send")
            if files is not None:
                multipart_form(payload, files)  # validate upload plan without sending
            sends.append(source)
            return SimpleNamespace(ok=True, ambiguous=False, message_id=str(1000 + len(sends)))

        def no_post(*args, **kwargs):
            raise AssertionError("POST prohibited in live-source probe")

        async with aiohttp.ClientSession(headers={"User-Agent": BOT_UA}) as session:
            fetcher = Fetcher(session, timeout=settings.http_timeout)
            ctx = SimpleNamespace(settings=settings, active=True, now=int(time.time()), fetcher=fetcher,
                                  webhook=SimpleNamespace(session=session), report=[], warnings=[])
            with (patch.object(runner, "ROOT", repo), patch.object(runner, "authoritative_branch", return_value=BRANCH),
                  patch.object(delivery, "send_candidate_once", fake_send), patch.object(aiohttp.ClientSession, "post", no_post)):
                await runner.run_candidate_news(ctx)
                if ctx.warnings or set(sends) != set(HOOKS):
                    print("Probe reports:", ctx.report, "warnings:", ctx.warnings, flush=True)
                    raise ValueError("one or more sources held")
                rows = await delivery.discover(fetcher, "silverpalace")
                long_row = next((entry for entry in rows if entry["id"] == "34"), None)
                if not long_row:
                    raise ValueError("known long article missing from source snapshot")
                pages = await delivery.render_candidate(fetcher, settings, "silverpalace", long_row)
                if len(pages) <= 12:
                    raise ValueError("known long article did not exercise candidate page bound")
                print(f"::notice title=Candidate release probe::all 3 live sources passed; simulated pages={len(sends)}; long Silver pages={len(pages)}; Discord POSTs=0", flush=True)
        saved = json.loads(git(base, "--git-dir", str(remote), "show",
                               f"refs/heads/{BRANCH}:state/candidate_news.json"))
        for source in HOOKS:
            record = saved["candidate_news"][source]
            if not record["posted"] and (not record["partial"] or not record["partial"]["messages"]):
                raise ValueError("synthetic confirmation missing")
            if record["partial"] and record["partial"]["inflight"]:
                raise ValueError("unexpected in-flight page")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception:  # noqa: BLE001 -- no endpoints or raw responses in logs
        raise SystemExit("Live-source synthetic-send release probe held; no Discord POSTs were attempted.") from None
