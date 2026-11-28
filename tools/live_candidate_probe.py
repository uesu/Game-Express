"""Read-only, fixed-target runner research. Never sends webhooks or writes state.

The Reddit tests call the existing listing adapter directly without Devvit or credentials.
Results are structural counts, not source content, health guarantees or activation approval.
"""
from __future__ import annotations

import asyncio
import contextlib
import io
import re
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import aiohttp  # noqa: E402

from gamexpress.cards import news_payloads, validate_payload  # noqa: E402
from gamexpress.config import Game, load_settings  # noqa: E402
from gamexpress.discord import payload_media_urls  # noqa: E402
from gamexpress.http import Fetcher  # noqa: E402
from gamexpress.media import news_media_available  # noqa: E402
from gamexpress.sources import endfield, nte_candidate, reddit, silverpalace  # noqa: E402

SUBS = ("Endfield", "ArknightsEndfield", "NevernessToEverness", "SilverPalaceOfficial")
ORIGINS = ("https://old.reddit.com", "https://redlib.mint.lgbt", "https://r.naa.gg")
FLEET = ("https://redlib.mint.lgbt", "https://reddit.idevicehacked.com",
         "https://redlib.reallyaweso.me", "https://r.naa.gg",
         "https://redlib.thepixora.com", "https://redlib.r4fo.com")


def format_result(name: str, status: str, count: int = 0) -> str:
    """Reject upstream-controlled text so annotations cannot contain content or directives."""
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", name):
        raise ValueError("invalid label")
    if status not in {"ok", "empty", "unavailable", "rejected", "invalid", "unreadable", "network-error"} and not re.fullmatch(r"http-[1-5][0-9]{2}", status):
        raise ValueError("invalid status")
    if type(count) is not int or not 0 <= count <= 100000:
        raise ValueError("invalid count")
    return f"{name} status={status} count={count}"


def show(name: str, status: str, count: int, annotations: bool) -> None:
    line = format_result(name, status, count)
    print(f"::notice title=Candidate probe::{line}" if annotations else line)


class NoRedirectSession:
    """Keep runner reconnaissance on its fixed hosts; production follows redirects."""
    def __init__(self, session):
        self.session = session

    def get(self, url, **kwargs):
        kwargs["allow_redirects"] = False
        return self.session.get(url, **kwargs)


async def probe(fetcher, *, annotations: bool = False, group: str = "all") -> None:
    if group in ("all", "endfield"):
        await probe_endfield(fetcher, annotations=annotations)
    if group in ("all", "reddit0", "reddit1", "reddit2"):
        await probe_reddit(fetcher, annotations=annotations, group=group)
    if group == "nte":
        for page, url in enumerate(("https://nte.perfectworld.com/en/article/news/index.html",
                                    "https://nte.perfectworld.com/en/article/news/index1.html"), 1):
            text = await fetcher.get_text(url, source="research-nte", retries=1)
            rows = nte_candidate.parse_list_page(text)
            show(f"nte-page-{page}", "unavailable" if rows is None else "ok", len(rows or []), annotations)
            if page == 1 and rows is not None:
                match = next((row for row in rows if row["id"] == "265053"), None)
                show("nte-265053-displayed-day", "ok" if match and match["date"] == "2026-11-20" else "unavailable",
                     int(bool(match)), annotations)
    if group == "silver":
        rows = await silverpalace.snapshot(fetcher)
        show("silver-snapshot", "unavailable" if rows is None else "ok" if rows else "empty",
             len(rows or []), annotations)
        selected = next((row for row in rows or [] if row["id"] == "120"), None)
        if selected:
            item = await silverpalace.detail(fetcher, selected)
            show("silver-detail-120", "ok" if item else "unavailable",
                 len(item["blocks"]) if item else 0, annotations)
        else:
            show("silver-detail-120", "unavailable", 0, annotations)
    if group == "redditfleet":
        await probe_reddit_fleet(fetcher, annotations=annotations)


