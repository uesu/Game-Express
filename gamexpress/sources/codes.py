"""Redemption-code sources (all verified live 2026-09-25 unless noted).

  hoyolab       official HoYoLAB game-page module — codes appear ONLY during livestreams
                .../circle/channel/guide/material?game_id=2 -> data.modules[].exchange_group.bonuses[]
  seria         https://hoyo-codes.seria.moe/codes?game=genshin|hkrpg|nap   (redeem-validated OK / NOT_OK)
  humbao        github.com/Hum-Bao/hoyoverse-codes  GENSHIN|HSR|ZZZ.txt  (redeem-validated daily, US region)
  ogc           Open Gacha Codes  https://api.ennead.cc/codes/genshin|starrail|zenless|wuwa
                (NEW 2026: multi-source collector by the ennead author — the only JSON API with
                Wuthering Waves; NOISY: it also lists stale / concatenated entries, so it can only
                CONFIRM a code, never post one alone)
  ennead        https://api.ennead.cc/mihoyo/{genshin|starrail|zenless}/codes  ({active, inactive})
  fandom        MediaWiki API wikitext (same query seria + PromoGacha use)
  codehub       PromoGacha's GitHub-hosted data/codes.json (daily GHA; includes Wuthering Waves)
  wuthering.gg  https://wuthering.gg/codes  (HTML table; marks expired codes explicitly)
  x             official tweets (codes are extracted only with explicit code wording)

Every parser also reports codes a source explicitly marks EXPIRED (seria NOT_OK, ennead
`inactive`, fandom expired rows, wuthering.gg "Expired") as CodeHit(expired=True): the
code gate never posts a code that a source calls expired unless an official source or a
redeem-validator vouches for it.
"""

from __future__ import annotations

import asyncio
import logging
import re

from ..http import Fetcher
from ..models import CodeHit

log = logging.getLogger("gamexpress.codes")

HOYOLAB_MATERIAL = "https://bbs-api-os.hoyolab.com/community/painter/wapi/circle/channel/guide/material"
SERIA = "https://hoyo-codes.seria.moe/codes"
ENNEAD = "https://api.ennead.cc/mihoyo/{}/codes"
OGC = "https://api.ennead.cc/codes/{}"
FANDOM = ("https://{wiki}.fandom.com/api.php?action=query&prop=revisions&titles={page}"
          "&rvprop=content&rvslots=main&format=json")
WUTHERING_GG = "https://wuthering.gg/codes"
# GitHub-hosted data: raw.githubusercontent.com first, jsDelivr's GitHub mirror as the fallback
CODEHUB = ("gripcrip-blip/codehub", "main", "data/codes.json")
HUMBAO = ("Hum-Bao/hoyoverse-codes", "main", "{}.txt")

# Real codes are 5-20 chars (longest known: WUTHERINGWAVESGIFT = 18). Longer tokens are
# scraper artifacts such as two codes glued together (seen live in the OGC feed).
CODE_SHAPE = re.compile(r"^[A-Z0-9]{5,20}$")
JUNK_CODES = {"TEST", "TESTCODE", "EXAMPLE", "SAMPLE", "CODE", "REDEEM", "EXPIRED", "COPY", "NEW"}

# Which sources share an origin — codes need agreement between DIFFERENT families.
SOURCE_FAMILY = {"ogc": "ennead", "ennead": "ennead"}
VALIDATORS = {"seria", "humbao", "hoyolab"}      # a real redemption attempt / the official module


def family(source: str) -> str:
    return SOURCE_FAMILY.get(source, source)


def sanitize(code: str) -> str:
    code = (code or "").split("/")[0].split(";")[0]
    code = re.sub(r"\[\d+\]", "", code).replace("NEW!", "").replace("Quick Redeem", "")
    code = re.sub(r"[^A-Za-z0-9]", "", code).upper()
    if code in JUNK_CODES:
        return ""
    return code if CODE_SHAPE.match(code) and re.search(r"[A-Z]", code) else ""


def drop_concatenations(hits: list[CodeHit]) -> list[CodeHit]:
    """Remove 'AAAA…BBBB…' entries that are two other codes from the same batch glued
    together (a known collector artifact: XVIZDH2B9WGX + EHVE2TEAFY6O)."""
    codes = {h.code for h in hits}
    out = []
    for h in hits:
        glued = any(h.code.startswith(a) and h.code[len(a):] in codes
                    for a in codes if a != h.code and len(a) < len(h.code))
        if not glued:
            out.append(h)
    return out


