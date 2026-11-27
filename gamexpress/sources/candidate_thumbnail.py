"""Optional verified YouTube-cover fallback for the inactive candidate sources.

This is not a live-source registration. Existing HoYoLAB/Kuro renderers are not
changed. A YouTube image is used only when no source image or native video exists,
and only after the caller's normal media preflight accepts the derived thumbnail.
"""
from __future__ import annotations

from dataclasses import replace
from urllib.parse import parse_qs, urlsplit

from ..cards import _youtube_watch_url

CANDIDATES = frozenset(("nte", "endfield", "silverpalace"))


def fallback_url(item):
    if (item.source not in CANDIDATES or item.game != item.source or item.images
            or any(b.get("kind") in ("image", "video") for b in item.article_blocks)):
        return None
    for block in item.article_blocks:
        if block.get("kind") != "link":
            continue
        watch = _youtube_watch_url(block.get("url", ""))
        if watch:
            video_id = parse_qs(urlsplit(watch).query)["v"][0]
            return f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"
    return None


async def with_verified_fallback(fetcher, item):
    """Copy the item only when a thumbnail passes preflight; never mutate the original."""
    url = fallback_url(item)
    if url and await fetcher.verify_media(url):
        return replace(item, images=[url])
    return item
