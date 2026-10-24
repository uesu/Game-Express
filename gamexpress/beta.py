"""Fifth feature: beta changelog / revision-diff cards for every tracked game.

WHAT IT DOES
    While a version is in beta, the community databases publish a new *revision*
    (v2, v3, …) every few days. This feature watches those revisions and posts ONE
    Components V2 batch per new revision to that game's own channel:

      * the characters that are NEW in this beta version — a full kit overview
        (every skill with its numbers, the mindscape / constellation / resonance
        chain, and the mechanic glossary the kit references);
      * the new weapons / W-Engines / light cones / disc drives / relic sets /
        echo sets, each as its own block;
      * the OLD characters a revision touched, tagged [CHANGED] (a buff, a nerf, a
        rework or a text fix) with a link to the before/after diff.

    It never invents a number and never guesses a direction it cannot see: an entry
    the changelog lists as updated but whose kit text is unchanged is reported as a
    text-only touch, and an entry with no readable kit is skipped with a warning.

DESIGN GUARANTEES
    * Disabled by default: `BETA_ENABLED=1` is an explicit opt-in. Per-game opt-in
      via `BETA_GAMES` (default: the four released games — Honkai: Nexus Anima and
      ANANTA are excluded until they ship).
    * Dedicated destinations: `DISCORD_WEBHOOK_BETA_<GAME>` > `DISCORD_WEBHOOK_BETA`
      > `DISCORD_WEBHOOK_NEWS_<GAME>`. It never falls back to the schedule/codes
      catch-all, so enabling it can never leak into an unrelated channel.
    * Ping is its own switch: `PING_BETA_<GAME>` > `PING_BETA`. Nothing else can
      supply it — `PING_ROLE_ID` is deliberately NOT inherited (config.ping).
    * Bounded and polite: a shared manifest, one changelog per game, one JSON per
      new entry, an in-run request budget, and a minimum re-poll interval. A quiet
      beta costs zero requests beyond one small manifest GET.
    * Image lock: a splash art URL resolved for a character is stored and reused.
      A locked image is never re-resolved, so a finished card stops generating
      traffic — the "monitor forever" bug this feature must not have.
    * Idempotent: one card set per (game, revision). A later run that sees the same
      revision posts nothing. A partial delivery is resumed from the stored
      message ids instead of re-posting.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from .cards import beta_payloads_with_map
from .config import Game
from .discord import webhook_fingerprint
from .models import BetaCharacter, BetaEquipment, BetaPatch, BetaSectionEntry
from .state import stable_hash

log = logging.getLogger("gamexpress.beta")

# --------------------------------------------------------------------------- sources
# One tiny JSON file that names, per game, the newest data revision and the ids that
# are new in it. It is the cheapest possible "did anything move?" probe: ~1 KiB.
MANIFEST_URL = "https://static.nanoka.cc/manifest.json"
STATIC_BASE = "https://static.nanoka.cc"
LOCALE = "en"

# nanoka namespace -> how that game names its things.
NANOKA_KINDS: dict[str, dict[str, Any]] = {
    "zzz": {
        "character_label": "Agents",
        "weapon": {"detail": "weapon", "listing": "weapon", "label": "W-Engines"},
        "relic": {"detail": "equipment", "listing": "equipment", "label": "Drive Discs"},
        "new_keys": {"character": "character", "weapon": "weapon", "relic": "equipment"},
    },
    "hsr": {
        "character_label": "Characters",
        "weapon": {"detail": "lightcone", "listing": "lightcone", "label": "Light Cones"},
        "relic": {"detail": "relicset", "listing": "relicset", "label": "Relics & Ornaments"},
        "new_keys": {"character": "character", "weapon": "lightcone", "relic": "relicset"},
    },
    "gi": {
        "character_label": "Characters",
        "weapon": {"detail": "weapon", "listing": "weapon", "label": "Weapons"},
        "relic": {"detail": "artifact", "listing": "artifact", "label": "Artifacts"},
        "new_keys": {"character": "character", "weapon": "weapon", "relic": "artifact"},
    },
    "ww": {
        "character_label": "Resonators",
        "weapon": {"detail": "weapon", "listing": "weapon", "label": "Weapons"},
        "relic": {"detail": "echo", "listing": "echo", "label": "Echoes"},
        "new_keys": {"character": "character", "weapon": "weapon", "relic": "echo"},
    },
}

# Wuthering Waves stores element / weapon as bare ints.
WW_ELEMENTS = {1: "Glacio", 2: "Fusion", 3: "Electro", 4: "Aero", 5: "Spectro", 6: "Havoc"}
WW_WEAPONS = {1: "Broadblade", 2: "Sword", 3: "Pistols", 4: "Gauntlets", 5: "Rectifier"}

PLACEHOLDER_NAMES = {
    "",
    "?",
    "-",
    "—",
    "placeholder",
    "unknown",
    "stay tuned",
    "tba",
    "tbd",
    "n/a",
}

# Unresolved backend strings such as `Robin_Skill_Normal_Title` or
# `EquipmentSuit_34300_name` are the database saying it has no localisation yet.
_KEY_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]*(?:_[A-Za-z0-9]+){2,}$")
_TEXT_FIX_RE = re.compile(r"\btext fix\b|\bwording\b|\btooltip\b", re.I)


def _is_key(value: str) -> bool:
    v = (value or "").strip()
    if not v or v.lower() in PLACEHOLDER_NAMES:
        return True
    if v.startswith("Item_") or v.startswith("EquipmentSuit_") or v.startswith("TestKey_"):
        return True
    if v.startswith("UI_") or v.startswith("Skill_") or v.startswith("SpriteOutput/"):
        return True
    return bool(_KEY_RE.match(v) and "_" in v and not " " in v)


def _clean(value: Any) -> str:
    """Collapse a scraped string into one clean line (or '' when it is noise)."""
    if value is None:
        return ""
    text = str(value)
    if _is_key(text):
        return ""
    text = text.replace("\\n", "\n").replace("\r", " ")
    text = re.sub(r"\{LINK#[^}]*\}([^\{]*)\{/LINK\}", r"\1", text)
    text = re.sub(r"\{(?:LINK|N|S)#\d+\}", "", text)
    text = re.sub(r"\{Cus:Ipt[^}]*\}", "", text)
    text = re.sub(r"\{Cus:Sap,S=[^,]*\sP=[^}\s]*\sSapTag=\d+\}", "", text)
    text = re.sub(r"\{CAL:[^}]*\}", "", text)
    text = re.sub(r"\{param(\d+)(?::[A-Z]\d?[PI]?)?\}", r"", text)
    text = re.sub(r"\[\s*\n\s*", "[", text)
    text = re.sub(r"[ \t]+\n", "\n", text)
    # An inline input marker ("Press {Cus:Ipt…} to activate") leaves a doubled space.
    text = re.sub(r"[ \t]{2,}", " ", text)
    lines = [ln.rstrip() for ln in text.split("\n")]
    return "\n".join(ln for ln in lines if ln.strip()).strip()


def _lines(value: Any) -> list[str]:
    return [ln.strip() for ln in _clean(value).split("\n") if ln.strip()]


def _display_version(version: str) -> str:
    """`3.4.1+19836465` -> `3.4.1`. The build number is noise on a card header."""
    return str(version or "").split("+", 1)[0].strip() or str(version or "")


def _pct(value: Any, digits: int = 1) -> str:
    try:
        return f"{round(float(value) * 100, digits):g}%"
    except (TypeError, ValueError):
        return ""


def _num(value: Any, digits: int = 4) -> str:
    try:
        f = float(value)
    except (TypeError, ValueError):
        return ""
    if f == int(f):
        return str(int(f))
    return f"{round(f, digits):g}"


# --------------------------------------------------------------------------- changelog
_ENTRY_RE = re.compile(
    r"\[!\[[^\]]*\]\((?P<img>[^)]*)\)"
    r"(?P<name>[^\]]*)\]\((?P<url>[^)]*)\)"
    r"(?:\s*\[See Changes\]\((?P<diff>[^)]*)\))?"
)
# A changelog entry wraps across three lines — the image markdown, a blank separator and
# the display name — so the entry regex has to run over the block, never line by line.
_REV_RE = re.compile(r"^##\s+(?P<label>v?[0-9][^\n|]*?)(?:\s*\|\s*(?P<date>[^\n]+))?\s*$", re.M)
_SECTION_RE = re.compile(r"^###[ \t]+(?P<name>[^\n]+?)[ \t]*$", re.M)
_ITEM_ID_RE = re.compile(r"/(?:agents|characters|resonators|w-engines|weapons|light-cones|"
                         r"lightcones|relics|relicsets|planar-ornaments|drive-discs|artifacts|"
                         r"echoes|echo)/(\d+)")


def _normalize_changelog(markdown: str) -> str:
    """Undo the page's escaped newlines so one entry becomes one contiguous match."""
    text = (markdown or "").replace("\r", "\n")
    # gachabase writes the entry's display name behind `\` + newline sequences; the exact
    # number of backslashes varies between page renders, so collapse every run of them.
    text = re.sub(r"\\+[ \t]*\n[ \t]*", "\n", text)
    return re.sub(r"\n{3,}", "\n\n", text)


