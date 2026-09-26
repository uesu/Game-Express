"""Official game news pages — the announcement's own link and its full-size key art.

Why this exists: the schedule card used to fall back to whatever the run happened to see. When
the only post in the lookback window was the *Update and Maintenance Notice*, the card's title
linked to that notice and showed the notice's cover (Pompom on HSR 4.6) instead of the Special
Program announcement and its art. These pages archive every announcement, so they can supply
the right link and the right picture even weeks later.

Verified 2026-09-25 (server-rendered, plain HTTP, no API key, no JS needed):
  https://hsr.hoyoverse.com/en-us/news             -> entries with a fastcdn cover + /news/<id>
  https://hsr.hoyoverse.com/en-us/news?type=notice -> the same shape for the Notices tab
  https://hsr.hoyoverse.com/en-us/news/166179      -> full-size cover AND the embedded
                                                      https://www.youtube.com/watch?v=ItNs39qvw_w
  https://genshin.hoyoverse.com/en/news            -> same template
  https://zenless.hoyoverse.com/en-us/news         -> same template
Kuro (Wuthering Waves) keeps its JSON article menus — see sources/kuro.py.

The page is parsed tolerantly (anchor blocks first, stripped text as a fallback) because the
template is a Next.js build and the markup around the entries is not a contract.
"""

from __future__ import annotations

import logging
import re
from html import unescape
from urllib.parse import urljoin

from ..config import Game
from ..media import upgrade, youtube_thumb
from ..textutil import find_version
from ..timeparse import find_datetimes

log = logging.getLogger("gamexpress.newspage")

# tab suffixes worth asking, in order. The Notices tab is where an official site files a
# program preview; the Latest tab is where the trailer (and its key art) lands.
TABS = ("?type=notice", "?type=news_all", "")

ANCHOR = re.compile(r'<a\b[^>]*href="(?P<href>[^"]*/news/(?:detail/)?(?P<id>\d{3,12}))"[^>]*>(?P<body>.*?)</a>',
                    re.I | re.S)
IMG = re.compile(r'(?:src|data-src|content)="(?P<u>https?://[^"\s>]+\.(?:jpg|jpeg|png|webp))"', re.I)
DATE = re.compile(r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b")
YOUTUBE = re.compile(r"(?:youtube\.com/watch\?v=|youtu\.be/)([A-Za-z0-9_-]{11})")
SCRIPT = re.compile(r"<(script|style|noscript)\b.*?</\1>", re.I | re.S)
TAG = re.compile(r"<[^>]+>")
# HoYoverse news titles: `Version 4.6 Trailer: "..." | Honkai: Star Rail` — the part before the
# pipe is the title, and it is what the program patterns are matched against.
_TITLE_SPLIT = re.compile(r"\s*[|｜]\s*")


def _clean(fragment: str) -> str:
    text = unescape(SCRIPT.sub(" ", fragment or ""))
    return re.sub(r"\s+", " ", TAG.sub(" ", text)).strip()


def _title_of(body: str) -> str:
    """Prefer a heading tag; fall back to the longest text run in the anchor."""
    m = re.search(r"<h\d[^>]*>(.*?)</h\d>", body, re.I | re.S)
    raw = _clean(m.group(1)) if m else ""
    if not raw:
        runs = [r for r in (_clean(p) for p in re.split(r"<(?:p|div|span)\b[^>]*>", body, flags=re.I)) if r]
        raw = max(runs, key=len) if runs else _clean(body)
    return _TITLE_SPLIT.split(raw)[0].strip()[:160]


def parse_news_page(html: str, base_url: str) -> list[dict]:
    """-> [{'id','url','title','image','ts'}], newest first as the page lists them."""
    out: list[dict] = []
    seen: set[str] = set()
    for m in ANCHOR.finditer(html or ""):
        pid = m.group("id")
        if pid in seen:
            continue
        seen.add(pid)
        href = m.group("href")
        url = href if href.startswith("http") else urljoin(base_url, href)
        imgs = [i.group("u") for i in IMG.finditer(m.group("body"))]
        d = DATE.search(_clean(m.group("body")))
        ts = 0
        if d:
            hits = find_datetimes(d.group(0), 0)
            ts = hits[0].ts if hits else 0
        out.append({"id": pid, "url": url.split("?")[0], "title": _title_of(m.group("body")),
                    "image": upgrade(imgs[0]) if imgs else "", "ts": ts})
    return out


def parse_article(html: str) -> dict:
    """An announcement page -> {'text','images','youtube'}. The embedded player is the reason to
    open the article at all: its thumbnail is the program's own artwork, and it is 1280x720
    where a HoYoLAB cover is a fraction of that. `text` carries the air time."""
    body = SCRIPT.sub(" ", html or "")
    yt = YOUTUBE.search(body)
    return {"text": _clean(body), "images": [upgrade(u.group("u")) for u in IMG.finditer(body)][:4],
            "youtube": f"https://www.youtube.com/watch?v={yt.group(1)}" if yt else None}


def _matches(game: Game, title: str, version: str | None) -> bool:
    if not title:
        return False
    if version and find_version(title) not in (version, None):
        return False
    lead = title.lower()
    return any(p.lower() in lead for p in game.program_patterns) or \
        bool(re.search(r"special\s+(?:program|broadcast)|livestream\s+preview", lead, re.I))


async def fetch_program(fetcher, game: Game, version: str | None, now: int) -> dict | None:
    """The official news page's entry for this version's program announcement.
    -> {'url','title','images','youtube','source'} or None (page down / no such article)."""
    base = (getattr(game, "news_url", "") or "").strip()
    if not base or fetcher is None:
        return None
    for tab in TABS:
        html = await fetcher.get_text(base + tab, source="newspage", retries=1)
        if not html:
            continue
        entries = [e for e in parse_news_page(html, base) if _matches(game, e["title"], version)]
        if not entries:
            continue
        best = entries[0]
        article = parse_article(await fetcher.get_text(best["url"], source="newspage", retries=1) or "")
        images = article["images"] or ([best["image"]] if best["image"] else [])
        if article.get("youtube"):
            images = [youtube_thumb(article["youtube"])] + images
        log.info("[%s] official news page: %s (%s)", game.key, best["title"], best["url"])
        return {"url": best["url"], "title": best["title"], "images": images,
                "text": article["text"], "youtube": article.get("youtube"), "ts": best["ts"],
                "source": "Official News"}
    return None
