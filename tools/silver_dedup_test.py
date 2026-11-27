"""One guarded private correction of Silver Palace article 7; never touches monitor state."""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import aiohttp  # noqa: E402
from live_candidate_probe import NoRedirectSession  # noqa: E402

from gamexpress import candidate_news_delivery as delivery  # noqa: E402
from gamexpress.config import load_settings  # noqa: E402
from gamexpress.http import Fetcher  # noqa: E402

BODY = "https://s.elementagames.com/official/image/20251218/e4a8b3d37c628be4e73294c8469e73d6.jpg"
# Run 46036854435 confirmed the one corrected card. Do not send it again.
PRIVATE_TEST_COMPLETED = True


async def prepare(fetcher):
    rows = await delivery.discover(fetcher, "silverpalace")
    row = next((row for row in rows or [] if row["id"] == "7"), None)
    if not row or row["title"] != "[Monotype] Beta Test Recruitment has officially started!":
        raise ValueError("fixed article not found")
    pages = await delivery.render_candidate(fetcher, load_settings({}), "silverpalace", row)
    if len(pages) != 1:
        raise ValueError("fixed article layout changed")
    children = [child for page in pages for box in page["components"] for child in box.get("components", [])]
    urls = [entry["media"]["url"] for child in children if child.get("type") == 12 for entry in child["items"]]
    text = "\n".join(child.get("content", "") for child in children if child.get("type") == 10)
    if urls != [BODY] or "How to Participate" not in text or "Recruitment Overview" not in text:
        raise ValueError("single body image or complete text not confirmed")
    return pages[0]


async def run():
    if PRIVATE_TEST_COMPLETED or os.environ.get("GITHUB_RUN_ATTEMPT") != "1":
        raise ValueError("this private test is locked or a rerun")
    webhook = os.environ.get("FEATURE3_TEST_WEBHOOK", "")
    settings = load_settings({"DISCORD_WEBHOOK_NEWS_SILVERPALACE": webhook})
    if delivery.destination(settings, "silverpalace") is None:
        raise ValueError("invalid private destination")
    async with aiohttp.ClientSession(trust_env=False) as session:
        payload = await prepare(Fetcher(NoRedirectSession(session)))
        print("::notice title=Silver duplicate fix::prepared=1 article=7 images=1 preflight=pass", flush=True)
        result = await delivery.send_candidate_once(session, settings, "silverpalace", payload)
        if not result.ok:
            print(f"::notice title=Silver duplicate fix::http={result.status} confirmed=0 "
                  "inspect-channel-before-rerun=1", flush=True)
            raise ValueError("send outcome not confirmed")
        print("::notice title=Silver duplicate fix::confirmed=1 sent=1 images=1 production-state=unchanged", flush=True)


if __name__ == "__main__":
    if sys.argv[1:]:
        raise SystemExit("This test has no arguments.")
    try:
        asyncio.run(run())
    except Exception:  # noqa: BLE001 — do not expose webhook or response content
        raise SystemExit("Private correction held; inspect the private channel before any new send.") from None
