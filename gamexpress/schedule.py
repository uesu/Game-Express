"""Version-schedule announcements: detect → extract → merge → post once → keep the card accurate.

Posting only happens on a keyword/pattern match (special program / special broadcast /
livestream announcement, or an official update-maintenance notice) — never daily.

Accuracy rules:
  * official posts (HoYoLAB / official X / Kuro) and config/overrides.json always win;
    countdown and learned-cadence fallbacks are visibly labelled estimated.
  * unknown values render as TBA; banners always carry (STC).
  * one card per game+version; later official info (maintenance notice, pre-install,
    banner notice, overrides edits) EDITS the same message silently (no re-ping).
"""

from __future__ import annotations

import logging
import math
import re
from dataclasses import dataclass, field
from statistics import median

from .cards import ESTIMATE_LABELS, mark_test, schedule_payload
from .config import Game
from .discord import webhook_fingerprint
from .media import rank, youtube_thumb
from .models import Item
from .sources.bannerfeed import banner_feed_for
from .sources.codes import extract_codes_from_text
from .state import stable_hash
from .textutil import (
    bump_minor,
    find_version,
    find_version_name,
    sentences,
    twitch_url,
    version_key,
    youtube_video_url,
)
from .timeparse import find_datetimes, find_duration_hours, find_time_ranges, parse_iso

log = logging.getLogger("gamexpress.schedule")

MAINT_RE = re.compile(
    r"update\s+(?:and\s+)?maintenance|maintenance\s+(?:notice|preview|details|announcement|time)|"
    r"update\s+details|version\s+update\s+(?:notice|details)|pre-?install(?:ation)?|pre-?download|pre-?load",
    re.I)
PROGRAM_EXCLUDE = re.compile(
    r"\b(recap|replay|re-?watch|highlights?|vod|thank(?:s| you) for (?:watching|tuning)|has ended|"
    r"codes? (?:are|is) (?:now )?(?:live|available|here))\b", re.I)
NOT_PROGRAM_TITLE = re.compile(
    r"\b(?:(?:prize|sharing|fan[- ]?art|creation|community|login|check-?in|web|in-?game|"
    r"time-?limited|lucky|anniversary|redeem(?:ption)?)\s+events?|event\s+prizes?|participate|"
    r"winners?|giveaway|redemption\s+cod(?:e|es)|update\s+(?:details|and\s+maintenance)|"
    r"maintenance\s+notice|version\s+update|hotfix|bug\s+fix(?:es)?|compensation\s+"
    r"(?:notice|details)|merchandise|recap|replay|vod|survey|questionnaire|thank\s+you|"
    r"collaboration|insider\s+channel|combat\s+intro|character\s+demo)\b", re.I)
DEFAULT_BANNER_RE = (r"event\s+wish|event\s+warp|signal\s+search|exclusive\s+channel|featured\s+resonator|"
                     r"resonator\s+convene|character\s+event|limited[-\s]time\s+(?:character|agent)")

# --------------------------------------------------------------------- X-first announcement test
# X is the PRIMARY schedule source, so this test has to be tight. One positive requirement does
# most of the work: an announcement says WHEN it airs. That is what separates a real announcement
# from the posts that merely mention one —
#   "Insider Channel: Special Program | Signs of Imprisonment: Part Three"  -> no air time (lore)
#   "[Prize Event] ... the Version 3.2 Special Program will air on August 28" -> prize-event title
#   "Follow @Wuthering_Waves and repost. 10 winners will be chosen..."        -> giveaway INSIDE the
#        real 3.7 announcement, so the giveaway words must not be allowed to veto it
PROGRAM_AIR = re.compile(
    r"\b(?:will\s+(?:premiere|begin|air|release|start|go\s+live|be\s+broadcast|be\s+available)|"
    r"is\s+scheduled\s+to\s+air|scheduled\s+for|airing\s+on|premieres?\s+on|"
    r"livestream\s+starts?|tune\s+in\s+(?:on|at)|starts?\s+(?:on|at)\b)", re.I)
AIR_DATE = re.compile(
    r"\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4}|\d{4}-\d{1,2}-\d{1,2}|"
    r"\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.?\s+\d{1,2}", re.I)
# Only the HEADLINE is screened for "this is some other kind of post". Every real announcement
# quotes its own giveaways and redemption codes in the body, so screening the whole text would
# reject all four of them (GI drops codes, WW runs a gift-card draw, ZZZ drops a code).
HEADLINE_LEN = 160


def is_program_announcement(game: Game, text: str, title: str = "") -> bool:
    """Strict positive test for 'this post IS the version's Special Program announcement'.

    Three things must all hold: the game's own phrase for its livestream, a stated air time, and
    a headline that is not some other kind of post. Verified against the four real 2026-09
    announcements (GI 7.1, HSR 4.6, ZZZ 3.2, WW 3.7) and against the three posts that used to
    steal the card's link."""
    body = text or ""
    if not _any(program_patterns(game), f"{title}\n{body}"):
        return False
    if title and NOT_PROGRAM_TITLE.search(title):
        return False
    if NOT_PROGRAM_TITLE.search(body[:HEADLINE_LEN]):
        return False
    if PROGRAM_EXCLUDE.search(body):
        return False
    return bool(PROGRAM_AIR.search(body)) and bool(AIR_DATE.search(body))


PRE_WORDS = re.compile(r"pre-?install|pre-?download|pre-?installation|pre-?load", re.I)
MAINT_WORDS = re.compile(r"maintenance|update\s+time|update\s+schedule|^begins?\s+at|^starts?\s+at|downtime", re.I)
MAINT_EXCLUDE = re.compile(
    r"compensation|claim|eligib|reached|reach\s|purchase|top-?up|expire|event\s+(?:period|duration)|"
    r"will\s+end|ends?\s+at|until|closed|deadline|reset", re.I)