def parse_changelog(markdown: str) -> list[dict]:
    """Parse a gachabase beta changelog page into revisions.

    -> [{'label', 'date', 'entries': [{'name', 'url', 'diff', 'image', 'section'}]}]
    Newest revision first, exactly as the page lists them.
    """
    text = _normalize_changelog(markdown)
    if not text:
        return []
    headers = [m for m in _REV_RE.finditer(text)
               if not (m.group("label") or "").lower().startswith("site")]
    revs: list[dict] = []
    for idx, head in enumerate(headers):
        label = (head.group("label") or "").strip().rstrip("\\").strip()
        if not label:
            continue
        start = head.end()
        end = headers[idx + 1].start() if idx + 1 < len(headers) else len(text)
        block = text[start:end]
        sections = [(m.start(), m.group("name").strip()) for m in _SECTION_RE.finditer(block)]
        entries: list[dict] = []
        for m in _ENTRY_RE.finditer(block):
            url = (m.group("url") or "").strip()
            name = re.sub(r"\s+", " ", (m.group("name") or "")).strip(" \n\t\\")
            if not name and url:
                slug = url.rstrip("/").rsplit("/", 1)[-1].split("?")[0].replace("-", " ")
                name = slug.title()
            if not name and not url:
                continue
            section = ""
            for pos, sname in sections:
                if pos < m.start():
                    section = sname
                else:
                    break
            entries.append({
                "name": name,
                "url": url,
                "diff": (m.group("diff") or "").strip(),
                "image": (m.group("img") or "").strip(),
                "section": section,
            })
        # The page escapes the `|` separator (`\|`), so the date arrives with a stray
        # backslash hanging off the end.
        date = (head.group("date") or "").strip().rstrip("\\").strip()
        revs.append({"label": label, "date": date, "entries": entries})
    return revs


def _entry_id(entry: dict) -> str:
    m = _ITEM_ID_RE.search(entry.get("url") or "")
    return m.group(1) if m else ""


# --------------------------------------------------------------------------- manifest
async def fetch_manifest(fetcher) -> dict:
    data = await fetcher.get_json(MANIFEST_URL, source="beta-manifest", retries=1)
    return data if isinstance(data, dict) else {}


def manifest_game(manifest: dict, ns: str) -> dict:
    g = (manifest or {}).get(ns)
    return g if isinstance(g, dict) else {}


def manifest_new_ids(manifest: dict, ns: str, key: str) -> set[str]:
    new = manifest_game(manifest, ns).get("new")
    if not isinstance(new, dict):
        return set()
    raw = new.get(key)
    if not isinstance(raw, list):
        return set()
    return {str(i) for i in raw}


# --------------------------------------------------------------------------- detail JSON
async def _detail(fetcher, ns: str, version: str, kind: str, item_id: str) -> dict | None:
    if not ns or not version or not item_id:
        return None
    url = f"{STATIC_BASE}/{ns}/{version}/{LOCALE}/{kind}/{item_id}.json"
    data = await fetcher.get_json(url, source="beta-data", retries=1)
    return data if isinstance(data, dict) else None


async def _listing(fetcher, ns: str, version: str, kind: str) -> dict:
    if not ns or not version:
        return {}
    url = f"{STATIC_BASE}/{ns}/{version}/{kind}.json"
    data = await fetcher.get_json(url, source="beta-data", retries=1)
    return data if isinstance(data, dict) else {}


# --------------------------------------------------------------------------- ZZZ kit
_ZZZ_CATEGORY_LABELS = {
    "basic": "Basic Attack",
    "dodge": "Dodge",
    "assist": "Assist",
    "special": "Special Attack & EX Special Attack",
    "chain": "Chain Attack & Ultimate",
    "core": "Core Passive & Additional Ability",
}


