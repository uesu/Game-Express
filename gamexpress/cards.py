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
     -# STC — Subject to Change • TBA — To be Announced • Source …

Hard limits enforced by validate_payload(): 40 components total (nested
included), 4000 characters across all Text Displays, 5 buttons per row,
10 media items per gallery, no `content`/`embeds` with IS_COMPONENTS_V2.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import quote

from .config import Game, Ping, Settings
from .timeparse import discord_ts
from .textutil import truncate

IS_COMPONENTS_V2 = 1 << 15
MAX_COMPONENTS = 40
MAX_TEXT_TOTAL = 4000
TBA = "TBA"
LEGEND = "STC — Subject to Change • TBA — To be Announced"


# --------------------------------------------------------------------------- primitives
def text(content: str) -> dict:
    return {"type": 10, "content": content}


def sep(divider: bool = True, spacing: int = 1) -> dict:
    return {"type": 14, "divider": divider, "spacing": spacing}


def gallery(urls: list[str]) -> dict:
    return {"type": 12, "items": [{"media": {"url": u}} for u in urls[:10]]}


def thumbnail(url: str) -> dict:
    return {"type": 11, "media": {"url": url}}


def section(texts: list[str], accessory: dict) -> dict:
    return {"type": 9, "components": [text(t) for t in texts[:3]], "accessory": accessory}


def link_button(label: str, url: str, emoji: dict | None = None) -> dict:
    b: dict[str, Any] = {"type": 2, "style": 5, "label": truncate(label, 80), "url": url}
    if emoji:
        b["emoji"] = emoji
    return b


def action_row(buttons: list[dict]) -> dict:
    return {"type": 1, "components": buttons[:5]}


def container(children: list[dict], color: int) -> dict:
    return {"type": 17, "accent_color": int(color) & 0xFFFFFF, "components": children}


def _md_link_text(s: str) -> str:
    return s.replace("[", "(").replace("]", ")")


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
            if ty == 2 and parent != 1 and c is not None:
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
        buttons.append(link_button("Youtube", game.youtube, settings.emoji.get("youtube")))
    if game.twitch:
        buttons.append(link_button("Twitch", game.twitch, settings.emoji.get("twitch")))
    buttons.extend(extra or [])
    for b in settings.extra_buttons:
        buttons.append(link_button(b["label"], b["url"], _emoji_of(b.get("emoji"))))
    return buttons[:5]


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
        lines.append("")
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
    url = d.get("title_url") or d.get("source_url")
    head = f"## [{title}]({url})" if url else f"## {title}"
    pts = d.get("program_ts")
    ts_line = f"{discord_ts(pts, 'F')} or {discord_ts(pts, 'R')}" if pts else f"{d.get('program_name') or game.program_label}: {TBA}"
    maint = maintenance_block(game, d)
    banners = banners_block(game, d)

    children: list[dict] = []
    if game.card.maintenance_first:          # WW order: timestamps → maintenance + note → banners
        children.append(text(f"{head}\n{ts_line}"))
        children += [sep(), text(f"{maint}\n\n{game.card.note}" if game.card.note else maint)]
        if game.card.show_banners:
            children += [sep(), text(banners)]
    else:                                     # GI / HSR / ZZZ order
        first = f"{head}\n{ts_line}" + (f"\n\n{game.card.note}" if game.card.note else "")
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
    if src and src != url:
        extra.append(link_button(d.get("source_label") or "Source", src, settings.emoji.get("source")))
    elif d.get("youtube_video") and d.get("youtube_video") != url:
        extra.append(link_button("Watch", d["youtube_video"], settings.emoji.get("youtube")))
    buttons = _std_buttons(game, settings, extra)
    if buttons:
        children.append(action_row(buttons))

    foot: list[str] = []
    if settings.show_legend:
        foot.append(LEGEND)
    if d.get("source_links"):
        foot.append("Source: " + " · ".join(f"[{n}]({u})" for n, u in d["source_links"][:3]))
    if updated_ts:
        foot.append(f"Updated {discord_ts(updated_ts, 'R')}")
    if foot:
        children.append(text("-# " + " • ".join(foot)))
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


def codes_payloads(game: Game, codes: list[dict], settings: Settings, ping: Ping,
                   now_ts: int) -> list[dict]:
    """One card per ≤10 codes. Each code gets a prefilled 'Redeem' button when the game
    has web redemption (GI / HSR / ZZZ); otherwise the in-game hint is shown."""
    payloads: list[dict] = []
    chunks = [codes[i:i + CODES_PER_CARD] for i in range(0, len(codes), CODES_PER_CARD)] or [[]]
    for idx, chunk in enumerate(chunks):
        n = len(chunk)
        head = f"## 🎁 {game.name} Redemption Code{'s' if n != 1 else ''}"
        sub = f"-# {n} new code{'s' if n != 1 else ''} • detected {discord_ts(now_ts, 'R')}"
        if len(chunks) > 1:
            sub += f" • part {idx + 1}/{len(chunks)}"
        children: list[dict] = []
        if game.icon:
            children.append(section([head, sub], thumbnail(game.icon)))
        else:
            children.append(text(f"{head}\n{sub}"))
        children.append(sep())
        lines = []
        for c in chunk:
            rw = pretty_rewards(c.get("rewards"))
            lines.append(f"✦ `{c['code']}`" + (f"\n-# {truncate(rw, 180)}" if rw else ""))
        children.append(text("\n".join(lines) if lines else "No codes."))
        children.append(sep())
        if game.redeem_url:
            btns = [link_button(c["code"], game.redeem_url.format(code=quote(c["code"])),
                                settings.emoji.get("redeem")) for c in chunk]
            for i in range(0, len(btns), 5):
                children.append(action_row(btns[i:i + 5]))
        hint = game.codes.get("redeem_hint")
        if hint:
            children.append(text(f"※ {hint}"))
        children.append(sep())
        extra = []
        if game.redeem_page:
            extra.append(link_button("Redeem Page", game.redeem_page, settings.emoji.get("redeem")))
        buttons = (extra + _std_buttons(game, settings))[:5]
        if buttons:
            children.append(action_row(buttons))
        srcs = sorted({s for c in chunk for s in c.get("sources", [])})
        foot = "-# Source: " + (", ".join(SOURCE_LABELS.get(s, s) for s in srcs) if srcs else "—")
        foot += " • Codes expire — redeem soon."
        children.append(text(foot))
        top = _top_line(ping, f"{game.name} Redemption Codes! 🎁") if idx == 0 else ""
        p = _payload(top, container(children, game.color), ping if idx == 0 else Ping())
        payloads.append(p)
    return payloads


SOURCE_LABELS = {
    "hoyolab": "HoYoLAB (official)",
    "x": "Official X",
    "seria": "hoyo-codes.seria.moe (verified)",
    "ennead": "api.ennead.cc",
    "fandom": "Fandom wiki",
    "codehub": "PromoGacha",
    "manual": "manual",
}


# --------------------------------------------------------------------------- notice card
def notice_payload(title: str, body: str, color: int = 0x5865F2) -> dict:
    """Plain V2 card used by `test-card` / diagnostics."""
    return {"flags": IS_COMPONENTS_V2, "allowed_mentions": {"parse": []},
            "components": [container([text(f"### {title}"), text(body)], color)]}