# ------------------------------------------------------------------ parsers (pure, tested)
def parse_hoyolab_material(data: dict) -> list[CodeHit]:
    hits = []
    for module in ((data or {}).get("data") or {}).get("modules") or []:
        group = (module or {}).get("exchange_group") or {}
        for bonus in group.get("bonuses") or []:
            code = sanitize(bonus.get("exchange_code") or "")
            if not code:
                continue
            if str(bonus.get("code_status") or "ON").upper() in ("OFF", "EXPIRED", "INVALID"):
                continue
            rewards = [f"×{b.get('bonus_num')}" for b in (bonus.get("icon_bonuses") or []) if b.get("bonus_num")]
            hits.append(CodeHit(code, "hoyolab", rewards or None, verified=True))
    return hits


def parse_seria(data: dict) -> list[CodeHit]:
    hits = []
    for c in (data or {}).get("codes") or []:
        code = sanitize(c.get("code") or "")
        if not code:
            continue
        status = str(c.get("status")).upper()
        if status == "OK":
            hits.append(CodeHit(code, "seria", c.get("rewards") or None, verified=True))
        elif status in ("NOT_OK", "EXPIRED", "INVALID"):
            hits.append(CodeHit(code, "seria", None, expired=True))
    return hits


def parse_ennead(data: dict) -> list[CodeHit]:
    hits = []
    for c in (data or {}).get("active") or []:
        code = sanitize(c.get("code") or "")
        rewards = [r for r in (c.get("rewards") or []) if r and r.lower() != "free items"]
        if code:
            hits.append(CodeHit(code, "ennead", rewards or None))
    for c in (data or {}).get("inactive") or []:
        code = sanitize(c.get("code") or "")
        if code:
            hits.append(CodeHit(code, "ennead", None, expired=True))
    return hits


def parse_ogc(data) -> list[CodeHit]:
    """Open Gacha Codes: [{"code": "...", "rewards": ["Astrite x50", ...]}]  (active only)."""
    hits: list[CodeHit] = []
    seen: set[str] = set()
    for c in data if isinstance(data, list) else []:
        if not isinstance(c, dict):
            continue
        code = sanitize(c.get("code") or "")
        if not code or code in seen:
            continue
        seen.add(code)
        rewards = [str(r).replace(" x", " ×") for r in (c.get("rewards") or [])
                   if r and "File:" not in str(r)]
        hits.append(CodeHit(code, "ogc", rewards or None))
    return drop_concatenations(hits)


def parse_humbao(text: str) -> list[CodeHit]:
    """Hum-Bao/hoyoverse-codes: one redeem-validated code per line."""
    hits = []
    for line in (text or "").splitlines():
        code = sanitize(line.strip())
        if code and not line.lstrip().startswith("#"):
            hits.append(CodeHit(code, "humbao", None, verified=True))
    return hits


_ROW_TEMPLATE = re.compile(r"\{\{\s*(?:Redemption\s+)?Code\s+Row\s*\|(?P<body>.*?)\}\}", re.I | re.S)


