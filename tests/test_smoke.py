"""Offline smoke + golden tests — no network, no secrets.

Run:   python tests/test_smoke.py        (plain runner, what CI uses)
   or: python -m pytest -q tests          (pytest also works)
Regenerate golden cards after an INTENTIONAL card change:
       UPDATE_GOLDEN=1 python tests/test_smoke.py

The parsers are fed REAL official posts captured on 2026-09-25 and must reproduce
the exact timestamps of the user's four reference cards.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import tempfile
import time
import traceback
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
FIX = ROOT / "tests" / "fixtures"
GOLDEN = FIX / "golden"

from gamexpress import cards, codeposter, media, schedule  # noqa: E402
from gamexpress.config import load_games, load_overrides, load_settings, parse_emoji, parse_ping  # noqa: E402
from gamexpress.discord import SendResult, WebhookClient, _split, webhook_fingerprint  # noqa: E402
from gamexpress.models import CodeHit, Item  # noqa: E402
from gamexpress.runner import Ctx, failover_check  # noqa: E402
from gamexpress.samples import CODE_SAMPLES, SCHEDULE_SAMPLES  # noqa: E402
from gamexpress.sources import codes as csrc  # noqa: E402
from gamexpress.sources import countdown, hoyolab, newspage  # noqa: E402
from gamexpress.sources.hoyolab import _post_text  # noqa: E402
from gamexpress.sources.kuro import parse_launcher_index  # noqa: E402
from gamexpress.sources.launcher import parse_branches  # noqa: E402
from gamexpress.sources.twitter import item_from_fx_json, nitter_pic_to_twimg  # noqa: E402
from gamexpress.state import State  # noqa: E402
from gamexpress.timeparse import find_datetimes, find_duration_hours, find_time_ranges  # noqa: E402

GAMES = load_games()
HOOK = "https://discord.com/api/webhooks/123456789012345678/tok_en-ABC"
BASE_ENV = {"PING_ROLE_ID": "1296268365593186426", "DISCORD_WEBHOOK_URL": HOOK}


def fx(name):
    return json.loads((FIX / name).read_text(encoding="utf-8"))


def settings(**extra):
    env = dict(BASE_ENV)
    env.update({k: str(v) for k, v in extra.items()})
    return load_settings(env)


def hoyolab_item(fixture: str, game: str) -> Item:
    post = fx(fixture)["data"]["post"]
    text, links, imgs = _post_text(post["post"])
    pid = post["post"]["post_id"]
    return Item("hoyolab", game, pid, f"https://www.hoyolab.com/article/{pid}", post["post"]["subject"], text,
                int(post["post"]["created_at"]), imgs, links)


# =========================================================================== time parsing
def test_time_formats_reproduce_reference_cards():
    assert [f.ts for f in find_datetimes("on 09/12/2026 at 08:00 AM (UTC-4)!", 1788753605)] == [1789214400]  # GI 7.1
    assert [f.ts for f in find_datetimes("on September 19, 2026, at 19:00 (UTC+8).", 1789182000)] == [1789815600]  # WW 3.7
    zzz = find_datetimes("will begin on December 19 at 19:30 (UTC+8).", 1765772100)
    assert zzz[0].ts == 1766143800 and zzz[0].year_inferred
    assert find_datetimes("2026/11/09 03:59 (server time)", 1790307006) == []   # server time is never trusted
    assert find_duration_hours("The update will take approximately 5 hours.") == 5.0
    assert find_duration_hours("is estimated to take 5 hours") == 5.0


def test_time_ranges():
    assert find_time_ranges("Maintenance: 2026/09/30 04:00 - 11:00 (UTC+8)", 1790000000) == [(1790712000, 1790737200)]
    assert find_time_ranges("September 30, 2026, 04:00 – 11:00 (UTC+8)", 1790000000) == [(1790712000, 1790737200)]


# =========================================================================== extraction (real posts)
def test_hsr_maintenance_notice_matches_reference_card():
    item = hoyolab_item("hoyolab_starrail_46814308_full.json", "starrail")
    assert "pre-installation will begin" in item.text           # content=='en-us' quirk handled
    e = schedule.extract(GAMES["starrail"], item)
    assert e and e.kind == "maintenance" and e.version == "4.6"
    assert e.fields["preinstall_ts"] == 1790229600
    assert e.fields["maint_start_ts"] == 1790546400
    assert e.fields["maint_end_ts"] == 1790564400
    assert e.fields["compensation"] == "Stellar Jade ×300"


def test_gi_program_article_matches_reference_card():
    item = hoyolab_item("hoyolab_genshin_46604275_full.json", "genshin")
    e = schedule.extract(GAMES["genshin"], item)
    assert e and e.kind == "program" and e.version == "7.1"
    assert e.fields["program_ts"] == 1789214400
    assert e.fields["program_name"] == "Special Program"


def test_gi_update_details_matches_reference_card():
    w = fx("hoyolab_genshin_list_update_details.json")["data"]["list"][0]["post"]
    item = Item("hoyolab", "genshin", w["post_id"], "https://www.hoyolab.com/article/46791577", w["subject"],
                w["content"], w["created_at"])
    e = schedule.extract(GAMES["genshin"], item)
    assert e and e.kind == "maintenance" and e.version == "7.1"
    assert e.fields["maint_start_ts"] == 1790114400 and e.fields["maint_end_ts"] == 1790132400
    assert e.fields["compensation"] == "Primogems ×300"
    assert "preinstall_ts" not in e.fields                   # compensation deadlines are never mistaken


def test_ww_broadcast_tweet():
    item = item_from_fx_json("wuwa", fx("fx_wuwa_3_7_broadcast.json"))
    e = schedule.extract(GAMES["wuwa"], item)
    assert e and e.kind == "program" and e.version == "3.7"
    assert e.fields["program_ts"] == 1789815600
    assert e.fields["program_name"] == "Special Broadcast"
    assert e.fields["youtube_video"] == "https://www.youtube.com/watch?v=nMa_e5ChL6w"
    assert "HR70hTAaoAA8Dzz" in e.fields["images"][0]         # the same image as the reference card


def test_hsr_and_zzz_tweets():
    e = schedule.extract(GAMES["starrail"], item_from_fx_json("starrail", fx("fx_starrail_4_5_program.json")))
    assert e.version == "4.5" and e.fields["program_ts"] == 1786707000
    assert e.fields["version_name"] == "To Roll the Stars in Astropolis"
    z = schedule.extract(GAMES["zzz"], item_from_fx_json("zzz", fx("fx_zzz_2_5_program.json")))
    assert z.version == "2.5" and z.fields["program_ts"] == 1766143800


def test_genshin_tweet_without_number_gets_version_from_launcher():
    e = schedule.extract(GAMES["genshin"], item_from_fx_json("genshin", fx("fx_genshin_luna2_program.json")))
    assert e.kind == "program" and e.version is None and e.fields["program_ts"] == 1760097600
    schedule.infer_versions([e], live="6.0", records={})
    assert e.version == "6.1" and e.version_inferred        # "Luna II" == 6.1


def test_non_announcements_are_ignored():
    codes_post = Item("x", "genshin", "1", "u", "", "The special program has ended! Redemption codes: ABCD1234EF", 1)
    assert schedule.classify(GAMES["genshin"], codes_post) is None or \
        schedule.extract(GAMES["genshin"], codes_post) is None
    merch = Item("x", "genshin", "2", "u", "", "New plushies are available in the official store!", 1)
    assert schedule.extract(GAMES["genshin"], merch) is None


def test_preview_article_event_dates_are_not_program_times():
    text = ("Greetings, Trailblazer! As revealed in the Special Program, here are the Version 4.6 events.\n"
            "Event period: 2026/10/01 10:00 (UTC+8) – 2026/10/20 03:59 (UTC+8).")
    item = Item("hoyolab", "starrail", "1", "u", "\"Dance With the Beast\" Version 4.6 Preview", text, 1790200000)
    assert schedule.extract(GAMES["starrail"], item) is None


def test_banner_extraction_conservative():
    text = ('Event Wish "Ballad" Phase II: the event-exclusive 5-star character "Vodyanitsa (Hydro)" and the '
            '4-star characters "Bennett (Pyro)", "Xingqiu (Hydro)" and "Sucrose (Anemo)" will get a huge drop-rate boost! '
            'The 5-star weapon "Some Sword" is not a character.')
    b = schedule.extract_banner(Item("hoyolab", "genshin", "1", "u", "Event Wish", text, 1))
    assert b["banner_five"] == ["Vodyanitsa"] and b["banner_phase"] == 2
    assert b["banner_four"] == ["Bennett", "Xingqiu", "Sucrose"]


# =========================================================================== cards
def _render(key):
    s = settings()
    return cards.schedule_payload(GAMES[key], SCHEDULE_SAMPLES[key], s, s.ping("schedule", key))


def test_golden_reference_cards():
    GOLDEN.mkdir(parents=True, exist_ok=True)
    for key in SCHEDULE_SAMPLES:
        payload = _render(key)
        path = GOLDEN / f"schedule_{key}.json"
        if os.getenv("UPDATE_GOLDEN") or not path.exists():
            path.write_text(json.dumps(payload, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        assert json.loads(path.read_text(encoding="utf-8")) == payload, f"golden mismatch: {path.name}"


def test_reference_card_text_is_exact():
    p = _render("starrail")
    top, box = p["components"]
    assert top["content"] == "<@&1296268365593186426> Honkai: Star Rail Version 4.6 Schedule! 📜"
    body = "\n".join(c["content"] for c in box["components"] if c["type"] == 10)
    for line in ("## [Honkai: Star Rail Version 4.6 Special Program](https://x.com/honkaistarrail/status/2099440781115211916)",
                 "<t:1789903800:F> or <t:1789903800:R>", "**Version 4.6 Banners (STC)**",
                 "✦ First Half/Phase: Pearl", "- 4 Star Characters: TBA", "**Maintenance Details (STC)**",
                 "✦ Pre-Install: <t:1790229600:F>", "✦ Start: <t:1790546400:F>", "✦ End: <t:1790564400:F>"):
        assert line in body, line
    ww = "\n".join(c["content"] for c in _render("wuwa")["components"][1]["components"] if c["type"] == 10)
    assert 'Wuthering Waves Version 3.7 "Special Broadcast"' in ww
    assert "✦ Maintenance: <t:1790712000:f> to <t:1790737200:t>" in ww
    assert "※ 4 Star Characters: Buling, Taoqi, Youhu, Lumi, Danjin, Yangyang" in ww
    assert ww.index("Maintenance Time & Compensation Details") < ww.index("Banners (STC)")
    gi = "\n".join(c["content"] for c in _render("genshin")["components"][1]["components"] if c["type"] == 10)
    assert "**[Version 7.1 Banners (STC)](https://lunaris.moe/banners)**" in gi
    assert "※ Re-runs: Skirk, Escoffier" in gi


def test_buttons_are_inside_the_card():
    for key in SCHEDULE_SAMPLES:
        p = _render(key)
        assert p["flags"] == cards.IS_COMPONENTS_V2 and "content" not in p and "embeds" not in p
        assert all(c["type"] in (10, 17) for c in p["components"])          # no top-level buttons
        box = p["components"][-1]
        rows = [c for c in box["components"] if c["type"] == 1]
        assert rows, "action row must be nested in the container"
        labels = [b["label"] for b in rows[0]["components"]]
        assert labels[:2] == ["Youtube", "Twitch"]
        assert rows[0]["components"][0]["emoji"]["name"] == "kurobbseventcalendar"
        assert not cards.validate_payload(p)


def test_codes_card():
    s = settings()
    for key, codes in CODE_SAMPLES.items():
        for p in cards.codes_payloads(GAMES[key], codes, s, s.ping("codes", key), 1790000000):
            assert not cards.validate_payload(p), cards.validate_payload(p)
    p = cards.codes_payloads(GAMES["genshin"], CODE_SAMPLES["genshin"], s, s.ping("codes", "genshin"), 1)[0]
    flat = json.dumps(p, ensure_ascii=False)
    assert "https://genshin.hoyoverse.com/en/gift?code=VESNAONPATROL" in flat
    assert "Primogem ×40 • Mora ×20000 • Hero's Wit ×3" in flat
    many = [{"code": f"CODE{i:04d}X", "sources": ["seria"]} for i in range(23)]
    parts = cards.codes_payloads(GAMES["zzz"], many, s, s.ping("codes", "zzz"), 1)
    assert len(parts) == 3 and all(not cards.validate_payload(x) for x in parts)
    assert parts[1]["allowed_mentions"] == {"parse": []}                     # only the first part pings


def test_validate_payload_catches_limits():
    too_many = {"flags": cards.IS_COMPONENTS_V2, "components": [cards.text("x")] * 41}
    assert any("components" in p for p in cards.validate_payload(too_many))
    too_long = {"flags": cards.IS_COMPONENTS_V2, "components": [cards.text("x" * 4001)]}
    assert any("text chars" in p for p in cards.validate_payload(too_long))
    loose = {"flags": cards.IS_COMPONENTS_V2, "components": [cards.link_button("a", "https://x.y")]}
    assert any("outside" in p for p in cards.validate_payload(loose))
    assert cards.validate_payload({"components": [cards.text("x")]})       # missing flag


# =========================================================================== config / routing
def test_ping_resolution():
    s = settings()
    assert s.ping("schedule", "genshin").text == "<@&1296268365593186426>"
    s = settings(PING_ROLE_ID="")
    assert not s.ping("schedule", "genshin") and s.ping("codes", "zzz").allowed_mentions == {"parse": []}
    s = settings(PING_CODES="none", PING_SCHEDULE_WUWA="111111111111111111,222222222222222222")
    assert not s.ping("codes", "genshin")
    assert s.ping("schedule", "wuwa").roles == ["111111111111111111", "222222222222222222"]
    assert s.ping("schedule", "genshin").roles == ["1296268365593186426"]
    assert parse_ping("everyone").allowed_mentions == {"parse": ["everyone"]}
    assert parse_ping("<@&1296268365593186426>").roles == ["1296268365593186426"]


def test_emoji_and_webhook_routing():
    assert parse_emoji("a:kurobbseventcalendar:1508619925940473966") == {
        "id": "1508619925940473966", "name": "kurobbseventcalendar", "animated": True}
    assert parse_emoji("<:x:123456789012345678>") == {"id": "123456789012345678", "name": "x"}
    assert parse_emoji("none") is None and parse_emoji("🎁") == {"name": "🎁"}
    s = settings(DISCORD_WEBHOOK_SCHEDULE="https://discord.com/api/webhooks/1/sched",
                 DISCORD_WEBHOOK_CODES_WUWA="https://discord.com/api/webhooks/2/wwcodes")
    assert s.webhook("schedule", "zzz").endswith("/sched")
    assert s.webhook("codes", "wuwa").endswith("/wwcodes")
    assert s.webhook("codes", "genshin") == HOOK
    base, keep = _split(HOOK + "?thread_id=999&wait=false")
    assert keep == {"thread_id": "999"} and "?" not in base
    assert webhook_fingerprint(HOOK) == webhook_fingerprint(HOOK + "?thread_id=1") and len(webhook_fingerprint(HOOK)) == 12


def test_games_config_is_valid():
    assert set(GAMES) >= {"genshin", "starrail", "zzz", "wuwa", "hna", "ananta"}
    for g in GAMES.values():
        if g.enabled:
            # YouTube is where every one of these games streams its program, so an enabled game
            # must have it. Twitch is NOT universal: HoYoverse has announced no Twitch channel for
            # Nexus Anima and NetEase lists none for ANANTA, and cards.py only adds the button
            # when the field is filled, so an empty twitch is a fact about the game, not a gap.
            assert g.youtube and g.x_accounts and g.codes.get("sources"), g.key
            assert g.youtube.startswith("https://www.youtube.com/@"), g.key
            assert not g.twitch or g.twitch.startswith("https://www.twitch.tv/"), g.key
        cards.program_title(g, {"version": "1.0"})
        cards.header_line(g, {"version": "1.0"})
    # both pre-release games are switched ON (2026-10-02) so nothing is missed before launch
    assert GAMES["hna"].enabled and GAMES["hna"].hoyolab_gid == 9
    assert GAMES["ananta"].enabled and not GAMES["ananta"].card.show_banners
    assert GAMES["ananta"].auto_enable_on == "2027-01-15"        # kept as a safety net
    # ...but neither is RELEASED, which is a separate fact: it is what the test bench uses to
    # decide a game has no real codes to fetch yet (--unlaunched), not whether it is monitored.
    assert not GAMES["hna"].released and not GAMES["ananta"].released
    assert all(GAMES[k].released for k in ("genshin", "starrail", "zzz", "wuwa"))
    assert isinstance(load_overrides(), dict)


# =========================================================================== sources
def test_code_parsers():
    assert [h.code for h in csrc.parse_seria(fx("seria_nap.json"))] == ["ZENLESSGIFT", "ZZZINK32", "ZZZVOID32", "ZZZGRIND32"]
    en = csrc.parse_ennead(fx("ennead_starrail_trimmed.json"))
    active = [h for h in en if not h.expired]
    assert [h.code for h in active] == ["STARRAILGIFT", "4TKSX77Y58QK", "CREATIONNYMPH"] and active[1].rewards is None
    assert [h.code for h in en if h.expired] == ["0206GRANDOPEN"]              # inactive list = expired flag
    assert csrc.parse_hoyolab_material(fx("hoyolab_material_empty.json")) == []
    live = csrc.parse_hoyolab_material(fx("hoyolab_material_live_SYNTHETIC.json"))
    assert [h.code for h in live] == ["VESNAONPATROL"] and live[0].verified
    assert [h.code for h in csrc.parse_fandom(fx("fandom_hsr_SYNTHETIC.json")) if not h.expired] == ["STARRAILGIFT"]
    assert [h.code for h in csrc.parse_fandom(fx("fandom_ww_table_SYNTHETIC.json")) if not h.expired] == [
        "WAKINGMOON", "FINDSENTINEL"]
    assert [h.code for h in csrc.parse_codehub(fx("codehub_trimmed.json"), "wuthering-waves")] == ["WAKINGMOON", "FINDSENTINEL"]
    assert csrc.sanitize("vesnaonpatrol[1] NEW!") == "VESNAONPATROL" and csrc.sanitize("123456") == ""


def test_code_extraction_from_official_posts():
    ww = ("Wuthering Waves Version 3.6 Special Broadcast Redemption Codes:\nHEARTOFSWORD\nETERNALFLAME\n"
          "THEANSWER\nRedeem before the version ends! #WutheringWaves")
    assert csrc.extract_codes_from_text(ww) == ["HEARTOFSWORD", "ETERNALFLAME", "THEANSWER"]
    for name in ("fx_genshin_luna2_program.json", "fx_zzz_2_5_program.json", "fx_wuwa_3_7_broadcast.json"):
        assert csrc.extract_codes_from_text(fx(name)["tweet"]["text"]) == [], name   # "drop some codes" != codes
    assert csrc.extract_codes_from_text("IMPORTANT UPDATE: code: VERSION SPECIAL") == []


def test_launcher_parsers():
    b = parse_branches(fx("hoyoplay_branches_trimmed.json"))
    assert b["U5hbdsT9W7"] == {"live": "3.2", "pre": None}
    assert b["4ziysqXOQ8"] == {"live": "4.5", "pre": "4.6"}
    assert parse_launcher_index(fx("kuro_launcher_index_trimmed.json")) == {"live": "3.6", "pre": "3.7"}
    assert nitter_pic_to_twimg("https://nitter.cf/pic/media%2FHR70hTAaoAA8Dzz.jpg") == \
        "https://pbs.twimg.com/media/HR70hTAaoAA8Dzz.jpg"


# =========================================================================== pipelines (offline)
class FakeCodeSources:
    def __init__(self, table):
        self.table = table

    async def fetch(self, spec):
        return self.table.get(spec, [])


def make_ctx(state_path, items=None, now=1789300000, codes_table=None, versions=None, overrides=None, **env):
    s = settings(**env)
    s.state_path = Path(state_path)
    return Ctx(settings=s, games=[g for g in GAMES.values() if g.enabled], state=State.load(Path(state_path)),
               fetcher=None, webhook=WebhookClient(None, dry_run=True), x=None,
               code_sources=FakeCodeSources(codes_table or {}), overrides=overrides or {}, now=now,
               versions=versions or {}, items=items or {})


def test_schedule_post_once_then_edit_silently():
    with tempfile.TemporaryDirectory() as tmp:
        sp = Path(tmp) / "state.json"
        ctx = make_ctx(sp)                                     # 1) first run = silent seed
        asyncio.run(schedule.run(ctx))
        assert ctx.webhook.sent == [] and ctx.state.is_bootstrapped("schedule", "wuwa")
        ctx.state.save()
        ww = item_from_fx_json("wuwa", fx("fx_wuwa_3_7_broadcast.json"))
        ctx = make_ctx(sp, items={"wuwa": [ww]}, now=1789300000)   # 2) broadcast announced -> ONE post
        asyncio.run(schedule.run(ctx))
        posts = [x for x in ctx.webhook.sent if x["method"] == "POST"]
        assert len(posts) == 1
        top = posts[0]["payload"]["components"][0]["content"]
        assert top == "<@&1296268365593186426> Wuthering Waves Version 3.7 Schedule! 📜"
        assert posts[0]["payload"]["allowed_mentions"] == {"parse": [], "roles": ["1296268365593186426"]}
        ctx.state.save()
        ctx = make_ctx(sp, items={"wuwa": [ww]}, now=1789303600)   # 3) same item again -> nothing
        asyncio.run(schedule.run(ctx))
        assert ctx.webhook.sent == []
        ctx.state.save()
        notice = Item("kuro", "wuwa", "9001", "https://wutheringwaves.kurogames.com/en/main/news/detail/9001",
                      "Version 3.7 Update Maintenance Notice",
                      "Version 3.7 pre-download will begin at 2026/09/28 10:00 (UTC+8).\n"
                      "Maintenance Time: 2026/09/30 04:00 - 11:00 (UTC+8)\nCompensation: Astrite ×300",
                      1790000000)
        ctx = make_ctx(sp, items={"wuwa": [ww, notice]}, now=1790001000)   # 4) notice -> EDIT, no ping
        asyncio.run(schedule.run(ctx))
        methods = [x["method"] for x in ctx.webhook.sent]
        assert methods == ["PATCH"], methods
        edit = ctx.webhook.sent[0]["payload"]
        assert edit["allowed_mentions"] == {"parse": []}
        flat = json.dumps(edit, ensure_ascii=False)
        assert "<t:1790560800:F>" in flat and "<t:1790712000:f> to <t:1790737200:t>" in flat
        assert "Astrite ×300" in flat


def test_overrides_edit_card():
    with tempfile.TemporaryDirectory() as tmp:
        sp = Path(tmp) / "state.json"
        ww = item_from_fx_json("wuwa", fx("fx_wuwa_3_7_broadcast.json"))
        ctx = make_ctx(sp, items={"wuwa": [ww]}, BOOTSTRAP_POST="1")
        asyncio.run(schedule.run(ctx))
        assert [x["method"] for x in ctx.webhook.sent] == ["POST"]
        ctx.state.save()
        ov = {"wuwa": {"3.7": {"banners": {"phase1": ["Hsin"], "phase2": ["Suoming"]}}}}
        ctx = make_ctx(sp, items={"wuwa": [ww]}, overrides=ov, now=1789300600)
        asyncio.run(schedule.run(ctx))
        assert [x["method"] for x in ctx.webhook.sent] == ["PATCH"]
        assert "✦ First Half/Phase: Hsin" in json.dumps(ctx.webhook.sent[0]["payload"], ensure_ascii=False)


def test_stale_announcements_are_not_posted():
    with tempfile.TemporaryDirectory() as tmp:
        sp = Path(tmp) / "state.json"
        ww = item_from_fx_json("wuwa", fx("fx_wuwa_3_7_broadcast.json"))
        ctx = make_ctx(sp, items={"wuwa": [ww]}, now=1789815600 + 3 * 86400, BOOTSTRAP_POST="1")
        asyncio.run(schedule.run(ctx))
        assert ctx.webhook.sent == []                        # program aired 3 days ago -> no late post


def test_codes_gate_pending_and_no_duplicates():
    with tempfile.TemporaryDirectory() as tmp:
        sp = Path(tmp) / "state.json"
        table = {"seria:nap": csrc.parse_seria(fx("seria_nap.json"))}
        ctx = make_ctx(sp, codes_table=table, GAME="zzz")
        ctx.games = [GAMES["zzz"]]
        asyncio.run(codeposter.run(ctx))                     # first run: seed silently
        assert ctx.webhook.sent == [] and len(ctx.state.code_records("zzz")) == 4
        ctx.state.save()
        table["seria:nap"].append(CodeHit("ZZZNEW33", "seria", "Polychrome*30", verified=True))
        table["ennead:zenless"] = [CodeHit("ONLYONESRC", "ennead", None)]
        ctx = make_ctx(sp, codes_table=table)
        ctx.games = [GAMES["zzz"]]
        asyncio.run(codeposter.run(ctx))
        assert len(ctx.webhook.sent) == 1
        flat = json.dumps(ctx.webhook.sent[0]["payload"])
        assert "ZZZNEW33" in flat and "ONLYONESRC" not in flat
        assert ctx.state.code_records("zzz")["ONLYONESRC"]["status"] == "pending"
        ctx.state.save()
        table["fandom:zenless-zone-zero/Redemption_Code"] = [CodeHit("ONLYONESRC", "fandom", None)]
        ctx = make_ctx(sp, codes_table=table)
        ctx.games = [GAMES["zzz"]]
        asyncio.run(codeposter.run(ctx))                     # second independent source -> posted
        assert len(ctx.webhook.sent) == 1 and "ONLYONESRC" in json.dumps(ctx.webhook.sent[0]["payload"])
        assert "ZZZNEW33" not in json.dumps(ctx.webhook.sent[0]["payload"])   # never twice


def test_identical_rerun_changes_nothing():
    """The state file (committed by the workflow) must not change when nothing new happened."""
    with tempfile.TemporaryDirectory() as tmp:
        sp = Path(tmp) / "state.json"
        table = {"seria:nap": csrc.parse_seria(fx("seria_nap.json"))}
        ww = item_from_fx_json("wuwa", fx("fx_wuwa_3_7_broadcast.json"))
        for i, now in enumerate((1789300000, 1789300600, 1789301200)):
            ctx = make_ctx(sp, items={"wuwa": [ww]}, codes_table=table, now=now, BOOTSTRAP_POST="1")
            asyncio.run(schedule.run(ctx))
            asyncio.run(codeposter.run(ctx))
            changed = ctx.state.save()
            if i == 0:
                assert changed
            else:
                assert not changed, f"run {i} rewrote the state file"


def test_official_codes_from_items():
    ww_codes = Item("x", "wuwa", "5", "https://x.com/Wuthering_Waves/status/5", "",
                    "Version 3.7 Special Broadcast Redemption Codes: WAKINGMOON, FINDSENTINEL, FALLINGSANCTUM", 1)
    with tempfile.TemporaryDirectory() as tmp:
        sp = Path(tmp) / "state.json"
        st = State.load(sp)
        st.mark_bootstrapped("codes", "wuwa")
        st.save()
        ctx = make_ctx(sp, items={"wuwa": [ww_codes]})
        ctx.games = [GAMES["wuwa"]]
        asyncio.run(codeposter.run(ctx))
        flat = json.dumps(ctx.webhook.sent[0]["payload"])
        assert all(c in flat for c in ("WAKINGMOON", "FINDSENTINEL", "FALLINGSANCTUM"))
        assert "redeem" not in flat.lower().split("gift?code")[0][:0]      # WW: no web redeem links
        assert "gift?code" not in flat


def test_failover():
    async def run(peer, role="standby", minutes=90, now=1790000000):
        with tempfile.TemporaryDirectory() as tmp:
            class F:
                async def get_json(self, *a, **k):
                    return peer
            ctx = make_ctx(Path(tmp) / "s.json", now=now, INSTANCE_ROLE=role, PEER_STATE_URL="https://raw/x.json",
                           FAILOVER_AFTER_MINUTES=minutes)
            ctx.fetcher = F()
            await failover_check(ctx)
            return ctx
    fresh = {"heartbeat": {"last_success": 1790000000 - 600}, "schedule": {"wuwa": {"3.7": {"status": "posted", "message_id": "9"}}}}
    ctx = asyncio.run(run(fresh))
    assert ctx.active is False and ctx.state.schedule_record("wuwa", "3.7")["message_id"] == "9"
    stale = {"heartbeat": {"last_success": 1790000000 - 3 * 3600}}
    assert asyncio.run(run(stale)).active is True
    assert asyncio.run(run(None)).active is False          # unreachable peer never triggers posting
    daily = {"heartbeat": {"last_success": 1790000000 - 5 * 3600, "every_min": 1440}}
    assert asyncio.run(run(daily)).active is False         # 5 h old but primary beats daily -> no false fail-over
    assert asyncio.run(run(fresh, role="primary")).active is True


def test_secrets_and_vars_json_blobs():
    s = load_settings({"GE_SECRETS_JSON": json.dumps({"DISCORD_WEBHOOK_CODES_WUWA": "https://discord.com/api/webhooks/7/w",
                                                      "github_token": "x"}),
                       "GE_VARS_JSON": json.dumps({"PING_ROLE_ID": "1296268365593186426", "DRY_RUN": "1"}),
                       "DRY_RUN": ""})
    assert s.webhook("codes", "wuwa").endswith("/7/w") and s.ping("schedule", "zzz").roles == ["1296268365593186426"]
    assert s.dry_run is True                                # empty explicit env -> the variable applies
    s2 = load_settings({"GE_VARS_JSON": json.dumps({"DRY_RUN": "1"}), "DRY_RUN": "0"})
    assert s2.dry_run is False                              # explicit input wins


def test_state_saves_only_on_change():
    with tempfile.TemporaryDirectory() as tmp:
        sp = Path(tmp) / "state.json"
        st = State.load(sp)
        assert st.save() is False and not sp.exists()
        st.code_records("genshin")["X"] = {"status": "seeded"}
        assert st.save() is True and sp.exists()
        st2 = State.load(sp)
        assert st2.save() is False
        st2.heartbeat("alpha", "1.0.0", 60, 1000)
        assert st2.save() is True
        st2.heartbeat("alpha", "1.0.0", 60, 1500)          # < 60 min later -> no new commit
        assert st2.save() is False


def test_hoyolab_quirk_and_html():
    post = fx("hoyolab_starrail_46814308_full.json")["data"]["post"]["post"]
    text, links, imgs = _post_text(post)
    assert text.startswith("Hello, Trailblazers!") and imgs and links
    gi = fx("hoyolab_genshin_46604275_full.json")["data"]["post"]["post"]
    t2, l2, i2 = _post_text(gi)
    assert "Version 7.1" in t2 and "https://www.youtube.com/@GenshinImpact" in l2 and i2


# =========================================================================== session 2 (v1.1)
def test_per_game_codes_webhooks_and_aliases():
    hooks = {k: f"https://discord.com/api/webhooks/{i}/codes-{k}" for i, k in
             enumerate(("genshin", "starrail", "hna", "zzz", "wuwa", "ananta"), start=10)}
    env = {f"DISCORD_WEBHOOK_CODES_{k.upper()}": v for k, v in hooks.items()}
    s = settings(**env)
    for key, url in hooks.items():
        assert s.webhook_source("codes", key) == (f"DISCORD_WEBHOOK_CODES_{key.upper()}", url), key
    assert s.webhook("schedule", "genshin") == HOOK                           # schedule falls back to URL
    s = settings(DISCORD_WEBHOOK_CODES_HSR="https://discord.com/api/webhooks/7/hsr",
                 DISCORD_WEBHOOK_CODES_NEXUSANIMA="https://discord.com/api/webhooks/8/hna",
                 DISCORD_WEBHOOK_CODES="https://discord.com/api/webhooks/9/all")
    assert s.webhook_source("codes", "starrail")[0] == "DISCORD_WEBHOOK_CODES_HSR"      # short name works
    assert s.webhook_source("codes", "hna")[0] == "DISCORD_WEBHOOK_CODES_NEXUSANIMA"    # alias works
    assert s.webhook_source("codes", "zzz")[0] == "DISCORD_WEBHOOK_CODES"               # feature fallback
    s = settings(FORCE_WEBHOOK="https://discord.com/api/webhooks/1/test", **env)
    assert s.webhook_source("codes", "wuwa") == ("FORCE_WEBHOOK", "https://discord.com/api/webhooks/1/test")
    assert "DISCORD_WEBHOOK_CODES_WUWA" in settings().expected_webhook_names("codes", "wuwa")


def test_no_ping_and_test_marker():
    s = settings(NO_PING="1", PING_CODES_GENSHIN="111111111111111111")
    assert not s.ping("codes", "genshin") and not s.ping("schedule", "wuwa")
    s = settings()
    p = cards.codes_payloads(GAMES["genshin"], CODE_SAMPLES["genshin"], s, s.ping("codes", "genshin"), 1)[0]
    t = cards.mark_test(p)
    assert t["components"][0]["content"].startswith("🧪 [TEST] <@&1296268365593186426>")
    assert "TEST CARD" in t["components"][1]["components"][0]["content"] and not cards.validate_payload(t)
    assert not p["components"][0]["content"].startswith("🧪")                    # original untouched
    for key in CODE_SAMPLES:                                                    # one sample per game (6)
        assert key in GAMES
    assert set(CODE_SAMPLES) == {"genshin", "starrail", "zzz", "wuwa", "hna", "ananta"}


def test_prepared_games_switch_on():
    """All six games ship ON now, but the prepared-game machinery must keep working: it is what
    an operator uses to run a subset, and what ANANTA's auto_enable_on date falls back to."""
    from gamexpress.config import active_games
    keys = lambda g, s, now=None: [x.key for x in active_games(g, s, now)]  # noqa: E731
    assert keys(GAMES, settings(), now=1790000000) == ["genshin", "starrail", "zzz", "wuwa", "hna", "ananta"]
    # a copy with both pre-release games switched back off -> the three switch-on paths still work
    off = dict(GAMES)
    off["hna"] = replace(GAMES["hna"], enabled=False)
    off["ananta"] = replace(GAMES["ananta"], enabled=False)
    assert keys(off, settings(), now=1790000000) == ["genshin", "starrail", "zzz", "wuwa"]
    assert "hna" in keys(off, settings(ENABLE_GAMES="hna"), now=1790000000)     # 1. ENABLE_GAMES
    jan15 = 1800000000                                                          # 2027-01-15 08:00 UTC
    assert "ananta" in keys(off, settings(), now=jan15) \
        and "ananta" not in keys(off, settings(), now=jan15 - 86400)            # 2. auto_enable_on
    assert keys(off, settings(GAMES="ananta"), now=1790000000) == ["ananta"]    # 3. explicit GAMES=


