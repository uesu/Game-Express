"""Read-only, fixed-article Endfield reader/card structural checks.

Up to three observed fixed-CDN media URLs are preflighted, but no source text,
media URL, payload, state, or Discord send is emitted. The results do not establish
Discord delivery, complete media availability or animation.
"""
from __future__ import annotations

import asyncio
import sys
import unittest
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import aiohttp  # noqa: E402
from live_candidate_probe import NoRedirectSession  # noqa: E402

from gamexpress.cards import _youtube_watch_url, news_payloads, text_length, validate_payload  # noqa: E402
from gamexpress.config import Game  # noqa: E402
from gamexpress.http import Fetcher  # noqa: E402
from gamexpress.models import Item  # noqa: E402
from gamexpress.sources import endfield  # noqa: E402

IDS = ("0766", "1340", "7011", "3840")


def summarize(game, item, expand_full):
    """Return numeric/boolean metrics only; payloads and upstream text stay private."""
    blocks = item.article_blocks
    pages = news_payloads(game, item, expand_full=expand_full)
    components = [c for page in pages for container in page["components"]
                  for c in container.get("components", [])]
    texts = [c.get("content", "") for c in components if c["type"] == 10]
    media = [i["media"]["url"] for c in components if c["type"] == 12 for i in c["items"]]
    body = [b["url"] for b in blocks if b["kind"] == "image"]
    youtube = [_youtube_watch_url(b.get("url", "")) for b in blocks if b["kind"] == "link"]
    youtube = [u for u in youtube if u]
    return {"body_images": len(body), "body_gifs": sum(u.split("?", 1)[0].lower().endswith(".gif") for u in body),
            "youtube": len(youtube), "youtube_inline": sum(u in texts for u in youtube),
            "pages": len(pages), "media": len(media),
            "body_images_present": sum(u in media for u in body),
            "excerpt": int(any("**Excerpt" in t for t in texts)),
            "valid": int(all(not validate_payload(page) for page in pages))}


async def preflight_samples(fetcher, item):
    """At most one fixed-host body image per observed suffix; never emit upstream URLs."""
    samples = {}
    for block in item.article_blocks:
        if block.get("kind") != "image":
            continue
        url = block.get("url", "")
        try:
            parts = urlsplit(url)
            if (parts.scheme != "https" or parts.hostname != "web-static.hg-cdn.com"
                    or parts.username or parts.password or parts.port not in (None, 443)):
                continue
        except ValueError:
            continue
        extension = parts.path.rsplit(".", 1)[-1].lower()
        if extension in ("jpg", "png", "gif") and extension not in samples:
            samples[extension] = url
    return {ext: int(await fetcher.verify_media(samples[ext])) for ext in sorted(samples)}


async def run():
    async with aiohttp.ClientSession(trust_env=False) as session:
        fetcher = Fetcher(NoRedirectSession(session))
        game = Game(key="endfield", name="Arknights: Endfield", short="Endfield", enabled=False, color=0)
        rows = await endfield.discover_news(fetcher, game, 0)
        for cid in IDS:
            row = next((r for r in rows or [] if r["id"] == cid), None)
            item = await endfield.news_article(fetcher, game, row) if row else None
            if not item:
                print(f"::notice title=Endfield reader card::id={cid} status=unavailable")
                continue
            for mode in (False, True):
                try:
                    result = summarize(game, item, mode)
                    metrics = " ".join(f"{k}={v}" for k, v in result.items())
                    print(f"::notice title=Endfield reader card::id={cid} expanded={int(mode)} {metrics}")
                except (KeyError, TypeError, ValueError, AttributeError):
                    print(f"::notice title=Endfield reader card::id={cid} expanded={int(mode)} status=invalid")
            if cid == "1340":
                expanded = news_payloads(game, item, expand_full=True)
                article_chars = sum(len(b.get("text", "")) for b in item.article_blocks if b.get("kind") == "text")
                text_per_page = [text_length(page["components"]) for page in expanded]
                print("::notice title=Endfield 1340 character metrics::"
                      f"parsed-body-text-characters={article_chars} "
                      f"expanded-card-text-characters={sum(text_per_page)} "
                      f"expanded-page-text-characters={','.join(map(str, text_per_page))} "
                      "count=python-unicode-codepoints-including-formatting", flush=True)
            if cid == "7011":
                samples = await preflight_samples(fetcher, item)
                for ext in ("jpg", "png", "gif"):
                    print(f"::notice title=Endfield CDN preflight::format={ext} "
                          f"status={'pass' if samples.get(ext) == 1 else 'fail' if ext in samples else 'absent'}")


class Tests(unittest.TestCase):
    def test_preflight_only_known_exact_host_and_one_per_format(self):
        class Fake:
            def __init__(self):
                self.calls = []

            async def verify_media(self, url):
                self.calls.append(url)
                return True

        fake = Fake()
        urls = ["https://web-static.hg-cdn.com/a.gif", "https://web-static.hg-cdn.com/b.gif",
                "https://web-static.hg-cdn.com/a.png", "https://evil.example/a.jpg",
                "https://user@web-static.hg-cdn.com/a.jpg"]
        item = Item(source="endfield", game="endfield", id="1", url="", title="", text="", published_ts=0,
                    article_blocks=[{"kind": "image", "url": url} for url in urls])
        self.assertEqual(asyncio.run(preflight_samples(fake, item)), {"gif": 1, "png": 1})
        self.assertEqual(fake.calls, [urls[0], urls[2]])

    def test_metrics_for_embedded_trailer_and_mixed_media(self):
        from gamexpress.textutil import news_blocks

        game = Game(key="endfield", name="Endfield", short="Endfield", enabled=False, color=0)
        item = Item(source="endfield", game="endfield", id="1", url=endfield.ARTICLE.format("1"),
                    title="Example", text="", published_ts=0,
                    article_blocks=news_blocks('<p>Before</p><iframe src="https://www.youtube.com/embed/Yt7eUS1X0Ec">'
                                               '</iframe><img src="https://web-static.hg-cdn.com/example.gif">'
                                               '<img src="https://web-static.hg-cdn.com/example.png">'))
        result = summarize(game, item, False)
        self.assertEqual(result, {"body_images": 2, "body_gifs": 1, "youtube": 1, "youtube_inline": 1,
                                  "pages": 1, "media": 2, "body_images_present": 2, "excerpt": 0, "valid": 1})


if __name__ == "__main__":
    if sys.argv[1:] == ["--self-test"]:
        unittest.main(argv=[sys.argv[0]])
    elif sys.argv[1:]:
        raise SystemExit("Usage: endfield_card_research.py [--self-test]")
    else:
        asyncio.run(run())