COMP_RE = re.compile(r"(?:Maintenance\s+)?Compensation\s*[:：]\s*([^\n(（]{3,80})", re.I)
FIVE_RE = re.compile(r"(?:5[-\s]?star|5\s?★|★\s?5|S[-\s]?Rank)\s+(?:limited[-\s]?(?:time\s+)?)?(?:event[-\s]exclusive\s+)?"
                     r"(?:character|resonator|agent)s?", re.I)
FOUR_RE = re.compile(r"(?:4[-\s]?star|4\s?★|★\s?4|A[-\s]?Rank)\s+(?:character|resonator|agent)s?", re.I)
QUOTED = re.compile(r"[\"“「『]([^\"”」』\n]{2,40})[\"”」』]")
PHASE1 = re.compile(r"phase\s*(?:I|1)\b(?!I)|first\s+(?:half|phase)|1st\s+(?:half|phase)", re.I)
PHASE2 = re.compile(r"phase\s*(?:II|2)\b|second\s+(?:half|phase)|2nd\s+(?:half|phase)", re.I)

# HoYoverse notices label their numbers with bracketed section headers and put the VALUE ON THE
# NEXT LINE, so a sentence scanner sees "2026-09-09 06:00 (UTC+8) : We estimate this will take five
# hours." with no "maintenance" anywhere in it and throws the time away. Read label+value as a pair.
# Reference: ZZZ 3.2 (HoYoLAB 46604333) -- "[Version Update Time]" / "[Pre-Download Period]".
LABELLED = re.compile(
    r"[\[【〓]?\s*(pre-?download\s+period|pre-?install(?:ation)?\s+(?:period|time)|"
    r"version\s+update\s+time|update\s+maintenance\s+(?:time|information)|maintenance\s+time)"
    r"\s*[\]】〓]?\s*[:：]?\s*([^\n]{0,140})", re.I)
# "[Pre-Installation Details]" is followed by storage sizes, not a clock -- never read those.
LABEL_NO_TIME = re.compile(r"storage|space|GB|file\s+size|download\s+size", re.I)

# precedence of sources for a field (higher wins). Derived values are below external countdown
# estimates; the banner feed is the lowest (5). Any official source or override replaces both.
PRIORITY = {"override": 100, "hoyolab": 50, "kuro": 50, "news": 45, "x": 40, "launcher": 20,
            "countdown": 10, "pattern": 9, "bannerfeed": 5}
ESTIMATED_KEYS = ("program_ts", "preinstall_ts", "maint_start_ts", "maint_end_ts")
MAINT_HOURS_ESTIMATE = 5          # typical HoYoverse / Kuro maintenance window

# Cold-start pre-install leads, measured from maintenance START. Once this installation has seen
# a real pre-install + maintenance pair for a game, observed_lead_h() supplies that game's median
# instead. A derived value is never recorded as an observation, so the fallback cannot teach itself.
PREINSTALL_LEAD_H = {
    "genshin": 43,                 # GI 7.1: Mon 11:00 -> Wed 06:00 (UTC+8)
    "starrail": 88,                # HSR 4.6: Thu 14:00 -> Mon 06:00 (UTC+8)
    "zzz": 42,                     # ZZZ 3.2: Mon 12:00 -> Wed 06:00 (UTC+8)
    "wuwa": 42,                    # WW 3.7: Mon 10:00 -> Wed 04:00 (UTC+8)
}
MAX_LEAD_H = 14 * 24               # reject corrupt/outlier observations (e.g. a mis-parsed 700 h)


@dataclass
class Extract:
    item: Item
    kind: str                         # program | maintenance | banner
    version: str | None
    version_inferred: bool = False
    fields: dict = field(default_factory=dict)


# --------------------------------------------------------------------------- classification
def _any(patterns: list[str], text: str) -> bool:
    return any(re.search(p, text, re.I) for p in patterns if p)


def program_patterns(game: Game) -> list[str]:
    return [re.escape(p) if not any(ch in p for ch in "\\[]()?*+|") else p for p in game.program_patterns]


def wants(game: Game):
    """Combined pre-filter used before fetching full posts (schedule + codes share it)."""
    pats = program_patterns(game) + [MAINT_RE.pattern, DEFAULT_BANNER_RE] + game.banner_patterns + \
        [r"redemption\s+codes?|redeem\s+codes?|\bcodes?\s*[:：]"]
    rx = re.compile("|".join(f"(?:{p})" for p in pats), re.I)
    return lambda text: bool(rx.search(text or ""))


def classify(game: Game, item: Item) -> str | None:
    lead = f"{item.title}\n{item.text[:400]}"
    if MAINT_RE.search(item.title or "") or (item.source == "x" and MAINT_RE.search(lead)):
        return "maintenance"
    if _any(program_patterns(game), lead) and not PROGRAM_EXCLUDE.search(lead) \
            and not NOT_PROGRAM_TITLE.search(item.title or "") \
            and not extract_codes_from_text(lead):      # a codes post is not an announcement
        return "program"
    banner_rx = "|".join([DEFAULT_BANNER_RE] + game.banner_patterns)
    if re.search(banner_rx, item.title or item.text[:200], re.I):
        return "banner"
    if MAINT_RE.search(lead):
        return "maintenance"
    return None


