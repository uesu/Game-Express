"""Fixed expanded-news private webhook test, not a production source/monitor.

Prepares all articles and verifies their media before posting. It does not touch
monitor state, register sources, retry posts or print credentials/response bodies.
A partially successful or ambiguous run must be inspected before any rerun.
"""
from __future__ import annotations

import asyncio
import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import aiohttp  # noqa: E402
from feature3_webhook_test import image_hosts_safe, nte_body, send_once, valid_webhook  # noqa: E402
from live_candidate_probe import NoRedirectSession  # noqa: E402

from gamexpress.cards import news_payloads, validate_payload  # noqa: E402
from gamexpress.config import Game, load_settings  # noqa: E402
from gamexpress.http import Fetcher  # noqa: E402
from gamexpress.media import news_media_available  # noqa: E402
from gamexpress.models import Item  # noqa: E402
from gamexpress.sources import endfield, silverpalace  # noqa: E402
from gamexpress.sources.candidate_thumbnail import with_verified_fallback  # noqa: E402

NTE_URL = "https://nte.perfectworld.com/en/article/news/gamenews/20240830/252469.html"
MAX_POSTS = 20


def settings_for_test():
    settings = load_settings({"NEWS_EXPAND_FULL": os.environ.get("NEWS_EXPAND_FULL", "")})
    if not settings.news_expand_full:
        raise ValueError("expanded mode is required for this test")
    return settings


def body_images(item):
    return [b["url"] for b in item.article_blocks if b.get("kind") == "image"]


def rendered_images(payloads):
    return [entry["media"]["url"] for payload in payloads for card in payload["components"]
            for component in card.get("components", []) if component["type"] == 12
            for entry in component["items"]]


def preserves_body_images(item, payloads):
    expected = iter(body_images(item))
    wanted = next(expected, None)
    for url in rendered_images(payloads):
        if url == wanted:
            wanted = next(expected, None)
    return wanted is None


def excerpted(payloads):
    return any("**Excerpt" in c.get("content", "") for p in payloads for box in p["components"]
               for c in box.get("components", []) if c["type"] == 10)


async def prepare(fetcher, settings):
    if not settings.news_expand_full:
        raise ValueError("expanded mode disabled")
    nte_game = Game(key="nte", name="Neverness to Everness", short="NTE", enabled=False, color=14922399)
    html = await fetcher.get_text(NTE_URL, source="expanded-test-nte", retries=0)
    blocks = nte_body(html)
    if not blocks:
        raise ValueError("NTE body unavailable")
    nte = Item(source="nte", game="nte", id="252469", url=NTE_URL,
               title="Neverness To Everness Trailer | Wonders Await, In Urban Cityscape!",
               text="", published_ts=0, article_blocks=blocks, author="Neverness to Everness")
    if not image_hosts_safe(nte, "ntevmg.perfectworld.com"):
        raise ValueError("unexpected NTE image host")
    nte = await with_verified_fallback(fetcher, nte)
    if not nte.images:
        raise ValueError("YouTube thumbnail could not be preflighted")
    entries = [("nte-252469", nte_game, nte)]

    end_game = Game(key="endfield", name="Arknights: Endfield", short="Endfield", enabled=False, color=14922399)
    rows = await endfield.discover_news(fetcher, end_game, 0)
    for cid in ("1340", "3840"):
        row = next((row for row in rows or [] if row["id"] == cid), None)
        item = await endfield.news_article(fetcher, end_game, row) if row else None
        if not item or not image_hosts_safe(item, "web-static.hg-cdn.com"):
            raise ValueError("Endfield body or media unavailable")
        images = body_images(item)
        if cid == "3840" and len(images) != 50:
            raise ValueError("50-image example changed")
        if cid == "1340" and not all(any(url.lower().split("?", 1)[0].endswith("." + ext) for url in images)
                                     for ext in ("jpg", "png", "gif")):
            raise ValueError("mixed-media example changed")
        entries.append(("endfield-" + cid, end_game, item))

    silver_game = Game(key="silverpalace", name="Silver Palace", short="Silver Palace", enabled=False, color=14922399)
    rows = await silverpalace.snapshot(fetcher)
    for cid in ("1", "120"):
        row = next((row for row in rows or [] if row["id"] == cid), None)
        data = await silverpalace.detail(fetcher, row) if row else None
        if not data:
            raise ValueError("Silver Palace body unavailable")
        item = Item(source="silverpalace", game="silverpalace", id=cid, url=data["url"], title=data["title"],
                    text="", published_ts=0, images=[data["cover"]], article_blocks=data["blocks"], author="Silver Palace")
        if not image_hosts_safe(item, "s.elementagames.com"):
            raise ValueError("unexpected Silver Palace image host")
        entries.append(("silver-" + cid, silver_game, item))

    posts = []
    for label, game, item in entries:
        payloads = news_payloads(game, item, expand_full=settings.news_expand_full,
                                 max_pages=settings.news_expand_max_pages, max_chars=settings.news_expand_max_chars,
                                 max_media=settings.news_expand_max_media)
        if (not payloads or any(validate_payload(p) for p in payloads) or excerpted(payloads)
                or not preserves_body_images(item, payloads)):
            raise ValueError("card incomplete or invalid")
        if not await news_media_available(fetcher, payloads, max_urls=settings.news_expand_max_media):
            print(f"::notice title=Expanded test preflight::{label} status=failed", flush=True)
            raise ValueError("card media preflight failed")
        media = body_images(item)
        gif_count = sum(url.lower().split("?", 1)[0].endswith(".gif") for url in media)
        print(f"::notice title=Expanded test article::{label} pages={len(payloads)} "
              f"body-images={len(media)} gifs={gif_count} media={len(rendered_images(payloads))} "
              "excerpt=0 preflight=pass", flush=True)
        posts.extend((label, payload) for payload in payloads)
    if not 1 <= len(posts) <= MAX_POSTS:
        raise ValueError("expanded message count outside test bound")
    return posts


