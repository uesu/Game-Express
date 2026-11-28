"""One-time development-branch GitHub checkpoint probe; simulated sends only.

The probe modifies only its dedicated tracked JSON file on the fixed development
branch. It never posts, touches monitor state, or handles any Discord secrets.
If interrupted or failed, inspect the branch before taking any further action.
"""
from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from gamexpress import candidate_news_delivery as delivery  # noqa: E402
from gamexpress.candidate_news_checkpoint import IsolatedGitLedger  # noqa: E402
from gamexpress.cards import news_payloads  # noqa: E402
from gamexpress.config import Game  # noqa: E402
from gamexpress.models import Item  # noqa: E402

BRANCH = "arena/98b5f4e1-game-express"
LEDGER = "state/candidate_ledger_probe.json"
# Run 46037384333 completed. Never repeat this mutating probe automatically.
PROBE_COMPLETED = True


def git(*args):
    result = subprocess.run(["git", *args], cwd=ROOT, stdin=subprocess.DEVNULL,
                            capture_output=True, timeout=30, check=False)
    if result.returncode:
        raise ValueError("Git probe failed")
    return result.stdout


async def run():
    if PROBE_COMPLETED:
        raise ValueError("development Git probe already completed")
    if (os.environ.get("GITHUB_REPOSITORY") != "uesu/Game-Express"
            or os.environ.get("GITHUB_REF_NAME") != BRANCH
            or os.environ.get("GITHUB_RUN_ATTEMPT") != "1"
            or os.environ.get("GITHUB_EVENT_NAME") != "workflow_dispatch"):
        raise ValueError("incorrect development probe context")
    if git("remote", "get-url", "origin").decode().strip() not in (
            "https://github.com/uesu/Game-Express", "https://github.com/uesu/Game-Express.git"):
        raise ValueError("unexpected origin")
    if git("status", "--porcelain") or json.loads((ROOT / LEDGER).read_text()) != {"schema": 1, "candidate_news": {}}:
        raise ValueError("probe not clean and uninitialized")
    initial_head = git("rev-parse", "HEAD")
    first, stale = IsolatedGitLedger(ROOT, BRANCH), IsolatedGitLedger(ROOT, BRANCH)
    first.LEDGER = stale.LEDGER = LEDGER
    try:
        if not await first.open() or not await stale.open():
            raise ValueError("ledger unavailable")
        row = {"id": "999999", "title": "Synthetic probe", "date": "2025-01-01"}
        record = delivery.ingest("silverpalace", "a" * 16, None, [row])
        game = Game(key="silverpalace", name="Silver Palace", short="Silver", enabled=False, color=0)
        item = Item(source="silverpalace", game="silverpalace", id="999999", title="Synthetic probe",
                    url="https://silverpalace.elementagames.com/en-us/newsDetail?id=999999", text="", published_ts=0,
                    article_blocks=[{"kind": "text", "text": "Simulated page; no Discord request."}])
        card = news_payloads(game, item)[0]
        sends = []

        async def checkpoint(snapshot):
            return await first.checkpoint("silverpalace", snapshot)

        async def render(article):
            return [card, card]

        async def send(page):
            # The real remote branch was verified by the preceding checkpoint.
            held = first.data["candidate_news"]["silverpalace"]["partial"]
            if not held or not held["inflight"]:
                raise ValueError("missing write-ahead intent")
            sends.append(len(sends) + 1)
            return SimpleNamespace(ok=True, ambiguous=False, message_id=str(900000 + len(sends)))

        record = await delivery.deliver_oldest(record, "silverpalace", "a" * 16, as_of=1795824000,
                                               checkpoint=checkpoint, render=render, send=send, max_pages=1)
        if record["partial"]["messages"] != ["900001"]:
            raise ValueError("first checkpoint incomplete")
        if await stale.checkpoint("silverpalace", record) or not stale.poisoned:
            raise ValueError("stale writer was not held")
        record = await delivery.deliver_oldest(record, "silverpalace", "a" * 16, as_of=1795824000,
                                               checkpoint=checkpoint, render=render, send=send, max_pages=1)
        if record["posted"]["999999"]["messages"] != ["900001", "900002"] or sends != [1, 2]:
            raise ValueError("resume or simulated delivery incorrect")
        if git("rev-parse", "HEAD") != initial_head or git("status", "--porcelain"):
            raise ValueError("monitor checkout changed")
        print("::notice title=Development GitHub ledger::remote-verified=1 stale-writer-held=1 "
              "simulated-pages=2 resume=pass checkout-unchanged=1 discord-posts=0", flush=True)
    finally:
        await first.close()
        await stale.close()


if __name__ == "__main__":
    if sys.argv[1:]:
        raise SystemExit("This probe has no arguments.")
    try:
        asyncio.run(run())
    except Exception:  # noqa: BLE001 — never expose Git credentials or remote output
        raise SystemExit("Development Git probe held; inspect the remote branch before further action.") from None