# --------------------------------------------------------------------------- extraction
def extract_program(game: Game, item: Item) -> dict:
    text = item.full
    ref = item.published_ts or None
    prog_rx = re.compile("|".join(program_patterns(game) + [r"premiere", r"\bair\b", r"livestream", r"broadcast",
                                                           r"will (?:begin|release|start)"]), re.I)
    ts = None
    for s in sentences(text):
        if prog_rx.search(s):
            found = find_datetimes(s, ref)
            if found:
                ts = found[0].ts
                break
    head = item.title if item.title else item.text[:240]
    if ts is None and _any(program_patterns(game), head):
        found = find_datetimes(text, ref)            # the post IS the announcement
        ts = found[0].ts if found else None
    if ts and item.published_ts and not (item.published_ts - 86400 <= ts <= item.published_ts + 45 * 86400):
        ts = None  # a date far from the post date is not this program's air time
    f: dict = {}
    if ts:
        f["program_ts"] = ts
    m = re.search(r"special\s+broadcast|special\s+program|livestream|showcase", text, re.I)
    if m:
        f["program_name"] = " ".join(w.capitalize() for w in m.group(0).split())
    yt = youtube_video_url(item.links, text)
    if yt:
        f["youtube_video"] = yt
    tw = twitch_url(item.links, text)
    if tw:
        f["twitch_live"] = tw
    if item.images:
        f["images"] = item.images[:4]
    return f


def extract_labelled(text: str, ref: int | None) -> dict:
    """Times that sit UNDER a bracketed section header instead of inside their own sentence.

    ZZZ 3.2 (HoYoLAB 46604333) is the case that motivated this: its maintenance start and its
    whole pre-download window are label/value pairs, so the sentence scanner saw neither and the
    card showed TBA for both even though the official notice stated them plainly.
    """
    f: dict = {}
    for m in LABELLED.finditer(text):
        label, value = m.group(1).lower(), m.group(2)
        if LABEL_NO_TIME.search(value):
            continue
        if label.startswith("pre-"):
            rngs = find_time_ranges(value, ref)
            if rngs:
                f.setdefault("preinstall_ts", rngs[0][0])
                continue
            found = find_datetimes(value, ref)
            if found:
                f.setdefault("preinstall_ts", found[0].ts)
        else:
            found = find_datetimes(value, ref)
            if found:
                f.setdefault("maint_start_ts", found[0].ts)
    return f


def extract_maintenance(item: Item) -> dict:
    text = item.full
    ref = item.published_ts or None
    f: dict = extract_labelled(text, ref)   # labelled values win; the loop only setdefaults
    for s in sentences(text):
        rngs = find_time_ranges(s, ref)
        if rngs and (MAINT_WORDS.search(s) or "maintenance" in s.lower()) and not MAINT_EXCLUDE.search(s):
            f.setdefault("maint_start_ts", rngs[0][0])
            f.setdefault("maint_end_ts", rngs[0][1])
            continue
        found = find_datetimes(s, ref)
        if not found:
            continue
        if PRE_WORDS.search(s) and not re.search(r"\b(?:end|ends|until|close|closes)\b", s, re.I):
            f.setdefault("preinstall_ts", found[0].ts)
            continue
        if MAINT_WORDS.search(s) and not MAINT_EXCLUDE.search(s):
            f.setdefault("maint_start_ts", found[0].ts)
            if len(found) > 1 and found[1].ts > found[0].ts and \
                    re.search(r"[-–~]|\bto\b|\buntil\b", s[found[0].end:found[1].start]):
                f.setdefault("maint_end_ts", found[1].ts)
    if "maint_start_ts" in f and "maint_end_ts" not in f:
        hours = find_duration_hours(text)
        if hours:
            f["maint_end_ts"] = int(f["maint_start_ts"] + hours * 3600)
    # HoYoverse posts the maintenance PREVIEW at the moment pre-install opens, so when the body
    # says "pre-installation ... is now available" the post's own timestamp IS the pre-install
    # time. Verified on GI 7.1 (HoYoLAB 46771203): created_at 1789960208, exactly 608 s after the
    # 11:00 UTC+8 open that game8 lists.
    # NOTE the phrase must be searched in title AND body. `item.title or text[:200]` short-circuits
    # to the TITLE ALONE whenever a title exists, and titles like "Version 7.1 Update Maintenance
    # Preview" never contain "pre-install" -- that one `or` was the whole gap.
    if "preinstall_ts" not in f and item.published_ts and \
            PRE_WORDS.search(f"{item.title or ''}\n{text[:400]}") and \
            re.search(r"now\s+(?:available|open)|has\s+(?:begun|started)|is\s+now\s+live", text, re.I):
        f["preinstall_ts"] = int(item.published_ts)      # "Pre-installation is now available"
    m = COMP_RE.search(text)
    if m:
        comp = m.group(1).strip(" .;,")
        if re.search(r"\d", comp):
            f["compensation"] = comp
    if item.images:
        f["notice_images"] = item.images[:1]
    return f


def _clean_name(raw: str) -> str:
    name = re.sub(r"\s*[\(（][^)）]*[\)）]\s*", "", raw).strip(" .,;:!")
    return name if 1 < len(name) <= 40 and not re.search(r"https?://|\d{3,}", name) else ""


# words that never appear in a character name — a "name" containing one is an extraction slip
NOT_A_NAME = {
    "character", "characters", "resonator", "resonators", "agent", "agents", "banner", "banners",
    "wish", "wishes", "warp", "warps", "convene", "convenes", "signal", "search", "event", "events",
    "weapon", "weapons", "cone", "cones", "w-engine", "w-engines", "engine", "version", "phase", "half",
    "tba", "tbd", "unknown", "rerun", "re-run", "reruns", "boosted", "rate", "rates", "drop", "limited",
    "star", "stars", "rank", "s-rank", "a-rank", "exclusive", "featured", "promotional", "reward", "rewards",
    "update", "maintenance", "livestream", "program", "broadcast", "http", "https", "www",
}
_NAME_CHARS = re.compile(r"[^\W\d_][\w'’.\-&•·: ]*")


