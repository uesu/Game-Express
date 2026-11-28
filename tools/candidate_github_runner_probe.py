"""No-send synthetic candidate runner + recovery + monitor rebase on dev GitHub.

Both paths are disposable synthetic files, never the production ledger or state.
"""
from __future__ import annotations

import asyncio
import base64
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from gamexpress import candidate_news_delivery as delivery  # noqa: E402
from gamexpress import candidate_news_recovery as recovery  # noqa: E402
from gamexpress import candidate_news_runner as runner  # noqa: E402
from gamexpress.candidate_news_checkpoint import IsolatedGitLedger  # noqa: E402
from gamexpress.config import load_settings  # noqa: E402
from gamexpress.models import Item  # noqa: E402

BRANCH = "arena/98b5f4e1-game-express"
REPO = "uesu/Game-Express"
LEDGER = "state/feature3-e2e-git-probe.json"
MONITOR = "state/feature3-e2e-monitor-probe.json"
SOURCE, ARTICLE = "silverpalace", "987654321"
URL = "https://s.elementagames.com/synthetic-private-test.jpg"
GIF = base64.b64decode("R0lGODlhBAAEAIEAAP8AAAAAAAAAAAAAACH/C05FVFNDQVBFMi4wAwEAAAAh+QQACgAAACwAAAAABAAEAAAICQABCBxIsCCAgAAh+QQBCgABACwAAAAABAAEAIEAAP8AAAAAAAAAAAAICQABCBxIsCCAgAA7")


def git(*args):
    result = subprocess.run(["git", *args], cwd=ROOT, stdin=subprocess.DEVNULL,
                            capture_output=True, timeout=45, check=False)
    if result.returncode:
        raise ValueError("Git operation not confirmed")
    return result.stdout


def guard():
    if (os.environ.get("GITHUB_REPOSITORY") != REPO or os.environ.get("GITHUB_REF_NAME") != BRANCH
            or os.environ.get("GITHUB_REF") != f"refs/heads/{BRANCH}"
            or os.environ.get("GITHUB_EVENT_NAME") != "workflow_dispatch"
            or os.environ.get("GITHUB_RUN_ATTEMPT") != "1"):
        raise ValueError("wrong test context")
    if (json.loads(git("show", f"HEAD:{LEDGER}")) != {"schema": 1, "candidate_news": {}}
            or json.loads(git("show", f"HEAD:{MONITOR}")) != {"synthetic": 0}):
        raise ValueError("probe already used")


class Fetcher:
    def __init__(self):
        self.media_prefixes = {}

    async def verify_media(self, url):
        if url != URL:
            return False
        self.media_prefixes[url] = (GIF[:32], "image/jpeg")
        return True

    async def media_dimensions(self, url):
        return None


async def discover(fetcher, source):
    if source != SOURCE:
        raise ValueError("unexpected source")
    return [{"id": ARTICLE, "title": "Synthetic GitHub runner probe", "date": "2000-01-01"}]


async def article(fetcher, game, row):
    return Item(source=SOURCE, game=SOURCE, id=ARTICLE, title="Synthetic GitHub runner probe",
                url=f"https://silverpalace.elementagames.com/en-us/newsDetail?id={ARTICLE}", text="",
                published_ts=0, article_blocks=[{"kind": "text", "text": "Synthetic, not real news."},
                                                {"kind": "image", "url": URL}])


async def media(fetcher, url):
    if url != URL:
        raise ValueError("unexpected media")
    return GIF


