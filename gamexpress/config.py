"""Settings (environment) + per-game config (config/games.json).

Secrets (GitHub → Settings → Secrets):   webhook URLs, NITTER_RSS_TOKEN, DISCORD_BOT_TOKEN
Variables (GitHub → Settings → Variables): everything else — ping roles, emojis,
feature switches, instance role. Nothing in a variable is sensitive, so they are
visible/editable in one click (the "easy, intuitive" switches).
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = ROOT / "config"
DEFAULT_STATE_PATH = ROOT / "state" / "state.json"

FEATURES = ("schedule", "codes")
DEFAULT_COLOR = 14922399  # the gold accent used by every reference card
MAINTENANCE_NOTE = ("※ In the event that the maintenance is extended, the dev team will issue a "
                    "follow-up notice and adjust the compensation accordingly.")

# Emojis from the reference cards (animated, from the user's server).
DEFAULT_EMOJI = {
    "youtube": "a:kurobbseventcalendar:1508619925940473966",
    "twitch": "a:hsrbbsevanescia:1508647148902813776",
    "source": "",
    "redeem": "🎁",
    "banners": "",
}

# round 13/14 nitter fleet from News-Express (live-probed there, 2026-09-20);
# the chain stops at the first instances that answer with real entries.
DEFAULT_NITTER = [
    "https://nitter.cf", "https://xitter.cf", "https://nitter.jaydenha.uk", "https://x.yuuki.sh",
    "https://x.n0g.xyz", "https://nitter.meowing.monster", "https://nitter.click",
    "https://nitter.xitter.cc", "https://nitter.miningtcup.me", "https://nitter.netbub.com",
    "https://shitter.thepixora.com", "https://nitter.perennialte.ch", "https://nitter.privacydev.net",
    "https://nitter.net", "https://xcancel.com",
]


# --------------------------------------------------------------------------- env helpers
def _env(env: Mapping[str, str], name: str, default: str = "") -> str:
    v = env.get(name)
    return default if v is None else str(v).strip()


def _bool(env, name, default=False) -> bool:
    v = _env(env, name, "")
    if v == "":
        return default
    return v.lower() in ("1", "true", "yes", "on", "y")


def _int(env, name, default: int) -> int:
    try:
        return int(_env(env, name, str(default)) or default)
    except ValueError:
        return default


def slug(key: str) -> str:
    return re.sub(r"[^A-Za-z0-9]", "_", key).upper()


def parse_emoji(value: str | None) -> dict | None:
    """'a:name:123' | 'name:123' | '<a:name:123>' | '<:name:123>' | unicode | '' / 'none'."""
    if value is None:
        return None
    v = value.strip()
    if not v or v.lower() in ("none", "off", "0", "false"):
        return None
    m = re.fullmatch(r"<?(a)?:?([A-Za-z0-9_~]{1,32}):(\d{15,25})>?", v)
    if m:
        e = {"id": m.group(3), "name": m.group(2)}
        if m.group(1):
            e["animated"] = True
        return e
    return {"name": v[:8]}  # unicode emoji


@dataclass
class Ping:
    """Resolved mention for one card. Empty = no ping (the 'optional ping' toggle)."""
    roles: list[str] = field(default_factory=list)
    everyone: bool = False
    here: bool = False

    @property
    def text(self) -> str:
        parts = [f"<@&{r}>" for r in self.roles]
        if self.everyone:
            parts.insert(0, "@everyone")
        if self.here:
            parts.insert(0, "@here")
        return " ".join(parts)

    @property
    def allowed_mentions(self) -> dict:
        # Never lets anything ping except exactly what was configured.
        am: dict[str, Any] = {"parse": []}
        if self.everyone or self.here:
            am["parse"] = ["everyone"]
        if self.roles:
            am["roles"] = self.roles[:100]
        return am

    def __bool__(self) -> bool:
        return bool(self.roles or self.everyone or self.here)


def parse_ping(value: str) -> Ping | None:
    """None = inherit (unset); Ping() = explicit no-ping ('none'/'off')."""
    v = (value or "").strip()
    if v == "":
        return None
    if v.lower() in ("none", "off", "no", "false", "0", "-"):
        return Ping()
    p = Ping()
    for tok in re.split(r"[,\s]+", v):
        t = tok.strip().lstrip("<@&").rstrip(">")
        if not t:
            continue
        if t.lower() in ("everyone", "@everyone"):
            p.everyone = True
        elif t.lower() in ("here", "@here"):
            p.here = True
        elif t.isdigit() and 15 <= len(t) <= 25:
            p.roles.append(t)
    return p


# --------------------------------------------------------------------------- settings
@dataclass
class Settings:
    env: Mapping[str, str]
    features: set[str]
    games_filter: set[str]
    dry_run: bool
    bootstrap_post: bool
    edit_on_update: bool
    post_on_maintenance: bool
    lookback_hours: int
    codes_min_sources: int
    x_enabled: bool
    nitter_instances: list[str]
    nitter_token: str
    instance_name: str
    instance_role: str          # primary | standby
    peer_state_url: str
    failover_after_min: int
    heartbeat_min: int
    state_path: Path
    extra_buttons: list[dict]
    emoji: dict[str, dict | None]
    show_legend: bool
    repost: str
    log_level: str
    http_timeout: int

    # -- routing ---------------------------------------------------------------
    def webhook(self, feature: str, game_key: str) -> str | None:
        """DISCORD_WEBHOOK_<FEATURE>_<GAME>  >  DISCORD_WEBHOOK_<FEATURE>  >  DISCORD_WEBHOOK_URL"""
        f, g = slug(feature), slug(game_key)
        for name in (f"DISCORD_WEBHOOK_{f}_{g}", f"DISCORD_WEBHOOK_{f}", "DISCORD_WEBHOOK_URL"):
            v = _env(self.env, name)
            if v:
                return v
        return None

    def ping(self, feature: str, game_key: str) -> Ping:
        """PING_<FEATURE>_<GAME>  >  PING_<FEATURE>  >  PING_ROLE_ID.  'none' = explicit off."""
        f, g = slug(feature), slug(game_key)
        for name in (f"PING_{f}_{g}", f"PING_{f}", "PING_ROLE_ID"):
            p = parse_ping(_env(self.env, name))
            if p is not None:
                return p
        return Ping()


def _merge_json_blobs(env: dict) -> None:
    """GitHub Actions passes ALL repo secrets/variables as JSON (GE_SECRETS_JSON / GE_VARS_JSON)
    so any per-game override you add (e.g. DISCORD_WEBHOOK_CODES_WUWA) works without
    editing the workflow. Explicit non-empty env values always win."""
    for blob in ("GE_SECRETS_JSON", "GE_VARS_JSON"):
        raw = env.pop(blob, "")
        if not raw:
            continue
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            continue
        for k, v in (data or {}).items():
            if isinstance(k, str) and k.isupper() and not str(env.get(k, "")).strip():
                env[k] = str(v)


def load_settings(env: Mapping[str, str] | None = None) -> Settings:
    env = dict(os.environ if env is None else env)
    _merge_json_blobs(env)
    feats_raw = _env(env, "ENABLED_FEATURES", "schedule,codes").lower()
    only = _env(env, "ONLY", "").lower()
    if feats_raw in ("none", "off", "standby", "0"):
        features: set[str] = set()
    else:
        features = {f.strip() for f in feats_raw.split(",") if f.strip() in FEATURES}
    if only in FEATURES:
        features &= {only}
    games_filter = {g.strip().lower() for g in (_env(env, "GAMES") + "," + _env(env, "GAME")).split(",")
                    if g.strip()}
    nitter = [u.strip().rstrip("/") for u in _env(env, "NITTER_INSTANCES").split(",") if u.strip()]
    extra: list[dict] = []
    raw_extra = _env(env, "EXTRA_BUTTONS")
    if raw_extra:
        try:
            parsed = json.loads(raw_extra)
            extra = [b for b in parsed if isinstance(b, dict) and b.get("url") and b.get("label")][:3]
        except json.JSONDecodeError:
            extra = []
    emoji = {k: parse_emoji(_env(env, f"EMOJI_{k.upper()}", v)) for k, v in DEFAULT_EMOJI.items()}
    state_path = Path(_env(env, "STATE_PATH")) if _env(env, "STATE_PATH") else DEFAULT_STATE_PATH
    return Settings(
        env=env,
        features=features,
        games_filter=games_filter,
        dry_run=_bool(env, "DRY_RUN"),
        bootstrap_post=_bool(env, "BOOTSTRAP_POST"),
        edit_on_update=_bool(env, "EDIT_ON_UPDATE", True),
        post_on_maintenance=_bool(env, "POST_ON_MAINTENANCE_NOTICE", True),
        lookback_hours=_int(env, "LOOKBACK_HOURS", 72),
        codes_min_sources=max(1, _int(env, "CODES_MIN_SOURCES", 2)),
        x_enabled=_bool(env, "X_ENABLED", True),
        nitter_instances=nitter or list(DEFAULT_NITTER),
        nitter_token=_env(env, "NITTER_RSS_TOKEN"),
        instance_name=_env(env, "INSTANCE_NAME", "alpha") or "alpha",
        instance_role=(_env(env, "INSTANCE_ROLE", "primary") or "primary").lower(),
        peer_state_url=_env(env, "PEER_STATE_URL"),
        failover_after_min=_int(env, "FAILOVER_AFTER_MINUTES", 90),
        heartbeat_min=max(5, _int(env, "HEARTBEAT_MINUTES", 1440)),
        state_path=state_path,
        extra_buttons=extra,
        emoji=emoji,
        show_legend=_bool(env, "SHOW_LEGEND", True),
        repost=_env(env, "REPOST"),
        log_level=_env(env, "LOG_LEVEL", "INFO").upper(),
        http_timeout=_int(env, "HTTP_TIMEOUT", 20),
    )


# --------------------------------------------------------------------------- games
@dataclass
class CardStyle:
    title: str = "{game} Version {version} {program}"
    header: str = "{game} Version {version} Schedule! 📜"
    maintenance_heading: str = "Maintenance Details"
    maintenance_style: str = "start_end"      # start_end | range (WW)
    maintenance_first: bool = False           # WW: maintenance block before banners
    four_star_summary: bool = False           # WW: '※ 4 Star Characters:' summary line
    banners_url: str = ""                     # GI: banner heading links to lunaris.moe/banners
    show_banners: bool = True                 # ANANTA is not a character gacha -> False
    note: str = MAINTENANCE_NOTE


@dataclass
class Game:
    key: str
    name: str
    short: str
    enabled: bool
    color: int
    publisher: str = ""
    icon: str = ""
    hoyolab_gid: int | None = None
    c3kay_feed: str = ""
    launcher: dict = field(default_factory=dict)
    x_accounts: list[str] = field(default_factory=list)
    kuro_news: bool = False
    program_label: str = "Special Program"
    program_patterns: list[str] = field(default_factory=lambda: ["special program"])
    banner_patterns: list[str] = field(default_factory=list)
    youtube: str = ""
    twitch: str = ""
    card: CardStyle = field(default_factory=CardStyle)
    codes: dict = field(default_factory=dict)
    note: str = ""

    @property
    def redeem_url(self) -> str:
        return self.codes.get("redeem_url", "")

    @property
    def redeem_page(self) -> str:
        return self.codes.get("redeem_page", "")


def load_games(path: Path | None = None) -> dict[str, Game]:
    path = path or (CONFIG_DIR / "games.json")
    raw = json.loads(path.read_text(encoding="utf-8"))
    defaults = raw.get("defaults", {})
    games: dict[str, Game] = {}
    for key, g in (raw.get("games") or {}).items():
        if key.startswith("_"):
            continue
        card_raw = {**defaults.get("card", {}), **g.get("card", {})}
        card = CardStyle(**{k: v for k, v in card_raw.items() if k in CardStyle.__dataclass_fields__})
        hl = g.get("hoyolab") or {}
        games[key] = Game(
            key=key,
            name=g["name"],
            short=g.get("short", key.upper()),
            enabled=bool(g.get("enabled", True)),
            color=int(g.get("color", defaults.get("color", DEFAULT_COLOR))),
            publisher=g.get("publisher", ""),
            icon=g.get("icon", ""),
            hoyolab_gid=hl.get("gid"),
            c3kay_feed=hl.get("c3kay", ""),
            launcher=g.get("launcher") or {},
            x_accounts=list(g.get("x_accounts") or []),
            kuro_news=bool(g.get("kuro_news", False)),
            program_label=g.get("program_label", "Special Program"),
            program_patterns=list(g.get("program_patterns") or ["special program"]),
            banner_patterns=list(g.get("banner_patterns") or []),
            youtube=g.get("youtube", ""),
            twitch=g.get("twitch", ""),
            card=card,
            codes=dict(g.get("codes") or {}),
            note=g.get("note", ""),
        )
    return games


def active_games(games: dict[str, Game], settings: Settings) -> list[Game]:
    out = []
    for g in games.values():
        if settings.games_filter and g.key not in settings.games_filter:
            continue
        if not g.enabled and g.key not in settings.games_filter:
            continue
        out.append(g)
    return out


def load_overrides(path: Path | None = None) -> dict:
    path = path or (CONFIG_DIR / "overrides.json")
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise SystemExit(f"config/overrides.json is not valid JSON: {e}") from e
    return {k: v for k, v in data.items() if not k.startswith("_")}