def plausible_name(name: str) -> bool:
    """True for something that can be a character name: starts with a letter, ≤ 32 chars,
    1-6 words, letters/digits/space/'-.&•·: only, no 3+ digit runs, no generic words
    ('Event', 'Wish', 'Character' …). 'March 7th', 'Soldier 11', 'Topaz & Numby',
    'Dan Heng • Imbibitor Lunae' pass; 'Event Wish', '2026', 'Character Event' don't."""
    if not name or len(name) > 32 or re.search(r"\d{3,}", name) or not _NAME_CHARS.fullmatch(name):
        return False
    words = [w for w in re.split(r"[\s•·&:]+", name) if w]
    if not 1 <= len(words) <= 6:
        return False
    return not any(w.lower().strip(".'’-") in NOT_A_NAME for w in words)


def extract_banner(item: Item) -> dict:
    """Conservative: only quoted names that directly follow '5-star character' /
    'S-Rank Agent' / '5-star Resonator' (and 4★ equivalents). Weapons never match.
    A 4★ list that contains anything implausible (or a name that is also a 5★) is flagged
    `banner_four_unsure` -> the card shows TBA instead of a possibly wrong list."""
    text = item.full
    five: list[str] = []
    four: list[str] = []
    four_unsure = False
    for s in sentences(text):
        for rx, bucket in ((FIVE_RE, five), (FOUR_RE, four)):
            m = rx.search(s)
            if not m:
                continue
            tail = s[m.end(): m.end() + 260]
            other = (FOUR_RE if rx is FIVE_RE else FIVE_RE).search(tail)
            if other:                                   # stop at the next star tier
                tail = tail[: other.start()]
            tail = re.split(r"\b(?:weapon|light\s+cone|w-engine|will\s+receive|drop[-\s]rate)\b", tail, flags=re.I)[0]
            for q in QUOTED.findall(tail):
                n = _clean_name(q)
                if not n:
                    continue
                if not plausible_name(n):
                    if bucket is four:
                        four_unsure = True
                    continue
                if n not in bucket:
                    bucket.append(n)
    if any(n in five for n in four):
        four_unsure = True
        four = [n for n in four if n not in five]
    if not five and not four and not four_unsure:
        return {}
    phase = 1 if PHASE1.search(item.full[:600]) else 2 if PHASE2.search(item.full[:600]) else None
    return {"banner_five": five, "banner_four": four, "banner_four_unsure": four_unsure, "banner_phase": phase}


def extract(game: Game, item: Item) -> Extract | None:
    kind = classify(game, item)
    if not kind:
        return None
    version = find_version(f"{item.title}\n{item.text}")
    if kind == "program":
        fields = extract_program(game, item)
        if "program_ts" not in fields:
            return None                       # no air time -> not an announcement we can post
        vn = find_version_name(item.full, version)
        if vn:
            fields["version_name"] = vn
    elif kind == "maintenance":
        fields = extract_maintenance(item)
        if not fields.get("maint_start_ts") and not fields.get("preinstall_ts"):
            return None
    else:
        fields = extract_banner(item)
        if not fields:
            return None
    return Extract(item=item, kind=kind, version=version, fields=fields)


# --------------------------------------------------------------------------- merging
def infer_versions(extracts: list[Extract], live: str | None, records: dict) -> None:
    """Fill missing versions (e.g. Genshin tweets say 'the new version'): match another
    program post within 3 h, else a tracked record within 3 h, else live+0.1."""
    known = [e for e in extracts if e.version and e.kind == "program"]
    for e in extracts:
        if e.version:
            continue
        pts = e.fields.get("program_ts")
        if e.kind == "program" and pts:
            match = next((k for k in known if abs((k.fields.get("program_ts") or 0) - pts) <= 3 * 3600), None)
            if match:
                e.version = match.version
                continue
            rec = next((v for v, r in records.items()
                        if abs(((r.get("data") or {}).get("program_ts") or 0) - pts) <= 3 * 3600), None)
            if rec:
                e.version = rec
                continue
            if live:
                e.version, e.version_inferred = bump_minor(live), True


def _to_ts(value) -> int | None:
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        return int(value)
    return parse_iso(str(value))


def _four_star_problem(game: Game, four: list[str], existing: list[str] | None,
                       sticky: str | None) -> str | None:
    """Why a 4★ list must NOT be shown (-> TBA), or None when it is trustworthy.

    An incomplete list is not by itself a reason to print TBA; extract_banner already removes
    implausible names. Wrong counts, overlap, disagreement and overrides still apply."""
    if sticky == "official sources disagree":
        return sticky
    if game.four_star_count and len(four) != game.four_star_count:
        return f"{len(four)} name(s) found, {game.four_star_count} expected"
    if existing and sorted(existing) != sorted(four):
        return "official sources disagree"
    return None


def _unmark_estimated(data: dict, key: str) -> None:
    if key in (data.get("estimated") or []):
        data["estimated"] = [k for k in data["estimated"] if k != key]
        if not data["estimated"]:
            data.pop("estimated", None)
            data.pop("estimate_sources", None)


