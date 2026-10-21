"""Optional news-description timestamp conversion into Discord ``<t:EPOCH:f>`` tokens.

Design invariants:
  * Disabled by default (`NEWS_TIMESTAMPS=0`): callers bypass scanning entirely,
    and calling `convert_news_timestamps(..., enabled=False)` returns input untouched.
  * Render-only: never mutates `Item`, `article_blocks`, raw HTML/JSON/XML, or state.
  * Never touches `gamexpress/timeparse.py` schedule defaults or consumers.
  * Explicit timezone in the source text always wins; explicit `"server time"` uses
    the approved `UTC+8` fallback; expressions with neither an explicit timezone nor
    `"server time"` are left unchanged (never guess UTC or UTC+8 on bare clock prose).
  * Date-only expressions, `"After the update"`, approximate times, unresolved ranges,
    and non-prose spans (Discord tokens, URLs, Markdown link targets, inline/fenced code)
    are preserved verbatim.
"""

from __future__ import annotations

import calendar
import re
from datetime import datetime, timedelta, timezone

SERVER_TZ = timezone(timedelta(hours=8))

_MONTHS: dict[str, int] = {
    "jan": 1, "january": 1,
    "feb": 2, "february": 2,
    "mar": 3, "march": 3,
    "apr": 4, "april": 4,
    "may": 5,
    "jun": 6, "june": 6,
    "jul": 7, "july": 7,
    "aug": 8, "august": 8,
    "sep": 9, "sept": 9, "september": 9,
    "oct": 10, "october": 10,
    "nov": 11, "november": 11,
    "dec": 12, "december": 12,
}

# Fixed-offset timezone abbreviations matching gamexpress.timeparse.TZ_OFFSETS.
# Bare "CST" without a UTC/GMT offset is excluded because prose varies between UTC-6 and UTC+8.
_NAMED_TZ_HOURS: dict[str, float] = {
    "UTC": 0.0,
    "GMT": 0.0,
    "PST": -8.0,
    "PDT": -7.0,
    "MST": -7.0,
    "MDT": -6.0,
    "EST": -5.0,
    "EDT": -4.0,
    "JST": 9.0,
    "KST": 9.0,
    "SGT": 8.0,
    "HKT": 8.0,
    "AEST": 10.0,
    "AEDT": 11.0,
    "BST": 1.0,
    "CET": 1.0,
    "CEST": 2.0,
}

_PROTECTED_RE = re.compile(
    r"```[\s\S]*?```"                                       # fenced code block
    r"|`[^`\n]+`"                                           # inline code span
    r"|<t:-?\d+(?::[tTdDfFR])?>"                            # existing Discord timestamp
    r"|<a?:\w{2,32}:\d{15,25}>"                             # custom emoji
    r"|<@!?\d+>|<@&\d+>|<#\d+>"                             # user/role/channel mention
    r"|\[[^\]\n]+\]\(https?://[^)\s]+\)"                    # markdown link [label](url)
    r"|<https?://[^>\s]+>"                                  # autolink <https://...>
    r"|https?://[^\s<>()]+"                                 # bare URL
)

_MONTH_PAT = (
    r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
    r"Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\.?"
)

_TZ_CORE = (
    r"(?:"
    r"(?:UTC|GMT)\s*(?:[+-−]\s*\d{1,2}(?::\d{2})?)?"
    r"|server\s+time"
    r"|(?:PST|PDT|MST|MDT|EST|EDT|JST|KST|SGT|HKT|AEST|AEDT|BST|CET|CEST)\b"
    r")"
)

# Single-pass candidate matcher: runs ONCE per prose slice in strict O(N) time.
_CANDIDATE_DT_RE = re.compile(
    r"(?:"
    r"(?P<ymd>\d{4}[./-]\d{1,2}[./-]\d{1,2})"
    rf"|(?P<mdy>{_MONTH_PAT}\s+\d{{1,2}}(?:st|nd|rd|th)?(?:,?\s+\d{{4}})?)"
    rf"|(?P<dmy>\d{{1,2}}(?:st|nd|rd|th)?\s+{_MONTH_PAT}(?:,?\s+\d{{4}})?)"
    r"|(?P<md>(?<!\d)\d{1,2}/\d{1,2}(?![/\d]))"
    r")"
    r"(?:\s*(?:,|\bat\b)\s*|\s+)"
    r"(?P<hh>\d{1,2}):(?P<mm>\d{2})(?::(?P<ss>\d{2}))?(?:\s*(?P<ampm>[AaPp]\.?[Mm]\.?))?"
    rf"(?:\s*(?:\(\s*(?P<tzp>{_TZ_CORE})\s*\)|(?P<tzb>{_TZ_CORE})))?",
    re.I,
)

_RANGE_BETWEEN_RE = re.compile(r"^\s*(?:[–—~]|-(?!\d)|\bto\b|\buntil\b)\s*$", re.I)

