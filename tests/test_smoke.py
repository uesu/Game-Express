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
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
FIX = ROOT / "tests" / "fixtures"
GOLDEN = FIX / "golden"

from gamexpress import cards, codeposter, schedule  # noqa: E402
from gamexpress.config import load_games, load_overrides, load_settings, parse_emoji, parse_ping  # noqa: E402
from gamexpress.discord import WebhookClient, _split, webhook_fingerprint  # noqa: E402
from gamexpress.models import CodeHit, Item  # noqa: E402
from gamexpress.runner import Ctx, failover_check  # noqa: E402
from gamexpress.samples import CODE_SAMPLES, SCHEDULE_SAMPLES  # noqa: E402
from gamexpress.sources import codes as csrc  # noqa: E402
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
    for line in ("## [Honkai: Star Rail Version 4.6 Special Program](https://www.youtube.com/watch?v=drFgtruoPe8)",
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
            assert g.youtube and g.twitch and g.x_accounts and g.codes.get("sources"), g.key
        cards.program_title(g, {"version": "1.0"})
        cards.header_line(g, {"version": "1.0"})
    assert not GAMES["hna"].enabled and GAMES["hna"].hoyolab_gid == 9
    assert not GAMES["ananta"].enabled and not GAMES["ananta"].card.show_banners
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


# =========================================================================== bot (offline)
def test_bot_registers_commands_and_replies_v2():
    try:
        import discord
        from discord import app_commands
    except ImportError:
        print("    (discord.py not installed — skipped)")
        return
    import gc
    captured = {}
    original_run = discord.Client.run
    discord.Client.run = lambda self, token, **kw: captured.update(client=self, token=token)
    os.environ["DISCORD_BOT_TOKEN"] = "fake.token.value"
    try:
        from gamexpress import bot
        assert bot.run_bot() == 0
    finally:
        discord.Client.run = original_run
        os.environ.pop("DISCORD_BOT_TOKEN", None)
    client = captured["client"]
    tree = next(o for o in gc.get_objects() if isinstance(o, app_commands.CommandTree) and o.client is client)
    cmds = {c.name: c for c in tree.get_commands()}
    assert sorted(cmds) == ["codes", "schedule", "status"]
    sent = []

    async def fake_request(route, **kw):
        sent.append((route.path, kw.get("json")))
    client.http.request = fake_request

    class FakeInteraction:
        id = 1234
        token = "itok"
    asyncio.run(cmds["codes"].callback(FakeInteraction(), app_commands.Choice(name="Genshin Impact", value="genshin")))
    path, body = sent[-1]
    assert path.endswith("/callback") and body["type"] == 4
    assert body["data"]["flags"] == cards.IS_COMPONENTS_V2 and body["data"]["allowed_mentions"] == {"parse": []}
    assert body["data"]["components"][0]["type"] == 17



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
    from gamexpress.config import active_games
    keys = lambda s, now=None: [g.key for g in active_games(GAMES, s, now)]  # noqa: E731
    assert keys(settings(), now=1790000000) == ["genshin", "starrail", "zzz", "wuwa"]
    assert "hna" in keys(settings(ENABLE_GAMES="hna"), now=1790000000)
    jan15 = 1800000000                                                          # 2027-01-15 08:00 UTC
    assert "ananta" in keys(settings(), now=jan15) and "ananta" not in keys(settings(), now=jan15 - 86400)
    assert keys(settings(GAMES="ananta"), now=1790000000) == ["ananta"]        # explicit test of a prepared game


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


def test_four_star_tba_when_unsure():
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
    test = yaml.safe_load((wf / "test.yml").read_text(encoding="utf-8"))
    opts = (test.get("on") or test.get(True))["workflow_dispatch"]["inputs"]["test"]["options"]
    assert {"webhooks", "sample-cards", "live-dry-run", "live-test-channel", "offline-tests", "full"} <= set(opts)
    assert test["permissions"] == {"contents": "read"}                           # the test bench never commits
    for name in ("monitor.yml", "test.yml", "ci.yml"):
        text = (wf / name).read_text(encoding="utf-8")
        assert "actions/checkout@v7" in text and "actions/setup-python@v7" in text, name
    am = (wf / "dependabot_auto_merge.yml").read_text(encoding="utf-8")
    assert "vars.AUTO_MERGE_DEPENDABOT == 'yes'" in am and "actions/checkout" not in am


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


# =========================================================================== runner
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


if __name__ == "__main__":
    sys.exit(main())
