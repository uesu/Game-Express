"""Privately test complete Silver articles with generic GIF attachment planning.

Separate durable journal, bounded batch and no retry on uncertain sends.
Not a production runner and never modifies historical or production state.
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
from gamexpress import news_animation  # noqa: E402
from gamexpress.http import Fetcher  # noqa: E402

MARKER = "feature3-silver-full-animated-v1"
COMMENT_ID = 0  # prepare first, independently verify, lock before sending
IDS = {"93", "99"}


async def prepare(fetcher, route):
    if COMMENT_ID:
        raise ValueError("preparation locked")
    old = await asyncio.to_thread(historic.gh_api,
        f"repos/{historic.REPOSITORY}/issues/comments/{historic.COMMENT_IDS['silverpalace']}")
    old_state = delivery._validate(historic.check_comment(old, "silverpalace", historic.COMMENT_IDS["silverpalace"]),
                                   "silverpalace", route)
    if old_state["pending"] or old_state["partial"] or not set(old_state["posted"]) >= IDS:
        raise ValueError("historic test is not complete")
    historic.MARKER = MARKER
    if any((await asyncio.to_thread(historic.prior_comments)).values()):
        raise ValueError("journal already exists; inspect before any action")
    rows = [row for row in await delivery.discover(fetcher, "silverpalace") if row["id"] in IDS]
    if len(rows) != 2 or {row["id"] for row in rows} != IDS:
        raise ValueError("expected articles missing")
    state = delivery.ingest("silverpalace", route, None, rows)
    comment = await asyncio.to_thread(historic.gh_api, f"repos/{historic.REPOSITORY}/issues/{historic.ISSUE}/comments",
                                      method="POST", body={"body": historic.encode("silverpalace", state)})
    if historic.check_comment(comment, "silverpalace") != state:
        raise ValueError("journal creation unconfirmed")
    print(f"::notice title=Full Silver animation test::prepared=1 articles=2 comment={comment['id']} sent=0", flush=True)


async def send(session, fetcher, settings, route):
    if not COMMENT_ID:
        raise ValueError("journal not locked")
    historic.MARKER = MARKER
    comment = await asyncio.to_thread(historic.gh_api, f"repos/{historic.REPOSITORY}/issues/comments/{COMMENT_ID}")
    journal = historic.CommentJournal("silverpalace", comment, route)
    state = journal.state
    if set(state["posted"]) | {row["id"] for row in state["pending"]} != IDS:
        raise ValueError("unexpected queue")
    if state["partial"] and state["partial"]["inflight"]:
        raise ValueError("inflight page requires inspection")
    if not state["pending"]:
        print("::notice title=Full Silver animation test::already-confirmed=2 no-send=1", flush=True)
        return
    assets = {}
    article_id = state["pending"][0]["id"]

    async def render(row):
        pages = await delivery.render_candidate(fetcher, settings, "silverpalace", row)
        planned, data = await news_animation.prepare(fetcher, pages, max_pages=120)
        assets.update(data)
        print(f"::notice title=Full Silver animation render::id={row['id']} pages={len(planned)} "
              f"animated-files={len(data)} bytes={sum(map(len, data.values()))}", flush=True)
        return planned

    async def send_one(payload):
        await asyncio.sleep(1.5)
        attachments = payload.get("attachments") or []
        files = {a["filename"]: assets[a["filename"]] for a in attachments} if attachments else None
        result = await delivery.send_candidate_once(session, settings, "silverpalace", payload, files=files)
        if not result.ok or result.ambiguous or not result.message_id:
            print(f"::notice title=Full Silver animation send::id={article_id} confirmed=0 inspect-before-resume=1", flush=True)
            return result
        print(f"::notice title=Full Silver animation send::id={article_id} confirmed=1 "
              f"animated-files={len(attachments)}", flush=True)
        return SimpleNamespace(ok=True, ambiguous=False, message_id=historic.anonymize(
            result.message_id, settings.env["DISCORD_WEBHOOK_NEWS_SILVERPALACE"]))

    state = await delivery.deliver_oldest(state, "silverpalace", route, as_of=int(time.time()),
        checkpoint=journal.checkpoint, render=render, send=send_one, max_pages=120)
    print(f"::notice title=Full Silver animation test::confirmed={len(state['posted'])} pending={len(state['pending'])} "
          f"partial={int(bool(state['partial']))} production-state=unchanged", flush=True)


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
    except Exception as exc:  # noqa: BLE001 — never expose secrets or remote response
        print(f"::notice title=Full Silver animation test held::error-type={type(exc).__name__}", flush=True)
        raise SystemExit("Held; inspect journal and channel before any further send.") from None
