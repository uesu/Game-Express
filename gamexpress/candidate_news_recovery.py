"""Attended candidate-news reconciliation; never sends to Discord.

The Actions workflow must serialize with the monitor, and the operator must pause
all schedulers and writers including any other repository. The tool cannot prove
Discord delivery or that external writers are paused. A failed/ambiguous Git
operation requires inspecting the remote before attempting another correction.
"""
from __future__ import annotations

import asyncio
import json
import os

from .candidate_news_checkpoint import IsolatedGitLedger, reconcile_checkpointed
from .candidate_news_delivery import SOURCES, DeliveryHold, _validate, destination
from .candidate_news_runner import authoritative_branch
from .config import ROOT, load_settings


def inspect_record(ledger, source, route):
    """Describe only a validated ledger record; never use a webhook or change state."""
    if ledger.poisoned or not isinstance(ledger.data, dict):
        raise DeliveryHold("authoritative ledger unavailable")
    record = ledger.data.get("candidate_news", {}).get(source)
    if record is None:
        raise DeliveryHold("candidate record unavailable")
    record = _validate(record, source, route)
    partial = record["partial"]
    result = {"source": source, "pending": len(record["pending"]), "posted": len(record["posted"]),
              "partial": partial is not None}
    if partial:
        result.update({"article_id": partial["id"], "pages": partial["pages"],
                       "confirmed_pages": len(partial["messages"]), "inflight": partial["inflight"],
                       "signature": partial["signature"]})
        if partial["inflight"]:
            result["held_page"] = len(partial["messages"]) + 1
    return result


async def reviewed_resolution(ledger, source, route, *, article_id, page, signature, resolution,
                              message_id=None, writers_paused=False, evidence_verified=False):
    """Apply only an explicitly attested, independently verified operator decision."""
    if writers_paused is not True or evidence_verified is not True:
        raise DeliveryHold("operator attestations required")
    inspect_record(ledger, source, route)
    return await reconcile_checkpointed(ledger, source, route, article_id=article_id, page=page,
                                        signature=signature, resolution=resolution, message_id=message_id)


async def run_from_environment():
    """Run only on the explicitly configured primary Actions repository and branch."""
    settings = load_settings()
    source = os.environ.get("RECOVERY_SOURCE", "")
    mode = os.environ.get("RECOVERY_MODE", "")
    if mode not in ("inspect", "resolve", "initialize") or (mode != "initialize" and source not in SOURCES):
        raise DeliveryHold("invalid recovery request")
    branch = authoritative_branch(settings, ROOT)
    if branch is None:
        raise DeliveryHold("authority unavailable")
    ledger = IsolatedGitLedger(ROOT, branch)
    if mode == "initialize":
        if (os.environ.get("RECOVERY_WRITERS_PAUSED") != "true"
                or os.environ.get("RECOVERY_INIT_CONFIRM") != "FIRST_INSTALL_BACKFILL"):
            raise DeliveryHold("first-install attestations required")
        targets = [destination(settings, candidate) for candidate in sorted(SOURCES)]
        if any(target is None for target in targets) or len({target[1] for target in targets}) != len(SOURCES):
            raise DeliveryHold("distinct dedicated destinations required")
        if not await ledger.initialize_empty():
            raise DeliveryHold("ledger initialization not confirmed")
        print("Empty ledger checkpointed. No discovery or Discord messages sent; release gate remains closed.")
        return
    target = destination(settings, source)
    if target is None:
        raise DeliveryHold("dedicated destination unavailable")
    route = target[1]
    if not await ledger.open():
        raise DeliveryHold("authoritative ledger unavailable")
    try:
        if mode == "inspect":
            print(json.dumps(inspect_record(ledger, source, route), sort_keys=True))
            return
        page_text = os.environ.get("RECOVERY_PAGE", "")
        if not page_text.isascii() or not page_text.isdecimal() or len(page_text) > 3:
            raise DeliveryHold("invalid held page")
        mid = os.environ.get("RECOVERY_MESSAGE_ID", "") or None
        await reviewed_resolution(
            ledger, source, route,
            article_id=os.environ.get("RECOVERY_ARTICLE_ID", ""), page=int(page_text),
            signature=os.environ.get("RECOVERY_SIGNATURE", ""),
            resolution=os.environ.get("RECOVERY_RESOLUTION", ""), message_id=mid,
            writers_paused=os.environ.get("RECOVERY_WRITERS_PAUSED") == "true",
            evidence_verified=os.environ.get("RECOVERY_EVIDENCE_VERIFIED") == "true",
        )
        print("Reviewed correction checkpointed. No Discord messages sent; keep writers paused until reviewed.")
    finally:
        await ledger.close()


if __name__ == "__main__":
    try:
        asyncio.run(run_from_environment())
    except Exception:  # noqa: BLE001 — no secrets, remote response or exceptions in logs
        raise SystemExit("Recovery held. Inspect the authoritative ledger and destination before any retry.") from None
