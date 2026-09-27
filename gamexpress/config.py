"""Settings (environment) + per-game config (config/games.json).

Secrets (GitHub → Settings → Secrets):   webhook URLs, NITTER_RSS_TOKEN
Variables (GitHub → Settings → Variables): everything else — ping roles, emojis,
feature switches, instance role. Nothing in a variable is sensitive, so they are
visible/editable in one click (the "easy, intuitive" switches).
"""

from __future__ import annotations

import json
import os
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

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

# Shown on every CODES card, in its own row under the codes (separated from the per-code
# Redeem links): a link to the user's own community server. Override with the variable
# COMMUNITY_BUTTONS (JSON list, max 3) — set it to "none" to switch the row off.
DEFAULT_COMMUNITY_BUTTONS = [
    {"label": "Citlali News", "url": "https://discord.gg/HyrVP9wRXu",
     "emoji": "a:starward11:1439878792653832253"},
]

# nitter.cf / xitter.cf lead: they are the public pair this monitor is built against, and the
# chain stops at the first TWO instances that answer with real entries.
#
# SLOTS 1-4 ARE THE HOT PATH. twitter.py probes NITTER_BATCH (= 4) instances IN PARALLEL on
# every run, for every handle, whether or not the ones ahead of them answered -- so a mirror
# that cannot answer costs a request on every single run from slot 4 just as surely as slot 1.
#
# This list was ordered by published uptime from status.d420.de on 2026-09-27, which put
# nitter.meowing.monster (95%) and nitter.netbub.com (93%) into slots 3 and 4. Live run
# 36305123457 measured what GitHub's runners actually get from them:
#   * nitter.meowing.monster -- HTTP 200 but 0 entries (bot check / stale), all 4 handles
#   * nitter.netbub.com      -- HTTP 403, all 4 handles
# 8 wasted requests per run -- the same failure x.n0g.xyz was demoted for, twice over. A
# published uptime figure is not a measurement of what THIS client gets, so the hot path is
# now ordered by what the runners observed, and the two are demoted rather than deleted:
# they answer for other clients, and they may work from a VPS.
#
# NOTHING IN THIS FLEET IS DELETED -- MIRRORS ARE DEMOTED, NOT REMOVED. x.n0g.xyz answered
# HTTP 404 then 429 on every handle in three consecutive live runs (36296323488, 36298632006,
# 36299586254), so it sits dead last rather than being cut. That placement is free:
# twitter.XClient.timeline() breaks out of its batch loop the moment TWO instances have
# answered, so anything behind that point costs zero requests in a healthy run -- and is a
# real backup again the run the fleet ahead of it degrades. Deleting a mirror throws away a
# host that may simply be blocking GitHub's runners while answering fine from a VPS.
DEFAULT_NITTER = [
    # ── hot path: probed on EVERY run (NITTER_BATCH = 4) — measured answerers only ──
    "https://nitter.cf", "https://xitter.cf",   # the pair that answers (12 ok / 0 fail)
    "https://nitter.miningtcup.me",             # token-gated — this is what NITTER_RSS_TOKEN is for
    "https://nitter.jaydenha.uk",
    # ── fallbacks: only reached when the hot path gave fewer than two working feeds ──
    "https://nitter.click", "https://shitter.thepixora.com", "https://nitter.xitter.cc",
    "https://tw.eir-nya.gay",
    "https://nitter.perennialte.ch", "https://nitter.privacydev.net", "https://nitter.net",
    "https://nitter.meowing.monster",   # demoted: 200 but 0 entries to GH runners (36305123457)
    # ── last: known to refuse GitHub's runners; a request only when everything above failed ──
    "https://nitter.netbub.com",        # demoted: HTTP 403 to GH runners (36305123457)
    "https://xcancel.com",              # suspended 2026-09-14
    "https://x.yuuki.sh",               # HTTP 403 to GH runners (2026-09-25)
    "https://x.n0g.xyz",                # dead last, kept as a backup: 404 then 429 in runs
                                        # 36296323488 / 36298632006 / 36299586254
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
    community_buttons: list[dict]
    emoji: dict[str, dict | None]
    show_legend: bool
    repost: str
    log_level: str
    http_timeout: int
    no_ping: bool = False              # NO_PING=1 -> never ping (test runs)
    force_webhook: str = ""            # FORCE_WEBHOOK -> every card goes to ONE channel (test channel)
    test_mode: bool = False            # TEST_MODE=1 -> post current items, mark cards as TEST (never commit)
    enable_games: set[str] = field(default_factory=set)   # ENABLE_GAMES=hna,ananta -> switch on prepared games
    aliases: dict[str, list[str]] = field(default_factory=dict)   # game key -> extra env-name slugs (GI, HSR…)
    codes_mark_expired: bool = True    # edit posted code cards when every source lists the code as expired
    countdown_estimates: bool = True   # COUNTDOWN_ESTIMATES=0 -> never fill times from countdown sites
    program_media: bool = True         # PROGRAM_MEDIA=0 -> never look an announcement up on the news page
    banner_feed: bool = True           # BANNER_FEED=0 -> never fill banner lineups from hub.json

    # -- routing ---------------------------------------------------------------
    def _game_slugs(self, game_key: str) -> list[str]:
        out = [slug(game_key)]
        for a in self.aliases.get(game_key, []):
            if slug(a) not in out:
                out.append(slug(a))
        return out

    def webhook_source(self, feature: str, game_key: str) -> tuple[str, str | None]:
        """(secret name, url). Order: FORCE_WEBHOOK (test channel) > DISCORD_WEBHOOK_<FEATURE>_<GAME>
        (the game key, or its short name: CODES_GENSHIN / CODES_GI, CODES_STARRAIL / CODES_HSR …)
        > DISCORD_WEBHOOK_<FEATURE> > DISCORD_WEBHOOK_URL."""
        if self.force_webhook:
            return "FORCE_WEBHOOK", self.force_webhook
        f = slug(feature)
        names = [f"DISCORD_WEBHOOK_{f}_{g}" for g in self._game_slugs(game_key)]
        names += [f"DISCORD_WEBHOOK_{f}", "DISCORD_WEBHOOK_URL"]
        for name in names:
            v = _env(self.env, name)
            if v:
                return name, v
        return "", None

    def webhook(self, feature: str, game_key: str) -> str | None:
        return self.webhook_source(feature, game_key)[1]

    def expected_webhook_names(self, feature: str, game_key: str) -> str:
        f = slug(feature)
        return f"DISCORD_WEBHOOK_{f}_{slug(game_key)} (or DISCORD_WEBHOOK_{f})"

    def ping(self, feature: str, game_key: str) -> Ping:
        """PING_<FEATURE>_<GAME>  >  PING_<FEATURE>  >  PING_ROLE_ID.  'none' = explicit off.
        NO_PING=1 (test runs) silences everything."""
        if self.no_ping:
            return Ping()
        f = slug(feature)
        names = [f"PING_{f}_{g}" for g in self._game_slugs(game_key)] + [f"PING_{f}", "PING_ROLE_ID"]
        for name in names:
            p = parse_ping(_env(self.env, name))
            if p is not None:
                return p
        return Ping()


def _off_to_empty(value: str) -> str:
    """'none' / 'off' / '-' switch a URL setting off explicitly (an empty value would be
    re-filled from the GE_VARS_JSON catch-all)."""
    return "" if value.strip().lower() in ("none", "off", "-", "no", "false", "0") else value


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


def _buttons_env(env: Mapping[str, str], name: str, limit: int = 3) -> list[dict]:
    """EXTRA_BUTTONS / COMMUNITY_BUTTONS = JSON list of {label,url[,emoji]}; bad JSON -> []."""
    raw = _env(env, name)
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return []
    return [b for b in parsed if isinstance(b, dict) and b.get("url") and b.get("label")][:limit]


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
    extra = _buttons_env(env, "EXTRA_BUTTONS", 3)
    community = _buttons_env(env, "COMMUNITY_BUTTONS") or list(DEFAULT_COMMUNITY_BUTTONS)
    if _env(env, "COMMUNITY_BUTTONS", "").strip().lower() in ("none", "off", "-", "0", "false"):
        community = []
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
        peer_state_url=_off_to_empty(_env(env, "PEER_STATE_URL")),
        failover_after_min=_int(env, "FAILOVER_AFTER_MINUTES", 90),
        heartbeat_min=max(5, _int(env, "HEARTBEAT_MINUTES", 1440)),
        state_path=state_path,
        extra_buttons=extra,
        community_buttons=community,
        emoji=emoji,
        countdown_estimates=_bool(env, "COUNTDOWN_ESTIMATES", True),
        program_media=_bool(env, "PROGRAM_MEDIA", True),
        banner_feed=_bool(env, "BANNER_FEED", True),
        show_legend=_bool(env, "SHOW_LEGEND", True),
        repost=_env(env, "REPOST").replace(" ", "").lower(),
        log_level=_env(env, "LOG_LEVEL", "INFO").upper(),
        http_timeout=_int(env, "HTTP_TIMEOUT", 20),
        no_ping=_bool(env, "NO_PING"),
        force_webhook=_env(env, "FORCE_WEBHOOK"),
        test_mode=_bool(env, "TEST_MODE"),
        enable_games={g.strip().lower() for g in _env(env, "ENABLE_GAMES").split(",") if g.strip()},
        aliases=_game_aliases(),
        codes_mark_expired=_bool(env, "CODES_MARK_EXPIRED", True),
    )


