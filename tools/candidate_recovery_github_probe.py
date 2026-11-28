"""One-shot synthetic recovery probe against the current development branch only.

No Discord requests, no production state, and no real article or message IDs.
The temporary ledger must already be committed and is locked after resolution.
"""
from __future__ import annotations

import asyncio
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from gamexpress.candidate_news_checkpoint import IsolatedGitLedger  # noqa: E402
from gamexpress.candidate_news_delivery import DeliveryHold  # noqa: E402
from gamexpress.candidate_news_recovery import inspect_record, reviewed_resolution  # noqa: E402

BRANCH = "arena/98b5f4e1-game-express"
LEDGER = "state/feature3-recovery-probe.json"
SOURCE, ROUTE, ARTICLE, SIGNATURE = "silverpalace", "a" * 16, "987654321", "b" * 64


def guard():
    if (os.environ.get("GITHUB_REPOSITORY") != "uesu/Game-Express"
            or os.environ.get("GITHUB_REF_NAME") != BRANCH
            or os.environ.get("GITHUB_REF") != f"refs/heads/{BRANCH}"
            or os.environ.get("GITHUB_EVENT_NAME") != "workflow_dispatch"
            or os.environ.get("GITHUB_RUN_ATTEMPT") != "1"):
        raise ValueError("wrong test context")


def git(*args):
    result = subprocess.run(["git", *args], cwd=ROOT, stdin=subprocess.DEVNULL,
                            capture_output=True, timeout=45, check=False)
    if result.returncode:
        raise ValueError("Git operation not confirmed")
    return result.stdout


def new_ledger():
    ledger = IsolatedGitLedger(ROOT, BRANCH)
    ledger.LEDGER = LEDGER
    return ledger


async def main():
    guard()
    ledger = new_ledger()
    if not await ledger.open():
        raise ValueError("probe ledger unavailable")
    try:
        info = inspect_record(ledger, SOURCE, ROUTE)
        if info != {"source": SOURCE, "pending": 1, "posted": 0, "partial": True,
                    "article_id": ARTICLE, "pages": 1, "confirmed_pages": 0,
                    "inflight": True, "signature": SIGNATURE, "held_page": 1}:
            raise ValueError("probe already used or unexpected state")
        await reviewed_resolution(ledger, SOURCE, ROUTE, article_id=ARTICLE, page=1, signature=SIGNATURE,
                                  resolution="absent", writers_paused=True, evidence_verified=True)
    finally:
        await ledger.close()
    # Restart on the updated branch and inspect the exact remote-confirmed state.
    git("pull", "--ff-only", "origin", BRANCH)
    restarted = new_ledger()
    if not await restarted.open():
        raise ValueError("restart could not verify remote")
    try:
        info = inspect_record(restarted, SOURCE, ROUTE)
        if info.get("inflight") is not False or info.get("confirmed_pages") != 0:
            raise ValueError("recovered state not persisted")
        try:
            await reviewed_resolution(restarted, SOURCE, ROUTE, article_id=ARTICLE, page=1, signature=SIGNATURE,
                                      resolution="absent", writers_paused=True, evidence_verified=True)
        except DeliveryHold:
            pass
        else:
            raise ValueError("stale correction unexpectedly accepted")
    finally:
        await restarted.close()
    print("::notice title=Synthetic candidate recovery::remote-checkpoint=pass restart=pass stale-decision=held posts=0 production-state=unchanged", flush=True)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception:  # noqa: BLE001 — no remote output, credential or exception text
        raise SystemExit("Synthetic recovery held; inspect the development ledger before any further action.") from None