def apply_estimates(data: dict, prov: dict, estimates: dict | None, now: int) -> list[str]:
    """Fill program / maintenance times a countdown site predicts, but ONLY fields no official
    source has given yet (PRIORITY['countdown'] is the lowest). Returns the keys it estimated."""
    if not estimates:
        return []
    added: list[str] = []
    for key in ESTIMATED_KEYS:
        ts = estimates.get(key)
        if not ts or data.get(key):
            continue
        ts = int(ts)
        if not now - 12 * 3600 <= ts <= now + 120 * 86400:      # nonsense / ancient -> ignore
            continue
        data[key] = ts
        prov[key] = [PRIORITY["countdown"], now]
        added.append(key)
    if "maint_start_ts" in added and not data.get("maint_end_ts"):
        data["maint_end_ts"] = int(data["maint_start_ts"]) + MAINT_HOURS_ESTIMATE * 3600
        prov["maint_end_ts"] = [PRIORITY["countdown"], now]
        added.append("maint_end_ts")
    if added:
        known = data.get("estimated") or []
        data["estimated"] = sorted(set(known) | set(added),
                                   key=lambda k: ESTIMATED_KEYS.index(k) if k in ESTIMATED_KEYS else 99)
        src = list(data.get("estimate_sources") or [])
        for label in estimates.get("labels") or []:
            if label not in src:
                src.append(label)
        data["estimate_sources"] = src[:3]
    return added


def observed_lead_h(records: dict) -> float | None:
    """Return the median real pre-install lead learned from this game's version records.

    State is long-lived and human-editable, so malformed values, non-finite numbers and implausible
    outliers are ignored. ``statistics.median`` deliberately averages the two middle values for an
    even-sized history; unlike a mean, one bad-but-still-plausible edge value cannot drag every
    later version towards it.
    """
    values: list[float] = []
    for record in (records or {}).values():
        value = record.get("preinstall_offset_h")
        try:
            hours = float(value)
        except (TypeError, ValueError):
            continue
        if math.isfinite(hours) and 0 < hours <= MAX_LEAD_H:
            values.append(hours)
    return float(median(values)) if values else None


def derive_preinstall(game: Game, data: dict, prov: dict, now: int,
                      lead_h: float | None = None) -> int | None:
    """Fill a missing pre-install time from maintenance start and mark it as estimated.

    ``lead_h`` is the median learned from real notices for this game. With no history, the shipped
    per-game value is only a cold-start fallback. A real/external pre-install value always wins;
    only a value previously derived by this function may be recalculated as the learned median or
    maintenance date changes.
    """
    start = data.get("maint_start_ts")
    if not start:
        return None
    current = data.get("preinstall_ts")
    own_estimate = ("preinstall_ts" in (data.get("estimated") or [])
                    and prov.get("preinstall_ts", [0])[0] == PRIORITY["pattern"])
    if current and not own_estimate:
        return None

    try:
        hours = float(lead_h) if lead_h is not None else float(PREINSTALL_LEAD_H[game.key])
    except (KeyError, TypeError, ValueError):
        return None
    if not math.isfinite(hours) or not 0 < hours <= MAX_LEAD_H:
        return None

    derived = int(round(int(start) - hours * 3600))
    if derived <= 0:
        return None
    data["preinstall_ts"] = derived
    prov["preinstall_ts"] = [PRIORITY["pattern"], now]
    estimated = set(data.get("estimated") or [])
    estimated.add("preinstall_ts")
    data["estimated"] = sorted(estimated,
                               key=lambda k: ESTIMATED_KEYS.index(k) if k in ESTIMATED_KEYS else 99)
    sources = list(data.get("estimate_sources") or [])
    if "version cadence" not in sources:
        sources.append("version cadence")
    data["estimate_sources"] = sources[:3]
    return derived


def needs_estimate(state, game_key: str, now: int) -> bool:
    """True when this game still misses a program / maintenance time -> worth asking a
    countdown site (otherwise the run doesn't spend a single request on it)."""
    for rec in (state.schedule_records(game_key) or {}).values():
        data = rec.get("data") or {}
        start = data.get("maint_start_ts")
        if start and now > int(start) + 12 * 3600:
            continue                                   # version already live — nothing to predict
        if not data.get("program_ts") or not start:
            return True
    return False


def data_release_ts(data: dict) -> int | None:
    """The version's launch / maintenance-end timestamp, used to phase-split banner lineups."""
    return data.get("maint_end_ts") or data.get("maint_start_ts")


def apply_banner_feed(data: dict, prov: dict, feed: dict | None, now: int) -> None:
    """Fill 5★ banner phases from the community banner feed (hub.json), but ONLY when that
    phase is currently empty (PRIORITY['bannerfeed'] is 5, the lowest in the bot)."""
    if not feed:
        return
    banners = dict(data.get("banners") or {})
    changed = False
    for key in ("phase1", "phase2"):
        if feed.get(key) and not banners.get(key) and prov.get(f"b_{key}", [0])[0] <= PRIORITY["bannerfeed"]:
            banners[key] = feed[key]
            prov[f"b_{key}"] = [PRIORITY["bannerfeed"], now]
            changed = True
    if changed:
        data["banners"] = banners


def apply_program_media(data: dict, prov: dict, media: dict | None, now: int) -> list[str]:
    """Give the card the ANNOUNCEMENT it should be showing: the program article's own link and
    its key art, instead of whatever the run happened to see.

    Why: HSR 4.6 linked to the *Update and Maintenance Notice* and showed its Pompom cover,
    because the Special Program preview (article 46691962) was 11 days older and had already
    fallen out of the lookback window. The official news pages archive every announcement, so
    the right link and the right picture are recoverable weeks later.

    program_ts is filled too when no official post has given one — the article IS official, it
    just arrived before the window. Returns the keys it changed."""
    if not media or not media.get("url"):
        return []
    changed: list[str] = []
    ts = media.get("program_ts")
    # A recovered announcement is OFFICIAL, so an air time that has already passed is kept (the
    # card renders it as "5 days ago") — unlike a countdown estimate, only absurd values go.
    if not data.get("program_ts") and ts and now - 90 * 86400 <= int(ts) <= now + 120 * 86400:
        data["program_ts"] = int(ts)
        prov["program_ts"] = [PRIORITY["news"], now]
        changed.append("program_ts")
    label = media.get("source") or "Official News"
    data["title_url"] = media.get("youtube") or media["url"]
    data["source_url"] = media["url"]
    data["source_label"] = label
    if media.get("youtube"):
        data["youtube_video"] = media["youtube"]
    links = [(lbl, u) for lbl, u in (data.get("source_links") or []) if u != media["url"]]
    links.insert(0, (label, media["url"]))
    data["source_links"] = links[:3]
    images = rank(media.get("images"))
    if images:
        data["images"] = images
        data["media_from"] = label           # the card says where the key art came from
    return changed + ["title_url", "source_url"]


