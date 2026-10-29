"""Read-only live official news probe; no webhooks, secrets, or state writes.

Run explicitly: python tools/live_news_probe.py genshin|starrail|zzz|wuwa
Results describe the current discovery window only, not historical recall.
"""
from __future__ import annotations

import asyncio
import copy
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import aiohttp

from gamexpress.cards import news_payloads, validate_payload
from gamexpress.config import load_games
from gamexpress.http import Fetcher
from gamexpress.reveal_ping import classify_character_reveal
from gamexpress.sources import hoyolab, kuro


async def probe(key: str) -> None:
    game = load_games()[key]
    src = kuro if key == "wuwa" else hoyolab
    async with aiohttp.ClientSession() as session:
        fetcher = Fetcher(session, timeout=15)
        rows = await src.discover_news(fetcher, game, int(time.time()) - 86400)
        if rows is None:
            raise RuntimeError(f"{key}: live discovery unavailable or incomplete: {fetcher.summary()}")
        checked = matches = fit = 0
        # All discovered items in this bounded window, not an exhaustive historical corpus.
        for row in rows:
            art = await src.news_article(fetcher, game, row)
            if art is None:
                raise RuntimeError(f"{key}: article {row['id']} unavailable or invalid")
            for expand in (False, True):
                payloads = news_payloads(game, art, expand_full=expand)
                if any(validate_payload(payload) for payload in payloads):
                    raise RuntimeError(f"{key}: article {row['id']} invalid, expand={expand}")
                if classify_character_reveal(key, art):
                    test = copy.deepcopy(payloads[0])
                    test["components"][0]["components"][0]["content"] += " · <@&1296268365593186426>"
                    if not validate_payload(test):
                        fit += 1
            checked += 1
            matches += bool(classify_character_reveal(key, art))
        print(f"{key}: discovered={len(rows)} checked={checked} reveal_matches={matches} "
              f"mention_fit_mode_checks={fit}/{matches * 2}; {fetcher.summary()}", flush=True)


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in {"genshin", "starrail", "zzz", "wuwa"}:
        raise SystemExit("Pass one of: genshin, starrail, zzz, wuwa")
    asyncio.run(probe(sys.argv[1]))
