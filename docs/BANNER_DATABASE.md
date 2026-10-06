# Banner line-ups: where they come from

A schedule card's banner block used to print `TBA` for every slot nobody had officially
announced yet — which, for a version whose livestream has not aired, is all of them. Each of
these games has a community wiki that documents the line-up the day the beta shows it, through
the same MediaWiki API: no key, pure JSON, `GET`. `gamexpress/sources/gachawiki.py` reads it.

**It fills blanks only.** An official notice (HoYoLAB, Kuro, the news page, X) or an entry in
`config/overrides.json` always wins. The reader sits at `PRIORITY["gachawiki"] = 6` — above the
community banner feed (5), below everything official.

## Precedence, top to bottom

| priority | source | what it may do |
|---|---|---|
| 100 | `config/overrides.json` | anything — the human is always right |
| 50 / 45 / 40 | HoYoLAB · Kuro · news page · X | the official line-up |
| 9 | cadence patterns | timestamps only |
| **6** | **the game wikis (this doc)** | **fill a banner slot that is still TBA** |
| 5 | `hub.json` banner feed | fill a 5★ phase that is still TBA |

## The four dialects

| game | host | pool template | 5★ field | 4★ field |
|---|---|---|---|---|
| genshin | `genshin-impact.fandom.com` | `Wish Pool` | `character_5_F` | `character_4_F` |
| starrail | `honkai-star-rail.fandom.com` | `Warp Pool` | `character_5_F` | `character_4_F` |
| zzz | `zenless-zone-zero.fandom.com` | `Signal Search Pool` | `agent_S_F` | `agent_A_F` |
| wuwa | `wutheringwaves.fandom.com` | `Convene/Pool` | `resonator_5_F` | `resonator_4_F` |

ANANTA and Honkai: Nexus Anima have no gacha data and are deliberately absent from `WIKIS`.

## Two requests, and only while a blank remains

1. `schedule.banner_block_complete()` runs **before any fetch**. A version whose banner block is
   already complete costs zero traffic, for ever.
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

## Traps, every one of them a real bug

- **A debut roster is not a line-up.** ZZZ 3.0 lists Pyrois with no Exclusive Channel; ZZZ 3.1
  puts Remielle under `* Lasting the whole version:`, which makes phase 1 the *re-run* Aria.
  That third bucket maps to phase 1 and can hold several characters.
- **Never detect a re-run from a repeated banner title.** HSR's `Indelible Coterie` was reused
  14 times with disjoint casts. It is always a set difference against the debut roster.
- **`character_5_F` is not single-valued** — always split on the separator.
- **ZZZ nicknames its own agents** on Version pages (`(Claret)`, `(Roxy)`). The banner page's
  full name wins; a prefix match is the fallback.
- **Sibling sections share the list layout** — HSR `Light Cone Event Warps:`, ZZZ
  `====W-Engine Channels====`, WuWa `Weapon Event Convenes`. Parsing stops at the section's own
  boundary, or weapons end up in the character line-up.
- **Placeholders exist in unannounced slots** — Genshin pads `character_4_F` with
  `Unknown Character` ×3. Those are filtered, and an official notice can be *ahead* of the wiki,
  which is the other reason this reader only ever fills blanks.
- **Wiki version ≠ calendar half.** Bucket on `time_start`.
- **Anchor the template regex**: `{{Wish` also matches `{{Wish Pool`.
- **Category listings are not clean lists** — filter `ns == 0`.
- **ZZZ's 4★ rate-ups are player-customisable** ("Custom Search", HoYoLAB post 46015688), so the
  ZZZ card renders that line as `4 Star Characters (Default)` — a default, not a guarantee.

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

ZZZ 3.3 was the early tier on that date: `Phoenix Reffaella`, `Severian Lowell`, releasing
2026-10-21. The fixtures behind `tests/fixtures/gachawiki/` are trimmed copies of those pages.
