"""Discord Components V2 card builders — buttons are NESTED INSIDE the card container.

Layout (schedule card), converted 1:1 from the reference embed cards:

  [Text Display]  "<@&ROLE> Honkai: Star Rail Version 4.6 Schedule! 📜"   <- old `content`
  [Container accent=14922399]                                               <- old embed
     ## [Honkai: Star Rail Version 4.6 Special Program](url)                <- title + url
     <t:…:F> or <t:…:R>  +  ※ maintenance-extended note
     ───────────
     **Version 4.6 Banners (STC)**  re-runs / phases / 4★ (TBA when unknown)
     ───────────
     **Maintenance Details (STC)**  ✦ Pre-Install / Start / End (+ compensation)
     [Media Gallery]  announcement image                                   <- embed image
     ───────────
     [Action Row]  Youtube · Twitch · Source (+ EXTRA_BUTTONS)             <- buttons INSIDE
     -# STC — Subject to Change • TBA — To be Announced

Hard limits enforced by validate_payload(): 40 components total (nested
included), 4000 characters across all Text Displays, 5 buttons per row,
10 media items per gallery, no `content`/`embeds` with IS_COMPONENTS_V2.
"""

from __future__ import annotations

import logging
import re
from typing import Any
from urllib.parse import quote

from .config import Game, Ping, Settings
from .textutil import strip_invisible, truncate
from .timeparse import discord_ts

log = logging.getLogger("gamexpress.cards")

IS_COMPONENTS_V2 = 1 << 15
MAX_COMPONENTS = 40
MAX_TEXT_TOTAL = 4000
TBA = "TBA"
LEGEND = "STC — Subject to Change • TBA — To be Announced"


# --------------------------------------------------------------------------- primitives
def text(content: str) -> dict:
    # Last chokepoint before Discord. Scraped text is already cleaned at the source, but a
    # field can also arrive through an override or a sample, and an invisible character (bidi
    # override, zero-width space) on a card is never intentional - it only ever makes a card
    # display something other than what it says.
    return {"type": 10, "content": strip_invisible(content)}


def sep(divider: bool = True, spacing: int = 1) -> dict:
    return {"type": 14, "divider": divider, "spacing": spacing}


def gallery(urls: list[str]) -> dict:
    safe = [u for u in (safe_url(x) for x in urls) if u]
    return {"type": 12, "items": [{"media": {"url": u}} for u in safe[:10]]}


def thumbnail(url: str) -> dict:
    return {"type": 11, "media": {"url": safe_url(url) or ""}}


def section(texts: list[str], accessory: dict) -> dict:
    return {"type": 9, "components": [text(t) for t in texts[:3]], "accessory": accessory}


def link_button(label: str, url: str, emoji: dict | None = None) -> dict | None:
    """None when the URL cannot be trusted: the caller drops that one button and the rest of the
    card still posts. Keeping a broken button would fail validate_payload() and lose the whole
    announcement over a single bad field."""
    safe = safe_url(url)
    if not safe:
        log.warning("dropping button %r - unusable url %r", label, (url or "")[:120])
        return None
    b: dict[str, Any] = {"type": 2, "style": 5, "label": truncate(label, 80), "url": safe}
    if emoji:
        b["emoji"] = emoji
    return b


def buttons_of(*candidates: dict | None) -> list[dict]:
    """Keep the buttons that survived link_button()."""
    return [b for b in candidates if b]


def action_row(buttons: list[dict]) -> dict:
    return {"type": 1, "components": [b for b in buttons if b][:5]}


def container(children: list[dict], color: int) -> dict:
    return {"type": 17, "accent_color": int(color) & 0xFFFFFF, "components": children}


def _md_link_text(s: str) -> str:
    return s.replace("[", "(").replace("]", ")")


SAFE_URL_MAX = 1024


