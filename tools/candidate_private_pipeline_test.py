"""Bounded candidate-delivery test: isolated local Git ledger and private webhook only.

All cards are fetched/preflighted before the first POST. The local bare remote is
not production persistence and disappears when the job ends. Never automatically
rerun a failed or interrupted send: inspect the private channel first.
"""
from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import aiohttp  # noqa: E402
from live_candidate_probe import NoRedirectSession  # noqa: E402

from gamexpress import candidate_news_delivery as delivery  # noqa: E402
from gamexpress.candidate_news_checkpoint import GitCheckpoint  # noqa: E402
from gamexpress.config import load_settings  # noqa: E402
from gamexpress.http import Fetcher  # noqa: E402
from gamexpress.state import State  # noqa: E402

SOURCES = ("nte", "endfield", "silverpalace")
# Avoid repeating the earlier private display tests, especially the one-shot NTE trailer.
ALREADY_TESTED = {"nte": {"252469", "252474"}, "endfield": {"0766", "7011", "1340", "3840"},
                  "silverpalace": {"1", "120"}}
MAX_MESSAGES = 8
# Pinned after the no-post preparation: any upstream change holds the test.
EXPECTED = (("nte", "252471", 1), ("endfield", "3857", 2), ("silverpalace", "7", 1))


async def prepare(fetcher, settings):
    prepared = []
    for source in SOURCES:
        rows = await delivery.discover(fetcher, source)
        queue = delivery.ingest(source, "a" * 16, None, rows)["pending"]
        chosen = None
        examined = 0
        for row in queue:
            if row["id"] in ALREADY_TESTED[source]:
                continue
            if examined >= 12:
                break
            examined += 1
            try:
                pages = await delivery.render_candidate(fetcher, settings, source, row)
            except delivery.DeliveryHold:
                continue
            # A multi-page Endfield article exercises restart and partial-page resume.
            if (source == "endfield" and not 2 <= len(pages) <= 4) or (source != "endfield" and len(pages) > 2):
                continue
            chosen = (source, row, pages)
            break
        if chosen is None:
            raise ValueError("no bounded new article found")
        prepared.append(chosen)
    if sum(len(pages) for _, _, pages in prepared) > MAX_MESSAGES:
        raise ValueError("private test exceeds message limit")
    for source, row, pages in prepared:
        print(f"::notice title=Private pipeline prepared::{source} id={row['id']} pages={len(pages)}", flush=True)
    return prepared


def git(root, *args):
    # Subprocess output may contain paths; nothing here ever handles a webhook URL.
    result = subprocess.run(["git", *args], cwd=root, stdin=subprocess.DEVNULL,
                            capture_output=True, timeout=30, check=False)
    if result.returncode:
        raise ValueError("isolated Git setup failed")
    return result.stdout


def isolated_repository(base):
    work = Path(base) / "work"
    remote = Path(base) / "private-ledger.git"
    work.mkdir()
    git(work, "init", "--bare", str(remote))
    git(work, "init", "-b", "private-test")
    git(work, "config", "user.name", "Private test")
    git(work, "config", "user.email", "test@example.invalid")
    (work / "state").mkdir()
    (work / "state/state.json").write_text('{"schema":1}\n', encoding="utf-8")
    git(work, "add", "state/state.json")
    git(work, "commit", "-m", "isolated initial state")
    git(work, "remote", "add", "origin", str(remote))
    git(work, "push", "origin", "HEAD:refs/heads/private-test")
    return work, remote


