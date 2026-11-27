"""Private test harness tests: only local Git and mocked Discord, never network."""
from __future__ import annotations

import asyncio
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT))

import candidate_private_pipeline_test as private  # noqa: E402

from gamexpress.cards import news_payloads  # noqa: E402
from gamexpress.config import Game, load_settings  # noqa: E402
from gamexpress.models import Item  # noqa: E402

HOOK = "https://discord.com/api/webhooks/123456789012345678/example_token_123456789"


def card():
    game = Game(key="silverpalace", name="Silver Palace", short="Silver", enabled=False, color=0)
    item = Item(source="silverpalace", game="silverpalace", id="2", title="Private fixture",
                url="https://silverpalace.elementagames.com/en-us/newsDetail?id=2", text="", published_ts=0,
                article_blocks=[{"kind": "text", "text": "Hello"}])
    return news_payloads(game, item)[0]


class PrivateHarnessTests(unittest.TestCase):
    def test_real_local_git_checkpoint_and_restart_with_mock_discord(self):
        nte = {"id": "252475", "title": "Test", "date": "2024-08-30",
               "url": "https://nte.perfectworld.com/en/article/news/gamenews/20240830/252475.html"}
        end = {"id": "100", "title": "Test", "ts": 1700000000}
        silver = {"id": "2", "title": "Test", "date": "2025-01-01"}
        prepared = [("nte", nte, [card()]), ("endfield", end, [card(), card()]),
                    ("silverpalace", silver, [card()])]
        calls = []

        async def send(session, settings, source, payload):
            calls.append(source)
            return SimpleNamespace(ok=True, ambiguous=False, message_id=str(100 + len(calls)))

        async def sleep(seconds):
            self.assertEqual(seconds, 1.5)

        with patch.object(private.delivery, "send_candidate_once", send), patch.object(private.asyncio, "sleep", sleep):
            sent = asyncio.run(private.send_prepared(None, prepared, HOOK))
        self.assertEqual(sent, 4)
        self.assertEqual(calls, ["nte", "endfield", "endfield", "silverpalace"])

    def test_invalid_webhook_stops_before_any_send(self):
        with (patch.object(private.delivery, "send_candidate_once", side_effect=AssertionError("unexpected post")),
              self.assertRaises(ValueError)):
            asyncio.run(private.send_prepared(None, [], "https://example.org"))

    def test_prepare_skips_previously_sent_and_requires_multipage_endfield(self):
        data = {
            "nte": [{"id": "252469", "title": "Previously sent", "date": "2024-08-30",
                     "url": "https://nte.perfectworld.com/en/article/news/gamenews/20240830/252469.html"},
                    {"id": "252475", "title": "New", "date": "2024-08-31",
                     "url": "https://nte.perfectworld.com/en/article/news/gamenews/20240830/252475.html"}],
            "endfield": [{"id": "100", "title": "One page", "ts": 1700000000},
                         {"id": "101", "title": "Two pages", "ts": 1700000010}],
            "silverpalace": [{"id": "1", "title": "Previously sent", "date": "2025-01-01"},
                             {"id": "2", "title": "New", "date": "2025-01-02"}],
        }

        async def discover(fetcher, source):
            return data[source]

        async def render(fetcher, settings, source, row):
            return [card()] * (2 if row["id"] == "101" else 1)

        with patch.object(private.delivery, "discover", discover), patch.object(private.delivery, "render_candidate", render):
            chosen = asyncio.run(private.prepare(None, load_settings({})))
        self.assertEqual([row["id"] for _, row, _ in chosen], ["252475", "101", "2"])


if __name__ == "__main__":
    unittest.main()
