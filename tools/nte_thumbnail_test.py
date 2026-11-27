"""One explicitly requested private NTE trailer post; no production state.

Only the fixed official article and its verified max-resolution YouTube image
are accepted. A POST is made exactly once; ambiguity is never automatically retried.
"""
from __future__ import annotations

import asyncio
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import aiohttp  # noqa: E402
from feature3_webhook_test import image_hosts_safe, nte_body, send_once, valid_webhook  # noqa: E402
from live_candidate_probe import NoRedirectSession  # noqa: E402

from gamexpress.cards import news_payloads, validate_payload  # noqa: E402
from gamexpress.config import Game  # noqa: E402
from gamexpress.http import Fetcher  # noqa: E402
from gamexpress.media import news_media_available  # noqa: E402
from gamexpress.models import Item  # noqa: E402
from gamexpress.sources.candidate_thumbnail import with_verified_fallback  # noqa: E402

URL = "https://nte.perfectworld.com/en/article/news/gamenews/20240830/252469.html"
THUMB = "https://i.ytimg.com/vi/tdZN6H1N3PU/maxresdefault.jpg"
WATCH = "https://www.youtube.com/watch?v=tdZN6H1N3PU"
TITLE = "Neverness To Everness Trailer | Wonders Await, In Urban Cityscape!"


async def prepare(fetcher):
    html = await fetcher.get_text(URL, source="nte-thumbnail-private-test", retries=0)
    blocks = nte_body(html)
    if not blocks:
        raise ValueError("article body unavailable")
    game = Game(key="nte", name="Neverness to Everness", short="NTE", enabled=False, color=14922399)
    item = Item(source="nte", game="nte", id="252469", url=URL, title=TITLE, text="", published_ts=0,
                article_blocks=blocks, author="Neverness to Everness")
    if not image_hosts_safe(item, "ntevmg.perfectworld.com"):
        raise ValueError("unexpected native image host")
    item = await with_verified_fallback(fetcher, item)
    # The user specifically requested max resolution for this fixed example.
    if item.images != [THUMB]:
        raise ValueError("maximum-resolution thumbnail not verified; no post")
    payloads = news_payloads(game, item, expand_full=True)
    if len(payloads) != 1 or validate_payload(payloads[0]):
        raise ValueError("unexpected card layout")
    children = payloads[0]["components"][0]["components"]
    if not any(c.get("content") == WATCH for c in children if c.get("type") == 10):
        raise ValueError("expected inline video link missing")
    if not await news_media_available(fetcher, payloads, max_urls=1):
        raise ValueError("media preflight failed")
    return payloads[0]


async def run(*, prepare_only=False):
    webhook = os.environ.get("FEATURE3_TEST_WEBHOOK", "") if not prepare_only else ""
    if not prepare_only and not valid_webhook(webhook):
        raise ValueError("dedicated webhook missing or invalid")
    async with aiohttp.ClientSession(trust_env=False) as session:
        payload = await prepare(Fetcher(NoRedirectSession(session)))
        if prepare_only:
            print("::notice title=NTE thumbnail test::prepared=1 maxres=verified sent=0 state=unchanged", flush=True)
            return
        ok, status = await send_once(session, webhook, payload)
        if not ok:
            print(f"::notice title=NTE thumbnail test::http={status} confirmed=0 inspect-channel-before-rerun=1",
                  flush=True)
            raise ValueError("send failed or ambiguous")
        print(f"::notice title=NTE thumbnail test::http={status} confirmed=1 maxres=verified sent=1 state=unchanged",
              flush=True)


class Tests(unittest.TestCase):
    def test_preparation_is_one_valid_maxres_card_with_inline_watch(self):
        class Fake:
            async def get_text(self, url, **kwargs):
                self.url = url
                return "fixed"

            async def media_dimensions(self, url):
                return (1280, 720) if url == THUMB else None

            async def verify_media(self, url):
                return url == THUMB

        fake = Fake()
        blocks = [{"kind": "text", "text": "Welcome"},
                  {"kind": "link", "url": "https://www.youtube.com/embed/tdZN6H1N3PU"}]
        with patch(__name__ + ".nte_body", return_value=blocks):
            payload = asyncio.run(prepare(fake))
        self.assertEqual(fake.url, URL)
        self.assertFalse(validate_payload(payload))
        components = payload["components"][0]["components"]
        self.assertIn(WATCH, [c.get("content") for c in components])
        self.assertTrue(any(c.get("type") == 12 and c["items"][0]["media"]["url"] == THUMB for c in components))

    def test_no_other_job_can_send_this_card_by_default(self):
        workflow = (ROOT / ".github/workflows/source_research_probe.yml").read_text(encoding="utf-8")
        self.assertIn("if: ${{ inputs.scope == 'nte-thumbnail-post' }}", workflow)
        self.assertEqual(workflow.count("python tools/nte_thumbnail_test.py\n"), 1)
        self.assertIn("--prepare-only", workflow)


if __name__ == "__main__":
    if sys.argv[1:] == ["--self-test"]:
        unittest.main(argv=[sys.argv[0]])
    elif sys.argv[1:] not in ([], ["--prepare-only"]):
        raise SystemExit("Usage: nte_thumbnail_test.py [--self-test|--prepare-only]")
    else:
        try:
            asyncio.run(run(prepare_only=sys.argv[1:] == ["--prepare-only"]))
        except (ValueError, TypeError, KeyError, AttributeError, RecursionError):
            raise SystemExit("NTE test stopped; inspect the channel before any rerun.") from None
