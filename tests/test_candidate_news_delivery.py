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
from gamexpress.candidate_news_checkpoint import GitCheckpoint, IsolatedGitLedger, reconcile_checkpointed  # noqa: E402
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

    def test_isolated_ledger_holds_stale_writer_and_leaves_monitor_checkout_alone(self):
        branch = "arena/98b5f4e1-game-express"
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            remote, seed = base / "remote.git", base / "seed"
            seed.mkdir()

            def git(cwd, *args):
                return subprocess.run(["git", *args], cwd=cwd, capture_output=True, check=True).stdout

            git(seed, "init", "--bare", str(remote))
            git(seed, "init", "-b", branch)
            git(seed, "config", "user.name", "Test")
            git(seed, "config", "user.email", "test@example.invalid")
            (seed / "state").mkdir()
            (seed / "state/state.json").write_text('{"schema":1}\n', encoding="utf-8")
            (seed / "state/candidate_news.json").write_text('{"schema":1,"candidate_news":{}}\n', encoding="utf-8")
            git(seed, "add", "state")
            git(seed, "commit", "-m", "initial")
            git(seed, "remote", "add", "origin", str(remote))
            git(seed, "push", "origin", "HEAD:refs/heads/" + branch)
            other = base / "other"
            git(base, "clone", "-b", branch, str(remote), str(other))
            original = git(seed, "rev-parse", "HEAD")
            first, stale = IsolatedGitLedger(seed, branch), IsolatedGitLedger(other, branch)
            self.assertTrue(asyncio.run(first.open()))
            self.assertTrue(asyncio.run(stale.open()))
            try:
                queued = delivery.ingest("silverpalace", ROUTE, None, [row("1")])
                self.assertTrue(asyncio.run(first.checkpoint("silverpalace", queued)))
                self.assertFalse(asyncio.run(stale.checkpoint("silverpalace", queued)))
                self.assertTrue(stale.poisoned)
                self.assertFalse(asyncio.run(stale.checkpoint("silverpalace", queued)))
                self.assertEqual(git(seed, "rev-parse", "HEAD"), original)
                self.assertEqual(git(seed, "status", "--porcelain"), b"")
                self.assertEqual(json.loads((seed / "state/candidate_news.json").read_text())["candidate_news"], {})
                # The existing final monitor-state commit can rebase over the separate ledger.
                (seed / "state/state.json").write_text('{"schema":1,"existing":"preserved"}\n', encoding="utf-8")
                git(seed, "add", "state/state.json")
                git(seed, "commit", "-m", "monitor state")
                git(seed, "pull", "--rebase", "origin", branch)
                git(seed, "push", "origin", f"HEAD:refs/heads/{branch}")
                persisted = json.loads(git(seed, "--git-dir", str(remote), "show",
                                           f"refs/heads/{branch}:state/candidate_news.json"))
                self.assertEqual(persisted["candidate_news"]["silverpalace"], queued)
                self.assertFalse(asyncio.run(first.checkpoint("silverpalace", queued)))
                self.assertTrue(first.poisoned)
            finally:
                asyncio.run(first.close())
                asyncio.run(stale.close())
            self.assertEqual(git(seed, "worktree", "list", "--porcelain").count(b"worktree "), 1)

    def test_isolated_ledger_requires_existing_tracked_valid_file(self):
        branch = "arena/98b5f4e1-game-express"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "work"
            remote = Path(tmp) / "remote.git"
            root.mkdir()

            def git(*args):
                return subprocess.run(["git", *args], cwd=root, capture_output=True, check=True).stdout

            git("init", "--bare", str(remote))
            git("init", "-b", branch)
            git("config", "user.name", "Test")
            git("config", "user.email", "test@example.invalid")
            (root / "state").mkdir()
            (root / "state/state.json").write_text('{"schema":1}\n', encoding="utf-8")
            git("add", "state")
            git("commit", "-m", "initial")
            git("remote", "add", "origin", str(remote))
            git("push", "origin", f"HEAD:refs/heads/{branch}")
            ledger = IsolatedGitLedger(root, branch)
            self.assertFalse(asyncio.run(ledger.open()))  # no ledger is not a fresh empty ledger
            self.assertTrue(ledger.poisoned)
            (root / "state/candidate_news.json").write_text('{"schema":true,"candidate_news":{}}\n', encoding="utf-8")
            git("add", "state/candidate_news.json")
            git("commit", "-m", "malformed ledger")
            git("push", "origin", f"HEAD:refs/heads/{branch}")
            ledger = IsolatedGitLedger(root, branch)
            self.assertFalse(asyncio.run(ledger.open()))
            self.assertTrue(ledger.poisoned)
            self.assertIsNone(ledger.data)

    def test_reconciliation_is_durably_checkpointed_without_resending(self):
        branch = "arena/98b5f4e1-game-express"
        with tempfile.TemporaryDirectory() as tmp:
            root, remote = Path(tmp) / "work", Path(tmp) / "remote.git"
            root.mkdir()

            def git(*args):
                return subprocess.run(["git", *args], cwd=root, capture_output=True, check=True).stdout

            git("init", "--bare", str(remote))
            git("init", "-b", branch)
            git("config", "user.name", "Test")
            git("config", "user.email", "test@example.invalid")
            queued = delivery.ingest("silverpalace", ROUTE, None, [row("1")])
            queued["partial"] = {"id": "1", "signature": "b" * 64, "pages": 1, "messages": [], "inflight": True}
            (root / "state").mkdir()
            (root / "state/candidate_news.json").write_text(
                json.dumps({"schema": 1, "candidate_news": {"silverpalace": queued}}), encoding="utf-8")
            git("add", "state/candidate_news.json")
            git("commit", "-m", "held page")
            git("remote", "add", "origin", str(remote))
            git("push", "origin", f"HEAD:refs/heads/{branch}")
            ledger = IsolatedGitLedger(root, branch)
            self.assertTrue(asyncio.run(ledger.open()))
            try:
                with self.assertRaises(delivery.DeliveryHold):
                    asyncio.run(reconcile_checkpointed(ledger, "silverpalace", ROUTE, article_id="1", page=2,
                                                       signature="b" * 64, resolution="delivered", message_id="101"))
                self.assertTrue(ledger.data["candidate_news"]["silverpalace"]["partial"]["inflight"])
                result = asyncio.run(reconcile_checkpointed(ledger, "silverpalace", ROUTE, article_id="1", page=1,
                                                           signature="b" * 64, resolution="delivered", message_id="101"))
                self.assertFalse(result["partial"]["inflight"])
                saved = json.loads(git("--git-dir", str(remote), "show", f"refs/heads/{branch}:state/candidate_news.json"))
                self.assertEqual(saved["candidate_news"]["silverpalace"], result)
                self.assertEqual(result["partial"]["messages"], ["101"])
            finally:
                asyncio.run(ledger.close())

    def test_stale_writer_and_crash_hold_until_reviewed_git_reconciliation(self):
        branch = "arena/98b5f4e1-game-express"
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            remote, seed = base / "remote.git", base / "seed"
            seed.mkdir()

            def git(cwd, *args):
                return subprocess.run(["git", *args], cwd=cwd, capture_output=True, check=True).stdout

            git(seed, "init", "--bare", str(remote))
            git(seed, "init", "-b", branch)
            git(seed, "config", "user.name", "Test")
            git(seed, "config", "user.email", "test@example.invalid")
            (seed / "state").mkdir()
            (seed / "state/state.json").write_text('{"schema":1}\n', encoding="utf-8")
            git(seed, "add", "state/state.json")
            git(seed, "commit", "-m", "initial")
            git(seed, "remote", "add", "origin", str(remote))
            git(seed, "push", "origin", "HEAD:refs/heads/" + branch)
            writer_a, writer_b, restarted = base / "a", base / "b", base / "restarted"
            for dest in (writer_a, writer_b):
                git(base, "clone", "-b", branch, str(remote), str(dest))
            state_a, state_b = (State.load(p / "state/state.json") for p in (writer_a, writer_b))
            queued = delivery.ingest("silverpalace", ROUTE, None, [row("1")])
            sends = []

            async def render(article):
                return [payload(article["id"])]

            async def ambiguous(card):
                sends.append("ambiguous")
                raise TimeoutError("lost after send")

            async def unexpected(card):
                sends.append("unexpected")
                return SimpleNamespace(ok=True, message_id="999", ambiguous=False)

            with self.assertRaises(delivery.DeliveryHold):
                asyncio.run(delivery.deliver_oldest(queued, "silverpalace", ROUTE, as_of=NOW,
                            checkpoint=GitCheckpoint(writer_a, state_a, "silverpalace", branch),
                            render=render, send=ambiguous))
            # A writer with the old HEAD must not send, even though it started before the first one.
            with self.assertRaises(delivery.DeliveryHold):
                asyncio.run(delivery.deliver_oldest(queued, "silverpalace", ROUTE, as_of=NOW,
                            checkpoint=GitCheckpoint(writer_b, state_b, "silverpalace", branch),
                            render=render, send=unexpected))
            git(base, "clone", "-b", branch, str(remote), str(restarted))
            state_c = State.load(restarted / "state/state.json")
            held = state_c.data["candidate_news"]["silverpalace"]
            self.assertTrue(held["partial"]["inflight"])
            checkpoint = GitCheckpoint(restarted, state_c, "silverpalace", branch)
            with self.assertRaises(delivery.DeliveryHold):
                asyncio.run(delivery.deliver_oldest(held, "silverpalace", ROUTE, as_of=NOW,
                            checkpoint=checkpoint, render=render, send=unexpected))
            reviewed = delivery.reconcile_inflight(held, "silverpalace", ROUTE, article_id="1", page=1,
                                                   signature=held["partial"]["signature"],
                                                   resolution="delivered", message_id="101")
            self.assertTrue(asyncio.run(checkpoint(reviewed)))
            result = asyncio.run(delivery.deliver_oldest(reviewed, "silverpalace", ROUTE, as_of=NOW,
                                 checkpoint=checkpoint, render=render, send=unexpected))
            self.assertEqual(sends, ["ambiguous"])
            self.assertEqual(result["posted"]["1"]["messages"], ["101"])
            persisted = json.loads(git(base, "--git-dir", str(remote), "show", f"refs/heads/{branch}:state/state.json"))
            self.assertEqual(persisted["candidate_news"]["silverpalace"], result)

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
                                  "NEWS_CANDIDATES_BACKFILL": "1", "DISCORD_WEBHOOK_NEWS_SILVERPALACE": HOOK,
                                  "NEWS_CANDIDATES_AUTHORITY_REPOSITORY": "uesu/Game-Express",
                                  "NEWS_CANDIDATES_AUTHORITY_BRANCH": "arena/98b5f4e1-game-express"})
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

        async def sleep(seconds):
            self.assertEqual(seconds, 1.5)

        ledgers = []

        class Ledger:
            def __init__(self, root, branch):
                self.data, self.poisoned = {"candidate_news": {}}, False
                if branch != "arena/98b5f4e1-game-express":
                    raise AssertionError("wrong branch")
                ledgers.append(self)

            async def open(self):
                return True

            async def checkpoint(self, source, snapshot):
                self.data["candidate_news"][source] = copy.deepcopy(snapshot)
                return True

            async def close(self):
                pass

        # The send callback observes the ledger, not the monitor state.
        async def send(session, conf, source, card):
            self.assertEqual(source, "silverpalace")
            self.assertTrue(ledgers[0].data["candidate_news"][source]["partial"]["inflight"])
            sent.append(card)
            return SimpleNamespace(ok=True, message_id="101", ambiguous=False)

        with (patch.dict("os.environ", {"GITHUB_ACTIONS": "true", "GITHUB_REF_NAME": "arena/98b5f4e1-game-express",
                                       "GITHUB_REF": "refs/heads/arena/98b5f4e1-game-express",
                                       "GITHUB_REPOSITORY": "uesu/Game-Express", "GITHUB_EVENT_NAME": "workflow_dispatch"}),
              patch.object(runner, "_origin_is_authority", return_value=True),
              patch.object(runner, "CANDIDATE_NEWS_READY", True), patch.object(runner, "IsolatedGitLedger", Ledger),
              patch.object(runner.asyncio, "sleep", sleep), patch.object(delivery, "discover", discover),
              patch.object(delivery, "render_candidate", render), patch.object(delivery, "send_candidate_once", send)):
            asyncio.run(runner.run_candidate_news(ctx))
        result = ledgers[0].data["candidate_news"]["silverpalace"]
        self.assertEqual(rendered, ["1"])
        self.assertEqual(len(sent), 1)
        self.assertEqual(result["posted"]["1"]["messages"], ["101"])
        self.assertEqual([r["id"] for r in result["pending"]], ["2"])
        self.assertEqual(state.data["news"], {"genshin": {"unchanged": True}})
        self.assertFalse(ctx.warnings)

    def test_gated_runner_uses_real_isolated_ledger_without_touching_monitor_state(self):
        branch = "arena/98b5f4e1-game-express"
        with tempfile.TemporaryDirectory() as tmp:
            root, remote = Path(tmp) / "work", Path(tmp) / "remote.git"
            root.mkdir()

            def git(*args):
                return subprocess.run(["git", *args], cwd=root, capture_output=True, check=True).stdout

            git("init", "--bare", str(remote))
            git("init", "-b", branch)
            git("config", "user.name", "Test")
            git("config", "user.email", "test@example.invalid")
            (root / "state").mkdir()
            (root / "state/state.json").write_text('{"schema":1,"news":{"old":"unchanged"}}\n', encoding="utf-8")
            (root / "state/candidate_news.json").write_text('{"schema":1,"candidate_news":{}}\n', encoding="utf-8")
            git("add", "state")
            git("commit", "-m", "initial")
            git("remote", "add", "origin", str(remote))
            git("push", "origin", f"HEAD:refs/heads/{branch}")
            before = git("rev-parse", "HEAD")
            settings = load_settings({"ENABLED_FEATURES": "news", "NEWS_GAMES": "silverpalace",
                                      "NEWS_CANDIDATES_BACKFILL": "1", "DISCORD_WEBHOOK_NEWS_SILVERPALACE": HOOK,
                                      "NEWS_CANDIDATES_AUTHORITY_REPOSITORY": "uesu/Game-Express",
                                      "NEWS_CANDIDATES_AUTHORITY_BRANCH": branch})
            ctx = SimpleNamespace(settings=settings, active=True, state=State.load(root / "state/state.json"), now=NOW,
                                  fetcher=None, webhook=SimpleNamespace(session=None), report=[], warnings=[])
            sends = []

            async def discover(fetcher, source):
                return [row("1"), row("2")]

            async def render(fetcher, conf, source, article):
                return [payload(article["id"])]

            async def send(session, conf, source, card):
                recorded = json.loads(git("--git-dir", str(remote), "show", f"refs/heads/{branch}:state/candidate_news.json"))
                self.assertTrue(recorded["candidate_news"][source]["partial"]["inflight"])
                sends.append(source)
                return SimpleNamespace(ok=True, message_id="101", ambiguous=False)

            async def sleep(seconds):
                pass

            with (patch.dict("os.environ", {"GITHUB_ACTIONS": "true", "GITHUB_REF_NAME": branch,
                                           "GITHUB_REF": f"refs/heads/{branch}", "GITHUB_REPOSITORY": "uesu/Game-Express",
                                           "GITHUB_EVENT_NAME": "workflow_dispatch"}),
                  patch.object(runner, "_origin_is_authority", return_value=True), patch.object(runner, "ROOT", root), patch.object(runner, "CANDIDATE_NEWS_READY", True),
                  patch.object(runner.asyncio, "sleep", sleep), patch.object(delivery, "discover", discover),
                  patch.object(delivery, "render_candidate", render), patch.object(delivery, "send_candidate_once", send)):
                asyncio.run(runner.run_candidate_news(ctx))
            self.assertEqual(sends, ["silverpalace"])
            self.assertFalse(ctx.warnings)
            self.assertEqual(git("rev-parse", "HEAD"), before)
            self.assertEqual(git("status", "--porcelain"), b"")
            self.assertEqual(ctx.state.data["news"], {"old": "unchanged"})
            self.assertNotIn("candidate_news", ctx.state.data)
            recorded = json.loads(git("--git-dir", str(remote), "show", f"refs/heads/{branch}:state/candidate_news.json"))
            self.assertEqual(recorded["candidate_news"]["silverpalace"]["posted"]["1"]["messages"], ["101"])
            self.assertEqual(recorded["candidate_news"]["silverpalace"]["pending"][0]["id"], "2")

    def test_candidate_authority_restricts_repo_branch_origin_role_and_event(self):
        branch = "arena/98b5f4e1-game-express"
        env = {"GITHUB_ACTIONS": "true", "GITHUB_EVENT_NAME": "workflow_dispatch", "GITHUB_REPOSITORY": "uesu/Game-Express",
               "GITHUB_REF_NAME": branch, "GITHUB_REF": f"refs/heads/{branch}"}
        config = {"NEWS_CANDIDATES_AUTHORITY_REPOSITORY": "uesu/Game-Express", "NEWS_CANDIDATES_AUTHORITY_BRANCH": branch}
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            subprocess.run(["git", "init", "-b", branch], cwd=root, capture_output=True, check=True)
            subprocess.run(["git", "remote", "add", "origin", "https://github.com/uesu/Game-Express.git"],
                           cwd=root, capture_output=True, check=True)
            with patch.dict("os.environ", env, clear=True):
                self.assertEqual(runner.authoritative_branch(load_settings(config), root), branch)
                self.assertEqual(runner.authoritative_branch(load_settings({**config, "PEER_STATE_URL": "https://peer.invalid"}), root), branch)
                self.assertIsNone(runner.authoritative_branch(load_settings({**config, "INSTANCE_ROLE": "standby"}), root))
                self.assertIsNone(runner.authoritative_branch(load_settings({}), root))
                for key, value in (("GITHUB_REPOSITORY", "uesu/Other"), ("GITHUB_REF", "refs/tags/" + branch),
                                   ("GITHUB_EVENT_NAME", "pull_request"), ("GITHUB_REF_NAME", "other")):
                    with patch.dict("os.environ", {key: value}):
                        self.assertIsNone(runner.authoritative_branch(load_settings(config), root))
                subprocess.run(["git", "remote", "set-url", "origin", "https://github.com/uesu/Other.git"],
                               cwd=root, capture_output=True, check=True)
                self.assertIsNone(runner.authoritative_branch(load_settings(config), root))
                subprocess.run(["git", "remote", "set-url", "origin", "https://secret@github.com/uesu/Game-Express.git"],
                               cwd=root, capture_output=True, check=True)
                self.assertIsNone(runner.authoritative_branch(load_settings(config), root))

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
            self.assertIn("authority unavailable", ctx.warnings[-1])
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

    def test_reviewed_reconciliation_prevents_blind_resend_and_rejects_stale_evidence(self):
        state = delivery.ingest("silverpalace", ROUTE, None, [row("1")])
        store = Storage()
        calls = []

        async def render(candidate):
            return [payload("1"), payload("1")]

        async def ambiguous(card):
            calls.append(card)
            return SimpleNamespace(ok=False, ambiguous=True, message_id=None)

        with self.assertRaises(delivery.DeliveryHold):
            asyncio.run(delivery.deliver_oldest(state, "silverpalace", ROUTE, as_of=NOW,
                                               checkpoint=store.checkpoint, render=render, send=ambiguous))
        held = store.states[-1]
        original = copy.deepcopy(held)
        signature = held["partial"]["signature"]
        for kwargs in (
            {"article_id": "2", "page": 1, "signature": signature, "resolution": "delivered", "message_id": "101"},
            {"article_id": "1", "page": 2, "signature": signature, "resolution": "delivered", "message_id": "101"},
            {"article_id": "1", "page": 1, "signature": "b" * 64, "resolution": "delivered", "message_id": "101"},
            {"article_id": "1", "page": 1, "signature": signature, "resolution": "delivered", "message_id": None},
            {"article_id": "1", "page": 1, "signature": signature, "resolution": "absent", "message_id": "101"},
        ):
            with self.assertRaises(delivery.DeliveryHold):
                delivery.reconcile_inflight(held, "silverpalace", ROUTE, **kwargs)
        self.assertEqual(held, original)
        corrected = delivery.reconcile_inflight(held, "silverpalace", ROUTE, article_id="1", page=1,
                                                signature=signature, resolution="delivered", message_id="101")
        self.assertEqual(corrected["partial"]["messages"], ["101"])
        self.assertTrue(held["partial"]["inflight"])  # no silent state mutation
        self.assertTrue(asyncio.run(store.checkpoint(corrected)))

        async def confirmed(card):
            calls.append(card)
            return SimpleNamespace(ok=True, ambiguous=False, message_id="102")

        posted = asyncio.run(delivery.deliver_oldest(corrected, "silverpalace", ROUTE, as_of=NOW,
                                                     checkpoint=store.checkpoint, render=render, send=confirmed))
        self.assertEqual(posted["posted"]["1"]["messages"], ["101", "102"])
        self.assertEqual(len(calls), 2)  # initial ambiguous page and only the second page
        self.assertFalse(posted["pending"])

    def test_reconcile_absence_requires_explicit_resolution_and_preserves_page(self):
        state = delivery.ingest("silverpalace", ROUTE, None, [row("1")])
        store = Storage()

        async def render(candidate):
            return [payload("1")]

        async def lost(card):
            raise TimeoutError("unknown")

        with self.assertRaises(delivery.DeliveryHold):
            asyncio.run(delivery.deliver_oldest(state, "silverpalace", ROUTE, as_of=NOW,
                                               checkpoint=store.checkpoint, render=render, send=lost))
        held = store.states[-1]
        fixed = delivery.reconcile_inflight(held, "silverpalace", ROUTE, article_id="1", page=1,
                                            signature=held["partial"]["signature"], resolution="absent")
        self.assertFalse(fixed["partial"]["inflight"])
        self.assertEqual(fixed["partial"]["messages"], [])
        self.assertTrue(held["partial"]["inflight"])

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