async def probe_endfield(fetcher, *, annotations: bool) -> None:
    game = Game(key="endfield", name="Arknights: Endfield", short="Endfield", enabled=False, color=0)
    rows = await endfield.discover_news(fetcher, game, 0)
    show("endfield-list", "unavailable" if rows is None else "ok" if rows else "empty",
         len(rows or []), annotations)
    selected = next((row for row in rows or [] if row["id"] == "0740"), None)
    if selected:
        item = await endfield.news_article(fetcher, game, selected)
        show("endfield-detail", "ok" if item else "unavailable", len(item.article_blocks) if item else 0, annotations)
        if item:
            try:
                payloads = news_payloads(game, item)
                errors = sum(len(validate_payload(payload)) for payload in payloads)
                show("endfield-card", "invalid" if errors else "ok", len(payloads), annotations)
                available = await news_media_available(fetcher, payloads)
                urls = set().union(*(payload_media_urls(payload) for payload in payloads))
                show("endfield-card-media-preflight", "ok" if available else "rejected", len(urls), annotations)
            except (TypeError, ValueError, KeyError, AttributeError):
                show("endfield-card", "invalid", 0, annotations)


async def probe_reddit(fetcher, *, annotations: bool, group: str) -> None:
    client = reddit.RedditClient(fetcher, load_settings({}))
    for idx, origin in enumerate(ORIGINS):
        if group != "all" and group != f"reddit{idx}":
            continue
        for sub in SUBS:
            health = getattr(fetcher, "health", {}).get("reddit")
            previous_failures = health.fail if health else 0
            rows = await client._fetch_listing_on(origin, "sub", sub)
            health = getattr(fetcher, "health", {}).get("reddit")
            if rows is None and health and health.fail > previous_failures:
                match = re.match(r"HTTP ([1-5][0-9]{2})(?:$| )", health.last_error)
                status = f"http-{match[1]}" if match else "network-error"
            else:
                status = "unreadable" if rows is None else "ok" if rows else "empty"
            show(f"reddit-{idx}-{sub}", status, len(rows or []), annotations)


async def probe_reddit_fleet(fetcher, *, annotations: bool) -> None:
    settings = load_settings({"INTAKE_READER": "off", "REDDIT_INSTANCES": ",".join(FLEET)})
    client = reddit.RedditClient(fetcher, settings)
    results = await asyncio.gather(*(client.subreddit(sub) for sub in SUBS))
    for sub, rows in zip(SUBS, results):
        status = "unavailable" if rows is None else "ok" if rows else "empty"
        show(f"reddit-fleet-{sub}", status, len(rows or []), annotations)