def _zzz_stats(data: dict) -> list[str]:
    stats = data.get("stats") or {}
    if not isinstance(stats, dict):
        return []
    level6 = (data.get("level") or {}).get("6") or {}
    if not isinstance(level6, dict):
        level6 = {}

    # Lv. 60 = Lv.1 base + per-level growth x 59 + the final promotion tier's flat bonus.
    # Cross-checked against the database's own rendered stat block (ZZZ Robin:
    # HP 8754 / ATK 750 / DEF 706; Sunbringer: HP 5736 / DEF 441).
    def at(base_key: str, grow_key: str, level_key: str, scale: float = 10000.0) -> str | None:
        base, grow = stats.get(base_key), stats.get(grow_key)
        extra = level6.get(level_key)
        if base is None or grow is None:
            return None
        try:
            value = float(base) + float(grow) * 59.0 / scale
            if extra is not None:
                value += float(extra)
            # Truncated, not rounded: that is how the database renders the same stat block
            # (Robin HP 8754 / ATK 750 / DEF 706 — rounding would print 8755 / 751).
            return str(int(value))
        except (TypeError, ValueError):
            return None

    # The core-skill track (`extra_level`) grants a FLAT ATK bonus and a % CRIT Rate bonus
    # at its last node; both have to be added or ATK comes out ~10% low (Robin 676 vs 750).
    extra_lv = (data.get("extra_level") or {}).get("6") or {}
    if not isinstance(extra_lv, dict):
        extra_lv = {}
    flat_atk = 0.0
    crit_bonus = 0.0
    for entry in (extra_lv.get("extra", {}).values()
                  if isinstance(extra_lv.get("extra"), dict) else ()):
        if not isinstance(entry, dict):
            continue
        label = str(entry.get("name") or "").strip().lower()
        try:
            value = float(entry.get("value") or 0)
        except (TypeError, ValueError):
            continue
        if label.startswith("crit rate"):
            crit_bonus += value
        elif "atk" in label:
            flat_atk += value

    out: list[str] = []
    hp, atk, df = at("hp_max", "hp_growth", "hp_max"), at("attack", "attack_growth", "attack"), \
        at("defence", "defence_growth", "defence")
    if atk is not None and flat_atk:
        try:
            atk = str(int(float(atk) + flat_atk))
        except (TypeError, ValueError):
            pass
    if hp and atk and df:
        out.append(f"Lv. 60 — HP {hp} · ATK {atk} · DEF {df}")
    crit = stats.get("crit")
    if crit is not None:
        try:
            out.append(f"CRIT Rate {round(float(crit) / 100 + crit_bonus / 100, 3):g}%")
        except (TypeError, ValueError):
            pass
    cd = stats.get("crit_damage")
    if cd is not None:
        p = _pct(float(cd) / 10000)
        if p:
            out.append(f"CRIT DMG {p}")
    for label, key in (("Impact", "break_stun"), ("Anomaly Mastery", "element_abnormal_power"),
                       ("Anomaly Proficiency", "element_mystery")):
        val = stats.get(key)
        if val not in (None, ""):
            out.append(f"{label} {_num(val)}")
    pr = stats.get("pen_rate")
    if pr is not None:
        out.append(f"PEN Ratio {_num(pr)}%")
    sharp = stats.get("sharp_critical_damage")
    if sharp:
        p = _pct(float(sharp) / 10000)
        if p:
            out.append(f"Laceration DMG {p}")
    return out


def _zzz_character(data: dict) -> dict:
    element = ""
    for v in (data.get("element_type") or {}).values():
        if isinstance(v, str) and v:
            element = v
            break
    role = ""
    for v in (data.get("weapon_type") or {}).values():
        if isinstance(v, str) and v:
            role = v
            break
    camp = ""
    for v in (data.get("camp") or {}).values():
        if isinstance(v, str) and v:
            camp = v
            break

    sections: list[BetaSectionEntry] = []
    skill = data.get("skill") or {}
    if isinstance(skill, dict):
        for key, label in _ZZZ_CATEGORY_LABELS.items():
            block = skill.get(key)
            if not isinstance(block, dict):
                continue
            for item in block.get("description") or []:
                if not isinstance(item, dict):
                    continue
                name = _clean(item.get("name"))
                desc = _clean(item.get("desc"))
                if not desc:
                    # The database repeats a skill as a second block holding only its stat
                    # table. Those numbers belong to the skill's own block, so the empty
                    # copy is dropped instead of printing a bare title.
                    continue
                sections.append(BetaSectionEntry(
                    title=name or label, category=label, tag="[NEW]", meta="",
                    lines=_lines(desc),
                ))
    talent = data.get("talent") or {}
    if isinstance(talent, dict):
        for level in sorted(talent, key=lambda k: int(k) if str(k).isdigit() else 0):
            item = talent[level]
            if not isinstance(item, dict):
                continue
            desc = _clean(item.get("desc"))
            if not desc:
                continue
            sections.append(BetaSectionEntry(
                title=f"Mindscape Cinema {level}", category="Mindscape Cinema",
                tag="[NEW]", meta="", lines=_lines(desc),
            ))
    return {
        "element": element, "role": role, "camp": camp,
        "stats_lines": _zzz_stats(data),
        "sections": sections,
    }


# --------------------------------------------------------------------------- HSR kit
def _hsr_stats(data: dict) -> list[str]:
    stats = data.get("stats") or {}
    last = None
    if isinstance(stats, dict):
        for key in sorted(stats, key=lambda k: int(k) if str(k).isdigit() else -1):
            entry = stats[key]
            if isinstance(entry, dict) and "attack_base" in entry:
                last = entry
    if not last:
        return []

    def at(base_key: str, add_key: str, level: int = 80) -> str | None:
        base, add = last.get(base_key), last.get(add_key)
        if base is None or add is None:
            return None
        try:
            return str(int(round(float(base) + float(add) * (level - 1))))
        except (TypeError, ValueError):
            return None

    out: list[str] = []
    hp, atk, df = at("hp_base", "hp_add"), at("attack_base", "attack_add"), at("defence_base", "defence_add")
    if hp and atk and df:
        out.append(f"Lv. 80 — HP {hp} · ATK {atk} · DEF {df}")
    spd = last.get("speed_base")
    if spd is not None:
        out.append(f"SPD {_num(spd)}")
    for label, key in (("CRIT Rate", "critical_chance"), ("CRIT DMG", "critical_damage")):
        val = last.get(key)
        if val is not None:
            p = _pct(val, 2)
            if p:
                out.append(f"{label} {p}")
    bonus: dict[str, float] = {}
    points = data.get("points") or {}
    for node in (points.values() if isinstance(points, dict) else ()):
        for tier in (node.values() if isinstance(node, dict) else ()):
            if not isinstance(tier, dict):
                continue
            for add in tier.get("status_add_list") or []:
                if not isinstance(add, dict):
                    continue
                name = str(add.get("name") or "")
                try:
                    bonus[name] = bonus.get(name, 0.0) + float(add.get("value") or 0)
                except (TypeError, ValueError):
                    pass
    if bonus:
        parts = []
        for name, total in bonus.items():
            if name in ("CRIT Rate", "CRIT DMG"):
                parts.append(f"{name} +{_pct(total, 3)}")
            else:
                parts.append(f"{name} +{_num(total, 3)}")
        out.append("Trace Stat Bonuses: " + " | ".join(parts))
    return out


