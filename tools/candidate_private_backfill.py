"""Manual private-only historic Feature 3 test, using guarded PR-comment JSON journals.

The comments are public development-test state, not production state. They contain
only official article metadata, payload hashes and irreversible hashes of Discord
message IDs. They never contain a webhook, token, raw response or message ID.
All cooperating jobs must use the same non-cancelling Actions concurrency group.
"""
from __future__ import annotations

import asyncio
import base64
import copy
import hashlib
import hmac
import json
import os
import re
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import aiohttp  # noqa: E402
from live_candidate_probe import NoRedirectSession  # noqa: E402

from gamexpress import candidate_news_delivery as delivery  # noqa: E402
from gamexpress.config import load_settings  # noqa: E402
from gamexpress.http import Fetcher  # noqa: E402

BRANCH = "arena/98b5f4e1-game-express"
REPOSITORY = "uesu/Game-Express"
ISSUE = 174
SOURCES = ("nte", "endfield", "silverpalace")
MARKER = "feature3-private-historic-test-v1"
MAX_BODY = 60000
MAX_MESSAGES_PER_RUN = 12
MAX_ARTICLES_PER_RUN = 10
# Populated only after a no-post preparation has created and verified all three journals.
COMMENT_IDS = {}
PREPARE_COMPLETE = False


def gh_api(endpoint, *, method="GET", body=None, paginate=False):
    args = ["gh", "api", "--method", method]
    if paginate:
        args += ["--paginate", "--slurp"]
    if body is not None:
        args += ["--input", "-"]
    args.append(endpoint)
    try:
        process = subprocess.run(args, input=json.dumps(body).encode() if body is not None else None,
                                 stdin=None if body is not None else subprocess.DEVNULL,
                                 capture_output=True, timeout=40, check=False)
        if process.returncode:
            text = process.stderr.decode("utf-8", errors="replace")
            status = re.search(r"HTTP ([1-5][0-9]{2})", text)
            print(f"::notice title=Private historic GitHub request::method={method} "
                  f"status={status.group(1) if status else 'unknown'}", flush=True)
            raise ValueError("GitHub journal request not confirmed")
        if len(process.stdout) > 5 * 1024 * 1024:
            raise ValueError("GitHub journal response oversized")
        return json.loads(process.stdout)
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        raise ValueError("GitHub journal request not confirmed") from exc