class Tests(unittest.TestCase):
    def test_workflow_keeps_target_checks_and_excludes_unrelated_crimson(self):
        workflow = (ROOT / ".github/workflows/source_research_probe.yml").read_text(encoding="utf-8")
        self.assertNotIn("--group crimson", workflow)
        self.assertNotIn("continue-on-error", workflow)
        for group in ("endfield-nte", "silver", "media", "codes"):
            self.assertIn(f"tools/source_research_probe.py --group {group} --annotations", workflow)
        for group in ("nte", "silver", "endfield", "reddit0", "reddit1", "reddit2", "redditfleet"):
            self.assertIn(f"tools/live_candidate_probe.py --group {group} --annotations", workflow)

    def test_annotation_content_is_restricted(self):
        self.assertEqual(format_result("reddit-0-Endfield", "ok", 2), "reddit-0-Endfield status=ok count=2")
        for args in (("unsafe\n::error::", "ok", 1), ("safe", "external text", 1),
                     ("safe", "ok", True), ("safe", "ok", 100001)):
            with self.assertRaises(ValueError):
                format_result(*args)

    def test_complete_probe_uses_existing_readers_without_emitting_source_content(self):
        class FakeFetcher:
            async def get_json(self, url, **kwargs):
                if url == endfield.BASE:
                    return {"code": 0, "data": {"current": 1, "pageSize": 20, "total": 1,
                            "list": [{"cid": "0740", "title": "secret title", "displayTime": 300}]}}
                return {"code": 0, "data": {"cid": "0740", "displayTime": 300,
                        "title": "secret title", "data": "<p>secret body</p>",
                        "cover": "https://web-static.hg-cdn.com/image.jpg"}}

            async def verify_media(self, url):
                return False

        class FakeReddit:
            calls = []

            def __init__(self, fetcher, settings):
                pass

            async def _fetch_listing_on(self, origin, kind, target):
                self.calls.append((origin, kind, target))
                return None if target == "Endfield" else [{"title": "never emit this"}]

        output = io.StringIO()
        with patch.object(reddit, "RedditClient", FakeReddit), contextlib.redirect_stdout(output):
            asyncio.run(probe(FakeFetcher(), annotations=True))
        text = output.getvalue()
        self.assertIn("endfield-list status=ok count=1", text)
        self.assertIn("endfield-card-media-preflight status=rejected count=1", text)
        self.assertIn("reddit-0-Endfield status=unreadable count=0", text)
        self.assertEqual(len(FakeReddit.calls), 12)
        self.assertNotIn("secret", text)
        self.assertNotIn("never emit", text)

    def test_nte_group_reports_only_fixed_structure(self):
        class FakeFetcher:
            async def get_text(self, url, **kwargs):
                return ('<div class="listNews"><a href="/en/article/news/gamebroad/20261113/265053.html">'
                        '<h2 class="title">secret title</h2><p class="date">2026-11-20</p></a></div>')

        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            asyncio.run(probe(FakeFetcher(), annotations=True, group="nte"))
        self.assertIn("nte-page-1 status=ok count=1", output.getvalue())
        self.assertIn("nte-265053-displayed-day status=ok count=1", output.getvalue())
        self.assertIn("nte-page-2 status=ok count=1", output.getvalue())
        self.assertNotIn("secret title", output.getvalue())

    def test_silver_group_scans_twice_without_printing_article_content(self):
        class FakeFetcher:
            calls = 0

            async def get_json(self, url, **kwargs):
                self.calls += 1
                if url == silverpalace.DETAIL:
                    return {"code": 0, "data": {"id": "120", "title": "never emit this title",
                            "publish_date": "2026-10-09", "cover": "https://s.elementagames.com/a.jpg",
                            "content": "<p>never emit article content</p>"}}
                return {"code": 0, "data": {"current_page": "1", "total_page": 1,
                        "list": [{"id": "120", "title": "never emit this title",
                                  "publish_date": "2026-10-09"}]}}

        fetcher = FakeFetcher()
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            asyncio.run(probe(fetcher, annotations=True, group="silver"))
        self.assertIn("silver-snapshot status=ok count=1", output.getvalue())
        self.assertIn("silver-detail-120 status=ok count=1", output.getvalue())
        self.assertNotIn("never emit", output.getvalue())
        self.assertEqual(fetcher.calls, 3)

    def test_redirect_override(self):
        class Fake:
            def get(self, url, **kwargs):
                return url, kwargs
        result = NoRedirectSession(Fake()).get("https://example.invalid", allow_redirects=True, timeout=1)
        self.assertEqual(result[1], {"allow_redirects": False, "timeout": 1})


async def main(annotations: bool, group: str = "all") -> None:
    async with aiohttp.ClientSession(trust_env=False) as session:
        await probe(Fetcher(NoRedirectSession(session)), annotations=annotations, group=group)


if __name__ == "__main__":
    if sys.argv[1:] == ["--self-test"]:
        unittest.main(argv=[sys.argv[0]])
    elif sys.argv[1:] in ([], ["--annotations"]):
        asyncio.run(main(bool(sys.argv[1:])))
    elif len(sys.argv) == 4 and sys.argv[1] == "--group" and sys.argv[3] == "--annotations":
        if sys.argv[2] not in ("endfield", "nte", "silver", "reddit0", "reddit1", "reddit2", "redditfleet"):
            raise SystemExit("Unknown fixed group")
        asyncio.run(main(True, sys.argv[2]))
    else:
        raise SystemExit("Usage: live_candidate_probe.py [--self-test | --annotations | --group NAME --annotations]")
