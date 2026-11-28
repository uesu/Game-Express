"""Private rechecks of Silver Palace articles 93 and 99, with an independent journal."""
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

MARKER = "feature3-silver-animation-rechecks-v1"
IDS = {"93", "99"}
COMMENT_ID = 7235875858  # independently verified; preparation permanently locked


async def prepare(fetcher, route):
    if COMMENT_ID:
        raise ValueError("preparation locked")
    comment = await asyncio.to_thread(historic.gh_api,
        f"repos/{historic.REPOSITORY}/issues/comments/{historic.COMMENT_IDS['silverpalace']}")
    state = delivery._validate(historic.check_comment(comment, "silverpalace", historic.COMMENT_IDS["silverpalace"]),
                               "silverpalace", route)
    if state["pending"] or state["partial"] or not set(state["posted"]) >= IDS:
        raise ValueError("originals not confirmed")
    historic.MARKER = MARKER
    if any((await asyncio.to_thread(historic.prior_comments)).values()):
        raise ValueError("journal already exists; inspect manually")
    rows = [row for row in await delivery.discover(fetcher, "silverpalace") if row["id"] in IDS]
    if len(rows) != 2 or {row["id"] for row in rows} != IDS:
        raise ValueError("fixed original articles missing")
    state = delivery.ingest("silverpalace", route, None, rows)
    comment = await asyncio.to_thread(historic.gh_api, f"repos/{historic.REPOSITORY}/issues/{historic.ISSUE}/comments",
                                      method="POST", body={"body": historic.encode("silverpalace", state)})
    if historic.check_comment(comment, "silverpalace") != state:
        raise ValueError("journal creation unconfirmed")
    print(f"::notice title=Silver animation rechecks::prepared=1 articles=2 comment={comment['id']} sent=0", flush=True)


async def send(session, fetcher, settings, route):
    if not COMMENT_ID:
        raise ValueError("journal ID not locked")
    historic.MARKER = MARKER
    comment = await asyncio.to_thread(historic.gh_api, f"repos/{historic.REPOSITORY}/issues/comments/{COMMENT_ID}")
    journal = historic.CommentJournal("silverpalace", comment, route)
    state = journal.state
    if set(state["posted"]) | {row["id"] for row in state["pending"]} != IDS:
        raise ValueError("unexpected queue")
    if state["partial"] and state["partial"]["inflight"]:
        raise ValueError("inflight page requires inspection")
    sent = 0
    while state["pending"] and sent < 12:
        async def render(row):
            return await delivery.render_candidate(fetcher, settings, "silverpalace", row)

        async def send_one(payload):
            nonlocal sent
            await asyncio.sleep(1.5)
            result = await delivery.send_candidate_once(session, settings, "silverpalace", payload)
            if not result.ok or result.ambiguous or not result.message_id:
                return result
            sent += 1
            return SimpleNamespace(ok=True, ambiguous=False, message_id=historic.anonymize(
                result.message_id, settings.env["DISCORD_WEBHOOK_NEWS_SILVERPALACE"]))

        state = await delivery.deliver_oldest(state, "silverpalace", route, as_of=int(time.time()),
            checkpoint=journal.checkpoint, render=render, send=send_one, max_pages=min(3, 12-sent))
        if state["partial"]:
            break
    print(f"::notice title=Silver animation rechecks::confirmed={len(state['posted'])} pending={len(state['pending'])} "
          f"partial={int(bool(state['partial']))} batch-pages={sent} production-state=unchanged", flush=True)


async def main(mode):
    historic.guard()
    settings, routes = historic.settings_and_routes()
    async with aiohttp.ClientSession(trust_env=False) as session:
        fetcher = Fetcher(NoRedirectSession(session))
        if mode == "prepare":
            await prepare(fetcher, routes["silverpalace"])
        else:
            await send(session, fetcher, settings, routes["silverpalace"])


if __name__ == "__main__":
    if sys.argv[1:] not in (["--prepare"], ["--send"]):
        raise SystemExit("Specify --prepare or --send explicitly.")
    try:
        asyncio.run(main(sys.argv[1][2:]))
    except Exception as exc:  # noqa: BLE001 — never expose destination or response
        print(f"::notice title=Silver rechecks held::error-type={type(exc).__name__}", flush=True)
        raise SystemExit("Held; inspect independent journal and channel before any retry.") from None
