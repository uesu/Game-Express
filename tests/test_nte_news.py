"""Neverness to Everness official news — the Perfect World adapter (feature 3).

Verified 2026-11-27 from a GitHub runner; the bytes it was written against are committed under
`tests/fixtures/probes/` and trimmed into `nte_news_index_trimmed.html` /
`nte_news_article_trimmed.html` (same markup, fewer rows).

What these tests pin, in the order the code runs:

1. the list is read from the **href**, not from a CSS class: tab, day and id come from the URL, so
   a template restyle cannot silently renumber anything;
2. the canonical day is the one in the path (`/20261123/`), because the printed date has no zone
   and appears in two different formats (list `2026-11-23`, article `2026.11.23`);
3. an article body is extracted with a **balanced** `<div>` walk, so a nested div (or a footer that
   follows the body) cannot truncate or swallow it;
4. a page that cannot be fetched is `None` — never `[]` — so the caller advances no baseline and a
   later run still sees the article;
5. the article becomes an `Item` with ordered blocks, the game's own key and the official author,
   which is what the news card renderer expects.

Run:  python tests/test_nte_news.py      (pytest collects it too)
No network, no secrets.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from gamexpress import config  # noqa: E402
from gamexpress.models import Item  # noqa: E402
from gamexpress.sources import perfectworld as pw  # noqa: E402

FIX = ROOT / "tests" / "fixtures"
INDEX = (FIX / "nte_news_index_trimmed.html").read_text(encoding="utf-8")
ARTICLE = (FIX / "nte_news_article_trimmed.html").read_text(encoding="utf-8")
GAMES = config.load_games()
NTE = GAMES["nte"]

DAY_265196 = 1795392000   # 2026-11-23 UTC midnight, from the /20261123/ path segment
DAY_265053 = 1794528000   # 2026-11-13
DAY_265063 = 1794787200   # 2026-11-16


def test_the_list_is_read_from_the_href_and_the_path_day():
    rows = pw.parse_news_list(INDEX)
    assert [r["id"] for r in rows] == ["265196", "265053", "265063"], rows
    assert {r["tab"] for r in rows} == {"gamebroad"}
    assert [r["ts"] for r in rows] == [DAY_265196, DAY_265053, DAY_265063]
    assert rows[0]["url"] == "https://nte.perfectworld.com/en/article/news/gamebroad/20261123/265196.html"
    assert rows[0]["title"] == "Account Action Notice: 2026-11-23 (UTC+8)"
    # the list's summary line repeats the title, so nothing is invented from it
    assert "Account Action Notice" in rows[1]["title"] or rows[1]["title"].startswith("《")


def test_relative_hrefs_are_absolutised_and_duplicates_collapse():
    html = ('<a href="/en/article/news/gamenews/20261120/265100.html"><h2 class="title">A</h2></a>'
            '<a href="/en/article/news/gamebroad/20261120/265100.html"><h2 class="title">A again</h2></a>'
            '<a href="/en/article/news/gameevent/20261118/265099.html"><h2 class="title">B</h2></a>')
    rows = pw.parse_news_list(html)
    assert [r["id"] for r in rows] == ["265100", "265099"]      # one article, one entry
    assert rows[0]["url"].startswith("https://nte.perfectworld.com/en/article/news/")
    assert rows[0]["title "] if False else rows[0]["title"] == "A"   # first occurrence wins


def test_a_garbage_list_is_empty_never_an_exception():
    for body in ("", "<html><body>maintenance</body></html>", "<a href='/en/article/news/x/1.html'>no</a>"):
        assert pw.parse_news_list(body) == []


def test_the_article_body_survives_nested_divs_and_a_footer():
    parsed = pw.parse_article(ARTICLE)
    assert parsed["title"] == "Account Action Notice: 2026-11-23 (UTC+8)"
    assert parsed["ts"] == DAY_265196                      # `.articleDate` + the path agree
    assert parsed["cover"].startswith("https://nte.perfectworld.com/public/images/")
    assert parsed["blocks"] and parsed["blocks"][0]["kind"] == "text"
    text = parsed["blocks"][0]["text"]
    assert "Hey Appraiser" in text
    # the balanced walk stops at the body's own close: the article footer is not part of it
    assert "NTE Team" not in text
    # ...and a nested div inside the body is kept, not cut at its first close
    nested = ('<div class="articleContent"><p>before</p><div class="quote">inner</div>'
              '<p>after</p></div><div class="footer">tail</div>')
    blocks = pw.parse_article(f'<h1 class="articleTitle">T</h1>{nested}')["blocks"]
    joined = " ".join(b.get("text", "") for b in blocks)
    assert "before" in joined and "inner" in joined and "after" in joined and "tail" not in joined


def test_an_article_without_a_body_is_empty_not_a_stub():
    assert pw.parse_article("")["blocks"] == []
    assert pw.parse_article("<html><body><h1 class='articleTitle'>T</h1></body></html>")["blocks"] == []


class _Fetcher:
    """Serves a URL -> body map and records every request (one request per URL in the real client)."""

    def __init__(self, pages: dict[str, str | None]) -> None:
        self.pages = pages
        self.calls: list[str] = []

    async def get_text(self, url, *, source, headers=None, retries=1, timeout=None):
        self.calls.append(url)
        return self.pages.get(url)


def _list_page(*ids, tab="gamebroad", day="20261123", base="https://nte.perfectworld.com") -> str:
    rows = "".join(f'<a href="/en/article/news/{tab}/{day}/{i}.html">'
                   f'<h2 class="title">Notice {i}</h2></a>' for i in ids)
    return rows


def test_discovery_reads_every_tab_once_and_stops_when_the_window_is_passed():
    urls = {f"https://nte.perfectworld.com/en/article/news/{tab}/index.html": _list_page("265196")
            for tab in pw.TABS}
    urls["https://nte.perfectworld.com/en/article/news/gamebroad/index1.html"] = _list_page("264000", day="20260101")
    f = _Fetcher(urls)
    rows = asyncio.run(pw.discover_news(f, NTE, 1795390000))
    # the second page is entirely older than `since`, so it is fetched once and then dropped
    assert [r["id"] for r in rows] == ["265196"]
    assert f.calls[0] == "https://nte.perfectworld.com/en/article/news/gamenews/index.html"
    assert "https://nte.perfectworld.com/en/article/news/gamebroad/index1.html" in f.calls
    assert all(call.endswith(("index.html", "index1.html")) for call in f.calls)


def test_every_tab_unreadable_is_none_but_a_read_empty_page_is_empty():
    assert asyncio.run(pw.discover_news(_Fetcher({}), NTE, 0)) is None
    blank = {f"https://nte.perfectworld.com/en/article/news/{tab}/index.html": "<html></html>"
             for tab in pw.TABS}
    assert asyncio.run(pw.discover_news(_Fetcher(blank), NTE, 0)) == []
    # a game without the flag never touches the network
    f = _Fetcher({})
    assert asyncio.run(pw.discover_news(f, GAMES["endfield"], 0)) is None and f.calls == []


def test_pagination_is_bounded():
    page = _list_page("265196")
    pages = [pw._page_path("gamenews", i) for i in range(9)]
    f = _Fetcher({f"https://nte.perfectworld.com/en/article/news/gamenews/{name}": page
                  for name in pages})
    rows = asyncio.run(pw.discover_news(f, NTE, 0))
    assert len(f.calls) <= len(pw.TABS) * pw.MAX_PAGES
    assert rows and rows[0]["id"] == "265196"


def test_the_article_becomes_a_news_item():
    row = {"id": "265196", "url": "https://nte.perfectworld.com/en/article/news/gamebroad/20261123/265196.html",
           "title": "Account Action Notice: 2026-11-23 (UTC+8)", "ts": DAY_265196, "tab": "gamebroad"}
    item = asyncio.run(pw.news_article(_Fetcher({row["url"]: ARTICLE}), NTE, row))
    assert isinstance(item, Item)
    assert (item.source, item.game, item.id) == ("perfectworld", "nte", "265196")
    assert item.url == row["url"] and item.published_ts == DAY_265196
    assert item.title.startswith("Account Action Notice") and item.author == "Perfect World"
    assert item.article_blocks and item.source_label == "Official News"
    assert item.images and item.images[0].startswith("https://nte.perfectworld.com/")
    # a page that no longer exists, or one whose body vanished, is nothing to post
    assert asyncio.run(pw.news_article(_Fetcher({}), NTE, row)) is None
    assert asyncio.run(pw.news_article(_Fetcher({row["url"]: "<html></html>"}), NTE, row)) is None


def test_wiring_flags_defaults_and_the_untouched_titles():
    assert NTE.pw_news is True and NTE.enabled and NTE.released
    assert "nte" in config.DEFAULT_NEWS_GAMES
    assert GAMES["endfield"].pw_news is False and "endfield" not in config.DEFAULT_NEWS_GAMES
    assert GAMES["silverpalace"].enabled is False and "silverpalace" not in config.DEFAULT_NEWS_GAMES
    # the HoYoLAB/Kuro flags must not have moved: this adapter is additive only
    assert GAMES["genshin"].hoyolab_gid == 2 and GAMES["wuwa"].kuro_news is True
    assert GAMES["hna"].hoyolab_gid == 9 and GAMES["nte"].hoyolab_gid is None


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
    print("NTE NEWS TEST:", "ALL PASS" if not failed else f"{failed} FAILED")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
