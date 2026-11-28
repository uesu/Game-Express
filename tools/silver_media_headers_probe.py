"""Read-only bounded headers/magic probe of the two user-reported Silver articles."""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import aiohttp  # noqa: E402
from live_candidate_probe import NoRedirectSession  # noqa: E402

from gamexpress import candidate_news_delivery as delivery  # noqa: E402
from gamexpress.http import Fetcher  # noqa: E402
from gamexpress.sources import silverpalace  # noqa: E402


async def main():
    async with aiohttp.ClientSession(trust_env=False) as session:
        fetcher = Fetcher(NoRedirectSession(session))
        rows = await delivery.discover(fetcher, "silverpalace")
        chosen = [row for row in rows if row["id"] in ("93", "99")]
        if {row["id"] for row in chosen} != {"93", "99"}:
            raise ValueError("missing article")
        for row in chosen:
            item = await silverpalace.news_article(fetcher, delivery.candidate_game("silverpalace"), row)
            if item is None:
                raise ValueError("missing detail")
            urls = [block["url"] for block in item.article_blocks if block.get("kind") == "image"]
            for idx, url in enumerate(urls):
                if not silverpalace._official_cover(url):
                    raise ValueError("unexpected image origin")
                async with session.get(url, allow_redirects=False, timeout=aiohttp.ClientTimeout(total=20)) as response:
                    if response.status != 200:
                        raise ValueError("media unavailable")
                    prefix = await response.content.read(16)
                    mime = response.headers.get("Content-Type", "").split(";")[0].lower()
                    length = response.headers.get("Content-Length", "unknown")
                    if not (length == "unknown" or length.isdigit()) or mime not in ("image/gif", "image/jpeg", "application/octet-stream"):
                        raise ValueError("unexpected headers")
                    magic = "gif" if prefix.startswith((b"GIF87a", b"GIF89a")) else "other"
                    print(f"::notice title=Silver animation source::{row['id']} index={idx} "
                          f"magic={magic} mime={mime} bytes={length}", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