def _hsr_character(data: dict) -> dict:
    sections: list[BetaSectionEntry] = []
    skills = data.get("skills") or {}
    defs: dict[str, tuple[str, str]] = {}

    def collect_extras(extra: Any) -> list[str]:
        names: list[str] = []
        for eid, entry in (extra.items() if isinstance(extra, dict) else ()):
            if not isinstance(entry, dict):
                continue
            nm = _clean(entry.get("name"))
            ds = _clean(entry.get("desc"))
            if nm and ds:
                defs[str(eid)] = (nm, ds)
                names.append(nm)
        return names

    for skill_id in sorted((skills or {}), key=lambda k: str(k)):
        item = skills[skill_id]
        if not isinstance(item, dict):
            continue
        tag = str(item.get("type_name") or "").strip()
        name = _clean(item.get("name"))
        desc = _clean(item.get("desc"))
        if not name and not desc:
            continue
        collect_extras(item.get("extra"))
        sections.append(BetaSectionEntry(
            title=f"{tag}: {name}" if tag else name, category=str(tag or "Skills"),
            tag="[NEW]", meta=str(item.get("tag") or "").title(), lines=_lines(desc),
        ))

    points = data.get("points") or {}
    for node_key in sorted((points or {}), key=lambda k: (len(str(k)), str(k))):
        node = points[node_key]
        if not isinstance(node, dict):
            continue
        for tier in node.values():
            if not isinstance(tier, dict):
                continue
            name = _clean(tier.get("point_name"))
            desc = _clean(tier.get("point_desc"))
            collect_extras(tier.get("extra"))
            if not (name or desc):
                continue
            sections.append(BetaSectionEntry(
                title=name or "Trace", category="Traces", tag="[NEW]", meta="",
                lines=_lines(desc),
            ))
            break

    unique = data.get("unique") or {}
    for ukey in sorted((unique or {}), key=str):
        item = unique[ukey]
        if not isinstance(item, dict):
            continue
        name = _clean(item.get("name"))
        desc = _clean(item.get("desc"))
        if not (name or desc):
            continue
        sections.append(BetaSectionEntry(
            title=name or "Exclusive Effect", category="Exclusive Effect", tag="[NEW]",
            meta=str(item.get("tag") or "").title(), lines=_lines(desc),
        ))

    ranks = data.get("ranks") or {}
    for level in sorted(ranks, key=lambda k: int(k) if str(k).isdigit() else 0):
        item = ranks[level]
        if not isinstance(item, dict):
            continue
        name = _clean(item.get("name"))
        desc = _clean(item.get("desc"))
        collect_extras(item.get("extra"))
        if not (name or desc):
            continue
        sections.append(BetaSectionEntry(
            title=f"E{level}" + (f" — {name}" if name else ""), category="Eidolons",
            tag="[NEW]", meta="", lines=_lines(desc),
        ))

    return {
        "element": str(data.get("damage_type") or "").strip(),
        "role": str(data.get("base_type") or "").strip(),
        "camp": "",
        "stats_lines": _hsr_stats(data),
        "sections": sections,
        "mechanic_defs": list(defs.values()),
    }


# --------------------------------------------------------------------------- GI kit
_GI_WEAPON_LABELS = {
    "WEAPON_SWORD_ONE_HAND": "Sword",
    "WEAPON_CLAYMORE": "Claymore",
    "WEAPON_POLE": "Polearm",
    "WEAPON_CATALYST": "Catalyst",
    "WEAPON_BOW": "Bow",
}


def _gi_character(data: dict) -> dict:
    sections: list[BetaSectionEntry] = []
    info = data.get("chara_info") or {}
    for skill in data.get("skills") or []:
        if not isinstance(skill, dict):
            continue
        name = _clean(skill.get("name"))
        desc = _clean(skill.get("desc"))
        if not (name or desc):
            continue
        promote = skill.get("promote") or {}
        rows: list[str] = []
        top = promote.get("10") or (promote.get("1") if isinstance(promote, dict) else None)
        if isinstance(top, dict):
            params = top.get("param") or []
            for spec in top.get("desc") or []:
                label = str(spec).split("|")[0].strip()
                if not label:
                    continue
                idx_match = re.search(r"param(\d+)", str(spec))
                if not idx_match:
                    continue
                idx = int(idx_match.group(1)) - 1
                if idx < 0 or idx >= len(params):
                    continue
                raw = params[idx]
                value = _pct(raw) if float(raw or 0) < 4 else _num(raw)
                if value:
                    rows.append(f"{label}: {value}")
        sections.append(BetaSectionEntry(
            title=name or "Talent", category="Talents", tag="[NEW]", meta="",
            lines=_lines(desc) + rows,
        ))

    for passive in data.get("passives") or []:
        if not isinstance(passive, dict):
            continue
        name = _clean(passive.get("name"))
        if not name:
            continue
        sections.append(BetaSectionEntry(
            title=name, category="Passives", tag="[NEW]", meta="",
            lines=_lines(passive.get("desc")),
        ))

    for idx, con in enumerate(data.get("constellations") or [], start=1):
        if not isinstance(con, dict):
            continue
        name = _clean(con.get("name"))
        if not name:
            continue
        sections.append(BetaSectionEntry(
            title=f"C{idx} — {name}", category="Constellations", tag="[NEW]", meta="",
            lines=_lines(con.get("desc")),
        ))

    stats: list[str] = []
    for label, key in (("CRIT Rate", "crit_rate"), ("CRIT DMG", "crit_dmg")):
        val = data.get(key)
        if val is not None:
            p = _pct(val, 2)
            if p:
                stats.append(f"{label} {p}")
    em = data.get("elemental_mastery")
    if em:
        stats.append(f"Elemental Mastery {_num(em)}")
    title = _clean(info.get("title"))
    constel = _clean(info.get("constellation"))
    sub = " · ".join(x for x in (title, (f"Constellation: {constel}" if constel else "")) if x)

    return {
        "element": str(data.get("element") or "").strip(),
        "role": _GI_WEAPON_LABELS.get(str(data.get("weapon") or ""), ""),
        "camp": "",
        "subtext": f"-# {sub}" if sub else "",
        "stats_lines": stats,
        "sections": sections,
    }


