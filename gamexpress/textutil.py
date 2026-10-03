"""Text helpers: HTML / HoYoLAB structured content -> plain text, version and link extraction."""

from __future__ import annotations

import html
import json
import re
from html.parser import HTMLParser

VERSION_RE = re.compile(r"\b(?:Version|Ver\.?|V)\s?(\d{1,2}\.\d{1,2})\b", re.I)
_QUOTED_AFTER = r"\s*[\"“”「『]([^\"“”」』\n]{2,80})[\"“”」』]"
URL_RE = re.compile(r"https?://[^\s<>\"'）)\]]+", re.I)
YOUTUBE_ID_RE = re.compile(
    r"(?:youtube\.com/(?:watch\?(?:[^\s]*&)?v=|live/|shorts/|embed/)|youtu\.be/)([A-Za-z0-9_-]{11})")


class _HTMLText(HTMLParser):
    BLOCK = {"p", "div", "br", "li", "ul", "ol", "h1", "h2", "h3", "h4", "h5", "h6", "tr", "section"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.links: list[str] = []
        self.images: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag in ("script", "style"):
            self._skip += 1
        if tag in self.BLOCK:
            self.parts.append("\n")
        if tag == "a" and a.get("href"):
            self.links.append(a["href"])
        if tag == "img" and a.get("src"):
            self.images.append(a["src"])
        if tag in ("iframe", "video") and a.get("src"):
            self.links.append(a["src"])

    def handle_endtag(self, tag):
        if tag in ("script", "style") and self._skip:
            self._skip -= 1
        if tag in self.BLOCK:
            self.parts.append("\n")

    def handle_data(self, data):
        if not self._skip:
            self.parts.append(data)


def html_to_text(raw: str) -> tuple[str, list[str], list[str]]:
    """Return (text, links, images) from an HTML fragment."""
    p = _HTMLText()
    try:
        p.feed(raw or "")
        p.close()
    except Exception:  # malformed HTML: fall back to tag stripping
        return clean_text(re.sub(r"<[^>]+>", "\n", html.unescape(raw or ""))), [], []
    return clean_text("".join(p.parts)), dedupe(p.links), dedupe(p.images)


def structured_to_text(structured: str) -> tuple[str, list[str], list[str]]:
    """HoYoLAB 'structured_content' (Quill delta JSON) -> (text, links, images).

    getPostFull sometimes returns content == 'en-us' (a HoYoLAB quirk — the
    real body is only in structured_content)."""
    try:
        ops = json.loads(structured or "[]")
    except (json.JSONDecodeError, TypeError):
        return "", [], []
    parts: list[str] = []
    links: list[str] = []
    images: list[str] = []
    for op in ops if isinstance(ops, list) else []:
        ins = op.get("insert") if isinstance(op, dict) else None
        attrs = (op.get("attributes") or {}) if isinstance(op, dict) else {}
        if isinstance(ins, str):
            parts.append(ins)
            if attrs.get("link"):
                links.append(attrs["link"])
        elif isinstance(ins, dict):
            if ins.get("image"):
                images.append(ins["image"])
            if ins.get("video"):
                links.append(ins["video"])
    return clean_text("".join(parts)), dedupe(links), dedupe(images)


# Characters that must never reach a Discord card. Scraped text passes through here, and these
# are invisible or layout-controlling: C0/C1 controls, zero-width joiners/spaces, the bidi
# overrides (U+202A-202E, U+2066-2069) that can display "NEWS" as "SWEN" or hide a URL's real
# host inside a line of text, and the BOM. Stripping them keeps a card honest about what it
# says. \n and \t are kept - they are real formatting.
_INVISIBLE = re.compile(
    "[\u0000-\u0008\u000b\u000c\u000e-\u001f\u007f-\u009f"
    "\u200b-\u200f\u202a-\u202e\u2060-\u2064\u2066-\u2069\ufeff]"
)


def strip_invisible(text: str) -> str:
    return _INVISIBLE.sub("", text or "")


def clean_text(text: str) -> str:
    text = html.unescape(text or "").replace("\r", "")
    text = strip_invisible(text).replace("\u00a0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def dedupe(seq):
    out, seen = [], set()
    for x in seq:
        if x and x not in seen:
            seen.add(x)
            out.append(x)
    return out


def find_versions(text: str) -> list[str]:
    return dedupe(m.group(1) for m in VERSION_RE.finditer(text or ""))


def find_version(text: str) -> str | None:
    v = find_versions(text)
    return v[0] if v else None


def find_version_name(text: str, version: str | None) -> str | None:
    """Version 4.5 "To Roll the Stars in Astropolis"  ->  To Roll the Stars in Astropolis"""
    if not text:
        return None
    if version:
        v = re.escape(version)
        for rx in (r"(?:Version|Ver\.?|V)\s?" + v + _QUOTED_AFTER,
                   r"[\"“「『]([^\"”」』\n]{2,80})[\"”」』]\s*(?:Version|Ver\.?|V)\s?" + v):
            m = re.search(rx, text, re.I)
            if m:
                name = m.group(1).strip().rstrip(".,!")
                if not re.search(r"special|program|broadcast", name, re.I):
                    return name
    return None


def version_key(v: str | None) -> tuple[int, int]:
    try:
        a, b = (v or "0.0").split(".")[:2]
        return int(a), int(b)
    except ValueError:
        return (0, 0)


def bump_minor(v: str) -> str:
    a, b = version_key(v)
    return f"{a}.{b + 1}"


def short_version(tag: str | None) -> str | None:
    """'7.1.0' -> '7.1'"""
    if not tag:
        return None
    m = re.match(r"(\d+)\.(\d+)", tag)
    return f"{int(m.group(1))}.{int(m.group(2))}" if m else None


def find_urls(text: str) -> list[str]:
    return dedupe(u.rstrip(".,!?;:") for u in URL_RE.findall(text or ""))


def youtube_id(url_or_text: str) -> str | None:
    m = YOUTUBE_ID_RE.search(url_or_text or "")
    return m.group(1) if m else None


def youtube_video_url(links: list[str], text: str = "") -> str | None:
    for candidate in list(links) + find_urls(text):
        vid = youtube_id(candidate)
        if vid:
            return f"https://www.youtube.com/watch?v={vid}"
    return None


def twitch_url(links: list[str], text: str = "") -> str | None:
    for candidate in list(links) + find_urls(text):
        if re.search(r"twitch\.tv/[A-Za-z0-9_]+", candidate):
            return candidate.split("?")[0].rstrip("/")
    return None


_SENT_SPLIT = re.compile(r"(?<!\bVer\.)(?<!\bNo\.)(?<!approx\.)(?<!\bvs\.)(?<=[.!?。！？])\s+(?=\S)")


def sentences(text: str) -> list[str]:
    """Split into sentence-ish chunks: lines, HoYoverse section markers (〓Title〓 ▌ ■ ●),
    then sentence punctuation (abbreviations like 'Ver. 4.6' stay intact)."""
    text = re.sub(r"〓([^〓\n]{1,60})〓", r"\n\1\n", text or "")
    text = re.sub(r"\s*[▌■●]\s*", "\n", text)
    out: list[str] = []
    for line in text.split("\n"):
        line = line.strip(" ※")
        if not line:
            continue
        for part in _SENT_SPLIT.split(line):
            part = part.strip()
            if part:
                out.append(part)
    return out


def truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)].rstrip() + "…"
