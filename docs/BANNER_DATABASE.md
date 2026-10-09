# Banner line-ups: where they come from

A schedule card's banner block used to print `TBA` for every slot nobody had officially
announced yet — which, for a version whose livestream has not aired, is all of them. Each of
these games has a community wiki that documents the line-up the day the beta shows it, through
the same MediaWiki API: no key, pure JSON, `GET`. `gamexpress/sources/gachawiki.py` reads it.

**It never overrides anyone else.** An official notice (HoYoLAB, Kuro, the news page, X) or an
entry in `config/overrides.json` always wins. The reader sits at `PRIORITY["gachawiki"] = 6` —
above the community banner feed (5), below everything official.

Inside its own lane it is **self-correcting**: an entry this reader wrote is kept in step with
what the wiki says now, and is withdrawn when the wiki stops supporting it. A value is only as
good as the read it came from — "already filled" is not the same as "already right", which is
how ZZZ 3.3 kept the slot word `Agent` on the card for a full day in October 2026.

## Precedence, top to bottom

| priority | source | what it may do |
|---|---|---|
| 100 | `config/overrides.json` | anything — the human is always right |
| 50 / 45 / 40 | HoYoLAB · Kuro · news page · X | the official line-up |
| 50 / 45 | title search (HoYoLAB search, Kuro menu) | the official notice of the card's own version, any age; a hit is a candidate, the lock rules still apply |
| 9 | cadence patterns | timestamps only |
| **6** | **the game wikis (this doc)** | **fill a banner slot that is still TBA, confirm a name another source gave, and revise or withdraw its own unconfirmed entries** |
| 5 | `hub.json` banner feed | fill a 5★ phase that is still TBA |

## Finding the notice by title

The wiki and the hub read the banner the community already knows. The title search asks the official
sources for the banner notice of the card's own version, whatever its age, so a notice older than the
72-hour lookback can still confirm a name. That is how HSR 4.6 Phase I (posted 2026-09-27) is found.
Code: `sources/banner_search.py`; templates: `banner_titles` in `config/games.json`.

| game | keyword template (filled with the version and the phase) |
|---|---|
| genshin | `Version {v} Event Wishes Notice - Phase {p}` |
| starrail | `Version {v} Event Warp: Phase {p}` |
| zzz | `V{v} Limited-Time Channels (Phase {p})`, and `V{v} Limited-Time Channels` for a Phase I posted with no suffix (ZZZ 3.1 Phase I, HoYoLAB 46015688) |
| wuwa | `Version {v} Featured Resonator/Weapon Convene: Phase {p}` |

- **Exact match.** `7.1` does not match `7.10`; Phase I never matches Phase II or III; `V3.2` and `Version 3.2`
  both match. A template with no `{p}` identifies Phase I only, and only its bare title; a weapon-only Convene title does not match the resonator template.
- **Official only.** A HoYoLAB hit must come from the game's `official_uid` (Genshin `1015537`, Star Rail
  `172534910`, ZZZ `219270333`). A fan repost is ignored. Wuthering Waves reads Kuro's own article menu, and the
  GitHub mirror (`TheLovinator1/wutheringwaves`) is read only when that menu gives nothing.
- **Order.** HoYoLAB keyword search first. When the search endpoint does not answer, the official news list is
  paged with `getNewsList` instead. The search is one request per phase per run.
- **Only a candidate.** A hit goes into the same merge as every other official post. Names come from the
  body (`extract_banner()`), and the lock rules above decide what may change.
- **When it runs.** `banner_search_due()`: a settled block never; a frozen card never; an incomplete block every
  3 hours; a complete unconfirmed block every 6 hours. Its own stamp is `banners_search_ts`, so it does not reset
  the wiki clock (`banners_checked_ts`). A failed search is still stamped and retried only when due again.
- **Off switch.** `BANNER_SEARCH=0`. With no fetcher (a dry test) there is no request and no stamp.

**Tentative values.** A hub or wiki name stays changeable until it is confirmed (a second source agreeing, or an
official notice). An official notice locks alone. Nothing in this section locks a value earlier than that:
HSR 4.6 Phase II (Mortenax Blade) is hub-sourced and stays unlocked until an official post exists.

## The four dialects