# Anchored tail matcher checked ONLY right after `m.end()` for same-date ranges like:
#   "2026/09/28 06:00 – 11:00 (UTC+8)"
_SAME_DATE_TAIL_RE = re.compile(
    r"(?P<sep>\s*(?:[–—~]|-(?!\d)|\bto\b|\buntil\b)\s*)"
    r"(?P<hh>\d{1,2}):(?P<mm>\d{2})(?::(?P<ss>\d{2}))?(?:\s*(?P<ampm>[AaPp]\.?[Mm]\.?))?"
    rf"\s*(?:\(\s*(?P<tzp>{_TZ_CORE})\s*\)|(?P<tzb>{_TZ_CORE}))",
    re.I,
)

_APPROX_PREFIX_RE = re.compile(
    r"(?:around|approx(?:\.|imately)?|about|roughly|circa|est(?:\.|imated)?|[~≈])\s*$",
    re.I,
)
_APPROX_WORDS_RE = re.compile(
    r"\b(?:around|approx(?:\.|imately)?|about|roughly|circa|estimated)\b|[~≈]",
    re.I,
)


def _parse_tz(raw: str | None) -> timezone | None:
    if not raw:
        return None
    cleaned = raw.strip().replace("−", "-")
    low = re.sub(r"\s+", " ", cleaned.lower())
    if low == "server time":
        return SERVER_TZ
    m = re.fullmatch(r"(?:utc|gmt)\s*([+-])\s*(\d{1,2})(?::(\d{2}))?", low)
    if m:
        sign = 1 if m.group(1) == "+" else -1
        hours = int(m.group(2))
        mins = int(m.group(3) or 0)
        if hours > 14 or mins > 59 or (hours == 14 and mins > 0):
            return None
        return timezone(sign * timedelta(hours=hours, minutes=mins))
    upper = cleaned.upper()
    if upper in _NAMED_TZ_HOURS:
        return timezone(timedelta(hours=_NAMED_TZ_HOURS[upper]))
    return None


def _parse_time_parts(gd: dict[str, str | None]) -> tuple[int, int, int] | None:
    hh = int(gd["hh"] or 0)
    mm = int(gd["mm"] or 0)
    ss = int(gd["ss"] or 0)
    ampm = (gd.get("ampm") or "").replace(".", "").upper()
    if mm > 59 or ss > 59:
        return None
    if ampm:
        if not 1 <= hh <= 12:
            return None
        if ampm == "AM":
            hh = 0 if hh == 12 else hh
        else:
            hh = 12 if hh == 12 else hh + 12
    elif not 0 <= hh <= 23:
        return None
    return hh, mm, ss


def _parse_date_parts(gd: dict[str, str | None]) -> tuple[int | None, int, int] | None:
    ymd = gd.get("ymd")
    if ymd:
        parts = re.split(r"[./-]", ymd)
        return int(parts[0]), int(parts[1]), int(parts[2])
    mdy = gd.get("mdy")
    if mdy:
        m = re.match(r"([A-Za-z]+)\.?\s+(\d{1,2})(?:st|nd|rd|th)?(?:,?\s+(\d{4}))?$", mdy.strip())
        if not m:
            return None
        month = _MONTHS.get(m.group(1).lower())
        if not month:
            return None
        return (int(m.group(3)) if m.group(3) else None), month, int(m.group(2))
    dmy = gd.get("dmy")
    if dmy:
        m = re.match(r"(\d{1,2})(?:st|nd|rd|th)?\s+([A-Za-z]+)\.?(?:,?\s+(\d{4}))?$", dmy.strip())
        if not m:
            return None
        month = _MONTHS.get(m.group(2).lower())
        if not month:
            return None
        return (int(m.group(3)) if m.group(3) else None), month, int(m.group(1))
    md = gd.get("md")
    if md:
        m_s, d_s = md.split("/")
        return None, int(m_s), int(d_s)
    return None


def _build_dt(
    year: int | None,
    month: int,
    day: int,
    hms: tuple[int, int, int],
    tz: timezone,
    published_ts: int,
) -> datetime | None:
    if not 1 <= month <= 12 or not 1 <= day <= 31:
        return None
    hh, mm, ss = hms
    if year is not None:
        if not 1990 <= year <= 2100:
            return None
        max_day = calendar.monthrange(year, month)[1]
        if day > max_day:
            return None
        return datetime(year, month, day, hh, mm, ss, tzinfo=tz)
    if not published_ts or published_ts <= 0:
        return None
    pub = datetime.fromtimestamp(published_ts, tz)
    candidates: list[datetime] = []
    for cand_year in (pub.year - 1, pub.year, pub.year + 1):
        if day <= calendar.monthrange(cand_year, month)[1]:
            candidates.append(datetime(cand_year, month, day, hh, mm, ss, tzinfo=tz))
    if not candidates:
        return None
    same = next((c for c in candidates if c.year == pub.year), None)
    if same is not None:
        delta_days = (same - pub).total_seconds() / 86400.0
        if delta_days < -120:
            later = next((c for c in candidates if c.year == pub.year + 1), None)
            if later is not None:
                return later
        elif delta_days > 245:
            earlier = next((c for c in candidates if c.year == pub.year - 1), None)
            if earlier is not None:
                return earlier
        return same
    return min(candidates, key=lambda c: abs((c - pub).total_seconds()))


