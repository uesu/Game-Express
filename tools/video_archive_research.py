"""Static article-body video research for the three candidate news archives.

Fixed official listing/detail requests only; never fetches linked media, executes JS,
posts messages, prints article bodies/media URLs, or reads credentials/writes state.
Extension and player markers are hints, not proof of video or playability. Dynamic,
encoded, extensionless or otherwise unsupported media can still be missed.
"""
from __future__ import annotations

import asyncio
import html
import re
import sys
import unittest
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import aiohttp  # noqa: E402
from archive_research_probe import nte_snapshot  # noqa: E402
from feature3_webhook_test import Body  # noqa: E402
from live_candidate_probe import NoRedirectSession  # noqa: E402
from nte_media_research import inspect as inspect_nte  # noqa: E402
from nte_media_research import safe_row  # noqa: E402

from gamexpress.config import Game  # noqa: E402
from gamexpress.http import Fetcher  # noqa: E402
from gamexpress.sources import endfield, silverpalace  # noqa: E402

MAX_BODY = 2 * 1024 * 1024
EXTENSION = re.compile(r"\.(?:mp4|m4v|webm|mov|m3u8|mpd|ogv|avi|mkv|flv|wmv)(?=$|[?#&\s\"'<>\\])", re.I)
MIME = re.compile(r"(?:video/(?:mp4|webm|quicktime|ogg|x-msvideo|x-matroska|x-flv)|"
                  r"application/(?:vnd\.apple\.mpegurl|x-mpegurl|dash\+xml))", re.I)
YOUTUBE = re.compile(r"(?:youtube(?:-nocookie)?\.com|youtu\.be)", re.I)
PLAYER = re.compile(r"(?:vimeo\.com|bilibili\.com/video|player\.bilibili\.com|dailymotion\.com|"
                    r"streamable\.com|videojs|video\.js|jwplayer|hls\.js|dash\.js)", re.I)
KEYS = ("video_tag", "source_tag", "iframe", "object_embed", "video_attr", "extension_hint", "mime_hint", "youtube_hint", "player_hint")


