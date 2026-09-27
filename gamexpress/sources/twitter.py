"""Official X (Twitter) accounts: nitter RSS fleet for the timeline, FxTwitter → vxTwitter
for full tweet data (text with expanded links, photos, exact timestamp).

Same approach as News-Express twitter_v3 (round 13/14 fleet); the first TWO working
instances are merged so one stale-but-200 mirror can't hide a fresh tweet.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from calendar import timegm
from collections.abc import Callable
from urllib.parse import quote, unquote

import feedparser

from .. import schedule
from ..config import CONFIG_DIR, Game, Settings
from ..http import Fetcher
from ..media import sane_aspect
from ..models import Item
from ..textutil import find_urls, html_to_text

log = logging.getLogger("gamexpress.x")

TOKEN_GATED = {"https://nitter.miningtcup.me"}

# --------------------------------------------------------------------------- announcement seed
SEED_PATH = CONFIG_DIR / "program_announcements.json"
_seeds: dict | None = None


def program_seed(game_key: str, version: str) -> dict:
    """config/program_announcements.json -> the recorded X post for game+version ({} if none).

    Committed to the repo and rewritten by the monitor workflow, so the knowledge survives the
    throwaway state of a test run. Keys starting with '_' are comments and are ignored."""
    global _seeds
    if _seeds is None:
        try:
            _seeds = json.loads(SEED_PATH.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            _seeds = {}
    per_game = (_seeds or {}).get(game_key)
    if not isinstance(per_game, dict):
        return {}
    hit = per_game.get(version)
    return hit if isinstance(hit, dict) else {}


def save_program_seed(game_key: str, version: str, entry: dict) -> bool:
    """Record a newly discovered announcement. Returns True when the file changed, which is what
    tells the workflow there is something to commit back."""
    global _seeds
    data = json.loads(SEED_PATH.read_text(encoding="utf-8")) if SEED_PATH.exists() else {}
    per_game = data.setdefault(game_key, {})
    old = per_game.get(version)
    if isinstance(old, dict) and old.get("id") == entry.get("id"):
        return False
    import time as _t
    per_game[version] = {**entry, "found_at": int(_t.time())}
    SEED_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
                         encoding="utf-8")
    _seeds = None                                  # next read picks the new entry up
    log.info("[x:%s] recorded the %s program announcement (%s) in %s",
             game_key, version, entry.get("id"), SEED_PATH.name)
    return True


FX_SOURCES = (("fxtwitter", "https://api.fxtwitter.com/status/{id}"),
              ("fixupx", "https://api.fixupx.com/status/{id}"))
VXTWITTER_URL = "https://api.vxtwitter.com/Twitter/status/{id}"
X_UA = "Game-Express/1.1"


def _from_fx(t: dict, tweet_id: str) -> dict:
    links = [f.get("replacement") for f in ((t.get("raw_text") or {}).get("facets") or [])
             if f.get("type") == "url" and f.get("replacement")]
    return {"id": str(t.get("id") or tweet_id), "text": t.get("text") or "",
            "ts": int(t.get("created_timestamp") or 0),
            "photos": [p.get("url") for p in ((t.get("media") or {}).get("photos") or [])
                       if p.get("url") and sane_aspect(p.get("width"), p.get("height"))],
            "links": links + [u for u in find_urls(t.get("text") or "") if u not in links],
            "author": (t.get("author") or {}).get("screen_name") or "",
            "avatar": (t.get("author") or {}).get("avatar_url") or "",
            "url": t.get("url") or ""}


def _from_vx(vx: dict, tweet_id: str) -> dict:
    return {"id": str(vx.get("tweetID") or tweet_id), "text": vx.get("text") or "",
            "ts": int(vx.get("date_epoch") or 0),
            "photos": [u for u in (vx.get("mediaURLs") or []) if "video" not in u],
            "links": find_urls(vx.get("text") or ""),
            "author": vx.get("user_screen_name") or "",
            "avatar": vx.get("user_profile_image_url") or "",
            "url": vx.get("tweetURL") or ""}

NITTER_BATCH = 4          # instances probed in parallel per round
NITTER_TIMEOUT = 12       # seconds — a dead mirror must not stall the run
STATUS_RE = re.compile(r"/status(?:es)?/(\d{8,25})")


def nitter_pic_to_twimg(url: str) -> str:
    """https://nitter.cf/pic/media%2FHR70hTAaoAA8Dzz.jpg -> https://pbs.twimg.com/media/HR70hTAaoAA8Dzz.jpg"""
    m = re.search(r"/pic/(?:orig/)?(.+)$", url)
    if not m:
        return url
    path = unquote(m.group(1)).split("?")[0]
    if path.startswith(("media/", "ext_tw_video_thumb/", "tweet_video_thumb/", "amplify_video_thumb/")):
        return f"https://pbs.twimg.com/{path}"
    return url