def parse_fandom(data: dict) -> list[CodeHit]:
    pages = ((data or {}).get("query") or {}).get("pages") or {}
    wikitext = ""
    for page in pages.values():
        revs = page.get("revisions") or []
        if revs:
            wikitext = (revs[0].get("slots") or {}).get("main", {}).get("*") or revs[0].get("*") or ""
            break
    if not wikitext:
        return []
    hits: list[CodeHit] = []
    # 1) template rows ({{Code Row|CODE|server|rewards…}} / {{Redemption Code Row|…}}),
    #    honoring <!-- active --> / <!-- expired --> section comments when present
    active = True
    markers = [(m.start(), "expired" not in m.group(0).lower()) for m in
               re.finditer(r"<!--[^>]*?(active|expired)[^>]*?-->", wikitext, re.I)]
    for m in _ROW_TEMPLATE.finditer(wikitext):
        while markers and markers[0][0] < m.start():
            active = markers.pop(0)[1]
        fields = [f.strip() for f in m.group("body").split("|")]
        if any(f.replace(" ", "").lower() == "notacode=yes" for f in fields):
            continue
        positional = [f for f in fields if "=" not in f]
        if not positional:
            continue
        if any(f.upper() == "CN" for f in positional[1:3]):
            continue
        code = sanitize(positional[0])
        if not code:
            continue
        expired = not active or any(re.fullmatch(r"(?:expired|ended)\s*=\s*(?:yes|true|1)", f, re.I) for f in fields)
        hits.append(CodeHit(code, "fandom", None, expired=expired))
    # 2) plain wikitable (Wuthering Waves page): first cell of each row; rows after an
    #    "Expired" heading are reported as expired
    if not hits:
        parts = re.split(r"\n=+\s*(?:Expired|Inactive|Invalid)\b[^\n]*", wikitext, maxsplit=1, flags=re.I)
        for idx, table in enumerate(parts):
            for row in re.split(r"\n\|-", table):
                cells = [c.strip() for c in re.split(r"\|\||\n\|", row) if c.strip()]
                if not cells:
                    continue
                first = re.sub(r"<[^>]+>|'''?|\[\[|\]\]", "", cells[0]).strip(" |*")
                code = sanitize(first.split("\n")[0])
                if code and first.upper() == first.split("\n")[0].upper():
                    hits.append(CodeHit(code, "fandom", None, expired=idx > 0))
    return hits


def parse_codehub(data: dict, slug: str) -> list[CodeHit]:
    hits = []
    for c in (data or {}).get("codes") or []:
        if c.get("game") != slug:
            continue
        code = sanitize(c.get("code") or "")
        if code:
            hits.append(CodeHit(code, "codehub", c.get("reward") or None))
    return hits


_TR = re.compile(r"<tr\b([^>]*)>(.*?)</tr>", re.I | re.S)
_TD = re.compile(r"<td\b[^>]*>(.*?)</td>", re.I | re.S)
_LI = re.compile(r"<li\b[^>]*>(.*?)</li>", re.I | re.S)
_TAGS = re.compile(r"<[^>]+>")


def parse_wuthering_gg(html: str) -> list[CodeHit]:
    """wuthering.gg/codes table rows: code | COPY button (active) or 'Expired' badge | rewards."""
    hits: list[CodeHit] = []
    seen: set[str] = set()
    for attrs, body in _TR.findall(html or ""):
        cells = _TD.findall(body)
        if len(cells) < 2:
            continue
        code = sanitize(_TAGS.sub("", cells[0]).strip())
        if not code or code in seen:
            continue
        row_text = _TAGS.sub(" ", body)
        cls = (re.search(r'class\s*=\s*"([^"]*)"', attrs) or [None, ""])[1].lower()
        if "expired" in cls or re.search(r"\bexpired\b", row_text, re.I):
            expired = True
        elif "active" in cls or re.search(r"\bcopy\b", row_text, re.I):
            expired = False
        else:
            continue                                      # unknown status -> ignore
        seen.add(code)
        rewards = None
        if not expired and len(cells) >= 3:
            items = [re.sub(r"\s+", " ", _TAGS.sub("", li)).strip() for li in _LI.findall(cells[2])]
            rewards = [i for i in items if i] or None
        hits.append(CodeHit(code, "wuthering.gg", rewards, expired=expired))
    return hits


_CODE_CONTEXT = re.compile(r"(?:redemption|redeem|promo|gift|exchange)\s*codes?|\bcodes?\s*[:：]|\bcode\s*>>", re.I)
_TOKEN = re.compile(r"(?<![#@/\w.])([A-Z0-9]{6,20})(?![\w/.])")
_STOP = {
    "YOUTUBE", "TWITCH", "TIKTOK", "HOYOVERSE", "HOYOLAB", "VERSION", "SPECIAL", "PROGRAM",
    "BROADCAST", "PREVIEW", "OFFICIAL", "LIVESTREAM", "REDEEM", "REDEMPTION", "EXPIRE", "EXPIRES",
    "REWARDS", "PRIMOGEMS", "POLYCHROME", "ASTRITE", "GENSHIN", "HONKAI", "ZENLESS", "WUTHERING",
    "WAVES", "ANANTA", "IMPORTANT", "REMINDER", "UPDATE", "ANNIVERSARY", "CONGRATULATIONS",
    "NETEASE", "NEXUS", "ANIMA", "TRAILER", "TEASER", "GIVEAWAY", "WINNERS",
}


