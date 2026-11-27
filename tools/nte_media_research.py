"""Read-only, rate-limited NTE article media inventory, not a production adapter.

No response bodies, credentials, signed media links, or user content are printed.
It follows no redirects, sends no Discord messages, and writes no state or fixtures.
"""
from __future__ import annotations

import asyncio
import re
import sys
import unittest
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import aiohttp  # noqa: E402
from archive_research_probe import nte_snapshot  # noqa: E402
from live_candidate_probe import NoRedirectSession  # noqa: E402

from gamexpress.http import Fetcher  # noqa: E402
from gamexpress.sources import nte_candidate  # noqa: E402

MAX_ARTICLES = 200


def media_type(url):
    if not isinstance(url, str) or len(url) > 4096:
        return ""
    try:
        parts = urlsplit(url)
    except ValueError:
        return ""
    host = (parts.hostname or "").lower()
    path = parts.path.lower()
    if host in ("youtube.com", "www.youtube.com", "www.youtube-nocookie.com") and re.fullmatch(
            r"/embed/[a-z0-9_-]{11}", path):
        return "youtube"
    if path.endswith(".gif"):
        return "gif"
    if path.endswith((".mp4", ".webm", ".mov", ".m3u8")):
        return "video"
    return ""


class Article(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.depth = 0
        self.found = 0
        self.closed = 0
        self.suppressed = 0
        self.images = self.gif = self.video = self.youtube = 0

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if not self.depth:
            if tag == "div" and "articleContent" in (attrs.get("class") or "").split():
                self.depth = 1
                self.found += 1
            return
        if tag == "div":
            self.depth += 1
        if tag in ("script", "style"):
            self.suppressed += 1
        if self.suppressed:
            return
        if tag == "img":
            self.images += 1
        if tag in ("img", "iframe", "video", "source", "a"):
            kind = media_type(attrs.get("src") or attrs.get("data-src") or attrs.get("href"))
            if kind == "gif":
                self.gif += 1
            elif kind == "video":
                self.video += 1
            elif kind == "youtube":
                self.youtube += 1
            elif tag == "video":
                self.video += 1  # markup only, not proof that it has playable media

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in ("img", "source", "br", "hr", "input", "meta", "link"):
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        if not self.depth:
            return
        if tag in ("script", "style") and self.suppressed:
            self.suppressed -= 1
        if tag == "div":
            self.depth -= 1
            if not self.depth:
                self.closed += 1


def inspect(html):
    if not isinstance(html, str) or not html or len(html) > 2 * 1024 * 1024:
        return None
    parser = Article()
    try:
        parser.feed(html)
        parser.close()
    except (ValueError, RecursionError):
        return None
    if parser.found != 1 or parser.closed != 1 or parser.depth or parser.suppressed:
        return None
    return {"images": parser.images, "gif": parser.gif, "video": parser.video, "youtube": parser.youtube}


def safe_row(row):
    if not isinstance(row, dict):
        return False
    url, cid, day = row.get("url"), row.get("id"), row.get("date")
    prefix = "https://nte.perfectworld.com"
    if not isinstance(url, str) or not url.startswith(prefix + "/"):
        return False
    match = nte_candidate._PATH.fullmatch(url[len(prefix):])
    return bool(match and match.group(1) == cid and isinstance(day, str) and nte_candidate._day(day))


def choose_examples(results):
    """Select oldest/newest by category and most-image case, never output HTML."""
    ok = [r for r in results if r.get("media") is not None and safe_row(r)]
    examples = []
    for category in ("youtube", "video", "gif", "images"):
        matching = sorted((r for r in ok if r["media"][category]), key=lambda r: (r["date"], r["id"]))
        if matching:
            examples.append((category + "-oldest", matching[0]))
            if matching[-1]["id"] != matching[0]["id"]:
                examples.append((category + "-latest", matching[-1]))
            if category == "images":
                largest = max(matching, key=lambda r: (r["media"]["images"], r["date"], r["id"]))
                examples.append(("images-most", largest))
    return examples


async def audit(fetcher, rows):
    if not isinstance(rows, list) or not 0 < len(rows) <= MAX_ARTICLES or any(not safe_row(r) for r in rows):
        return None
    if len({r["id"] for r in rows}) != len(rows):
        return None
    results = []
    # Two requests at a time; stop after a rate-limit response rather than hammering.
    for i in range(0, len(rows), 2):
        batch = rows[i:i + 2]
        await asyncio.sleep(0.25)
        bodies = await asyncio.gather(*(fetcher.get_text(r["url"], source="research-nte-media",
                                                        retries=0, timeout=15) for r in batch))
        results.extend({**row, "media": inspect(body)} for row, body in zip(batch, bodies))
        health = getattr(fetcher, "health", {}).get("research-nte-media")
        if health and "HTTP 429" in health.last_error:
            break
    return results


def emit(rows, results):
    if results is None:
        print("::notice title=NTE media inventory::nte-audit status=unavailable")
        return
    good = [r for r in results if r["media"] is not None]
    failures = len(results) - len(good)
    unexamined = len(rows) - len(results)
    counts = {key: sum(bool(r["media"][key]) for r in good) for key in ("images", "gif", "video", "youtube")}
    print("::notice title=NTE media inventory::"
          f"nte-audit listed={len(rows)} attempted={len(results)} parsed={len(good)} "
          f"failed={failures} unexamined={unexamined} "
          + " ".join(f"{key}-articles={value}" for key, value in counts.items()))
    for label, row in choose_examples(results):
        m = row["media"]
        print("::notice title=NTE media example::"
              f"{label} day={row['date']} images={m['images']} gif={m['gif']} "
              f"video={m['video']} youtube={m['youtube']} article={row['url']}")


async def run():
    async with aiohttp.ClientSession(trust_env=False) as session:
        fetcher = Fetcher(NoRedirectSession(session))
        rows = await nte_snapshot(fetcher)
        results = await audit(fetcher, rows)
        emit(rows, results)


class Tests(unittest.TestCase):
    def test_counts_article_only_and_youtube_and_gif(self):
        html = ('<img src="/outside.gif"><div class="articleContent"><p><img src="https://x/p.png">'
                '<img src="https://x/anim.gif?ignored=yes"><iframe src="https://www.youtube.com/embed/tdZN6H1N3PU?x=1"></iframe>'
                '<video src="https://x/example.mp4"></video><script><img src="/fake.gif"></script>'
                '</p><div><img src="/extra.webp"></div></div><img src="/footer.gif">')
        self.assertEqual(inspect(html), {"images": 3, "gif": 1, "video": 1, "youtube": 1})
        self.assertIsNone(inspect('<div class="articleContent">no close'))
        self.assertIsNone(inspect('<div class="articleContent"></div><div class="articleContent"></div>'))
        self.assertIsNone(inspect(None))

    def test_only_canonical_listing_urls_can_be_fetched(self):
        row = {"id": "1", "date": "2026-01-01", "url": "https://nte.perfectworld.com/en/article/news/gamenews/20260101/1.html"}
        self.assertTrue(safe_row(row))
        for suffix in ("?token=hidden", "#fragment", "x"):
            self.assertFalse(safe_row({**row, "url": row["url"] + suffix}))
        self.assertFalse(safe_row({**row, "url": row["url"].replace("nte.perfectworld.com", "nte.perfectworld.com.evil.invalid")}))
        self.assertFalse(safe_row({**row, "id": "2"}))

    def test_selection_and_unavailable(self):
        row = {"id": "1", "date": "2026-01-01", "url": "https://nte.perfectworld.com/en/article/news/gamenews/20260101/1.html",
               "media": {"images": 2, "gif": 0, "video": 0, "youtube": 1}}
        self.assertEqual([label for label, _ in choose_examples([row])], ["youtube-oldest", "images-oldest", "images-most"])
        self.assertIsNone(asyncio.run(audit(None, None)))

    def test_rate_limit_stops_remaining_batches(self):
        from types import SimpleNamespace

        class FetcherFake:
            def __init__(self):
                self.calls = []
                self.health = {"research-nte-media": SimpleNamespace(last_error="HTTP 429")}

            async def get_text(self, url, **kwargs):
                self.calls.append((url, kwargs))
                return None

        rows = [{"id": str(i), "date": "2026-01-01", "url":
                 f"https://nte.perfectworld.com/en/article/news/gamenews/20260101/{i}.html"}
                for i in range(4)]
        fetcher = FetcherFake()
        results = asyncio.run(audit(fetcher, rows))
        self.assertEqual(len(results), 2)
        self.assertEqual(len(fetcher.calls), 2)
        self.assertTrue(all(call[1]["retries"] == 0 for call in fetcher.calls))


if __name__ == "__main__":
    if sys.argv[1:] == ["--self-test"]:
        unittest.main(argv=[sys.argv[0]])
    elif sys.argv[1:]:
        raise SystemExit("Usage: nte_media_research.py [--self-test]")
    else:
        asyncio.run(run())
