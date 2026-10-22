"""Reddit & Redlib frontend fleet + rich-embed proxy chain (verified live 2026-10-22).

Three distinct jobs, each matched to the route shape upstream actually serves:
  * official posts (`game.reddit_official`, e.g. `u/genshinimpact`, `u/HonkaiStarRail`,
    `u/ZZZ_Official`, `u/WutheringWaves`) — feed `schedule` and `codes` as first-party items
    (`source="reddit"`, `PRIORITY["reddit"] = 50`). When an official publisher posts an image
    thread and places the broadcast air time or links in its own follow-up comment under the
    same post id (observed live on `u/genshinimpact` `1xbd2nm`, 2026-10-21), that same-author
    comment body is merged onto the post automatically.
  * community code corroboration (`reddit:<Subreddit>` in `game.codes["sources"]`) — extracts
    explicit redemption-code mentions from recent subreddit posts as unverified
    `CodeHit(code, "reddit", None)`. Because `family("reddit") == "reddit"`, a community post
    never bypasses `CODES_MIN_SOURCES` on its own; it acts strictly as an independent witness
    alongside `fandom`, `seria`, `humbao`, `ennead`/`ogc`, or `wuthering.gg` (including pre-launch
    games `hna` and `ananta` that otherwise have only one community wiki source).
  * single-post media / text resolution (`resolve_post`) — dual-path Redlib `/comments/<id>/`
    first (skipping pre-#592 listing-only tail hosts), then the `Discordbot/2.0` rich-embed
    proxy chain (`www.vxreddit.com` -> `embedez.com` -> `embeddit.deltandy.me`), then the
    `arctic-shift.photon-reddit.com` JSON archive as a last resort.

Upstream Redlib leaves `REDLIB_ENABLE_RSS` off by default (`RSS is disabled on this instance.`
across public instances), so public Redlib hosts are queried directly on `/r/<sub>/new` and
`/user/<account>` HTML rather than wasting requests on `.rss`.

For `embeddit.deltandy.me`, both wire formats are supported under `User-Agent: Discordbot/2.0`
(required so strict bot-only middleware does not `302`-redirect to `www.reddit.com`):
  1. Legacy v1 Mastodon status JSON (`/api/v1/statuses/<id>`) and OpenGraph `<meta>` tags.
  2. Component-Embed v2 HTML (`<script id="discord:component-embed" type="application/json">`,
     with `\\u003c` unescaping across `media_gallery`, `section`, and `text_display` nodes).
     Because that unfinished rewrite emits raw `v.redd.it` `fallback_url` video streams without
     muxed audio, `vxreddit.com` and `embedez.com` always sit ahead of `embeddit.deltandy.me`
     and any un-muxed `v.redd.it` fallback video is marked `audio_muxed=False`.
"""

from __future__ import annotations

import asyncio
import html
import json
import logging
import re
from calendar import timegm
from collections.abc import Callable
from datetime import datetime, timezone
from urllib.parse import quote, urlsplit

import feedparser

from ..config import DEFAULT_REDDIT_ARCHIVE, Game, Settings
from ..http import Fetcher
from ..models import CodeHit, Item
from ..textutil import clean_text, dedupe, find_urls, find_versions, html_to_text
from .codes import extract_codes_from_text

log = logging.getLogger("gamexpress.reddit")

REDDIT_BATCH = 4
REDDIT_WORKING = 2
REDDIT_GRACE = 1.5
REDDIT_TIMEOUT = 10
PROXY_BOT_UA = "Discordbot/2.0 (+https://discordapp.com)"
BROWSER_UA = "Mozilla/5.0 (compatible; Game-Express/1.0)"

TOKEN_GATED_REDDIT = frozenset({"https://redlib.miningtcup.me"})
OFFICIAL_RSS_HOSTS = frozenset({"https://www.reddit.com", "https://old.reddit.com"})
EDDRIT_HOSTS = frozenset({"https://eddrit.com"})
# Pre-#592 Redlib instances: `/r/<sub>/new` and `/user/<name>` render cleanly, while single-post
# `/comments/<id>/` fails JSON deserialization upstream. Keep them at the tail for listings and
# skip them when resolving an individual post by id.
REDDIT_LISTING_ONLY = frozenset({
    "https://red.artemislena.eu",
    "https://rl.awy.one",
    "https://redlib.freedit.eu",
    "https://redlib.utilibre.org",
})

POST_LINK_RE = re.compile(
    r"(?:(?<=[\s\"'<>(])|^|https?://[^/\s\"'<>]+)/r/([A-Za-z0-9_]+)/comments/([a-z0-9]{5,10})(?:/([^/?#\"'<>\s]*))?",
    re.I,
)
REDLIB_IMG_RE = re.compile(r"^https?://[^/]+/img/([^?#\s]+)", re.I)
REDLIB_PREVIEW_RE = re.compile(r"^https?://[^/]+/preview/(external-pre|pre)/([^?#\s]+)(\?[^\s\"'<>]*)?", re.I)
REDLIB_VID_RE = re.compile(r"^https?://[^/]+/vid/([A-Za-z0-9_-]+)/([^\s\"'<>]+)", re.I)
UNMUXED_REDDIT_VIDEO_RE = re.compile(r"https?://v\.redd\.it/[^/?#]+/(?:DASH|CMAF)_[^/?#]+\.mp4", re.I)

