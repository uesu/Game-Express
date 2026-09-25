"""HoYoLAB official news — official API first, c3kay JSON-Feed mirror as fallback.

Verified live 2026-09-25:
  getNewsList?gids=6&page_size=12&type=1  -> "Version 4.6 Update and Maintenance Notice"
  getPostFull?gids=6&post_id=46814308     -> content == "en-us" (quirk) -> body in structured_content
  getPostFull?gids=2&post_id=46604275     -> "Genshin Impact Version 7.1 Special Program Preview"
  https://feeds.c3kay.de/starrail.json    -> JSON Feed 1.1 with full content_html
Game ids (gids): 1 HI3 · 2 Genshin · 6 Star Rail · 8 ZZZ · 9 Nexus Anima.
News types: 1 Notices · 2 Events · 3 Info.
"""

from __future__ import annotations

import logging
import re
from typing import Callable

from ..config import Game
from ..http import Fetcher
from ..models import Item
from ..textutil import html_to_text, structured_to_text
from ..timeparse import parse_iso

log = logging.getLogger("gamexpress.hoyolab")

API = "https://bbs-api-os.hoyolab.com/community/post/wapi/"
HEADERS = {"Origin": "https://www.hoyolab.com", "Referer": "https://www.hoyolab.com/",
           "x-rpc-language": "en-us", "Accept": "application/json"}
ARTICLE_URL = "https://www.hoyolab.com/article/{}"
NEWS_TYPES = (1, 3, 2)


def _post_text(post: dict) -> tuple[str, list[str], list[str]]:
    content = (post.get("content") or "").strip()
    if re.fullmatch(r"[a-z]{2}-[a-z]{2}", content) or not content:
        return structured_to_text(post.get("structured_content") or "[]")
    if "<" in content:
        return html_to_text(content)
    return content, [], []


def _images(wrapper: dict) -> list[str]:
    urls = [c.get("url") for c in (wrapper.get("cover_list") or []) if c.get("url")]
    urls += [c.get("url") for c in (wrapper.get("image_list") or []) if c.get("url")]
    out = []
    for u in urls:
        if u not in out:
            out.append(u)
    return out


async def _full_post(fetcher: Fetcher, gid: int, post_id: str) -> dict | None:
    data = await fetcher.get_json(API + "getPostFull", source="hoyolab",
                                  headers=HEADERS, params={"gids": gid, "post_id": post_id, "read": 1})
    if not data or data.get("retcode") != 0:
        return None
    return (data.get("data") or {}).get("post")


async def official_items(fetcher: Fetcher, game: Game, want: Callable[[str], bool],
                         since_ts: int) -> list[Item] | None:
    """None = the API is unreachable (caller falls back to c3kay)."""
    gid = game.hoyolab_gid
    if not gid:
        return []
    any_ok = False
    items: dict[str, Item] = {}
    for news_type in NEWS_TYPES:
        data = await fetcher.get_json(API + "getNewsList", source="hoyolab", headers=HEADERS,
                                      params={"gids": gid, "page_size": 15, "type": news_type})
        if not data or data.get("retcode") != 0:
            continue
        any_ok = True
        for wrapper in (data.get("data") or {}).get("list") or []:
            post = wrapper.get("post") or {}
            pid = str(post.get("post_id") or "")
            created = int(post.get("created_at") or 0)
            subject = (post.get("subject") or "").strip()
            if not pid or pid in items or created < since_ts:
                continue
            preview = f"{subject}\n{post.get('content') or ''}\n{post.get('desc') or ''}"
            if not want(preview):
                continue
            full = await _full_post(fetcher, gid, pid)
            if full:
                text, links, imgs = _post_text(full.get("post") or {})
                images = _images(full) or imgs or _images(wrapper)
            else:  # list preview is truncated but usually holds the key sentences
                text, links, imgs = (post.get("content") or post.get("desc") or ""), [], []
                images = _images(wrapper)
            items[pid] = Item(source="hoyolab", game=game.key, id=pid, url=ARTICLE_URL.format(pid),
                              title=subject, text=text, published_ts=created, images=images,
                              links=links, author=((wrapper.get("user") or {}).get("nickname") or ""))
    if not any_ok:
        return None
    return list(items.values())


async def c3kay_items(fetcher: Fetcher, game: Game, want: Callable[[str], bool],
                      since_ts: int) -> list[Item]:
    if not game.c3kay_feed:
        return []
    feed = await fetcher.get_json(game.c3kay_feed, source="c3kay")
    if not feed:
        return []
    out = []
    for it in feed.get("items") or []:
        ts = parse_iso(it.get("date_published") or "") or 0
        if ts < since_ts:
            continue
        title = it.get("title") or ""
        text, links, imgs = html_to_text(it.get("content_html") or "")
        if not want(f"{title}\n{text}"):
            continue
        images = [it["image"]] if it.get("image") else []
        images += [i for i in imgs if i not in images]
        out.append(Item(source="hoyolab", game=game.key, id=str(it.get("id")), url=it.get("url") or "",
                        title=title, text=text, published_ts=ts, images=images, links=links))
    return out


async def fetch_items(fetcher: Fetcher, game: Game, want: Callable[[str], bool],
                      since_ts: int) -> list[Item]:
    items = await official_items(fetcher, game, want, since_ts)
    if items is None:
        log.warning("[%s] HoYoLAB API unreachable — using the c3kay mirror", game.key)
        items = await c3kay_items(fetcher, game, want, since_ts)
    return items