def test_four_star_names_rules():
    ok = ("Bennett", "March 7th", "Soldier 11", "Topaz & Numby", "Dan Heng • Imbibitor Lunae", "Yumemizuki Mizuki")
    bad = ("Event Wish", "2026", "Character Event", "Light Cone", "https://x.y", "TBA", "Limited 4-Star")
    assert all(schedule.plausible_name(n) for n in ok), [n for n in ok if not schedule.plausible_name(n)]
    assert not any(schedule.plausible_name(n) for n in bad), [n for n in bad if schedule.plausible_name(n)]
    txt = ('Warp "Butterfly" Phase I: the limited 5-star character "Pearl" and the 4-star characters '
           '"Event Wish", "Gallagher" and "Pela" will get a boost.')
    b = schedule.extract_banner(Item("hoyolab", "starrail", "1", "u", "Event Warp", txt, 1))
    assert b["banner_five"] == ["Pearl"] and b["banner_four_unsure"] is True


def _banner_extract(names4, five="Pearl", ts=1, source="hoyolab", unsure=False, phase=1):
    f = {"banner_five": [five], "banner_four": list(names4), "banner_four_unsure": unsure, "banner_phase": phase}
    return schedule.Extract(item=Item(source, "starrail", str(ts), f"u{ts}", "Warp", "x", ts), kind="banner",
                            version="4.7", fields=f)


def test_four_star_tba_when_the_list_is_incomplete():
    g = GAMES["starrail"]                                                       # 3 rate-up 4★ per phase
    rec, notes = {}, []
    d = schedule.merge(g, "4.7", [_banner_extract(["Gallagher", "Pela"])], rec, {}, {}, 1, notes)
    assert d["banners"]["phase1"] == ["Pearl"] and d["banners"]["phase1_4"] == []          # 2 of 3 -> TBA
    assert notes and "2 name(s) found, 3 expected" in notes[0]
    rec, notes = {}, []
    d = schedule.merge(g, "4.7", [_banner_extract(["Gallagher", "Pela", "Lynx"])], rec, {}, {}, 1, notes)
    assert d["banners"]["phase1_4"] == ["Gallagher", "Pela", "Lynx"] and not notes
    rec["data"] = d                                                             # a 2nd official post disagrees
    d = schedule.merge(g, "4.7", [_banner_extract(["Gallagher", "Pela", "Lynx"]),
                                  _banner_extract(["Gallagher", "Pela", "Asta"], ts=2)], rec, {}, {}, 3, notes)
    assert d["banners"]["phase1_4"] == [] and "disagree" in notes[-1]
    rec["data"], n = d, len(notes)                                              # sticky: stays TBA, no new note
    d = schedule.merge(g, "4.7", [_banner_extract(["Gallagher", "Pela", "Lynx"])], rec, {}, {}, 4, notes)
    assert d["banners"]["phase1_4"] == [] and len(notes) == n
    ov = {"banners": {"phase1_4": ["Gallagher", "Pela", "Lynx"]}}                # override is always trusted
    rec["data"] = d
    d = schedule.merge(g, "4.7", [_banner_extract(["Gallagher", "Pela", "Asta"], ts=2)], rec, ov, {}, 5, notes)
    assert d["banners"]["phase1_4"] == ["Gallagher", "Pela", "Lynx"]
    d = schedule.merge(g, "4.7", [_banner_extract([], unsure=True)], {}, {}, {}, 6, [])
    assert d["banners"]["phase1_4"] == []
    notes = []
    d = schedule.merge(g, "4.7", [_banner_extract(["Gallagher", "Pela", "Lynx"], unsure=True)],
                       {}, {}, {}, 7, notes)
    assert d["banners"]["phase1_4"] == ["Gallagher", "Pela", "Lynx"]
    card = json.dumps(cards.schedule_payload(g, {**d, "version": "4.7"}, settings(), settings().ping("schedule", "starrail")),
                      ensure_ascii=False)
    assert "4 Star Characters: TBA" in card


def test_new_code_sources_parsers():
    ogc = csrc.parse_ogc(fx("ogc_genshin_trimmed.json"))
    codes = [h.code for h in ogc]
    assert "TEST" not in codes and "UIVIBUQM6Q8AUIVI13C8X156" not in codes and "XVIZDH2B9WGXEHVE2TEAFY6O" not in codes
    assert {"EPIC2026", "VESNAONPATROL", "UIVIBUQM6Q8A", "XVIZDH2B9WGX"} <= set(codes)   # mixed case normalised
    assert all(h.source == "ogc" and not h.verified for h in ogc)
    ww = csrc.parse_ogc(fx("ogc_wuwa.json"))
    assert [h.code for h in ww][:2] == ["BAHAMUTKXMHM", "DCARD3VN7M"] and ww[0].rewards[0] == "Medium Energy Core ×5"
    hb = csrc.parse_humbao((FIX / "humbao_genshin.txt").read_text(encoding="utf-8"))
    assert [h.code for h in hb] == ["2BJ64QRZ7RT8", "GS71XDYGEO"] and all(h.verified for h in hb)
    wg = csrc.parse_wuthering_gg((FIX / "wuthering_gg_SYNTHETIC.html").read_text(encoding="utf-8"))
    assert [(h.code, h.expired) for h in wg] == [("WUTHERINGGIFT", False), ("NEWBROADCAST37", False),
                                                  ("WUWA4PC", True), ("BAHAMUTKXMHM", True)]
    assert wg[1].rewards == ["100 × Astrite"]
    seria = csrc.parse_seria({"codes": [{"code": "DEADCODE1", "status": "NOT_OK"}, {"code": "GOODCODE1", "status": "OK"}]})
    assert [(h.code, h.expired, h.verified) for h in seria] == [("DEADCODE1", True, False), ("GOODCODE1", False, True)]
    en = csrc.parse_ennead(fx("ennead_genshin_trimmed.json"))
    assert {h.code for h in en if h.expired} == {"GENSHINGIFT", "6ALMWAVKLK35"}
    assert csrc.family("ogc") == csrc.family("ennead") != csrc.family("fandom")