# --------------------------------------------------------------------------- WW kit
def _ww_character(data: dict) -> dict:
    sections: list[BetaSectionEntry] = []
    trees = data.get("skill_trees") or {}
    for node_key in sorted((trees or {}), key=lambda k: int(k) if str(k).isdigit() else 0):
        node = trees[node_key]
        if not isinstance(node, dict):
            continue
        skill = node.get("skill") or {}
        if not isinstance(skill, dict):
            continue
        name = _clean(skill.get("name"))
        if not name:
            continue
        stype = str(skill.get("type") or "").strip() or "Skill"
        desc = _clean(skill.get("desc"))
        rows: list[str] = []
        levels = skill.get("level") or {}
        for spec_key in sorted((levels or {}), key=lambda k: int(k) if str(k).isdigit() else 0):
            spec = levels[spec_key]
            if not isinstance(spec, dict):
                continue
            label = _clean(spec.get("name"))
            params = spec.get("param") or []
            if not params or not isinstance(params[0], list):
                continue
            col = params[0]
            top = col[-1] if col else ""
            if label and top:
                rows.append(f"{label}: {top}")
        if rows:
            rows = ["**Skill Attributes (Lv. 10)**"] + rows
        sections.append(BetaSectionEntry(
            title=f"{stype}: {name}", category=stype, tag="[NEW]", meta="",
            lines=_lines(desc) + rows,
        ))

    chains = data.get("chains") or {}
    for level in sorted(chains, key=lambda k: int(k) if str(k).isdigit() else 0):
        item = chains[level]
        if not isinstance(item, dict):
            continue
        name = _clean(item.get("name"))
        desc = _clean(item.get("desc"))
        if not (name or desc):
            continue
        sections.append(BetaSectionEntry(
            title=f"Sequence Node {level}" + (f" — {name}" if name else ""),
            category="Resonance Chain", tag="[NEW]", meta="", lines=_lines(desc),
        ))

    stats: list[str] = []
    stat_table = data.get("stats") or {}
    if isinstance(stat_table, dict):
        max_block = None
        for key in sorted(stat_table, key=lambda k: int(k) if str(k).isdigit() else -1):
            if isinstance(stat_table[key], dict):
                max_block = stat_table[key]
        if isinstance(max_block, dict):
            lvl = max_block.get("90") or max_block.get("1")
            if isinstance(lvl, dict):
                life, atk, df = lvl.get("life"), lvl.get("atk"), lvl.get("def")
                if life is not None and atk is not None and df is not None:
                    stats.append(f"Lv. 90 — HP {_num(life)} · ATK {_num(atk)} · DEF {_num(df)}")

    element = data.get("element")
    try:
        element_label = WW_ELEMENTS.get(int(element), "")
    except (TypeError, ValueError):
        element_label = ""
    weapon = data.get("weapon")
    try:
        weapon_label = WW_WEAPONS.get(int(weapon), "")
    except (TypeError, ValueError):
        weapon_label = ""

    return {
        "element": element_label,
        "role": weapon_label,
        "camp": "",
        "stats_lines": stats,
        "sections": sections,
    }


_CHARACTER_BUILDERS = {
    "zzz": _zzz_character,
    "hsr": _hsr_character,
    "gi": _gi_character,
    "ww": _ww_character,
}


# --------------------------------------------------------------------------- equipment
def _equip_from_detail(ns: str, kind: str, data: dict, listing: dict) -> dict:
    """Pull the display fields of one weapon / relic out of its detail JSON."""
    stats_line = ""
    effect_title = ""
    lines: list[str] = []
    sub_type = ""

    if ns == "zzz" and kind == "weapon":
        bp = data.get("base_property") or {}
        rp = data.get("rand_property") or {}
        atk = listing.get("atk")
        if atk:
            stats_line = f"Base ATK {_num(atk)}"
        sub_name = _clean(rp.get("name2") or rp.get("name"))
        if sub_name:
            sub_type = sub_name
        talents = data.get("talents") or {}
        first = None
        for key in sorted(talents, key=lambda k: int(k) if str(k).isdigit() else 0):
            if isinstance(talents[key], dict):
                first = talents[key]
                break
        if isinstance(first, dict):
            effect_title = _clean(first.get("name"))
            lines = _lines(first.get("desc"))
    elif ns == "zzz" and kind == "equipment":
        d2, d4 = _clean(data.get("desc2")), _clean(data.get("desc4"))
        if d2:
            lines.append(f"2-Piece: {d2}")
        if d4:
            lines.append(f"4-Piece: {d4}")
    elif ns == "hsr" and kind == "lightcone":
        stats_table = data.get("stats") or {}
        last = None
        for key in sorted(stats_table, key=lambda k: int(k) if str(k).isdigit() else -1):
            if isinstance(stats_table[key], dict):
                last = stats_table[key]
        if isinstance(last, dict):
            hp, atk, df = last.get("base_hp"), last.get("base_attack"), last.get("base_defence")
            if hp is not None and atk is not None:
                stats_line = f"Lv. 80 — HP {_num(hp)} · ATK {_num(atk)}"
                if df is not None:
                    stats_line += f" · DEF {_num(df)}"
        ref = data.get("refinements") or {}
        if isinstance(ref, dict):
            effect_title = _clean(ref.get("name"))
            lines = _lines(ref.get("desc"))
    elif ns == "hsr" and kind == "relicset":
        sets = data.get("require_num") or data.get("set") or {}
        for num in sorted(sets, key=lambda k: int(k) if str(k).isdigit() else 0):
            entry = sets[num]
            desc = _clean((entry or {}).get("desc") if isinstance(entry, dict) else entry)
            if desc:
                lines.append(f"{num}-Piece: {desc}")
    elif ns == "gi" and kind == "weapon":
        props = data.get("weapon_prop") or []
        main = None
        for prop in props:
            if isinstance(prop, dict) and "BASE_ATTACK" in str(prop.get("prop_type") or ""):
                main = prop
                break
        if isinstance(main, dict):
            stats_line = f"Base ATK {_num(main.get('init_value'))}"
        ref = (data.get("refinement") or {}).get("1") or {}
        if isinstance(ref, dict):
            effect_title = _clean(ref.get("name"))
            lines = _lines(ref.get("desc"))
    elif ns == "gi" and kind == "artifact":
        sets = data.get("set") or {}
        for sid in sorted(sets, key=str):
            entry = sets[sid] or {}
            name = _clean((entry.get("name") or {}).get("en") if isinstance(entry.get("name"), dict) else entry.get("name"))
            desc = _clean((entry.get("desc") or {}).get("en") if isinstance(entry.get("desc"), dict) else entry.get("desc"))
            if desc:
                lines.append(f"{name}: {desc}" if name else desc)
    elif ns == "ww" and kind == "weapon":
        effect_title = _clean(data.get("effect_name"))
        lines = _lines(data.get("effect"))
        stats_table = data.get("stats") or {}
        block = None
        for key in sorted(stats_table, key=lambda k: int(k) if str(k).isdigit() else -1):
            if isinstance(stats_table[key], dict):
                block = stats_table[key]
        if isinstance(block, dict):
            top = block.get("90") or block.get("1")
            if isinstance(top, list):
                parts = []
                for stat in top:
                    if isinstance(stat, dict):
                        parts.append(f"{stat.get('name')} {_num(stat.get('value'), 2)}")
                if parts:
                    stats_line = " · ".join(parts)
    elif ns == "ww" and kind == "echo":
        skill = data.get("skill") or {}
        if isinstance(skill, dict):
            lines = _lines(skill.get("desc"))
        groups = data.get("group") or {}
        for gid in sorted(groups, key=str):
            group = groups[gid] or {}
            gname = _clean(group.get("name"))
            for num in sorted((group.get("set") or {}), key=lambda k: int(k) if str(k).isdigit() else 0):
                entry = (group.get("set") or {})[num] or {}
                desc = _clean(entry.get("desc"))
                if desc:
                    lines.append(f"{gname} {num}-Piece: {desc}" if gname else f"{num}-Piece: {desc}")

    return {"stats_line": stats_line, "effect_title": effect_title, "lines": lines,
            "sub_type": sub_type}


