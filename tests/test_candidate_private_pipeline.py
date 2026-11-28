"""Private test harness tests: only local Git and mocked Discord, never network."""
from __future__ import annotations

import asyncio
import contextlib
import copy
import io
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT))

import candidate_private_backfill as historical  # noqa: E402
import candidate_private_backfill_control as control  # noqa: E402
import candidate_private_pipeline_test as private  # noqa: E402
import silver_dedup_test as silver_fix  # noqa: E402

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

        with (patch.object(private.delivery, "send_candidate_once", send), patch.object(private.asyncio, "sleep", sleep),
              contextlib.redirect_stdout(io.StringIO())):
            sent = asyncio.run(private.send_prepared(None, prepared, HOOK))
        self.assertEqual(sent, 4)
        self.assertEqual(calls, ["nte", "endfield", "endfield", "silverpalace"])

    def test_historical_supervisor_dispatches_one_run_and_requires_progress(self):
        seen = []
        run_record = {"id": 42, "head_sha": "abc", "event": "workflow_dispatch"}

        def command(*args, timeout=50):
            seen.append(args)
            return b"abc\n" if args[:3] == ("git", "rev-parse", "HEAD") else b""

        with (patch.object(control, "current_head", return_value="abc"), patch.object(control, "command", command),
              patch.object(control, "status", side_effect=[(266, 1, 0), (267, 0, 0)]),
              patch.object(control, "runs", side_effect=[{}, {42: run_record}]), patch.object(control, "watch") as watch,
              contextlib.redirect_stdout(io.StringIO())):
            control.run()
        watch.assert_called_once_with(42)
        self.assertEqual(sum(args[:3] == ("gh", "workflow", "run") for args in seen), 1)

        with (patch.object(control, "current_head", return_value="abc"), patch.object(control, "command", command),
              patch.object(control, "status", side_effect=[(266, 1, 0), (266, 1, 0)]),
              patch.object(control, "runs", side_effect=[{}, {42: run_record}]), patch.object(control, "watch"),
              contextlib.redirect_stdout(io.StringIO()), self.assertRaises(ValueError)):
            control.run()

    def test_historical_batch_is_ordered_persisted_and_hides_message_ids(self):
        from gamexpress import candidate_news_delivery as delivery

        settings = load_settings({f"DISCORD_WEBHOOK_NEWS_{source.upper()}": HOOK for source in historical.SOURCES})
        routes = {source: delivery.destination(settings, source)[1] for source in historical.SOURCES}
        rows = {
            "nte": [{"id": "252475", "title": "NTE", "date": "2024-08-30",
                     "url": "https://nte.perfectworld.com/en/article/news/gamenews/20240830/252475.html"}],
            "endfield": [{"id": "100", "title": "Endfield", "ts": 1700000000}],
            "silverpalace": [{"id": "2", "title": "Silver", "date": "2025-01-01"}],
        }
        comments, ids = {}, {source: 1000 + n for n, source in enumerate(historical.SOURCES)}
        for source in historical.SOURCES:
            state = delivery.ingest(source, routes[source], None, rows[source])
            comments[ids[source]] = {"id": ids[source], "user": {"login": "github-actions[bot]"},
                                     "issue_url": "https://api.github.com/repos/uesu/Game-Express/issues/174",
                                     "body": historical.encode(source, state)}
        sends = []

        def api(endpoint, *, method="GET", body=None, paginate=False):
            cid = int(endpoint.rsplit("/", 1)[-1])
            if method == "PATCH":
                comments[cid]["body"] = body["body"]
            return copy.deepcopy(comments[cid])

        async def render(fetcher, conf, source, row):
            return [card(), card()] if source == "endfield" else [card()]

        async def send(session, conf, source, payload):
            cid = ids[source]
            record = historical.decode(source, comments[cid]["body"])
            self.assertTrue(record["partial"]["inflight"])
            sends.append(source)
            return SimpleNamespace(ok=True, ambiguous=False, message_id=str(991234500000000000 + len(sends)))

        async def sleep(seconds):
            self.assertEqual(seconds, 1.5)

        with (patch.object(historical, "COMMENT_IDS", ids), patch.object(historical, "PREPARE_COMPLETE", True),
              patch.object(historical, "gh_api", api), patch.object(delivery, "render_candidate", render),
              patch.object(delivery, "send_candidate_once", send), patch.object(historical.asyncio, "sleep", sleep),
              contextlib.redirect_stdout(io.StringIO())):
            pending = asyncio.run(historical.send_batch(None, None, settings, routes))
        self.assertEqual(pending, 0)
        self.assertEqual(sends, ["endfield", "endfield", "nte", "silverpalace"])
        for source in historical.SOURCES:
            body = comments[ids[source]]["body"]
            self.assertNotIn(HOOK, body)
            self.assertNotIn("9912345000000000", body)
            self.assertEqual(len(historical.decode(source, body)["posted"]), 1)

    def test_historical_inflight_or_changed_journal_never_sends(self):
        from gamexpress import candidate_news_delivery as delivery

        state = delivery.ingest("silverpalace", "a" * 16, None, [{"id": "2", "title": "Silver", "date": "2025-01-01"}])
        state["partial"] = {"id": "2", "signature": "b" * 64, "pages": 1, "messages": [], "inflight": True}
        journals = {source: SimpleNamespace(state={"partial": None, "pending": []}) for source in historical.SOURCES}
        journals["silverpalace"].state = state
        with self.assertRaises(delivery.DeliveryHold):
            historical.oldest(journals)
        comment = {"id": 123, "user": {"login": "github-actions[bot]"},
                   "issue_url": "https://api.github.com/repos/uesu/Game-Express/issues/174",
                   "body": historical.encode("silverpalace", state)}
        journal = historical.CommentJournal("silverpalace", comment, "a" * 16)
        changed = copy.deepcopy(comment)
        changed["body"] += "changed"
        with patch.object(historical, "gh_api", return_value=changed):
            self.assertFalse(asyncio.run(journal.checkpoint(state)))
        self.assertNotEqual(historical.anonymize("123456", "secret-one"), historical.anonymize("123456", "secret-two"))

    def test_silver_fix_preparation_requires_one_article_image_and_full_text(self):
        async def discover(fetcher, source):
            return [{"id": "7", "title": "[Monotype] Beta Test Recruitment has officially started!"}]

        async def render(fetcher, settings, source, row):
            return [{"components": [{"components": [
                {"type": 12, "items": [{"media": {"url": silver_fix.BODY}}]},
                {"type": 10, "content": "How to Participate\nRecruitment Overview"}]}]}]

        with patch.object(silver_fix.delivery, "discover", discover), patch.object(silver_fix.delivery, "render_candidate", render):
            payload = asyncio.run(silver_fix.prepare(None))
        self.assertIn("components", payload)

        async def bad_render(fetcher, settings, source, row):
            result = await render(fetcher, settings, source, row)
            result[0]["components"][0]["components"].append({"type": 12, "items": [{"media": {"url": silver_fix.BODY}}]})
            return result

        with (patch.object(silver_fix.delivery, "discover", discover),
              patch.object(silver_fix.delivery, "render_candidate", bad_render), self.assertRaises(ValueError)):
            asyncio.run(silver_fix.prepare(None))

    def test_silver_fix_refuses_rerun_and_completed_test(self):
        with patch.dict("os.environ", {"GITHUB_RUN_ATTEMPT": "2"}), self.assertRaises(ValueError):
            asyncio.run(silver_fix.run())
        with (patch.dict("os.environ", {"GITHUB_RUN_ATTEMPT": "1"}),
              patch.object(silver_fix, "PRIVATE_TEST_COMPLETED", True), self.assertRaises(ValueError)):
            asyncio.run(silver_fix.run())

    def test_completed_private_test_is_locked_against_repeat(self):
        with (patch.object(private, "prepare", side_effect=AssertionError("unexpected discovery")),
              self.assertRaises(ValueError)):
            asyncio.run(private.main(prepare_only=False))

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

        with (patch.object(private.delivery, "discover", discover), patch.object(private.delivery, "render_candidate", render),
              contextlib.redirect_stdout(io.StringIO())):
            chosen = asyncio.run(private.prepare(None, load_settings({})))
        self.assertEqual([row["id"] for _, row, _ in chosen], ["252475", "101", "2"])