def test_code_gate_families_and_expired_veto():
    H = CodeHit
    g = lambda *hits: codeposter.gate(codeposter.group_hits(list(hits))["NEWCODE1"], 2)  # noqa: E731
    assert g(H("NEWCODE1", "ogc"), H("NEWCODE1", "ennead"))[0] is False        # same family = 1 source
    assert g(H("NEWCODE1", "ogc"), H("NEWCODE1", "fandom"))[0] is True
    ok, why = g(H("NEWCODE1", "ogc"), H("NEWCODE1", "fandom"), H("NEWCODE1", "wuthering.gg", expired=True))
    assert ok is False and "expired" in why                                     # any expired flag -> hold
    assert g(H("NEWCODE1", "seria", verified=True), H("NEWCODE1", "ennead", expired=True))[0] is True
    assert g(H("NEWCODE1", "humbao", verified=True), H("NEWCODE1", "seria", expired=True))[0] is False
    assert g(H("NEWCODE1", "x", verified=True), H("NEWCODE1", "seria", expired=True))[0] is True   # official wins
    assert g(H("NEWCODE1", "kuro", verified=True))[1] == "official"


def test_posted_code_card_is_edited_when_code_expires():
    with tempfile.TemporaryDirectory() as tmp:
        sp = Path(tmp) / "state.json"
        st = State.load(sp)
        st.mark_bootstrapped("codes", "wuwa")
        st.save()
        table = {"ogc:wuwa": [CodeHit("WAKINGMOON", "ogc", ["Astrite ×100"])],
                 "fandom:wutheringwaves/Redemption_Code": [CodeHit("WAKINGMOON", "fandom", None),
                                                            CodeHit("FINDSENTINEL", "fandom", None)],
                 "codehub:wuthering-waves": [CodeHit("FINDSENTINEL", "codehub", None)]}
        ctx = make_ctx(sp, codes_table=table)
        ctx.games = [GAMES["wuwa"]]
        asyncio.run(codeposter.run(ctx))
        assert [x["method"] for x in ctx.webhook.sent] == ["POST"]
        rec = ctx.state.code_records("wuwa")["WAKINGMOON"]
        assert rec["msg_codes"] == ["FINDSENTINEL", "WAKINGMOON"] and rec["status"] == "posted"
        ctx.state.save()
        table = {"wuthering.gg": [CodeHit("WAKINGMOON", "wuthering.gg", None, expired=True)],
                 "fandom:wutheringwaves/Redemption_Code": [CodeHit("WAKINGMOON", "fandom", None, expired=True),
                                                            CodeHit("FINDSENTINEL", "fandom", None)]}
        ctx = make_ctx(sp, codes_table=table, now=1789400000)
        ctx.games = [GAMES["wuwa"]]
        asyncio.run(codeposter.run(ctx))
        assert [x["method"] for x in ctx.webhook.sent] == ["PATCH"]
        edit = ctx.webhook.sent[0]["payload"]
        flat = json.dumps(edit, ensure_ascii=False)
        assert "~~`WAKINGMOON`~~ · expired" in flat and "`FINDSENTINEL`" in flat and "1 expired" in flat
        assert edit["allowed_mentions"] == {"parse": []}
        ctx.state.save()
        ctx = make_ctx(sp, codes_table=table, now=1789400600)                  # no repeated edits
        ctx.games = [GAMES["wuwa"]]
        asyncio.run(codeposter.run(ctx))
        assert ctx.webhook.sent == []


def test_missing_codes_webhook_names_the_secret():
    with tempfile.TemporaryDirectory() as tmp:
        sp = Path(tmp) / "state.json"
        st = State.load(sp)
        st.mark_bootstrapped("codes", "zzz")
        st.save()
        ctx = make_ctx(sp, codes_table={"seria:nap": [CodeHit("ZZZNEW99", "seria", None, verified=True)]},
                       DISCORD_WEBHOOK_URL="")
        ctx.games = [GAMES["zzz"]]
        asyncio.run(codeposter.run(ctx))
        assert any("DISCORD_WEBHOOK_CODES_ZZZ" in r for r in ctx.report)
        assert ctx.state.code_records("zzz")["ZZZNEW99"]["status"] == "pending"   # retried once a webhook exists


def test_webhook_spacing_is_never_charged_after_the_last_post():
    """n posts must cost n-1 gaps, not n: the old code slept 1.2s even after the final send."""
    from gamexpress.discord import WEBHOOK_SPACING

    class Resp:
        status = 200
        headers: dict = {}

        async def text(self):
            return '{"id": "1234567890"}'

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

    class Session:
        def __init__(self):
            self.n = 0

        def request(self, method, url, **kw):
            self.n += 1
            return Resp()

    st = settings()
    payload = cards.schedule_payload(GAMES["genshin"], SCHEDULE_SAMPLES["genshin"], st,
                                     st.ping("schedule", "genshin"), 1789815600)

    async def post(times: int) -> float:
        session = Session()
        wh = WebhookClient(session)
        t0 = time.monotonic()
        for _ in range(times):
            assert (await wh.send(HOOK, payload)).ok
        assert session.n == times
        return time.monotonic() - t0

    one = asyncio.run(post(1))
    assert one < WEBHOOK_SPACING / 2, one                      # single post: no trailing wait at all
    two = asyncio.run(post(2))
    assert WEBHOOK_SPACING <= two < 2 * WEBHOOK_SPACING, two   # exactly one gap, and still spaced


def test_test_mode_posts_latest_card_marked_test():
    with tempfile.TemporaryDirectory() as tmp:
        ww = item_from_fx_json("wuwa", fx("fx_wuwa_3_7_broadcast.json"))
        ctx = make_ctx(Path(tmp) / "s.json", items={"wuwa": [ww]}, now=1789815600 + 5 * 86400, TEST_MODE="1")
        asyncio.run(schedule.run(ctx))                                          # 5 days old, fresh state
        posts = [x for x in ctx.webhook.sent if x["method"] == "POST"]
        assert len(posts) == 1 and posts[0]["payload"]["components"][0]["content"].startswith("🧪 [TEST]")


def test_parallel_probe_counts_per_game():
    from gamexpress.http import Probe

    class Slow:
        health = {}

        async def get_json(self, url, **k):
            await asyncio.sleep(0.01)
            return {"ok": 1} if "good" in url else None

        async def get_text(self, url, **k):
            return None

    async def main():
        a, b = Probe(Slow()), Probe(Slow())
        await asyncio.gather(a.get_json("https://good/1"), b.get_json("https://bad/1"), a.get_json("https://good/2"))
        return a.ok, b.ok, a.health is b.health
    assert asyncio.run(main()) == (2, 0, True)


RSS = """<?xml version="1.0"?><rss version="2.0" xmlns:dc="http://purl.org/dc/elements/1.1/"><channel><title>x</title>
<item><title>t</title><dc:creator>@Wuthering_Waves</dc:creator><link>https://n/Wuthering_Waves/status/{id}#m</link>
<description>Version 3.7 Special Broadcast</description><pubDate>Fri, 18 Sep 2026 10:00:00 GMT</pubDate></item>
</channel></rss>"""


def test_nitter_fleet_probed_in_parallel_batches():
    from gamexpress.sources.twitter import XClient
    calls = []

    class F:
        async def get_text(self, url, **k):
            calls.append(url)
            await asyncio.sleep(0.01)
            if "inst3" in url:
                return RSS.format(id="1111111111")
            if "inst6" in url:
                return RSS.format(id="2222222222")
            return None
    s = settings(NITTER_INSTANCES=",".join(f"https://inst{i}" for i in range(1, 11)))
    x = XClient(F(), s)
    tl = asyncio.run(x.timeline("Wuthering_Waves"))
    assert [e["id"] for e in tl] and {e["id"] for e in tl} == {"1111111111", "2222222222"}
    assert len(calls) == 8 and "wuthering_waves" in x.reachable                 # 2 batches of 4, then stop


def _nitter_fleet_fetcher(ids: dict, hang: str, hung: asyncio.Event, calls: list):
    """Fake Fetcher: every mirror answers with its own tweet id, except `hang`, which never does."""
    class F:
        async def get_text(self, url, **k):
            calls.append(url)
            host = url.split("/")[2]
            if host == hang:
                hung.set()
                await asyncio.sleep(60)          # stands in for the 12 s the live mirror burned
                return None
            return RSS.format(id=ids[host])
    return F()


def test_a_hung_mirror_no_longer_holds_the_batch_once_two_answered():
    """Live run #217 took 16.2 s where #215/#216/#218 took 4.9-6 s, for one reason: nitter.cf
    timed out and asyncio.gather() waited out its whole 12 s NITTER_TIMEOUT even though two
    higher-ranked mirrors in the same batch had already returned the timeline. The batch now
    stops as soon as the winners are decided and cancels the rest, which also frees the
    Fetcher's global request slot for the HoYoLAB / Kuro / code requests queued behind it."""
    from gamexpress.sources.twitter import XClient
    calls, hung = [], asyncio.Event()
    ids = {"m1": "1111111111", "m2": "2222222222", "m3": "3333333333"}
    fleet = ["https://m1", "https://m2", "https://m3", "https://dead"]
    x = XClient(_nitter_fleet_fetcher(ids, "dead", hung, calls), settings(NITTER_INSTANCES=",".join(fleet)))

    async def run():
        started = time.monotonic()
        tl = await asyncio.wait_for(x.timeline("Wuthering_Waves"), timeout=20)
        return tl, time.monotonic() - started
    tl, elapsed = asyncio.run(run())
    assert {e["id"] for e in tl} == {"1111111111", "2222222222"}     # the top two, as before
    assert len(calls) == 4 and hung.is_set()                        # all four were still asked
    assert elapsed < 1, elapsed      # but nothing waited for the hang (old code: the full 60 s)


def test_a_hung_top_ranked_mirror_only_costs_the_grace_window():
    """A mirror ranked ABOVE the answers would have won the merge, so it still gets a grace
    window — but NITTER_GRACE seconds, not the full 12 s timeout. Ranking beats speed: the two
    highest-ranked answers are merged, never just the two fastest."""
    from gamexpress.sources import twitter as tw
    calls, hung = [], asyncio.Event()
    ids = {"m2": "2222222222", "m3": "3333333333", "m4": "4444444444"}
    fleet = ["https://dead", "https://m2", "https://m3", "https://m4"]
    x = tw.XClient(_nitter_fleet_fetcher(ids, "dead", hung, calls), settings(NITTER_INSTANCES=",".join(fleet)))
    grace, tw.NITTER_GRACE = tw.NITTER_GRACE, 0.3
    try:
        async def run():
            started = time.monotonic()
            tl = await asyncio.wait_for(x.timeline("Wuthering_Waves"), timeout=20)
            return tl, time.monotonic() - started
        tl, elapsed = asyncio.run(run())
    finally:
        tw.NITTER_GRACE = grace
    assert {e["id"] for e in tl} == {"2222222222", "3333333333"}     # m2 + m3, never m4
    assert 0.3 <= elapsed < 5, elapsed                               # the grace window, not 60 s


def test_workflows_cron_job_org_and_test_bench():
    try:
        import yaml
    except ImportError:
        print("    (pyyaml not installed — workflow checks skipped)")
        return
    wf = ROOT / ".github" / "workflows"
    mon = yaml.safe_load((wf / "monitor.yml").read_text(encoding="utf-8"))
    on = mon.get("on") or mon.get(True)
    assert "schedule" not in on and "workflow_dispatch" in on                  # cron-job.org is the only trigger
    env = mon["jobs"]["monitor"]["env"]
    for key in ("GENSHIN", "STARRAIL", "HNA", "ZZZ", "WUWA", "ANANTA"):
        assert env[f"DISCORD_WEBHOOK_CODES_{key}"] == f"${{{{ secrets.DISCORD_WEBHOOK_CODES_{key} }}}}"
    assert mon["concurrency"]["cancel-in-progress"] is False
    # v1.6.0: two modes and nothing else — a live run, or a test that uses REAL live data.
    assert not (wf / "test.yml").exists()
    inputs = on["workflow_dispatch"]["inputs"]
    assert set(inputs) == {"mode", "only", "game", "repost", "test", "ping"}   # no dry_run/probe/kind
    assert inputs["mode"]["options"] == ["live", "test"] and inputs["mode"]["default"] == "live"
    # cron-job.org sends NO inputs at all, so the defaults must be a plain live run
    assert inputs["only"]["default"] == "all" and inputs["game"]["default"] == "" \
        and inputs["repost"]["default"] == ""
    # ⑥ (ping) is documented as a TEST switch, but job-level env reaches the LIVE run too, and
    # cron-job.org sends no inputs -- so an unscoped `!inputs.ping` made NO_PING=1 on every
    # scheduled run: settings.ping() short-circuits on it, PING_SCHEDULE was dead weight, and a
    # real version announcement posted without pinging the role (seen in the 2026-09-27 runs:
    # live = "no ping", test+ping = "<@&1296268365593186426>").
    assert env["NO_PING"] == "${{ inputs.mode != 'live' && !inputs.ping && '1' || '0' }}"
    assert inputs["test"]["options"] == ["webhooks", "codes", "schedule", "all"]
    job = mon["jobs"]["monitor"]
    assert "|| inputs.mode == 'test'" in str(job["if"])          # a test still runs on the dev repo
    steps = {str(s.get("name", "")): s for s in job["steps"]}
    live = {n: s for n, s in steps.items() if n.startswith("LIVE")}
    tests = {n: s for n, s in steps.items() if n.startswith("TEST")}
    assert len(live) == 2 and len(tests) == 4, (sorted(live), sorted(tests))
    assert live["LIVE · monitor run"]["if"] == "inputs.mode == 'live'"
    commit = next(s for n, s in live.items() if "commit state" in n)
    assert "inputs.mode == 'live'" in commit["if"] and "dry_run" not in commit["if"]
    for n, s in tests.items():                                   # every test is mode-gated…
        assert s["if"].startswith("inputs.mode == 'test'"), n
        assert "git commit" not in str(s.get("run", "")) and "git push" not in str(s.get("run", ""))
    # the codes/schedule tests are REAL runs (not sample cards) that can never save the state,
    # so the live run still posts the real thing later
    real = [s for n, s in tests.items() if "codes — the REAL" in n or "schedule — the REAL" in n]
    assert len(real) == 2
    for s in real:
        assert s["run"].strip() == "python -m gamexpress run"
        assert s["env"]["TEST_MODE"] == "1" and s["env"]["BOOTSTRAP_POST"] == "1"
        assert "runner.temp" in s["env"]["STATE_PATH"] and s["env"]["PEER_STATE_URL"] == "none"
    assert {s["env"]["ONLY"] for s in real} == {"codes", "schedule"}
    # a game that is not live yet has nothing real to fetch, so it is checked with example codes
    unl = next(s for n, s in tests.items() if "not live yet" in n)
    assert "--unlaunched" in unl["run"] and "--kind codes" in unl["run"]
    for name in ("monitor.yml", "ci.yml"):
        text = (wf / name).read_text(encoding="utf-8")
        assert "actions/checkout@v7" in text and "actions/setup-python@v7" in text, name
    am = yaml.safe_load((wf / "ci.yml").read_text(encoding="utf-8"))["jobs"]["automerge"]
    assert am["needs"] == "test" and "vars.AUTO_MERGE_DEPENDABOT == 'yes'" in am["if"]   # only after green tests
    assert "dependabot[bot]" in am["if"] and am["permissions"] == {"contents": "write", "pull-requests": "write"}
    assert not any("checkout" in str(step.get("uses", "")) for step in am["steps"])      # PR code never runs here
    assert not (wf / "dependabot_auto_merge.yml").exists()
    dep = yaml.safe_load((ROOT / ".github" / "dependabot.yml").read_text(encoding="utf-8"))
    assert all("labels" not in u for u in dep["updates"])            # custom labels must pre-exist -> none
    assert dep["updates"][0]["versioning-strategy"] == "increase-if-necessary"


def test_astral_actions_are_pinned_to_a_full_version_tag():
    """astral-sh publishes NO floating major tag (no `v10` for setup-uv, no `v4` for
    ruff-action — only `v10.2.0`, `v4.1.0`). A `uses: astral-sh/x@vN` therefore cannot be
    resolved, and GitHub resolves every `uses:` during *Set up job*, BEFORE any step runs —
    so `continue-on-error` cannot save the job either. That exact mistake has already failed
    a run twice (setup-uv@v9, ruff-action@v4), so it gets a test."""
    import re
    wf = ROOT / ".github" / "workflows"
    seen = []
    for path in sorted(wf.glob("*.yml")):
        for ref in re.findall(r"uses:\s*(astral-sh/[\w.-]+@\S+)", path.read_text(encoding="utf-8")):
            seen.append(ref)
            assert re.fullmatch(r"astral-sh/[\w.-]+@v\d+\.\d+\.\d+", ref), f"{path.name}: {ref}"
    assert len(seen) >= 3, seen          # 2x setup-uv (ci + monitor) + ruff-action


def test_preview_html_renders_cards():
    from gamexpress.preview_html import inline, render_page
    s = settings()
    pages = [("Code cards", k, p) for k, codes in CODE_SAMPLES.items()
             for p in cards.codes_payloads(GAMES[k], codes, s, s.ping("codes", k), 1790000000)]
    pages += [("Schedule cards", k, _render(k)) for k in SCHEDULE_SAMPLES]
    page = render_page(pages)
    assert page.count('class="container"') == len(pages) and 'class="btn"' in page
    assert "&lt;t:" in page and 'data-f="R"' in page and "@ping-role" in page
    assert "<script>" in page and "cdn.discordapp.com/emojis/1508619925940473966.gif" in page
    assert inline("**a** `<b>` [x](https://e.x) <t:1:R>").startswith("<strong>a</strong> <code>&lt;b&gt;</code>")



# =========================================================================== 1.1.1 (first live runs)
LIVE_NOW = 1790322634          # 2026-09-25 07:50 UTC — the user's first Test/Monitor runs


def test_fandom_live_tables_expiry_and_multi_code_rows():
    ww = {h.code: h for h in csrc.parse_fandom(fx("fandom_ww_live_trimmed.json"), LIVE_NOW)}
    assert list(ww) == ["WUTHERINGGIFT", "FALLINGSANCTUM", "FINDSENTINEL", "WAKINGMOON", "HEARTOFSWORD", "BURNINGSUN"]
    assert not ww["WUTHERINGGIFT"].expired and ww["WUTHERINGGIFT"].expires_at is None
    assert ww["WAKINGMOON"].expired and ww["WAKINGMOON"].expires_at == 1790006399        # Sep 21 08:59:59 PDT
    assert ww["WAKINGMOON"].rewards == "Astrite*100;Premium Tuner*20;Advanced Sealed Tube*5"
    hsr = {h.code: h for h in csrc.parse_fandom(fx("fandom_hsr_live_trimmed.json"), LIVE_NOW)}
    assert hsr["MALSV2F247FP"].expired and hsr["MALSV2F247FP"].expires_at == 1790035199  # end of 2026-09-21 UTC
    assert not hsr["OMEGA"].expired and not hsr["CREATIONNYMPH"].expired and not hsr["NSJR3B97ZZ5X"].expired
    assert hsr["MH5KC"].expired and hsr["MH5KC"].expires_at is None and hsr["SILVERWOLFLV999"].expired
    assert hsr["CREATIONNYMPH"].rewards == "Stellar Jade*60;Fuel*1;Heroic Variable*1"   # [[a|b]] inside ref=
    assert csrc.parse_fandom(fx("fandom_hsr_live_trimmed.json"), 1790000000)[0].expired is False  # before the date
    gi = [h.code for h in csrc.parse_fandom(fx("fandom_gi_live_trimmed.json"), LIVE_NOW)]
    assert gi == ["VESNAONPATROL", "GS71XAVWDS", "GS71XDYGEO", "GS71XYNSYJ", "GS71XOXYLG", "2BJ64QRZ7RT8"]  # CN skipped
    assert csrc.parse_expiry("December 14, 2025 07:59 (PT)", LIVE_NOW) == (True, 1765727999)       # PST in winter
    assert csrc.parse_expiry("indef") == (False, None) and csrc.parse_expiry("exp") == (True, None)
    assert csrc.parse_expiry("2026-10-01", LIVE_NOW) == (False, 1790899199)
    # a row without its valid-until column: the discovered date (4th field) is NOT an expiry
    no_until = {"query": {"pages": {"1": {"revisions": [{"*": "{{Code Row|NEWCODE123|G|Primogem*60|2026-09-20}}"}]}}}}
    assert [(h.code, h.expired, h.expires_at) for h in csrc.parse_fandom(no_until, LIVE_NOW)] == [("NEWCODE123", False, None)]