class XClient:
    """Per-run cache so schedule + codes share one timeline fetch per account."""

    def __init__(self, fetcher: Fetcher, settings: Settings) -> None:
        self.fetcher = fetcher
        self.settings = settings
        self._timelines: dict[str, list[dict] | None] = {}
        self._tweets: dict[str, dict | None] = {}
        self.avatars: dict[str, str] = {}     # account (lower) -> current avatar url
        self.source_used: dict[str, int] = {}  # tweet-data service that answered, per run
        self.reachable: set[str] = set()      # accounts with >= 1 working instance this run

    async def _probe(self, inst: str, account: str) -> list | None:
        """One nitter instance -> parsed feed entries, or None (dead / bot-check / stale)."""
        url = f"{inst}/{account}/rss"
        headers = {"User-Agent": "Mozilla/5.0"}
        if inst in TOKEN_GATED:
            token = self.settings.nitter_token
            if not token:
                return None
            headers = {"User-Agent": f"Mozilla/5.0 {token}", "Authorization": f"Bearer {token}"}
            url += f"?token={quote(token, safe='')}"
        body = await self.fetcher.get_text(url, source="nitter", headers=headers, retries=0,
                                           timeout=NITTER_TIMEOUT)
        if not body:
            return None
        feed = await asyncio.to_thread(feedparser.parse, body)
        if not feed.entries:
            log.info("[x:%s] %s: HTTP 200 but 0 entries (bot check / stale) — next", account, inst)
            return None
        return list(feed.entries)

    async def timeline(self, account: str) -> list[dict]:
        """Instances are probed in parallel batches (a dead mirror costs one short timeout
        for the whole batch instead of one per instance); the first TWO working instances
        (in fleet order) are merged."""
        if account in self._timelines:
            return self._timelines[account] or []
        entries: dict[str, dict] = {}
        working = 0
        fleet = list(self.settings.nitter_instances)
        for i in range(0, len(fleet), NITTER_BATCH):
            if working >= 2:
                break
            batch = fleet[i:i + NITTER_BATCH]
            results = await asyncio.gather(*(self._probe(inst, account) for inst in batch))
            for feed_entries in results:
                if working >= 2 or not feed_entries:
                    continue
                working += 1
                for e in feed_entries:
                    m = STATUS_RE.search(e.get("link", ""))
                    if not m:
                        continue
                    creator = (e.get("author") or e.get("dc_creator") or "").lstrip("@").lower()
                    if creator and creator != account.lower():
                        continue  # retweet of another account
                    tid = m.group(1)
                    ts = timegm(e.published_parsed) if e.get("published_parsed") else 0
                    html_body = e.get("summary") or e.get("description") or ""
                    text, links, imgs = html_to_text(html_body)
                    entries.setdefault(tid, {
                        "id": tid, "ts": ts, "title": e.get("title") or "", "text": text or e.get("title") or "",
                        "links": links, "images": [nitter_pic_to_twimg(i) for i in imgs],
                    })
        if not working:
            log.warning("[x:%s] no working nitter instance this run", account)
        else:
            self.reachable.add(account.lower())
        self._timelines[account] = sorted(entries.values(), key=lambda x: x["ts"], reverse=True) if working else None
        return self._timelines[account] or []

    async def tweet(self, tweet_id: str) -> dict | None:
        if tweet_id in self._tweets:
            return self._tweets[tweet_id]
        result = None
        for name, url in FX_SOURCES:
            data = await self.fetcher.get_json(url.format(id=tweet_id), source=name,
                                               headers={"User-Agent": X_UA},
                                               retries=1 if name == "fxtwitter" else 0)
            t = (data or {}).get("tweet") if isinstance(data, dict) else None
            if t:
                result = _from_fx(t, tweet_id)
                self.source_used[name] = self.source_used.get(name, 0) + 1
                if name != "fxtwitter":
                    log.info("[x] %s answered for %s (fxtwitter could not)", name, tweet_id)
                break
        if not result:
            vx = await self.fetcher.get_json(VXTWITTER_URL.format(id=tweet_id),
                                             source="vxtwitter", retries=1)
            if isinstance(vx, dict) and vx.get("text") is not None:
                result = _from_vx(vx, tweet_id)
                self.source_used["vxtwitter"] = self.source_used.get("vxtwitter", 0) + 1
                log.info("[x] vxtwitter answered for %s (FxEmbed could not)", tweet_id)
        self._tweets[tweet_id] = result
        if result and result.get("author") and result.get("avatar"):
            self.avatars[result["author"].lower()] = result["avatar"]
        return result

    async def program_tweet(self, game: Game, version: str) -> Item | None:
        """THE schedule lookup, X first. Two stages, because the two halves of X age differently:

        1. SEED — config/program_announcements.json maps game+version to a tweet id that a
           previous run discovered. fxtwitter still serves a five-week-old tweet by id (verified:
           the ZZZ 3.2 announcement from 2026-08-24 resolves fine on 2026-09-27), so this is the
           stage that makes a `mode=test` run — whose state is always empty — show the real link
           and the real key art.
        2. TIMELINE — a nitter RSS feed only reaches back a few days (nitter.cf on 2026-09-27
           stopped at 2026-09-23), so it can only ever find an announcement that is still new.
           That is exactly when one first appears, which is when it gets discovered and seeded.
        """
        seed = program_seed(game.key, version)
        if seed and seed.get("id"):
            t = await self.tweet(str(seed["id"]))
            if t and t.get("text"):
                log.info("[x:%s] %s program announcement from the seed file: %s",
                         game.key, version, t.get("url") or seed["id"])
                return self._program_item(game, str(seed["id"]), seed.get("account") or "", t)
            log.info("[x:%s] seed tweet %s did not resolve — falling back to the timeline",
                     game.key, seed.get("id"))
        for account in game.x_accounts:
            for e in await self.timeline(account):
                if not schedule.is_program_announcement(game, e["text"]):
                    continue
                if version and version not in e["text"]:
                    continue                      # an announcement for some other version
                t = await self.tweet(e["id"]) or e
                log.info("[x:%s] %s program announcement found on the timeline: %s",
                         game.key, version or "?", t.get("url") or e["id"])
                item = self._program_item(game, e["id"], account, t)
                save_program_seed(game.key, version or "?", {
                    "id": e["id"], "account": account, "url": item.url,
                    "posted_ts": item.published_ts, "image": (item.images or [""])[0],
                })
                return item
        return None

    def _program_item(self, game: Game, tid: str, account: str, t: dict) -> Item:
        return Item(source="x", game=game.key, id=tid,
                    url=t.get("url") or f"https://x.com/{account}/status/{tid}",
                    title="", text=t.get("text") or "", published_ts=t.get("ts") or 0,
                    images=t.get("photos") or [], links=t.get("links") or [],
                    author=t.get("author") or account)

    async def items(self, game: Game, want: Callable[[str], bool], since_ts: int) -> list[Item]:
        if not self.settings.x_enabled:
            return []
        timelines = await asyncio.gather(*(self.timeline(a) for a in game.x_accounts))
        picked = [(account, e) for account, tl in zip(game.x_accounts, timelines) for e in tl
                  if not (e["ts"] and e["ts"] < since_ts) and want(e["text"])]
        details = await asyncio.gather(*(self.tweet(e["id"]) for _, e in picked))
        out: list[Item] = []
        for (account, e), t in zip(picked, details):
            text = (t or {}).get("text") or e["text"]
            out.append(Item(
                source="x", game=game.key, id=e["id"],
                url=(t or {}).get("url") or f"https://x.com/{account}/status/{e['id']}",
                title="", text=text, published_ts=(t or {}).get("ts") or e["ts"],
                images=(t or {}).get("photos") or e["images"],
                links=(t or {}).get("links") or e["links"], author=account))
        return out


def item_from_fx_json(game_key: str, data: dict) -> Item:
    """Build an Item from a raw FxTwitter /status response (tests + TEST tools)."""
    t = data.get("tweet") or data
    links = [f.get("replacement") for f in ((t.get("raw_text") or {}).get("facets") or [])
             if f.get("type") == "url" and f.get("replacement")]
    return Item(source="x", game=game_key, id=str(t.get("id")), url=t.get("url") or "", title="",
                text=t.get("text") or "", published_ts=int(t.get("created_timestamp") or 0),
                images=[p["url"] for p in ((t.get("media") or {}).get("photos") or []) if p.get("url")],
                links=links + find_urls(t.get("text") or ""),
                author=(t.get("author") or {}).get("screen_name") or "")
