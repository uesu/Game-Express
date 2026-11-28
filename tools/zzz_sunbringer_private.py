"""One private Sunbringer example; independent intent journal, no ambiguous retry."""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import aiohttp  # noqa: E402
import candidate_private_backfill as historic  # noqa: E402
from live_candidate_probe import NoRedirectSession  # noqa: E402

from gamexpress import candidate_news_delivery as delivery  # noqa: E402
from gamexpress.cards import news_payloads, validate_payload  # noqa: E402
from gamexpress.config import load_games  # noqa: E402
from gamexpress.http import Fetcher  # noqa: E402
from gamexpress.media import news_media_available  # noqa: E402
from gamexpress.sources import hoyolab  # noqa: E402
from gamexpress.sources.candidate_thumbnail import with_verified_fallback  # noqa: E402
from gamexpress.state import stable_hash  # noqa: E402

MARKER = "feature3-zzz-sunbringer-example-v1"
COMMENT_ID = 0  # prepare, independently verify and lock before sending
ARTICLE = "47586861"


def existing():
    found = []
    for number in range(1, 21):
        page = historic.gh_api(f"repos/{historic.REPOSITORY}/issues/{historic.ISSUE}/comments?per_page=100&page={number}")
        if not isinstance(page, list):
            raise ValueError("journal listing unavailable")
        found.extend(c for c in page if isinstance(c, dict) and
                     str(c.get("body", "")).startswith(f"<!-- {MARKER}:zzz:"))
        if len(page) < 100:
            return found
    raise ValueError("journal listing bound reached")


def check(comment, route):
    data = historic.check_comment(comment, "zzz", COMMENT_ID or None)
    if (not isinstance(data, dict) or set(data) != {"article", "route", "phase", "signature", "message"}
            or data["article"] != ARTICLE or data["route"] != route
            or data["phase"] not in ("pending", "inflight", "confirmed")):
        raise ValueError("unexpected journal")
    return data


def save(comment, old, new, route):
    current = historic.gh_api(f"repos/{historic.REPOSITORY}/issues/comments/{COMMENT_ID}")
    if current.get("body") != comment.get("body") or check(current, route) != old:
        raise ValueError("journal changed")
    updated = historic.gh_api(f"repos/{historic.REPOSITORY}/issues/comments/{COMMENT_ID}", method="PATCH",
                              body={"body": historic.encode("zzz", new)})
    if check(updated, route) != new:
        raise ValueError("journal update unconfirmed")
    return updated


async def run(mode):
    historic.guard()
    settings, routes = historic.settings_and_routes()
    route = routes["nte"]  # only the private test destination; never a production NTE route
    historic.MARKER = MARKER
    if mode == "prepare":
        if COMMENT_ID or await asyncio.to_thread(existing):
            raise ValueError("journal exists or preparation locked")
        state = {"article": ARTICLE, "route": route, "phase": "pending", "signature": None, "message": None}
        comment = await asyncio.to_thread(historic.gh_api, f"repos/{historic.REPOSITORY}/issues/{historic.ISSUE}/comments",
                                           method="POST", body={"body": historic.encode("zzz", state)})
        if check(comment, route) != state:
            raise ValueError("journal creation unconfirmed")
        print(f"::notice title=ZZZ private example::prepared=1 comment={comment['id']} sent=0", flush=True)
        return
    if not COMMENT_ID:
        raise ValueError("journal not locked")
    comment = await asyncio.to_thread(historic.gh_api, f"repos/{historic.REPOSITORY}/issues/comments/{COMMENT_ID}")
    state = check(comment, route)
    if state["phase"] == "confirmed":
        print("::notice title=ZZZ private example::already-confirmed=1 no-send=1", flush=True)
        return
    if state != {"article": ARTICLE, "route": route, "phase": "pending", "signature": None, "message": None}:
        raise ValueError("inflight or unexpected state; inspect manually")
    async with aiohttp.ClientSession(trust_env=False) as session:
        fetcher = Fetcher(NoRedirectSession(session))
        game = load_games()["zzz"]
        full = await hoyolab._full_post(fetcher, game.hoyolab_gid, ARTICLE)
        if not full or str((full.get("user") or {}).get("uid")) != "219270333":
            raise ValueError("official author mismatch")
        post = full.get("post") or {}
        if post.get("subject") != 'Sunbringer EP - "Triple Threat" | Zenless Zone Zero':
            raise ValueError("title mismatch")
        item = await hoyolab.news_article(fetcher, game, {"id": ARTICLE, "ts": int(post["created_at"])})
        if item is None:
            raise ValueError("article unavailable")
        enriched = await with_verified_fallback(fetcher, item)
        if enriched is item or len(enriched.images) != 1:
            raise ValueError("verified thumbnail unavailable or native media present")
        pages = news_payloads(game, enriched, expand_full=True)
        if (len(pages) != 1 or validate_payload(pages[0])
                or not await news_media_available(fetcher, pages, max_urls=20)):
            raise ValueError("article render or media preflight failed")
        inflight = {**state, "phase": "inflight", "signature": stable_hash(pages)}
        comment = await asyncio.to_thread(save, comment, state, inflight, route)
        result = await delivery.send_candidate_once(session, settings, "nte", pages[0])
        if not result.ok or result.ambiguous or not result.message_id:
            raise ValueError("send outcome unconfirmed; no retry")
        confirmed = {**inflight, "phase": "confirmed",
                     "message": historic.anonymize(result.message_id, settings.env["DISCORD_WEBHOOK_NEWS_NTE"])}
        await asyncio.to_thread(save, comment, inflight, confirmed, route)
        print("::notice title=ZZZ private example::confirmed=1 pages=1 production-state=unchanged", flush=True)


if __name__ == "__main__":
    if sys.argv[1:] not in (["--prepare"], ["--send"]):
        raise SystemExit("Specify --prepare or --send explicitly.")
    try:
        asyncio.run(run(sys.argv[1][2:]))
    except Exception as exc:  # noqa: BLE001 — never expose private destination or response
        print(f"::notice title=ZZZ example held::error-type={type(exc).__name__}", flush=True)
        raise SystemExit("Held; inspect journal and private channel before any retry.") from None