class Tags(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.counts = {key: 0 for key in KEYS}

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if (any(re.match(r"data-(?:video|videourl)", name) for name in attributes)
                or (tag == "meta" and str(attributes.get("property", "")).lower().startswith("og:video"))):
            self.counts["video_attr"] += 1
        if tag == "video":
            self.counts["video_tag"] += 1
        elif tag == "source":
            self.counts["source_tag"] += 1
        elif tag == "iframe":
            self.counts["iframe"] += 1
        elif tag in ("object", "embed"):
            self.counts["object_embed"] += 1


def analyze(body):
    if not isinstance(body, str) or not body.strip() or len(body) > MAX_BODY:
        return None
    parser = Tags()
    try:
        parser.feed(body)
        parser.close()
    except (ValueError, RecursionError):
        return None
    # Inspect literal markup, text and script contents, including common JSON/HTML
    # URL escaping. This does not execute scripts or decode arbitrary data.
    normalized = html.unescape(body).replace(r"\/", "/")
    normalized = re.sub(r"\\u00(2e|2f|3a|26|3d|3f|23)", lambda m: chr(int(m[1], 16)), normalized, flags=re.I)
    normalized = unquote(normalized)
    counts = parser.counts
    for key, regex in (("extension_hint", EXTENSION), ("mime_hint", MIME),
                       ("youtube_hint", YOUTUBE), ("player_hint", PLAYER)):
        counts[key] = len(regex.findall(normalized))
    return counts


async def listings(fetcher, game_name):
    if game_name == "nte":
        rows = await nte_snapshot(fetcher)
        if (not isinstance(rows, list) or not 0 < len(rows) <= 200
                or any(not safe_row(row) for row in rows) or len({r["id"] for r in rows}) != len(rows)):
            return None
        return sorted(rows, key=lambda row: (row["date"], row["id"]))
    if game_name == "endfield":
        game = Game(key="endfield", name="Endfield", short="Endfield", enabled=False, color=0)
        rows = await endfield.discover_news(fetcher, game, 0)
        again = await endfield.discover_news(fetcher, game, 0)
        if not rows or rows != again or len(rows) > endfield.MAX_PAGES * endfield.PAGE_SIZE:
            return None
        return rows
    rows = await silverpalace.snapshot(fetcher)
    if not rows or len(rows) > silverpalace.MAX_PAGES * silverpalace.MAX_ROWS_PER_PAGE:
        return None
    return sorted(rows, key=lambda row: (row["date"], row["id"]))


async def get_body(fetcher, game_name, row):
    if game_name == "nte":
        if not safe_row(row):
            return None
        document = await fetcher.get_text(row["url"], source="video-audit-nte", retries=0, timeout=15)
        if inspect_nte(document) is None:
            return None
        parser = Body()
        parser.feed(document)
        parser.close()
        return "".join(parser.parts)
    if game_name == "endfield":
        cid = row.get("id")
        if not isinstance(cid, str) or not endfield._ID.fullmatch(cid):
            return None
        response = await fetcher.get_json(endfield.BASE + "/" + cid, source="video-audit-endfield",
                                          params=endfield.PARAMS, retries=0, timeout=15)
        data = endfield._envelope(response)
        if (data is None or data.get("cid") != cid or type(data.get("displayTime")) is not int
                or data.get("displayTime") != row.get("ts") or not isinstance(data.get("title"), str)
                or data["title"].strip() != row.get("title")):
            return None
        return data.get("data")
    cid = row.get("id")
    if not isinstance(cid, str) or not silverpalace._ID.fullmatch(cid):
        return None
    response = await fetcher.get_json(silverpalace.DETAIL, source="video-audit-silver",
                                      params={"lang": "en-us", "id": cid}, retries=0, timeout=15)
    if (not isinstance(response, dict) or type(response.get("code")) is not int or response["code"] != 0
            or not isinstance(response.get("data"), dict)):
        return None
    data = response["data"]
    if (data.get("id") != cid or data.get("publish_date") != row.get("date")
            or not isinstance(data.get("title"), str) or data["title"].strip() != row.get("title")):
        return None
    return data.get("content")


def article_url(game_name, row):
    if game_name == "nte":
        return row["url"] if safe_row(row) else None
    cid = row.get("id")
    if not isinstance(cid, str) or not re.fullmatch(r"[0-9]{1,32}", cid):
        return None
    return (endfield.ARTICLE if game_name == "endfield" else silverpalace.ARTICLE).format(cid)


async def audit(fetcher, game_name, rows):
    results = []
    source = {"nte": "video-audit-nte", "endfield": "video-audit-endfield", "silver": "video-audit-silver"}[game_name]
    for i in range(0, len(rows), 2):
        batch = rows[i:i + 2]
        await asyncio.sleep(0.25)
        bodies = await asyncio.gather(*(get_body(fetcher, game_name, row) for row in batch))
        results.extend((row, analyze(body)) for row, body in zip(batch, bodies))
        health = getattr(fetcher, "health", {}).get(source)
        if health and "HTTP 429" in health.last_error:
            break
    return results


def emit(game_name, rows, results):
    valid = [(row, finding) for row, finding in results if finding is not None]
    print(f"::notice title=Video archive audit::{game_name} listed={len(rows)} attempted={len(results)} "
          f"parsed={len(valid)} failed={len(results) - len(valid)} unexamined={len(rows) - len(results)}")
    print(f"::notice title=Video archive markers::{game_name} "
          + " ".join(f"{key}={sum(bool(result[key]) for _, result in valid)}" for key in KEYS))
    for key in KEYS:
        found = [row for row, result in valid if result[key]]
        if found:
            print(f"::notice title=Video archive example::{game_name} marker={key} "
                  f"oldest={article_url(game_name, found[0])} newest={article_url(game_name, found[-1])}")


async def run(game_name):
    async with aiohttp.ClientSession(trust_env=False) as session:
        fetcher = Fetcher(NoRedirectSession(session))
        rows = await listings(fetcher, game_name)
        if rows is None:
            raise ValueError("listing incomplete, changed or unavailable")
        results = await audit(fetcher, game_name, rows)
        emit(game_name, rows, results)
        if len(results) != len(rows) or any(finding is None for _, finding in results):
            raise ValueError("archive audit incomplete")


class Tests(unittest.TestCase):
    def test_static_markers_and_escapes(self):
        body = ('<video><source src="https://example.org/a.mp4?x=1" type="video/mp4"></video>'
                '<iframe src="https://www.youtube.com/embed/abcdefghijk"></iframe>'
                '<script>const x="https:\\/\\/example.org\\/x\\u002em3u8"</script>'
                '<a href="https://example.org/clip.webm">link</a>')
        result = analyze(body)
        self.assertEqual(result["video_tag"], 1)
        self.assertEqual(result["source_tag"], 1)
        self.assertEqual(result["iframe"], 1)
        self.assertEqual(result["extension_hint"], 3)
        self.assertEqual(result["mime_hint"], 1)
        self.assertEqual(result["youtube_hint"], 1)
        self.assertEqual(analyze('<img src="photo.mp4.jpg">')["extension_hint"], 0)
        self.assertIsNone(analyze(None))

    def test_detail_matching_and_no_untrusted_targets(self):
        class Fake:
            def __init__(self):
                self.calls = []

            async def get_json(self, url, **kwargs):
                self.calls.append((url, kwargs))
                return {"code": 0, "data": {"id": "01", "title": "Test", "publish_date": "2025-01-02",
                                            "content": '<video src="x.webm"></video>'}}

        fake = Fake()
        row = {"id": "01", "date": "2025-01-02", "title": "Test"}
        body = asyncio.run(get_body(fake, "silver", row))
        self.assertEqual(analyze(body)["video_tag"], 1)
        self.assertEqual(fake.calls[0][0], silverpalace.DETAIL)
        self.assertIsNone(asyncio.run(get_body(fake, "silver", {**row, "id": "../../x"})))
        self.assertIsNone(asyncio.run(get_body(fake, "silver", {**row, "title": "Different"})))
        self.assertEqual(len(fake.calls), 2)

    def test_fixed_article_url_and_invalid_rows(self):
        self.assertIsNone(article_url("endfield", {"id": "../2"}))
        self.assertEqual(article_url("endfield", {"id": "0740"}), endfield.ARTICLE.format("0740"))


if __name__ == "__main__":
    if sys.argv[1:] == ["--self-test"]:
        unittest.main(argv=[sys.argv[0]])
    elif len(sys.argv) == 2 and sys.argv[1] in ("nte", "endfield", "silver"):
        asyncio.run(run(sys.argv[1]))
    else:
        raise SystemExit("Usage: video_archive_research.py [nte|endfield|silver|--self-test]")
