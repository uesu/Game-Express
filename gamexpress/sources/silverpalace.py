"""Experimental Silver Palace listing snapshot, not registered with the monitor.

Publication dates are day-only; this reader intentionally returns no timestamp and
cannot be plugged into the timestamp-floor news runner. Two identical walks reduce
some pagination races; they cannot prove the upstream offers a consistent snapshot.
"""
from __future__ import annotations

import re
from datetime import date

BASE = "https://silverpalace.elementagames.com/server/index.php/home/news_list"
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
    day-only dates as exact instants. No detail, state, or delivery is implemented.
    """
    first = await _walk(fetcher)
    if first is None:
        return None
    second = await _walk(fetcher)
    if second is None or first != second:
        return None
    return first