# --------------------------------------------------------------------------- images
_MISSING_IMAGE_RE = re.compile(r"(?:^|/)missing\.webp$", re.I)


def _usable_image(url: str) -> str:
    """A gallery URL, or '' when it is a placeholder the database itself uses."""
    u = (url or "").strip()
    if not u.lower().startswith(("http://", "https://")):
        return ""
    if _MISSING_IMAGE_RE.search(u):
        return ""
    return u


async def _resolve_image(fetcher, entry: dict, locked: dict, cache: dict) -> str:
    """Changelog art, locked once seen. Verification is best-effort and never fatal."""
    key = entry.get("id") or entry.get("name") or ""
    if not key:
        return ""
    if key in cache:
        return cache[key]
    cached = locked.get(key)
    if isinstance(cached, dict) and cached.get("url"):
        cache[key] = str(cached["url"])
        return cache[key]
    url = _usable_image(entry.get("image") or "")
    if url:
        try:
            ok = await fetcher.verify_media(url)
        except Exception:  # noqa: BLE001 - a preflight failure must never break a card
            ok = False
        if ok:
            cache[key] = url
            return url
    cache[key] = ""
    return ""


# --------------------------------------------------------------------------- run
def _game_ns(game: Game) -> str:
    beta_cfg = getattr(game, "beta", None) or {}
    return str(beta_cfg.get("nanoka") or "").strip()


def _changelog_url(game: Game) -> str:
    beta_cfg = getattr(game, "beta", None) or {}
    return str(beta_cfg.get("changelog") or "").strip()


def _budget(ctx) -> dict:
    s = ctx.settings
    env = s.env

    def _int(name: str, default: int, low: int, high: int) -> int:
        raw = str(env.get(name, "") or "").strip()
        if not raw:
            return default
        try:
            return max(low, min(high, int(raw)))
        except ValueError:
            return default

    return {
        "min_poll_min": _int("BETA_MIN_POLL_MINUTES", 30, 0, 1440),
        "max_chars": _int("BETA_MAX_CHARACTERS", 4, 1, 8),
        "max_equip": _int("BETA_MAX_EQUIPMENT", 12, 1, 24),
        "max_changed": _int("BETA_MAX_CHANGES", 8, 0, 16),
        "max_requests": _int("BETA_MAX_REQUESTS", 48, 4, 120),
    }


async def _changelog_entries(ctx, game: Game) -> tuple[list[dict], str, str]:
    """(entries, rev_label, rev_key) from the game's beta changelog, or ([], '', '')."""
    ch_url = _changelog_url(game)
    if not ch_url:
        return [], "", ""
    text = await ctx.fetcher.get_text(ch_url, source="beta-changelog", retries=1)
    if not text:
        ctx.warnings.append(f"{game.short} beta: changelog unavailable; falling back to the manifest")
        return [], "", ""
    revisions = parse_changelog(text)
    if not revisions:
        return [], "", ""
    top = revisions[0]
    label = str(top.get("label") or "").strip()
    if top.get("date"):
        label = f"{label} \u2014 {top['date']}"
    return list(top.get("entries") or []), label, str(top.get("label") or "").strip()


def _entry_role(ns: str, url: str) -> str:
    low = (url or "").lower()
    if "/agents/" in low or "/characters/" in low or "/resonators/" in low:
        return "character"
    if "/w-engines/" in low or "/light-cones/" in low or "/lightcones/" in low or "/weapons/" in low:
        return "weapon"
    if ("/drive-discs/" in low or "/relics/" in low or "/relicsets/" in low
            or "/planar-ornaments/" in low or "/artifacts/" in low or "/echoes/" in low
            or "/echo/" in low):
        return "relic"
    return ""


