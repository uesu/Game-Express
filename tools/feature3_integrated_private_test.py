"""One approved synthetic private message; durable one-use lock before any POST.

Never run against production. The real candidate runner, renderer, GIF planner and
Discord sender use a local bare-Git ledger; a separate lock on the development
branch makes the entire experiment one-shot, including failed/ambiguous attempts.
No private Discord message ID is pushed to the public development repository.
"""
from __future__ import annotations

import asyncio
import base64
import json
import os
import secrets
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import aiohttp  # noqa: E402
import candidate_private_backfill as historic  # noqa: E402

from gamexpress import candidate_news_delivery as delivery  # noqa: E402
from gamexpress import candidate_news_runner as runner  # noqa: E402
from gamexpress.config import load_settings  # noqa: E402
from gamexpress.models import Item  # noqa: E402
from gamexpress.news_animation import gif_info  # noqa: E402

BRANCH = "arena/98b5f4e1-game-express"
REPOSITORY = "uesu/Game-Express"
LOCK = "state/feature3-integrated-private-test-lock.json"
READY = {"test": "feature3-integrated-private-synthetic-v1", "status": "ready"}
CLAIMED = {"test": READY["test"], "status": "claimed-never-repeat"}
SOURCE = "silverpalace"
ARTICLE = "987654321"
URL = "https://s.elementagames.com/synthetic-private-test.jpg"
GIF = base64.b64decode("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")


def git(root, *args):
    result = subprocess.run(["git", *args], cwd=root, stdin=subprocess.DEVNULL,
                            capture_output=True, timeout=45, check=False)
    if result.returncode:
        raise ValueError("Git operation not confirmed")
    return result.stdout


def guard():
    if (os.environ.get("GITHUB_REPOSITORY") != REPOSITORY or os.environ.get("GITHUB_REF_NAME") != BRANCH
            or os.environ.get("GITHUB_REF") != f"refs/heads/{BRANCH}"
            or os.environ.get("GITHUB_EVENT_NAME") != "workflow_dispatch"
            or os.environ.get("GITHUB_RUN_ATTEMPT") != "1" or not os.environ.get("GH_TOKEN")):
        raise ValueError("wrong private test context")


def current_remote():
    result = git(ROOT, "ls-remote", "--heads", "origin", f"refs/heads/{BRANCH}").splitlines()
    if len(result) != 1:
        raise ValueError("remote branch unavailable")
    parts = result[0].split()
    if len(parts) != 2 or parts[1] != f"refs/heads/{BRANCH}".encode():
        raise ValueError("remote branch mismatch")
    return parts[0]


def claim_once():
    if git(ROOT, "symbolic-ref", "--short", "HEAD").strip() != BRANCH.encode():
        raise ValueError("wrong checkout branch")
    head = git(ROOT, "rev-parse", "HEAD").strip()
    if current_remote() != head or git(ROOT, "status", "--porcelain"):
        raise ValueError("stale or dirty checkout")
    if json.loads(git(ROOT, "show", f"HEAD:{LOCK}")) != READY:
        raise ValueError("private test already claimed or missing")
    (ROOT / LOCK).write_text(json.dumps(CLAIMED, sort_keys=True) + "\n", encoding="utf-8")
    git(ROOT, "add", "--", LOCK)
    if git(ROOT, "diff", "--cached", "--name-only", "-z") != LOCK.encode() + b"\0":
        raise ValueError("unexpected staged paths")
    git(ROOT, "-c", "user.name=github-actions[bot]", "-c",
        "user.email=41898282+github-actions[bot]@users.noreply.github.com", "commit", "-m",
        f"test: claim synthetic private runner {secrets.token_hex(16)} [skip ci]")
    git(ROOT, "push", "origin", f"HEAD:refs/heads/{BRANCH}")
    claimed_head = git(ROOT, "rev-parse", "HEAD").strip()
    if current_remote() != claimed_head:
        raise ValueError("lock not confirmed")
    return claimed_head


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
    return [{"id": ARTICLE, "title": "PRIVATE SYNTHETIC TEST — NOT REAL NEWS", "date": "2000-01-01"}]


async def article(fetcher, game, row):
    if game.key != SOURCE or row["id"] != ARTICLE:
        raise ValueError("unexpected test article")
    return Item(source=SOURCE, game=SOURCE, id=ARTICLE,
                title="PRIVATE SYNTHETIC TEST — NOT REAL NEWS",
                url=f"https://silverpalace.elementagames.com/en-us/newsDetail?id={ARTICLE}", text="",
                published_ts=0, article_blocks=[
                    {"kind": "text", "text": "Private synthetic test only. This is not an official article or announcement."},
                    {"kind": "image", "url": URL},
                    {"kind": "text", "text": "The two-frame animation above is generated test media."},
                ])


async def synthetic_gif(fetcher, url):
    if url != URL:
        raise ValueError("unexpected media")
    return GIF


