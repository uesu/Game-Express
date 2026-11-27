"""Offline synthetic tests for the inactive Silver Palace listing snapshot."""
from __future__ import annotations

import asyncio
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from gamexpress.sources import silverpalace  # noqa: E402


def row(cid, day):
    return {"id": cid, "title": f"Official {cid}", "publish_date": day}


def page(number, total, rows):
    return {"code": 0, "data": {"current_page": str(number), "total_page": total, "list": rows}}


class Fetcher:
    def __init__(self, responses):
        self.responses, self.calls = list(responses), []

    async def get_json(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return self.responses.pop(0) if self.responses else None


def run(responses):
    f = Fetcher(responses)
    return asyncio.run(silverpalace.snapshot(f)), f


class SilverCandidateTests(unittest.TestCase):
    def test_unsorted_day_only_listing_scans_every_page_twice(self):
        p1 = page(1, 2, [row("01", "2026-10-01"), row("2", "2026-09-01")])
        p2 = page(2, 2, [row("3", "2026-11-01")])
        items, fetcher = run([p1, p2, p1, p2])
        self.assertEqual(items, [{"id": "01", "title": "Official 01", "date": "2026-10-01"},
                                 {"id": "2", "title": "Official 2", "date": "2026-09-01"},
                                 {"id": "3", "title": "Official 3", "date": "2026-11-01"}])
        self.assertEqual([call[1]["params"]["page"] for call in fetcher.calls], [1, 2, 1, 2])
        self.assertNotIn("ts", items[0])

    def test_invalid_incomplete_or_mutating_walks_fail_closed(self):
        one = page(1, 2, [row("1", "2026-01-01")])
        two = page(2, 2, [row("2", "2026-01-02")])
        cases = (
            [], [None], [{"code": False, "data": {}}],
            [page(1, 31, [row("1", "2026-01-01")])],
            [page(1, 1, [])],
            [page(1, 1, [row("1", "2026-02-30")])],
            [page(1, 1, [row("../1", "2026-01-01")])],
            [one], [one, page(2, 3, [row("2", "2026-01-02")])],
            [one, page(2, 2, [row("1", "2026-01-02")])],
            [one, two, one, page(2, 2, [row("3", "2026-01-02")])],
            [page(1, 2, [row("1", "2026-01-01"), row("2", "2026-01-01")]),
             page(2, 2, [row("3", "2026-01-01"), row("4", "2026-01-01"), row("5", "2026-01-01")])],
        )
        for responses in cases:
            with self.subTest(responses=responses):
                self.assertIsNone(run(responses)[0])


if __name__ == "__main__":
    unittest.main()
