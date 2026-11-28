"""Read-only check of all observed NTE account-notice table rows."""
from __future__ import annotations

import asyncio
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import aiohttp  # noqa: E402
from live_candidate_probe import NoRedirectSession  # noqa: E402

from gamexpress.candidate_news_delivery import discover  # noqa: E402
from gamexpress.http import Fetcher  # noqa: E402
from gamexpress.sources.nte_candidate import _body  # noqa: E402


async def main():
    async with aiohttp.ClientSession(trust_env=False) as session:
        fetcher = Fetcher(NoRedirectSession(session))
        rows = await discover(fetcher, "nte")
        if not rows:
            raise ValueError("NTE listing unavailable")
        matches = [r for r in rows if "account action notice" in r["title"].lower()]
        print(f"::notice title=NTE account notice inventory::listed={len(rows)} matching-notices={len(matches)} "
              f"article-ids={','.join(r['id'] for r in matches)}", flush=True)
        for row in matches:
            raw = await fetcher.get_text(row["url"], source="nte-table-audit", retries=1, allow_redirects=False)
            blocks = _body(raw)
            if blocks is None:
                raise ValueError("notice unavailable")
            original = re.findall(r"\d{4}\*{4}\d{4}", raw)
            text = "\n".join(b.get("text", "") for b in blocks).replace(r"\*", "*")
            rendered = re.findall(r"\d{4}\*{4}\d{4}", text)
            glued = bool(re.search(r"\d{4}\*{4}\d{4}\d{4}\*{4}\d{4}", text))
            if original != rendered or glued:
                raise ValueError("notice table mismatch")
            print(f"::notice title=NTE account notice::{row['id']} ids={len(original)} same-order=1 joined-ids=0", flush=True)
        print(f"::notice title=NTE account notice audit::listed={len(rows)} matching-notices={len(matches)} "
              f"article-ids={','.join(r['id'] for r in matches)}", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