def safe_url(url: str | None) -> str | None:
    """A URL that is safe to put on a card, or None if it cannot be trusted.

    Most URLs on a card are scraped from somebody else's server - 16 community nitter mirrors,
    wikis, code APIs - so any of them can turn hostile the day a mirror changes hands. Two
    things go wrong if the string is used as-is:

      * a non-http scheme ("javascript:", "data:") in a link button makes Discord reject the
        whole message, so one poisoned field silently kills a real announcement;
      * a ")" inside a markdown link closes it early: [title](https://ok/x) [FREE CODES](evil)
        renders as an extra clickable link nobody here wrote - a phishing line inside a card
        readers trust because it came from this bot.

    So: http(s) only, no whitespace or control characters, bounded length, and parentheses are
    percent-encoded (servers decode them back; markdown stops seeing them).
    """
    u = (url or "").strip()
    if not u.lower().startswith(("http://", "https://")) or len(u) > SAFE_URL_MAX:
        return None
    if any(ch.isspace() or ord(ch) < 0x20 or ord(ch) == 0x7F for ch in u):
        return None
    return u.replace("(", "%28").replace(")", "%29")


def _is_x_url(url: str) -> bool:
    """An x.com / twitter.com link — the announcement tweet itself, which the card already links
    to in its title, so it never needs its own button."""
    return bool(re.match(r"https?://(?:www\.|mobile\.)?(?:x|twitter|fxtwitter|vxtwitter|fixupx)\.com/",
                         url or "", re.I))


def names(values: list[str] | None) -> str:
    vals = [v for v in (values or []) if v and v.strip()]
    return ", ".join(vals) if vals else TBA


# --------------------------------------------------------------------------- validation
def count_components(components: list[dict]) -> int:
    total = 0
    for c in components or []:
        total += 1
        total += count_components(c.get("components", []))
        if isinstance(c.get("accessory"), dict):
            total += 1
    return total


def text_length(components: list[dict]) -> int:
    total = 0
    for c in components or []:
        if c.get("type") == 10:
            total += len(c.get("content", ""))
        total += text_length(c.get("components", []))
    return total


def validate_payload(payload: dict) -> list[str]:
    """Return a list of problems (empty = safe to send)."""
    problems: list[str] = []
    comps = payload.get("components") or []
    if not payload.get("flags", 0) & IS_COMPONENTS_V2:
        problems.append("missing IS_COMPONENTS_V2 flag")
    if payload.get("content") or payload.get("embeds"):
        problems.append("content/embeds are not allowed with Components V2")
    n = count_components(comps)
    if n > MAX_COMPONENTS:
        problems.append(f"{n} components > {MAX_COMPONENTS}")
    t = text_length(comps)
    if t > MAX_TEXT_TOTAL:
        problems.append(f"{t} text chars > {MAX_TEXT_TOTAL}")

    def walk(cs: list[dict], parent: int | None) -> None:
        for c in cs:
            ty = c.get("type")
            if ty == 2 and parent != 1:
                problems.append("button outside an action row")
            if ty == 1 and len(c.get("components", [])) > 5:
                problems.append("more than 5 buttons in a row")
            if ty == 2 and c.get("style") == 5 and not str(c.get("url", "")).startswith(("http://", "https://")):
                problems.append(f"link button without a valid url: {c.get('label')}")
            if ty == 10 and not c.get("content"):
                problems.append("empty text display")
            if ty == 12 and not 1 <= len(c.get("items", [])) <= 10:
                problems.append("media gallery needs 1-10 items")
            walk(c.get("components", []), ty)
    walk(comps, None)
    return problems


def _payload(top_line: str, card: dict, ping: Ping) -> dict:
    comps = [text(top_line), card] if top_line else [card]
    return {"flags": IS_COMPONENTS_V2, "components": comps, "allowed_mentions": ping.allowed_mentions}


def _top_line(ping: Ping, line: str) -> str:
    return f"{ping.text} {line}".strip() if ping else line