class NewsAnimationPlanTests(unittest.TestCase):
    def test_split_preserves_all_text_and_media_order(self):
        from gamexpress.cards import IS_COMPONENTS_V2, container, gallery, text, validate_payload
        from gamexpress.news_animation import split_pages

        a, b, static = "https://s.elementagames.com/a.jpg", "https://s.elementagames.com/b.jpg", "https://s.elementagames.com/c.jpg"
        original = [{"flags": IS_COMPONENTS_V2, "allowed_mentions": {"parse": []}, "components": [container([
            text("Header and first text"), gallery([a]), text("Middle"), gallery([static, b]), text("Footer")])]}]
        snapshot = copy.deepcopy(original)
        planned = split_pages(original, {a: "animation-" + "a" * 64 + ".gif", b: "animation-" + "b" * 64 + ".gif"}, max_pages=10)
        self.assertEqual(original, snapshot)
        self.assertEqual(len(planned), 2)
        children = [c for p in planned for box in p["components"] for c in box["components"]]
        self.assertEqual([c["content"] for c in children if c["type"] == 10], ["Header and first text", "Middle", "Footer"])
        media = [entry["media"]["url"] for c in children if c["type"] == 12 for entry in c["items"]]
        self.assertEqual(media, ["attachment://animation-" + "a" * 64 + ".gif", static,
                                 "attachment://animation-" + "b" * 64 + ".gif"])
        self.assertTrue(all(len(p["attachments"]) == 1 and not validate_payload(p) for p in planned))
        with self.assertRaises(ValueError):
            split_pages(original, {a: "a", b: "b"}, max_pages=1)
        self.assertIs(split_pages(original, {}, max_pages=1), original)

    def test_allowlist_rejects_spoofed_and_non_https_hosts(self):
        from gamexpress.news_animation import trusted_url

        self.assertTrue(trusted_url("https://s.elementagames.com/a.jpg"))
        self.assertTrue(trusted_url("https://upload-os-bbs.hoyolab.com/a.jpg"))
        for url in ("http://s.elementagames.com/x", "https://s.elementagames.com.evil.test/x",
                    "https://evil@s.elementagames.com/x", "https://s.elementagames.com:444/x",
                    "https://s.elementagames.com/x#fragment"):
            self.assertFalse(trusted_url(url))

class SilverGifProbeTests(unittest.TestCase):
    def test_parser_counts_frames_and_rejects_incomplete_data(self):
        import base64

        from silver_animation_upload_probe import gif_info

        raw = base64.b64decode(
            "R0lGODlhBAAEAIEAAP8AAAAAAAAAAAAAACH/C05FVFNDQVBFMi4wAwEAAAAh+QQACgAAACwAAAAABAAEAAAICQABCBxIsCCAgAAh+QQBCgABACwAAAAABAAEAIEAAP8AAAAAAAAAAAAICQABCBxIsCCAgAA7"
        )
        self.assertEqual(gif_info(raw), (4, 4, 2))
        for invalid in (b"", b"GIF89a", raw[:-1], raw + b"extra", b"JPEG" + raw):
            with self.assertRaises(ValueError):
                gif_info(invalid)
        altered = bytearray(raw)
        altered[6:8] = (1921).to_bytes(2, "little")
        with self.assertRaises(ValueError):
            gif_info(bytes(altered))


if __name__ == "__main__":
    unittest.main()
