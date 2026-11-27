"""Perfect World official news pages — Neverness to Everness (NTE).

Why this exists: NTE has no HoYoLAB game id and no Kuro menu, so feature 3 had no source for it.
Its official site is plain server-rendered HTML (`nte.perfectworld.com`), and the news archive is
the same for every tab and every page, so it is read the same way a browser renders it — no API
key, no JavaScript, no header tricks.

Verified 2026-11-27 from a GitHub runner (the bytes are committed under `tests/fixtures/probes/`):

  https://nte.perfectworld.com/en/article/news/index.html        -> the Latest tab
  https://nte.perfectworld.com/en/article/news/gamenews/index.html  (Intel / news)
  https://nte.perfectworld.com/en/article/news/gamebroad/index.html (Notices)
  https://nte.perfectworld.com/en/article/news/gameevent/index.html (Events)
  https://nte.perfectworld.com/en/article/news/<tab>/YYYYMMDD/<id>.html  -> one article
  pages 2..N are `index1.html`, `index2.html`, … (page 1 is `index.html`)

Three things are deliberately *not* trusted:

* the printed date. It is `2026-11-23` in the list and `2026.11.23` in the article, in local time,
  with no zone. The **canonical** day is the one in the URL path (`/20261123/`), which is fixed at
  publication and cannot be restyled by a template change.
* the list's summary line: it is the title repeated (see the fixture), so it carries nothing.
* the tab name: the same article can be listed under more than one tab, so entries are keyed by id.

A page that fails is not an empty page: `discover_news` returns `None` when every tab's first page
is unavailable, so the caller advances no baseline and a later run still sees the article.
"""

from __future__ import annotations

import calendar
import logging
import re
import time
from html import unescape

from ..config import Game
from ..models import Item
from ..textutil import news_blocks

log = logging.getLogger("gamexpress.perfectworld")

BASE = "https://nte.perfectworld.com"
LIST = BASE + "/en/article/news/{tab}/{page}"
# The three tabs the site itself links from the news index (order = the order it links them).
TABS = ("gamenews", "gamebroad", "gameevent")
MAX_PAGES = 3          # bounded traffic: 3 tabs x 3 pages = 9 requests at most, usually 3

# One list row: `<a href="/en/article/news/gamebroad/20261123/265196.html"><div class="listItem">…`.
# The href is the contract; the classes inside are only used to read the title.
_ENTRY = re.compile(
    r'<a\b[^>]*href="(?P<href>[^"]*/article/news/(?P<tab>gamenews|gamebroad|gameevent)'
    r'/(?P<day>\d{8})/(?P<id>\d+)\.html)"[^>]*>(?P<body>.*?)</a>',
    re.I | re.S)
_TITLE = re.compile(r'<h\d[^>]*class="[^"]*title[^"]*"[^>]*>(?P<text>.*?)</h\d>', re.I | re.S)
_ARTICLE_TITLE = re.compile(r'<h1[^>]*class="[^"]*articleTitle[^"]*"[^>]*>(?P<text>.*?)</h1>',
                            re.I | re.S)
_ARTICLE_DATE = re.compile(r'<p[^>]*class="[^"]*articleDate[^"]*"[^>]*>(?P<text>[^<]{4,16})</p>', re.I)
_CONTENT_OPEN = re.compile(r'<div[^>]*class="[^"]*articleContent[^"]*"[^>]*>', re.I)
_COVER = re.compile(r'<meta[^>]+property="og:image"[^>]+content="(?P<url>[^"]+)"', re.I)
_SCRIPT = re.compile(r"<(script|style|noscript)\b.*?</\1>", re.I | re.S)
_TAG = re.compile(r"<[^>]+>")
_SPACE = re.compile(r"[\s\u00a0]+")


def _text(fragment: str) -> str:
    return _SPACE.sub(" ", unescape(_TAG.sub(" ", _SCRIPT.sub(" ", fragment or "")))).strip()


def _day_ts(day: str) -> int:
    """`20261123` -> UTC midnight of that day. The site publishes no zone; the path is the day."""
    try:
        return calendar.timegm(time.strptime(day, "%Y%m%d"))
    except (ValueError, TypeError):
        return 0


