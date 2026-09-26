"""Full-size media for the schedule card.

Every source hands back a *small* rendition by default, and a schedule card is the one place
where the picture is the point (it is the program's key art). This module upgrades whatever a
source gave us to the biggest rendition that source serves, without ever inventing a URL that
the source does not have:

  pbs.twimg.com/media/X.jpg              -> ?name=orig              (X gives `small` by default)
  nitter.<instance>/pic/media%2FX.jpg    -> https://pbs.twimg.com/media/X.jpg  (+ ?name=orig)
  i.ytimg.com/vi/ID/hqdefault.jpg        -> maxresdefault.jpg       (1280x720 instead of 480x360)
  fastcdn.hoyoverse.com/content-v2/...   -> kept as-is (already the full-size article cover)

Ranking puts the rendition most likely to be program key art first: a YouTube thumbnail (the
livestream's own artwork) beats a tweet photo, which beats a small article cover.
"""

from __future__ import annotations

import re
from urllib.parse import unquote

TWIMG = re.compile(r"^https?://(?:pbs\.twimg\.com|ton\.twimg\.com)/", re.I)
NITTER_PIC = re.compile(r"/pic/(?:orig/)?(.+)$")
YOUTUBE_IMG = re.compile(r"^https?://i\.ytimg\.com/vi/([^/]+)/", re.I)
_MEDIA_PREFIXES = ("media/", "ext_twvideo_thumb/", "ext_tw_video_thumb/", "tweet_video_thumb/",
                   "amplify_video_thumb/")


def nitter_pic_to_twimg(url: str) -> str:
    """https://nitter.cf/pic/media%2FHR70hTAaoAA8Dzz.jpg -> https://pbs.twimg.com/media/HR70hTAaoAA8Dzz.jpg"""
    m = NITTER_PIC.search(url or "")
    if not m:
        return url
    path = unquote(m.group(1)).split("?")[0]
    if path.startswith(_MEDIA_PREFIXES):
        return f"https://pbs.twimg.com/{path}"
    return url


def twimg_orig(url: str) -> str:
    """A tweet photo without a size hint is served at `small`. `name=orig` is the full upload.
    A URL that already asks for a size is left exactly as the source gave it."""
    if not TWIMG.match(url or ""):
        return url
    if "name=" in url:
        return url
    return url + ("&" if "?" in url else "?") + "name=orig"


def youtube_thumb(video_or_id: str) -> str:
    """A watch URL, a youtu.be link, or a bare video id -> the 1280x720 thumbnail."""
    if not video_or_id:
        return ""
    m = re.search(r"(?:v=|youtu\.be/|/embed/|/shorts/|^)([A-Za-z0-9_-]{11})", video_or_id)
    vid = m.group(1) if m else video_or_id
    return f"https://i.ytimg.com/vi/{vid}/maxresdefault.jpg"


def upgrade(url: str) -> str:
    """Biggest rendition of one URL. Never returns a host the source did not already give us."""
    url = (url or "").strip()
    if not url:
        return ""
    if "/pic/" in url:
        url = nitter_pic_to_twimg(url)
    if TWIMG.match(url):
        return twimg_orig(url)
    m = YOUTUBE_IMG.match(url)
    if m:
        return f"https://i.ytimg.com/vi/{m.group(1)}/maxresdefault.jpg"
    return url


def _score(url: str) -> int:
    """Program key art first: a livestream thumbnail, then a full-size tweet photo, then a cover."""
    u = url.lower()
    if "i.ytimg.com" in u and "maxresdefault" in u:
        return 3
    if "pbs.twimg.com" in u:
        return 2
    if "fastcdn.hoyoverse.com" in u or "kurogame.com" in u:
        return 1
    return 0


def rank(images: list[str] | None, limit: int = 4) -> list[str]:
    """Dedupe, upgrade, best rendition first. Stable inside a score band."""
    out: list[str] = []
    for u in images or []:
        big = upgrade(u)
        if big and big not in out:
            out.append(big)
    out.sort(key=lambda u: -_score(u))
    return out[:limit]
