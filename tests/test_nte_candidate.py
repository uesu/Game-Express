"""Synthetic one-page tests for the inactive NTE listing parser.

The date/path mismatch is modelled on article 265053 observed in the publisher's
listing and #173 capture, not a raw HTML fixture or an assumed publication time.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from gamexpress.sources import nte_candidate  # noqa: E402


def article(href, title="Official &amp; news", day="2026-11-20"):
    return f'<a href="{href}"><div><h2 class="title">{title}</h2><p class="date">{day}</p></div></a>'


def listing(content):
    return f'<html><div class="other">ignored</div><div class="listNews">{content}</div></html>'


class NteCandidateTests(unittest.TestCase):
    def test_observed_path_date_mismatch_uses_displayed_day(self):
        result = nte_candidate.parse_list_page(listing(article(
            "/en/article/news/gamebroad/20261113/265053.html", "Fan Content Guidelines", "2026-11-20")))
        self.assertEqual(result, [{"id": "265053", "title": "Fan Content Guidelines", "date": "2026-11-20"}])
        self.assertNotIn("ts", result[0])

    def test_canonical_links_and_source_order(self):
        html = listing(article("https://nte.perfectworld.com/en/article/news/gamenews/20260101/001.html") +
                       article("/en/article/news/gameevent/20261201/5.html", "News", "2026-10-01"))
        self.assertEqual(nte_candidate.parse_list_page(html), [
            {"id": "001", "title": "Official & news", "date": "2026-11-20"},
            {"id": "5", "title": "News", "date": "2026-10-01"}])

    def test_untrusted_host_malformed_or_incomplete_is_failure_not_empty(self):
        path = "/en/article/news/gamenews/20261113/123.html"
        invalid = [None, "<html>temporary error</html>", listing(""),
                   listing(article("https://evil.invalid" + path)),
                   listing(article("https://nte.perfectworld.com.evil.invalid" + path)),
                   listing(article("https://nte.perfectworld.com:443" + path)),
                   listing(article("https://u@nte.perfectworld.com" + path)),
                   listing(article(path + "?x=1")), listing(article(path, day="2026-02-30")),
                   listing(article(path, title="")), listing(article(path) + article(path)),
                   '<div class="listNews">' + article(path),
                   '<div class="listNews"><a href="' + path + '"><h2 class="title">broken</h2></div>',
                   listing(article(path)) + listing(article(path)), "x" * (1024 * 1024 + 1)]
        for value in invalid:
            with self.subTest(value=str(value)[:100]):
                self.assertIsNone(nte_candidate.parse_list_page(value))


if __name__ == "__main__":
    unittest.main()