async def send_prepared(session, prepared, webhook):
    settings = load_settings({f"DISCORD_WEBHOOK_NEWS_{source.upper()}": webhook for source in SOURCES})
    targets = {source: delivery.destination(settings, source) for source in SOURCES}
    if any(target is None for target in targets.values()):
        raise ValueError("private webhook unavailable or invalid")
    sent = 0
    with tempfile.TemporaryDirectory(prefix="candidate-private-") as temp:
        work, remote = isolated_repository(temp)
        path = work / "state/state.json"
        for source, row, pages in prepared:
            fingerprint = targets[source][1]
            state = State.load(path)
            record = delivery.ingest(source, fingerprint, None, [row])

            async def render(current, *, _row=row, _pages=pages):
                if current != _row:
                    raise ValueError("article identity changed")
                return _pages

            async def send(payload, *, _source=source, _id=row["id"]):
                nonlocal sent
                await asyncio.sleep(1.5)
                persisted = json.loads(git(work, "--git-dir", str(remote), "show",
                                           "refs/heads/private-test:state/state.json"))
                partial = persisted["candidate_news"][_source]["partial"]
                if not partial or not partial["inflight"] or partial["id"] != _id:
                    raise ValueError("write-ahead intent not persisted")
                result = await delivery.send_candidate_once(session, settings, _source, payload)
                if result.ok:
                    sent += 1
                print(f"::notice title=Private pipeline send::{_source} id={_id} "
                      f"confirmed-total={sent} status={'confirmed' if result.ok else 'hold'}", flush=True)
                return result

            while record["pending"]:
                # One page per invocation, then reload the JSON as a process restart would.
                checkpoint = GitCheckpoint(work, state, source, "private-test")
                record = await delivery.deliver_oldest(record, source, fingerprint, as_of=int(time.time()),
                                                        checkpoint=checkpoint, render=render, send=send, max_pages=1)
                committed = git(work, "--git-dir", str(remote), "show", "refs/heads/private-test:state/state.json")
                remote_data = json.loads(committed)
                state = State.load(path)
                if state.data.get("candidate_news", {}).get(source) != remote_data["candidate_news"][source]:
                    raise ValueError("isolated checkpoint mismatch")
                record = state.data["candidate_news"][source]
            # A restarted completed record cannot send the same article again.
            before = sent
            state_record = delivery.ingest(source, fingerprint, record, [row])
            if state_record["pending"] or sent != before:
                raise ValueError("restart deduplication failed")
            print(f"::notice title=Private pipeline checkpoint::{source} id={row['id']} "
                  f"pages={len(pages)} restart=pass isolated-ledger=pass", flush=True)
    return sent


async def main(prepare_only):
    if not prepare_only and os.environ.get("GITHUB_RUN_ATTEMPT") != "1":
        raise ValueError("automatic or manual workflow reruns are not allowed")
    settings = load_settings({"NEWS_EXPAND_FULL": "1"})
    webhook = os.environ.get("FEATURE3_TEST_WEBHOOK", "") if not prepare_only else ""
    if not prepare_only:
        conf = load_settings({f"DISCORD_WEBHOOK_NEWS_{source.upper()}": webhook for source in SOURCES})
        if any(delivery.destination(conf, source) is None for source in SOURCES):
            raise ValueError("private webhook unavailable or invalid")
    async with aiohttp.ClientSession(trust_env=False) as session:
        prepared = await prepare(Fetcher(NoRedirectSession(session)), settings)
        if prepare_only:
            print("::notice title=Private pipeline::preparation only; no state or posts", flush=True)
            return
        if tuple((source, row["id"], len(pages)) for source, row, pages in prepared) != EXPECTED:
            raise ValueError("prepared selection changed; no posts")
        sent = await send_prepared(session, prepared, webhook)
        print(f"::notice title=Private pipeline complete::confirmed={sent} sources=3 production-state=unchanged", flush=True)


if __name__ == "__main__":
    if sys.argv[1:] not in ([], ["--prepare-only"]):
        raise SystemExit("Usage: candidate_private_pipeline_test.py [--prepare-only]")
    try:
        asyncio.run(main(prepare_only=bool(sys.argv[1:])))
    except Exception:  # noqa: BLE001 — do not leak URLs or response content
        raise SystemExit("Private pipeline held. Inspect the private channel before any new send; no automatic retry.") from None