def version_extracts(ctx, game: Game, log_missing: bool = False) -> dict[str, list[Extract]]:
    """Group this run's official extracts by version. The monitor and program lookup share this
    grouping so they can never disagree about which versions are current."""
    live = (ctx.versions.get(game.key) or {}).get("live")
    records = ctx.state.schedule_records(game.key)
    extracts = [e for e in (extract(game, it) for it in ctx.items.get(game.key, [])) if e]
    infer_versions(extracts, live, records)
    by_version: dict[str, list[Extract]] = {}
    for e in extracts:
        if not e.version:
            if log_missing:
                log.info("[%s] %s item %s has no version yet — waiting for another source",
                         game.key, e.kind, e.item.url)
            continue
        if live and version_key(e.version) < version_key(live):
            continue
        by_version.setdefault(e.version, []).append(e)
    return by_version


def needs_program_lookup(extracts: list[Extract], record: dict, now: int) -> bool:
    """Whether this version still needs its archived announcement looked up."""
    data = (record or {}).get("data") or {}
    start = data.get("maint_start_ts")
    if start and now > int(start) + 12 * 3600:
        return False
    if data.get("program_seen") or data.get("media_from"):
        return False
    return not any(e.kind == "program" for e in extracts)


def needs_media(state, game_key: str, now: int) -> bool:
    """True when a tracked version still shows somebody else's announcement -> worth one page
    fetch to find the program article. Never for a version that is already live, and never
    twice for the same version."""
    for rec in (state.schedule_records(game_key) or {}).values():
        data = rec.get("data") or {}
        start = data.get("maint_start_ts")
        if start and now > int(start) + 12 * 3600:
            continue                                   # long live — the card is history by now
        if data.get("program_seen") or data.get("media_from"):
            continue                                   # already the right announcement
        return True
    return False