def test_ogc_reward_cleanup():
    ogc = {h.code: h.rewards for h in csrc.parse_ogc(fx("ogc_starrail_trimmed.json"))}
    assert ogc["7S4AD2X35NE3"] == ["Stellar Jade ×100", "Traveler's Guide ×5"]           # no "Unknown reward (hash)"
    assert ogc["AT45Q"] == ["Credit ×50,000", "Stellar Jade ×100"]                         # duplicate dropped
    assert ogc["BESTCOFFEEEVER"] == ["Express Special Blend - Rustic Infusion ×2", "Traveler's Guide ×3"]
    assert "BLADEFITCHECK" in ogc


def test_aggregator_copies_count_as_their_upstream():
    H = CodeHit
    g = lambda *hits: codeposter.gate(codeposter.group_hits(list(hits), LIVE_NOW)["NEWCODE1"], 2)
    assert g(H("NEWCODE1", "fandom"), H("NEWCODE1", "codehub", origin="fandom"))[0] is False   # same source twice
    assert g(H("NEWCODE1", "ogc"), H("NEWCODE1", "codehub", origin="fandom"))[0] is True
    hub = csrc.parse_codehub(fx("codehub_live_trimmed.json"), "honkai-star-rail")
    assert [(h.code, h.origin) for h in hub] == [("MALSV2F247FP", "seria")]
    results = {"seria:hkrpg": [H("OMEGA", "seria", verified=True)], "codehub:honkai-star-rail": hub}
    kept = codeposter.drop_stale_copies([h for r in results.values() for h in r], results)
    assert [h.code for h in kept] == ["OMEGA"]                 # seria dropped it -> PromoGacha's copy is stale
    results["seria:hkrpg"] = None                               # seria down: the copy is the best we have
    assert [h.code for h in codeposter.drop_stale_copies(hub, results)] == ["MALSV2F247FP"]


# =========================================================================== fandom code pages
# The four community wikis the codes monitor reads, exactly as listed in the request. A rename or
# a typo in config/games.json silently drops a whole source, so the mapping is asserted here.
FANDOM_PAGES = {
    "genshin": "fandom:genshin-impact/Promotional_Code",       # /wiki/Promotional_Code
    "starrail": "fandom:honkai-star-rail/Redemption_Code",     # /wiki/Redemption_Code
    "zzz": "fandom:zenless-zone-zero/Redemption_Code",         # /wiki/Redemption_Code
    "wuwa": "fandom:wutheringwaves/Redemption_Code",           # /wiki/Redemption_Code
}


def test_every_game_watches_the_fandom_page_the_community_maintains():
    for key, spec in FANDOM_PAGES.items():
        assert spec in GAMES[key].codes.get("sources", []), (key, GAMES[key].codes["sources"])


def test_the_live_genshin_fandom_page_yields_every_active_code_exactly_once():
    """Verbatim 'Active Codes' section of genshin-impact.fandom.com/wiki/Promotional_Code,
    captured 2026-09-27 (pageid 10893, revid 2183997, 2026-09-25T12:05:33Z). It carries every
    awkwardness the GI table has: a four-code row, a mixed-case code, a |ref= field full of
    URLs, and a China-only row that must not reach a global channel."""
    hits = csrc.parse_fandom(fx("fandom_gi_live_active_codes.json"), LIVE_NOW)
    codes = [h.code for h in hits]
    assert codes == ["EPIC2026", "VESNAONPATROL",                       # mixed case -> upper
                     "GS71XAVWDS", "GS71XDYGEO", "GS71XYNSYJ", "GS71XOXYLG",   # one row, 4 codes
                     "Y6JYMKV6JKSL", "YOAL3V36XHS7", "DUGODWKRHAKDNJ", "BALLETCOLLAB",
                     "2BJ64QRZ7RT8"]
    assert len(codes) == len(set(codes)), "the same code twice from one page"
    assert "YUANSHEN" not in codes                       # CN-only row
    assert not [h for h in hits if h.expired]            # the whole section is under ==Active==
    by_code = {h.code: h for h in hits}
    assert by_code["EPIC2026"].rewards == "Primogem*40;Mora*20000;Hero's Wit*5"
    assert by_code["GS71XOXYLG"].rewards == "Mora*30000;Hero's Wit*3;Mystic Enhancement Ore*5"


def test_an_expired_heading_in_column_zero_still_expires_its_codes():
    """The MediaWiki API returns a page from its first byte, so a wiki whose very first line is
    '==Expired Codes==' has no newline in front of it. The marker regex was anchored on \n, so
    that heading was invisible and every dead code on the page was posted as active."""
    wikitext = ("==Expired Codes==\n"
                "{{Code Row|DEADCODE1|G|Primogem*60|2026-01-01|unknown}}\n"
                "==Active Codes==\n"
                "{{Code Row|LIVECODE1|G|Primogem*60|2026-09-01|unknown}}\n")
    data = {"query": {"pages": {"1": {"revisions": [{"slots": {"main": {"*": wikitext}}}]}}}}
    hits = {h.code: h for h in csrc.parse_fandom(data, LIVE_NOW)}
    assert hits["DEADCODE1"].expired is True
    assert hits["LIVECODE1"].expired is False


def test_an_aggregator_copy_is_never_a_second_independent_source():
    """PromoGacha (codehub) copies other collectors and never deletes entries, so a copy counts
    as its UPSTREAM -- including an Open Gacha Codes / api.ennead.cc copy, which is the same
    backend as `ogc`. Otherwise one real source could satisfy a two-source gate all by itself."""
    hub = {"codes": [{"game": "genshin", "code": "GS71XAVWDS", "source": {"name": "Open Gacha Codes"}},
                     {"game": "genshin", "code": "EPIC2026", "source": {"name": "Fandom Wiki"}},
                     {"game": "genshin", "code": "DUGODWKRHAKDNJ", "source": {"name": "hoyo-codes"}},
                     {"game": "genshin", "code": "YOAL3V36XHS7", "source": {"name": "api.ennead.cc"}}]}
    origins = {h.code: h.origin for h in csrc.parse_codehub(hub, "genshin")}
    assert origins == {"GS71XAVWDS": "ennead", "EPIC2026": "fandom",
                       "DUGODWKRHAKDNJ": "seria", "YOAL3V36XHS7": "ennead"}

    # and the gate sees ONE family, not two, when ogc and its codehub copy are the only sources
    hits = [CodeHit("GS71XAVWDS", "ogc", None),
            next(h for h in csrc.parse_codehub(hub, "genshin") if h.code == "GS71XAVWDS")]
    info = codeposter.group_hits(hits, LIVE_NOW)["GS71XAVWDS"]
    assert info["families"] == {"ennead"}
    assert codeposter.passes_gate(info, 2) is False


def test_valid_until_date_beats_every_other_source():
    H = CodeHit
    dead = H("NEWCODE1", "fandom", None, expired=True, expires_at=LIVE_NOW - 3600)
    info = codeposter.group_hits([H("NEWCODE1", "ogc"), H("NEWCODE1", "humbao", verified=True),
                                  H("NEWCODE1", "x", verified=True), dead], LIVE_NOW)["NEWCODE1"]
    ok, why = codeposter.gate(info, 2)
    assert ok is False and why.startswith("expired 2026-09-25")
    alive = H("NEWCODE1", "fandom", None, expires_at=LIVE_NOW + 86400)          # a future date is fine
    assert codeposter.gate(codeposter.group_hits([H("NEWCODE1", "ogc"), alive], LIVE_NOW)["NEWCODE1"], 2)[0] is True


def test_live_2026_09_25_expired_livestream_codes_are_not_posted():
    """Regression from the first real dry run: 3 HSR + 3 WW livestream codes expired on
    2026-09-21 but the wikis still listed them under 'Active', PromoGacha never deletes and
    Open Gacha Codes lags — they must NOT be posted; the genuinely active ones must be."""
    hsr_hub = csrc.parse_codehub(fx("codehub_live_trimmed.json"), "honkai-star-rail")
    with tempfile.TemporaryDirectory() as tmp:
        sp = Path(tmp) / "s.json"
        st = State.load(sp)
        st.mark_bootstrapped("codes", "wuwa")
        st.mark_bootstrapped("codes", "starrail")
        st.save()
        table = {"fandom:wutheringwaves/Redemption_Code": csrc.parse_fandom(fx("fandom_ww_live_trimmed.json"), LIVE_NOW),
                 "codehub:wuthering-waves": csrc.parse_codehub(fx("codehub_live_trimmed.json"), "wuthering-waves"),
                 "ogc:wuwa": [CodeHit("WUTHERINGGIFT", "ogc", ["Astrite ×50"])],
                 "fandom:honkai-star-rail/Redemption_Code": csrc.parse_fandom(fx("fandom_hsr_live_trimmed.json"), LIVE_NOW),
                 "codehub:honkai-star-rail": hsr_hub,
                 "ogc:starrail": csrc.parse_ogc(fx("ogc_starrail_trimmed.json")),
                 "seria:hkrpg": [CodeHit("OMEGA", "seria", "60 stellar jade and one fuel", verified=True)]}
        ctx = make_ctx(sp, codes_table=table, now=LIVE_NOW)
        ctx.games = [GAMES["wuwa"], GAMES["starrail"]]
        asyncio.run(codeposter.run(ctx))
        posted = " ".join(json.dumps(x["payload"], ensure_ascii=False) for x in ctx.webhook.sent)
        for dead in ("FALLINGSANCTUM", "FINDSENTINEL", "WAKINGMOON", "MALSV2F247FP", "7S4AD2X35NE3"):
            assert dead not in posted, dead
        assert "WUTHERINGGIFT" in posted and "OMEGA" in posted
        assert ctx.state.code_records("starrail")["7S4AD2X35NE3"]["status"] == "rejected"
        assert any(r.startswith("🧊 HSR: 1 code(s) ignored — already expired") for r in ctx.report)
        assert any(r.startswith("⏳ HSR: ") and "NSJR3B97ZZ5X (only fandom)" in r for r in ctx.report)
        assert not any("pending (listed as expired" in r for r in ctx.report)        # no more 100-line summaries


def test_posted_code_is_struck_when_its_valid_until_date_passes():
    t0 = 1789900000
    with tempfile.TemporaryDirectory() as tmp:
        sp = Path(tmp) / "state.json"
        st = State.load(sp)
        st.mark_bootstrapped("codes", "starrail")
        st.save()
        table = {"seria:hkrpg": [CodeHit("LIVE4610", "seria", "Stellar Jade ×100", verified=True)],
                 "fandom:honkai-star-rail/Redemption_Code": [CodeHit("LIVE4610", "fandom", None, expires_at=t0 + 86400)]}
        ctx = make_ctx(sp, codes_table=table, now=t0)
        ctx.games = [GAMES["starrail"]]
        asyncio.run(codeposter.run(ctx))
        assert [x["method"] for x in ctx.webhook.sent] == ["POST"]
        ctx.state.save()
        table = {"seria:hkrpg": [CodeHit("LIVE4610", "seria", None, verified=True)],    # not re-checked yet
                 "ogc:starrail": [CodeHit("LIVE4610", "ogc", None)],                     # lagging aggregator
                 "fandom:honkai-star-rail/Redemption_Code": [
                     CodeHit("LIVE4610", "fandom", None, expired=True, expires_at=t0 + 86400)]}
        ctx = make_ctx(sp, codes_table=table, now=t0 + 2 * 86400)
        ctx.games = [GAMES["starrail"]]
        asyncio.run(codeposter.run(ctx))
        assert [x["method"] for x in ctx.webhook.sent] == ["PATCH"]
        assert "~~`LIVE4610`~~ · expired" in json.dumps(ctx.webhook.sent[0]["payload"], ensure_ascii=False)


def test_program_tba_line_hidden_once_the_update_is_known():
    s = settings()
    d = {"version": "4.6", "maint_start_ts": 1790546400, "maint_end_ts": 1790564400, "preinstall_ts": 1790229600}
    txt = json.dumps(cards.schedule_payload(GAMES["starrail"], d, s, s.ping("schedule", "starrail")), ensure_ascii=False)
    assert "Special Program: TBA" not in txt and "<t:1790546400:F>" in txt
    teaser = cards.schedule_payload(GAMES["starrail"], {"version": "4.7"}, s, s.ping("schedule", "starrail"))
    assert "Special Program: TBA" in json.dumps(teaser, ensure_ascii=False)          # nothing known yet -> TBA
    ww = cards.schedule_payload(GAMES["wuwa"], {"version": "3.7", "maint_start_ts": 1790712000}, s, s.ping("schedule", "wuwa"))
    assert "Special Broadcast: TBA" not in json.dumps(ww, ensure_ascii=False) and not cards.validate_payload(ww)


def test_repost_feedback_and_first_run_notes():
    with tempfile.TemporaryDirectory() as tmp:
        sp = Path(tmp) / "state.json"
        for value, expected in (("genshin:7.2", "version 7.2 isn't tracked"), ("genshin7.2", "use game:version"),
                                ("gensin:7.1", "unknown or inactive game 'gensin'")):
            ctx = make_ctx(sp, REPOST=value)
            asyncio.run(schedule.run(ctx))
            assert any(expected in r for r in ctx.report), (value, ctx.report)
        sp2 = Path(tmp) / "state2.json"
        ww = item_from_fx_json("wuwa", fx("fx_wuwa_3_7_broadcast.json"))
        late = 1789815600 + 10 * 86400                         # the broadcast was 10 days ago
        ctx = make_ctx(sp2, items={"wuwa": [ww]}, now=late)
        asyncio.run(schedule.run(ctx))
        assert ctx.webhook.sent == [] and any(r.startswith("🗂 WW 3.7: already out") for r in ctx.report)
        ctx.state.save()
        ctx = make_ctx(sp2, items={"wuwa": [ww]}, now=late + 600, REPOST=" WUWA:3.7 ")    # spaces / case forgiven
        asyncio.run(schedule.run(ctx))
        assert [x["method"] for x in ctx.webhook.sent] == ["POST"] and not any("repost" in r for r in ctx.report)



# =========================================================================== 1.2.0 (card buttons + countdown estimates)
def test_code_card_buttons_are_the_code_links_then_the_community_row():
    s = settings()
    codes = [{"code": "VESNAONPATROL", "sources": ["ogc", "fandom"], "rewards": "Primogem ×40"}]
    p = cards.codes_payloads(GAMES["genshin"], codes, s, s.ping("codes", "genshin"), LIVE_NOW)[0]
    flat = json.dumps(p, ensure_ascii=False)
    box = p["components"][-1]["components"]
    rows = [c for c in box if c["type"] == 1]
    assert [b["label"] for b in rows[0]["components"]] == ["VESNAONPATROL"]       # one Redeem link per code
    assert [b["label"] for b in rows[-1]["components"]] == ["Citlali News"]       # community row, at the end
    assert rows[-1]["components"][0]["url"] == "https://discord.gg/HyrVP9wRXu"
    assert rows[-1]["components"][0]["emoji"] == {"id": "1439878792653832253", "name": "starward11",
                                                  "animated": True}
    assert box[box.index(rows[-1]) - 1]["type"] == 14            # a separator in front of the row
    for gone in ("Redeem Page", "Youtube", "Twitch"):            # livestream buttons, not code buttons
        assert gone not in flat, gone
    assert not cards.validate_payload(p)
    ww = cards.codes_payloads(GAMES["wuwa"], [{"code": "WUTHERINGGIFT", "sources": ["ogc"]}],
                              s, s.ping("codes", "wuwa"), LIVE_NOW)[0]
    rows = [c for c in ww["components"][-1]["components"] if c["type"] == 1]
    assert [b["label"] for b in rows[-1]["components"]] == ["Citlali News"]       # in-game-only game too
    # the livestream card keeps Youtube / Twitch
    labels = [b["label"] for c in _render("starrail")["components"][1]["components"] if c["type"] == 1
              for b in c["components"]]
    assert labels[:2] == ["Youtube", "Twitch"]
    # configurable: COMMUNITY_BUTTONS=none -> no row at all
    off = settings(COMMUNITY_BUTTONS="none")
    assert off.community_buttons == []
    p2 = cards.codes_payloads(GAMES["genshin"], codes, off, off.ping("codes", "genshin"), LIVE_NOW)[0]
    assert [c for c in p2["components"][-1]["components"] if c["type"] == 1] == [
        {"type": 1, "components": [cards.link_button("VESNAONPATROL",
                                                    "https://genshin.hoyoverse.com/en/gift?code=VESNAONPATROL",
                                                    {"name": "🎁"})]}]
    custom = settings(COMMUNITY_BUTTONS='[{"label":"My Server","url":"https://discord.gg/abc"}]')
    assert [b["label"] for b in custom.community_buttons] == ["My Server"]


def test_countdown_pages_are_parsed():
    now = LIVE_NOW
    gengamer = (FIX / "countdown_gengamer_gi_livestream.html").read_text(encoding="utf-8")
    hit = countdown.parse_page("program", gengamer, now)
    assert hit["version"] == "7.2" and hit["ts"] == 1792756800        # Friday, October 23 at 8:00 AM EDT
    gacha = (FIX / "countdown_gachacountdown_gi.html").read_text(encoding="utf-8")
    hit2 = countdown.parse_page("update", gacha, now)
    assert hit2["version"] == "7.2"
    assert hit2["ts"] == now + 39 * 86400 + 14 * 3600 + 9 * 60 + 8    # 39d 14h 09m 08s from now
    assert countdown.find_version("Countdown to Version 7.2") == "7.2"
    assert "Hello & bye" in countdown.strip_html("<script>x=1</script><p>Hello &amp; bye</p>")
    assert countdown.SOURCES["wuwa"] and not countdown.SOURCES["ananta"]      # not released yet


def test_apply_estimates_never_overwrites_official_times():
    data, prov = {"maint_start_ts": 100}, {}
    assert schedule.apply_estimates(data, prov, {"maint_start_ts": 200}, 0) == []
    assert data["maint_start_ts"] == 100 and "estimated" not in data
    assert schedule.apply_estimates({}, {}, {"program_ts": 10 ** 10}, 0) == []        # absurd -> ignored
    data2, prov2 = {}, {}
    added = schedule.apply_estimates(data2, prov2, {"maint_start_ts": 1790712000,
                                                    "labels": ["Gacha Countdown"]}, 1790000000)
    assert added == ["maint_start_ts", "maint_end_ts"]                            # +5 h window
    assert data2["maint_end_ts"] == 1790712000 + 5 * 3600
    assert data2["estimated"] == ["maint_start_ts", "maint_end_ts"] and data2["estimate_sources"] == ["Gacha Countdown"]
    assert prov2["maint_start_ts"][0] == schedule.PRIORITY["countdown"] < schedule.PRIORITY["kuro"]


def test_estimated_maintenance_times_fill_only_what_official_misses():
    with tempfile.TemporaryDirectory() as tmp:
        sp = Path(tmp) / "state.json"
        ww = item_from_fx_json("wuwa", fx("fx_wuwa_3_7_broadcast.json"))
        estimate = {"wuwa": {"version": "3.7", "maint_start_ts": 1790712000, "labels": ["Gacha Countdown"]}}
        ctx = make_ctx(sp, items={"wuwa": [ww]}, now=1789300000, BOOTSTRAP_POST=1)
        ctx.estimates = estimate
        asyncio.run(schedule.run(ctx))
        posts = [x for x in ctx.webhook.sent if x["method"] == "POST"]
        assert len(posts) == 1
        flat = json.dumps(posts[0]["payload"], ensure_ascii=False)
        assert "<t:1790712000:f>" in flat and "<t:1790730000:t>" in flat       # start + the 5 h estimate
        assert "estimated from Gacha Countdown" in flat
        assert any(r.startswith("🕒 WW 3.7: pre-install, maintenance start, maintenance end estimated")
                   for r in ctx.report)
        ctx.state.save()
        # the official maintenance notice arrives -> it wins and the 🕒 line disappears silently
        notice = Item("kuro", "wuwa", "9001", "https://wutheringwaves.kurogames.com/en/main/news/detail/9001",
                      "Version 3.7 Update Maintenance Notice",
                      "Version 3.7 pre-download will begin at 2026-09-28 10:00 (UTC+8).\n"
                      "Maintenance Time: 2026-09-30 04:00 - 11:00 (UTC+8)\nCompensation: Astrite ×300",
                      1790000000)
        ctx = make_ctx(sp, items={"wuwa": [ww, notice]}, now=1790001000)
        ctx.estimates = estimate
        asyncio.run(schedule.run(ctx))
        assert [x["method"] for x in ctx.webhook.sent] == ["PATCH"]
        flat2 = json.dumps(ctx.webhook.sent[0]["payload"], ensure_ascii=False)
        assert "<t:1790712000:f>" in flat2 and "<t:1790737200:t>" in flat2     # the official window
        assert "estimated from" not in flat2
        assert ctx.state.schedule_records("wuwa")["3.7"]["data"].get("estimated") is None


