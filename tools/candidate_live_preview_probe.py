"""Read-only development probe of the real candidate preview; never posts or writes state."""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from gamexpress.candidate_news_checkpoint import IsolatedGitLedger  # noqa: E402
from gamexpress.candidate_news_recovery import run_from_environment  # noqa: E402

BRANCH = "arena/98b5f4e1-game-express"


async def main():
    if (os.environ.get("GITHUB_REPOSITORY") != "uesu/Game-Express" or os.environ.get("GITHUB_REF_NAME") != BRANCH
            or os.environ.get("GITHUB_REF") != f"refs/heads/{BRANCH}"
            or os.environ.get("GITHUB_EVENT_NAME") != "workflow_dispatch"):
        raise ValueError("wrong test context")
    IsolatedGitLedger.LEDGER = "state/feature3-live-preview-probe.json"
    for source in ("nte", "endfield", "silverpalace"):
        os.environ["RECOVERY_SOURCE"] = source
        try:
            await run_from_environment()
            print(f"::notice title=Live candidate preview::{source}=pass sends=0 checkpoints=0", flush=True)
        except Exception:  # noqa: BLE001 — no body, response, URL or exception text
            print(f"::warning title=Live candidate preview::{source}=held sends=0 checkpoints=0", flush=True)
            raise ValueError("live preview held") from None


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception:  # noqa: BLE001 — no secret, source data or Git output in logs
        raise SystemExit("Live preview held; no Discord posts or ledger writes were attempted.") from None