def merge(game: Game, version: str, extracts: list[Extract], record: dict, override: dict,
          launcher: dict, now: int, notes: list[str] | None = None,
          estimates: dict | None = None, media: dict | None = None,
          banner_feed: list[dict] | None = None, lead_h: float | None = None) -> dict:
    """Return the merged card data (record['data'] is the previous state).
    4★ rule: no data or ANY doubt (wrong count, odd name, sources disagree) -> TBA;
    config/overrides.json is always trusted."""
    prev = dict(record.get("data") or {})
    prov = dict(record.get("prov") or {})
    data = dict(prev)
    data["version"] = version

    def put(key, value, source, ts):
        if value in (None, "", []):
            return
        pri = PRIORITY.get(source, 10)
        cur = prov.get(key)
        if cur is None or pri > cur[0] or (pri == cur[0] and ts >= cur[1]):
            data[key] = value
            prov[key] = [pri, ts]
            if pri > PRIORITY["countdown"]:
                _unmark_estimated(data, key)      # an official time replaces an estimate

    program_items = []
    for e in sorted(extracts, key=lambda x: x.item.published_ts):
        src, ts = e.item.source, e.item.published_ts
        f = e.fields
        if e.kind == "program":
            program_items.append(e)
            for k in ("program_ts", "program_name", "version_name", "youtube_video"):
                put(k, f.get(k), src, ts)
        elif e.kind == "maintenance":
            for k in ("preinstall_ts", "maint_start_ts", "maint_end_ts", "compensation"):
                put(k, f.get(k), src, ts)
        elif e.kind == "banner":
            banners = dict(data.get("banners") or {})
            phase = f.get("banner_phase")
            if phase is None and data.get("maint_start_ts"):
                phase = 1 if ts < int(data["maint_start_ts"]) + 7 * 86400 else 2
            if phase in (1, 2):
                key5, key4 = f"phase{phase}", f"phase{phase}_4"
                if f.get("banner_five") and prov.get(f"b_{key5}", [0])[0] < PRIORITY["override"]:
                    banners[key5] = f["banner_five"]
                    prov[f"b_{key5}"] = [PRIORITY.get(src, 10), ts]
                four = list(f.get("banner_four") or [])
                if ((four or f.get("banner_four_unsure"))
                        and prov.get(f"b_{key4}", [0])[0] < PRIORITY["override"]):
                    flag = f"b_{key4}_tba"
                    problem = _four_star_problem(game, four, banners.get(key4), prov.get(flag))
                    prov[f"b_{key4}"] = [PRIORITY.get(src, 10), ts]
                    if problem:
                        banners[key4] = []                                # TBA
                        if prov.get(flag) != problem and notes is not None:
                            notes.append(f"⚠️ {game.short} {version} phase {phase}: 4★ shown as TBA — {problem} "
                                         f"(found: {', '.join(four) or 'nothing usable'}). Confirm via "
                                         "config/overrides.json if you know the names.")
                        prov[flag] = problem
                    else:
                        banners[key4] = four
            data["banners"] = banners

    # presentation: title link / image / source from the best program post
    if program_items:
        data["program_seen"] = True          # this card already shows the real announcement
        best = sorted(program_items, key=lambda e: (-PRIORITY.get(e.item.source, 0), e.item.published_ts))[0]
        images = next((e.fields.get("images") for e in program_items if e.fields.get("images")), None)
        yt = data.get("youtube_video")
        data["title_url"] = yt or best.item.url
        data["source_url"] = best.item.url
        data["source_label"] = best.item.source_label
        if images:
            data["images"] = rank(images)
        elif yt:
            data["images"] = [youtube_thumb(yt)]
        links = []
        for e in program_items:
            label = e.item.source_label
            if label not in [lbl for lbl, _ in links]:
                links.append((label, e.item.url))
        data["source_links"] = links[:3]
    else:
        # nobody in the lookback window announced the program: look the article up on the
        # official news page / HoYoLAB news list (link + full-size key art + air time).
        apply_program_media(data, prov, media, now)
        if not data.get("title_url"):
            notice = next((e for e in extracts if e.kind == "maintenance"), None)
            if notice:
                data.setdefault("title_url", notice.item.url)
                data.setdefault("source_url", notice.item.url)
                data.setdefault("source_label", notice.item.source_label)
                data.setdefault("source_links", [(notice.item.source_label, notice.item.url)])
                # NOTE: the notice's own cover is deliberately NOT used as the card image — a
                # maintenance notice cover (Pompom on HSR 4.6) is not the program's key art.

    # launcher: pre-download became available (official client signal)
    if launcher.get("pre") == version and not data.get("preinstall_ts"):
        data["preinstall_ts"] = int(record.get("pre_detected_ts") or now)
        record.setdefault("pre_detected_ts", data["preinstall_ts"])
        prov["preinstall_ts"] = [PRIORITY["launcher"], now]

    # countdown sites: an ESTIMATE for every field no official source has given yet
    apply_estimates(data, prov, estimates, now)

    # banner feed: fill empty banner phases from hub.json
    if banner_feed:
        rel_ts = data_release_ts(data)
        lineup = banner_feed_for(banner_feed, rel_ts) if rel_ts else {}
        apply_banner_feed(data, prov, lineup, now)

    # human overrides win over everything
    for key in ("program_ts", "preinstall_ts", "maint_start_ts", "maint_end_ts"):
        if key in override:
            ts = _to_ts(override[key])
            if ts:
                data[key] = ts
                prov[key] = [PRIORITY["override"], now]
                _unmark_estimated(data, key)
    for key in ("program_name", "version_name", "title_url", "compensation"):
        if override.get(key):
            data[key] = override[key]
    if override.get("image"):
        data["images"] = [override["image"]]
    if isinstance(override.get("banners"), dict):
        banners = dict(data.get("banners") or {})
        for k, v in override["banners"].items():
            if isinstance(v, list):
                banners[k] = v
                prov[f"b_{k}"] = [PRIORITY["override"], now]
        data["banners"] = banners

    # Last, derive only what every external source and human override left empty. This can use a
    # real maintenance start or an explicitly labelled countdown estimate; either way the derived
    # pre-install value remains labelled estimated until an official notice replaces it.
    derive_preinstall(game, data, prov, now, lead_h)
    record["prov"] = prov
    return data


# --------------------------------------------------------------------------- pipeline
def repost_problem(repost: str, games: list, records_of) -> str | None:
    """Explain why a REPOST request can't be honoured (None = fine)."""
    if not repost:
        return None
    rg, _, rv = repost.strip().partition(":")
    keys = [g.key for g in games]
    if not rv:
        return f"⚠️ repost '{repost}': use game:version, e.g. starrail:4.6"
    if rg not in keys:
        return f"⚠️ repost '{repost}': unknown or inactive game '{rg}' (use one of: {', '.join(keys)})"
    tracked = sorted(records_of(rg), key=version_key)
    if rv not in tracked:
        have = ", ".join(tracked) if tracked else "none yet"
        return (f"⚠️ repost '{repost}': version {rv} isn't tracked — only versions the bot has already seen "
                f"in an official post can be reposted (tracked: {have})")
    return None


async def run(ctx) -> None:
    s = ctx.settings
    for game in ctx.games:
        live_info = ctx.versions.get(game.key, {})
        records = ctx.state.schedule_records(game.key)
        by_version = version_extracts(ctx, game, log_missing=True)
        overrides = ctx.overrides.get(game.key, {})
        for ver in overrides:
            if ver in records and ver not in by_version:
                by_version[ver] = []                       # override-only edits
        if s.repost:
            rg, _, rv = s.repost.partition(":")
            if rg == game.key and rv in records and rv not in by_version:
                by_version[rv] = []

        bootstrapped = ctx.state.is_bootstrapped("schedule", game.key)
        est = (ctx.estimates.get(game.key) or {}) if s.countdown_estimates else {}
        media = (ctx.media.get(game.key) or {}) if s.program_media else {}
        feed_list = (ctx.banners.get(game.key) or []) if s.banner_feed else []
        for ver in sorted(by_version, key=version_key):
            version_est = est if (est.get("version") in (None, ver)) else {}
            await _handle_version(ctx, game, ver, by_version[ver], records, overrides.get(ver, {}),
                                  live_info, bootstrapped, version_est, media.get(ver), feed_list)
        if not bootstrapped and ctx.reachable.get(game.key, True):
            ctx.state.mark_bootstrapped("schedule", game.key)   # only after a source really answered
    problem = repost_problem(s.repost, ctx.games, ctx.state.schedule_records)   # after this run's records
    if problem:
        ctx.report.append(problem)