def _std_buttons(game: Game, settings: Settings, extra: list[dict] | None = None) -> list[dict]:
    buttons: list[dict] = []
    if game.youtube:
        buttons += buttons_of(link_button("Youtube", game.youtube, settings.emoji.get("youtube")))
    if game.twitch:
        buttons += buttons_of(link_button("Twitch", game.twitch, settings.emoji.get("twitch")))
    buttons.extend(b for b in (extra or []) if b)
    for b in settings.extra_buttons:
        buttons += buttons_of(link_button(b["label"], b["url"], _emoji_of(b.get("emoji"))))
    return buttons[:5]


ESTIMATE_LABELS = {
    "program_ts": "program time",
    "preinstall_ts": "pre-install",
    "maint_start_ts": "maintenance start",
    "maint_end_ts": "maintenance end",
}


def _emoji_of(value) -> dict | None:
    from .config import parse_emoji
    if isinstance(value, dict):
        return value
    return parse_emoji(value) if value else None


# --------------------------------------------------------------------------- schedule card
def program_title(game: Game, d: dict) -> str:
    program = d.get("program_name") or game.program_label
    return game.card.title.format(game=game.name, version=d.get("version") or TBA, program=program,
                                  version_name=d.get("version_name") or "").strip()


def header_line(game: Game, d: dict) -> str:
    return game.card.header.format(game=game.name, version=d.get("version") or TBA,
                                   program=d.get("program_name") or game.program_label,
                                   version_name=d.get("version_name") or "").strip()


def banners_block(game: Game, d: dict) -> str:
    b = d.get("banners") or {}
    v = d.get("version") or TBA
    heading = f"Version {v} Banners (STC)"
    heading = f"**[{heading}]({game.card.banners_url})**" if game.card.banners_url else f"**{heading}**"
    lines = [heading, "", f"※ Re-runs: {names(b.get('reruns'))}"]
    if game.card.four_star_summary:
        lines.append(f"※ 4 Star Characters: {names(b.get('four_star'))}")
    lines += ["", f"✦ First Half/Phase: {names(b.get('phase1'))}",
              f"- 4 Star Characters: {names(b.get('phase1_4'))}", "",
              f"✦ Second Half/Phase: {names(b.get('phase2'))}",
              f"- 4 Star Characters: {names(b.get('phase2_4'))}"]
    return "\n".join(lines)


def maintenance_block(game: Game, d: dict) -> str:
    lines = [f"**{game.card.maintenance_heading}**", ""]
    pre, start, end = d.get("preinstall_ts"), d.get("maint_start_ts"), d.get("maint_end_ts")
    if game.card.maintenance_style == "range":
        lines.append(f"✦ Pre-Install: {discord_ts(pre, 'F')}")
        if start and end:
            lines.append(f"✦ Maintenance: {discord_ts(start, 'f')} to {discord_ts(end, 't')}")
        elif start:
            lines.append(f"✦ Maintenance: {discord_ts(start, 'f')} to {TBA}")
        else:
            lines.append(f"✦ Maintenance: {TBA}")
    else:
        lines += [f"✦ Pre-Install: {discord_ts(pre, 'F')}",
                  f"✦ Start: {discord_ts(start, 'F')}",
                  f"✦ End: {discord_ts(end, 'F')}"]
    if d.get("compensation"):
        lines.append(f"✦ Compensation: {d['compensation']}")
    return "\n".join(lines)


