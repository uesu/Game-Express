"""Read-only, bounded inspection of public SKPORT pages and their script references.

No login, tokens, writes, dynamic code execution, arbitrary links, or endpoint calls.
A discovered string is not evidence that it is a supported or accessible API.
"""
from __future__ import annotations

import asyncio
import re
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlsplit

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import aiohttp  # noqa: E402
from live_candidate_probe import NoRedirectSession  # noqa: E402

from gamexpress.http import Fetcher  # noqa: E402

PAGES = ("https://www.skport.com/", "https://www.skport.com/game/endfield",
         "https://www.skport.com/game/endfield?cateId=1001")


class Scripts(HTMLParser):
    def __init__(self):
        super().__init__()
        self.urls = []

    def handle_starttag(self, tag, attrs):
        src = dict(attrs).get("src")
        if tag == "script" and src:
            u = urljoin(PAGES[0], src)
            p = urlsplit(u)
            if p.scheme == "https" and p.hostname in ("www.skport.com", "static.skport.com") and not p.username and not p.password and p.port in (None, 443) and not p.query and not p.fragment:
                self.urls.append(u)


async def main():
    async with aiohttp.ClientSession(trust_env=False) as session:
        fetcher = Fetcher(NoRedirectSession(session))
        scripts, chunks = set(), []
        for page in PAGES:
            html = await fetcher.get_text(page, source="skport-public", retries=0, allow_redirects=False)
            if not html:
                print("::notice title=SKPORT research::public-page=unavailable", flush=True)
                continue
            parser = Scripts()
            parser.feed(html)
            scripts.update(parser.urls)
            chunks.append(html)
            print(f"::notice title=SKPORT research::public-page=available bytes={len(html)} "
                  f"scripts={len(parser.urls)}", flush=True)
        chosen = sorted(scripts)[:12]
        for url in chosen:
            js = await fetcher.get_text(url, source="skport-public-js", retries=0, allow_redirects=False)
            if js:
                chunks.append(js)
        text = "\n".join(chunks)
        paths = sorted(set(re.findall(r"/(?:api|web)/v[0-9]+/[A-Za-z0-9_/-]{3,100}", text)))
        print(f"::notice title=SKPORT research::scripts-found={len(scripts)} inspected={len(chunks)-len(PAGES)} "
              f"api-path-strings={len(paths)} truncated={int(len(scripts)>len(chosen))}", flush=True)
        for path in paths[:30]:
            print(f"::notice title=SKPORT static path hint::{path}", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
