"""Redemption-code sources (all verified live 2026-09-25 unless noted).

  hoyolab  official HoYoLAB game-page module — codes appear ONLY during livestreams
           .../circle/channel/guide/material?game_id=2  -> data.modules[].exchange_group.bonuses[]
  seria    https://hoyo-codes.seria.moe/codes?game=genshin|hkrpg|nap  (redeem-validated OK/NOT_OK)
  ennead   https://api.ennead.cc/mihoyo/{genshin|starrail|zenless}/codes  ({active, inactive})
  fandom   MediaWiki API wikitext (same query seria + PromoGacha use)
  codehub  PromoGacha's GitHub-hosted data/codes.json (daily GHA; includes Wuthering Waves)
  x        official tweets (codes are extracted only with explicit code wording)
"""

from __future__ import annotations

import logging
import re

from ..http import Fetcher
from ..models import CodeHit

log = logging.getLogger("gamexpress.codes")

HOYOLAB_MATERIAL = "https://bbs-api-os.hoyolab.com/community/painter/wapi/circle/channel/guide/material"
SERIA = "https://hoyo-codes.seria.moe/codes"
ENNEAD = "https://api.ennead.cc/mihoyo/{}/codes"
FANDOM = ("https://{wiki}.fandom.com/api.php?action=query&prop=revisions&titles={page}"
          "&rvprop=content&rvslots=main&format=json")
CODEHUB = "https://raw.githubusercontent.com/gripcrip-blip/codehub/main/data/codes.json"

CODE_SHAPE = re.compile(r"^[A-Z0-9]{5,24}$")


def sanitize(code: str) -> str:
    code = (code or "").split("/")[0].split(";")[0]
    code = re.sub(r"\[\d+\]", "", code).replace("NEW!", "").replace("Quick Redeem", "")
    code = re.sub(r"[^A-Za-z0-9]", "", code).upper()
    return code if CODE_SHAPE.match(code) and re.search(r"[A-Z]", code) else ""


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
        if not code or str(c.get("status")).upper() != "OK":
            continue
        hits.append(CodeHit(code, "seria", c.get("rewards") or None, verified=True))
    return hits


def parse_ennead(data: dict) -> list[CodeHit]:
    hits = []
    for c in (data or {}).get("active") or []:
        code = sanitize(c.get("code") or "")
        rewards = [r for r in (c.get("rewards") or []) if r and r.lower() != "free items"]
        if code:
            hits.append(CodeHit(code, "ennead", rewards or None))
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
    pos = 0
    markers = [(m.start(), "expired" not in m.group(0).lower()) for m in
               re.finditer(r"<!--[^>]*?(active|expired)[^>]*?-->", wikitext, re.I)]
    for m in _ROW_TEMPLATE.finditer(wikitext):
        while markers and markers[0][0] < m.start():
            active = markers.pop(0)[1]
        pos = m.end()
        fields = [f.strip() for f in m.group("body").split("|")]
        if not active or any(f.replace(" ", "").lower() == "notacode=yes" for f in fields):
            continue
        positional = [f for f in fields if "=" not in f]
        if not positional:
            continue
        if any(f.upper() == "CN" for f in positional[1:3]):
            continue
        code = sanitize(positional[0])
        if code:
            hits.append(CodeHit(code, "fandom", None))
    # 2) plain wikitable (Wuthering Waves page): first cell of each row before "Expired"
    if not hits:
        table = re.split(r"\n=+\s*(Expired|Inactive|Invalid)\b", wikitext, maxsplit=1, flags=re.I)[0]
        for row in re.split(r"\n\|-", table):
            cells = [c.strip() for c in re.split(r"\|\||\n\|", row) if c.strip()]
            if not cells:
                continue
            first = re.sub(r"<[^>]+>|'''?|\[\[|\]\]", "", cells[0]).strip(" |*")
            code = sanitize(first.split("\n")[0])
            if code and first.upper() == first.split("\n")[0].upper():
                hits.append(CodeHit(code, "fandom", None))
    _ = pos
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


_CODE_CONTEXT = re.compile(r"(?:redemption|redeem|promo|gift|exchange)\s*codes?|\bcodes?\s*[:：]|\bcode\s*>>", re.I)
_TOKEN = re.compile(r"(?<![#@/\w.])([A-Z0-9]{6,24})(?![\w/.])")
_STOP = {
    "YOUTUBE", "TWITCH", "TIKTOK", "HOYOVERSE", "HOYOLAB", "VERSION", "SPECIAL", "PROGRAM",
    "BROADCAST", "PREVIEW", "OFFICIAL", "LIVESTREAM", "REDEEM", "REDEMPTION", "EXPIRE", "EXPIRES",
    "REWARDS", "PRIMOGEMS", "POLYCHROME", "ASTRITE", "GENSHIN", "HONKAI", "ZENLESS", "WUTHERING",
    "WAVES", "ANANTA", "IMPORTANT", "REMINDER", "UPDATE", "ANNIVERSARY", "CONGRATULATIONS",
}


def extract_codes_from_text(text: str) -> list[str]:
    """Codes from an OFFICIAL post. Requires explicit code wording; tokens must follow it
    within 400 chars, be ALL-CAPS/digits (6-24), not hashtags/URLs/stop-words."""
    m = _CODE_CONTEXT.search(text or "")
    if not m:
        return []
    window = text[m.start(): m.start() + 400]
    explicit = bool(re.search(r"redemption\s+codes?|redeem\s+codes?", text, re.I))
    out: list[str] = []
    for tok in _TOKEN.findall(window):
        if tok in _STOP or not re.search(r"[A-Z]", tok) or tok.isdigit():
            continue
        if not explicit and not re.search(r"\d", tok):
            continue
        if tok not in out:
            out.append(tok)
    return out[:10]


# ------------------------------------------------------------------ fetchers
class CodeSources:
    """Per-run cache (codehub JSON is shared by every game)."""

    def __init__(self, fetcher: Fetcher) -> None:
        self.fetcher = fetcher
        self._codehub: dict | None = None
        self._codehub_loaded = False

    async def fetch(self, spec: str) -> list[CodeHit] | None:
        """spec examples: 'hoyolab:2' 'seria:genshin' 'ennead:starrail'
        'fandom:genshin-impact/Promotional_Code' 'codehub:genshin-impact'.
        None = source unreachable this run."""
        kind, _, arg = spec.partition(":")
        f = self.fetcher
        if kind == "hoyolab":
            d = await f.get_json(HOYOLAB_MATERIAL, source="codes:hoyolab", params={"game_id": arg},
                                 headers={"Origin": "https://www.hoyolab.com", "x-rpc-language": "en-us"})
            return parse_hoyolab_material(d) if d is not None else None
        if kind == "seria":
            d = await f.get_json(SERIA, source="codes:seria", params={"game": arg})
            return parse_seria(d) if d is not None else None
        if kind == "ennead":
            d = await f.get_json(ENNEAD.format(arg), source="codes:ennead")
            return parse_ennead(d) if d is not None else None
        if kind == "fandom":
            wiki, _, page = arg.partition("/")
            d = await f.get_json(FANDOM.format(wiki=wiki, page=page or "Redemption_Code"),
                                 source="codes:fandom", headers={"User-Agent": "Game-Express/1.0 (code monitor)"})
            return parse_fandom(d) if d is not None else None
        if kind == "codehub":
            if not self._codehub_loaded:
                self._codehub = await f.get_json(CODEHUB, source="codes:codehub")
                self._codehub_loaded = True
            return parse_codehub(self._codehub, arg) if self._codehub is not None else None
        log.warning("unknown code source spec %r", spec)
        return None
