"""One-shot synthetic first-install probe; no Discord or production operations."""
from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from gamexpress.candidate_news_checkpoint import IsolatedGitLedger  # noqa: E402
from gamexpress.candidate_news_delivery import DeliveryHold  # noqa: E402
from gamexpress.candidate_news_recovery import run_from_environment  # noqa: E402

BRANCH = "arena/98b5f4e1-game-express"
PATH = "state/feature3-initialization-probe.json"


def git(*args):
    result = subprocess.run(["git", *args], cwd=ROOT, stdin=subprocess.DEVNULL,
                            capture_output=True, timeout=45, check=False)
    if result.returncode:
        raise ValueError("Git operation not confirmed")
    return result.stdout


async def main():
    if (os.environ.get("GITHUB_REPOSITORY") != "uesu/Game-Express"
            or os.environ.get("GITHUB_REF_NAME") != BRANCH
            or os.environ.get("GITHUB_REF") != f"refs/heads/{BRANCH}"
            or os.environ.get("GITHUB_EVENT_NAME") != "workflow_dispatch"
            or os.environ.get("GITHUB_RUN_ATTEMPT") != "1"):
        raise ValueError("wrong test context")
    IsolatedGitLedger.LEDGER = PATH
    await run_from_environment()
    git("pull", "--ff-only", "origin", BRANCH)
    if json.loads(git("show", f"HEAD:{PATH}")) != {"schema": 1, "candidate_news": {}}:
        raise ValueError("unexpected test ledger")
    try:
        await run_from_environment()
    except DeliveryHold:
        pass
    else:
        raise ValueError("repeat initialization accepted")
    print("::notice title=Synthetic initialization::initialization=pass remote-restart=pass repeat=held posts=0", flush=True)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception:  # noqa: BLE001 — do not expose remote output or exceptions
        raise SystemExit("Probe held; inspect the development branch before any retry.") from None