async def build_patch(ctx, game: Game, manifest: dict, budget: dict) -> BetaPatch | None:
    """Assemble the deliverable card set for one game, or None when there is nothing new.

    Two discovery paths, in order:
      1. a gachabase beta changelog (GI / HSR / ZZZ) names the newest revision AND every
         entry it touched, so "new" and "changed" can be told apart by id;
      2. the nanoka manifest alone (Wuthering Waves, which has no gachabase site) — it
         only lists what is NEW in `latest`, which is exactly the right scope there.
    """
    ns = _game_ns(game)
    kinds = NANOKA_KINDS.get(ns)
    if not ns or kinds is None:
        return None

    m_game = manifest_game(manifest, ns)
    version = str(m_game.get("latest") or "").strip()
    if not version:
        log.info("[%s] beta: no manifest version for %s", game.key, ns)
        return None

    record = ctx.state.beta_record(game.key)
    entries, ch_label, ch_key = await _changelog_entries(ctx, game)
    rev_key = ch_key or version
    rev_id = stable_hash([game.key, rev_key, version])
    if rev_id == str(record.get("latest_rev") or "").strip():
        log.info("[%s] beta: revision %s already published", game.key, rev_key)
        return None

    rev_label = ch_label or f"v{version}"
    patch = BetaPatch(game_key=game.key, beta_version=_display_version(version),
                      rev_label=rev_label, rev_id=rev_id,
                      source_url=_changelog_url(game) or f"{STATIC_BASE}/{ns}/{version}")

    new_char_ids = manifest_new_ids(manifest, ns, kinds["new_keys"]["character"])
    new_weapon_ids = manifest_new_ids(manifest, ns, kinds["new_keys"]["weapon"])
    new_relic_ids = manifest_new_ids(manifest, ns, kinds["new_keys"]["relic"])

    locked = record.get("locked_images") or {}
    cache: dict[str, str] = {}
    snapshots = record.get("snapshots") or {}

    char_label = kinds["character_label"].lower()
    if entries:
        char_entries = [e for e in entries
                        if (e.get("section") or "").strip().lower() == char_label]
        equip_entries = [e for e in entries if e not in char_entries]
    else:
        char_entries = [{"name": "", "url": f"/{kinds['character_label'].lower()}/{cid}/",
                         "diff": "", "image": "", "section": kinds["character_label"]}
                        for cid in sorted(new_char_ids)]
        equip_entries = [
            {"name": "", "url": f"/{kinds['weapon']['detail']}/{wid}/", "diff": "",
             "image": "", "section": kinds["weapon"]["label"]}
            for wid in sorted(new_weapon_ids)
        ] + [
            {"name": "", "url": f"/{kinds['relic']['detail']}/{rid}/", "diff": "",
             "image": "", "section": kinds["relic"]["label"]}
            for rid in sorted(new_relic_ids)
        ]

    requests = 2            # manifest + changelog are already spent
    max_changed_sections = 3
    for entry in char_entries:
        item_id = _entry_id(entry)
        if not item_id:
            continue
        is_new = item_id in new_char_ids or (not new_char_ids and bool(entries) is False)
        pool = [c for c in patch.characters if c.is_new == is_new]
        cap = budget["max_chars"] if is_new else budget["max_changed"]
        if len(pool) >= cap:
            continue
        if requests >= budget["max_requests"]:
            ctx.warnings.append(f"{game.short} beta: request budget reached; remaining "
                                f"entries deferred to the next run")
            break
        data = await _detail(ctx.fetcher, ns, version, kinds["new_keys"]["character"], item_id)
        requests += 1
        if not data:
            ctx.warnings.append(f"{game.short} beta: no kit data for id {item_id}; skipped")
            continue
        builder = _CHARACTER_BUILDERS.get(ns)
        built = builder(data) if builder else None
        if not built or not built.get("sections"):
            log.info("[%s] beta: id %s has no readable kit yet", game.key, item_id)
            continue
        try:
            raw_rank = int(data.get("rarity"))
        except (TypeError, ValueError):
            raw_rank = 4
        # nanoka's ZZZ export labels S-Rank as 4 and A-Rank as 3; the card shows them as
        # the 5-star and 4-star ranks players recognise.
        rarity = (raw_rank + 1) if ns == "zzz" and raw_rank in (3, 4) else max(1, min(5, raw_rank))
        name = str(entry.get("name") or "").strip() or _clean(data.get("name")) or f"ID {item_id}"
        snap_key = f"{ns}:{item_id}"
        prev = snapshots.get(snap_key)
        prev_sig = str(prev.get("signature") or "") if isinstance(prev, dict) else ""
        cur_sig = stable_hash([s.title for s in built["sections"]])
        if is_new:
            tag = "[NEW]"
        elif prev_sig and prev_sig == cur_sig:
            # We hold the previous revision's kit and its sections are identical: the only
            # thing a revision can still have moved is wording.
            tag = "[TEXT FIX]"
        else:
            # Either the sections differ from the stored kit, or this is the first time we
            # have seen the character and there is no baseline to diff against. The
            # changelog lists it as UPDATED, so "changed" is the honest label — inventing
            # a [BUFF]/[NERF] direction from a single snapshot is not.
            tag = "[CHANGED]"
        sections = list(built["sections"])
        if not is_new and len(sections) > max_changed_sections:
            sections = sections[:max_changed_sections]
        image = await _resolve_image(
            ctx.fetcher, {"id": snap_key, "image": entry.get("image")}, locked, cache)
        if image:
            requests += 1
        patch.characters.append(BetaCharacter(
            id=snap_key, name=name, rarity=rarity,
            element=str(built.get("element") or ""), role=str(built.get("role") or ""),
            subtext=str(built.get("subtext") or ""),
            stats_lines=list(built.get("stats_lines") or []),
            sections=[BetaSectionEntry(title=s.title, category=s.category, tag=tag,
                                       meta=s.meta, lines=list(s.lines))
                      for s in sections],
            mechanic_defs=list(built.get("mechanic_defs") or []),
            image_url=image, is_new=is_new, diff_url=str(entry.get("diff") or ""),
        ))

    listing_cache: dict[str, dict] = {}
    for entry in equip_entries:
        if len(patch.equipment) >= budget["max_equip"]:
            break
        item_id = _entry_id(entry)
        if not item_id:
            continue
        if requests >= budget["max_requests"]:
            ctx.warnings.append(f"{game.short} beta: request budget reached; remaining "
                                f"equipment deferred")
            break
        role = _entry_role(ns, str(entry.get("url") or ""))
        if role not in ("weapon", "relic"):
            role = "weapon" if item_id in new_weapon_ids else "relic"
        detail_kind = kinds[role]["detail"]
        listing_kind = kinds[role]["listing"]
        if listing_kind not in listing_cache:
            listing_cache[listing_kind] = await _listing(ctx.fetcher, ns, version, listing_kind)
            requests += 1
        listing = listing_cache.get(listing_kind) or {}
        listing_entry = listing.get(item_id) if isinstance(listing, dict) else None
        data = await _detail(ctx.fetcher, ns, version, detail_kind, item_id)
        requests += 1
        fields: dict[str, Any] = {"stats_line": "", "effect_title": "", "lines": [], "sub_type": ""}
        if data:
            fields = _equip_from_detail(
                ns, detail_kind, data, listing_entry if isinstance(listing_entry, dict) else {})
        if not fields["lines"] and not fields["stats_line"]:
            continue
        rarity = None
        if isinstance(listing_entry, dict):
            try:
                rarity = int(listing_entry.get("rank") or 0) or None
            except (TypeError, ValueError):
                rarity = None
        name = str(entry.get("name") or "").strip()
        if not name:
            name = (_clean((listing_entry or {}).get("en") if isinstance(listing_entry, dict) else None)
                    or _clean(data.get("name")) or f"ID {item_id}")
        image = await _resolve_image(
            ctx.fetcher, {"id": f"{ns}:{item_id}", "image": entry.get("image")}, locked, cache)
        if image:
            requests += 1
        patch.equipment.append(BetaEquipment(
            id=f"{ns}:{item_id}", name=name,
            category_label=str(kinds[role]["label"]), rarity=rarity,
            sub_type=str(fields.get("sub_type") or ""),
            tag="[NEW]" if (item_id in new_weapon_ids or item_id in new_relic_ids) else "[CHANGED]",
            stats_line=str(fields.get("stats_line") or ""),
            effect_title=str(fields.get("effect_title") or ""),
            lines=list(fields.get("lines") or []),
            image_url=image, diff_url=str(entry.get("diff") or ""),
        ))

    if not patch.characters and not patch.equipment:
        log.info("[%s] beta: revision %s has nothing readable to publish", game.key, rev_label)
        return None
    return patch


