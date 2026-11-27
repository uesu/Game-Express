"""Experimental Silver Palace listing snapshot, not registered with the monitor.

Publication dates are day-only; this reader intentionally returns no timestamp and
cannot be plugged into the timestamp-floor news runner. Two identical walks reduce
some pagination races; they cannot prove the upstream offers a consistent snapshot.
"""
from __future__ import annotations

import re
from datetime import date
from urllib.parse import urlsplit

from ..textutil import news_blocks

BASE = "https://silverpalace.elementagames.com/server/index.php/home/news_list"
DETAIL = "https://silverpalace.elementagames.com/server/index.php/home/news_detail"
ARTICLE = "https://silverpalace.elementagames.com/en-us/newsDetail?id={}"
MAX_PAGES = 30
MAX_ROWS_PER_PAGE = 100
_ID = re.compile(r"[0-9]{1,32}\Z")
_DATE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}\Z")


def _valid_date(value):
    if not isinstance(value, str) or not _DATE.fullmatch(value):
        return False
    try:
        return date.fromisoformat(value).isoformat() == value
    except ValueError:
        return False


async def _walk(fetcher):
    pages, first_size, found = None, None, {}
    number = 1
    while pages is None or number <= pages:
        response = await fetcher.get_json(BASE, source="news-silverpalace", retries=1,
                                          params={"lang": "en-us", "page": number})
        if (not isinstance(response, dict) or type(response.get("code")) is not int
                or response["code"] != 0 or not isinstance(response.get("data"), dict)):
            return None
        data = response["data"]
        total, current, rows = data.get("total_page"), data.get("current_page"), data.get("list")
        if (type(total) is not int or not 1 <= total <= MAX_PAGES
                or not isinstance(current, str) or current != str(number)
                or not isinstance(rows, list) or not 1 <= len(rows) <= MAX_ROWS_PER_PAGE):
            return None
        if pages is None:
            pages, first_size = total, len(rows)
        elif pages != total:
            return None
        if (number < pages and len(rows) != first_size) or len(rows) > first_size:
            return None
        for row in rows:
            if not isinstance(row, dict):
                return None
            cid, title, day = row.get("id"), row.get("title"), row.get("publish_date")
            if (not isinstance(cid, str) or not _ID.fullmatch(cid) or cid in found
                    or not isinstance(title, str) or not title.strip() or not _valid_date(day)):
                return None
            found[cid] = {"id": cid, "title": title.strip(), "date": day}
        number += 1
    return list(found.values())


async def snapshot(fetcher):
    """Return two matching complete scans, or None for any ambiguity or drift.

    The caller must not interpret a missing snapshot as an empty listing or use
    day-only dates as exact instants. No state or delivery is implemented.
    """
    first = await _walk(fetcher)
    if first is None:
        return None
    second = await _walk(fetcher)
    if second is None or first != second:
        return None
    return first


def _official_cover(value):
    """Only accept the exact observed image host; no network or redirects here."""
    if (not isinstance(value, str) or not value
            or any(c.isspace() or ord(c) < 32 or ord(c) == 127 for c in value)):
        return False
    try:
        parts = urlsplit(value)
        return (parts.scheme == "https" and parts.hostname == "s.elementagames.com"
                and not parts.username and not parts.password and parts.port in (None, 443)
                and bool(parts.path) and not parts.fragment)
    except ValueError:
        return False


async def detail(fetcher, row):
    """Fetch matching publisher detail as ordered blocks, without inventing a time.

    This is exploratory, not an article-fidelity or Discord-readiness guarantee.
    Delivery must separately validate every media URL and its redirect chain.
    """
    if not isinstance(row, dict) or set(row) != {"id", "title", "date"}:
        return None
    cid, title, day = row.get("id"), row.get("title"), row.get("date")
    if (not isinstance(cid, str) or not _ID.fullmatch(cid) or not isinstance(title, str)
            or not title.strip() or len(title) > 512 or not _valid_date(day)):
        return None
    response = await fetcher.get_json(DETAIL, source="news-silverpalace", retries=1,
                                      params={"lang": "en-us", "id": cid})
    if (not isinstance(response, dict) or type(response.get("code")) is not int
            or response["code"] != 0 or not isinstance(response.get("data"), dict)):
        return None
    data = response["data"]
    detail_title, content, cover = data.get("title"), data.get("content"), data.get("cover")
    if (data.get("id") != cid or data.get("publish_date") != day
            or not isinstance(detail_title, str) or detail_title.strip() != title.strip()
            or not isinstance(content, str) or not content.strip() or len(content) > 1024 * 1024
            or not _official_cover(cover)):
        return None
    try:
        blocks = news_blocks(content)
    except (ValueError, TypeError, AttributeError, RecursionError):
        return None
    if not blocks:
        return None
    return {"id": cid, "title": detail_title.strip(), "date": day,
            "url": ARTICLE.format(cid), "cover": cover, "blocks": blocks}
