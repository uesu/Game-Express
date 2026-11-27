"""Offline tests for the inactive candidates' optional YouTube cover fallback."""
from __future__ import annotations

import asyncio
import sys
import unittest
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from gamexpress.cards import news_payloads, validate_payload  # noqa: E402
from gamexpress.config import Game  # noqa: E402
from gamexpress.models import Item  # noqa: E402
from gamexpress.sources.candidate_thumbnail import fallback_url, with_verified_fallback  # noqa: E402


class Fetcher:
    def __init__(self, ok=True):
        self.ok, self.calls = ok, []

    async def verify_media(self, url):
        self.calls.append(url)
        return self.ok


def item(source="nte"):
    return Item(source=source, game=source, id="1", url="https://example.org/article/1", title="Trailer",
                text="", published_ts=0, article_blocks=[{"kind": "text", "text": "Before"},
                    {"kind": "link", "url": "https://www.youtube.com/embed/tdZN6H1N3PU"},
                    {"kind": "text", "text": "After"}])


class CandidateThumbnailTests(unittest.TestCase):
    def test_youtube_fallback_is_verified_and_link_stays_inline(self):
        original = item()
        before = deepcopy(original)
        fetcher = Fetcher()
        result = asyncio.run(with_verified_fallback(fetcher, original))
        url = "https://i.ytimg.com/vi/tdZN6H1N3PU/hqdefault.jpg"
        self.assertEqual(fetcher.calls, [url])
        self.assertEqual(result.images, [url])
        self.assertEqual(original, before)
        game = Game(key="nte", name="NTE", short="NTE", enabled=False, color=0)
        payload = news_payloads(game, result)[0]
        self.assertEqual(validate_payload(payload), [])
        children = payload["components"][0]["components"]
        texts = [c.get("content", "") for c in children if c["type"] == 10]
        self.assertIn("https://www.youtube.com/watch?v=tdZN6H1N3PU", texts)
        self.assertTrue(any(c["type"] == 12 and c["items"][0]["media"]["url"] == url for c in children))

    def test_existing_media_legacy_sources_and_bad_links_never_guess(self):
        variants = []
        for source in ("hoyolab", "kuro", "nte"):
            a = item(source)
            if source == "nte":
                a.images = ["https://example.org/existing.jpg"]
            variants.append(a)
        for kind in ("image", "video"):
            a = item()
            a.article_blocks.append({"kind": kind, "url": "https://example.org/source"})
            variants.append(a)
        a = item()
        a.article_blocks[1]["url"] = "https://youtube.com.evil.example/embed/tdZN6H1N3PU"
        variants.append(a)
        a = item()
        a.game = "wuwa"
        variants.append(a)
        for a in variants:
            with self.subTest(source=a.source):
                f = Fetcher()
                self.assertIsNone(fallback_url(a))
                self.assertIs(asyncio.run(with_verified_fallback(f, a)), a)
                self.assertEqual(f.calls, [])
        failed = item()
        f = Fetcher(False)
        self.assertIs(asyncio.run(with_verified_fallback(f, failed)), failed)
        self.assertEqual(failed.images, [])
        self.assertEqual(len(f.calls), 1)


if __name__ == "__main__":
    unittest.main()