def _balanced_div(html: str, start: int) -> str:
    """Everything inside the `articleContent` div, honouring nested divs.

    A greedy `.*?</div>` would cut the article at the first nested close and a greedy
    `.*</div>` would swallow the footer; counting open/closes is the only correct read of an
    unknown body, and it degrades to the end of the document when the markup is truncated.
    """
    depth = 1
    for m in re.finditer(r"<(/?)div\b", html[start:], re.I):
        depth += -1 if m.group(1) else 1
        if depth == 0:
            return html[start:start + m.start()]
    return html[start:]


def parse_news_list(html: str, base_url: str = BASE) -> list[dict]:
    """-> [{'id','url','title','ts','tab'}] in page order; ids are deduped, first wins."""
    out: list[dict] = []
    seen: set[str] = set()
    for m in _ENTRY.finditer(html or ""):
        aid = m.group("id")
        if aid in seen:
            continue
        seen.add(aid)
        href = m.group("href")
        url = href if href.startswith("http") else base_url.rstrip("/") + href
        t = _TITLE.search(m.group("body"))
        title = _text(t.group("text")) if t else _text(m.group("body"))
        if not title:
            continue
        out.append({"id": aid, "url": url.split("?")[0].split("#")[0], "title": title[:200],
                    "ts": _day_ts(m.group("day")), "tab": m.group("tab").lower()})
    return out


def parse_article(html: str) -> dict:
    """-> {'title','ts','cover','blocks'} for one article page. Empty blocks = nothing to post."""
    raw = html or ""
    m = _CONTENT_OPEN.search(raw)
    body_html = _balanced_div(raw, m.end()) if m else ""
    title_m = _ARTICLE_TITLE.search(raw)
    title = _text(title_m.group("text")) if title_m else ""
    cover_m = _COVER.search(raw)
    date_m = _ARTICLE_DATE.search(raw)
    ts = 0
    if date_m:
        digits = re.sub(r"\D", "", date_m.group("text"))
        ts = _day_ts(digits) if len(digits) == 8 else 0
    blocks = news_blocks(body_html) if body_html.strip() else []
    return {"title": title[:200], "ts": ts, "cover": cover_m.group("url") if cover_m else "",
            "blocks": blocks}


def _page_path(tab: str, index: int) -> str:
    return "index.html" if index == 0 else f"index{index}.html"


async def discover_news(fetcher, game: Game, since: int) -> list[dict] | None:
    """Newest-first official list across the three tabs, bounded to `MAX_PAGES` pages per tab.

    `None` means "the site could not be read" (no baseline may advance); `[]` means "read fine,
    nothing new". A tab whose first page fails is skipped, but if every tab fails the result is
    `None`, never an empty list that would look like a quiet day.
    """
    if not getattr(game, "pw_news", False):
        return None
    picked: dict[str, dict] = {}
    tabs_read = 0
    for tab in TABS:
        for index in range(MAX_PAGES):
            html = await fetcher.get_text(LIST.format(tab=tab, page=_page_path(tab, index)),
                                          source="news-perfectworld", retries=1)
            if not html:
                break
            if index == 0:
                tabs_read += 1      # the tab answered: an empty list here is a quiet tab, not a failure
            rows = parse_news_list(html)
            if not rows:
                break
            oldest = min(r["ts"] for r in rows)
            for row in rows:
                if row["ts"] and row["ts"] < since:
                    continue
                picked.setdefault(row["id"], row)
            # The list is date-ordered; once a whole page is older than the window, later pages are too.
            if oldest and oldest < since:
                break
    if tabs_read == 0:
        return None
    return sorted(picked.values(), key=lambda row: (row["ts"], row["id"]))


async def news_article(fetcher, game: Game, row: dict) -> Item | None:
    """One NTE article -> Item with ordered blocks (the card's own renderer draws them)."""
    html = await fetcher.get_text(row["url"], source="news-perfectworld", retries=1)
    if not html:
        return None
    parsed = parse_article(html)
    title = parsed["title"] or row.get("title") or ""
    if not parsed["blocks"] or not title:
        return None
    return Item(source="perfectworld", game=game.key, id=str(row["id"]), url=row["url"],
                title=title, text="", published_ts=int(row.get("ts") or parsed["ts"] or 0),
                images=[parsed["cover"]] if parsed["cover"] else [],
                article_blocks=parsed["blocks"], author="Perfect World")
