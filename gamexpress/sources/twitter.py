"""Official X (Twitter) accounts: nitter RSS fleet for the timeline, FxTwitter → vxTwitter
for full tweet data (text with expanded links, photos, exact timestamp).

Same approach as News-Express twitter_v3 (round 13/14 fleet); the first TWO working
instances are merged so one stale-but-200 mirror can't hide a fresh tweet.
"""

from __future__ import annotations

import asyncio
import logging
import re
from calendar import timegm
from collections.abc import Callable
from urllib.parse import quote, unquote

import feedparser

from ..config import Game, Settings
from ..http import Fetcher
from ..models import Item
from ..textutil import find_urls, html_to_text

log = logging.getLogger("gamexpress.x")

TOKEN_GATED = {"https://nitter.miningtcup.me"}

FX_SOURCES = (("fxtwitter", "https://api.fxtwitter.com/status/{id}"),
              ("fixupx", "https://api.fixupx.com/status/{id}"))
VXTWITTER_URL = "https://api.vxtwitter.com/Twitter/status/{id}"
X_UA = "Game-Express/1.1"


def _from_fx(t: dict, tweet_id: str) -> dict:
    links = [f.get("replacement") for f in ((t.get("raw_text") or {}).get("facets") or [])
             if f.get("type") == "url" and f.get("replacement")]
    return {"id": str(t.get("id") or tweet_id), "text": t.get("text") or "",
            "ts": int(t.get("created_timestamp") or 0),
            "photos": [p.get("url") for p in ((t.get("media") or {}).get("photos") or []) if p.get("url")],
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
