"""Read-only candidate source/payload checks. No state or Discord access."""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import aiohttp  # noqa: E402
from live_candidate_probe import NoRedirectSession  # noqa: E402

from gamexpress import candidate_news_delivery as candidate  # noqa: E402
from gamexpress.config import load_settings  # noqa: E402
from gamexpress.http import Fetcher  # noqa: E402

FIXED = {"nte": ("252469", "252474"), "endfield": ("0766", "7011"), "silverpalace": ("1", "7", "120")}


async def run():
    settings = load_settings({"NEWS_EXPAND_FULL": "1"})
    async with aiohttp.ClientSession(trust_env=False) as session:
        fetcher = Fetcher(NoRedirectSession(session))
        for source in ("nte", "endfield", "silverpalace"):
            rows = await candidate.discover(fetcher, source)
            if rows is None:
                raise ValueError(f"{source} snapshot unavailable")
            state = candidate.ingest(source, "a" * 16, None, rows)
            print(f"::notice title=Candidate snapshot::{source} complete={len(rows)} queued={len(state['pending'])} "
                  "persisted=0 posted=0", flush=True)
            for cid in FIXED[source]:
                row = next((r for r in rows if r["id"] == cid), None)
                if row is None:
                    raise ValueError(f"{source} example missing")
                pages = await candidate.render_candidate(fetcher, settings, source, row)
                children = [c for p in pages for card in p["components"] for c in card.get("components", [])]
                urls = [i["media"]["url"] for c in children if c.get("type") == 12 for i in c["items"]]
                maxres = sum(url.endswith("/maxresdefault.jpg") for url in urls)
                print(f"::notice title=Candidate card::{source} id={cid} pages={len(pages)} "
                      f"media={len(urls)} maxres={maxres} preflight=pass", flush=True)
                if source == "silverpalace" and cid == "7" and (len(urls) != 1 or not urls[0].endswith("/e4a8b3d37c628be4e73294c8469e73d6.jpg")):
                    raise ValueError("duplicate cover/body image not removed")
                if source == "nte" and cid == "252469" and maxres != 1:
                    raise ValueError("NTE maximum-resolution fallback missing")


if __name__ == "__main__":
    if sys.argv[1:]:
        raise SystemExit("Usage: candidate_pipeline_probe.py")
    try:
        asyncio.run(run())
    except (ValueError, TypeError, KeyError, AttributeError, RecursionError):
        raise SystemExit("Candidate pipeline probe stopped; no state or messages changed.") from None
