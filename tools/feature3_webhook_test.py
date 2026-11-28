"""Manual, bounded private Discord card test. Never reads or writes monitor state.

Uses only four fixed official articles, the existing renderer and media preflight.
The NTE body extractor is test-only, not a registered production reader. Posts
are one-shot and stop on failure/ambiguity; a rerun may duplicate earlier cards.
"""
from __future__ import annotations

import asyncio
import os
import re
import sys
import unittest
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import aiohttp  # noqa: E402
from live_candidate_probe import NoRedirectSession  # noqa: E402
from nte_media_research import inspect as inspect_nte  # noqa: E402

from gamexpress.cards import news_payloads, validate_payload  # noqa: E402
from gamexpress.config import Game  # noqa: E402
from gamexpress.http import Fetcher  # noqa: E402
from gamexpress.media import news_media_available  # noqa: E402
from gamexpress.models import Item  # noqa: E402
from gamexpress.sources import endfield  # noqa: E402
from gamexpress.textutil import news_blocks  # noqa: E402

NTE = (
    ("252469", "Neverness To Everness Trailer | Wonders Await, In Urban Cityscape!"),
    ("252474", "Character Introduction - Nanally"),
)
ENDFIELD = ("0766", "7011")
MAX_POSTS = 8


def valid_webhook(url):
    # No query, fragment, credentials, extra path, alternative ports or host aliases.
    return bool(re.fullmatch(r"https://discord(?:app)?\.com/api/webhooks/[0-9]{1,32}/[A-Za-z0-9._-]{16,256}", url or ""))