def schedule_payload(game: Game, d: dict, settings: Settings, ping: Ping,
                     updated_ts: int | None = None) -> dict:
    title = _md_link_text(program_title(game, d))
    url = safe_url(d.get("title_url") or d.get("source_url"))
    head = f"## [{title}]({url})" if url else f"## {title}"
    pts = d.get("program_ts")
    if pts:
        ts_line = f"{discord_ts(pts, 'F')} or {discord_ts(pts, 'R')}"
    elif d.get("maint_start_ts") or d.get("preinstall_ts"):
        ts_line = ""      # the program aired before the update notice — never show a misleading "TBA"
    else:
        ts_line = f"{d.get('program_name') or game.program_label}: {TBA}"
    top = f"{head}\n{ts_line}" if ts_line else head
    maint = maintenance_block(game, d)
    banners = banners_block(game, d)

    children: list[dict] = []
    if game.card.maintenance_first:          # WW order: timestamps → maintenance + note → banners
        children.append(text(top))
        children += [sep(), text(f"{maint}\n\n{game.card.note}" if game.card.note else maint)]
        if game.card.show_banners:
            children += [sep(), text(banners)]
    else:                                     # GI / HSR / ZZZ order
        first = top + (f"\n\n{game.card.note}" if game.card.note else "")
        children.append(text(first))
        if game.card.show_banners:
            children += [sep(), text(banners)]
        children += [sep(), text(maint)]
    images = [u for u in (d.get("images") or ([d["image"]] if d.get("image") else [])) if u][:4]
    if images:
        children.append(gallery(images))
    children.append(sep())

    extra: list[dict] = []
    src = d.get("source_url")
    # No "x" button. The announcement tweet is already the card's title link whenever the version
    # has no single YouTube video (GI/ZZZ), and when it does (HSR/WW) the title points there — so
    # a third button labelled "x" only ever duplicated something already on the card.
    if src and src != url and not _is_x_url(src):
        extra += buttons_of(link_button(d.get("source_label") or "Source", src,
                                        settings.emoji.get("source")))
    elif d.get("youtube_video") and d.get("youtube_video") != url:
        extra += buttons_of(link_button("Watch", d["youtube_video"], settings.emoji.get("youtube")))
    buttons = _std_buttons(game, settings, extra)
    if buttons:
        children.append(action_row(buttons))

    foot: list[str] = []
    if settings.show_legend:
        foot.append(LEGEND)
    if d.get("estimated"):
        what = ", ".join(ESTIMATE_LABELS.get(k, k) for k in d["estimated"])
        est_src = ", ".join((d.get("estimate_sources") or ["countdown sites"])[:2])
        foot.append(f"🕒 {what} estimated from {est_src} — the official notice replaces it automatically")
    if updated_ts:
        foot.append(f"Updated {discord_ts(updated_ts, 'R')}")
    for part in foot:                      # one small-text line each, not one run-on line
        children.append(text("-# " + part))
    return _payload(_top_line(ping, header_line(game, d)), container(children, game.color), ping)


# --------------------------------------------------------------------------- codes card
CODES_PER_CARD = 10


def pretty_rewards(raw: str | list | None) -> str:
    """'Primogem*60;Mora*20,000' -> 'Primogem ×60 • Mora ×20,000'"""
    if not raw:
        return ""
    if isinstance(raw, list):
        return " • ".join(str(x).strip() for x in raw if str(x).strip())
    parts = [p.strip() for p in str(raw).replace("\n", ";").split(";") if p.strip()]
    out = []
    for p in parts:
        if "*" in p:
            name, _, qty = p.rpartition("*")
            out.append(f"{name.strip()} ×{qty.strip()}")
        else:
            out.append(p)
    return " • ".join(out)