def test_an_estimate_for_another_version_is_ignored():
    with tempfile.TemporaryDirectory() as tmp:
        sp = Path(tmp) / "state.json"
        ww = item_from_fx_json("wuwa", fx("fx_wuwa_3_7_broadcast.json"))
        ctx = make_ctx(sp, items={"wuwa": [ww]}, now=1789300000, BOOTSTRAP_POST=1)
        ctx.estimates = {"wuwa": {"version": "9.9", "maint_start_ts": 1790712000, "labels": ["X"]}}
        asyncio.run(schedule.run(ctx))
        assert [x["method"] for x in ctx.webhook.sent] == ["POST"]
        assert "estimated from" not in json.dumps(ctx.webhook.sent[0]["payload"], ensure_ascii=False)


# =========================================================================== 1.3.0 (program media)
def test_images_are_upgraded_to_the_full_size_rendition():
    # a tweet photo: X serves `small` unless you ask for the original upload
    assert media.twimg_orig("https://pbs.twimg.com/media/HR70hTAaoAA8Dzz.jpg") == \
        "https://pbs.twimg.com/media/HR70hTAaoAA8Dzz.jpg?name=orig"
    assert media.twimg_orig("https://pbs.twimg.com/media/HR70hTAaoAA8Dzz?format=jpg&name=large") == \
        "https://pbs.twimg.com/media/HR70hTAaoAA8Dzz?format=jpg&name=large"      # already sized — untouched
    # a nitter mirror's pic proxy -> the twimg CDN, then the original
    assert media.upgrade("https://nitter.cf/pic/media%2FHR70hTAaoAA8Dzz.jpg") == \
        "https://pbs.twimg.com/media/HR70hTAaoAA8Dzz.jpg?name=orig"
    # a YouTube thumbnail: 480x360 -> 1280x720, from a watch URL, a short link or a bare id
    assert media.youtube_thumb("https://www.youtube.com/watch?v=ItNs39qvw_w") == \
        "https://i.ytimg.com/vi/ItNs39qvw_w/maxresdefault.jpg"
    assert media.youtube_thumb("ItNs39qvw_w") == "https://i.ytimg.com/vi/ItNs39qvw_w/maxresdefault.jpg"
    assert media.upgrade("https://i.ytimg.com/vi/ItNs39qvw_w/hqdefault.jpg") == \
        "https://i.ytimg.com/vi/ItNs39qvw_w/maxresdefault.jpg"
    # an official article cover is already full size -> never rewritten to another host
    cover = "https://fastcdn.hoyoverse.com/content-v2/hkrpg/166179/c66081f0bbfae6d938b50c41e595c185_1.jpg"
    assert media.upgrade(cover) == cover and media.upgrade("") == ""
    # ranking: livestream artwork first, then a full-size tweet photo, then a cover
    ranked = media.rank([cover, "https://pbs.twimg.com/media/HR70hTAaoAA8Dzz.jpg",
                         "https://i.ytimg.com/vi/ItNs39qvw_w/maxresdefault.jpg", ""])
    assert ranked == ["https://i.ytimg.com/vi/ItNs39qvw_w/maxresdefault.jpg",
                      "https://pbs.twimg.com/media/HR70hTAaoAA8Dzz.jpg?name=orig", cover]
    assert media.rank(None) == [] and media.rank([cover] * 9) == [cover]         # duplicates collapse
    assert len(media.rank([cover.replace("/166179/", f"/{i}/") for i in range(9)])) == 4   # capped at 4


def test_official_news_page_entries_are_parsed():
    page = (FIX / "newspage_hsr_news.html").read_text(encoding="utf-8")
    entries = newspage.parse_news_page(page, "https://hsr.hoyoverse.com/en-us/news")
    assert [e["id"] for e in entries] == ["166181", "166180", "166179", "166100", "166116", "165975"]
    first = entries[0]
    assert first["url"] == "https://hsr.hoyoverse.com/en-us/news/166181"          # relative href resolved
    assert first["title"] == 'Improv Tour Trailer: "It Became Art"'               # site suffix stripped
    assert first["image"].startswith("https://fastcdn.hoyoverse.com/content-v2/hkrpg/166181/")
    assert first["ts"] == 0                                   # a bare M/D/YYYY carries no time — never guessed
    # only the program entry matches, and only for its own version
    prog = [e for e in entries if newspage._matches(GAMES["starrail"], e["title"], "4.6")]
    assert [e["id"] for e in prog] == ["166100"]
    assert newspage._matches(GAMES["starrail"], prog[0]["title"], "4.5") is False
    assert newspage._matches(GAMES["starrail"], entries[2]["title"], "4.6") is False   # a trailer is not it
    # the article page yields the embedded stream -> the 1280x720 artwork
    art = newspage.parse_article((FIX / "newspage_hsr_article.html").read_text(encoding="utf-8"))
    assert art["youtube"] == "https://www.youtube.com/watch?v=ItNs39qvw_w"
    assert "166179" in art["images"][0] and "Tap to unmute" not in art["text"]


def test_hoyolab_program_article_is_picked_not_the_maintenance_notice():
    page = fx("hoyolab_starrail_newslist_program.json")
    hit = hoyolab.pick_program([page], "4.6", GAMES["starrail"].program_patterns)
    assert hit and hit[0] == "46691962"                        # the Special Program preview, not 46814308
    assert hit[2]["subject"] == "Version 4.6 Special Program Preview"
    assert hoyolab.pick_program([page], "4.5", GAMES["starrail"].program_patterns) is None   # other version
    assert hoyolab.pick_program([{"retcode": 1}], "4.6", ["special program"]) is None        # API error page
    assert hoyolab.pick_program([], "4.6", ["special program"]) is None


def test_the_program_announcement_replaces_the_maintenance_notice_on_the_card():
    with tempfile.TemporaryDirectory() as tmp:
        sp = Path(tmp) / "state.json"
        notice = hoyolab_item("hoyolab_starrail_46814308_full.json", "starrail")
        ctx = make_ctx(sp, items={"starrail": [notice]}, now=1790000000, BOOTSTRAP_POST=1)
        asyncio.run(schedule.run(ctx))
        posts = [x for x in ctx.webhook.sent if x["method"] == "POST"]
        assert len(posts) == 1
        flat = json.dumps(posts[0]["payload"], ensure_ascii=False)
        assert "hoyolab.com/article/46814308" in flat          # all the run saw was the notice
        assert "pompom" not in flat.lower()                    # ...but its cover is NOT the program's art
        assert "🖼️" not in flat
        assert schedule.needs_media(ctx.state, "starrail", 1790000000)     # -> worth one lookup
        ctx.state.save()
        # the lookup finds the Special Program preview: link + key art + air time
        found = {"url": "https://www.hoyolab.com/article/46691962",
                 "title": "Version 4.6 Special Program Preview",
                 "images": ["https://pbs.twimg.com/media/HR70hTAaoAA8Dzz.jpg"],
                 "youtube": "https://www.youtube.com/watch?v=EXAMPLE1234",
                 "program_ts": 1789860600, "source": "HoYoLAB"}
        ctx = make_ctx(sp, items={"starrail": [notice]}, now=1790000000)
        ctx.media = {"starrail": {"4.6": found}}
        asyncio.run(schedule.run(ctx))
        assert [x["method"] for x in ctx.webhook.sent] == ["PATCH"]       # same card, edited silently
        flat2 = json.dumps(ctx.webhook.sent[0]["payload"], ensure_ascii=False)
        # the title links the ANNOUNCEMENT, not the stream it happens to mention
        assert "## [Honkai: Star Rail Version 4.6 Special Program](https://www.hoyolab.com/article/46691962)" in flat2, flat2
        assert "youtube.com/watch?v=EXAMPLE1234" in flat2                 # the stream stays in source_links
        assert "pbs.twimg.com/media/HR70hTAaoAA8Dzz.jpg?name=orig" in flat2    # full-size key art
        assert "<t:1789860600:F>" in flat2 and "<t:1789860600:R>" in flat2     # the air time, user's format
        assert "🖼️" not in flat2
        rec = ctx.state.schedule_records("starrail")["4.6"]
        assert rec["data"]["media_from"] == "HoYoLAB"
        assert "program_seen" not in rec["data"]                # the lookup never claims a real post
        assert not schedule.needs_media(ctx.state, "starrail", 1790000000)     # never looked up twice
    # PROGRAM_MEDIA=0 -> the lookup is skipped entirely, so the card keeps the notice link and
    # stays "needs a lookup" (a fresh state, so this is a clean first post and not an edit)
    with tempfile.TemporaryDirectory() as tmp:
        sp2 = Path(tmp) / "state.json"
        notice = hoyolab_item("hoyolab_starrail_46814308_full.json", "starrail")
        ctx = make_ctx(sp2, items={"starrail": [notice]}, now=1790000000, PROGRAM_MEDIA=0, BOOTSTRAP_POST=1)
        ctx.media = {"starrail": {"4.6": found}}
        asyncio.run(schedule.run(ctx))
        posts = [x for x in ctx.webhook.sent if x["method"] == "POST"]
        assert len(posts) == 1
        flat3 = json.dumps(posts[0]["payload"], ensure_ascii=False)
        assert "46691962" not in flat3 and "🖼️" not in flat3
        assert schedule.needs_media(ctx.state, "starrail", 1790000000)


def test_program_media_is_only_looked_up_when_it_is_missing():
    s = settings()
    assert s.program_media and not settings(PROGRAM_MEDIA=0).program_media
    assert GAMES["starrail"].news_url == "https://hsr.hoyoverse.com/en-us/news"
    assert GAMES["genshin"].news_url == "https://genshin.hoyoverse.com/en/news"
    assert GAMES["wuwa"].news_url == "https://wutheringwaves.kurogames.com/en/main/news"
    assert schedule.PRIORITY["news"] < schedule.PRIORITY["hoyolab"]       # an in-feed post still wins
    assert schedule.PRIORITY["news"] > schedule.PRIORITY["x"]
    # no media -> nothing changes, and an empty dict is not an error
    data, prov = {"title_url": "https://x/y"}, {}
    assert schedule.apply_program_media(data, prov, None, 0) == []
    assert schedule.apply_program_media(data, prov, {}, 0) == []
    assert data == {"title_url": "https://x/y"}
    # an absurd air time is dropped, but a past one is kept (it is an official post, not a guess)
    d2 = {}
    schedule.apply_program_media(d2, {}, {"url": "https://x/y", "program_ts": 10 ** 10}, 1790000000)
    assert "program_ts" not in d2
    d3 = {}
    schedule.apply_program_media(d3, {}, {"url": "https://x/y", "program_ts": 1789860600}, 1790000000)
    assert d3["program_ts"] == 1789860600
    # an existing official program time is never overwritten by the lookup
    d4 = {"program_ts": 1789860600}
    schedule.apply_program_media(d4, {}, {"url": "https://x/y", "program_ts": 1780000000}, 1790000000)
    assert d4["program_ts"] == 1789860600


 # =========================================================================== runner