_CHALLENGE_MARKERS = (
    "__goaway_challenge",
    "anubis",
    "loading your page",
    "still trying to load your page",
    "rss is disabled on this instance",
    "failed to parse page json data",
    "error: reddit error",
    "error: nothing here",
    "502: bad gateway",
    "502 bad gateway",
)
_OFFICIAL_FLAIR_RE = re.compile(r"\bofficial\b", re.I)
_COMPONENT_SCRIPT_RE = re.compile(
    r'<script[^>]*\bid=["\']discord:component-embed["\'][^>]*>(.*?)</script>',
    re.I | re.S,
)
_META_TAG_RE = re.compile(
    r'<meta\b[^>]*?(?:property|name)=["\']([^"\']+)["\'][^>]*?\bcontent=["\']([^"\']*)["\']'
    r'|<meta\b[^>]*?\bcontent=["\']([^"\']*)["\'][^>]*?(?:property|name)=["\']([^"\']+)["\']',
    re.I,
)


def is_challenge_or_error_page(body: str | None) -> bool:
    """True when an HTTP 200 body is a bot challenge, splash wall, empty shell, or Redlib error."""
    if not body:
        return True
    stripped = body.strip()
    if len(stripped) < 120:
        return True
    low = stripped[:4096].lower()
    if any(marker in low for marker in _CHALLENGE_MARKERS):
        return True
    return bool('http-equiv="refresh"' in low and 'class="post' not in low and "<entry" not in low)


def redlib_media_to_reddit(url: str, base_origin: str = "") -> str:
    """Rewrite Redlib-proxied `/img/`, `/preview/`, `/vid/` paths back to canonical `redd.it` URLs."""
    raw = html.unescape(str(url or "")).strip()
    if not raw:
        return ""
    if raw.startswith("/") and base_origin:
        raw = f"{base_origin.rstrip('/')}{raw}"
    m = REDLIB_IMG_RE.match(raw)
    if m:
        return f"https://i.redd.it/{m.group(1)}"
    m = REDLIB_PREVIEW_RE.match(raw)
    if m:
        host = "external-preview.redd.it" if m.group(1).lower() == "external-pre" else "preview.redd.it"
        return f"https://{host}/{m.group(2)}{m.group(3) or ''}"
    m = REDLIB_VID_RE.match(raw)
    if m:
        return f"https://v.redd.it/{m.group(1)}/{m.group(2)}"
    return raw if raw.lower().startswith(("http://", "https://")) else ""


def canonical_post_url(subreddit: str, post_id: str, slug_part: str = "") -> str:
    tail = f"{slug_part.strip('/')}/" if slug_part.strip("/") else ""
    return f"https://www.reddit.com/r/{subreddit}/comments/{post_id}/{tail}"