def codes_card(game: Game, chunk: list[dict], settings: Settings, ping: Ping, detected_ts: int,
               part: tuple[int, int] = (1, 1)) -> dict:
    """ONE code message. A code dict may carry "expired": True — it is then shown struck
    through, without a Redeem button (used when a posted card is edited after the code dies)."""
    n = len(chunk)
    dead = sum(1 for c in chunk if c.get("expired"))
    plural = "s" if n != 1 else ""
    head = f"## 🎁 {game.name} Redemption Code{plural}"
    if dead and dead == n:
        sub = f"-# {'all ' if n > 1 else ''}{n} code{plural} in this post expired • posted {discord_ts(detected_ts, 'R')}"
    elif dead:
        sub = f"-# {n} codes • {dead} expired • detected {discord_ts(detected_ts, 'R')}"
    else:
        sub = f"-# {n} new code{plural} • detected {discord_ts(detected_ts, 'R')}"
    if part[1] > 1:
        sub += f" • part {part[0]}/{part[1]}"
    children: list[dict] = []
    if game.icon:
        children.append(section([head, sub], thumbnail(game.icon)))
    else:
        children.append(text(f"{head}\n{sub}"))
    children.append(sep())
    lines = []
    for c in chunk:
        rw = pretty_rewards(c.get("rewards"))
        code_md = f"~~`{c['code']}`~~ · expired" if c.get("expired") else f"`{c['code']}`"
        lines.append(f"✦ {code_md}" + (f"\n-# {truncate(rw, 180)}" if rw else ""))
    children.append(text("\n".join(lines) if lines else "No codes."))
    children.append(sep())
    live = [c for c in chunk if not c.get("expired")]
    if game.redeem_url and live:
        btns = buttons_of(*(link_button(c["code"], game.redeem_url.format(code=quote(c["code"])),
                                        settings.emoji.get("redeem")) for c in live))
        for i in range(0, len(btns), 5):
            children.append(action_row(btns[i:i + 5]))
    hint = game.codes.get("redeem_hint")
    if hint and live:
        children.append(text(f"※ {hint}"))
    children.append(sep())
    # Own row, under the codes and separated from the per-code Redeem links: the community
    # invite (+ EXTRA_BUTTONS). No Redeem Page / Youtube / Twitch here — those belong to the
    # livestream (special program / special broadcast) card, not to a codes card.
    buttons = buttons_of(*(link_button(b["label"], b["url"], _emoji_of(b.get("emoji")))
                           for b in (settings.community_buttons + settings.extra_buttons)))[:5]
    if buttons:
        children.append(action_row(buttons))
    srcs = sorted({s for c in chunk for s in c.get("sources", [])})
    foot = "-# Source: " + (", ".join(SOURCE_LABELS.get(s, s) for s in srcs) if srcs else "—")
    foot += " • Codes expire — redeem soon." if live else " • Expired codes are kept for reference."
    children.append(text(foot))
    top = _top_line(ping, f"{game.name} Redemption Codes! 🎁") if part[0] == 1 else ""
    return _payload(top, container(children, game.color), ping if part[0] == 1 else Ping())


def codes_payloads(game: Game, codes: list[dict], settings: Settings, ping: Ping,
                   now_ts: int) -> list[dict]:
    """One card per ≤10 codes. Each code gets a prefilled 'Redeem' button when the game
    has web redemption (GI / HSR / ZZZ); otherwise the in-game hint is shown. Only the
    first card of a batch pings."""
    chunks = [codes[i:i + CODES_PER_CARD] for i in range(0, len(codes), CODES_PER_CARD)] or [[]]
    return [codes_card(game, chunk, settings, ping, now_ts, (idx + 1, len(chunks)))
            for idx, chunk in enumerate(chunks)]


SOURCE_LABELS = {
    "hoyolab": "HoYoLAB (official)",
    "x": "Official X",
    "kuro": "Kuro official news",
    "seria": "hoyo-codes.seria.moe (verified)",
    "humbao": "hoyoverse-codes (verified)",
    "ogc": "Open Gacha Codes",
    "ennead": "api.ennead.cc",
    "fandom": "Fandom wiki",
    "codehub": "PromoGacha",
    "wuthering.gg": "wuthering.gg",
    "manual": "manual",
}

TEST_NOTE = "🧪 TEST CARD — sample / test data, not a real announcement"


def mark_test(payload: dict, note: str = TEST_NOTE) -> dict:
    """Label a card as a test: a line at the top of the card + '🧪 [TEST]' on the header line.
    Used by the monitor's test bench so nobody mistakes a test post for real news or real codes."""
    import copy
    p = copy.deepcopy(payload)
    comps = p.get("components") or []
    for c in comps:
        if c.get("type") == 10 and c.get("content") and not c["content"].startswith("🧪"):
            c["content"] = f"🧪 [TEST] {c['content']}"
            break
    for c in comps:
        if c.get("type") == 17:
            c["components"].insert(0, text(f"-# {note}"))
            break
    return p