def test_the_program_lookup_falls_back_past_x_to_hoyolab_then_the_news_page():
    """runner.find_program is the ONE lookup, X first (v1.8.0). Without an X client the backups
    run in their proven order: the HoYoLAB news list, then the official news page (which
    archives every announcement and carries the key art), then the feed mirror."""
    from gamexpress.runner import find_program

    class News:
        def __init__(self, html):
            self.html, self.urls = html, []

        async def get_json(self, url, **k):
            return None                                    # HoYoLAB down -> the next backup runs

        async def get_text(self, url, **k):
            self.urls.append(url)
            last = url.split("?")[0].rstrip("/").rsplit("/", 1)[-1]
            return ((FIX / "newspage_hsr_article.html").read_text(encoding="utf-8")
                    if last.isdigit() else self.html)

    def ctx_of(fetcher, tmp):
        ctx = make_ctx(Path(tmp) / "s.json", now=1790000000)   # make_ctx has no X client (x=None)
        ctx.fetcher = fetcher
        return ctx

    f = News((FIX / "newspage_hsr_news.html").read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory() as tmp:
        hit = asyncio.run(find_program(ctx_of(f, tmp), GAMES["starrail"], "4.6"))
    assert hit["url"] == "https://hsr.hoyoverse.com/en-us/news/166100"      # the Special Program…
    assert "46814308" not in hit["url"]                                     # …not the maintenance notice
    assert hit["images"][0] == "https://i.ytimg.com/vi/ItNs39qvw_w/maxresdefault.jpg"   # 1280x720
    assert hit["source"] == "Official News"
    assert f.urls[0].endswith("?type=notice") and len(f.urls) == 2          # first tab wins -> 2 fetches
    # HoYoLAB answers -> it wins and the news page is never even fetched
    calls = []

    async def fake_list(fetcher, game, version, **k):
        calls.append(version)
        return {"url": "https://www.hoyolab.com/article/46691962",
                "title": "Version 4.6 Special Program Preview",
                "images": ["https://pbs.twimg.com/media/AAA.jpg"], "text": "", "ts": 1789000000}

    old = hoyolab.find_program
    hoyolab.find_program = fake_list
    try:
        f2 = News((FIX / "newspage_hsr_news.html").read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as tmp:
            hit2 = asyncio.run(find_program(ctx_of(f2, tmp), GAMES["starrail"], "4.6"))
    finally:
        hoyolab.find_program = old
    assert calls == ["4.6"] and hit2["url"].endswith("46691962")
    assert hit2["images"] == ["https://pbs.twimg.com/media/AAA.jpg"]
    assert f2.urls == []                                    # the news page was never asked


def test_sample_cards_are_only_for_the_games_with_nothing_real_to_fetch():
    """The codes test posts the REAL codes of the live games, so the sample cards are kept for
    the games that are not out yet only — a sample must never stand in for a real source."""
    from gamexpress.__main__ import sample_payloads

    def names(**kw):
        return [n for _f, n, _p in sample_payloads("codes", **kw)]

    assert set(names()) >= {"codes_genshin", "codes_starrail", "codes_zzz", "codes_wuwa",
                            "codes_hna", "codes_ananta"}
    assert names(unlaunched=True) == ["codes_hna", "codes_ananta"]       # the unreleased games only
    assert names(unlaunched=True, game="ananta") == ["codes_ananta"]
    assert names(game="genshin") == ["codes_genshin"]          # one card per game, all its codes


# ================================================== the 2026-09-26 schedule-card fixes
def _it(source="hoyolab", game="zzz", title="", text="", url="https://x/y", ts=1790000000, imgs=None):
    return Item(source=source, game=game, id="1", url=url, title=title, text=text,
                published_ts=ts, images=list(imgs or []))


def test_the_program_lookup_runs_on_a_first_run_when_the_state_is_empty():
    now = 1790000000
    assert schedule.needs_program_lookup([], {}, now)
    seen = [schedule.Extract(_it(), "program", "3.2")]
    assert not schedule.needs_program_lookup(seen, {}, now)
    assert not schedule.needs_program_lookup([], {"data": {"program_seen": True}}, now)
    assert not schedule.needs_program_lookup([], {"data": {"media_from": "Official News"}}, now)
    assert not schedule.needs_program_lookup([], {"data": {"maint_start_ts": now - 13 * 3600}}, now)
    assert callable(schedule.version_extracts)


def test_an_event_post_is_never_mistaken_for_the_program_announcement():
    prize = _it(title="[Prize Event] Participate in the event for a chance to obtain Master Tape x10!",
                text="The Zenless Zone Zero Version 3.2 Special Program will air on August 28.")
    assert schedule.classify(GAMES["zzz"], prize) != "program"
    notice = _it(title="Version 4.6 Update and Maintenance Notice",
                 text="The Honkai: Star Rail Version 4.6 Special Program aired on 2026-09-20.")
    assert schedule.classify(GAMES["starrail"], notice) != "program"
    for key, title in (("zzz", 'Zenless Zone Zero Version 3.2 "Their Secret Histories" Special Program Announcement'),
                       ("starrail", 'Honkai: Star Rail Version 4.6 "Dance With the Beast Before Moonrise" Special Program'),
                       ("genshin", "Genshin Impact Version 7.1 Special Program Preview"),
                       ("wuwa", "Wuthering Waves Version 3.7 Preview Special Broadcast")):
        assert schedule.classify(GAMES[key], _it(title=title, text=title)) == "program", key
    assert not newspage._matches(GAMES["zzz"], "[Prize Event] Participate in the event", "3.2")
    assert newspage._matches(GAMES["zzz"], "Version 3.2 Special Program Announcement", "3.2")
    assert hoyolab.pick_program([{"retcode": 0, "data": {"list": [
        {"post": {"post_id": "46814308", "subject": "Version 4.6 Update and Maintenance Notice", "created_at": 1790300000}},
        {"post": {"post_id": "46691962", "subject": 'Honkai: Star Rail Version 4.6 "Dance With the Beast Before Moonrise" Special Program', "created_at": 1789100000}},
    ]}}], "4.6", ["special program"])[0] == "46691962"


def test_a_livestream_link_yields_a_real_thumbnail():
    assert media.youtube_thumb("https://youtube.com/live/drFgtruoPe8") == \
        "https://i.ytimg.com/vi/drFgtruoPe8/maxresdefault.jpg"
    assert media.youtube_thumb("https://youtube.com/live/nMa_e5ChL6w?feature=share") == \
        "https://i.ytimg.com/vi/nMa_e5ChL6w/maxresdefault.jpg"
    assert media.youtube_thumb("ItNs39qvw_w") == "https://i.ytimg.com/vi/ItNs39qvw_w/maxresdefault.jpg"
    assert media.youtube_thumb("not a video") == "" and media.youtube_thumb("") == ""
    assert newspage.YOUTUBE.search("on youtube.com/live/drFgtruoPe8 tonight").group(1) == "drFgtruoPe8"


def test_the_same_key_art_at_two_sizes_is_one_image():
    small = "https://upload-os-bbs.hoyolab.com/upload/community/2026/08/28/e81786764983f1b06b437847ce9f1569.jpg"
    big = "https://upload-os-bbs.hoyolab.com/upload/community/2026/08/28/d65d59264a6f377c0683cd3323c6b006.jpg"
    got = hoyolab._images({"image_list": [{"url": small, "width": 1200, "height": 675},
                                          {"url": big, "width": 1920, "height": 1080}]})
    assert got == [big]
    other = "https://upload-os-bbs.hoyolab.com/upload/community/2026/08/28/other.jpg"
    assert hoyolab._images({"image_list": [{"url": big, "width": 1920, "height": 1080},
                                           {"url": other, "width": 1080, "height": 1080}]}) == [big, other]
    assert hoyolab._images({"image_list": [{"url": small}, {"url": big}]}) == [small, big]
    assert media.rank([small + "?x-oss-process=image/resize,s_600", small]) == [small]


def test_the_maintenance_block_has_no_blank_line_between_pre_install_and_maintenance():
    d = {"preinstall_ts": 1790560800, "maint_start_ts": 1790712000, "maint_end_ts": 1790737200,
         "compensation": "Astrite x300, Crystal Solvent x2"}
    block = cards.maintenance_block(GAMES["wuwa"], d)
    assert "✦ Pre-Install: <t:1790560800:F>\n✦ Maintenance: <t:1790712000:f> to <t:1790737200:t>" in block
    assert "\n\n✦ Maintenance" not in block


def test_a_news_feed_mirror_finds_the_announcement():
    body = (FIX / "ww_articles_latest.xml").read_text(encoding="utf-8")
    entries = newspage.parse_feed_entries(body)
    assert [e["title"] for e in entries] == ["About Tiered Client Resource Downloads",
                                             "Version 3.7 Update Maintenance Notice",
                                             "Version 3.7 Preview Special Broadcast"]
    assert GAMES["wuwa"].program_feeds[0].endswith("articles_latest.xml")

    class Feed:
        async def get_text(self, url, **k):
            return body if url.endswith("articles_latest.xml") else ""

    hit = asyncio.run(newspage.fetch_program_feed(Feed(), GAMES["wuwa"], "3.7", 1790000000))
    assert hit["url"].endswith("/5441") and hit["title"] == "Version 3.7 Preview Special Broadcast"
    assert hit["images"] == ["https://hw-media-cdn-mingchao.kurogame.com/akiwebsite/website2.0/images/1789182000000/broadcast-1789182000.jpeg"]
    assert hit["youtube"] == "https://www.youtube.com/watch?v=nMa_e5ChL6w"


def test_the_tweet_data_chain_tries_fxtwitter_then_fixupx_then_vxtwitter():
    from gamexpress.sources.twitter import FX_SOURCES, VXTWITTER_URL, XClient
    assert [n for n, _ in FX_SOURCES] == ["fxtwitter", "fixupx"]
    assert VXTWITTER_URL == "https://api.vxtwitter.com/Twitter/status/{id}"
    fx_body = {"tweet": {"id": "1", "text": "hello", "created_timestamp": 5,
                          "media": {"photos": []}, "author": {"screen_name": "ZZZ_EN"},
                          "url": "https://x.com/ZZZ_EN/status/1"}}
    vx_body = {"tweetID": "1", "text": "hello", "date_epoch": 5, "mediaURLs": [],
               "user_screen_name": "ZZZ_EN", "tweetURL": "https://x.com/ZZZ_EN/status/1"}
    class F:
        def __init__(self, ok): self.ok, self.calls = set(ok), []
        async def get_json(self, url, source="", **k):
            self.calls.append(source)
            if source not in self.ok:
                return None
            return fx_body if source in ("fxtwitter", "fixupx") else vx_body
    st = settings()
    f = F(["fxtwitter"])
    c = XClient(f, st)
    assert asyncio.run(c.tweet("1"))["author"] == "ZZZ_EN" and f.calls == ["fxtwitter"]
    f = F(["fixupx"])
    c = XClient(f, st)
    asyncio.run(c.tweet("1"))
    assert f.calls == ["fxtwitter", "fixupx"] and c.source_used == {"fixupx": 1}
    f = F(["vxtwitter"])
    c = XClient(f, st)
    asyncio.run(c.tweet("1"))
    assert f.calls == ["fxtwitter", "fixupx", "vxtwitter"] and c.source_used == {"vxtwitter": 1}


def test_the_program_lookup_runs_end_to_end_on_a_fresh_state():
    """v1.8.0: on an empty state the card is built from the real announcement TWEET (seed file ->
    fxtwitter by id), not from a page — the whole point of the X-first change."""
    from gamexpress import runner
    notice = Item(source="hoyolab", game="starrail", id="46814308",
                  url="https://www.hoyolab.com/article/46814308",
                  title="Version 4.6 Update and Maintenance Notice",
                  text="The Version 4.6 pre-installation will begin at 2026-09-24 14:00 (UTC+8). Version update maintenance on 2026-09-28 06:00 (UTC+8) for 5 hours.",
                  published_ts=1790300000, images=[])
    with tempfile.TemporaryDirectory() as tmp:
        ctx, _f = _x_ctx(Path(tmp) / "state.json",
                         {"2099440781115211916": "fx_starrail_4_6_program.json"}, now=1790400000)
        ctx.items = {"starrail": [notice]}
        assert ctx.state.schedule_records("starrail") == {}            # a first run: nothing stored
        asyncio.run(runner.gather_program_media(ctx))
        hit = (ctx.media.get("starrail") or {}).get("4.6")
        assert hit, "the lookup did not run on a fresh state"
        assert hit["source"] == "x"
        assert hit["url"] == "https://x.com/honkaistarrail/status/2099440781115211916"
        assert "46814308" not in hit["url"]
        assert "https://pbs.twimg.com/media/HSK2Q2pXsAA4YJA.jpg?name=orig" in hit["images"]
        assert hit["program_ts"] == 1789903800
        d = schedule.merge(GAMES["starrail"], "4.6",
                           schedule.version_extracts(ctx, GAMES["starrail"])["4.6"],
                           {}, {}, {}, ctx.now, [], None, hit)
        # the title links the ANNOUNCEMENT (the tweet), not the livestream it mentions
        assert d["title_url"] == "https://x.com/honkaistarrail/status/2099440781115211916"
        assert d["source_url"] == "https://x.com/honkaistarrail/status/2099440781115211916"
        assert d["youtube_video"] == "https://www.youtube.com/watch?v=drFgtruoPe8"

# --------------------------------------------------------------- X-first schedule (v1.8.0)
# The 2026-09-27 run got all four games wrong: GI/HSR/ZZZ reported "no program announcement
# found" and WW linked a lore article. X is now the primary lookup, so these run against the
# four REAL api.fxtwitter.com responses captured on 2026-09-27, not example data.
REAL_PROGRAMS = {
    "genshin": ("7.1", "fx_genshin_7_1_program.json", "2096810691021689205",
                "https://pbs.twimg.com/media/HRlONCqXcAUhgGD.jpg?name=orig", 1789214400),
    "starrail": ("4.6", "fx_starrail_4_6_program.json", "2099440781115211916",
                 "https://pbs.twimg.com/media/HSK2Q2pXsAA4YJA.jpg?name=orig", 1789903800),
    "zzz": ("3.2", "fx_zzz_3_2_program.json", "2091737263398862915",
            "https://pbs.twimg.com/media/HQZWs-3WAAEj32y.jpg?name=orig", 1787916600),
    "wuwa": ("3.7", "fx_wuwa_3_7_broadcast.json", "2098607530780021002",
             "https://pbs.twimg.com/media/HR70hTAaoAA8Dzz.jpg?name=orig", 1789815600),
}


class SeedFetcher:
    """Serves api.fxtwitter.com/status/<id> from the captured fixtures, and records every other
    source that gets asked — so a test can prove the backups were never reached."""

    def __init__(self, ids):
        self.bodies = {i: fx(f) for i, f in ids.items()}
        self.asked: list[str] = []
        self.health: dict = {}

    async def get_json(self, url, source="", **kw):
        self.asked.append(source or url)
        import re as _re
        m = _re.search(r"/status/(\d+)", url)
        return self.bodies.get(m.group(1)) if m else None

    async def get_text(self, url, source="", **kw):
        self.asked.append(source or url)
        return ""


def _x_ctx(state_path, ids, now=1789300000):
    from gamexpress.sources.twitter import XClient
    f = SeedFetcher(ids)
    ctx = make_ctx(state_path, now=now)
    ctx.fetcher, ctx.x = f, XClient(f, ctx.settings)
    return ctx, f


def test_the_program_lookup_is_x_first_for_every_live_game():
    """All four real 2026-09 announcements resolve to the tweet itself — its URL, its `?name=orig`
    key art and its air time — and no backup source is consulted at all."""
    from gamexpress.runner import find_program
    ids = {tid: f for _, f, tid, _, _ in REAL_PROGRAMS.values()}
    with tempfile.TemporaryDirectory() as tmp:
        ctx, f = _x_ctx(Path(tmp) / "s.json", ids)
        for key, (ver, _, tid, img, ts) in REAL_PROGRAMS.items():
            hit = asyncio.run(find_program(ctx, GAMES[key], ver))
            assert hit, f"{key} {ver}: X-first lookup found nothing"
            assert hit["source"] == "x", f"{key} {ver}: fell back to {hit.get('source')}"
            assert hit["url"].endswith(f"/status/{tid}"), f"{key} {ver}: wrong link {hit['url']}"
            assert img in hit["images"], f"{key} {ver}: key art missing from {hit['images']}"
            assert hit["program_ts"] == ts, f"{key} {ver}: air time {hit['program_ts']} != {ts}"
        assert not [a for a in f.asked if a in ("hoyolab", "newspage")], \
            f"a backup source was asked: {f.asked}"


def test_the_seeded_tweet_makes_a_fresh_test_run_show_real_data():
    """`mode=test` starts from an empty state every run, and a nitter timeline only reaches back a
    few days — so the announcement id lives in config/program_announcements.json. That is what
    lets a test card show the real link and the real key art instead of TBA."""
    from gamexpress.runner import find_program
    from gamexpress.sources import twitter
    for key, (ver, _, tid, img, _) in REAL_PROGRAMS.items():
        seed = twitter.program_seed(key, ver)
        assert seed.get("id") == tid, f"{key} {ver} is not seeded with {tid} (got {seed.get('id')})"
        assert seed.get("url", "").endswith(f"/status/{tid}"), f"{key} {ver}: bad seeded url"
        assert seed.get("image") == img, f"{key} {ver}: seeded art is not the ?name=orig one"
    ids = {tid: f for _, f, tid, _, _ in REAL_PROGRAMS.values()}
    with tempfile.TemporaryDirectory() as tmp:                 # an EMPTY state, as a test run has
        ctx, _ = _x_ctx(Path(tmp) / "fresh.json", ids)
        for key, (ver, _, _, _, _) in REAL_PROGRAMS.items():
            hit = asyncio.run(find_program(ctx, GAMES[key], ver))
            assert hit and hit["images"], f"{key} {ver}: a fresh run produced no image"


def test_a_lore_article_is_never_the_program_announcement():
    """The exact post that put the wrong link on the WW card on 2026-09-27: it contains the words
    "Special Program" and is a story chapter. An announcement states WHEN it airs; this does not."""
    lore = ("Insider Channel: Special Program | Signs of Imprisonment: Part Three\nQiuyuan once "
            "investigated a medicinal-herb corruption case at Mingting's order during his service "
            "as the senior agent of the Internal Security Agency.")
    assert schedule.is_program_announcement(GAMES["wuwa"], lore) is False
    assert schedule.NOT_PROGRAM_TITLE.search("Insider Channel: Special Program")
    # ...while the real one still passes, giveaway clause and all
    real = fx("fx_wuwa_3_7_broadcast.json")["tweet"]["text"]
    assert schedule.is_program_announcement(GAMES["wuwa"], real) is True


def test_a_giveaway_inside_the_announcement_does_not_veto_it():
    """Three of the four real announcements mention codes or prizes in the BODY. Only the headline
    is screened, or every one of them would be rejected."""
    for key, (_, fixture, _, _, _) in REAL_PROGRAMS.items():
        text = fx(fixture)["tweet"]["text"]
        assert schedule.is_program_announcement(GAMES[key], text), f"{key}: real one rejected"


def test_a_stitched_vertical_strip_is_not_key_art():
    """The 2026-09-27 WW card carried a 1440x29482 image — a whole article as one vertical strip,
    which Discord renders as an unreadable sliver."""
    from gamexpress.media import sane_aspect
    assert sane_aspect(1440, 29482) is False
    assert sane_aspect(1920, 1080) is True          # HSR / ZZZ / WW key art
    assert sane_aspect(1200, 675) is True           # GI key art
    assert sane_aspect(None, None) is True          # most sources report no size at all


def test_a_timeline_scan_finds_a_new_announcement_and_seeds_it():
    """Discovery half: when the announcement is still new enough to be in the nitter timeline it is
    matched there and written back to the seed file for the runs that come later."""
    import shutil

    from gamexpress.sources import twitter
    entry = {"id": "9", "account": "GenshinImpact",
             "url": "https://x.com/GenshinImpact/status/9", "posted_ts": 1, "image": "i"}
    with tempfile.TemporaryDirectory() as tmp:
        backup = Path(tmp) / "backup.json"
        shutil.copy2(twitter.SEED_PATH, backup)
        try:
            assert twitter.save_program_seed("genshin", "9.9", entry) is True
            assert twitter.program_seed("genshin", "9.9")["id"] == "9"
            assert twitter.save_program_seed("genshin", "9.9", entry) is False   # idempotent
        finally:
            shutil.copy2(backup, twitter.SEED_PATH)
            twitter._seeds = None
    assert twitter.program_seed("genshin", "9.9") == {}          # the seed file is back as it was


# =========================================================================== 1.3.0 (card cleanup + banner feed)
def test_no_x_button_and_no_key_art_or_source_line_on_the_schedule_card():
    """Card cleanup:
      * the 'x' button is gone (it only ever duplicated what's already in the card's title);
      * the '🖼️ key art: ...' footer line is gone;
      * the 'Source: ...' footer line is gone;
      * the legend remains: STC — Subject to Change • TBA — To be Announced."""
    s = settings()
    d = dict(SCHEDULE_SAMPLES["starrail"])
    d["source_url"] = "https://x.com/HonkaiStarRail/status/2099440781115211916"
    d["source_label"] = "X Post"
    d["media_from"] = "HoYoLAB"
    p = cards.schedule_payload(GAMES["starrail"], d, s, s.ping("schedule", "starrail"))
    flat = json.dumps(p, ensure_ascii=False)
    assert "https://x.com/HonkaiStarRail/status/" not in flat
    assert "🖼️" not in flat
    assert "Source:" not in flat
    assert "-# STC — Subject to Change • TBA — To be Announced" in flat


def test_a_non_x_source_still_gets_its_own_button():
    """Non-X sources (like HoYoLAB or the official news page) still get their own button when the
    title points elsewhere (e.g. YouTube stream), because they carry genuine extra information."""
    s = settings()
    d = dict(SCHEDULE_SAMPLES["starrail"])
    d["title_url"] = "https://www.youtube.com/watch?v=drFgtruoPe8"
    d["source_url"] = "https://www.hoyolab.com/article/46814308"
    d["source_label"] = "HoYoLAB"
    p = cards.schedule_payload(GAMES["starrail"], d, s, s.ping("schedule", "starrail"))
    btn_urls = [c["url"] for comp in p["components"][1]["components"] if comp["type"] == 1
                for c in comp.get("components", [])]
    assert "https://www.hoyolab.com/article/46814308" in btn_urls


def test_the_banner_feed_fills_the_lineup_no_official_post_ever_listed():
    """Banner feed (hub.json): fills empty 5★ phases at PRIORITY['bannerfeed'] = 5."""
    from gamexpress.sources import bannerfeed
    data = json.loads((FIX / "bannerfeed_hub_trimmed.json").read_text(encoding="utf-8"))
    feed = bannerfeed.parse_hub(data, now=1790452566)
    # HSR 4.6 (maint_end_ts: 1790564400)
    hsr_lineup = bannerfeed.banner_feed_for(feed["starrail"], 1790564400)
    assert set(hsr_lineup["phase1"]) == {"Evanescia", "Pearl"}
    assert hsr_lineup["phase2"] == ["Mortenax Blade"]

    # merge into HSR 4.6 card data
    prov: dict = {}
    record: dict = {"data": {"version": "4.6", "maint_end_ts": 1790564400}, "prov": prov}
    merged = schedule.merge(GAMES["starrail"], "4.6", [], record, {}, {}, 1790452566,
                            banner_feed=feed["starrail"])
    banners = merged.get("banners") or {}
    assert set(banners.get("phase1") or []) == {"Evanescia", "Pearl"}
    assert banners.get("phase2") == ["Mortenax Blade"]
    assert record["prov"]["b_phase1"][0] == 5
    assert record["prov"]["b_phase2"][0] == 5

    # Genshin 7.1 (maint_end_ts: 1790132400)
    gi_lineup = bannerfeed.banner_feed_for(feed["genshin"], 1790132400)
    assert set(gi_lineup["phase1"]) == {"Vodyanitsa", "Vesna"}
    assert "phase2" not in gi_lineup


def test_the_banner_feed_never_invents_a_lineup_for_the_wrong_version():
    """If the version has no release/maintenance timestamp, or one that doesn't match the feed,
    the banners stay empty / TBA."""
    from gamexpress.sources import bannerfeed
    data = json.loads((FIX / "bannerfeed_hub_trimmed.json").read_text(encoding="utf-8"))
    feed = bannerfeed.parse_hub(data, now=1790452566)
    lineup = bannerfeed.banner_feed_for(feed["starrail"], 1999999999)
    assert "phase1" not in lineup and "phase2" not in lineup   # titles may ride along

    record: dict = {"data": {"version": "9.9", "maint_end_ts": 1999999999}, "prov": {}}
    merged = schedule.merge(GAMES["starrail"], "9.9", [], record, {}, {}, 1790452566,
                            banner_feed=feed["starrail"])
    banners = merged.get("banners") or {}
    assert not banners.get("phase1") and not banners.get("phase2")


def test_a_stale_banner_feed_is_ignored_not_served():
    """A feed payload older than 14 days is refused rather than serving last month's lineup."""
    from gamexpress.sources import bannerfeed
    data = json.loads((FIX / "bannerfeed_hub_trimmed.json").read_text(encoding="utf-8"))
    stale = bannerfeed.parse_hub(data, now=1790452566 + 15 * 86400)
    assert stale == {}


def test_the_banner_feed_never_overrides_an_official_lineup():
    """PRIORITY['bannerfeed'] = 5 (lowest). An official post (priority 40/50) or override (100)
    beats the feed and is never overwritten."""
    from gamexpress.sources import bannerfeed
    data = json.loads((FIX / "bannerfeed_hub_trimmed.json").read_text(encoding="utf-8"))
    feed = bannerfeed.parse_hub(data, now=1790452566)
    prov = {"b_phase1": [50, 1790000000]}
    record = {"data": {"version": "4.6", "maint_end_ts": 1790564400, "banners": {"phase1": ["OfficialHero"]}},
              "prov": prov}
    merged = schedule.merge(GAMES["starrail"], "4.6", [], record, {}, {}, 1790452566,
                            banner_feed=feed["starrail"])
    assert merged["banners"]["phase1"] == ["OfficialHero"]


def test_banner_feed_can_be_switched_off():
    """BANNER_FEED=0 switches the fill-in off entirely."""
    s = settings(BANNER_FEED="0")
    assert s.banner_feed is False
    with tempfile.TemporaryDirectory() as tmp:
        sp = Path(tmp) / "state.json"
        ctx = make_ctx(sp, BANNER_FEED=0)
        assert ctx.settings.banner_feed is False


# =========================================================================== 1.5/1.6 (deleted cards + learned pre-install lead)
UNKNOWN_MESSAGE = '{"message": "Unknown Message", "code": 10008}'


class ScriptedWebhook:
    def __init__(self, edits: list[SendResult], sends: list[SendResult] | None = None):
        self.edit_results = list(edits)
        self.send_results = list(sends or [])
        self.edits: list[tuple[str, dict]] = []
        self.sends: list[dict] = []

    async def edit(self, webhook: str, message_id: str, payload: dict) -> SendResult:
        self.edits.append((message_id, payload))
        return self.edit_results.pop(0)

    async def send(self, webhook: str, payload: dict) -> SendResult:
        self.sends.append(payload)
        return self.send_results.pop(0)


# The real HSR 4.6 air time. At the now=1790450000 these tests use, that program aired six days
# earlier, so 4.6 is a SETTLED version -- exactly the case a live run must leave alone.
HSR_46_AIRED = 1789903800


def _posted_hsr_record(message_id: str = "dead-message",
                       program_ts: int = HSR_46_AIRED) -> dict:
    data = dict(SCHEDULE_SAMPLES["starrail"])
    data["program_ts"] = program_ts
    return {"status": "posted", "first_seen": 1790400000,
            "data": data, "prov": {},
            "message_id": message_id, "webhook_fp": webhook_fingerprint(HOOK),
            "payload_hash": "old-payload"}


def test_a_deleted_card_is_reposted_and_adopts_the_new_id():
    with tempfile.TemporaryDirectory() as tmp:
        ctx = make_ctx(Path(tmp) / "state.json", now=1790450000)
        ctx.webhook = ScriptedWebhook(
            [SendResult(False, 404, error=UNKNOWN_MESSAGE), SendResult(True, 200)],
            [SendResult(True, 200, message_id="replacement-message")])
        # program still inside the 36 h news window -> recovery must still repost
        records = {"4.6": _posted_hsr_record(program_ts=1790440000)}
        asyncio.run(schedule._handle_version(ctx, GAMES["starrail"], "4.6", [], records,
                                             {"compensation": "Stellar Jade ×301"}, {}, True))
        assert ctx.errors == [] and len(ctx.webhook.sends) == 1
        assert records["4.6"]["message_id"] == "replacement-message"
        assert any("10008" in line for line in ctx.report)

        # A later data change edits the adopted id; it does not PATCH the dead id forever or repost again.
        ctx.now += 600
        asyncio.run(schedule._handle_version(ctx, GAMES["starrail"], "4.6", [], records,
                                             {"compensation": "Stellar Jade ×302"}, {}, True))
        assert [message_id for message_id, _ in ctx.webhook.edits] == [
            "dead-message", "replacement-message"]
        assert len(ctx.webhook.sends) == 1 and ctx.errors == []


def test_a_deleted_card_whose_repost_fails_still_reports_an_error():
    with tempfile.TemporaryDirectory() as tmp:
        ctx = make_ctx(Path(tmp) / "state.json", now=1790450000)
        ctx.webhook = ScriptedWebhook(
            [SendResult(False, 404, error=UNKNOWN_MESSAGE)],
            [SendResult(False, 503, error="upstream unavailable")])
        records = {"4.6": _posted_hsr_record(program_ts=1790440000)}   # not settled yet
        asyncio.run(schedule._handle_version(ctx, GAMES["starrail"], "4.6", [], records,
                                             {"compensation": "Stellar Jade ×301"}, {}, True))
        assert len(ctx.webhook.sends) == 1 and len(ctx.errors) == 1
        assert "repost failed (503)" in ctx.errors[0] and "10008" in ctx.errors[0]
        assert records["4.6"]["message_id"] == "dead-message"   # retry recovery next run
        assert records["4.6"]["payload_hash"] == "old-payload"


def test_a_non_404_edit_failure_is_still_an_error_not_a_repost():
    with tempfile.TemporaryDirectory() as tmp:
        ctx = make_ctx(Path(tmp) / "state.json", now=1790450000)
        ctx.webhook = ScriptedWebhook([SendResult(False, 400, error="bad payload")])
        records = {"4.6": _posted_hsr_record()}
        asyncio.run(schedule._handle_version(ctx, GAMES["starrail"], "4.6", [], records,
                                             {"compensation": "Stellar Jade ×301"}, {}, True))
        assert ctx.webhook.sends == [] and ctx.errors == ["HSR 4.6: edit failed (400) bad payload"]
        assert records["4.6"]["message_id"] == "dead-message"


def test_preinstall_cold_start_reproduces_four_real_notices():
    cases = {
        "genshin": (1790114400, 1789959600),
        "starrail": (1790546400, 1790229600),
        "zzz": (1788904800, 1788753600),
        "wuwa": (1790712000, 1790560800),
    }
    for game_key, (maintenance, want) in cases.items():
        record = {"data": {"maint_start_ts": maintenance},
                  "prov": {"maint_start_ts": [schedule.PRIORITY["hoyolab"], maintenance]}}
        got = schedule.merge(GAMES[game_key], "test", [], record, {}, {}, maintenance - 86400)
        assert got["preinstall_ts"] == want, (game_key, got["preinstall_ts"], want)


def test_preinstall_fallback_never_overwrites_a_real_time():
    real = 1790200000
    data = {"maint_start_ts": 1790546400, "preinstall_ts": real}
    prov = {"maint_start_ts": [50, 1], "preinstall_ts": [50, 1]}
    assert schedule.derive_preinstall(GAMES["starrail"], data, prov, 2, lead_h=12) is None
    assert data["preinstall_ts"] == real and "estimated" not in data


def test_preinstall_fallback_is_labelled_estimated():
    data, prov = {"maint_start_ts": 1790546400}, {"maint_start_ts": [50, 1]}
    assert schedule.derive_preinstall(GAMES["starrail"], data, prov, 2) == 1790229600
    assert data["estimated"] == ["preinstall_ts"]
    assert data["estimate_sources"] == ["version cadence"]
    assert prov["preinstall_ts"][0] == schedule.PRIORITY["pattern"]


def test_a_real_preinstall_replaces_the_fallback():
    record = {"data": {"maint_start_ts": 1790546400},
              "prov": {"maint_start_ts": [50, 1]}}
    derived = schedule.merge(GAMES["starrail"], "4.6", [], record, {}, {}, 2)
    assert "preinstall_ts" in derived.get("estimated", [])
    record["data"] = derived
    real = schedule.merge(GAMES["starrail"], "4.6", [], record,
                          {"preinstall_ts": 1790229660}, {}, 3)
    assert real["preinstall_ts"] == 1790229660 and "preinstall_ts" not in real.get("estimated", [])
    assert record["prov"]["preinstall_ts"][0] == schedule.PRIORITY["override"]


def test_a_real_notice_teaches_the_game_its_own_lead_time():
    with tempfile.TemporaryDirectory() as tmp:
        ctx = make_ctx(Path(tmp) / "state.json", now=1789900000)
        item = Item("hoyolab", "genshin", "real-7.1", "https://www.hoyolab.com/article/real-7.1",
                    "Version 7.1 Update Details", "official notice", 1789900000)
        notice = schedule.Extract(item, "maintenance", "7.1", fields={
            "preinstall_ts": 1789959600, "maint_start_ts": 1790114400,
            "maint_end_ts": 1790132400})
        records: dict = {}
        asyncio.run(schedule._handle_version(ctx, GAMES["genshin"], "7.1", [notice], records,
                                             {}, {}, True))
        assert 42 <= records["7.1"]["preinstall_offset_h"] <= 44
        assert "preinstall_ts" not in (records["7.1"]["data"].get("estimated") or [])


def test_a_derived_preinstall_never_teaches_the_model():
    with tempfile.TemporaryDirectory() as tmp:
        ctx = make_ctx(Path(tmp) / "state.json", now=1790000000)
        item = Item("hoyolab", "starrail", "maint-4.7", "https://www.hoyolab.com/article/maint-4.7",
                    "Version 4.7 Update Details", "official notice", 1790000000)
        notice = schedule.Extract(item, "maintenance", "4.7", fields={
            "maint_start_ts": 1791000000, "maint_end_ts": 1791018000})
        records: dict = {}
        asyncio.run(schedule._handle_version(ctx, GAMES["starrail"], "4.7", [notice], records,
                                             {}, {}, True))
        record = records["4.7"]
        assert "preinstall_ts" in record["data"]["estimated"]
        assert "preinstall_offset_h" not in record


def test_observed_history_beats_the_shipped_default():
    records = {
        "4.4": {"preinstall_offset_h": 42},
        "4.5": {"preinstall_offset_h": 44},
        "bad-number": {"preinstall_offset_h": "not a number"},
        "bad-outlier": {"preinstall_offset_h": 700},
        "missing": {},
    }
    assert schedule.observed_lead_h(records) == 43                # even count -> average middle pair
    record = {"data": {"maint_start_ts": 2_000_000},
              "prov": {"maint_start_ts": [50, 1]}}
    got = schedule.merge(GAMES["starrail"], "4.6", [], record, {}, {}, 1,
                         lead_h=schedule.observed_lead_h(records))
    assert got["preinstall_ts"] == 2_000_000 - 43 * 3600         # not shipped HSR default (88 h)

    assert schedule.observed_lead_h({"x": {"preinstall_offset_h": "junk"}}) is None
    unknown = replace(GAMES["starrail"], key="unknown-game")
    data, prov = {"maint_start_ts": 2_000_000}, {"maint_start_ts": [50, 1]}
    assert schedule.derive_preinstall(unknown, data, prov, 1) is None
    assert "preinstall_ts" not in data


# --------------------------------------------------------------------- real notices, parser gaps
# Genshin 7.1 maintenance preview (HoYoLAB 46771203). The title never says "pre-install"; the body
# does, and HoYoverse publishes the post at the moment pre-installation opens.
GI_71_NOTICE = """Dear Travelers,

In order to provide a better gaming experience, the Genshin Impact team will be carrying out
Version 7.1 update maintenance, during which the game will be unavailable.

Update maintenance will begin on 2026-09-23 06:00 (UTC+8) and is estimated to take 5 hours.

At the same time, pre-installation for the Version 7.1 update is now available. Travelers on PC
and mobile devices can open the game and follow the prompts to start pre-installing the update.

Maintenance Compensation: Primogems ×300
"""

# ZZZ 3.2 update notice (HoYoLAB 46604333). Every number sits under a bracketed section header on
# the following line, and the window is spelled out in words instead of digits.
ZZZ_32_NOTICE = """Dear Proxies,

[Version Update Time]
2026-09-09 06:00 (UTC+8)
We estimate this will take five hours. Thank you for your patience.

[Pre-Download Period]
2026-09-07 12:00 (UTC+8) – 2026-09-09 06:00 (UTC+8)

[Pre-Installation Details]
Please make sure you have at least 32 GB of available storage space on your device.
"""


def test_genshin_preinstall_is_read_from_the_body_not_the_title():
    item = Item("hoyolab", "genshin", "46771203", "https://www.hoyolab.com/article/46771203",
                "Version 7.1 Update Maintenance Preview", GI_71_NOTICE, 1789960208)
    e = schedule.extract(GAMES["genshin"], item)
    assert e and e.kind == "maintenance" and e.version == "7.1"
    assert e.fields["maint_start_ts"] == 1790114400          # Wed 2026-09-23 06:00 (UTC+8)
    assert e.fields["maint_end_ts"] == 1790132400            # +5 h, == the banner feed's phase-1 start
    assert e.fields["preinstall_ts"] == 1789960208           # the post's own time: "is now available"


def test_zzz_labelled_sections_carry_the_times_the_sentence_scanner_dropped():
    item = Item("hoyolab", "zzz", "46604333", "https://www.hoyolab.com/article/46604333",
                "Version 3.2 Update Maintenance Notice", ZZZ_32_NOTICE, 1788700000)
    e = schedule.extract(GAMES["zzz"], item)
    assert e and e.kind == "maintenance" and e.version == "3.2"
    assert e.fields["maint_start_ts"] == 1788904800          # Wed 2026-09-09 06:00 (UTC+8)
    assert e.fields["maint_end_ts"] == 1788922800            # "take five hours" -> 11:00
    assert e.fields["preinstall_ts"] == 1788753600           # Mon 2026-09-07 12:00 (UTC+8)


def test_spelled_out_maintenance_duration_parses():
    assert find_duration_hours("We estimate this will take five hours.") == 5.0
    assert find_duration_hours("The maintenance is expected to take about three hours.") == 3.0
    assert find_duration_hours("is estimated to take 5 hours") == 5.0      # digits still win
    assert find_duration_hours("five hours of new story content await") is None


def test_the_storage_block_is_not_mistaken_for_a_preinstall_clock():
    text = ("[Pre-Download Period]\n"
            "Reserve at least 32 GB of storage space before 2026-09-01 00:00 (UTC+8).\n"
            "[Version Update Time]\n"
            "2026-09-09 06:00 (UTC+8)\n")
    f = schedule.extract_labelled(text, 1788700000)
    assert "preinstall_ts" not in f                            # a size line is not a schedule
    assert f["maint_start_ts"] == 1788904800


def test_the_title_links_the_announcement_not_the_youtube_stream():
    media = {
        "url": "https://x.com/honkaistarrail/status/2099440781115211916",
        "youtube": "https://www.youtube.com/watch?v=drFgtruoPe8",
        "source": "X Post",
    }
    data, prov = {}, {}
    schedule.apply_program_media(data, prov, media, 1790000000)
    assert data["title_url"] == "https://x.com/honkaistarrail/status/2099440781115211916"
    assert data["source_url"] == "https://x.com/honkaistarrail/status/2099440781115211916"
    assert data["youtube_video"] == "https://www.youtube.com/watch?v=drFgtruoPe8"


def test_an_official_announcement_replaces_a_countdown_estimate():
    data = {
        "program_ts": 1790341813,
        "estimated": ["program_ts"],
        "estimate_sources": ["hsr-countdown"],
    }
    prov = {"program_ts": [schedule.PRIORITY["countdown"], 1789000000]}
    media = {
        "url": "https://x.com/honkaistarrail/status/2099440781115211916",
        "program_ts": 1789903800,
    }
    changed = schedule.apply_program_media(data, prov, media, 1790000000)
    assert data["program_ts"] == 1789903800
    assert "program_ts" in changed
    assert "estimated" not in data
    assert "estimate_sources" not in data
    assert prov["program_ts"] == [schedule.PRIORITY["news"], 1790000000]

    data2 = {
        "program_ts": 1790341813,
        "preinstall_ts": 1790229600,
        "estimated": ["program_ts", "preinstall_ts"],
        "estimate_sources": ["hsr-countdown"],
    }
    prov2 = {"program_ts": [schedule.PRIORITY["countdown"], 1789000000]}
    schedule.apply_program_media(data2, prov2, media, 1790000000)
    assert data2["program_ts"] == 1789903800
    assert data2["estimated"] == ["preinstall_ts"]
    assert data2["estimate_sources"] == ["hsr-countdown"]


def test_a_real_official_air_time_is_never_replaced_by_media():
    data = {"program_ts": 1789903800}
    prov = {"program_ts": [schedule.PRIORITY["hoyolab"], 1789000000]}
    media = {
        "url": "https://x.com/honkaistarrail/status/2099440781115211916",
        "program_ts": 1789999999,
    }
    changed = schedule.apply_program_media(data, prov, media, 1790000000)
    assert data["program_ts"] == 1789903800
    assert "program_ts" not in changed
    assert prov["program_ts"] == [schedule.PRIORITY["hoyolab"], 1789000000]


def test_the_footer_puts_each_note_on_its_own_small_text_line():
    d = {
        "version": "4.6",
        "estimated": ["program_ts"],
        "estimate_sources": ["hsr-countdown"],
    }
    p = cards.schedule_payload(GAMES["starrail"], d, settings(show_legend=True), cards.Ping(), None)
    flat = json.dumps(p, ensure_ascii=False)
    assert "• 🕒" not in flat
    box = p["components"][-1]
    foot_lines = [c["content"] for c in box["components"] if c["type"] == 10 and c["content"].startswith("-# ")]
    assert len(foot_lines) == 2
    assert foot_lines[0] == "-# STC — Subject to Change • TBA — To be Announced"
    assert foot_lines[1] == "-# 🕒 program time estimated from hsr-countdown — the official notice replaces it automatically"


def test_a_version_whose_air_time_is_only_an_estimate_is_looked_up_again():
    now = 1790000000
    # Gate reopens while air time is estimated
    rec_est = {"data": {"media_from": "X", "estimated": ["program_ts"]}}
    assert schedule.needs_program_lookup([], rec_est, now) is True

    rec_seen_est = {"data": {"program_seen": True, "estimated": ["program_ts"]}}
    assert schedule.needs_program_lookup([], rec_seen_est, now) is True

    # Gate closes once settled (not in estimated)
    rec_settled = {"data": {"media_from": "X"}}
    assert schedule.needs_program_lookup([], rec_settled, now) is False

    rec_seen_settled = {"data": {"program_seen": True}}
    assert schedule.needs_program_lookup([], rec_seen_settled, now) is False

    # Still respects the maintenance cutoff (+12 h)
    rec_cutoff = {
        "data": {
            "media_from": "X",
            "estimated": ["program_ts"],
            "maint_start_ts": now - 13 * 3600,
        }
    }
    assert schedule.needs_program_lookup([], rec_cutoff, now) is False


def main() -> int:
    tests = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_") and callable(f)]
    failed = 0
    for name, fn in tests:
        try:
            fn()
            print(f"  PASS  {name}")
        except Exception:
            failed += 1
            print(f"  FAIL  {name}")
            traceback.print_exc()
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    return 1 if failed else 0


# =========================================================================== settled programs
# HSR 4.6's special program aired 2026-09-20; the version itself went live 2026-09-28. A live run
# must stop announcing it, while a test run must keep rendering it so the fetch stays observable.
def test_a_settled_program_is_never_resurrected_on_a_live_run():
    with tempfile.TemporaryDirectory() as tmp:
        ctx = make_ctx(Path(tmp) / "state.json", now=1790450000)
        ctx.webhook = ScriptedWebhook([SendResult(False, 404, error=UNKNOWN_MESSAGE)],
                                      [SendResult(True, 200, message_id="should-not-happen")])
        records = {"4.6": _posted_hsr_record()}                 # air time 6 days ago
        assert schedule.program_settled(records["4.6"]["data"], ctx.now)
        asyncio.run(schedule._handle_version(ctx, GAMES["starrail"], "4.6", [], records,
                                             {"compensation": "Stellar Jade ×301"}, {}, True))
        assert ctx.webhook.sends == [] and ctx.errors == []      # nothing reappears in the channel
        assert records["4.6"].get("message_id") is None          # dead id dropped, no retry loop
        assert records["4.6"]["card_retired"] == ctx.now
        assert any("program already aired" in line for line in ctx.report)

        # and it stays gone: the later data change adds no PATCH and no POST (the single edit
        # above is the one that 404'd and triggered the retirement)
        ctx.now += 600
        asyncio.run(schedule._handle_version(ctx, GAMES["starrail"], "4.6", [], records,
                                             {"compensation": "Stellar Jade ×302"}, {}, True))
        assert ctx.webhook.sends == [] and len(ctx.webhook.edits) == 1 and ctx.errors == []


def test_a_test_run_still_reposts_a_settled_version():
    """The whole point of a test run is to see the real card, however old the program is."""
    with tempfile.TemporaryDirectory() as tmp:
        ctx = make_ctx(Path(tmp) / "state.json", now=1790450000, TEST_MODE="1")
        ctx.webhook = ScriptedWebhook([SendResult(False, 404, error=UNKNOWN_MESSAGE)],
                                      [SendResult(True, 200, message_id="test-card")])
        records = {"4.6": _posted_hsr_record()}
        assert schedule.program_settled(records["4.6"]["data"], ctx.now)
        asyncio.run(schedule._handle_version(ctx, GAMES["starrail"], "4.6", [], records,
                                             {"compensation": "Stellar Jade ×301"}, {}, True))
        assert len(ctx.webhook.sends) == 1 and ctx.errors == []
        assert records["4.6"]["message_id"] == "test-card"
        assert "card_retired" not in records["4.6"]


def test_a_settled_program_does_not_freeze_the_card_that_is_already_posted():
    """Settled program != finished version: HSR 4.6's banners and maintenance landed AFTER the
    stream, so in-place edits must keep flowing. Only NEW messages are suppressed."""
    with tempfile.TemporaryDirectory() as tmp:
        ctx = make_ctx(Path(tmp) / "state.json", now=1790450000)
        ctx.webhook = ScriptedWebhook([SendResult(True, 200)])
        records = {"4.6": _posted_hsr_record()}
        assert schedule.program_settled(records["4.6"]["data"], ctx.now)
        asyncio.run(schedule._handle_version(ctx, GAMES["starrail"], "4.6", [], records,
                                             {"compensation": "Stellar Jade ×301"}, {}, True))
        assert len(ctx.webhook.edits) == 1 and ctx.webhook.sends == []
        assert any("schedule card updated" in line for line in ctx.report)
        assert records["4.6"]["message_id"] == "dead-message"


def test_a_settled_version_is_never_announced_anew_on_a_live_run():
    with tempfile.TemporaryDirectory() as tmp:
        ctx = make_ctx(Path(tmp) / "state.json", now=1790450000)
        records = {"4.6": {"status": "new", "first_seen": ctx.now,
                           "data": dict(SCHEDULE_SAMPLES["starrail"]), "prov": {}}}
        asyncio.run(schedule._handle_version(ctx, GAMES["starrail"], "4.6", [], records,
                                             {}, {}, False))          # not bootstrapped
        assert ctx.webhook.sent == [] and records["4.6"]["status"] == "tracked"
        assert any("nothing to announce" in line for line in ctx.report)

        # the same version on a test run IS rendered, from an empty state
        ctx2 = make_ctx(Path(tmp) / "s2.json", now=1790450000, TEST_MODE="1")
        records2 = {"4.6": {"status": "new", "first_seen": ctx2.now,
                            "data": dict(SCHEDULE_SAMPLES["starrail"]), "prov": {}}}
        asyncio.run(schedule._handle_version(ctx2, GAMES["starrail"], "4.6", [], records2,
                                             {}, {}, True))
        assert len(ctx2.webhook.sent) == 1


def test_program_settled_shares_the_window_with_the_announce_decision():
    now = 1790450000
    assert schedule.program_settled({"program_ts": now - int(36 * 3600) - 1}, now) is True
    assert schedule.program_settled({"program_ts": now - int(36 * 3600) + 60}, now) is False
    assert schedule.program_settled({"program_ts": now + 86400}, now) is False   # not aired yet
    assert schedule.program_settled({}, now) is False                            # air time unknown


# =========================================================================== banner accuracy
# Verbatim body of HoYoLAB post 46851682, "Version 4.6 Event Warp: Phase I" (created_at
# 1790488804), fetched 2026-09-27 from
#   bbs-api-os.hoyolab.com/community/post/wapi/getPostFull?post_id=46851682
# This is the post that produced the wrong live card, and it must be the WHOLE body: the
# first two paragraphs alone read correctly, and an earlier fixture stopped there -- which is
# exactly why the two banner TITLES that leak out of the "※ Event Warp Details" section
# ("Celestial Invitation", "An Ocean in a Pearl") survived into production. With them present
# the reader has to prove it ignores a banner name in every clause of the notice.
HSR_46_WARP_PHASE1 = """\
Hello, Trailblazers!
The drop rates for the limited 5-star character Pearl (Elation: Ice) and the limited 5-star Light Cone "Colors for Tomorrow (Elation)" will be boosted for a limited time. The drop rates for the 4-star characters Qingque (Erudition: Quantum), Xueyi (Destruction: Quantum), and Misha (Destruction: Ice), as well as the 4-star Light Cones "Post-Op Conversation (Abundance)," "Planetary Rendezvous (Harmony)," and "Boundless Choreo (Nihility)" will be boosted for a limited time. The Warp period is from after the Version 4.6 update on 2026-09-28 – 2026-11-10 15:00 (server time).
The limited 5-star character Evanescia (Elation: Physical) and the limited 5-star Light Cone "Until the Flowers Bloom Again (Elation)" will return. The Warp period is from after the Version 4.6 update on 2026-09-28 – 2026-10-21 11:59 (server time).

▌"An Ocean in a Pearl" and "Brilliant Fixation: Colors for Tomorrow" Event Warps
● During the "An Ocean in a Pearl" Character Event Warp, the drop rates of the limited 5-star character Pearl (Elation: Ice) and 4-star characters Qingque (Erudition: Quantum), Xueyi (Destruction: Quantum), and Misha (Destruction: Ice) will be boosted for a limited time.
● During the "Brilliant Fixation: Colors for Tomorrow" Light Cone Event Warp, the drop rates of the limited 5-star Light Cone "Colors for Tomorrow (Elation)" and the 4-star Light Cones "Post-Op Conversation (Abundance)," "Planetary Rendezvous (Harmony)," and "Boundless Choreo (Nihility)" will be boosted for a limited time.

▌"The Demoiselle in Charge" and "Bygone Reminiscence: Until the Flowers Bloom Again" Event Warps
● During "The Demoiselle in Charge" Character Event Warp, the drop rates of the limited 5-star character Evanescia (Elation: Physical) and 4-star characters Qingque (Erudition: Quantum), Xueyi (Destruction: Quantum), and Misha (Destruction: Ice) will be boosted for a limited time.
● During the "Bygone Reminiscence: Until the Flowers Bloom Again" Light Cone Event Warp, the drop rates of the limited 5-star Light Cone "Until the Flowers Bloom Again (Elation)" and the 4-star Light Cones "Post-Op Conversation (Abundance)," "Planetary Rendezvous (Harmony)," and "Boundless Choreo (Nihility)" will be boosted for a limited time.

▌ Event Warp Details
※ Among the above characters and Light Cones, limited characters and limited Light Cones will not be available in the Stellar Warp event.
※ In this phase of Warp, obtainable 5-star characters include the featured 5-star characters and the custom-selected characters from "Celestial Invitation."
※ During the Event Warp period, the limited 5-star character Pearl (Elation: Ice) can only be obtained from the "An Ocean in a Pearl" Character Event Warp, and the limited 5-star character Evanescia (Elation: Physical) can only be obtained from the "The Demoiselle in Charge" Character Event Warp.
※ During the Event Warp period, the limited 5-star Light Cone "Colors for Tomorrow (Elation)" can only be obtained from the "Brilliant Fixation: Colors for Tomorrow" Light Cone Event Warp, and the limited 5-star Light Cone "Until the Flowers Bloom Again (Elation)" can only be obtained from the "Bygone Reminiscence: Until the Flowers Bloom Again" Light Cone Event Warp.
※ "An Ocean in a Pearl" and "The Demoiselle in Charge" are Character Event Warps that share the same guaranteed drop counter. The cumulative Warp count for a guaranteed 5-star character in any Character Event Warp will always be carried over to other Character Event Warps, but is independent of and unaffected by other types of Warps.
※ "Brilliant Fixation: Colors for Tomorrow" and "Bygone Reminiscence: Until the Flowers Bloom Again" are considered Light Cone Event Warps, and share the same guaranteed drop counter. The cumulative Warp count for a guaranteed 5-star Light Cone in any Light Cone Event Warp will always be carried over to other Light Cone Event Warps, but is independent of and unaffected by other types of Warps.
※ For more information, please head to the Warp screen.

▌ "Aptitude Showcase" Character Trial Event
● Requirement: Unlock Travel Log
Event Details: After the Version 4.6 update on 2026-09-28 – 2026-11-10 15:00 (server time), you can experience the trial stages for characters Pearl (Elation: Ice), Qingque (Erudition: Quantum), Xueyi (Destruction: Quantum), and Misha (Destruction: Ice). After the Version 4.6 update on 2026-09-28 – 2026-10-21 11:59 (server time), you can experience the trial stage for the character Evanescia (Elation: Physical). Completing the challenges awards Stellar Jades, Adventure Logs, Universal Enhancement Materials, and Credits.
"""
HSR_46_NOT_CHARACTERS = {
    "Celestial Invitation", "An Ocean in a Pearl", "The Demoiselle in Charge",   # banner titles
    "Post-Op Conversation", "Planetary Rendezvous", "Boundless Choreo",          # 4* light cones
    "Colors for Tomorrow", "Until the Flowers Bloom Again",                      # 5* light cones
}


def test_the_real_warp_notice_yields_characters_not_light_cones():
    item = Item("hoyolab", "starrail", "46851682", "https://www.hoyolab.com/article/46851682",
                "Version 4.6 Event Warp: Phase I", HSR_46_WARP_PHASE1, 1790488804)
    b = schedule.extract_banner(item)
    assert b["banner_five"] == ["Pearl", "Evanescia"]
    assert b["banner_four"] == ["Qingque", "Xueyi", "Misha"]
    assert b["banner_four_unsure"] is False and b["banner_phase"] == 1
    leaked = (set(b["banner_five"]) | set(b["banner_four"])) & HSR_46_NOT_CHARACTERS
    assert not leaked, leaked


def test_re_reading_the_same_post_heals_a_wrong_four_star_list():
    """phase1_4 held three LIGHT CONES, written into the state by post 46851682 itself. The
    corrected reader re-reads THAT VERY POST, so _four_star_problem() must not treat the stored
    list as a second official source disagreeing -- doing so latches the wrong list into a
    permanent TBA (the flag is sticky) and the 4-stars never come back."""
    item = Item("hoyolab", "starrail", "46851682", "https://www.hoyolab.com/article/46851682",
                "Version 4.6 Event Warp: Phase I", HSR_46_WARP_PHASE1, 1790488804)
    ex = schedule.extract(GAMES["starrail"], item)
    record = {"data": {"version": "4.6", "banners": {
                  "phase1": ["Celestial Invitation", "An Ocean in a Pearl"],
                  "phase1_4": ["Post-Op Conversation", "Planetary Rendezvous", "Boundless Choreo"]}},
              "prov": {"b_phase1": [50, 1790488804], "b_phase1_4": [50, 1790488804]}}
    for i in (1, 2):                                    # and it stays healed on every later run
        data = schedule.merge(GAMES["starrail"], "4.6", [ex], record, {}, {}, 1790510400 + i * 600)
        record["data"] = data
        assert data["banners"]["phase1"] == ["Pearl", "Evanescia"]
        assert data["banners"]["phase1_4"] == ["Qingque", "Xueyi", "Misha"]
        assert "b_phase1_4_tba" not in record["prov"]


def test_two_different_posts_that_disagree_still_fall_back_to_tba():
    """The re-read exemption is narrow: a DIFFERENT post contradicting the stored 4-star list is
    still a real disagreement and must still show TBA."""
    item = Item("hoyolab", "starrail", "46851682", "u", "Version 4.6 Event Warp: Phase I",
                HSR_46_WARP_PHASE1, 1790488804)
    ex = schedule.extract(GAMES["starrail"], item)
    record = {"data": {"version": "4.6",
                       "banners": {"phase1_4": ["Hanya", "Sampo", "Natasha"]}},
              "prov": {"b_phase1_4": [50, 1790400000]}}   # an EARLIER, different post
    data = schedule.merge(GAMES["starrail"], "4.6", [ex], record, {}, {}, 1790510400)
    assert data["banners"]["phase1_4"] == []
    assert record["prov"]["b_phase1_4_tba"] == "official sources disagree"


def test_a_quoted_character_notice_still_reads_the_quotes():
    """The other official style quotes its characters. Both must work."""
    text = ('Event Wish "Ballad" Phase II: the event-exclusive 5-star character "Vodyanitsa (Hydro)" '
            'and the 4-star characters "Bennett (Pyro)", "Xingqiu (Hydro)" and "Sucrose (Anemo)" '
            'will get a huge drop-rate boost!')
    b = schedule.extract_banner(Item("hoyolab", "genshin", "1", "u", "Event Wish", text, 1))
    assert b["banner_five"] == ["Vodyanitsa"]
    assert b["banner_four"] == ["Bennett", "Xingqiu", "Sucrose"]


def test_a_dangling_article_is_never_read_as_a_character_name():
    b = schedule.bare_names(' "Vodyanitsa (Hydro)" and the ')
    assert "the" not in b and "The" not in b


def test_a_prose_tail_is_never_read_as_a_character_name():
    """A bare run is raw prose. When the sentence ends with a clause TIER_STOP does not know,
    the leftover must not be posted as a character -- the quoted-only reader posted NOTHING
    here, so absorbing the tail would be a new way to be wrong."""
    for tail in (" Pearl debuts soon.", " Pearl is here", " Pearl arrives in the new update"):
        assert schedule.bare_names(tail) == [], tail
    item = Item("hoyolab", "starrail", "2", "u", "Warp",
                "The limited 5-star character Pearl debuts soon.", 1)
    assert "Pearl debuts soon" not in (schedule.extract_banner(item).get("banner_five") or [])
    # ...while real multi-word names, which look like prose to a word counter, still pass.
    assert schedule.bare_names(" Dan Heng • Imbibitor Lunae, Topaz & Numby, and March 7th ") == [
        "Dan Heng • Imbibitor Lunae", "Topaz & Numby", "March 7th"]


def test_the_banner_feed_replaces_a_phase_that_holds_a_banner_title():
    """The hub is the only source that separates a banner's NAME from its featured character."""
    data = {"banners": {"phase1": ["An Ocean in a Pearl", "The Demoiselle in Charge"]}}
    prov = {"b_phase1": [50, 1790488804]}          # hoyolab -- higher priority than the feed
    schedule.apply_banner_feed(data, prov,
                               {"phase1": ["Evanescia", "Pearl"],
                                "titles": ["An Ocean in a Pearl", "The Demoiselle in Charge",
                                           "Now I Am Become Blade"]}, 1790500000)
    assert data["banners"]["phase1"] == ["Evanescia", "Pearl"]
    assert prov["b_phase1"][0] == 5                # now attributed to the feed


def test_the_banner_feed_still_never_overwrites_real_characters():
    data = {"banners": {"phase1": ["Evanescia", "Pearl"]}}
    prov = {"b_phase1": [50, 1790488804]}
    schedule.apply_banner_feed(data, prov,
                               {"phase1": ["Evanescia", "Pearl"], "titles": ["An Ocean in a Pearl"]},
                               1790500000)
    assert data["banners"]["phase1"] == ["Evanescia", "Pearl"]
    assert prov["b_phase1"][0] == 50               # untouched


# =========================================================================== nitter fleet
def test_the_nitter_fleet_leads_with_nitter_cf_and_demotes_the_flaky_mirror():
    """nitter.cf / xitter.cf lead. Nothing is deleted: x.n0g.xyz answered HTTP 404 then 429 on
    every handle in runs 36296323488 / 36298632006 / 36299586254, so it is demoted to dead last
    and kept as a backup rather than removed."""
    from gamexpress.config import DEFAULT_NITTER
    from gamexpress.sources.twitter import NITTER_BATCH
    assert DEFAULT_NITTER[0] == "https://nitter.cf"
    assert DEFAULT_NITTER[1] == "https://xitter.cf"
    assert len(DEFAULT_NITTER) == len(set(DEFAULT_NITTER))

    idx = DEFAULT_NITTER.index("https://x.n0g.xyz")
    assert idx >= NITTER_BATCH, "a mirror that answers nothing must never sit in the hot path"
    assert idx == len(DEFAULT_NITTER) - 1, "demoted means dead last"
    for inst in ("https://nitter.cf", "https://xitter.cf", "https://nitter.miningtcup.me",
                 "https://nitter.jaydenha.uk", "https://shitter.thepixora.com"):
        assert DEFAULT_NITTER.index(inst) < idx, inst


def test_the_token_gated_instance_is_in_the_fleet():
    from gamexpress.config import DEFAULT_NITTER
    from gamexpress.sources.twitter import TOKEN_GATED
    for inst in TOKEN_GATED:
        assert inst in DEFAULT_NITTER, inst


# =========================================================================== nitter hot path
# twitter.py probes NITTER_BATCH instances in parallel on EVERY run, for EVERY handle, whether
# or not the ones ahead of them answered. A mirror in that first batch is therefore a cost on
# every run -- which is why x.n0g.xyz was demoted out of it. These are the instances measured
# as unable to answer GitHub's runners, each with the run that proved it; none of them may sit
# in the hot path again, whatever a public uptime table claims. They all stay in the fleet.
NITTER_CANNOT_ANSWER = {
    "https://nitter.netbub.com": "HTTP 403 on all 4 handles (live run 36305123457)",
    "https://nitter.meowing.monster": "HTTP 200 but 0 entries, bot check (live run 36305123457)",
    "https://xcancel.com": "suspended 2026-09-14",
    "https://x.yuuki.sh": "HTTP 403 to GitHub runners (2026-09-25)",
    "https://x.n0g.xyz": "404 then 429 in runs 36296323488 / 36298632006 / 36299586254",
}


def test_the_first_nitter_batch_holds_only_instances_that_answer():
    from gamexpress.config import DEFAULT_NITTER
    from gamexpress.sources.twitter import NITTER_BATCH
    hot = DEFAULT_NITTER[:NITTER_BATCH]
    for inst, why in NITTER_CANNOT_ANSWER.items():
        assert inst not in hot, f"{inst} is probed on every run but {why}"
    assert hot[0] == "https://nitter.cf" and hot[1] == "https://xitter.cf"


def test_a_demoted_instance_is_kept_as_a_fallback_rather_than_deleted():
    """Demoting is cheap and reversible; deleting throws away a mirror that may work from a VPS.
    Nothing in the fleet is removed -- a mirror that stopped answering is pushed down instead."""
    from gamexpress.config import DEFAULT_NITTER
    for inst in ("https://nitter.netbub.com", "https://nitter.meowing.monster",
                 "https://x.n0g.xyz"):
        assert inst in DEFAULT_NITTER, inst
    assert len(DEFAULT_NITTER) == len(set(DEFAULT_NITTER))


def test_a_demoted_tail_mirror_costs_no_request_while_the_fleet_answers():
    """The backup at the end of the fleet is free until it is needed: XClient.timeline() breaks
    out of its batch loop the moment TWO instances have answered, so a demoted mirror behind
    that point is never even requested -- and is a real backup again once the fleet degrades."""
    from gamexpress.sources.twitter import XClient
    calls = []

    class F:
        async def get_text(self, url, **k):
            calls.append(url)
            if "n0g" in url:
                return None                        # the 404/429 the live runs recorded
            if "nitter.cf" in url or "xitter.cf" in url:
                return RSS.format(id="3333333333")
            return None

    fleet = ["https://nitter.cf", "https://xitter.cf", "https://nitter.miningtcup.me",
             "https://nitter.jaydenha.uk", "https://x.n0g.xyz"]
    x = XClient(F(), settings(NITTER_INSTANCES=",".join(fleet)))
    tl = asyncio.run(x.timeline("Wuthering_Waves"))
    assert {e["id"] for e in tl} == {"3333333333"}
    assert not [u for u in calls if "n0g" in u], calls



def test_the_notice_carries_phase_one_so_the_hub_cross_check_stays_quiet():
    """Live HSR 4.6 held `prov.b_phase1 = [5, ...]` -- the community banner feed, the LOWEST
    priority in the bot -- and the log said "banner phase1 held a banner TITLE, not a character
    -- replaced from the feed" on every single run. The notice itself was the source of those
    titles. Read correctly, phase1 belongs to the notice at priority 50, in the notice's own
    order (Pearl is the new 5-star, Evanescia the rerun), and the cross-check has nothing left to
    replace -- so the card no longer depends on hub.json being up to date."""
    item = Item("hoyolab", "starrail", "46851682", "https://www.hoyolab.com/article/46851682",
                "Version 4.6 Event Warp: Phase I", HSR_46_WARP_PHASE1, 1790488804)
    ex = schedule.extract(GAMES["starrail"], item)
    record = {"data": {"version": "4.6", "banners": {"phase1": ["Evanescia", "Pearl"]}},
              "prov": {"b_phase1": [5, 1790504763]}}      # exactly what live state holds
    data = schedule.merge(GAMES["starrail"], "4.6", [ex], record, {}, {}, 1790510400)
    assert data["banners"]["phase1"] == ["Pearl", "Evanescia"]     # the notice's own order
    assert record["prov"]["b_phase1"][0] == 50                     # official notice, not the feed

    # With the notice carrying it, a feed that knows every banner TITLE has nothing to replace.
    prov = dict(record["prov"])
    schedule.apply_banner_feed(
        data, prov,
        {"phase1": ["Evanescia", "Pearl"],
         "titles": ["An Ocean in a Pearl", "The Demoiselle in Charge", "Celestial Invitation"]},
        1790510400)
    assert data["banners"]["phase1"] == ["Pearl", "Evanescia"]
    assert prov["b_phase1"][0] == 50


def test_a_quoted_name_after_prose_is_a_banner_not_a_character():
    """The two clauses that broke HSR 4.6 phase1, isolated: a quoted span is only a character
    when a NAME can sit between the star-tier phrase and the quote."""
    text = ('The drop rates for the limited 5-star character Pearl (Elation: Ice) will be '
            'boosted for a limited time. In this phase of Warp, obtainable 5-star characters '
            'include the featured 5-star characters and the custom-selected characters from '
            '"Celestial Invitation." The limited 5-star character Evanescia (Elation: Physical) '
            'can only be obtained from the "The Demoiselle in Charge" Character Event Warp.')
    b = schedule.extract_banner(Item("hoyolab", "starrail", "1", "u",
                                     "Version 4.6 Event Warp: Phase I", text, 1790488804))
    # the name that FOLLOWS the tier phrase is a character; the two quoted spans that sit behind
    # prose are banner names, and must not be read as 5-stars
    assert b["banner_five"] == ["Pearl"], b


def test_a_live_run_pings_even_with_a_stale_no_ping_variable():
    """monitor.yml sets NO_PING for EVERY step, so the live branch has to emit a value that is
    not blank. config._merge_json_blobs() only fills keys whose env value is empty, so
    `NO_PING=''` leaves a hole: the day a NO_PING repo variable is added it arrives in
    GE_VARS_JSON, re-fills the blank, and settings.ping() short-circuits again -- PING_SCHEDULE
    back to dead weight. No such variable exists today (the 2026-09-27 run logs show
    GE_VARS_JSON = {AUTO_MERGE_DEPENDABOT, PING_SCHEDULE}), so this is a guard, not a fix."""
    role = "1296268365593186426"
    stale = '{"NO_PING": "1", "PING_SCHEDULE": "'+ role + '"}'

    live = settings(NO_PING="0", GE_VARS_JSON=stale)          # what a cron/live run now sends
    assert live.no_ping is False
    assert live.ping("schedule", "starrail").roles == [role]

    blank = settings(NO_PING="", GE_VARS_JSON=stale)          # the bug '0' exists to avoid
    assert blank.no_ping is True
    assert not blank.ping("schedule", "starrail")

    test_run = settings(NO_PING="1", PING_SCHEDULE=role)      # ⑥ off -> a test card never pings
    assert not test_run.ping("schedule", "starrail")

if __name__ == "__main__":
    sys.exit(main())