def extract_codes_from_text(text: str) -> list[str]:
    """Codes from an OFFICIAL post. Requires explicit code wording; tokens must follow it
    within 400 chars, be ALL-CAPS/digits (6-20), not hashtags/URLs/stop-words."""
    m = _CODE_CONTEXT.search(text or "")
    if not m:
        return []
    window = text[m.start(): m.start() + 400]
    explicit = bool(re.search(r"redemption\s+codes?|redeem\s+codes?", text, re.I))
    out: list[str] = []
    for tok in _TOKEN.findall(window):
        if tok in _STOP or tok in JUNK_CODES or not re.search(r"[A-Z]", tok) or tok.isdigit():
            continue
        if not explicit and not re.search(r"\d", tok):
            continue
        if tok not in out:
            out.append(tok)
    return out[:10]


# ------------------------------------------------------------------ fetchers
class CodeSources:
    """Per-run cache + in-flight de-duplication: every spec is fetched at most once per
    run even when all games prefetch concurrently (codehub's JSON is shared by 4 games)."""

    def __init__(self, fetcher: Fetcher) -> None:
        self.fetcher = fetcher
        self._inflight: dict[str, asyncio.Task] = {}

    async def _once(self, key: str, factory):
        task = self._inflight.get(key)
        if task is None:
            task = asyncio.ensure_future(factory())
            self._inflight[key] = task
        return await task

    async def _github_raw(self, repo_ref_path: tuple[str, str, str], arg: str = "", *, source: str,
                          as_json: bool = False):
        repo, ref, path = repo_ref_path
        path = path.format(arg) if "{}" in path else path
        urls = (f"https://raw.githubusercontent.com/{repo}/{ref}/{path}",
                f"https://cdn.jsdelivr.net/gh/{repo}@{ref}/{path}")
        for url in urls:
            if as_json:
                d = await self.fetcher.get_json(url, source=source, retries=1)
            else:
                d = await self.fetcher.get_text(url, source=source, retries=1)
            if d is not None:
                return d
        return None

    async def fetch(self, spec: str) -> list[CodeHit] | None:
        """spec examples: 'hoyolab:2' 'seria:genshin' 'ogc:wuwa' 'ennead:starrail' 'humbao:HSR'
        'fandom:genshin-impact/Promotional_Code' 'codehub:genshin-impact' 'wuthering.gg'.
        None = source unreachable this run."""
        return await self._once(f"spec:{spec}", lambda: self._fetch(spec))

    async def _fetch(self, spec: str) -> list[CodeHit] | None:
        kind, _, arg = spec.partition(":")
        f = self.fetcher
        if kind == "hoyolab":
            d = await f.get_json(HOYOLAB_MATERIAL, source="codes:hoyolab", params={"game_id": arg},
                                 headers={"Origin": "https://www.hoyolab.com", "x-rpc-language": "en-us"})
            return parse_hoyolab_material(d) if d is not None else None
        if kind == "seria":
            d = await f.get_json(SERIA, source="codes:seria", params={"game": arg})
            return parse_seria(d) if d is not None else None
        if kind == "ogc":
            d = await f.get_json(OGC.format(arg), source="codes:ogc")
            return parse_ogc(d) if d is not None else None
        if kind == "ennead":
            d = await f.get_json(ENNEAD.format(arg), source="codes:ennead")
            return parse_ennead(d) if d is not None else None
        if kind == "humbao":
            t = await self._once(f"humbao:{arg}", lambda: self._github_raw(HUMBAO, arg, source="codes:humbao"))
            return parse_humbao(t) if t is not None else None
        if kind == "fandom":
            wiki, _, page = arg.partition("/")
            d = await f.get_json(FANDOM.format(wiki=wiki, page=page or "Redemption_Code"),
                                 source="codes:fandom", headers={"User-Agent": "Game-Express/1.1 (code monitor)"})
            return parse_fandom(d) if d is not None else None
        if kind == "codehub":
            d = await self._once("codehub", lambda: self._github_raw(CODEHUB, source="codes:codehub", as_json=True))
            return parse_codehub(d, arg) if d is not None else None
        if kind == "wuthering.gg":
            t = await f.get_text(WUTHERING_GG, source="codes:wuthering.gg", retries=1,
                                 headers={"Accept": "text/html,application/xhtml+xml"})
            return parse_wuthering_gg(t) if t is not None else None
        log.warning("unknown code source spec %r", spec)
        return None