async def run(ctx) -> None:
    """Post one beta card set per game that has a new revision. Safe to call every run."""
    if "beta" not in ctx.settings.features or not ctx.active:
        return
    enabled = {g.key for g in ctx.games} & set(ctx.settings.beta_games)
    if not enabled:
        return
    budget = _budget(ctx)
    manifest = await fetch_manifest(ctx.fetcher)
    if not manifest:
        ctx.warnings.append("beta: manifest unavailable; no beta cards this run")
        return

    for game in ctx.games:
        if game.key not in enabled:
            continue
        record = ctx.state.beta_record(game.key)
        last_poll = int(record.get("last_poll") or 0)
        if budget["min_poll_min"] and ctx.now - last_poll < budget["min_poll_min"] * 60:
            continue
        record["last_poll"] = ctx.now
        ephemeral = ctx.settings.dry_run or ctx.settings.test_mode
        if not ephemeral:
            ctx.state.save()

        try:
            patch = await build_patch(ctx, game, manifest, budget)
        except Exception as exc:  # noqa: BLE001 - one game must never sink the run
            log.exception("beta: %s failed to build its patch", game.key)
            ctx.warnings.append(f"{game.short} beta: {type(exc).__name__}: {exc}")
            continue
        if patch is None:
            continue
        await _deliver(ctx, game, patch, record, ephemeral)


async def _deliver(ctx, game: Game, patch: BetaPatch, record: dict, ephemeral: bool) -> None:
    hook = ctx.settings.webhook("beta", game.key)
    if not hook:
        ctx.warnings.append(
            f"{game.short} beta: missing dedicated webhook; add "
            f"{ctx.settings.expected_webhook_names('beta', game.key)}")
        return
    fp = webhook_fingerprint(hook)
    fp = stable_hash([fp, hook.partition("?")[2]])
    if record.get("route") and record.get("route") != fp:
        ctx.warnings.append(f"{game.short} beta: destination changed; review beta state before posting")
        return
    record.setdefault("route", fp)

    ping = ctx.settings.ping("beta", game.key)
    try:
        payloads, char_map = beta_payloads_with_map(
            game, patch, ctx.settings, ping)
    except Exception as exc:  # noqa: BLE001 - a render bug must not post a half card
        log.exception("beta: %s failed to render", game.key)
        ctx.warnings.append(f"{game.short} beta: render failed ({type(exc).__name__}: {exc})")
        return
    if ctx.settings.test_mode:
        from .cards import mark_test

        payloads = [mark_test(p) for p in payloads]

    revisions = record.setdefault("revisions", {})
    entry = revisions.get(patch.rev_id)
    if not isinstance(entry, dict):
        entry = {"status": "partial", "ts": ctx.now, "messages": []}
        revisions[patch.rev_id] = entry
    messages = entry.setdefault("messages", [])
    sent = 0
    for idx in range(len(messages), len(payloads)):
        result = await ctx.webhook.send(hook, payloads[idx], stop_on_ambiguous=True)
        if result.ambiguous or (result.ok and not result.message_id):
            entry["ambiguous"] = True
            if not ephemeral:
                ctx.state.save()
            ctx.warnings.append(
                f"{game.short} beta: ambiguous Discord outcome on page {idx + 1}; "
                f"held to prevent a duplicate post")
            return
        if not result.ok:
            ctx.warnings.append(
                f"{game.short} beta: page {idx + 1} failed ({result.status}); will retry")
            return
        messages.append(result.message_id)
        if not ephemeral:
            ctx.state.save()
        sent += 1

    if not ephemeral:
        locked = record.setdefault("locked_images", {})
        for char in patch.characters:
            if char.image_url:
                locked[char.id] = {"url": char.image_url, "locked": True, "ts": ctx.now}
        for equip in patch.equipment:
            if equip.image_url:
                locked[equip.id] = {"url": equip.image_url, "locked": True, "ts": ctx.now}
        snaps = record.setdefault("snapshots", {})
        for char in patch.characters:
            snaps[char.id] = {"ts": ctx.now,
                              "signature": stable_hash([s.title for s in char.sections])}
        record["latest_rev"] = patch.rev_id
        entry["status"] = "posted"
        entry["label"] = patch.rev_label
        entry["characters"] = char_map
        ctx.state.save()

    names = ", ".join(c.name for c in patch.characters) or "no new characters"
    ctx.report.append(
        f"🧪 {game.short} {patch.beta_version} beta ({patch.rev_label}): "
        f"{len(payloads)} page(s) — {names}"
        + (f", {len(patch.equipment)} equipment entr(ies)" if patch.equipment else "")
        + (" [DRY RUN]" if ephemeral and not ctx.settings.test_mode else "")
    )
    if sent:
        log.info("[%s] beta: delivered %d page(s) for %s", game.key, sent, patch.rev_label)
