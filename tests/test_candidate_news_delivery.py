"""Offline state and routing tests; no real webhook, persistence or source access."""
from __future__ import annotations

import asyncio
import copy
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from gamexpress import candidate_news_delivery as delivery  # noqa: E402
from gamexpress.cards import news_payloads  # noqa: E402
from gamexpress.config import Game, load_settings  # noqa: E402
from gamexpress.models import Item  # noqa: E402

ROUTE = "a" * 16
NOW = 1795824000
HOOK = "https://discord.com/api/webhooks/123456789012345678/example_token_123456789"


def row(cid, date="2026-11-27"):
    return {"id": cid, "title": "Official " + cid, "date": date}


def payload(cid):
    game = Game(key="silverpalace", name="Silver Palace", short="Silver", enabled=False, color=0)
    item = Item(source="silverpalace", game="silverpalace", id=cid, title="Official " + cid,
                url="https://silverpalace.elementagames.com/en-us/newsDetail?id=" + cid,
                text="", published_ts=0, article_blocks=[{"kind": "text", "text": "Hello"}])
    return news_payloads(game, item)[0]


class Storage:
    def __init__(self, fail_at=0):
        self.states, self.calls, self.fail_at = [], 0, fail_at

    async def checkpoint(self, state):
        self.calls += 1
        if self.calls == self.fail_at:
            return False
        self.states.append(copy.deepcopy(state))
        return True