| game | host | pool template | 5★ field | 4★ field |
|---|---|---|---|---|
| genshin | `genshin-impact.fandom.com` | `Wish Pool` | `character_5_F` | `character_4_F` |
| starrail | `honkai-star-rail.fandom.com` | `Warp Pool` | `character_5_F` | `character_4_F` |
| zzz | `zenless-zone-zero.fandom.com` | `Signal Search Pool` | `agent_S_F` | `agent_A_F` |
| wuwa | `wutheringwaves.fandom.com` | `Convene/Pool` | `resonator_5_F` | `resonator_4_F` |

ANANTA and Honkai: Nexus Anima have no gacha data and are deliberately absent from `WIKIS`.

## Two requests, and only while a name is open

1. `schedule.wiki_recheck_due()` runs **before any fetch**:
   - an incomplete block (still TBA) is read at most every `WIKI_INCOMPLETE_H` = **3 hours**;
   - a complete block with an unconfirmed name at most every `WIKI_RECHECK_H` = **6 hours**;
   - a block whose every name is locked is never read again;
   - a card whose maintenance started more than 45 days ago (`CARD_FREEZE_D`) is never read.

   Before the throttle, an incomplete block was read on every five-minute run. A version processed
   every run (the ZZZ 3.3 override pins it) cost 288 wiki requests a day. It now costs 8. Each answered
   read is stamped in the state (`banners_checked_ts`), so the state file changes at most once per interval.
2. Request 1 — `action=parse&page=Version/<X.Y>&prop=wikitext`: the debut roster and the banner
   section, split into phases.
3. Request 2 — one batched `action=query&prop=revisions` over the *dated* banner pages found in
   step 2 (up to 50 titles per call, `|` encoded as `%7C`). Their pool templates give the exact
   5★ and 4★ names.
4. `reruns = featured − debuts`.
5. A 4★ list whose length is not exactly the game's `four_star_count` is dropped, not published.

User-Agent: `Game-Express (banner monitor)` — no version number, same rule as everywhere else.
No new dependencies: standard-library `re` and the existing `Fetcher.get_json`.

## Phase markers differ per game

| game | banner section | phase marker |
|---|---|---|
| genshin | `;Event Wishes` | `* Phase I` / `* Phase II` |
| starrail | `* Character Event Warps:` | `… - Phase 1` at the end of each line |
| zzz | `====Exclusive Channels====` | `* Phase 1:` / `* Phase 2:` |
| wuwa | `===Character Event Convenes===` | none — **dated page = phase 1, undated = phase 2** |

## The early tier

When a version has a debut roster but no phase data yet, the reader emits
`{"confirmed": [...]}` and the card prints

```
※ Confirmed: Phoenix Reffaella, Severian Lowell
※ Re-runs: TBA
```

`confirmed` belongs to the wiki's key set but **not** to the banner key set, so the line
disappears by itself on the silent edit that brings the real phase data in. That is intended,
not a regression.

A channel list that exists but names no character counts as "no phase data": a version stub
whose phases read `** [[Exclusive Channel]] (Agent)` is the early tier with extra markup, so the
card shows the debut roster instead of the slot word.

## Traps, every one of them a real bug

- **A debut roster is not a line-up.** ZZZ 3.0 lists Pyrois with no Exclusive Channel; ZZZ 3.1
  puts Remielle under `* Lasting the whole version:`, which makes phase 1 the *re-run* Aria.
  That third bucket maps to phase 1.
- **One annotation can hold several characters.** ZZZ 3.1's `Exclusive Rescreening` reads
  `([[Dialyn]], [[Ukinami Yuzuha]], [[Asaba Harumasa]])` — one banner, three agents.
- **Never detect a re-run from a repeated banner title.** HSR's `Indelible Coterie` was reused
  14 times with disjoint casts. It is always a set difference against the debut roster.
- **`character_5_F` is not single-valued** — always split on the separator.
- **ZZZ nicknames its own agents** on Version pages (`(Claret)`, `(Roxy)`). The banner page's
  full name wins; a prefix match is the fallback.
- **Sibling sections share the list layout** — HSR `Light Cone Event Warps:`, ZZZ
  `====W-Engine Channels====`, WuWa `Weapon Event Convenes`. Parsing stops at the section's own
  boundary, or weapons end up in the character line-up.
- **Placeholders exist in unannounced slots** — Genshin pads `character_4_F` with
  `Unknown Character` ×3, and a version stub names the *slot* rather than the character: ZZZ
  writes `(Agent)`, Genshin `(Character)`, WuWa `(Resonator)`. `publishable_name()` rejects both
  kinds at every point a name enters, in all four dialects. An official notice can also be
  *ahead* of the wiki, which is why this reader never outranks one.