async def _handle_version(ctx, game: Game, ver: str, extracts: list[Extract], records: dict,
                          override: dict, live_info: dict, bootstrapped: bool,
                          estimates: dict | None = None, media: dict | None = None,
                          banner_feed: list[dict] | None = None) -> None:
    s, now = ctx.settings, ctx.now
    record = records.setdefault(ver, {"status": "new", "first_seen": now})
    notes: list[str] = []
    data = merge(game, ver, extracts, record, override, live_info, now, notes, estimates, media,
                 banner_feed, lead_h=observed_lead_h(records))
    ctx.report.extend(notes)
    estimated = data.get("estimated") or []
    if estimated and estimated != record.get("estimated_reported"):
        record["estimated_reported"] = estimated
        what = ", ".join(ESTIMATE_LABELS.get(k, k) for k in estimated)
        ctx.report.append(f"🕒 {game.short} {ver}: {what} estimated from "
                          f"{', '.join(data.get('estimate_sources') or ['countdown sites'])} — "
                          "the official notice replaces it automatically")

    # Teach later versions only from a real pair. In particular, the pre-install timestamp this
    # code just derived is in `estimated`, so it can never confirm its own guess on the next run.
    if data.get("preinstall_ts") and data.get("maint_start_ts") \
            and not {"preinstall_ts", "maint_start_ts"}.intersection(estimated):
        offset_h = (int(data["maint_start_ts"]) - int(data["preinstall_ts"])) / 3600
        if 0 < offset_h <= MAX_LEAD_H:
            record["preinstall_offset_h"] = round(offset_h, 3)
    record["data"] = data
    kinds = {e.kind for e in extracts}
    status = record.get("status")
    webhook = s.webhook("schedule", game.key)
    ping = s.ping("schedule", game.key)
    repost = s.repost == f"{game.key}:{ver}"

    maint_start = data.get("maint_start_ts")
    frozen = bool(maint_start and now > int(maint_start) + 45 * 86400)

    if status in ("posted", "live") and not repost:
        if frozen or not s.edit_on_update:
            return
        payload = schedule_payload(game, data, s, ping)
        h = stable_hash(payload["components"])
        if h == record.get("payload_hash"):
            return
        mid = record.get("message_id")
        if not webhook or not mid or record.get("webhook_fp") != webhook_fingerprint(webhook):
            record["payload_hash"] = h
            ctx.report.append(f"{game.short} {ver}: card data changed but the original message can't be edited here")
            return
        payload = schedule_payload(game, data, s, ping, updated_ts=now)
        res = await ctx.webhook.edit(webhook, mid, payload)
        if res.ok:
            record["payload_hash"] = h
            record["updated_at"] = now
            ctx.report.append(f"✏️ {game.short} {ver}: schedule card updated")
        elif res.status == 404:
            # Discord 10008 means this message is permanently gone. Repeating the PATCH would
            # fail forever, so post the current card once and adopt its new id. No other edit
            # failure is reposted: a malformed payload or transient outage must not create spam.
            fresh = schedule_payload(game, data, s, ping)
            if s.test_mode:
                fresh = mark_test(fresh)
            reposted = await ctx.webhook.send(webhook, fresh)
            if reposted.ok:
                record.update({"message_id": reposted.message_id, "posted_at": now,
                               "updated_at": now, "webhook_fp": webhook_fingerprint(webhook),
                               "payload_hash": stable_hash(fresh["components"])})
                ctx.report.append(f"♻️ {game.short} {ver}: deleted schedule card reposted "
                                  f"after edit returned 404 {res.error}")
            else:
                # Keep the dead id and old payload hash: the next run retries the same recovery.
                ctx.errors.append(f"{game.short} {ver}: edit returned 404 {res.error}; repost failed "
                                  f"({reposted.status}) {reposted.error}")
        else:
            ctx.errors.append(f"{game.short} {ver}: edit failed ({res.status}) {res.error}")
        return

    # decide whether this version deserves a NEW post
    pts, fresh_program = data.get("program_ts"), False
    if "program" in kinds and pts:
        fresh_program = int(pts) > now - 36 * 3600
    fresh_maint = bool(s.post_on_maintenance and "maintenance" in kinds and maint_start
                       and int(maint_start) > now - 6 * 3600)
    if s.test_mode and (pts or maint_start):
        fresh_program = True                  # TEST MODE: show the latest real card, even if older
    if not (fresh_program or fresh_maint or repost):
        if status == "new":
            record["status"] = "tracked"
            if not bootstrapped:
                ctx.report.append(f"🗂 {game.short} {ver}: already out / program long past — recorded, "
                                  f"nothing to announce (repost with {game.key}:{ver} if you want it anyway)")
        return
    if not bootstrapped and not (s.bootstrap_post or s.test_mode) and not repost:
        record["status"] = "seeded"
        ctx.report.append(f"🌱 {game.short} {ver}: seeded silently (first run — set BOOTSTRAP_POST=1 to post)")
        return
    if status == "seeded" and not repost:
        return
    if not webhook:
        ctx.report.append(f"⚠️ {game.short} {ver}: no schedule webhook — add the secret "
                          f"{s.expected_webhook_names('schedule', game.key)}")
        return
    payload = schedule_payload(game, data, s, ping)
    if s.test_mode:
        payload = mark_test(payload)
    res = await ctx.webhook.send(webhook, payload)
    if res.ok:
        record.update({"status": "posted", "message_id": res.message_id, "posted_at": now,
                       "webhook_fp": webhook_fingerprint(webhook),
                       "payload_hash": stable_hash(payload["components"])})
        ctx.report.append(f"📜 {game.short} {ver}: schedule card posted")
    else:
        ctx.errors.append(f"{game.short} {ver}: post failed ({res.status}) {res.error}")