class CandidateDeliveryTests(unittest.TestCase):
    def test_scoped_renderer_calls_correct_reader_preflight_and_fallback(self):
        game = delivery.candidate_game("silverpalace")
        article = Item(source="silverpalace", game="silverpalace", id="1", title="Official 1",
                       url="https://silverpalace.elementagames.com/en-us/newsDetail?id=1", text="", published_ts=0,
                       article_blocks=[{"kind": "text", "text": "Watch https://youtu.be/ELC4r7fbKEQ"}])

        class Fetcher:
            async def media_dimensions(self, url):
                return (1280, 720)

            async def verify_media(self, url):
                return url == "https://i.ytimg.com/vi/ELC4r7fbKEQ/maxresdefault.jpg"

        async def read(fetcher, gm, candidate):
            self.assertEqual(gm, game)
            self.assertEqual(candidate, row("1"))
            return article

        with patch.object(delivery.silverpalace, "news_article", read):
            pages = asyncio.run(delivery.render_candidate(Fetcher(), load_settings({}), "silverpalace", row("1")))
        children = pages[0]["components"][0]["components"]
        self.assertTrue(any(c.get("type") == 12 and c["items"][0]["media"]["url"].endswith("/maxresdefault.jpg")
                            for c in children))
        self.assertTrue(any("https://youtu.be/ELC4r7fbKEQ" in c.get("content", "") for c in children))
        self.assertEqual(article.images, [])

    def test_dedicated_routing_only_and_no_secret_in_fingerprint(self):
        settings = load_settings({"DISCORD_WEBHOOK_NEWS_SILVERPALACE": HOOK,
                                  "DISCORD_WEBHOOK_URL": "https://wrong.example/secret"})
        result = delivery.destination(settings, "silverpalace")
        self.assertEqual(result[0], HOOK)
        self.assertEqual(len(result[1]), 16)
        self.assertNotIn("example_token", result[1])
        self.assertIsNone(delivery.destination(settings, "nte"))
        self.assertIsNone(delivery.destination(settings, "hoyolab"))
        for value in ("https://evil.example/api/webhooks/123/example_token_123456789",
                      HOOK + "?thread_id=1&other=secret", HOOK + "#fragment", HOOK.replace("https:", "http:")):
            self.assertIsNone(delivery.destination(load_settings({"DISCORD_WEBHOOK_NEWS_NTE": value}), "nte"))
        a = delivery.destination(load_settings({"DISCORD_WEBHOOK_NEWS_NTE": HOOK}), "nte")
        b = delivery.destination(load_settings({"DISCORD_WEBHOOK_NEWS_NTE": HOOK + "?thread_id=123"}), "nte")
        self.assertNotEqual(a[1], b[1])

    def test_initial_backfill_and_new_articles_sort_without_pruning(self):
        state = delivery.ingest("silverpalace", ROUTE, None,
                                [row("8", "2026-03-01"), row("3", "2025-01-01"), row("1", "2026-03-01")])
        self.assertEqual([r["id"] for r in state["pending"]], ["3", "1", "8"])
        state = delivery.ingest("silverpalace", ROUTE, state, [row("4", "2024-01-01"), row("8")])
        self.assertEqual([r["id"] for r in state["pending"]], ["4", "3", "1", "8"])
        with self.assertRaises(delivery.DeliveryHold):
            delivery.ingest("silverpalace", "b" * 16, state, [])
        with self.assertRaises(delivery.DeliveryHold):
            delivery.ingest("silverpalace", ROUTE, state, None)
        with self.assertRaises(delivery.DeliveryHold):
            delivery.ingest("silverpalace", ROUTE, None, [row("1"), row("1")])
        end = delivery.ingest("endfield", ROUTE, None, [{"id": "2", "title": "two", "ts": 20},
                                                        {"id": "1", "title": "one", "ts": 10}])
        self.assertEqual([r["id"] for r in end["pending"]], ["1", "2"])

    def test_future_article_is_held_before_persist_or_send(self):
        state = delivery.ingest("silverpalace", ROUTE, None, [row("1", "2099-01-01")])
        store = Storage()
        calls = []
        async def render(article):
            calls.append(article)
            return [payload(article["id"])]
        async def send(page):
            calls.append(page)
        with self.assertRaises(delivery.DeliveryHold):
            asyncio.run(delivery.deliver_oldest(state, "silverpalace", ROUTE, as_of=NOW,
                                                checkpoint=store.checkpoint, render=render, send=send))
        self.assertEqual(store.calls, 0)
        self.assertEqual(calls, [])
        with self.assertRaises(delivery.DeliveryHold):
            delivery.ingest("silverpalace", ROUTE, None, [])

    def test_each_page_has_persisted_intent_and_confirmed_id_before_next(self):
        state = delivery.ingest("silverpalace", ROUTE, None, [row("1"), row("2")])
        store = Storage()
        sent = []
        pages = [payload("1"), payload("1")]
        pages[1] = copy.deepcopy(pages[1])
        pages[1]["components"][0]["components"][0]["content"] += " continued"

        async def render(article):
            self.assertEqual(article["id"], "1")
            return pages

        async def send(page):
            persisted = store.states[-1]
            self.assertTrue(persisted["partial"]["inflight"])
            self.assertEqual(len(persisted["partial"]["messages"]), len(sent))
            sent.append(page)
            return SimpleNamespace(ok=True, message_id=str(len(sent) + 100), ambiguous=False)

        result = asyncio.run(delivery.deliver_oldest(state, "silverpalace", ROUTE, as_of=NOW, checkpoint=store.checkpoint,
                                                     render=render, send=send))
        self.assertEqual(sent, pages)
        self.assertEqual(result["posted"]["1"]["messages"], ["101", "102"])
        self.assertEqual(result["pending"], [row("2")])
        self.assertIsNone(result["partial"])
        self.assertEqual(store.states[-1], result)
        self.assertEqual(state["posted"], {})
        self.assertNotIn("webhook", str(result).lower())
        after = delivery.ingest("silverpalace", ROUTE, result, [row("1"), row("2")])
        self.assertEqual(after["pending"], [row("2")])

    def test_ambiguous_result_or_failed_checkpoint_never_reposts(self):
        initial = delivery.ingest("silverpalace", ROUTE, None, [row("1")])

        async def render(article):
            return [payload(article["id"])]

        calls = []

        async def ambiguous(page):
            calls.append(page)
            return SimpleNamespace(ok=True, message_id=None, ambiguous=True)

        store = Storage()
        with self.assertRaises(delivery.DeliveryHold):
            asyncio.run(delivery.deliver_oldest(initial, "silverpalace", ROUTE, as_of=NOW, checkpoint=store.checkpoint,
                                                render=render, send=ambiguous))
        self.assertEqual(len(calls), 1)
        saved = store.states[-1]
        self.assertTrue(saved["partial"]["inflight"])
        with self.assertRaises(delivery.DeliveryHold):
            asyncio.run(delivery.deliver_oldest(saved, "silverpalace", ROUTE, as_of=NOW, checkpoint=store.checkpoint,
                                                render=render, send=ambiguous))
        self.assertEqual(len(calls), 1)
        store = Storage(fail_at=3)  # intent checkpoint fails, before sending
        with self.assertRaises(delivery.DeliveryHold):
            asyncio.run(delivery.deliver_oldest(initial, "silverpalace", ROUTE, as_of=NOW, checkpoint=store.checkpoint,
                                                render=render, send=ambiguous))
        self.assertEqual(len(calls), 1)

    def test_partial_resume_holds_changed_content_and_finishes_original(self):
        state = delivery.ingest("silverpalace", ROUTE, None, [row("1")])
        store = Storage(fail_at=5)  # confirmed page 1 persisted; page 2 intent fails
        pages = [payload("1"), payload("1")]

        async def render(article):
            return pages

        count = []
        async def send(page):
            count.append(page)
            return SimpleNamespace(ok=True, message_id=str(100 + len(count)), ambiguous=False)

        with self.assertRaises(delivery.DeliveryHold):
            asyncio.run(delivery.deliver_oldest(state, "silverpalace", ROUTE, as_of=NOW, checkpoint=store.checkpoint,
                                                render=render, send=send))
        saved = store.states[-1]
        self.assertEqual(saved["partial"]["messages"], ["101"])
        self.assertFalse(saved["partial"]["inflight"])
        async def changed(article):
            return [payload("2")]
        with self.assertRaises(delivery.DeliveryHold):
            asyncio.run(delivery.deliver_oldest(saved, "silverpalace", ROUTE, as_of=NOW, checkpoint=Storage().checkpoint,
                                                render=changed, send=send))
        clean = Storage()
        result = asyncio.run(delivery.deliver_oldest(saved, "silverpalace", ROUTE, as_of=NOW, checkpoint=clean.checkpoint,
                                                     render=render, send=send))
        self.assertEqual(result["posted"]["1"]["messages"], ["101", "102"])


if __name__ == "__main__":
    unittest.main()