def _parse_created_ts(raw: str | None) -> int:
    """Parse Redlib `title="Oct 22 2026, 03:05:00 UTC"` or ISO-8601 timestamps into epoch seconds."""
    text = html.unescape(str(raw or "")).strip()
    if not text:
        return 0
    for fmt in (
        "%b %d %Y, %H:%M:%S %Z",
        "%b %d %Y, %H:%M:%S UTC",
        "%B %d %Y, %H:%M:%S UTC",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%d %H:%M:%S%z",
    ):
        try:
            dt = datetime.strptime(text, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return int(dt.timestamp())
        except ValueError:
            continue
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return int(dt.timestamp())
    except ValueError:
        return 0


def _strip_tags(fragment: str) -> str:
    return clean_text(html.unescape(re.sub(r"<[^>]+>", " ", fragment or "")))


def _extract_div_blocks(page: str, marker_re: re.Pattern[str]) -> list[tuple[str, str]]:
    """Extract balanced `<div|details ...>...</div|details>` blocks matching `marker_re`."""
    blocks: list[tuple[str, str]] = []
    for m in marker_re.finditer(page):
        open_tag = m.group(0)
        tm = re.match(r"<([a-z0-9]+)\b", open_tag, re.I)
        tag = tm.group(1) if tm else "div"
        tag_re = re.compile(rf"</?{re.escape(tag)}\b[^>]*>", re.I)
        depth = 1
        pos = m.end()
        end_idx = len(page)
        while depth > 0:
            nxt = tag_re.search(page, pos)
            if not nxt:
                break
            tok = nxt.group(0)
            if tok.startswith("</"):
                depth -= 1
                if depth == 0:
                    end_idx = nxt.start()
            elif not tok.endswith("/>"):
                depth += 1
            pos = nxt.end()
        blocks.append((open_tag, page[m.end():end_idx]))
    return blocks


_POST_OPEN_RE = re.compile(r'<div\b(?=[^>]*\bclass="(?:[^"]*\s)?post(?:\s[^"]*)?")[^>]*>', re.I)
_COMMENT_OPEN_RE = re.compile(r'<(?:div|details)\b(?=[^>]*\bclass="(?:[^"]*\s)?comment(?:\s[^"]*)?")[^>]*>', re.I)


def parse_redlib_html(body: str, base_origin: str = "https://snoo.habedieeh.re") -> list[dict]:
    """Parse Redlib `/r/<sub>/new`, `/user/<name>`, `/search`, or `/comments/<id>/` HTML into post dicts."""
    if is_challenge_or_error_page(body):
        return []

    posts: dict[str, dict] = {}
    order: list[str] = []

    for open_tag, chunk in _extract_div_blocks(body, _POST_OPEN_RE):
        tm = re.search(r'<h[12]\s+class="post_title">(.*?)</h[12]>', chunk, re.I | re.S)
        pm = POST_LINK_RE.search(tm.group(1)) if tm else None
        if not pm:
            cm_link = re.search(r'class="post_comments"[^>]*href="([^"]+)"', chunk, re.I)
            pm = POST_LINK_RE.search(cm_link.group(1)) if cm_link else POST_LINK_RE.search(chunk)
        id_attr = re.search(r'\bid="([^"]+)"', open_tag)
        post_id = (pm.group(2) if pm else (id_attr.group(1) if id_attr else "")).strip().lower()
        subreddit = (pm.group(1) if pm else "").strip()
        slug_part = (pm.group(3) if pm and pm.group(3) else "").strip()
        if not subreddit:
            sm = re.search(r'class="post_subreddit"[^>]*href="/r/([A-Za-z0-9_]+)"', chunk, re.I)
            if sm:
                subreddit = sm.group(1)
        if not post_id or not subreddit:
            continue

        cls = (re.search(r'class="([^"]*)"', open_tag) or [None, ""])[1]
        stickied = "stickied" in cls.split()

        am = re.search(r'class="post_author([^"]*)"[^>]*>u/([^<\s]+)<', chunk, re.I)
        distinguished = (am.group(1).strip() if am else "")
        author = (am.group(2).strip() if am else "")

        cm = re.search(r'<span\s+class="created"\s+title="([^"]+)"', chunk, re.I)
        ts = _parse_created_ts(cm.group(1) if cm else "")

        flair = ""
        title = ""
        if tm:
            h_inner = tm.group(1)
            fm = re.search(r'class="post_flair"[^>]*>(.*?)</a>', h_inner, re.I | re.S)
            if fm:
                flair = _strip_tags(fm.group(1))
                h_inner = h_inner[:fm.start()] + h_inner[fm.end():]
            h_inner = re.sub(r'<small\s+class="(?:nsfw|spoiler)"[^>]*>.*?</small>', "", h_inner, flags=re.I | re.S)
            title = _strip_tags(h_inner)

        body_text = ""
        body_links: list[str] = []
        body_imgs: list[str] = []
        for _, bchunk in _extract_div_blocks(chunk, re.compile(r'<div\s+class="post_body(?:\s+[^"]*)?"[^>]*>', re.I)):
            body_text, body_links, body_imgs = html_to_text(bchunk)
            break

        images: list[str] = []
        videos: list[str] = []
        for m_img in re.finditer(r'class="post_media_image[^"]*"[^>]*href="([^"]+)"', chunk, re.I):
            u = redlib_media_to_reddit(m_img.group(1), base_origin)
            if u:
                images.append(u)
        for _, gchunk in _extract_div_blocks(chunk, re.compile(r'<div\s+class="gallery"[^>]*>', re.I)):
            for gm in re.finditer(r'<figure>\s*<a\s+href="([^"]+)"', gchunk, re.I):
                u = redlib_media_to_reddit(gm.group(1), base_origin)
                if u:
                    images.append(u)
        for bi in body_imgs:
            u = redlib_media_to_reddit(bi, base_origin)
            if u:
                images.append(u)
        for vm in re.finditer(r'<(?:video|source)\b[^>]*\bsrc="([^"]+)"', chunk, re.I):
            raw_v = html.unescape(vm.group(1)).strip()
            if raw_v.endswith(".m3u8"):
                continue
            u = redlib_media_to_reddit(raw_v, base_origin)
            if u:
                videos.append(u)

        ext_links = [
            u for u in body_links
            if u.startswith(("http://", "https://")) and not POST_LINK_RE.search(u)
        ]
        url = canonical_post_url(subreddit, post_id, slug_part)
        entry = {
            "id": post_id,
            "subreddit": subreddit,
            "author": author,
            "distinguished": distinguished,
            "flair": flair,
            "title": title,
            "text": body_text,
            "url": url,
            "ts": ts,
            "images": dedupe(images),
            "videos": dedupe(videos),
            "links": dedupe(ext_links),
            "stickied": stickied,
            "comments": [],
        }
        if post_id not in posts:
            posts[post_id] = entry
            order.append(post_id)

    # Extract comments on `/comments/<id>/` pages AND author comments on `/user/<name>` overview
    # pages so official publisher accounts that put air times/codes in the first comment under an
    # image post (e.g. `u/genshinimpact` `1xbd2nm`) inherit their own comment body automatically.
    page_author_m = re.search(r"<title>\s*([A-Za-z0-9_-]+)\s*\(u/\1\)", body, re.I)
    profile_author = page_author_m.group(1) if page_author_m else ""

    for open_tag, cchunk in _extract_div_blocks(body, _COMMENT_OPEN_RE):
        nested_c = _COMMENT_OPEN_RE.search(cchunk)
        own_cchunk = cchunk[:nested_c.start()] if nested_c else cchunk
        cid_m = re.search(r'\bid="([^"]+)"', open_tag)
        cid = cid_m.group(1) if cid_m else ""
        cam = re.search(r'class="comment_author[^"]*"[^>]*>u/([^<\s]+)<', own_cchunk, re.I)
        cauthor = cam.group(1).strip() if cam else ""
        if len(order) == 1:
            target_pid = order[0]
        else:
            plink_m = POST_LINK_RE.search(own_cchunk)
            target_pid = plink_m.group(2).lower() if plink_m else ""
        cbody = ""
        clinks: list[str] = []
        cimgs: list[str] = []
        for _, cb in _extract_div_blocks(own_cchunk, re.compile(r'<div\s+class="comment_body\b[^"]*"[^>]*>', re.I)):
            cbody, clinks, cimgs = html_to_text(cb)
            break
        if target_pid and target_pid in posts and cbody:
            p = posts[target_pid]
            p["comments"].append({"id": cid, "author": cauthor, "text": cbody})
            if cauthor and p["author"] and cauthor.lower() == p["author"].lower():
                p["text"] = f"{p['text']}\n\n{cbody}".strip() if p["text"] else cbody
                p["links"] = dedupe(p["links"] + [u for u in clinks if u.startswith(("http://", "https://"))])
                p["images"] = dedupe(p["images"] + [redlib_media_to_reddit(i, base_origin) for i in cimgs if redlib_media_to_reddit(i, base_origin)])

    # Redlib `/user/<name>` overview renders user comments as standalone cards referencing
    # `/r/<sub>/comments/<post_id>/<slug>/<comment_id>/#...` outside `<div class="post">`.
    if profile_author and posts:
        for cm in re.finditer(
            r'<a\s+href="(/r/[A-Za-z0-9_]+/comments/([a-z0-9]{5,10})/[^"#?]*/([a-z0-9]+)/[^"]*)"[^>]*>'
            r".*?</a>(.*?)(?=<div\s+class=\"post|<hr|<a\s+href=\"/r/[A-Za-z0-9_]+/comments/|\Z)",
            body,
            re.I | re.S,
        ):
            pid = cm.group(2).lower()
            if pid not in posts:
                continue
            ctext, clinks, cimgs = html_to_text(cm.group(4))
            # Strip leading metadata line `in r/<Subreddit> • 23h ago`
            ctext = re.sub(r"^in\s+r/[A-Za-z0-9_]+\s*[•·]\s*[^\n]+\n*", "", ctext, flags=re.I).strip()
            if ctext and ctext not in posts[pid]["text"]:
                posts[pid]["text"] = f"{posts[pid]['text']}\n\n{ctext}".strip() if posts[pid]["text"] else ctext
                posts[pid]["links"] = dedupe(
                    posts[pid]["links"] + [u for u in clinks if u.startswith(("http://", "https://"))]
                )
                posts[pid]["images"] = dedupe(
                    posts[pid]["images"]
                    + [redlib_media_to_reddit(i, base_origin) for i in cimgs if redlib_media_to_reddit(i, base_origin)]
                )

    return [posts[pid] for pid in order]


def parse_reddit_rss(xml_text: str) -> list[dict]:
    """Parse Atom/RSS from `www.reddit.com`, `old.reddit.com`, `redlib.miningtcup.me`, or `eddrit.com`."""
    if is_challenge_or_error_page(xml_text):
        return []
    feed = feedparser.parse(xml_text)
    out: list[dict] = []
    seen: set[str] = set()
    for e in feed.entries:
        link = str(e.get("link") or "")
        pm = POST_LINK_RE.search(link)
        raw_id = str(e.get("id") or "")
        post_id = (pm.group(2) if pm else re.sub(r"^t3_", "", raw_id)).strip().lower()
        subreddit = (pm.group(1) if pm else str((e.get("tags") or [{}])[0].get("term") or "")).strip().lstrip("r/")
        slug_part = (pm.group(3) if pm and pm.group(3) else "").strip()
        if not post_id or not subreddit or post_id in seen:
            continue
        seen.add(post_id)
        author = str(e.get("author") or "").strip().lstrip("/").removeprefix("u/").strip()
        parsed_time = e.get("published_parsed") or e.get("updated_parsed")
        ts = int(timegm(parsed_time)) if parsed_time else 0
        content_blocks = e.get("content") or []
        html_body = (content_blocks[0].get("value") if content_blocks and isinstance(content_blocks[0], dict) else "") or (
            e.get("summary") or e.get("description") or ""
        )
        text, links, imgs = html_to_text(html_body)
        text = re.sub(r"\s*submitted by\s+/u/\S+\s*\[link\]\s*\[comments\]\s*$", "", text, flags=re.I).strip()
        images: list[str] = []
        for u in links + imgs:
            cu = redlib_media_to_reddit(u)
            if cu and re.search(r"https?://(?:i\.redd\.it|preview\.redd\.it|external-preview\.redd\.it)/", cu, re.I):
                images.append(cu)
        for thumb in e.get("media_thumbnail") or []:
            if isinstance(thumb, dict) and thumb.get("url"):
                images.append(html.unescape(str(thumb["url"])))
        ext_links = [
            u for u in links
            if u.startswith(("http://", "https://"))
            and not POST_LINK_RE.search(u)
            and "reddit.com/user/" not in u
            and u not in images
        ]
        out.append({
            "id": post_id,
            "subreddit": subreddit,
            "author": author,
            "distinguished": "",
            "flair": "",
            "title": clean_text(html.unescape(str(e.get("title") or ""))),
            "text": text,
            "url": canonical_post_url(subreddit, post_id, slug_part),
            "ts": ts,
            "images": dedupe(images),
            "videos": [],
            "links": dedupe(ext_links),
            "stickied": False,
            "comments": [],
        })
    return out


# ------------------------------------------------ rich-embed proxy & component-embed parsers
def _extract_meta_tags(html_text: str) -> dict[str, list[str]]:
    tags: dict[str, list[str]] = {}
    for m in _META_TAG_RE.finditer(html_text or ""):
        key = (m.group(1) or m.group(4) or "").strip().lower()
        val = html.unescape(m.group(2) if m.group(1) else (m.group(3) or "")).strip()
        if key and val:
            tags.setdefault(key, []).append(val)
    return tags


def parse_embeddit_status(data: dict) -> dict | None:
    """Parse v1 Mastodon-compatible JSON response (`/api/v1/statuses/<id>`)."""
    if not isinstance(data, dict):
        return None
    atts = data.get("media_attachments")
    content_html = str(data.get("content") or "")
    if not isinstance(atts, list) and not content_html:
        return None
    text, links, _ = html_to_text(content_html)
    images: list[str] = []
    videos: list[str] = []
    audio_muxed = True
    for att in atts or []:
        if not isinstance(att, dict):
            continue
        u = str(att.get("url") or att.get("remote_url") or "").strip()
        if not u.startswith(("http://", "https://")):
            continue
        kind = str(att.get("type") or "").lower()
        if kind in ("video", "gifv") or u.lower().endswith((".mp4", ".webm")):
            videos.append(u)
            if UNMUXED_REDDIT_VIDEO_RE.match(u):
                audio_muxed = False
        else:
            images.append(u)
    return {
        "text": text,
        "links": links,
        "images": dedupe(images),
        "videos": dedupe(videos),
        "audio_muxed": audio_muxed,
        "format": "mastodon-v1",
    }


def parse_embeddit_component_html(html_text: str) -> dict | None:
    """Parse both Component-Embed v2 `<script id="discord:component-embed">` HTML and v1 OpenGraph HTML.

    Unescapes JSON-script `\\u003c` sequences automatically via `json.loads`, walks nested
    `component.components` trees (`media_gallery`, `section` accessories, `text_display`), flags
    removed/deleted posts cleanly, and marks raw un-muxed `v.redd.it` `fallback_url` video items
    with `audio_muxed=False` so callers prefer muxed video+audio streams from `vxreddit`/`embedez`.
    """
    if not html_text:
        return None
    sm = _COMPONENT_SCRIPT_RE.search(html_text)
    if sm:
        raw_json = sm.group(1).strip()
        try:
            payload = json.loads(raw_json)
        except json.JSONDecodeError:
            payload = None
        if isinstance(payload, dict) and isinstance(payload.get("component"), dict):
            texts: list[str] = []
            images: list[str] = []
            videos: list[str] = []
            audio_muxed = True

            def _walk(node: object) -> None:
                nonlocal audio_muxed
                if isinstance(node, list):
                    for item in node:
                        _walk(item)
                    return
                if not isinstance(node, dict):
                    return
                ntype = node.get("type")
                if ntype in ("text_display", 10) and isinstance(node.get("content"), str):
                    texts.append(node["content"])
                elif ntype in ("media_gallery", 12) and isinstance(node.get("items"), list):
                    for item in node["items"]:
                        if not isinstance(item, dict):
                            continue
                        media = item.get("media") if isinstance(item.get("media"), dict) else item
                        u = str((media or {}).get("url") or "").strip()
                        if not u.startswith(("http://", "https://")):
                            continue
                        if u.lower().endswith((".mp4", ".webm")) or "v.redd.it/" in u.lower():
                            videos.append(u)
                            if UNMUXED_REDDIT_VIDEO_RE.match(u):
                                audio_muxed = False
                        else:
                            images.append(u)
                elif ntype in ("section", 9):
                    acc = node.get("accessory")
                    if isinstance(acc, dict):
                        media = acc.get("media") if isinstance(acc.get("media"), dict) else acc
                        u = str((media or {}).get("url") or "").strip()
                        if u.startswith(("http://", "https://")):
                            images.append(u)
                for child_key in ("components", "children"):
                    if child_key in node:
                        _walk(node[child_key])

            _walk(payload["component"])
            joined = "\n\n".join(t.strip() for t in texts if t.strip())
            removed = joined.strip() in ("[removed]", "[deleted]") or "*This post was removed" in joined
            return {
                "text": joined,
                "links": find_urls(joined),
                "images": dedupe(images),
                "videos": dedupe(videos),
                "audio_muxed": audio_muxed,
                "removed": removed,
                "format": "component-embed-v2",
            }

    meta = _extract_meta_tags(html_text)
    if not meta:
        return None
    videos = [
        u for k in ("og:video", "og:video:secure_url", "twitter:player:stream")
        for u in meta.get(k, [])
        if u.startswith(("http://", "https://"))
    ]
    images = [
        u for k in ("og:image", "twitter:image", "twitter:image:src")
        for u in meta.get(k, [])
        if u.startswith(("http://", "https://"))
    ]
    desc = (meta.get("og:description") or meta.get("twitter:description") or [""])[0]
    title = (meta.get("og:title") or meta.get("twitter:title") or [""])[0]
    if not (videos or images or desc or title):
        return None
    audio_muxed = not any(UNMUXED_REDDIT_VIDEO_RE.match(v) for v in videos)
    return {
        "title": clean_text(title),
        "text": clean_text(desc),
        "links": find_urls(desc),
        "images": dedupe(images),
        "videos": dedupe(videos),
        "audio_muxed": audio_muxed,
        "format": "opengraph",
    }


# ----------------------------------------------------------------------------- client
class RedditClient:
    """Async Reddit & Redlib client matching `XClient`: batched healthy-first probing, zero hits to
    tail fallbacks while primary hosts answer, and strict separation between official publisher
    posts and unverified community code corroboration."""

    def __init__(self, fetcher: Fetcher, settings: Settings) -> None:
        self.fetcher = fetcher
        self.settings = settings
        self._subreddit_cache: dict[str, list[dict] | None] = {}
        self._user_cache: dict[str, list[dict] | None] = {}
        self._post_cache: dict[str, dict | None] = {}
        self.reachable: set[str] = set()

    async def _get_text(self, url: str, **kwargs) -> str | None:
        fn = getattr(self.fetcher, "get_text", None)
        return await fn(url, **kwargs) if callable(fn) else None

    async def _get_json(self, url: str, **kwargs):
        fn = getattr(self.fetcher, "get_json", None)
        return await fn(url, **kwargs) if callable(fn) else None

    def _eligible_instances(self, *, for_post_detail: bool = False, kind: str = "sub") -> list[str]:
        out: list[str] = []
        for raw in self.settings.reddit_instances:
            inst = raw.strip().rstrip("/")
            if not inst:
                continue
            if inst in TOKEN_GATED_REDDIT and not self.settings.nitter_token:
                continue
            if for_post_detail and inst in REDDIT_LISTING_ONLY:
                continue
            out.append(inst)
        if kind == "sub" and self.settings.reddit_token and "https://www.reddit.com" in out:
            out.remove("https://www.reddit.com")
            out.insert(0, "https://www.reddit.com")
        return out

    async def _fetch_listing_on(self, inst: str, kind: str, target: str) -> list[dict] | None:
        """Fetch one subreddit (`kind='sub'`) or user (`kind='user'`) listing from `inst`."""
        if inst in OFFICIAL_RSS_HOSTS:
            if kind == "sub":
                url = f"{inst}/r/{target}/new.rss"
                if inst == "https://www.reddit.com" and self.settings.reddit_token:
                    url = f"{url}?feed={quote(self.settings.reddit_token)}"
            else:
                url = f"{inst}/user/{target}/submitted.rss"
            body = await self._get_text(
                url, source="reddit", headers={"User-Agent": BROWSER_UA}, retries=0, timeout=REDDIT_TIMEOUT
            )
            if not body or is_challenge_or_error_page(body):
                return None
            return await asyncio.to_thread(parse_reddit_rss, body)

        if inst in EDDRIT_HOSTS:
            if kind != "sub":
                return None
            body = await self._get_text(
                f"{inst}/r/{target}/.rss",
                source="reddit",
                headers={"User-Agent": BROWSER_UA},
                retries=0,
                timeout=REDDIT_TIMEOUT,
            )
            if not body or is_challenge_or_error_page(body):
                return None
            return await asyncio.to_thread(parse_reddit_rss, body)

        token_q = f"?token={quote(self.settings.nitter_token)}" if inst in TOKEN_GATED_REDDIT else ""
        if inst in TOKEN_GATED_REDDIT:
            rss_path = f"{inst}/r/{target}.rss{token_q}" if kind == "sub" else f"{inst}/user/{target}.rss{token_q}"
            rss_body = await self._get_text(
                rss_path, source="reddit", headers={"User-Agent": BROWSER_UA}, retries=0, timeout=REDDIT_TIMEOUT
            )
            if rss_body and not is_challenge_or_error_page(rss_body):
                parsed = await asyncio.to_thread(parse_reddit_rss, rss_body)
                if parsed:
                    return parsed

        html_path = f"{inst}/r/{target}/new{token_q}" if kind == "sub" else f"{inst}/user/{target}{token_q}"
        body = await self._get_text(
            html_path, source="reddit", headers={"User-Agent": BROWSER_UA}, retries=0, timeout=REDDIT_TIMEOUT
        )
        if not body or is_challenge_or_error_page(body):
            return None
        return await asyncio.to_thread(parse_redlib_html, body, inst)

    async def _probe_batch(self, batch: list[str], kind: str, target: str, need: int) -> list[list[dict]]:
        tasks = [asyncio.create_task(self._fetch_listing_on(inst, kind, target)) for inst in batch]
        pending: set[asyncio.Task] = set(tasks)
        good: list[list[dict]] = []
        deadline: float | None = None
        loop = asyncio.get_running_loop()
        try:
            while pending:
                wait = None if deadline is None else max(0.0, deadline - loop.time())
                done, pending = await asyncio.wait(pending, timeout=wait, return_when=asyncio.FIRST_COMPLETED)
                if not done:
                    break
                for task in done:
                    res = task.result()
                    if res is not None:
                        good.append(res)
                if len(good) >= need and deadline is None:
                    deadline = loop.time() + REDDIT_GRACE
        finally:
            for task in pending:
                task.cancel()
            await asyncio.gather(*pending, return_exceptions=True)
        return good

    async def _gather_listing(self, kind: str, target: str) -> list[dict] | None:
        merged: dict[str, dict] = {}
        working = 0
        fleet = self._eligible_instances(for_post_detail=False, kind=kind)
        for i in range(0, len(fleet), REDDIT_BATCH):
            if working >= REDDIT_WORKING:
                break
            batch = fleet[i:i + REDDIT_BATCH]
            for entries in await self._probe_batch(batch, kind, target, REDDIT_WORKING - working):
                working += 1
                for e in entries:
                    pid = e["id"]
                    if pid not in merged:
                        merged[pid] = dict(e)
                    else:
                        cur = merged[pid]
                        if len(e.get("text") or "") > len(cur.get("text") or ""):
                            cur["text"] = e["text"]
                        cur["images"] = dedupe(cur["images"] + e.get("images", []))
                        cur["videos"] = dedupe(cur["videos"] + e.get("videos", []))
                        cur["links"] = dedupe(cur["links"] + e.get("links", []))
                        if e.get("flair") and not cur.get("flair"):
                            cur["flair"] = e["flair"]
        if not working:
            log.debug("[reddit:%s:%s] no working frontend this run", kind, target)
            return None
        return sorted(merged.values(), key=lambda x: x.get("ts") or 0, reverse=True)

    async def subreddit(self, name: str) -> list[dict] | None:
        if not self.settings.reddit_enabled or not name:
            return None
        key = name.lower()
        if key not in self._subreddit_cache:
            res = await self._gather_listing("sub", name)
            self._subreddit_cache[key] = res
            if res is not None:
                self.reachable.add(f"r/{key}")
        return self._subreddit_cache[key]

    async def user(self, account: str) -> list[dict] | None:
        if not self.settings.reddit_enabled or not account:
            return None
        key = account.lower()
        if key not in self._user_cache:
            res = await self._gather_listing("user", account)
            self._user_cache[key] = res
            if res is not None:
                self.reachable.add(f"u/{key}")
        return self._user_cache[key]

    async def _probe_proxy(self, proxy_base: str, subreddit: str, post_id: str, slug_part: str = "") -> dict | None:
        """Query one rich-embed proxy (`vxreddit`, `embedez`, or `embeddit.deltandy.me`)."""
        base = proxy_base.rstrip("/")
        host = (urlsplit(base).hostname or "").lower()
        tail = f"/{slug_part.strip('/')}" if slug_part.strip("/") else ""
        post_path = f"/r/{subreddit}/comments/{post_id}{tail}/"

        if "embeddit" in host:
            # 1. Live v1 Mastodon JSON endpoint; 2. v2 `<script id="discord:component-embed">` / OG HTML.
            data = await self._get_json(
                f"{base}/api/v1/statuses/{post_id}",
                source="reddit-proxy",
                headers={"User-Agent": PROXY_BOT_UA},
                retries=0,
                timeout=REDDIT_TIMEOUT,
            )
            parsed = parse_embeddit_status(data) if isinstance(data, dict) else None
            if parsed and (parsed["images"] or parsed["videos"] or parsed["text"]):
                return parsed
            page = await self._get_text(
                f"{base}{post_path}",
                source="reddit-proxy",
                headers={"User-Agent": PROXY_BOT_UA},
                retries=0,
                timeout=REDDIT_TIMEOUT,
            )
            return parse_embeddit_component_html(page or "")

        if "embedez" in host:
            target = canonical_post_url(subreddit, post_id, slug_part)
            data = await self._get_json(
                f"{base}/api/v1/providers/search",
                source="reddit-proxy",
                params={"q": target},
                headers={"User-Agent": PROXY_BOT_UA},
                retries=0,
                timeout=REDDIT_TIMEOUT,
            )
            if isinstance(data, dict):
                key = str(data.get("key") or (data.get("data") or {}).get("key") or "").strip()
                if key:
                    page = await self._get_text(
                        f"{base}/embed/{key}",
                        source="reddit-proxy",
                        headers={"User-Agent": PROXY_BOT_UA},
                        retries=0,
                        timeout=REDDIT_TIMEOUT,
                    )
                    parsed = parse_embeddit_component_html(page or "")
                    if parsed:
                        return parsed
            page = await self._get_text(
                f"{base}{post_path}",
                source="reddit-proxy",
                headers={"User-Agent": PROXY_BOT_UA},
                retries=0,
                timeout=REDDIT_TIMEOUT,
            )
            return parse_embeddit_component_html(page or "")

        # Default rich-embed proxy (`www.vxreddit.com` and compatible OpenGraph/oEmbed mirrors).
        page = await self._get_text(
            f"{base}{post_path}",
            source="reddit-proxy",
            headers={"User-Agent": PROXY_BOT_UA},
            retries=0,
            timeout=REDDIT_TIMEOUT,
        )
        return parse_embeddit_component_html(page or "")

    async def resolve_post(self, subreddit: str, post_id: str, slug_part: str = "") -> dict | None:
        """Resolve a single Reddit post (`text`, `images`, `videos`, `links`), preferring muxed video."""
        cache_key = f"{subreddit.lower()}:{post_id.lower()}"
        if cache_key in self._post_cache:
            return self._post_cache[cache_key]

        best: dict | None = None
        for inst in self._eligible_instances(for_post_detail=True):
            if inst in OFFICIAL_RSS_HOSTS or inst in EDDRIT_HOSTS:
                continue
            token_q = f"?token={quote(self.settings.nitter_token)}" if inst in TOKEN_GATED_REDDIT else ""
            tail = f"/{slug_part.strip('/')}" if slug_part.strip("/") else ""
            body = await self._get_text(
                f"{inst}/r/{subreddit}/comments/{post_id}{tail}/{token_q}",
                source="reddit",
                headers={"User-Agent": BROWSER_UA},
                retries=0,
                timeout=REDDIT_TIMEOUT,
            )
            if not body or is_challenge_or_error_page(body):
                continue
            parsed_list = await asyncio.to_thread(parse_redlib_html, body, inst)
            if parsed_list:
                best = parsed_list[0]
                break

        unmuxed_fallback: dict | None = None
        need_proxy = best is None or (best.get("videos") and any(UNMUXED_REDDIT_VIDEO_RE.match(v) for v in best["videos"]))
        if need_proxy:
            for proxy_base in self.settings.reddit_proxies:
                if not proxy_base:
                    continue
                hit = await self._probe_proxy(proxy_base, subreddit, post_id, slug_part)
                if not hit or hit.get("removed"):
                    continue
                if hit.get("videos") and not hit.get("audio_muxed", True):
                    unmuxed_fallback = unmuxed_fallback or hit
                    continue
                if best is None:
                    best = {
                        "id": post_id.lower(),
                        "subreddit": subreddit,
                        "author": "",
                        "distinguished": "",
                        "flair": "",
                        "title": hit.get("title") or "",
                        "text": hit.get("text") or "",
                        "url": canonical_post_url(subreddit, post_id, slug_part),
                        "ts": 0,
                        "images": list(hit.get("images") or []),
                        "videos": list(hit.get("videos") or []),
                        "links": list(hit.get("links") or []),
                        "stickied": False,
                        "comments": [],
                    }
                else:
                    best["videos"] = list(hit.get("videos") or best["videos"])
                    best["images"] = dedupe(best["images"] + list(hit.get("images") or []))
                break

        if best is None and unmuxed_fallback is not None:
            best = {
                "id": post_id.lower(),
                "subreddit": subreddit,
                "author": "",
                "distinguished": "",
                "flair": "",
                "title": unmuxed_fallback.get("title") or "",
                "text": unmuxed_fallback.get("text") or "",
                "url": canonical_post_url(subreddit, post_id, slug_part),
                "ts": 0,
                "images": list(unmuxed_fallback.get("images") or []),
                "videos": list(unmuxed_fallback.get("videos") or []),
                "links": list(unmuxed_fallback.get("links") or []),
                "stickied": False,
                "comments": [],
            }

        if best is None:
            arc = await self._get_json(
                f"{DEFAULT_REDDIT_ARCHIVE.rstrip('/')}/api/posts/ids",
                source="reddit-archive",
                params={"ids": post_id.lower()},
                retries=0,
                timeout=REDDIT_TIMEOUT,
            )
            rows = (arc or {}).get("data") if isinstance(arc, dict) else None
            if isinstance(rows, list) and rows and isinstance(rows[0], dict):
                row = rows[0]
                selftext = clean_text(str(row.get("selftext") or ""))
                ext_url = str(row.get("url") or "").strip()
                imgs = [ext_url] if re.search(r"https?://(?:i\.redd\.it|preview\.redd\.it)/", ext_url, re.I) else []
                best = {
                    "id": post_id.lower(),
                    "subreddit": str(row.get("subreddit") or subreddit),
                    "author": str(row.get("author") or ""),
                    "distinguished": str(row.get("distinguished") or ""),
                    "flair": str(row.get("link_flair_text") or ""),
                    "title": clean_text(str(row.get("title") or "")),
                    "text": selftext,
                    "url": canonical_post_url(subreddit, post_id, slug_part),
                    "ts": int(row.get("created_utc") or 0),
                    "images": imgs,
                    "videos": [],
                    "links": find_urls(selftext),
                    "stickied": False,
                    "comments": [],
                }

        self._post_cache[cache_key] = best
        return best

    async def items(self, game: Game, want: Callable[[str], bool], since_ts: int) -> list[Item]:
        """Official publisher posts from `game.reddit_official` matching `want` since `since_ts`."""
        if not self.settings.reddit_enabled or not game.reddit_official:
            return []
        allowed_subs = {s.lower() for s in game.subreddits}
        allowed_authors = {a.lower() for a in game.reddit_official}
        feeds = await asyncio.gather(*(self.user(acc) for acc in game.reddit_official))
        out: list[Item] = []
        seen: set[str] = set()
        for entries in feeds:
            for e in entries or []:
                if e["id"] in seen:
                    continue
                if e.get("author") and e["author"].lower() not in allowed_authors:
                    continue
                if allowed_subs and e.get("subreddit", "").lower() not in allowed_subs:
                    continue
                if e.get("ts") and e["ts"] < since_ts:
                    continue
                combined = f"{e.get('title') or ''}\n{e.get('text') or ''}".strip()
                if not want(combined):
                    continue
                seen.add(e["id"])
                out.append(Item(
                    source="reddit",
                    game=game.key,
                    id=e["id"],
                    url=e["url"],
                    title=e.get("title") or "",
                    text=e.get("text") or "",
                    published_ts=int(e.get("ts") or 0),
                    images=list(e.get("images") or []),
                    links=list(e.get("links") or []),
                    author=e.get("author") or "",
                ))
        return out

    async def program_post(self, game: Game, version: str) -> Item | None:
        """Backup Special Program lookup when X, HoYoLAB, and the official news page miss."""
        from .. import schedule

        if not self.settings.reddit_enabled:
            return None
        candidates: list[dict] = []
        for acc in game.reddit_official:
            candidates.extend(await self.user(acc) or [])
        official_set = {a.lower() for a in game.reddit_official}
        for sub in game.subreddits:
            for e in await self.subreddit(sub) or []:
                if e.get("author", "").lower() in official_set or _OFFICIAL_FLAIR_RE.search(e.get("flair") or ""):
                    candidates.append(e)

        found: dict | None = None
        unresolved: list[dict] = []
        for e in candidates:
            title = e.get("title") or ""
            body = e.get("text") or ""
            if schedule.is_program_announcement(game, body, title=title):
                full_text = f"{title}\n{body}"
                mentioned = find_versions(full_text)
                if version and mentioned and version not in mentioned and version not in full_text:
                    continue
                if found is None or (e.get("ts") or 0) < (found.get("ts") or 0):
                    found = e
                continue
            if (
                not body
                and e.get("id")
                and e.get("subreddit")
                and not schedule.NOT_PROGRAM_TITLE.search(title)
                and any(re.search(pat, title, re.I) for pat in game.program_patterns)
            ):
                mentioned_title = find_versions(title)
                if version and mentioned_title and version not in mentioned_title and version not in title:
                    continue
                unresolved.append(e)

        if found is None:
            for e in unresolved[:2]:
                detail = await self.resolve_post(e["subreddit"], e["id"])
                if not detail:
                    continue
                title = detail.get("title") or e.get("title") or ""
                body = detail.get("text") or ""
                if not schedule.is_program_announcement(game, body, title=title):
                    continue
                full_text = f"{title}\n{body}"
                mentioned = find_versions(full_text)
                if version and mentioned and version not in mentioned and version not in full_text:
                    continue
                if found is None or (detail.get("ts") or 0) < (found.get("ts") or 0):
                    found = detail
        if found is None:
            return None
        return Item(
            source="reddit",
            game=game.key,
            id=found["id"],
            url=found["url"],
            title=found.get("title") or "",
            text=found.get("text") or "",
            published_ts=int(found.get("ts") or 0),
            images=list(found.get("images") or []),
            links=list(found.get("links") or []),
            author=found.get("author") or "",
        )

    async def community_codes(self, subreddit: str) -> list[CodeHit] | None:
        """Unverified `CodeHit(..., source='reddit')` extracted from recent `/r/<sub>/new` posts."""
        entries = await self.subreddit(subreddit)
        if entries is None:
            return None
        hits: list[CodeHit] = []
        seen: set[str] = set()
        for e in entries:
            blob = f"{e.get('title') or ''}\n{e.get('text') or ''}"
            for code in extract_codes_from_text(blob):
                if code not in seen:
                    seen.add(code)
                    hits.append(CodeHit(code, "reddit", None))
        return hits
