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

import asyncio
import logging
import re
from collections.abc import Callable

from ..config import Game
from ..http import Fetcher
from ..models import Item
from ..schedule import NOT_PROGRAM_TITLE
from ..textutil import find_version, html_to_text, structured_to_text, youtube_video_url
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
    """Post pictures, dropping a smaller upload when two same-aspect-ratio entries are the same art."""
    out: list[str] = []
    dims: dict[str, tuple[int, int]] = {}
    for group in ("cover_list", "image_list"):
        for c in wrapper.get(group) or []:
            u = c.get("url")
            if not u or u.split("?")[0] in {o.split("?")[0] for o in out}:
                continue
            w, h = int(c.get("width") or 0), int(c.get("height") or 0)
            if w and h:
                dims[u] = (w, h)
            out.append(u)

    def ratio(u: str) -> float:
        w, h = dims[u]
        return round(w / h, 3)

    drop = set()
    for a in out:
        for b in out:
            if a == b or a not in dims or b not in dims or a in drop or b in drop:
                continue
            wa, ha = dims[a]
            wb, hb = dims[b]
            if ratio(a) == ratio(b) and wb >= wa and hb >= ha and (wb, hb) != (wa, ha):
                drop.add(a)
    return [u for u in out if u not in drop]


async def _full_post(fetcher: Fetcher, gid: int, post_id: str) -> dict | None:
    data = await fetcher.get_json(API + "getPostFull", source="hoyolab",
                                  headers=HEADERS, params={"gids": gid, "post_id": post_id, "read": 1})
    if not data or data.get("retcode") != 0:
        return None
    return (data.get("data") or {}).get("post")


async def official_items(fetcher: Fetcher, game: Game, want: Callable[[str], bool],
                         since_ts: int) -> list[Item] | None:
    """None = the API is unreachable (caller falls back to c3kay). The news lists and the
    matching full posts are fetched concurrently."""
    gid = game.hoyolab_gid
    if not gid:
        return []
    lists = await asyncio.gather(*(
        fetcher.get_json(API + "getNewsList", source="hoyolab", headers=HEADERS,
                         params={"gids": gid, "page_size": 15, "type": news_type})
        for news_type in NEWS_TYPES))
    any_ok = False
    picked: dict[str, tuple[dict, dict, int, str]] = {}
    for data in lists:
        if not data or data.get("retcode") != 0:
            continue
        any_ok = True
        for wrapper in (data.get("data") or {}).get("list") or []:
            post = wrapper.get("post") or {}
            pid = str(post.get("post_id") or "")
            created = int(post.get("created_at") or 0)
            subject = (post.get("subject") or "").strip()
            if not pid or pid in picked or created < since_ts:
                continue
            preview = f"{subject}\n{post.get('content') or ''}\n{post.get('desc') or ''}"
            if want(preview):
                picked[pid] = (wrapper, post, created, subject)
    if not any_ok:
        return None
    fulls = await asyncio.gather(*(_full_post(fetcher, gid, pid) for pid in picked))
    items: list[Item] = []
    for (pid, (wrapper, post, created, subject)), full in zip(picked.items(), fulls):
        if full:
            text, links, imgs = _post_text(full.get("post") or {})
            images = _images(full) or imgs or _images(wrapper)
        else:  # list preview is truncated but usually holds the key sentences
            text, links, imgs = (post.get("content") or post.get("desc") or ""), [], []
            images = _images(wrapper)
        items.append(Item(source="hoyolab", game=game.key, id=pid, url=ARTICLE_URL.format(pid),
                          title=subject, text=text, published_ts=created, images=images,
                          links=links))
    return items


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


# --------------------------------------------------------------------------- program lookup
PROGRAM_TITLE = re.compile(r"special\s+(?:program|broadcast)|livestream\s+preview", re.I)


def pick_program(lists: list[dict], version: str | None, patterns: list[str]) -> tuple[str, dict, dict] | None:
    """The version's program article out of raw getNewsList pages -> (post_id, wrapper, post).

    Deliberately ignores `created_at`: the whole point is to reach an announcement that has
    already fallen out of the run's lookback window (HSR 4.6: the Special Program preview was
    11 days older than the maintenance notice that the card had linked to)."""
    pats = [p.lower() for p in patterns]
    best = None
    for data in lists:
        if not isinstance(data, dict) or data.get("retcode") != 0:
            continue
        for wrapper in (data.get("data") or {}).get("list") or []:
            post = wrapper.get("post") or {}
            subject = (post.get("subject") or "").strip()
            if not post.get("post_id") or not subject:
                continue
            lead = subject.lower()
            if not (PROGRAM_TITLE.search(subject) or any(p in lead for p in pats)):
                continue
            if NOT_PROGRAM_TITLE.search(subject):
                continue
            if version and find_version(subject) not in (version, None):
                continue
            created = int(post.get("created_at") or 0)
            if best is None or created > int(best[1].get("post", {}).get("created_at") or 0):
                best = (str(post["post_id"]), wrapper, post)
    return best


async def find_program(fetcher: Fetcher, game: Game, version: str | None, pages: int = 3) -> dict | None:
    """-> {'url','title','images','ts','source'} for the version's Special Program article, or
    None. Pages the official news list back until it finds one (page_size 20 x `pages`)."""
    gid = game.hoyolab_gid
    if not gid:
        return None
    last_id, lists = "", []
    for _ in range(max(1, pages)):
        params = {"gids": gid, "page_size": 20, "type": 1}
        if last_id:
            params["last_id"] = last_id
        data = await fetcher.get_json(API + "getNewsList", source="hoyolab", headers=HEADERS, params=params)
        if not data or data.get("retcode") != 0:
            break
        rows = (data.get("data") or {}).get("list") or []
        lists.append(data)
        if not rows:
            break
        last_id = str((rows[-1].get("post") or {}).get("post_id") or "")
        if not last_id:
            break
    hit = pick_program(lists, version, game.program_patterns)
    if not hit:
        return None
    pid, wrapper, post = hit
    full = await _full_post(fetcher, gid, pid)
    images = _images(wrapper)
    text, youtube = (post.get("content") or post.get("desc") or ""), None
    if full:
        text, links, imgs = _post_text(full.get("post") or {})
        images = _images(full) or imgs or images
        youtube = youtube_video_url(links, text)
    log.info("[%s] HoYoLAB program article: %s", game.key, post.get("subject"))
    return {"url": ARTICLE_URL.format(pid), "title": (post.get("subject") or "").strip(),
            "images": images, "text": text, "youtube": youtube,
            "ts": int(post.get("created_at") or 0), "source": "HoYoLAB"}
