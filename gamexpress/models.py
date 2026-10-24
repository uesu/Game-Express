"""Normalized items shared by every source."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Item:
    """One official post (HoYoLAB article, tweet, Kuro news article)."""
    source: str                      # hoyolab | x | kuro
    game: str
    id: str
    url: str
    title: str
    text: str
    published_ts: int
    images: list[str] = field(default_factory=list)
    links: list[str] = field(default_factory=list)
    official: bool = True
    # Only the news feature uses ordered content blocks; existing source consumers stay unchanged.
    article_blocks: list[dict] = field(default_factory=list)
    author: str = ""

    @property
    def full(self) -> str:
        return f"{self.title}\n{self.text}" if self.title and self.title not in self.text else self.text

    @property
    def source_label(self) -> str:
        return {
            "hoyolab": "HoYoLAB",
            "x": "X Post",
            "kuro": "Official News",
            "reddit": "Reddit",
        }.get(self.source, "Source")


@dataclass
class BetaSectionEntry:
    """One rendered skill / ability block inside a beta character kit.

    `category` is the kit heading it belongs to (Core Skills, Basic Attack, ...).
    `tag` is the change marker: **[NEW]** / **[CHANGED]** / **[BUFF]** / **[NERF]** /
    **[ADJUSTMENT]** / **[REWORK]** / **[TEXT FIX]**. `meta` carries the short
    descriptor line (e.g. "Single Target" / "Support"). `lines` are the description
    lines, already normalized for Discord markdown.
    """

    title: str = ""
    category: str = ""
    tag: str = "[NEW]"
    meta: str = ""
    lines: list[str] = field(default_factory=list)


@dataclass
class BetaCharacter:
    """A character (agent / resonator / unit) whose beta kit is being published."""

    id: str = ""
    name: str = ""
    rarity: int = 5
    element: str = ""
    role: str = ""
    subtext: str = ""
    stats_header: str = "Base Stats"
    stats_lines: list[str] = field(default_factory=list)
    sections: list[BetaSectionEntry] = field(default_factory=list)
    total_stat_bonuses: str = ""
    mechanic_defs: list[tuple[str, str]] = field(default_factory=list)
    image_url: str = ""
    is_new: bool = True
    diff_url: str = ""


@dataclass
class BetaEquipment:
    """A weapon / W-Engine / light cone / disc drive / relic / echo set entry."""

    id: str = ""
    name: str = ""
    category_label: str = "Equipment"
    rarity: int | None = None
    sub_type: str = ""
    tag: str = "[NEW]"
    stats_line: str = ""
    effect_title: str = ""
    lines: list[str] = field(default_factory=list)
    image_url: str = ""
    diff_url: str = ""


@dataclass
class BetaPatch:
    """One deliverable beta revision for one game."""

    game_key: str = ""
    beta_version: str = ""
    rev_label: str = ""
    rev_id: str = ""
    characters: list[BetaCharacter] = field(default_factory=list)
    equipment: list[BetaEquipment] = field(default_factory=list)
    source_url: str = ""


@dataclass
class CodeHit:
    """One code as reported by one source."""
    code: str
    source: str                      # hoyolab | seria | humbao | ogc | ennead | fandom | codehub | wuthering.gg | x
    rewards: str | list | None = None
    verified: bool = False           # redeem-validated (seria OK / humbao) or the official module
    url: str = ""
    expired: bool = False            # the source explicitly lists this code as EXPIRED / invalid
    expires_at: int | None = None    # explicit "valid until" time given by the source (unix seconds)
    origin: str = ""                 # aggregators only: the upstream they copied it from (seria / fandom)