def _is_approximate(segment: str, match_start: int, matched: str) -> bool:
    prefix = segment[max(0, match_start - 24):match_start]
    return bool(_APPROX_PREFIX_RE.search(prefix) or _APPROX_WORDS_RE.search(matched))


def _replace_prose_segment(segment: str, published_ts: int) -> str:
    """Single-pass O(N) scan across one unprotected prose slice."""
    if ":" not in segment:
        return segment
    matches = list(_CANDIDATE_DT_RE.finditer(segment))
    if not matches:
        return segment

    edits: list[tuple[int, int, str]] = []
    idx = 0
    total = len(matches)
    while idx < total:
        m1 = matches[idx]
        s1, e1 = m1.span()
        gd1 = m1.groupdict()

        # Check two-date range `<dt1> <sep> <dt2>` with adjacent candidate match `m2`.
        if idx + 1 < total:
            m2 = matches[idx + 1]
            s2, e2 = m2.span()
            between = segment[e1:s2]
            if _RANGE_BETWEEN_RE.match(between) and not _is_approximate(segment, s1, segment[s1:e2]):
                gd2 = m2.groupdict()
                tz2 = _parse_tz(gd2.get("tzp") or gd2.get("tzb"))
                tz1 = _parse_tz(gd1.get("tzp") or gd1.get("tzb")) or tz2
                d1 = _parse_date_parts(gd1)
                t1 = _parse_time_parts(gd1)
                d2 = _parse_date_parts(gd2)
                t2 = _parse_time_parts(gd2)
                if tz1 and tz2 and d1 and t1 and d2 and t2:
                    dt1 = _build_dt(d1[0], d1[1], d1[2], t1, tz1, published_ts)
                    if dt1 is not None:
                        if d2[0] is None:
                            dt2 = _build_dt(dt1.year, d2[1], d2[2], t2, tz2, published_ts)
                            if dt2 is not None and dt2 < dt1:
                                dt2 = _build_dt(dt1.year + 1, d2[1], d2[2], t2, tz2, published_ts)
                        else:
                            dt2 = _build_dt(d2[0], d2[1], d2[2], t2, tz2, published_ts)
                        if dt2 is not None and int(dt2.timestamp()) >= int(dt1.timestamp()):
                            edits.append((s1, e2, f"<t:{int(dt1.timestamp())}:f>{between}<t:{int(dt2.timestamp())}:f>"))
                            idx += 2
                            continue

        # Check anchored same-date range `<dt1> <sep> <time2> <tz2>` right at `e1`.
        tail = _SAME_DATE_TAIL_RE.match(segment, e1)
        if tail and not _is_approximate(segment, s1, segment[s1:tail.end()]):
            gdt = tail.groupdict()
            tz2 = _parse_tz(gdt.get("tzp") or gdt.get("tzb"))
            tz1 = _parse_tz(gd1.get("tzp") or gd1.get("tzb")) or tz2
            d1 = _parse_date_parts(gd1)
            t1 = _parse_time_parts(gd1)
            t2 = _parse_time_parts(gdt)
            if tz1 and tz2 and d1 and t1 and t2:
                dt1 = _build_dt(d1[0], d1[1], d1[2], t1, tz1, published_ts)
                if dt1 is not None:
                    dt2 = _build_dt(dt1.year, d1[1], d1[2], t2, tz2, published_ts)
                    if dt2 is not None and int(dt2.timestamp()) >= int(dt1.timestamp()):
                        edits.append((s1, tail.end(), f"<t:{int(dt1.timestamp())}:f>{gdt['sep']}<t:{int(dt2.timestamp())}:f>"))
                        idx += 1
                        continue

        # Check standalone datetime with explicit TZ or "server time".
        tz1 = _parse_tz(gd1.get("tzp") or gd1.get("tzb"))
        if tz1 and not _is_approximate(segment, s1, m1.group(0)):
            d1 = _parse_date_parts(gd1)
            t1 = _parse_time_parts(gd1)
            if d1 and t1:
                dt1 = _build_dt(d1[0], d1[1], d1[2], t1, tz1, published_ts)
                if dt1 is not None:
                    edits.append((s1, e1, f"<t:{int(dt1.timestamp())}:f>"))
        idx += 1

    if not edits:
        return segment
    out: list[str] = []
    pos = 0
    for s, e, rep in edits:
        out.append(segment[pos:s])
        out.append(rep)
        pos = e
    out.append(segment[pos:])
    return "".join(out)


def convert_news_timestamps(text: str, *, published_ts: int = 0, enabled: bool = False) -> str:
    """Convert exact news-description datetimes into Discord ``<t:EPOCH:f>`` tokens.

    When ``enabled`` is ``False`` (the default), returns ``text`` directly with zero
    regex scanning or allocation.
    """
    if not enabled or not text:
        return text
    out: list[str] = []
    pos = 0
    for m in _PROTECTED_RE.finditer(text):
        s, e = m.span()
        if s > pos:
            out.append(_replace_prose_segment(text[pos:s], published_ts))
        out.append(m.group(0))
        pos = e
    if pos < len(text):
        out.append(_replace_prose_segment(text[pos:], published_ts))
    return "".join(out)