- **Wiki version ≠ calendar half.** Bucket on `time_start`.
- **Anchor the template regex**: `{{Wish` also matches `{{Wish Pool`.
- **Category listings are not clean lists** — filter `ns == 0`.
- **ZZZ's 4★ rate-ups are player-customisable** ("Custom Search", HoYoLAB post 46015688), so the
  ZZZ card renders that line as `4 Star Characters (Default)` — a default, not a guarantee.

## Confirmation and the lock

A banner name (a 5★ phase, its 4★ list, the re-runs and the 4★ summary) is **locked** in one of three ways:

- **An official notice locks it on its own.** A HoYoverse, Kuro, news-page or X notice that parses cleanly
  is the strongest source the bot reads, so its name locks at once.
- **Two community groups agree.** The community hub (`feed`) and this wiki reader (`wiki`) name the same
  value. Two copies of one notice (HoYoLAB and X) are one group, not two.
- **An override** in `config/overrides.json` locks it alone.

A **locked** name is recorded in `banners_settled`. The feed and the wiki never change it. An official name
is final too: a later official notice that names someone else is logged once as a conflict, not applied
(correct it through `config/overrides.json`). The one official exception is a 4★ list: two clean official
lists that disagree become TBA with a warning. A doubtful 4★ reading (wrong count, odd names) never blanks a
list that is already locked. Re-reading the same post after a parser fix does heal its own name.

A name that is **not** locked is tentative, and it can still change:

- the hub follows its own later reading of a phase it wrote;
- the wiki corrects a hub name (the wiki outranks the hub), but never an official name;
- an official notice replaces a hub or wiki name, because an official notice outranks both, and locks it;
- a hub title held in a phase (a banner name, never a character) is corrected even when it was locked, and
  that correction is unlocked until another source agrees.

A silent wiki or hub never erases a value it did not write. Only the wiki withdraws a value the wiki itself wrote.

Details:

- `reruns` and the 4★ summary come only from the wiki. They lock only when the wiki names them **and** the
  phase lists they come from are already locked. The 4★ summary must equal both phases' 4★ lists, and a
  re-run must be a name featured in a phase.
- The early-tier `※ Confirmed:` line comes only from the wiki. It never locks, and it is removed when phase
  data arrives, as before.
- A name only the wiki gives, with no official notice and no hub agreement, stays open. The wiki reads it every
  six hours until the freeze. Genshin 7.1's 4★ list is in this state today.
- Locks written by earlier versions of the bot are honoured: an official name already on a card is locked on
  the next merge (`_sync_official_locks`), so it does not keep the wiki busy.

## Switching it off

`GACHA_WIKI=0` disables the whole reader: no requests, banner blocks go back to showing whatever
official sources and the banner feed provide. See [CONFIGURATION.md](CONFIGURATION.md).

## Verified line-ups (2026-10-06)

| game | version | phase 1 | phase 2 |
|---|---|---|---|
| genshin | 7.1 | Vesna, Vodyanitsa | Skirk, Escoffier *(re-runs)* |
| starrail | 4.6 | Pearl, Evanescia | Mortenax Blade |
| zzz | 3.2 | Claret Flint, Nangong Yu | Roxy Ifrita Pryce, Promeia |
| wuwa | 3.7 | Hsin, Chisa, Iuno | Suoming, Lucilla, Lynae |

Re-checked on 2026-10-09 against the community hub (`hub.json`). The hub's `startsAt` values run about seven hours later than the official start times for Star Rail (4.6 Phase II: the hub's value is 2026-10-21 19:00 UTC+8, the post says 12:00 server time) and for Genshin 7.1 Phase II. The ennead Star Rail calendar carries the same stamps. Genshin and ZZZ calendar stamps match their posts to the minute. The offset only moves the phase split, never a name: Genshin 7.1 and Star Rail 4.6 phase 1 and 2 names match the table, and the hub already lists the Star Rail 4.6 phase 2 banner (Mortenax Blade) with a start date of 2026-10-21.

ZZZ 3.3 was the early tier on that date: `Phoenix Reffaella`, `Severian Lowell`, releasing
2026-10-21. The fixtures behind `tests/fixtures/gachawiki/` are trimmed copies of those pages.