def encode(source, state):
    raw = json.dumps(state, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode()
    content = f"<!-- {MARKER}:{source}:{base64.b64encode(raw).decode()} -->\nPrivate Feature 3 historic test ledger; do not edit or delete while testing."
    if len(content.encode()) > MAX_BODY:
        raise ValueError("journal exceeds safe size")
    return content


def decode(source, body):
    if not isinstance(body, str) or len(body.encode()) > MAX_BODY:
        raise ValueError("journal missing or oversized")
    match = re.fullmatch(rf"<!-- {MARKER}:{source}:([A-Za-z0-9+/=]+) -->\nPrivate Feature 3 historic test ledger; do not edit or delete while testing\.", body)
    if not match:
        raise ValueError("journal format mismatch")
    return json.loads(base64.b64decode(match.group(1), validate=True))


def check_comment(comment, source, expected_id=None):
    if (not isinstance(comment, dict) or type(comment.get("id")) is not int
            or (expected_id is not None and comment["id"] != expected_id)
            or comment.get("user", {}).get("login") != "github-actions[bot]"
            or comment.get("issue_url") != f"https://api.github.com/repos/{REPOSITORY}/issues/{ISSUE}"):
        raise ValueError("unexpected journal identity")
    return decode(source, comment.get("body"))


class CommentJournal:
    def __init__(self, source, comment, route):
        self.source, self.id, self.route = source, comment["id"], route
        self.body = comment["body"]
        self.state = delivery._validate(check_comment(comment, source, self.id), source, route)

    def _save(self, state):
        try:
            state = delivery._validate(state, self.source, self.route)
            current = gh_api(f"repos/{REPOSITORY}/issues/comments/{self.id}")
            if check_comment(current, self.source, self.id) != self.state or current["body"] != self.body:
                return False
            body = encode(self.source, state)
            result = gh_api(f"repos/{REPOSITORY}/issues/comments/{self.id}", method="PATCH", body={"body": body})
            if check_comment(result, self.source, self.id) != state or result["body"] != body:
                return False
            self.state, self.body = copy.deepcopy(state), body
            return True
        except (ValueError, TypeError, KeyError, AttributeError):
            return False

    async def checkpoint(self, state):
        return await asyncio.to_thread(self._save, state)


def settings_and_routes():
    webhook = os.environ.get("FEATURE3_TEST_WEBHOOK", "")
    settings = load_settings({f"DISCORD_WEBHOOK_NEWS_{source.upper()}": webhook for source in SOURCES})
    routes = {source: delivery.destination(settings, source) for source in SOURCES}
    if any(value is None for value in routes.values()):
        raise ValueError("private test destination unavailable")
    return settings, {source: value[1] for source, value in routes.items()}


def guard():
    if (os.environ.get("GITHUB_REPOSITORY") != REPOSITORY or os.environ.get("GITHUB_REF_NAME") != BRANCH
            or os.environ.get("GITHUB_EVENT_NAME") != "workflow_dispatch" or os.environ.get("GITHUB_RUN_ATTEMPT") != "1"
            or not os.environ.get("GH_TOKEN")):
        raise ValueError("invalid private test context")


def prior_comments():
    found = {source: [] for source in SOURCES}
    for number in range(1, 21):
        page = gh_api(f"repos/{REPOSITORY}/issues/{ISSUE}/comments?per_page=100&page={number}")
        if not isinstance(page, list) or len(page) > 100:
            raise ValueError("comment listing invalid")
        for comment in page:
            text = comment.get("body", "") if isinstance(comment, dict) else ""
            if isinstance(text, str):
                for source in SOURCES:
                    if text.startswith(f"<!-- {MARKER}:{source}:"):
                        found[source].append(comment)
        if len(page) < 100:
            return found
    raise ValueError("too many comments to safely scan")


async def prepare(fetcher, routes):
    if PREPARE_COMPLETE or COMMENT_IDS:
        raise ValueError("private historic test initialization is locked")
    existing = await asyncio.to_thread(prior_comments)
    print("::notice title=Private historic preparation::existing-journals-checked=1", flush=True)
    if any(existing[source] for source in SOURCES):
        raise ValueError("prior journals exist; inspect before creating anything")
    states = {}
    # Complete and validate every snapshot before creating any test journal.
    for source in SOURCES:
        rows = await delivery.discover(fetcher, source)
        states[source] = delivery.ingest(source, routes[source], None, rows)
        print(f"::notice title=Private historic snapshot::{source} items={len(states[source]['pending'])}", flush=True)
        encode(source, states[source])  # check bounded size before any journal creation
    for source in SOURCES:
        result = await asyncio.to_thread(gh_api, f"repos/{REPOSITORY}/issues/{ISSUE}/comments", method="POST",
                                         body={"body": encode(source, states[source])})
        if check_comment(result, source) != states[source]:
            raise ValueError("journal creation not verified")
        print(f"::notice title=Private historic journal::{source} comment={result['id']} "
              f"queued={len(states[source]['pending'])} sent=0", flush=True)


def oldest(journals):
    partials = [source for source in SOURCES if journals[source].state["partial"]]
    if len(partials) > 1 or any(journals[source].state["partial"]["inflight"] for source in partials):
        raise delivery.DeliveryHold("in-flight page requires review")
    if partials:
        return partials[0]
    candidates = []
    for source in SOURCES:
        rows = journals[source].state["pending"]
        if not rows:
            continue
        row = rows[0]
        if source == "endfield":
            day = datetime.fromtimestamp(row["ts"], UTC).date().isoformat()
            within = row["ts"]
        else:
            day = row["date"]
            within = 0  # day-only: tie order is deterministic, not verified chronology
        candidates.append(((day, within, source, int(row["id"]), row["id"]), source))
    return min(candidates)[1] if candidates else None


def anonymize(message_id, secret):
    if not isinstance(message_id, str) or not re.fullmatch(r"[0-9]{1,32}", message_id):
        raise ValueError("invalid confirmed message ID")
    if not isinstance(secret, str) or not secret:
        raise ValueError("missing private hashing key")
    return str(int.from_bytes(hmac.new(secret.encode(), message_id.encode(), hashlib.sha256).digest()[:12], "big"))


async def send_batch(session, fetcher, settings, routes):
    if not PREPARE_COMPLETE or set(COMMENT_IDS) != set(SOURCES):
        raise ValueError("private test journal IDs are not locked")
    journals = {}
    for source in SOURCES:
        comment = await asyncio.to_thread(gh_api, f"repos/{REPOSITORY}/issues/comments/{COMMENT_IDS[source]}")
        journals[source] = CommentJournal(source, comment, routes[source])
    sent, articles = 0, 0
    while sent < MAX_MESSAGES_PER_RUN and articles < MAX_ARTICLES_PER_RUN:
        source = oldest(journals)
        if source is None:
            break
        journal = journals[source]
        row_id = journal.state["pending"][0]["id"]
        before = len(journal.state["posted"])

        async def render(row, *, _source=source):
            return await delivery.render_candidate(fetcher, settings, _source, row)

        async def send(payload, *, _source=source, _id=row_id):
            nonlocal sent
            await asyncio.sleep(1.5)
            result = await delivery.send_candidate_once(session, settings, _source, payload)
            if not result.ok or result.ambiguous or not result.message_id:
                print(f"::notice title=Private historic send::{_source} id={_id} confirmed=0 inspect-before-resume=1", flush=True)
                return result
            sent += 1
            print(f"::notice title=Private historic send::{_source} id={_id} confirmed=1 batch-pages={sent}", flush=True)
            return SimpleNamespace(ok=True, ambiguous=False, message_id=anonymize(
                result.message_id, settings.env[f"DISCORD_WEBHOOK_NEWS_{_source.upper()}"]))

        state = await delivery.deliver_oldest(journal.state, source, journal.route, as_of=int(time.time()),
                                              checkpoint=journal.checkpoint, render=render, send=send,
                                              max_pages=min(3, MAX_MESSAGES_PER_RUN - sent))
        if len(state["posted"]) > before:
            articles += 1
        if state["partial"]:
            # Continue the same article on the next job, never skip to another.
            break
    pending = sum(len(journal.state["pending"]) for journal in journals.values())
    posted = sum(len(journal.state["posted"]) for journal in journals.values())
    print(f"::notice title=Private historic progress::confirmed-articles={posted} remaining-articles={pending} "
          f"batch-pages={sent} finished={int(pending == 0)} production-state=unchanged", flush=True)
    return pending


async def main(mode):
    guard()
    settings, routes = settings_and_routes()
    async with aiohttp.ClientSession(trust_env=False) as session:
        fetcher = Fetcher(NoRedirectSession(session))
        if mode == "prepare":
            await prepare(fetcher, routes)
        else:
            await send_batch(session, fetcher, settings, routes)


if __name__ == "__main__":
    if sys.argv[1:] not in (["--prepare"], ["--send"]):
        raise SystemExit("Specify --prepare or --send explicitly.")
    try:
        asyncio.run(main(sys.argv[1][2:]))
    except Exception as exc:  # noqa: BLE001 — never expose webhook URLs, token or remote response content
        print(f"::notice title=Private historic hold::error-type={type(exc).__name__}", flush=True)
        raise SystemExit("Private backfill held; inspect journal and channel before continuing. No automatic retry.") from None
