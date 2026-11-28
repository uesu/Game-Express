"""User-authorized private repost of exactly NTE 252478, with a separate durable journal."""
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

MARKER = "feature3-nte-252478-correction-v1"
ROW = {"id": "252478", "title": "Character Introduction - Taygedo", "date": "2024-08-30",
       "url": "https://nte.perfectworld.com/en/article/news/gamenews/20240830/252478.html"}


def get_or_create(route):
    # Verify the original private historic journal already confirms this article.
    comment = historic.gh_api(f"repos/{historic.REPOSITORY}/issues/comments/{historic.COMMENT_IDS['nte']}")
    original = historic.check_comment(comment, "nte", historic.COMMENT_IDS["nte"])
    delivery._validate(original, "nte", route)
    if ROW["id"] not in original["posted"] or original["partial"]:
        raise ValueError("original historic record not confirmed")
    historic.MARKER = MARKER
    found = historic.prior_comments()
    if len(found["nte"]) > 1 or found["endfield"] or found["silverpalace"]:
        raise ValueError("unexpected correction journals")
    if found["nte"]:
        comment = found["nte"][0]
    else:
        state = delivery.ingest("nte", route, None, [ROW])
        comment = historic.gh_api(f"repos/{historic.REPOSITORY}/issues/{historic.ISSUE}/comments", method="POST",
                                  body={"body": historic.encode("nte", state)})
    return historic.CommentJournal("nte", comment, route)


async def run():
    historic.guard()
    settings, routes = historic.settings_and_routes()
    journal = await asyncio.to_thread(get_or_create, routes["nte"])
    if not journal.state["pending"]:
        if set(journal.state["posted"]) != {ROW["id"]} or journal.state["partial"]:
            raise ValueError("unexpected correction state")
        print("::notice title=NTE correction::already-confirmed=1 no-send=1", flush=True)
        return
    if journal.state["pending"] != [ROW] or journal.state["posted"]:
        raise ValueError("unexpected correction queue")
    async with aiohttp.ClientSession(trust_env=False) as session:
        fetcher = Fetcher(NoRedirectSession(session))

        async def render(row):
            pages = await delivery.render_candidate(fetcher, settings, "nte", row)
            texts = "\n".join(c.get("content", "") for p in pages for box in p["components"]
                              for c in box.get("components", []) if c.get("type") == 10)
            if len(pages) != 1 or texts.count(r"Taygedo\~\~taygedo!") != 2 or "Taygedo~~taygedo!" in texts:
                raise ValueError("corrected article format not confirmed")
            return pages

        async def send(payload):
            result = await delivery.send_candidate_once(session, settings, "nte", payload)
            if not result.ok or result.ambiguous or not result.message_id:
                return result
            return SimpleNamespace(ok=True, ambiguous=False,
                                   message_id=historic.anonymize(result.message_id, settings.env["DISCORD_WEBHOOK_NEWS_NTE"]))

        result = await delivery.deliver_oldest(journal.state, "nte", routes["nte"], as_of=int(time.time()),
                                               checkpoint=journal.checkpoint, render=render, send=send, max_pages=1)
        if result["pending"] or ROW["id"] not in result["posted"]:
            raise ValueError("correction not fully confirmed")
        print("::notice title=NTE correction::confirmed=1 pages=1 production-state=unchanged", flush=True)


if __name__ == "__main__":
    try:
        asyncio.run(run())
    except Exception:  # noqa: BLE001 — do not expose private webhook or remote response
        raise SystemExit("Correction held; inspect its journal and channel before any retry.") from None