async def run(*, prepare_only=False):
    settings = settings_for_test()
    webhook = os.environ.get("FEATURE3_TEST_WEBHOOK", "") if not prepare_only else ""
    if not prepare_only and not valid_webhook(webhook):
        raise ValueError("dedicated webhook secret missing or invalid")
    async with aiohttp.ClientSession(trust_env=False) as session:
        fetcher = Fetcher(NoRedirectSession(session))
        posts = await prepare(fetcher, settings)
        print(f"::notice title=Expanded test preparation::expanded=1 prepared={len(posts)} no-state=1", flush=True)
        if prepare_only:
            return
        sent = 0
        for label, payload in posts:
            if sent:
                await asyncio.sleep(1.5)
            ok, status = await send_once(session, webhook, payload)
            if not ok:
                print(f"::notice title=Expanded test send::sent={sent} failed={label} http={status} "
                      "inspect-channel-before-rerun=1", flush=True)
                raise ValueError("send failed or ambiguous")
            sent += 1
        print(f"::notice title=Expanded test send::sent={sent} confirmed={sent} no-state=1", flush=True)


class Tests(unittest.TestCase):
    def test_body_image_order_and_excerpt_checks(self):
        item = Item(source="endfield", game="endfield", id="1", url="", title="", text="", published_ts=0,
                    article_blocks=[{"kind": "image", "url": "a"}, {"kind": "image", "url": "b"}])
        def payload(urls):
            return [{"components": [{"components": [{"type": 12, "items": [
                {"media": {"url": url}} for url in urls]}]}]}]
        self.assertTrue(preserves_body_images(item, payload(["cover", "a", "b"])))
        self.assertFalse(preserves_body_images(item, payload(["b", "a"])))
        self.assertFalse(preserves_body_images(item, payload(["cover", "a"])))
        self.assertTrue(excerpted([{"components": [{"components": [{"type": 10, "content": "**Excerpt"}]}]}]))

    def test_settings_require_expanded_mode_and_no_implicit_post(self):
        from unittest.mock import patch
        with patch.dict(os.environ, {"NEWS_EXPAND_FULL": "1"}):
            self.assertTrue(settings_for_test().news_expand_full)
        with patch.dict(os.environ, {"NEWS_EXPAND_FULL": "0"}), self.assertRaises(ValueError):
            settings_for_test()
        workflow = (ROOT / ".github/workflows/source_research_probe.yml").read_text(encoding="utf-8")
        self.assertIn("if: ${{ inputs.scope == 'feature3-expanded-prepare' }}", workflow)
        self.assertIn("if: ${{ inputs.scope == 'feature3-expanded-post' }}", workflow)


if __name__ == "__main__":
    if sys.argv[1:] == ["--self-test"]:
        unittest.main(argv=[sys.argv[0]])
    elif sys.argv[1:] not in ([], ["--prepare-only"]):
        raise SystemExit("Usage: feature3_expanded_test.py [--self-test|--prepare-only]")
    else:
        try:
            asyncio.run(run(prepare_only=sys.argv[1:] == ["--prepare-only"]))
        except (ValueError, TypeError, KeyError, AttributeError, RecursionError):
            raise SystemExit("Expanded test stopped; inspect the channel before any rerun.") from None
