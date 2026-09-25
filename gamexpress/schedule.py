"""Version-schedule announcements: detect → extract → merge → post once → keep the card accurate.

Posting only happens on a keyword/pattern match (special program / special broadcast /
livestream announcement, or an official update-maintenance notice) — never daily.

Accuracy rules:
  * every time on the card comes from an official post (HoYoLAB / official X / Kuro) or
    from config/overrides.json (human-verified). Nothing is estimated.
  * unknown values render as TBA; banners always carry (STC).
  * one card per game+version; later official info (maintenance notice, pre-install,
    banner notice, overrides edits) EDITS the same message silently (no re-ping).
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

from .cards import mark_test, schedule_payload
from .config import Game
from .discord import webhook_fingerprint
from .models import Item
from .sources.codes import extract_codes_from_text
from .state import stable_hash
from .textutil import (
    bump_minor,
    find_version,
    find_version_name,
    sentences,
    twitch_url,
    version_key,
    youtube_id,
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
DEFAULT_BANNER_RE = (r"event\s+wish|event\s+warp|signal\s+search|exclusive\s+channel|featured\s+resonator|"
                     r"resonator\s+convene|character\s+event|limited[-\s]time\s+(?:character|agent)")
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

# precedence of sources for a field (higher wins)
PRIORITY = {"override": 100, "hoyolab": 50, "kuro": 50, "x": 40, "launcher": 20}


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


def extract_maintenance(item: Item) -> dict:
    text = item.full
    ref = item.published_ts or None
    f: dict = {}
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
    if "preinstall_ts" not in f and PRE_WORDS.search(item.title or text[:200]) and \
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


def _four_star_problem(game: Game, four: list[str], unsure: bool, existing: list[str] | None,
                       sticky: str | None) -> str | None:
    """Why a 4★ list must NOT be shown (-> TBA), or None when it is trustworthy."""
    if sticky == "official sources disagree":
        return sticky
    if unsure:
        return "a name looked unreliable"
    if game.four_star_count and len(four) != game.four_star_count:
        return f"{len(four)} name(s) found, {game.four_star_count} expected"
    if existing and sorted(existing) != sorted(four):
        return "official sources disagree"
    return None


def merge(game: Game, version: str, extracts: list[Extract], record: dict, override: dict,
          launcher: dict, now: int, notes: list[str] | None = None) -> dict:
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
                    problem = _four_star_problem(game, four, bool(f.get("banner_four_unsure")),
                                                 banners.get(key4), prov.get(flag))
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
        best = sorted(program_items, key=lambda e: (-PRIORITY.get(e.item.source, 0), e.item.published_ts))[0]
        images = next((e.fields.get("images") for e in program_items if e.fields.get("images")), None)
        yt = data.get("youtube_video")
        data["title_url"] = yt or best.item.url
        data["source_url"] = best.item.url
        data["source_label"] = best.item.source_label
        if images:
            data["images"] = images
        elif yt:
            data["images"] = [f"https://i.ytimg.com/vi/{youtube_id(yt)}/maxresdefault.jpg"]
        links = []
        for e in program_items:
            label = e.item.source_label
            if label not in [lbl for lbl, _ in links]:
                links.append((label, e.item.url))
        data["source_links"] = links[:3]
    elif not data.get("title_url"):
        notice = next((e for e in extracts if e.kind == "maintenance"), None)
        if notice:
            data.setdefault("title_url", notice.item.url)
            data.setdefault("source_url", notice.item.url)
            data.setdefault("source_label", notice.item.source_label)
            data.setdefault("source_links", [(notice.item.source_label, notice.item.url)])
            if notice.fields.get("notice_images") and not data.get("images"):
                data["images"] = notice.fields["notice_images"]

    # launcher: pre-download became available (official client signal)
    if launcher.get("pre") == version and not data.get("preinstall_ts"):
        data["preinstall_ts"] = int(record.get("pre_detected_ts") or now)
        record.setdefault("pre_detected_ts", data["preinstall_ts"])
        prov["preinstall_ts"] = [PRIORITY["launcher"], now]

    # human overrides win over everything
    for key in ("program_ts", "preinstall_ts", "maint_start_ts", "maint_end_ts"):
        if key in override:
            ts = _to_ts(override[key])
            if ts:
                data[key] = ts
                prov[key] = [PRIORITY["override"], now]
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
    record["prov"] = prov
    return data


# --------------------------------------------------------------------------- pipeline
async def run(ctx) -> None:
    s = ctx.settings
    for game in ctx.games:
        items: list[Item] = ctx.items.get(game.key, [])
        live_info = ctx.versions.get(game.key, {})
        live = live_info.get("live")
        records = ctx.state.schedule_records(game.key)
        extracts = [e for e in (extract(game, it) for it in items) if e]
        infer_versions(extracts, live, records)
        by_version: dict[str, list[Extract]] = {}
        for e in extracts:
            if not e.version:
                log.info("[%s] %s item %s has no version yet — waiting for another source",
                         game.key, e.kind, e.item.url)
                continue
            if live and version_key(e.version) < version_key(live):
                continue                                   # old version — ignore
            by_version.setdefault(e.version, []).append(e)
        overrides = ctx.overrides.get(game.key, {})
        for ver in overrides:
            if ver in records and ver not in by_version:
                by_version[ver] = []                       # override-only edits
        if s.repost:
            rg, _, rv = s.repost.partition(":")
            if rg == game.key and rv in records and rv not in by_version:
                by_version[rv] = []

        bootstrapped = ctx.state.is_bootstrapped("schedule", game.key)
        for ver in sorted(by_version, key=version_key):
            await _handle_version(ctx, game, ver, by_version[ver], records, overrides.get(ver, {}),
                                  live_info, bootstrapped)
        if not bootstrapped and ctx.reachable.get(game.key, True):
            ctx.state.mark_bootstrapped("schedule", game.key)   # only after a source really answered


async def _handle_version(ctx, game: Game, ver: str, extracts: list[Extract], records: dict,
                          override: dict, live_info: dict, bootstrapped: bool) -> None:
    s, now = ctx.settings, ctx.now
    record = records.setdefault(ver, {"status": "new", "first_seen": now})
    notes: list[str] = []
    data = merge(game, ver, extracts, record, override, live_info, now, notes)
    ctx.report.extend(notes)
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