def _game_aliases() -> dict[str, list[str]]:
    """key -> [SHORT] from config/games.json, so DISCORD_WEBHOOK_CODES_HSR works like
    DISCORD_WEBHOOK_CODES_STARRAIL (and PING_CODES_GI like PING_CODES_GENSHIN)."""
    try:
        raw = json.loads((CONFIG_DIR / "games.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    out: dict[str, list[str]] = {}
    for key, g in (raw.get("games") or {}).items():
        if key.startswith("_") or not isinstance(g, dict):
            continue
        names = [g.get("short", "")] + list(g.get("aliases") or [])
        out[key] = [n for n in names if n and slug(n) != slug(key)]
    return out


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
    news_url: str = ""                 # official news page: archives every announcement + its key art
    program_feeds: list[str] = field(default_factory=list)   # RSS/Atom mirrors of that news list
    card: CardStyle = field(default_factory=CardStyle)
    codes: dict = field(default_factory=dict)
    note: str = ""
    four_star_count: int | None = None   # rate-up 4★ per banner phase (GI/HSR/WW 3, ZZZ 2); other counts -> TBA
    auto_enable_on: str = ""             # YYYY-MM-DD: a prepared game switches itself on at launch

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
            news_url=g.get("news_url", ""),
            program_feeds=list(g.get("program_feeds") or []),
            card=card,
            codes=dict(g.get("codes") or {}),
            note=g.get("note", ""),
            four_star_count=(int(g["four_star_count"]) if g.get("four_star_count") else None),
            auto_enable_on=str(g.get("auto_enable_on") or ""),
        )
    return games


def game_is_on(g: Game, settings: Settings, now: float | None = None) -> bool:
    """enabled in games.json, or listed in ENABLE_GAMES, or its auto_enable_on date has arrived."""
    if g.enabled or g.key in settings.enable_games:
        return True
    if g.auto_enable_on:
        import time as _t
        today = _t.strftime("%Y-%m-%d", _t.gmtime(now if now is not None else _t.time()))
        return today >= g.auto_enable_on
    return False


def active_games(games: dict[str, Game], settings: Settings, now: float | None = None) -> list[Game]:
    out = []
    for g in games.values():
        if settings.games_filter and g.key not in settings.games_filter:
            continue
        if not game_is_on(g, settings, now) and g.key not in settings.games_filter:
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