class Body(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.depth = 0
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if not self.depth:
            if tag == "div" and "articleContent" in (dict(attrs).get("class") or "").split():
                self.depth = 1
            return
        if tag == "div":
            self.depth += 1
        self.parts.append(self.get_starttag_text())

    def handle_startendtag(self, tag, attrs):
        if self.depth:
            self.parts.append(self.get_starttag_text())

    def handle_endtag(self, tag):
        if not self.depth:
            return
        if tag == "div":
            self.depth -= 1
            if not self.depth:
                return
        self.parts.append(f"</{tag}>")

    def handle_data(self, data):
        if self.depth:
            self.parts.append(data)

    def handle_entityref(self, name):
        if self.depth:
            self.parts.append(f"&{name};")

    def handle_charref(self, name):
        if self.depth:
            self.parts.append(f"&#{name};")


def nte_body(html):
    if inspect_nte(html) is None:
        return None
    body = Body()
    body.feed(html)
    body.close()
    return news_blocks("".join(body.parts))


def image_hosts_safe(item, host):
    urls = list(item.images) + [b.get("url", "") for b in item.article_blocks if b.get("kind") == "image"]
    for url in urls:
        try:
            parts = urlsplit(url)
            if (parts.scheme != "https" or parts.hostname != host or parts.username or parts.password
                    or parts.port not in (None, 443)):
                return False
        except ValueError:
            return False
    return True


async def prepare(fetcher):
    """Render and preflight everything before sending the first message."""
    entries = []
    nte_game = Game(key="nte", name="Neverness to Everness", short="NTE", enabled=False, color=14922399)
    for cid, title in NTE:
        url = f"https://nte.perfectworld.com/en/article/news/gamenews/20240830/{cid}.html"
        html = await fetcher.get_text(url, source="private-card-nte", retries=0)
        blocks = nte_body(html)
        if not blocks:
            raise ValueError("NTE body unavailable")
        item = Item(source="nte", game="nte", id=cid, url=url, title=title, text="", published_ts=0,
                    article_blocks=blocks, author="Neverness to Everness")
        if not image_hosts_safe(item, "ntevmg.perfectworld.com"):
            raise ValueError("NTE unexpected image host")
        entries.append(("nte-" + cid, nte_game, item))
    end_game = Game(key="endfield", name="Arknights: Endfield", short="Endfield", enabled=False, color=14922399)
    rows = await endfield.discover_news(fetcher, end_game, 0)
    for cid in ENDFIELD:
        row = next((r for r in rows or [] if r["id"] == cid), None)
        item = await endfield.news_article(fetcher, end_game, row) if row else None
        if not item or not image_hosts_safe(item, "web-static.hg-cdn.com"):
            raise ValueError("Endfield body or media unavailable")
        entries.append(("endfield-" + cid, end_game, item))
    posts = []
    for label, game, item in entries:
        payloads = news_payloads(game, item)
        if (not payloads or any(validate_payload(payload) for payload in payloads)
                or not await news_media_available(fetcher, payloads, max_urls=40)):
            raise ValueError("card validation or media preflight failed")
        posts.extend((label, payload) for payload in payloads)
    if not 1 <= len(posts) <= MAX_POSTS:
        raise ValueError("card count outside test bound")
    return posts


async def send_once(session, webhook, payload):
    """One POST; no redirects or retries. Return only status class and whether ID exists."""
    try:
        async with session.post(webhook, params={"wait": "true", "with_components": "true"},
                                json=payload, allow_redirects=False,
                                timeout=aiohttp.ClientTimeout(total=30)) as response:
            status = response.status
            try:
                data = await response.json(content_type=None)
            except (ValueError, aiohttp.ClientError, asyncio.TimeoutError):
                data = None
            return 200 <= status < 300 and isinstance(data, dict) and bool(data.get("id")), status
    except (aiohttp.ClientError, asyncio.TimeoutError):
        return False, 0


async def run(*, prepare_only=False):
    webhook = os.environ.get("FEATURE3_TEST_WEBHOOK", "") if not prepare_only else ""
    if not prepare_only and not valid_webhook(webhook):
        raise ValueError("dedicated FEATURE3_TEST_WEBHOOK secret missing or invalid")
    async with aiohttp.ClientSession(trust_env=False) as session:
        fetcher = Fetcher(NoRedirectSession(session))
        posts = await prepare(fetcher)
        print(f"::notice title=Private card preparation::prepared={len(posts)} no-state=1", flush=True)
        for label in ("nte-252469", "nte-252474", "endfield-0766", "endfield-7011"):
            print(f"::notice title=Private card preparation::{label} pages="
                  f"{sum(entry_label == label for entry_label, _ in posts)}", flush=True)
        if prepare_only:
            return
        for number, (label, payload) in enumerate(posts, 1):
            if number > 1:
                await asyncio.sleep(1.5)
            ok, status = await send_once(session, webhook, payload)
            print(f"::notice title=Private card send::{label} message={number}/{len(posts)} "
                  f"http={status} confirmed={int(ok)}", flush=True)
            if not ok:
                raise ValueError("send failed or outcome ambiguous; stopped, inspect channel before rerunning")


class Tests(unittest.TestCase):
    def test_workflow_requires_explicit_scope_and_dedicated_secret(self):
        workflow = (ROOT / ".github/workflows/source_research_probe.yml").read_text(encoding="utf-8")
        self.assertIn("default: all", workflow)
        self.assertIn("if: ${{ inputs.scope == 'feature3-prepare' }}", workflow)
        self.assertIn("if: ${{ inputs.scope == 'feature3-post' }}", workflow)
        self.assertEqual(workflow.count("secrets.FEATURE3_TEST_WEBHOOK"), 10)
        self.assertIn("inputs.scope == 'candidate-private-post'", workflow)
        self.assertIn("inputs.scope == 'nte-taygedo-correction'", workflow)
        self.assertIn("inputs.scope == 'nte-corrections-prepare'", workflow)
        self.assertIn("inputs.scope == 'nte-corrections-send'", workflow)
        self.assertEqual(workflow.count("python tools/feature3_webhook_test.py --prepare-only"), 1)
        self.assertEqual(workflow.count("run: python tools/feature3_webhook_test.py\n"), 1)

    def test_one_shot_sender_stops_on_non_success_without_retry(self):
        class Response:
            status = 500

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                return None

            async def json(self, **kwargs):
                return {}

        class Session:
            def __init__(self):
                self.calls = []

            def post(self, *args, **kwargs):
                self.calls.append(kwargs)
                return Response()

        session = Session()
        self.assertEqual(asyncio.run(send_once(session, "not-used", {})), (False, 500))
        self.assertEqual(len(session.calls), 1)
        self.assertIs(session.calls[0]["allow_redirects"], False)

    def test_url_restrictions(self):
        good = "https://discord.com/api/webhooks/123/" + "a" * 32
        self.assertTrue(valid_webhook(good))
        for bad in ("", good + "?foo=1", good + "/messages/1", good.replace("https:", "http:"),
                    good.replace("discord.com", "discord.com.evil.test"),
                    good.replace("discord.com", "user@discord.com")):
            self.assertFalse(valid_webhook(bad))

    def test_nte_extracts_only_unique_closed_body(self):
        html = ('<p>outside</p><div class="articleContent"><p>Before &amp; after</p>'
                '<img src="https://ntevmg.perfectworld.com/a.jpg"><div><p>last</p></div></div>'
                '<img src="https://outside.invalid/a.jpg">')
        blocks = nte_body(html)
        self.assertEqual([b["kind"] for b in blocks], ["text", "image", "text"])
        self.assertIsNone(nte_body('<div class="articleContent">unclosed'))
        self.assertIsNone(nte_body(html + '<div class="articleContent">another</div>'))

    def test_host_restrictions(self):
        item = Item(source="nte", game="nte", id="1", url="", title="", text="", published_ts=0,
                    article_blocks=[{"kind": "image", "url": "https://ntevmg.perfectworld.com/a.jpg"}])
        self.assertTrue(image_hosts_safe(item, "ntevmg.perfectworld.com"))
        item.article_blocks[0]["url"] = "https://ntevmg.perfectworld.com.evil.test/a.jpg"
        self.assertFalse(image_hosts_safe(item, "ntevmg.perfectworld.com"))


if __name__ == "__main__":
    if sys.argv[1:] == ["--self-test"]:
        unittest.main(argv=[sys.argv[0]])
    elif sys.argv[1:] not in ([], ["--prepare-only"]):
        raise SystemExit("Usage: feature3_webhook_test.py [--self-test|--prepare-only]")
    else:
        try:
            asyncio.run(run(prepare_only=sys.argv[1:] == ["--prepare-only"]))
        except (ValueError, TypeError, KeyError, AttributeError, RecursionError):
            raise SystemExit("Private card test stopped. Check fixed targets, secret and channel before rerunning.") from None
