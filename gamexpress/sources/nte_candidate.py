"""Unregistered parser for one observed NTE English news listing page.

This is not a complete listing, article reader or monitor source. Callers must
establish full pagination and a reliable snapshot before using any parsed rows.
"""
from __future__ import annotations

import re
from datetime import date
from html.parser import HTMLParser

_PATH = re.compile(r"/en/article/news/(?:gamenews|gamebroad|gameevent)/[0-9]{8}/([0-9]{1,32})\.html\Z")
_DATE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}\Z")
_HOST = "https://nte.perfectworld.com"
_VOID = frozenset(("area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"))


def _day(value):
    if not _DATE.fullmatch(value):
        return False
    try:
        return date.fromisoformat(value).isoformat() == value
    except ValueError:
        return False


class _Listing(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = []
        self.found = 0
        self.closed = 0
        self.invalid = False
        self.current = None
        self.capture = None
        self.rows = []

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        classes = (attributes.get("class") or "").split()
        if not self.stack:
            if tag == "div" and "listNews" in classes:
                self.found += 1
                self.stack.append(tag)
            return
        if tag == "a":
            if self.current is not None:
                self.invalid = True
            href = attributes.get("href") or ""
            path = href[len(_HOST):] if href.startswith(_HOST + "/") else href
            match = _PATH.fullmatch(path)
            if not match:
                self.invalid = True
            self.current = {"id": match[1] if match else "", "title": None, "date": None}
        if self.current is not None and ((tag == "h2" and "title" in classes) or
                                         (tag == "p" and "date" in classes)):
            key = "title" if tag == "h2" else "date"
            if self.capture is not None or self.current[key] is not None:
                self.invalid = True
            self.capture = (key, len(self.stack), tag)
            self.current[key] = ""
        if tag not in _VOID:
            self.stack.append(tag)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in _VOID and self.stack:
            self.handle_endtag(tag)

    def handle_data(self, data):
        if self.capture and self.current is not None:
            self.current[self.capture[0]] += data

    def handle_endtag(self, tag):
        if not self.stack or tag in _VOID:
            return
        if self.stack[-1] != tag:
            self.invalid = True
            return
        self.stack.pop()
        if self.capture and len(self.stack) == self.capture[1] and tag == self.capture[2]:
            self.capture = None
        if tag == "a":
            if self.current is None or self.capture:
                self.invalid = True
            else:
                self.rows.append(self.current)
                self.current = None
        if not self.stack:
            self.closed += 1


def parse_list_page(html):
    """Return validated ID/title/day rows or None; never infer a time from the URL."""
    if not isinstance(html, str) or not html or len(html) > 1024 * 1024:
        return None
    parser = _Listing()
    try:
        parser.feed(html)
        parser.close()
    except (ValueError, RecursionError):
        return None
    if (parser.invalid or parser.found != 1 or parser.closed != 1 or parser.stack
            or parser.current is not None or not 1 <= len(parser.rows) <= 100):
        return None
    result = []
    seen = set()
    for row in parser.rows:
        cid, title, day = row["id"], row["title"], row["date"]
        if (cid in seen or not isinstance(title, str) or not title.strip() or len(title) > 512
                or not isinstance(day, str) or not _day(day.strip())):
            return None
        seen.add(cid)
        result.append({"id": cid, "title": title.strip(), "date": day.strip()})
    return result