def make_local_ledger(base):
    remote, work = base / "remote.git", base / "work"
    work.mkdir()
    git(base, "init", "--bare", str(remote))
    git(work, "init", "-b", BRANCH)
    (work / "state").mkdir()
    (work / "state/candidate_news.json").write_text('{"schema":1,"candidate_news":{}}\n', encoding="utf-8")
    git(work, "add", "state/candidate_news.json")
    git(work, "-c", "user.name=Private Test", "-c", "user.email=test@example.invalid", "commit", "-m", "synthetic seed")
    git(work, "remote", "add", "origin", str(remote))
    git(work, "push", "origin", f"HEAD:refs/heads/{BRANCH}")
    return work, remote


async def main():
    guard()
    webhook = os.environ.get("FEATURE3_TEST_WEBHOOK", "")
    settings = load_settings({"ENABLED_FEATURES": "news", "NEWS_GAMES": SOURCE,
                              "NEWS_CANDIDATES_BACKFILL": "1", "NO_PING": "1",
                              "DISCORD_WEBHOOK_NEWS_SILVERPALACE": webhook,
                              "NEWS_CANDIDATES_AUTHORITY_REPOSITORY": REPOSITORY,
                              "NEWS_CANDIDATES_AUTHORITY_BRANCH": BRANCH})
    target = delivery.destination(settings, SOURCE)
    if target is None:
        raise ValueError("private test route unavailable")
    previous = await asyncio.to_thread(historic.gh_api,
                                       f"repos/{REPOSITORY}/issues/comments/{historic.COMMENT_IDS[SOURCE]}")
    previous_state = historic.check_comment(previous, SOURCE, historic.COMMENT_IDS[SOURCE])
    delivery._validate(previous_state, SOURCE, target[1])
    if gif_info(GIF, with_duration=True, with_loop=True) != (320, 120, 2, 140, 0):
        raise ValueError("invalid test GIF")
    fetcher = Fetcher()
    real_render = delivery.render_candidate_animated
    real_send = delivery.send_candidate_once
    sent = []

    async def render_once(fetch, conf, source, row):
        pages, files = await real_render(fetch, conf, source, row)
        if len(pages) != 1 or len(files) != 1 or len(pages[0].get("attachments", [])) != 1:
            raise ValueError("test must fit exactly one GIF message")
        return pages, files

    # Validate synthetic render before claiming the irreversible one-use lock.
    with (patch.object(delivery.silverpalace, "news_article", article),
          patch("gamexpress.news_animation.fetch_gif", synthetic_gif)):
        await render_once(fetcher, settings, SOURCE, (await discover(fetcher, SOURCE))[0])

    with tempfile.TemporaryDirectory(prefix="candidate-private-local-git-") as tmp:
        work, remote = make_local_ledger(Path(tmp))
        claimed_head = await asyncio.to_thread(claim_once)

        async def send_once(session, conf, source, payload, *, files=None):
            if sent or source != SOURCE or not files or len(files) != 1:
                raise ValueError("more than one test send prohibited")
            if await asyncio.to_thread(current_remote) != claimed_head:
                raise ValueError("test lock branch changed")
            saved = json.loads(await asyncio.to_thread(git, work, "--git-dir", str(remote), "show",
                                                       f"refs/heads/{BRANCH}:state/candidate_news.json"))
            partial = saved["candidate_news"][SOURCE]["partial"]
            if partial["id"] != ARTICLE or not partial["inflight"] or partial["pages"] != 1 or partial["messages"]:
                raise ValueError("pre-send checkpoint missing")
            sent.append(True)  # no second call even after an uncertain outcome
            return await real_send(session, conf, source, payload, files=files)

        async with aiohttp.ClientSession() as session:
            ctx = SimpleNamespace(settings=settings, active=True, now=int(time.time()), fetcher=fetcher,
                                  webhook=SimpleNamespace(session=session), report=[], warnings=[])
            with (patch.object(runner, "ROOT", work), patch.object(runner, "_origin_is_authority", return_value=True),
                  patch.object(runner, "CANDIDATE_NEWS_READY", True), patch.object(delivery, "discover", discover),
                  patch.object(delivery.silverpalace, "news_article", article),
                  patch.object(delivery, "render_candidate_animated", render_once),
                  patch.object(delivery, "send_candidate_once", send_once),
                  patch("gamexpress.news_animation.fetch_gif", synthetic_gif)):
                await runner.run_candidate_news(ctx)
        saved = json.loads(git(work, "--git-dir", str(remote), "show",
                               f"refs/heads/{BRANCH}:state/candidate_news.json"))
        record = saved["candidate_news"].get(SOURCE, {})
        if (ctx.warnings or len(sent) != 1 or record.get("pending") or record.get("partial") is not None
                or len(record.get("posted", {}).get(ARTICLE, {}).get("messages", [])) != 1):
            raise ValueError("test send or local checkpoint not confirmed")
    print("::notice title=Private integrated test::confirmed=1 messages=1 gifs=1 local-git-checkpoints=pass locked=1", flush=True)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception:  # noqa: BLE001 — no secrets, response bodies, IDs or remote output in logs
        raise SystemExit("Private test held. Never rerun; inspect the lock and private channel first.") from None
