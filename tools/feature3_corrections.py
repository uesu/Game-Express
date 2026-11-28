"""Private correction journal for the fixed NTE notices and heading example.

Preparation never posts. A locked, separate journal is mandatory before sending;
any ambiguous send or in-flight state requires manual inspection, not a retry.
"""
from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import aiohttp  # noqa: E402
import candidate_private_backfill as historic  # noqa: E402
from live_candidate_probe import NoRedirectSession  # noqa: E402

from gamexpress import candidate_news_delivery as delivery  # noqa: E402
from gamexpress.http import Fetcher  # noqa: E402

MARKER = "feature3-nte-format-corrections-v1"
NOTICE_IDS = frozenset(["265196", "265063", "264938", "264852", "264812", "264665", "264504", "264393", "264250", "264144", "263938", "263816", "263718", "263598", "263505", "263409", "263286", "263221", "263143", "263019", "262911", "262793", "262705", "262601", "262456", "262335", "262255", "262132", "262101", "262038"])
IDS = NOTICE_IDS | {"262998"}
COMMENT_ID = 7235741976  # independently verified; preparation permanently locked


async def prepare(fetcher, route):
    if COMMENT_ID:
        raise ValueError("preparation is locked")
    original_comment = await asyncio.to_thread(historic.gh_api,
        f"repos/{historic.REPOSITORY}/issues/comments/{historic.COMMENT_IDS['nte']}")
    original = historic.check_comment(original_comment, "nte", historic.COMMENT_IDS["nte"])
    delivery._validate(original, "nte", route)
    if original["pending"] or original["partial"] or not set(original["posted"]) >= IDS:
        raise ValueError("historical confirmations missing")
    historic.MARKER = MARKER
    found = await asyncio.to_thread(historic.prior_comments)
    if any(found.values()):
        raise ValueError("correction journal exists; inspect manually")
    all_rows = await delivery.discover(fetcher, "nte")
    rows = [row for row in all_rows if row["id"] in IDS]
    if {row["id"] for row in rows} != IDS or len(rows) != len(IDS):
        raise ValueError("expected fixed snapshot not available")
    if any("account action notice" not in row["title"].lower() for row in rows if row["id"] in NOTICE_IDS):
        raise ValueError("notice identity changed")
    state = delivery.ingest("nte", route, None, rows)
    result = await asyncio.to_thread(historic.gh_api,
        f"repos/{historic.REPOSITORY}/issues/{historic.ISSUE}/comments", method="POST",
        body={"body": historic.encode("nte", state)})
    if historic.check_comment(result, "nte") != state:
        raise ValueError("journal creation unconfirmed")
    print(f"::notice title=NTE formatting corrections::prepared=1 articles={len(rows)} "
          f"comment={result['id']} sent=0 production-state=unchanged", flush=True)


async def send_batch(session, fetcher, settings, route):
    if not COMMENT_ID:
        raise ValueError("correction journal ID not locked")
    historic.MARKER = MARKER
    comment = await asyncio.to_thread(historic.gh_api,
        f"repos/{historic.REPOSITORY}/issues/comments/{COMMENT_ID}")
    journal = historic.CommentJournal("nte", comment, route)
    state = journal.state
    if set(state["posted"]) | {row["id"] for row in state["pending"]} != IDS:
        raise ValueError("unexpected correction queue")
    if state["partial"] and state["partial"]["inflight"]:
        raise ValueError("inflight page requires manual inspection")
    sent = 0
    while state["pending"] and sent < 12:
        row_id = state["pending"][0]["id"]

        async def render(row):
            return await delivery.render_candidate(fetcher, settings, "nte", row)

        async def send(payload, *, _id=row_id):
            nonlocal sent
            await asyncio.sleep(1.5)
            result = await delivery.send_candidate_once(session, settings, "nte", payload)
            if not result.ok or result.ambiguous or not result.message_id:
                print(f"::notice title=NTE correction send::id={_id} confirmed=0 inspect-before-resume=1", flush=True)
                return result
            sent += 1
            print(f"::notice title=NTE correction send::id={_id} confirmed=1 batch-pages={sent}", flush=True)
            return SimpleNamespace(ok=True, ambiguous=False,
                message_id=historic.anonymize(result.message_id, settings.env["DISCORD_WEBHOOK_NEWS_NTE"]))

        state = await delivery.deliver_oldest(state, "nte", route, as_of=int(time.time()),
            checkpoint=journal.checkpoint, render=render, send=send, max_pages=min(3, 12-sent))
        if state["partial"]:
            break
    print(f"::notice title=NTE formatting correction progress::confirmed={len(state['posted'])} "
          f"pending={len(state['pending'])} partial={int(bool(state['partial']))} batch-pages={sent} "
          "production-state=unchanged", flush=True)


async def main(mode):
    historic.guard()
    settings, routes = historic.settings_and_routes()
    async with aiohttp.ClientSession(trust_env=False) as session:
        fetcher = Fetcher(NoRedirectSession(session))
        if mode == "prepare":
            await prepare(fetcher, routes["nte"])
        else:
            await send_batch(session, fetcher, settings, routes["nte"])


if __name__ == "__main__":
    if sys.argv[1:] not in (["--prepare"], ["--send"]):
        raise SystemExit("Specify --prepare or --send explicitly.")
    try:
        asyncio.run(main(sys.argv[1][2:]))
    except Exception as exc:  # noqa: BLE001 — never expose private destination or response
        print(f"::notice title=NTE corrections held::error-type={type(exc).__name__}", flush=True)
        raise SystemExit("Held; inspect the independent journal and channel before any retry.") from None
