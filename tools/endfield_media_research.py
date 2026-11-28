"""Read-only, bounded Endfield article-detail media inventory.

Only counts and validated fixed-host article links are emitted. No response bodies,
media files, credentials, Discord messages, state or artifacts are saved or sent.
"""
from __future__ import annotations

import asyncio
import sys
import unittest
from datetime import UTC, datetime
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import aiohttp  # noqa: E402
from live_candidate_probe import NoRedirectSession  # noqa: E402
from nte_media_research import media_type  # noqa: E402

from gamexpress.config import Game  # noqa: E402
from gamexpress.http import Fetcher  # noqa: E402
from gamexpress.sources import endfield  # noqa: E402

MAX_ARTICLES = endfield.MAX_PAGES * endfield.PAGE_SIZE


class Fragment(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.suppressed = 0
        self.images = self.gif = self.video = self.youtube = 0

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
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
                self.video += 1

    def handle_endtag(self, tag):
        if tag in ("script", "style") and self.suppressed:
            self.suppressed -= 1


def valid_row(row):
    return (isinstance(row, dict) and isinstance(row.get("id"), str)
            and bool(endfield._ID.fullmatch(row["id"]))
            and type(row.get("ts")) is int and 0 < row["ts"] < 253402300800
            and isinstance(row.get("title"), str) and bool(row["title"].strip()))


def inspect(row, response):
    if not valid_row(row):
        return None
    data = endfield._envelope(response)
    if (data is None or data.get("cid") != row["id"] or type(data.get("displayTime")) is not int
            or data["displayTime"] != row["ts"] or not isinstance(data.get("title"), str)
            or data["title"].strip() != row["title"].strip()):
        return None
    content = data.get("data")
    if not isinstance(content, str) or not content.strip() or len(content) > 2 * 1024 * 1024:
        return None
    parser = Fragment()
    try:
        parser.feed(content)
        parser.close()
    except (ValueError, RecursionError):
        return None
    if parser.suppressed:
        return None
    return {"images": parser.images, "gif": parser.gif, "video": parser.video,
            "youtube": parser.youtube, "cover": int(bool(data.get("cover")))}


async def audit(fetcher, rows):
    if (not isinstance(rows, list) or not 0 < len(rows) <= MAX_ARTICLES
            or any(not valid_row(r) for r in rows) or len({r["id"] for r in rows}) != len(rows)):
        return None
    results = []
    for i in range(0, len(rows), 2):
        batch = rows[i:i + 2]
        await asyncio.sleep(0.25)
        details = await asyncio.gather(*(fetcher.get_json(endfield.BASE + "/" + row["id"],
                                                         source="research-endfield-media", retries=0,
                                                         timeout=15, params=endfield.PARAMS)
                                         for row in batch))
        results.extend({**row, "media": inspect(row, response)} for row, response in zip(batch, details))
        health = getattr(fetcher, "health", {}).get("research-endfield-media")
        if health and "HTTP 429" in health.last_error:
            break
    return results


def choose_examples(results):
    ok = [r for r in results if valid_row(r) and r.get("media") is not None]
    examples = []
    for category in ("youtube", "video", "gif", "images", "cover"):
        matching = sorted((r for r in ok if r["media"][category]), key=lambda r: (r["ts"], r["id"]))
        if matching:
            examples.append((category + "-oldest", matching[0]))
            if matching[-1]["id"] != matching[0]["id"]:
                examples.append((category + "-latest", matching[-1]))
            if category == "images":
                examples.append(("images-most", max(matching, key=lambda r: (r["media"]["images"], r["ts"], r["id"]))))
    return examples


def emit(rows, results):
    if results is None:
        print("::notice title=Endfield media inventory::endfield-audit status=unavailable")
        return
    good = [r for r in results if r["media"] is not None]
    counts = {key: sum(bool(r["media"][key]) for r in good)
              for key in ("images", "gif", "video", "youtube", "cover")}
    print("::notice title=Endfield media inventory::"
          f"endfield-audit listed={len(rows)} attempted={len(results)} parsed={len(good)} "
          f"failed={len(results) - len(good)} unexamined={len(rows) - len(results)} "
          + " ".join(f"{key}-articles={value}" for key, value in counts.items()))
    for label, row in choose_examples(results):
        m = row["media"]
        day = datetime.fromtimestamp(row["ts"], UTC).date().isoformat()
        print("::notice title=Endfield media example::"
              f"{label} utc-day={day} images={m['images']} gif={m['gif']} video={m['video']} "
              f"youtube={m['youtube']} cover={m['cover']} article={endfield.ARTICLE.format(row['id'])}")


async def run():
    async with aiohttp.ClientSession(trust_env=False) as session:
        fetcher = Fetcher(NoRedirectSession(session))
        game = Game(key="endfield", name="Arknights: Endfield", short="Endfield", enabled=False, color=0)
        rows = await endfield.discover_news(fetcher, game, 0)
        confirm = await endfield.discover_news(fetcher, game, 0)
        if rows is None or confirm != rows:
            print("::notice title=Endfield listing consistency::endfield-snapshot status=unavailable-or-drift")
            emit(rows, None)
            return
        results = await audit(fetcher, rows)
        after = await endfield.discover_news(fetcher, game, 0)
        print("::notice title=Endfield listing consistency::endfield-snapshot status="
              + ("matching-before-after" if after == rows else "unavailable-or-drift-after"))
        emit(rows, results)


class Tests(unittest.TestCase):
    def test_detail_checks_identity_and_media_in_order_independent_counts(self):
        row = {"id": "0740", "ts": 300, "title": "Official"}
        data = {"cid": "0740", "displayTime": 300, "title": "Official", "cover": "present",
                "data": '<img src="https://x/a.gif"><iframe src="https://youtube.com/embed/tdZN6H1N3PU"></iframe>'
                        '<video src="https://x/a.mp4"></video><script><img src="/bad.gif"></script>'}
        response = {"code": 0, "data": data}
        self.assertEqual(inspect(row, response), {"images": 1, "gif": 1, "video": 1, "youtube": 1, "cover": 1})
        for changed in ({"cid": "740"}, {"displayTime": 301}, {"title": "Different"}, {"data": ""}):
            with self.subTest(changed=changed):
                self.assertIsNone(inspect(row, {"code": 0, "data": {**data, **changed}}))
        self.assertIsNone(inspect({**row, "id": "../1"}, response))

    def test_rate_limit_stops_and_fixed_urls(self):
        from types import SimpleNamespace

        class Fake:
            def __init__(self):
                self.calls = []
                self.health = {"research-endfield-media": SimpleNamespace(last_error="HTTP 429")}

            async def get_json(self, url, **kwargs):
                self.calls.append((url, kwargs))
                return None

        rows = [{"id": str(i), "ts": 300, "title": "x"} for i in range(4)]
        fake = Fake()
        self.assertEqual(len(asyncio.run(audit(fake, rows))), 2)
        self.assertEqual(len(fake.calls), 2)
        self.assertTrue(all(call[0].startswith(endfield.BASE + "/") and call[1]["retries"] == 0
                            for call in fake.calls))
        self.assertIsNone(asyncio.run(audit(fake, [{**rows[0], "id": "../../x"}])))

    def test_select_oldest_latest_and_max(self):
        media = {"images": 2, "gif": 0, "video": 0, "youtube": 1, "cover": 1}
        rows = [{"id": "001", "ts": 300, "title": "x", "media": media}]
        self.assertEqual([label for label, _ in choose_examples(rows)],
                         ["youtube-oldest", "images-oldest", "images-most", "cover-oldest"])


if __name__ == "__main__":
    if sys.argv[1:] == ["--self-test"]:
        unittest.main(argv=[sys.argv[0]])
    elif sys.argv[1:]:
        raise SystemExit("Usage: endfield_media_research.py [--self-test]")
    else:
        asyncio.run(run())
