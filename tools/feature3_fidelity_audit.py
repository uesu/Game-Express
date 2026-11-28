"""Bounded, read-only official-news fidelity audit; never accesses webhooks or state."""
from __future__ import annotations

import asyncio
import re
import sys
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import aiohttp  # noqa: E402
from live_candidate_probe import NoRedirectSession  # noqa: E402

from gamexpress import candidate_news_delivery as delivery  # noqa: E402
from gamexpress.cards import _youtube_watch_url  # noqa: E402
from gamexpress.config import load_settings  # noqa: E402
from gamexpress.http import Fetcher  # noqa: E402
from gamexpress.sources import hoyolab, nte_candidate, silverpalace  # noqa: E402
from gamexpress.sources.candidate_thumbnail import with_verified_fallback  # noqa: E402


async def inspect_source(fetcher, source):
    rows = await delivery.discover(fetcher, source)
    if not rows or len(rows) > (200 if source == "nte" else 50):
        raise ValueError("snapshot unavailable or outside bound")
    module = nte_candidate if source == "nte" else silverpalace
    game = delivery.candidate_game(source)
    urls, items, failures = set(), {}, 0
    for start in range(0, len(rows), 2):
        batch = rows[start:start + 2]
        results = await asyncio.gather(*(module.news_article(fetcher, game, row) for row in batch))
        for row, item in zip(batch, results):
            if item is None:
                failures += 1
                continue
            items[row["id"]] = item
            for b in item.article_blocks:
                if b.get("kind") in ("image", "video"):
                    urls.add(b.get("url", ""))
        await asyncio.sleep(.15)
    if len(urls) > 350:
        raise ValueError("media bound exceeded")
    counts = {"gif": 0, "gif_jpg": 0, "video": 0, "other": 0, "unavailable": 0}
    for start in range(0, len(urls), 2):
        batch = sorted(urls)[start:start + 2]
        results = await asyncio.gather(*(fetcher._news_media_prefix(url) for url in batch))
        for url, result in zip(batch, results):
            if result is None:
                counts["unavailable"] += 1
            elif result[0].startswith((b"GIF87a", b"GIF89a")):
                counts["gif"] += 1
                counts["gif_jpg"] += int(urlsplit(url).path.lower().endswith((".jpg", ".jpeg")))
            elif result[0][4:8] == b"ftyp" or result[0].startswith(b"\x1aE\xdf\xa3"):
                counts["video"] += 1
            else:
                counts["other"] += 1
        await asyncio.sleep(.1)
    print(f"::notice title=Feature 3 media audit::{source} listed={len(rows)} parsed={len(items)} "
          f"detail-failures={failures} body-media={len(urls)} " + " ".join(f"{k}={v}" for k, v in counts.items()), flush=True)
    if failures or counts["unavailable"]:
        raise ValueError("incomplete media audit")
    if source == "silverpalace":
        for cid in ("93", "99"):
            item = items[cid]
            media = [b["url"] for b in item.article_blocks if b.get("kind") == "image"]
            signatures = [await fetcher._news_media_prefix(u) for u in media]
            gifs = sum(bool(x and x[0].startswith((b"GIF87a", b"GIF89a"))) for x in signatures)
            print(f"::notice title=Silver sample::{cid} media={len(media)} gif-signatures={gifs} state=unchanged", flush=True)
    else:
        for cid in ("262101", "262255", "262998"):
            row = next(r for r in rows if r["id"] == cid)
            pages = await delivery.render_candidate(fetcher, load_settings({"NEWS_EXPAND_MAX_PAGES": "120"}), source, row)
            texts = ["\n".join(c.get("content", "") for box in p["components"] for c in box.get("components", [])) for p in pages]
            if cid in ("262101", "262255"):
                raw = await fetcher.get_text(row["url"], source="fidelity-nte", retries=1, allow_redirects=False)
                source_ids = re.findall(r"\d{4}\*{4}\d{4}", raw or "")
                rendered = "\n".join(texts).replace(r"\*", "*")
                rendered_ids = re.findall(r"\d{4}\*{4}\d{4}", rendered)
                stuck = bool(re.search(r"\d{4}\*{4}\d{4}\d{4}\*{4}\d{4}", rendered))
                if not source_ids or source_ids != rendered_ids or stuck:
                    raise ValueError("account table rendering did not preserve rows")
                print(f"::notice title=NTE table sample::{cid} pages={len(pages)} masked-ids={len(source_ids)} "
                      "same-order=1 joined-ids=0", flush=True)
            else:
                locations = [i for i, text in enumerate(texts) if "**Important Notes**" in text]
                nexts = [i for i, text in enumerate(texts) if "Only one work link" in text]
                if not locations or not nexts or locations[0] != nexts[0]:
                    raise ValueError("heading separated from its first note")
                print(f"::notice title=NTE page sample::{cid} pages={len(pages)} heading-page={locations[0]+1} "
                      f"first-note-page={nexts[0]+1}", flush=True)


async def hoyo_sample(fetcher):
    from gamexpress.config import load_games
    game = load_games()["zzz"]
    full = await hoyolab._full_post(fetcher, game.hoyolab_gid, "47586861")
    if not full or not isinstance(full.get("post"), dict):
        print("::notice title=HoYoLAB thumbnail sample::source-unavailable=1", flush=True)
        return
    post = full["post"]
    row = {"id": "47586861", "ts": int(post["created_at"])}
    item = await hoyolab.news_article(fetcher, game, row)
    if not item:
        raise ValueError("HoYoLAB detail mismatch")
    improved = await with_verified_fallback(fetcher, item)
    native = bool(item.images or any(x.get("kind") == "image" or
                                     (x.get("kind") == "video" and not _youtube_watch_url(x.get("url", "")))
                                     for x in item.article_blocks))
    print(f"::notice title=HoYoLAB thumbnail sample::native={int(native)} fallback={int(improved is not item)} "
          "posted=0", flush=True)


async def main():
    async with aiohttp.ClientSession(trust_env=False) as session:
        fetcher = Fetcher(NoRedirectSession(session))
        if sys.argv[1:] != ["--hoyo-only"]:
            if sys.argv[1:]:
                raise ValueError("invalid audit mode")
            await inspect_source(fetcher, "nte")
            await inspect_source(fetcher, "silverpalace")
        await hoyo_sample(fetcher)


if __name__ == "__main__":
    asyncio.run(main())
