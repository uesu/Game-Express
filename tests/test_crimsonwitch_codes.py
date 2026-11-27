"""Crimson Witch (crimsonwitch.com) as a redemption-code witness — parser + wiring.

The pages were probed live on 2026-11-27 (docs/RESEARCH_NEW_GAMES.md): `/codes/<Game>` is a
Next.js App Router page, so the client component's props arrive in the RSC stream as
`self.__next_f.push([1, "…"])` chunks, and the decoded text carries a structured
`initialCodes` array — code, added, expires, rewards[{item, qty}], region_locked. No JavaScript is
needed to read it, and the payload is the data: the page's CSS-module class names and navigation
are rebuild noise and are never matched here.

Fixtures are trimmed real payloads (`tests/fixtures/crimsonwitch_*_trimmed.html`): the same
`self.__next_f.push` wrapper and the same escaped JSON, with a handful of entries kept.

Run:  python tests/test_crimsonwitch_codes.py     (pytest collects it too)
No network, no secrets.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from gamexpress.config import load_games  # noqa: E402
from gamexpress.sources import codes as csrc  # noqa: E402

FIX = ROOT / "tests" / "fixtures"
NOW = 1795882000.0  # just after "ArchonsAnswers" (1795881659) expires in the fixture


def _page(payload: list) -> str:
    """A minimal Next.js page carrying `initialCodes`, escaped exactly like the real stream."""
    fragment = '17:["$","$L22",null,{"initialCodes":' + json.dumps(payload, separators=(",", ":")) + "}"
    return ('<!DOCTYPE html><html><body><script>self.__next_f.push([1,'
            + json.dumps(fragment) + "])</script></body></html>")


def test_the_trimmed_fixtures_are_the_real_stream_shape():
    for name in ("crimsonwitch_genshin_trimmed.html", "crimsonwitch_zzz_trimmed.html"):
        text = (FIX / name).read_text(encoding="utf-8")
        assert "self.__next_f.push([1," in text and "initialCodes" in text, name
        assert csrc._rsc_text(text), name          # the RSC strings decode


def test_genshin_codes_rewards_and_expiry_are_read_from_the_payload():
    hits = csrc.parse_crimsonwitch((FIX / "crimsonwitch_genshin_trimmed.html").read_text(encoding="utf-8"),
                                   NOW)
    by = {h.code: h for h in hits}
    assert list(by) == ["AZHGG7H2ZQZS", "POYMANSXF877", "ARCHONSANSWERS", "CDOF4X83H7X2"], list(by)
    # itemised rewards, quantity formatted, exactly as the page shows them
    assert by["AZHGG7H2ZQZS"].rewards == ["Mora ×10,000", "Adventurer's Experience ×10",
                                          "Fine Enhancement Ore ×5", "Jueyun Chili Chicken ×5",
                                          "Stir-Fried Fish Noodles ×5"]
    assert by["POYMANSXF877"].rewards == ["Primogem ×20", "Geode of Replication ×160"]
    # every hit is this source, unverified (it is a community tracker, not a validator), with no origin
    assert {h.source for h in hits} == {"crimsonwitch"}
    assert not any(h.verified or h.origin for h in hits)
    # an explicit `expires` becomes expires_at; an absent one stays None (no invented date)
    assert by["ARCHONSANSWERS"].expires_at == 1795881659 and by["ARCHONSANSWERS"].expired is True
    assert by["AZHGG7H2ZQZS"].expires_at is None and by["AZHGG7H2ZQZS"].expired is False
    # the same page read *before* that expiry is not expired
    early = {h.code: h for h in csrc.parse_crimsonwitch(
        (FIX / "crimsonwitch_genshin_trimmed.html").read_text(encoding="utf-8"), 1795800000.0)}
    assert early["ARCHONSANSWERS"].expired is False
    assert early["ARCHONSANSWERS"].expires_at == 1795881659


def test_zenless_page_reads_under_its_own_slug_fixture():
    hits = csrc.parse_crimsonwitch((FIX / "crimsonwitch_zzz_trimmed.html").read_text(encoding="utf-8"))
    assert [h.code for h in hits] == ["INKSHIFT34", "HOLLOWRUN34"]
    assert hits[0].rewards == ["Polychrome ×20", "Denny ×2,222"]


def test_region_locked_entries_duplicates_and_junk_are_handled():
    html = _page([
        {"id": 1, "code": "GLOBALCODE1", "expires": None, "region_locked": None,
         "rewards": [{"item": "Primogem", "qty": 60}]},
        {"id": 2, "code": "CNONLYCODE2", "expires": None, "region_locked": "CN",
         "rewards": [{"item": "Primogem", "qty": 60}]},
        {"id": 3, "code": "GLOBALCODE1", "expires": None, "region_locked": None,
         "rewards": [{"item": "Primogem", "qty": 60}]},                      # duplicate id/code
        {"id": 4, "code": "", "expires": None, "region_locked": None},        # no code
        {"id": 5, "code": "ALLREGIONS5", "expires": None, "region_locked": "all",
         "rewards": [{"item": "Mora", "qty": 0}, {"item": "  ", "qty": 5}, {"item": "Hero's Wit"}]},
        "not-a-dict",
    ])
    hits = csrc.parse_crimsonwitch(html)
    assert [h.code for h in hits] == ["GLOBALCODE1", "ALLREGIONS5"], hits
    # a zero/absent quantity is not "×0"; an item without a quantity is kept as its name
    assert hits[1].rewards == ["Mora", "Hero's Wit"], hits[1].rewards


def test_escapes_inside_the_payload_are_decoded_not_split():
    html = _page([{"id": 9, "code": "ESCAPED1", "expires": None, "region_locked": None,
                   "rewards": [{"item": 'A "quoted" item', "qty": 2},
                               {"item": "line\nbreak", "qty": 1}]}])
    hits = csrc.parse_crimsonwitch(html)
    assert len(hits) == 1 and hits[0].code == "ESCAPED1"
    assert hits[0].rewards == ['A "quoted" item ×2', "line break ×1"], hits[0].rewards


def test_a_page_without_the_payload_is_a_clean_empty_result_never_a_guess():
    assert csrc.parse_crimsonwitch("") == []
    assert csrc.parse_crimsonwitch("<html><body>Klee couldn't find the page</body></html>") == []
    # a truncated preview / bot-challenge page keeps the same contract
    truncated = '<script>self.__next_f.push([1,"17:{\\"initialCodes\\":[{"code":' + "</script>"
    assert csrc.parse_crimsonwitch(truncated) == []


class _Fetcher:
    """Only what the crimsonwitch branch uses: one text GET, recorded."""

    def __init__(self, body: str | None) -> None:
        self.body = body
        self.calls: list[tuple[str, str]] = []

    async def get_text(self, url, *, source, headers=None, retries=2, timeout=None):
        self.calls.append((url, source))
        return self.body


def test_the_source_spec_fetches_the_right_page_and_tags_the_hits():
    body = (FIX / "crimsonwitch_zzz_trimmed.html").read_text(encoding="utf-8")
    f = _Fetcher(body)
    hits = asyncio.run(csrc.CodeSources(f).fetch("crimsonwitch:Zenless_Zone_Zero"))
    assert f.calls == [("https://www.crimsonwitch.com/codes/Zenless_Zone_Zero", "codes:crimsonwitch")]
    assert [h.code for h in hits] == ["INKSHIFT34", "HOLLOWRUN34"]
    # an unreachable page is None (the corroboration gate treats it as "no witness"), not []
    assert asyncio.run(csrc.CodeSources(_Fetcher(None)).fetch("crimsonwitch:Zenless_Zone_Zero")) is None


def test_wiring_labels_family_and_config():
    from gamexpress import cards
    assert csrc.CRIMSONWITCH.format("Genshin_Impact") == "https://www.crimsonwitch.com/codes/Genshin_Impact"
    # a community tracker is its own witness family: it never collapses into ennead/ogc
    assert csrc.family("crimsonwitch") == "crimsonwitch" and csrc.family("ogc") == csrc.family("ennead")
    assert "crimsonwitch" not in csrc.VALIDATORS
    assert cards.SOURCE_LABELS["crimsonwitch"] == "Crimson Witch"
    games = load_games()
    for key, slug in (("genshin", "Genshin_Impact"), ("starrail", "Honkai_Star_Rail"),
                      ("zzz", "Zenless_Zone_Zero")):
        srcs = games[key].codes["sources"]
        assert f"crimsonwitch:{slug}" in srcs, (key, srcs)
        assert srcs.index(f"crimsonwitch:{slug}") < srcs.index("reddit:Genshin_Impact"
                                                               if key == "genshin" else
                                                               f"reddit:{ {'starrail': 'HonkaiStarRail', 'zzz': 'ZZZ_Official'}[key] }")
    # Wuthering Waves / HNA / ANANTA have no Crimson Witch page in scope: nothing is wired there
    assert not any("crimsonwitch" in s for s in games["wuwa"].codes["sources"])
    assert not any("crimsonwitch" in s for s in games["hna"].codes["sources"])


def main() -> int:
    failed = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"  PASS  {name}")
            except Exception as exc:  # noqa: BLE001
                failed += 1
                print(f"  FAIL  {name}: {type(exc).__name__}: {exc}")
    print("CRIMSON WITCH TEST:", "ALL PASS" if not failed else f"{failed} FAILED")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