async def main():
    guard()
    settings = load_settings({"ENABLED_FEATURES": "news", "NEWS_GAMES": SOURCE,
        "NEWS_CANDIDATES_BACKFILL": "1", "NO_PING": "1",
        "DISCORD_WEBHOOK_NEWS_SILVERPALACE": "https://discord.com/api/webhooks/111111111111111111/aaaaaaaaaaaaaaaaaaaa",
        "NEWS_CANDIDATES_AUTHORITY_REPOSITORY": REPO, "NEWS_CANDIDATES_AUTHORITY_BRANCH": BRANCH})
    route = delivery.destination(settings, SOURCE)[1]
    IsolatedGitLedger.LEDGER = LEDGER
    attempts = []

    async def fake_send(session, conf, source, payload, *, files=None):
        git("fetch", "origin", BRANCH)
        saved = json.loads(git("show", f"FETCH_HEAD:{LEDGER}"))
        partial = saved["candidate_news"][SOURCE]["partial"]
        if (partial["id"] != ARTICLE or partial["inflight"] is not True or partial["messages"]
                or partial["pages"] != 1 or not files or len(files) != 1):
            raise ValueError("intent checkpoint missing")
        attempts.append(True)
        if len(attempts) == 1:
            return SimpleNamespace(ok=False, message_id=None, ambiguous=True)
        if len(attempts) == 2:
            return SimpleNamespace(ok=True, message_id="101", ambiguous=False)
        raise ValueError("unexpected simulated send")

    async def run_once():
        ctx = SimpleNamespace(settings=settings, active=True, now=int(time.time()), fetcher=Fetcher(),
                              webhook=SimpleNamespace(session=None), report=[], warnings=[])
        await runner.run_candidate_news(ctx)
        return ctx

    with (patch.object(runner, "CANDIDATE_NEWS_READY", True), patch.object(delivery, "discover", discover),
          patch.object(delivery.silverpalace, "news_article", article),
          patch("gamexpress.news_animation.fetch_gif", media), patch.object(delivery, "send_candidate_once", fake_send)):
        first = await run_once()
        if len(attempts) != 1 or not first.warnings:
            raise ValueError("ambiguous attempt did not hold")
        git("pull", "--ff-only", "origin", BRANCH)
        second = await run_once()
        if len(attempts) != 1 or not second.warnings:
            raise ValueError("held page retried unexpectedly")
        ledger = IsolatedGitLedger(ROOT, BRANCH)
        if not await ledger.open():
            raise ValueError("held ledger unavailable")
        try:
            partial = recovery.inspect_record(ledger, SOURCE, route)
            if not partial.get("inflight") or partial.get("held_page") != 1:
                raise ValueError("unexpected held state")
            await recovery.reviewed_resolution(ledger, SOURCE, route, article_id=ARTICLE, page=1,
                                               signature=partial["signature"], resolution="absent",
                                               writers_paused=True, evidence_verified=True)
        finally:
            await ledger.close()
        git("pull", "--ff-only", "origin", BRANCH)
        third = await run_once()
        if len(attempts) != 2 or third.warnings:
            raise ValueError("reviewed resumption did not complete")
    # Emulate the real monitor's final state-only commit/rebase after ledger pushes.
    (ROOT / MONITOR).write_text('{"synthetic":1}\n', encoding="utf-8")
    git("add", "--", MONITOR)
    if git("diff", "--cached", "--name-only", "-z") != MONITOR.encode() + b"\0":
        raise ValueError("unexpected staged file")
    git("config", "user.name", "github-actions[bot]")
    git("config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com")
    git("commit", "-m", "test: synthetic monitor state [skip ci]")
    git("pull", "--rebase", "--autostash", "origin", BRANCH)
    git("push", "origin", f"HEAD:refs/heads/{BRANCH}")
    result = json.loads(git("show", f"HEAD:{LEDGER}"))["candidate_news"][SOURCE]
    remote = git("ls-remote", "--heads", "origin", f"refs/heads/{BRANCH}").split()
    if (result["pending"] or result["partial"] is not None or result["posted"][ARTICLE]["messages"] != ["101"]
            or json.loads(git("show", f"HEAD:{MONITOR}")) != {"synthetic": 1}
            or len(remote) != 2 or remote[0] != git("rev-parse", "HEAD").strip()):
        raise ValueError("final monitor rebase or checkpoint not confirmed")
    print("::notice title=Synthetic GitHub integrated runner::remote-intent=pass ambiguous=held restart=held reviewed=pass rebase=pass discord-posts=0", flush=True)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception:  # noqa: BLE001 — do not expose raw Git output or exception details
        raise SystemExit("Synthetic GitHub runner probe held; inspect development branch before any retry.") from None
