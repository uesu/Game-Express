"""Read-only diagnostics for the private backlog hold. No webhook or state access."""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import aiohttp  # noqa: E402
from live_candidate_probe import NoRedirectSession  # noqa: E402

from gamexpress import candidate_news_delivery as delivery  # noqa: E402
from gamexpress.cards import _split_expanded_text, news_payloads  # noqa: E402
from gamexpress.config import load_settings  # noqa: E402
from gamexpress.http import Fetcher  # noqa: E402
from gamexpress.sources import endfield, silverpalace  # noqa: E402

ROW = {"date": "2026-01-16", "id": "34", "title": "[Monotype] Beta Test  Survey Event Qualification Results Announcement"}


async def run():
    async with aiohttp.ClientSession(trust_env=False) as session:
        fetcher = Fetcher(NoRedirectSession(session))
        game = delivery.candidate_game("silverpalace")
        item = await silverpalace.news_article(fetcher, game, ROW)
        if item is None:
            print("::notice title=Historic hold diagnostic::detail=unavailable", flush=True)
            return
        body = [x.get("text", "") for x in item.article_blocks if x["kind"] == "text"]
        max_token = max((len(y) for x in body for y in x.split()), default=0)
        print(f"::notice title=Historic hold diagnostic::detail=available text-chars={sum(map(len, body))} "
              f"longest-whitespace-token={max_token} blocks={len(item.article_blocks)}", flush=True)
        for label, max_pages, max_chars in (("default", 12, 120000), ("bounded-large", 120, 1000000)):
            pages = news_payloads(game, item, expand_full=True, max_pages=max_pages, max_chars=max_chars, max_media=120)
            excerpt = any("**Excerpt — this article " in str(c.get("content", ""))
                          for p in pages for box in p.get("components", []) for c in box.get("components", []))
            rendered = "".join(c.get("content", "") for p in pages for box in p.get("components", [])
                               for c in box.get("components", []) if c.get("type") == 10)
            expected_separators = sum(x.count("、") for x in body)
            rendered_separators = rendered.count("、")
            print(f"::notice title=Historic hold diagnostic::profile={label} pages={len(pages)} excerpt={int(excerpt)} "
                  f"source-separators={expected_separators} rendered-separators={rendered_separators}", flush=True)
            if label == "bounded-large" and (excerpt or expected_separators != rendered_separators):
                raise ValueError("large article was not fully rendered")
        try:
            await delivery.render_candidate(fetcher, load_settings({"NEWS_EXPAND_MAX_PAGES": "120"}), "silverpalace", ROW)
        except delivery.DeliveryHold as exc:
            allowed = {"full article exceeds rendering safety limits", "article media preflight or payload validation failed",
                       "article unavailable or mismatched", "official article unavailable or mismatched", "grouped article payload invalid"}
            reason = str(exc) if str(exc) in allowed else "other delivery hold"
            print(f"::notice title=Historic hold diagnostic::result=hold reason={reason}", flush=True)
        else:
            print("::notice title=Historic hold diagnostic::result=renderable", flush=True)

        end_row = {"id": "4494", "title": "Arknights: Endfield [At the Wake of Spring] Core Chapter Version DEV Comm",
                   "ts": 1776049200}
        end_item = await endfield.news_article(fetcher, delivery.candidate_game("endfield"), end_row)
        if end_item is None:
            print("::notice title=Endfield hold diagnostic::detail=unavailable-or-mismatch", flush=True)
        else:
            text_chars = sum(len(b.get("text", "")) for b in end_item.article_blocks if b.get("kind") == "text")
            media = sum(b.get("kind") != "text" for b in end_item.article_blocks)
            print(f"::notice title=Endfield hold diagnostic::detail=available text-chars={text_chars} media-blocks={media}", flush=True)
            for i, block in enumerate(end_item.article_blocks):
                if block.get("kind") != "text":
                    continue
                value = block.get("text", "").strip()
                result = _split_expanded_text(value, 3500)
                if result is None:
                    print(f"::notice title=Endfield hold block::index={i} length={len(value)} "
                          f"bold-markers={value.count('**')} brackets-open={value.count('[')} "
                          f"brackets-close={value.count(']')} backticks={value.count('`')} "
                          f"longest-token={max((len(x) for x in value.split()), default=0)}", flush=True)
            preview = news_payloads(delivery.candidate_game("endfield"), end_item, expand_full=True, max_pages=120)
            excerpt = next((c.get("content", "") for p in preview for box in p["components"]
                            for c in box.get("components", []) if "**Excerpt — this article " in c.get("content", "")), "")
            if excerpt:
                kind = "single-message" if "single-message" in excerpt else "safety-limit"
                print(f"::notice title=Endfield hold diagnostic::excerpt-kind={kind}", flush=True)
            try:
                result = await delivery.render_candidate(fetcher, load_settings({"NEWS_EXPAND_MAX_PAGES": "120"}), "endfield", end_row)
            except delivery.DeliveryHold as exc:
                allowed = {"full article exceeds rendering safety limits", "article media preflight or payload validation failed",
                           "official article unavailable or mismatched", "grouped article payload invalid"}
                reason = str(exc) if str(exc) in allowed else "other delivery hold"
                print(f"::notice title=Endfield hold diagnostic::result=hold reason={reason}", flush=True)
            else:
                print(f"::notice title=Endfield hold diagnostic::result=renderable pages={len(result)}", flush=True)


if __name__ == "__main__":
    asyncio.run(run())
