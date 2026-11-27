"""Offline state and routing tests; no real webhook, persistence or source access."""
from __future__ import annotations

import asyncio
import contextlib
import copy
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from gamexpress import candidate_news_delivery as delivery  # noqa: E402
from gamexpress import candidate_news_runner as runner  # noqa: E402
from gamexpress.candidate_news_checkpoint import GitCheckpoint  # noqa: E402
from gamexpress.cards import news_payloads  # noqa: E402
from gamexpress.config import Game, load_settings  # noqa: E402
from gamexpress.models import Item  # noqa: E402
from gamexpress.state import State  # noqa: E402

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
    def test_git_checkpoint_persists_to_same_remote_branch_and_rejects_unpushed_work(self):
        branch = "arena/98b5f4e1-game-express"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "work"
            remote = Path(tmp) / "remote.git"
            root.mkdir()

            def git(*args, cwd=root):
                return subprocess.run(["git", *args], cwd=cwd, capture_output=True, check=True)

            git("init", "--bare", str(remote))
            git("init", "-b", branch)
            git("config", "user.name", "Test")
            git("config", "user.email", "test@example.invalid")
            (root / "state").mkdir()
            path = root / "state/state.json"
            path.write_text('{"schema":1}\n', encoding="utf-8")
            git("add", "state/state.json")
            git("commit", "-m", "initial")
            git("remote", "add", "origin", str(remote))
            git("push", "origin", "HEAD:refs/heads/" + branch)
            state = State.load(path)
            data = delivery.ingest("silverpalace", ROUTE, None, [row("1")])
            checkpoint = GitCheckpoint(root, state, "silverpalace", branch)
            self.assertTrue(asyncio.run(checkpoint(data)))
            raw = git("--git-dir", str(remote), "show", "refs/heads/" + branch + ":state/state.json").stdout
            self.assertEqual(json.loads(raw)["candidate_news"]["silverpalace"], data)
            self.assertTrue(asyncio.run(checkpoint(data)))  # identical state is still remote-confirmed

            async def render(article):
                return [payload(article["id"])]

            async def send(page):
                saved = git("--git-dir", str(remote), "show", "refs/heads/" + branch + ":state/state.json").stdout
                record = json.loads(saved)["candidate_news"]["silverpalace"]
                self.assertTrue(record["partial"]["inflight"])
                return SimpleNamespace(ok=True, message_id="101", ambiguous=False)

            posted = asyncio.run(delivery.deliver_oldest(data, "silverpalace", ROUTE, as_of=NOW,
                                                        checkpoint=checkpoint, render=render, send=send))
            raw = git("--git-dir", str(remote), "show", "refs/heads/" + branch + ":state/state.json").stdout
            self.assertEqual(json.loads(raw)["candidate_news"]["silverpalace"], posted)
            self.assertEqual(posted["posted"]["1"]["messages"], ["101"])
            self.assertFalse(asyncio.run(GitCheckpoint(root, state, "silverpalace", "other")(posted)))
            # A lost or modified local candidate record is not an empty first run.
            lost_state = State(path, {"schema": 1})
            self.assertFalse(asyncio.run(GitCheckpoint(root, lost_state, "silverpalace", branch)(data)))
            self.assertEqual(json.loads(git("--git-dir", str(remote), "show", "refs/heads/" + branch + ":state/state.json").stdout)
                             ["candidate_news"]["silverpalace"], posted)
            (root / "unrelated.txt").write_text("keep", encoding="utf-8")
            git("add", "unrelated.txt")
            self.assertFalse(asyncio.run(checkpoint(posted)))  # never commit unrelated staged files
            self.assertEqual(git("diff", "--cached", "--name-only").stdout.strip(), b"unrelated.txt")

    def test_validation_accepts_only_opted_in_candidate_news_and_checks_dedicated_route(self):
        from gamexpress.__main__ import cmd_validate
        base = {"NEWS_GAMES": "silverpalace", "NEWS_CANDIDATES_BACKFILL": "1",
                "DISCORD_WEBHOOK_NEWS_SILVERPALACE": HOOK}
        output = io.StringIO()
        with patch.dict("os.environ", base, clear=True), contextlib.redirect_stdout(output):
            self.assertEqual(cmd_validate(None), 1)
        self.assertIn("delivery is not released", output.getvalue())
        self.assertIn("candidate news silverpalace: dedicated route configured", output.getvalue())
        self.assertNotIn(HOOK, output.getvalue())
        output = io.StringIO()
        with patch.dict("os.environ", {"NEWS_GAMES": "silverpalace"}, clear=True), contextlib.redirect_stdout(output):
            self.assertEqual(cmd_validate(None), 1)
            self.assertIn("unknown game", output.getvalue())
        output = io.StringIO()
        with patch.dict("os.environ", {"NEWS_GAMES": "silverpalace", "NEWS_CANDIDATES_BACKFILL": "1"}, clear=True), contextlib.redirect_stdout(output):
            self.assertEqual(cmd_validate(None), 1)
            self.assertIn("missing/invalid dedicated route", output.getvalue())

    def test_opt_in_runner_routes_oldest_and_persists_without_touching_other_news(self):
        settings = load_settings({"ENABLED_FEATURES": "news", "NEWS_GAMES": "silverpalace",
                                  "NEWS_CANDIDATES_BACKFILL": "1", "DISCORD_WEBHOOK_NEWS_SILVERPALACE": HOOK})
        state = SimpleNamespace(data={"news": {"genshin": {"unchanged": True}}})
        ctx = SimpleNamespace(settings=settings, active=True, state=state, now=NOW,
                              fetcher=object(), webhook=SimpleNamespace(session=object()), report=[], warnings=[])
        rendered, sent = [], []

        async def discover(fetcher, source):
            self.assertEqual(source, "silverpalace")
            return [row("2", "2026-01-02"), row("1", "2026-01-01")]

        async def render(fetcher, conf, source, candidate):
            rendered.append(candidate["id"])
            return [payload(candidate["id"])]

        async def send(session, conf, source, card):
            self.assertEqual(source, "silverpalace")
            self.assertTrue(state.data["candidate_news"][source]["partial"]["inflight"])
            sent.append(card)
            return SimpleNamespace(ok=True, message_id="101", ambiguous=False)

        async def sleep(seconds):
            self.assertEqual(seconds, 1.5)

        class Checkpoint:
            def __init__(self, root, target, source, branch):
                self.target, self.source = target, source
                self_branch = branch
                if self_branch != "arena/98b5f4e1-game-express":
                    raise AssertionError("wrong branch")

            async def __call__(self, snapshot):
                self.target.data.setdefault("candidate_news", {})[self.source] = copy.deepcopy(snapshot)
                return True

        with (patch.dict("os.environ", {"GITHUB_ACTIONS": "true", "GITHUB_REF_NAME": "arena/98b5f4e1-game-express"}),
              patch.object(runner, "CANDIDATE_NEWS_READY", True), patch.object(runner, "GitCheckpoint", Checkpoint), patch.object(runner.asyncio, "sleep", sleep),
              patch.object(delivery, "discover", discover), patch.object(delivery, "render_candidate", render),
              patch.object(delivery, "send_candidate_once", send)):
            asyncio.run(runner.run_candidate_news(ctx))
        result = state.data["candidate_news"]["silverpalace"]
        self.assertEqual(rendered, ["1"])
        self.assertEqual(len(sent), 1)
        self.assertEqual(result["posted"]["1"]["messages"], ["101"])
        self.assertEqual([r["id"] for r in result["pending"]], ["2"])
        self.assertEqual(state.data["news"], {"genshin": {"unchanged": True}})
        self.assertFalse(ctx.warnings)

    def test_runner_stays_inert_without_explicit_opt_in_and_on_peer_config(self):
        settings = load_settings({"ENABLED_FEATURES": "news", "NEWS_GAMES": "silverpalace",
                                  "DISCORD_WEBHOOK_NEWS_SILVERPALACE": HOOK})
        ctx = SimpleNamespace(settings=settings, active=True, state=SimpleNamespace(data={}), now=NOW,
                              fetcher=None, webhook=None, report=[], warnings=[])
        with patch.object(delivery, "discover", side_effect=AssertionError("unexpected network")):
            asyncio.run(runner.run_candidate_news(ctx))
            self.assertEqual(ctx.state.data, {})
            settings = load_settings({"ENABLED_FEATURES": "news", "NEWS_GAMES": "silverpalace",
                                      "NEWS_CANDIDATES_BACKFILL": "1", "PEER_STATE_URL": "https://example.org/state"})
            ctx.settings = settings
            asyncio.run(runner.run_candidate_news(ctx))
            self.assertIn("not released", ctx.warnings[-1])
            with patch.object(runner, "CANDIDATE_NEWS_READY", True):
                asyncio.run(runner.run_candidate_news(ctx))
            self.assertIn("single-instance", ctx.warnings[-1])
            self.assertEqual(ctx.state.data, {})

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

    def test_candidate_full_article_is_required_even_when_default_mode_is_off(self):
        article = Item(source="silverpalace", game="silverpalace", id="1", title="Official 1",
                       url="https://silverpalace.elementagames.com/en-us/newsDetail?id=1", text="", published_ts=0,
                       article_blocks=[{"kind": "text", "text": "Full text " * 1500}])

        async def read(fetcher, game, candidate):
            return article

        settings = load_settings({})
        self.assertFalse(settings.news_expand_full)
        with patch.object(delivery.silverpalace, "news_article", read):
            pages = asyncio.run(delivery.render_candidate(None, settings, "silverpalace", row("1")))
        self.assertGreater(len(pages), 1)
        self.assertNotIn("**Excerpt — this article", json.dumps(pages, ensure_ascii=False))
        settings = load_settings({"NEWS_EXPAND_MAX_PAGES": "1"})
        with (patch.object(delivery.silverpalace, "news_article", read),
              self.assertRaises(delivery.DeliveryHold)):
            asyncio.run(delivery.render_candidate(None, settings, "silverpalace", row("1")))

    def test_private_destination_sends_once_without_redirects_or_retries(self):
        class Content:
            def __init__(self, raw):
                self.raw = raw

            async def iter_chunked(self, size):
                yield self.raw

        class Response:
            def __init__(self, status, raw):
                self.status, self.content = status, Content(raw)

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                return False

        class Session:
            def __init__(self, status=200, raw=b'{"id":"12345"}'):
                self.calls, self.status, self.raw = [], status, raw

            def post(self, url, **kwargs):
                self.calls.append((url, kwargs))
                return Response(self.status, self.raw)

        settings = load_settings({"DISCORD_WEBHOOK_NEWS_SILVERPALACE": HOOK + "?thread_id=123"})
        session = Session()
        result = asyncio.run(delivery.send_candidate_once(session, settings, "silverpalace", payload("1")))
        self.assertTrue(result.ok)
        self.assertEqual(result.message_id, "12345")
        self.assertEqual(len(session.calls), 1)
        self.assertEqual(session.calls[0][0], HOOK)
        self.assertFalse(session.calls[0][1]["allow_redirects"])
        self.assertEqual(session.calls[0][1]["params"], {"wait": "true", "with_components": "true", "thread_id": "123"})
        for status, raw in ((500, b'{}'), (200, b'{}'), (200, b'{bad'), (200, b'x' * 65537)):
            session = Session(status, raw)
            result = asyncio.run(delivery.send_candidate_once(session, settings, "silverpalace", payload("1")))
            self.assertFalse(result.ok)
            self.assertTrue(result.ambiguous)
            self.assertEqual(len(session.calls), 1)
        session = Session()
        result = asyncio.run(delivery.send_candidate_once(session, settings, "nte", payload("1")))
        self.assertFalse(result.ok)
        self.assertFalse(session.calls)

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

    def test_bounded_pages_resume_without_marking_incomplete_article_posted(self):
        state = delivery.ingest("silverpalace", ROUTE, None, [row("1"), row("2")])
        store = Storage()
        pages = [payload("1"), payload("1"), payload("1")]
        calls = []
        async def render(article):
            return pages
        async def send(page):
            calls.append(page)
            return SimpleNamespace(ok=True, message_id=str(100 + len(calls)), ambiguous=False)
        state = asyncio.run(delivery.deliver_oldest(state, "silverpalace", ROUTE, as_of=NOW,
                            checkpoint=store.checkpoint, render=render, send=send, max_pages=2))
        self.assertEqual(state["partial"]["messages"], ["101", "102"])
        self.assertFalse(state["partial"]["inflight"])
        self.assertEqual(state["posted"], {})
        state = asyncio.run(delivery.deliver_oldest(state, "silverpalace", ROUTE, as_of=NOW,
                            checkpoint=store.checkpoint, render=render, send=send, max_pages=2))
        self.assertEqual(state["posted"]["1"]["messages"], ["101", "102", "103"])
        self.assertEqual([r["id"] for r in state["pending"]], ["2"])

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
