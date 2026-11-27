"""Bounded, read-only archive research, not a source adapter or baseline.

Reports complete listing scans and oldest/newest *displayed days*. It does not
read every article body, post to Discord, save state, or guarantee a snapshot.
"""
from __future__ import annotations

import asyncio
import re
import sys
import unittest
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import aiohttp  # noqa: E402
from live_candidate_probe import NoRedirectSession  # noqa: E402

from gamexpress.config import Game  # noqa: E402
from gamexpress.http import Fetcher  # noqa: E402
from gamexpress.sources import endfield, nte_candidate, silverpalace  # noqa: E402

MAX_PAGES = 100
NTE_BASE = "https://nte.perfectworld.com/en/article/news/"


class Pager(HTMLParser):
    """Validate the observed numbered first-page navigation, without trusting hrefs."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.depth = 0
        self.found = 0
        self.href = None
        self.text = ""
        self.numbers = []
        self.invalid = False

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if not self.depth:
            if tag == "ul" and "pagination" in (attrs.get("class") or "").split():
                self.depth = 1
                self.found += 1
            return
        if tag == "ul":
            self.depth += 1
        if tag == "a":
            if self.href is not None:
                self.invalid = True
            self.href = attrs.get("href", "")
            self.text = ""

    def handle_data(self, data):
        if self.href is not None:
            self.text += data

    def handle_endtag(self, tag):
        if not self.depth:
            return
        if tag == "a" and self.href is not None:
            text = self.text.strip()
            if re.fullmatch(r"[0-9]{1,3}", text):
                number = int(text)
                expected = "#" if number == 1 else f"index{number - 1}.html"
                if self.href != expected:
                    self.invalid = True
                self.numbers.append(number)
            self.href = None
        elif tag == "ul":
            self.depth -= 1


def nte_pages(html):
    if not isinstance(html, str) or not html or len(html) > 1024 * 1024:
        return None
    parser = Pager()
    try:
        parser.feed(html)
        parser.close()
    except (ValueError, RecursionError):
        return None
    n = len(parser.numbers)
    if (parser.invalid or parser.found != 1 or parser.depth or parser.href is not None
            or not 1 <= n <= MAX_PAGES or parser.numbers != list(range(1, n + 1))):
        return None
    return n


def nte_url(index):
    if type(index) is not int or not 0 <= index < MAX_PAGES:
        raise ValueError("page out of bounds")
    return NTE_BASE + ("index.html" if index == 0 else f"index{index}.html")


async def nte_walk(fetcher):
    first = await fetcher.get_text(nte_url(0), source="research-nte-archive", retries=1)
    total = nte_pages(first)
    initial = nte_candidate.parse_list_page(first)
    if total is None or initial is None:
        return None
    gate = asyncio.Semaphore(3)

    async def read(index):
        async with gate:
            await asyncio.sleep(0.1)
            return await fetcher.get_text(nte_url(index), source="research-nte-archive", retries=1)

    pages = [first, *await asyncio.gather(*(read(i) for i in range(1, total)))]
    rows = []
    seen = set()
    width = len(initial)
    for index, html in enumerate(pages):
        parsed = nte_candidate.parse_list_page(html)
        if (parsed is None or (index < total - 1 and len(parsed) != width)
                or len(parsed) > width):
            return None
        for row in parsed:
            if row["id"] in seen:
                return None
            seen.add(row["id"])
            rows.append(row)
    # Re-read the first page to notice some changes during the walk.
    end = await fetcher.get_text(nte_url(0), source="research-nte-archive", retries=1)
    if nte_pages(end) != total or nte_candidate.parse_list_page(end) != initial:
        return None
    return rows


async def nte_snapshot(fetcher):
    first = await nte_walk(fetcher)
    if first is None:
        return None
    second = await nte_walk(fetcher)
    return first if first == second else None


def report(name, rows, day_key):
    if rows is None:
        print(f"::notice title=Archive research::{name} status=unavailable count=0")
        return
    if not rows:
        print(f"::notice title=Archive research::{name} status=empty count=0")
        return
    days = [day_key(row) for row in rows]
    if any(not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", day) for day in days):
        raise ValueError("invalid day")
    print(f"::notice title=Archive research::{name} status=ok count={len(rows)} "
          f"oldest={min(days)} latest={max(days)}")


async def run():
    from datetime import UTC, datetime

    async with aiohttp.ClientSession(trust_env=False) as session:
        fetcher = Fetcher(NoRedirectSession(session))
        nte = await nte_snapshot(fetcher)
        report("nte-listings", nte, lambda row: row["date"])
        silver = await silverpalace.snapshot(fetcher)
        report("silver-listings", silver, lambda row: row["date"])
        game = Game(key="endfield", name="Arknights: Endfield", short="Endfield", enabled=False, color=0)
        end = await endfield.discover_news(fetcher, game, 0)
        report("endfield-listings", end, lambda row: datetime.fromtimestamp(row["ts"], UTC).date().isoformat())


class Tests(unittest.TestCase):
    def test_pagination_is_exact_and_bounded(self):
        page = '<ul class="pagination"><li><a href="#">1</a></li><li><a href="index1.html">2</a></li></ul>'
        self.assertEqual(nte_pages(page), 2)
        for bad in (None, "", page.replace("index1.html", "https://evil.invalid/index1.html"),
                    page.replace(">2<", ">3<"), page.replace("index1.html", "index2.html"),
                    page + page, page.replace("</ul>", ""), "x" * (1024 * 1024 + 1)):
            with self.subTest(value=str(bad)[:100]):
                self.assertIsNone(nte_pages(bad))
        for bad in (-1, 100, True, "1"):
            with self.assertRaises(ValueError):
                nte_url(bad)

    def test_complete_walk_and_drift_rejection(self):
        def listing(cid, day):
            return ('<div class="listNews"><a href="/en/article/news/gamenews/20260101/' + cid + '.html">'
                    '<h2 class="title">Title</h2><p class="date">' + day + '</p></a></div>')
        pager = '<ul class="pagination"><li><a href="#">1</a></li><li><a href="index1.html">2</a></li></ul>'
        first = listing("1", "2026-01-02") + pager
        last = listing("2", "2026-01-01")

        class FetcherFake:
            def __init__(self, final=first):
                self.final, self.count = final, 0

            async def get_text(self, url, **kwargs):
                if url == nte_url(0):
                    self.count += 1
                    return first if self.count == 1 else self.final
                return last

        self.assertEqual(len(asyncio.run(nte_walk(FetcherFake()))), 2)
        self.assertIsNone(asyncio.run(nte_walk(FetcherFake(final=first.replace("Title", "Changed")))))
        self.assertIsNone(asyncio.run(nte_walk(FetcherFake(final=None))))


if __name__ == "__main__":
    if sys.argv[1:] == ["--self-test"]:
        unittest.main(argv=[sys.argv[0]])
    elif sys.argv[1:]:
        raise SystemExit("Usage: archive_research_probe.py [--self-test]")
    else:
        asyncio.run(run())
