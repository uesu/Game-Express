# Data sources — what is used, why, and how it was verified

Everything marked ✅ was **fetched live on 2026-09-25** while building v1.0. The response
shapes are pinned by the fixtures in `tests/fixtures/`. Every source is optional at runtime:
a dead source is logged and skipped, and the next one in the chain is used.

## Schedule & announcements

| Source | Endpoint | Gives | Status |
|---|---|---|---|
| HoYoLAB news list (official) | `https://bbs-api-os.hoyolab.com/community/post/wapi/getNewsList?gids={2,6,8,9}&page_size=15&type={1,2,3}` | titles + truncated text of Notices (1) / Events (2) / Info (3) | ✅ found "Version 4.6 Update and Maintenance Notice" |

**All three official tabs are read, for every game that has a HoYoLAB circle.** What the website
shows as `page_sort=notices | events | news` is `type=1 | 2 | 3` of the same API call, so the
monitor sees exactly the pages below — an announcement cannot hide in the "wrong" tab
(`test_every_official_feed_a_game_declares_is_actually_requested` pins this):

| Game | gid | Official circle the monitor reads (all three sorts) |
|---|---|---|
| Genshin Impact | 2 | `hoyolab.com/circles/2/27/official?page_type=27&page_sort={notices,events,news}` |
| Honkai: Star Rail | 6 | `hoyolab.com/circles/6/39/official?page_type=39&page_sort={notices,events,news}` |
| Zenless Zone Zero | 8 | `hoyolab.com/circles/8/47/official?page_type=47&page_sort={notices,events,news}` |
| Honkai: Nexus Anima | 9 | `hoyolab.com/circles/9/90002/official?page_type=90002&page_sort={notices,events,news}` |

Wuthering Waves (Kuro) and ANANTA (NetEase) have no HoYoLAB circle — they are covered by the Kuro
official site / launcher and by X respectively. The API is used rather than the web pages because
it returns the same posts as structured JSON, with no HTML or JavaScript to scrape.
| HoYoLAB post (official) | `…/getPostFull?gids={gid}&post_id={id}` | full body (`content` HTML, or `structured_content` when `content == "en-us"`) + images | ✅ HSR 46814308 (quirk), GI 46604275 |
| c3kay JSON-Feed (mirror, fallback) | `https://feeds.c3kay.de/{genshin,starrail,zenless}.json` | JSON Feed 1.1 with full `content_html`, refreshed every 30 min | ✅ |
| Official X accounts | nitter RSS fleet `https://<instance>/<account>/rss` (18 entries, 17 live — `xcancel.com` is suspended; originally from News-Express round 13/14) | timeline (first 2 working instances merged) | fleet taken from News-Express |
| Tweet details | `https://nitter.cf/<account>/status/{id}/rss` (then `xitter.cf`, when the account is known) → `https://api.fxtwitter.com/status/{id}` → `https://api.fixupx.com/status/{id}` → `https://api.vxtwitter.com/Twitter/status/{id}` | full text with expanded links, photos, exact timestamp; the winner is logged | ✅ all 4 reference tweets |
| Kuro official site (WW) | `https://hw-media-cdn-mingchao.kurogame.com/akiwebsite/website2.0/json/G152/en/{ArticleMenu,MainMenu}.json` + `…/article/{id}.json` | official articles incl. *Featured Resonator/Weapon Convene* banner notices; times are UTC+8 | ✅ (English menus are homepage **subsets**, so X stays primary for WW) |
| HoYoPlay launcher | `https://sg-hyp-api.hoyoverse.com/hyp/hyp-connect/api/getGameBranches?launcher_id=VYTpXlbWo8` | exact live version (`main.tag`) + pre-install availability (`pre_download`) | ✅ ZZZ `3.2.0` |
| Kuro launcher (WW) | `https://prod-alicdn-gamestarter.kurogame.com/launcher/game/G153/50004_obOHXFrFanqsaIEOmuKroCcbZkQRBC7c/index.json` | live version (`default.version`) + `predownload` | structure from WW downloader configs |

HoYoLAB game IDs: 1 HI3 · 2 Genshin · 6 Star Rail · 8 ZZZ · **9 Honkai: Nexus Anima** (already
wired for launch day).

**Why `getGameBranches` and not `getGamePackages`:** the legacy package list is stale for games
that moved to Sophon downloads. On 2026-09-24 it still reported GI 5.5.0 while the live game was
7.1.

## X (Twitter) fetching — no X API account

Timelines come from the public nitter fleet, with `nitter.cf` first. Four instances are probed
in parallel and the first two that answer are merged; a mirror returning HTTP 200 with zero
entries is treated as a bot check and skipped. The token-gated `https://nitter.miningtcup.me/`
mirror alone needs `NITTER_RSS_TOKEN`.

The fleet is audited by **reading the feed body**, not by trusting a status page — public
trackers probe the homepage, so they score a mirror as "RSS ✅" while `/rss` actually serves a
browser check. The 2026-10-03 audit fetched every host by hand and found three of the four
hot-path slots were dead weight: `xitter.cf` is the same backend as `nitter.cf` behind a second
domain (every link in its feed points back at `nitter.cf`), and `nitter.jaydenha.uk` answers
`/rss` with a "click anywhere to enter" splash. `nitter.kareem.one` and `tw.eir-nya.gay` —
both verified to serve a real, current feed — took those slots. `tw.eir-nya.gay` is also the
only mirror that keeps real expanded links instead of rewriting them to its own `/t.co/` proxy.

**And both of those promotions then failed in production**, which is the rule the fleet is
built on: a hand probe from anywhere else does not predict what a GitHub runner gets. In the
run of 2026-10-03 04:25, `nitter.kareem.one` — the best-scoring mirror on the public tracker —
answered **HTTP 403 on all six handles**, and `tw.eir-nya.gay` was not blocked but simply too
slow, still silent when the quorum had already been met, so `NITTER_GRACE` discarded it on four
handles and it returned zero entries on the other two. Both were demoted and two fresh
candidates took the slots. A hot-path slot therefore needs **two** things, enforced by separate
tests: a feed body read by hand, *and* no runner-measured failure.

Only `nitter.cf` and the token-gated `nitter.miningtcup.me` have answered 6/6 handles live, and
they hold slots 1 and 4 — so the quorum of two never depends on a trial slot, and an experiment
costs wasted requests at worst, never a missed announcement. Worth knowing where that leaves
the fleet: `nitter.cf` and `xitter.cf` are one machine, so the only *independent* redundancy
today is the token-gated mirror. Finding a second backend that answers Actions IPs is exactly
what the two trial slots are for.

Being polite about it matters: these are volunteer-run mirrors and `status.d420.de` asks
outright that they not be scraped. The design already keeps the cost low — the loop stops at
the first two answers, so a healthy run spends 2 requests per handle, not 16.

A mirror that stops answering is **demoted, never deleted**. `x.n0g.xyz` returned HTTP 404 then
429 on every handle in three consecutive live runs, so it sits at the very end of the fleet as a
backup instead of being cut — and because the loop above breaks once two instances have answered,
a demoted mirror costs no requests at all until the mirrors ahead of it degrade. The same applies
to `nitter.netbub.com`, `nitter.meowing.monster`, `xcancel.com` and `x.yuuki.sh`: a host may
simply be blocking GitHub's runners while answering fine from a VPS.

Single tweets are read **from nitter.cf first** when the account is known: `XClient.tweet()` asks the
nitter status feed (`nitter.cf`, then `xitter.cf`, the same backend) for that post. FxTwitter is asked
only when nitter cannot answer, or when the post carries a `t.co` link that nitter leaves unexpanded (the
YouTube link is read from the expanded URL). The chain after that is **fxtwitter → fixupx → vxtwitter**,
and the nitter text is the last resort. A status mirror that fails `STATUS_FAIL_LIMIT` (2) times in one run
is skipped for the rest of that run, so a dead mirror costs two timeouts instead of one per tweet. FxTwitter and fixupx are
normalized to the same shape, while vxtwitter is the last fallback. `fixupx` intentionally uses
zero retries because it is an optional public host and should fail over immediately when DNS is
unavailable. Tweet responses are cached once per run, and `XClient.source_used` records which
service answered.

## Redemption codes

| Source | Endpoint | Trust | Status |
|---|---|---|---|
| HoYoLAB livestream module (official) | `…/community/painter/wapi/circle/channel/guide/material?game_id={2,6,8}` → `data.modules[].exchange_group.bonuses[].exchange_code` | **official**: posts immediately | ✅ (empty outside livestreams, as expected) |
| hoyo-codes.seria.moe | `https://hoyo-codes.seria.moe/codes?game={genshin,hkrpg,nap}` | **redeem-validator** (`status: OK` = works, `NOT_OK` = counted as an *expired* flag) | ✅ 9 GI codes, all OK (2026-09-25) |
| Hum-Bao/hoyoverse-codes *(v1.1)* | `https://raw.githubusercontent.com/Hum-Bao/hoyoverse-codes/main/{GENSHIN,HSR,ZZZ}.txt` → jsDelivr mirror | **redeem-validator**: a daily job redeems every code on a US account and keeps only working ones | ✅ updated daily (~20:18 UTC) |
| Open Gacha Codes *(v1.1)* | `https://api.ennead.cc/codes/{genshin,starrail,zenless,wuwa}` | community (**confirming only**: noisy, includes glued-together and stale codes, which are filtered) | ✅ incl. Wuthering Waves |
| api.ennead.cc (legacy) | `https://api.ennead.cc/mihoyo/{genshin,starrail,zenless}/codes` (`active` → active, `inactive` → *expired* flag) | community, **same backend as Open Gacha Codes = counted as one source** | ✅ |
| wuthering.gg *(v1.1)* | `https://wuthering.gg/codes` (HTML table: code · COPY/Expired · rewards · date) | community (WW), provides **expired** flags | ✅ (only WUTHERINGGIFT active on 2026-09-25) |
| Fandom wikis (MediaWiki API) | `https://{wiki}.fandom.com/api.php?action=query&prop=revisions&titles={page}&rvprop=content&rvslots=main&format=json` | community. Expired rows and **passed *valid until* dates** give an *expired* flag; a passed date beats every other source *(v1.1.1)* | ✅ **all four pages re-checked live 2026-09-27** — GI `Promotional_Code` (pageid 10893, revid 2183997, 2026-09-25T12:05:33Z, 4 891 B) · HSR `Redemption_Code` (2451, 470121, 2026-09-20T11:51:48Z, 44 109 B) · ZZZ `Redemption_Code` (15440, 184104, 2026-09-13T06:30:28Z, 3 357 B) · WW `Redemption_Code` (2513, 143093, 2026-09-19T12:03:08Z, 15 082 B). GI's live `Active Codes` section is now a fixture — 11 codes, none duplicated, the CN-only `YuanShen` row dropped, `VesnaOnPatrol` normalised to upper case |
| PromoGacha data | `https://raw.githubusercontent.com/gripcrip-blip/codehub/main/data/codes.json` → jsDelivr mirror | **aggregator**: every entry says where it was copied from (`hoyo-codes` = seria, `Fandom Wiki` = fandom, `Open Gacha Codes` / `api.ennead.cc` = ennead), and entries are never removed. It counts as that upstream — never as an extra independent source — and stale copies are ignored *(v1.1.1)* | ✅ |
| Official posts | X / HoYoLAB text that explicitly lists "Redemption Codes" | **official**: posts immediately | extraction tested on real tweets (no false positives) |

### How one code stays one code (v1.20.0)

Every hit is folded into a single record keyed by the **sanitised** code (`sanitize()` strips
non-alphanumerics and upper-cases, so `VesnaOnPatrol` and `VESNAONPATROL` are the same code), and
the gate counts **families**, not sources:

| rule | effect |
|---|---|
| `SOURCE_FAMILY` maps `ogc` → `ennead` | one backend, one vote |
| a codehub entry counts as its upstream (`seria` / `fandom` / `ennead`) | an aggregator copy is never a second source |
| `drop_stale_copies()` | a codehub copy is ignored once its upstream answered and no longer lists the code |
| `drop_concatenations()` | `AAAA…BBBB…` collector artifacts (two codes glued together) are dropped |
| `CodeSources._once()` | each spec is fetched at most once per run, even with all six games prefetching |
| state is keyed by code | a code already `posted` is never posted twice |

A wiki heading decides active vs expired, and the marker is anchored with `(?m)^`, **not** `\n`:
the MediaWiki API returns a page from its first byte, so a wiki whose opening line is
`==Expired Codes==` has no newline in front of it. The old anchor skipped that heading and read
every dead code on the page as active.

## X (Twitter) is the PRIMARY schedule source (v1.8.0)

The 2026-09-27 run proved the old order wrong: all three HoYoverse games reported "no program
announcement found" and WW linked a lore article whose title merely contains "Special Program" —
while the same run's log showed the X client healthy (`fxtwitter 6ok · nitter 16ok / 0 fail`) and
never asked. `runner.find_program` now runs X first; everything below it is a backup.

| # | Stage | What it reaches | Why it is where it is |
|---|---|---|---|
| 1 | **X seed** — `config/program_announcements.json` → `nitter.cf/<account>/status/<id>/rss` (then `xitter.cf`), with `api.fxtwitter.com/status/<id>` as the expander for `t.co` links | a tweet of ANY age by id (the ZZZ 3.2 announcement from 2026-08-24 — 34 days old — resolved fine on 2026-09-27, full key art) | the card is re-rendered for the whole 6-week version, and `mode=test` starts from an empty state — the committed id is what makes both show the real link and the real `?name=orig` key art |
| 2 | **X timeline** — nitter RSS fleet (`nitter.cf` first) | only the last few days (`nitter.cf` on 2026-09-27 stopped at 2026-09-23) | that is exactly when an announcement first appears — it is discovered here once and written back to the seed file by the monitor workflow |
| 3 | **HoYoLAB** news list | official text + timestamps, paged back past the lookback window | its image list is often a small article cover, not the key art |
| 4 | **Official news page** | archives every announcement | image can be a page rendition; Kuro's page is a JS build |
| 5 | **Feed mirror** (WW) | RSS/Atom mirror of Kuro's news list | last resort for the one site the scraper cannot read |

**Lookup order and the lock.** `runner.find_program` asks X first (the seed, then the X timeline), then
HoYoLAB, then the official news page, then the feed mirror. The card's lock follows
`schedule.LOCK_RANK` (X 3, HoYoLAB and Kuro 2, news 1), so an X post wins when both carry the
announcement. See [ACCURACY.md → Once posted](ACCURACY.md#once-posted-the-card-keeps-its-announcement).

**Positive matching** (`schedule.is_program_announcement`): a post qualifies only when it carries
the game's own livestream phrase AND a stated air time (`will premiere / is scheduled to air /
will begin … on <date>`). A negative filter alone is what failed — the WW lore article's title
genuinely contains "Special Program". Only the first 160 characters (the headline) are screened
against the not-an-announcement patterns, because three of the four real announcements mention
redemption codes or a giveaway in the body.

**Shape check** (`media.sane_aspect`): an image whose aspect ratio exceeds 3.5:1 is never used as
key art — the 2026-09-27 run put a 1440×29482 stitched article strip on the WW card.

**No new secret.** Discovery uses the public nitter fleet, recall uses the public FxEmbed /
BetterTwitFix APIs; `NITTER_RSS_TOKEN` remains the only Twitter-related secret.

## Official news pages + media (v1.3.0 — the announcement's own link and key art)

> **v1.8.0:** these are now the *backups* behind X (see the section above).

These are **official** sources: they carry the announcement itself, not an interpretation of it.
They are used for *presentation* (which link and which picture the card shows) and, when no
official post in the lookback window gave one, for the program air time — which is as
trustworthy as any other official post, because that is what it is.

| Source | URL | Parsed from | Status |
|---|---|---|---|
| HoYoLAB news list | `bbs-api-os.hoyolab.com/.../getNewsList?gids=<gid>&type=1&page_size=20&last_id=…` | paged back past the lookback window; `subject` matched against the game's program patterns + version; `cover_list` is the article cover | ✅ official API, already in use |
| HSR news page | https://hsr.hoyoverse.com/en-us/news (+ `?type=notice`) | server-rendered entries: cover on `fastcdn.hoyoverse.com`, article id, title, `M/D/YYYY` | ✅ checked 2026-09-25 |
| HSR article page | https://hsr.hoyoverse.com/en-us/news/166179 | full-size cover **and** the embedded `youtube.com/watch?v=…` → `maxresdefault.jpg` (1280×720) | ✅ checked 2026-09-25 |
| Genshin news page | https://genshin.hoyoverse.com/en/news | same template | ⏳ same template, not separately captured |
| ZZZ news page | https://zenless.hoyoverse.com/en-us/news | same template | ⏳ same template, not separately captured |
| WW news page | https://wutheringwaves.kurogames.com/en/main/news | Kuro's own template; the JSON article menus in `sources/kuro.py` remain the primary WW source | ⏳ client-rendered list — the menus cover it |
| **WW news mirrors** *(v1.7.0)* | `raw.githubusercontent.com/TheLovinator1/wutheringwaves/…/articles_{latest,all}.xml` | RSS/Atom mirrors of the same news list; used when Kuro's client-rendered page cannot be scraped | ✅ parsed against the live `articles_latest.xml` (2026-09-26) |

**Image renditions** (`gamexpress/media.py`) — every source hands back a small picture by default:

| What the source gives | What the card uses |
|---|---|
| `pbs.twimg.com/media/X.jpg` | `…X.jpg?name=orig` (X serves `small` unless you ask) |
| `pbs.twimg.com/media/X?format=jpg&name=large` | unchanged — it already asks for a size |
| `nitter.<instance>/pic/media%2FX.jpg` | `https://pbs.twimg.com/media/X.jpg?name=orig` |
| `i.ytimg.com/vi/ID/hqdefault.jpg` | `…/maxresdefault.jpg` (1280×720 instead of 480×360) |
| `fastcdn.hoyoverse.com/content-v2/…` | unchanged — already the full-size article cover |

Ranking puts the program's own artwork first: a livestream thumbnail, then a full-size tweet
photo, then an article cover. Nothing is ever rewritten to a host the source did not give us.

**Not used:** Reddit (`reddit.com/r/<official sub>/…/search.json`) was considered as an image
fallback. It is skipped for now — the official pages already serve the key art at full size, and a
subreddit preview image is a re-upload, so it would be the first non-official pixel on a card.

## Countdown / timer sites (v1.2.0 — estimates only)

The official maintenance notice arrives days after the Special Program, so until then the card
would show `TBA`. These community sites extrapolate the patch cycle (42 days for HoYoverse,
~42 days for Kuro) and fill the gap. They are an **estimate**: `schedule.PRIORITY['countdown']`
is low (10), so an estimate is used only when no official source has given that time, and it is
replaced — with the 🕒 line on the card — the moment the official notice is seen.
`COUNTDOWN_ESTIMATES=0` switches the feature off.

| Source | URL | Parsed from | Status |
|---|---|---|---|
| gengamer.in livestream | `https://{genshin,hsr,zenless,wuthering}-countdown.gengamer.in/livestream` | `Release Date & Time: Friday, October 23 at 8:00 AM EDT` → the **program** time | ✅ checked 2026-09-25 |
| gengamer.in version | `https://{game}-countdown.gengamer.in/` | same line / live countdown → **maintenance start** | ✅ |
| Gacha Countdown | `https://gachacountdown.online/games/{genshin,hsr,zzz,wuwa}/` | `39 Days 14 Hours 09 Minutes 08 Seconds` (a delta from now) → **maintenance start** | ✅ |
| version-counter.netlify.app | https://version-counter.netlify.app | client-rendered; no absolute date in the HTML | ⏳ add once it exposes a date |
| gengamer countdown network | `https://gachacountdown.online/`, `https://wuthering-countdown.gengamer.in/` … | same parsers, per game | ✅ |
| game8 maintenance pages | `https://game8.co/games/{genshin-impact,honkai-star-rail,zenless-zone-zero,wuthering-waves}/…` | not verified yet — add through `COUNTDOWN_SOURCES` once a page with an absolute date is found | ⏳ |
| torikushiii/hoyoverse-api · hoyolab-auto · ennead.cc | https://github.com/torikushiii/hoyoverse-api · https://api.ennead.cc/mihoyo | **codes / HoYoLAB mirrors only** — no schedule endpoint (ennead answers with its code-endpoint list), so nothing to add here | ❌ for schedules |

Prepared but empty: `hna` and `ananta` — no countdown site tracks a game before release. Fill
`gamexpress/sources/countdown.py:SOURCES` when one appears.

## Pre-install lead — learned from official notices (v1.6.0)

A maintenance start does not imply one universal pre-install weekday. Patch lengths, holidays and
schedule changes move the notice, so the fallback stores a single value per real version:

```text
preinstall_offset_h = (maintenance start - official pre-install time) / 3600
```

`observed_lead_h()` takes the median of that game's valid history (not the mean), ignores malformed
entries and leads over 14 days, and passes it into `schedule.merge()` once for the current run.
A timestamp derived by the fallback is listed in `data["estimated"]`; `_handle_version` therefore
never records it as an observation. This prevents a guess from feeding back and confirming itself.
An official value from any existing maintenance path replaces it — including X/Nitter, because
`schedule.classify()` already accepts maintenance/pre-install text from `item.source == "x"`.

Cold start uses one verified 2026 lead per released game:

| Game | Cold-start lead | Real notice reproduced |
|---|---:|---|
| Genshin Impact | 43 h | 7.1: Mon 2026-09-21 11:00 → Wed 06:00 (UTC+8) |
| Honkai: Star Rail | 88 h | 4.6: Thu 2026-09-24 14:00 → Mon 06:00 (UTC+8) |
| Zenless Zone Zero | 42 h | 3.2: Mon 2026-09-07 12:00 → Wed 06:00 (UTC+8) |
| Wuthering Waves | 42 h | 3.7: Mon 2026-09-28 10:00 → Wed 04:00 (UTC+8) |

These are startup data, not permanent per-game rules. As soon as this installation observes a real
notice, that game's median takes precedence. This still cannot predict an unprecedented shortened
version before any source publishes it; the card stays honestly labelled estimated until one does.

## Banner lineups — Kitsudock-data, ex Gacha-hub-info (v1.3.0)

When no official banner notice has been posted yet, rate-up character lineups are filled from
`ertezy.github.io/Kitsudock-data/hub.json` (renamed from `Gacha-hub-info` in Oct 2026 — the old
Pages URL returns 404). It is rebuilt hourly by GitHub Actions from the fandom
wikis (CC BY-SA 3.0), requires no key, and returns a single JSON file covering the four released games
(`genshin`, `hsr`, `zzz`, `wuthering` + `endfield`).

Lineups are phase-split around the version's release / maintenance timestamp (`startsAt` around
release = Phase 1, `startsAt` ~3 weeks later = Phase 2).

**Accuracy & limits:**
- Sits at `PRIORITY["bannerfeed"] = 5` — the lowest priority in the bot. It only fills an empty
  phase, and any official notice or override replaces it immediately, until the phase is confirmed. A phase the hub names
  exactly as the card holds it is one of the two confirmations that lock it (see
  [BANNER_DATABASE.md](BANNER_DATABASE.md#confirmation-and-the-lock)).
- 4★ rate-ups and re-run flags are not present in the feed and remain `TBA`.
- Stale payloads (>14 days) are refused rather than serving outdated lineups.
- `BANNER_FEED=0` switches the fill-in off completely.
- **Cross-check, not only a fill-in:** the hub is the one source that separates a banner's NAME
  from the character featured on it, so a phase holding a string the hub knows as a banner title
  means the notice was mis-read — the hub's own `featured` list replaces it. That is what caught
  HSR 4.6 phase 1 carrying `An Ocean in a Pearl` (a banner) instead of `Pearl` (the character).
- The notice reader no longer needs that rescue for the common case. A name list follows the
  star-tier phrase **immediately**, so a quoted span sitting behind prose belongs to another
  clause and names a banner, never a character:
  `… obtainable 5-star characters include … the custom-selected characters from "Celestial
  Invitation."` and `… the limited 5-star character Pearl … can only be obtained from the "An
  Ocean in a Pearl" Character Event Warp` (both verbatim from HoYoLAB post `46851682`, checked
  against `getPostFull` on 2026-09-27). Read as characters, those two titles made the cross-check
  fire on **every** run, so phase 1 was carried by the feed at priority 5 — in the feed's order —
  instead of by the official notice at 50 in the notice's own order.

### Banner sources evaluated

| Source | Verdict |
|---|---|
| **`ertezy.github.io/Kitsudock-data/hub.json`** | ✅ **used.** Rebuilt hourly by GitHub Actions, GitHub Pages, no key, one small file for all games. `banners[] = {gameId, title, featured[], rarity, startsAt, endsAt, url, image}`. Covers genshin / hsr / zzz / wuthering (+ endfield). Assembled from the fandom wikis → CC BY-SA 3.0 |
| `torikushiii/hoyoverse-api` (`/mihoyo/{game}/calendar`) | ⚠️ good shape (`banners[].characters[].rarity`, `start_time`) but **no Wuthering Waves**, and no public instance was confirmed — not usable as the primary |
| `DGCK81LNN/gi-gacha` `banners.json` | ⚠️ auto-updated and precise, but **Chinese names only** (`薇斯纳池`) — would need a name-mapping table |
| `game-i.daa.jp` / `achenachena/gacha_revenue` | ❌ revenue estimates and banner *windows*, not lineups |
| IGN · game8 · dotesports · pcgamer · timesaver.gg | ❌ editorial HTML, no API, every site a different layout — useful only to cross-check |
| HoYoverse `getGachaLog` | ❌ needs a per-user `authkey`; that is a wish history, not a schedule |

**Gate (v1.1):**

1. An official source posts immediately.
2. A redeem-validator (seria / Hum-Bao) says the code works and no validator says it's expired
   → posts immediately.
3. Any *expired* flag from any source → held.
4. At least `CODES_MIN_SOURCES` (2) **independent** community sources → posts. Open Gacha Codes
   and ennead are one family.
5. Otherwise the code stays pending for 14 days, and the reason is shown in the job summary.

A posted code that every source now lists as expired is struck through on the posted card
(`CODES_MARK_EXPIRED`, default on).

All code sources are fetched **in parallel, each URL once per run**, even when several games
share it.

## Banner notices by title (2026-10-09)

The title search (`sources/banner_search.py`, [BANNER_DATABASE.md → Finding the notice by title](BANNER_DATABASE.md#finding-the-notice-by-title))
reads these, in order:

| source | used for | verified on 2026-10-09 |
|---|---|---|
| HoYoLAB `bbs-api-os.hoyolab.com` keyword search (`community/search/wapi/search/post`) | the official notice of the card's version, by title | answers for `gids=2` (Genshin), `6` (Star Rail), `8` (ZZZ); `size=10` |
| HoYoLAB `getNewsList` (official news list) | fallback when the search does not answer | yes (`type=2`) |
| Kuro `ArticleMenu` JSON (`G152/en`) and `article/<id>.json` | Wuthering Waves notices, the official menu and body | `5318` (3.6 Phase I) read |
| GitHub `TheLovinator1/wutheringwaves` Atom mirror | fallback only, when Kuro's menu gives nothing | list read; the repository declares **no license** |

Facts the searches confirmed: Genshin 7.1 Phase I (`46771531`) and Phase II (`47010361`), Star Rail 4.6 Phase I
(`46851682`), ZZZ 3.2 Phase I (`46604530`) and Phase II (`46863847`). **No** Star Rail 4.6 Phase II official post and
**no** ZZZ 3.3 official post existed on 2026-10-09; both stay hub-sourced and unlocked.

The sandbox cannot reach `bbs-api-os.hoyolab.com` with `curl` (TLS reset); the endpoint was checked through the
page fetcher, and so were the ennead calendars. The production reachability of the search endpoint is therefore verified only by the first live run
(see the log line below), and the `getNewsList` fallback covers it if the search is refused.

**Evaluated on 2026-10-09 (requested by the operator's links):**

- **`torikushiii/hoyoverse-api`** (Rust, AGPL-3.0; public instance `api.ennead.cc/mihoyo`). Its `/mihoyo/{game}/calendar`
  endpoints return the in-game event calendar with banners: `version`, the characters or weapons, and start and end times.
  Checked through the page fetcher: `genshin/calendar`, `starrail/calendar` and `zenless/calendar` all answer. The
  root `/mihoyo` lists only the code endpoints, so the calendar is not in its endpoint list.
  - Genshin 7.1 Phase I: both banners (`Character Event Wish` Vesna, `Character Event Wish 2` Vodyanitsa; Diona, Faruzan, Chongyun at 4★) match the post. End 2026-10-13 17:59 UTC+8, matching the post.
  - ZZZ 3.2 Phase II (Roxy, Promeia; Corin, Billy): start 2026-09-30 12:00 and end 2026-10-20 14:59 UTC+8, matching the post.
  - Star Rail 4.6: Pearl and Evanescia, and the Qingque/Xueyi/Misha 4★ lists match the posts. **Mortenax Blade (4.6 Phase II) is already listed** with start 1792580400 (2026-10-21 19:00 UTC+8, the same stamp as the hub). Star Rail stamps run about 7 hours later than the posts' "server time".
  - Not yet listed: Genshin 7.1 Phase II and ZZZ 3.3.
  - **Status: not integrated.** It is a third-party relay of HoYoverse's game data, not an official post, so it would count as a hub-level source. Whether it may confirm a name is an operator decision (see the note below).
- **`hakush.in` / `seriaati/hakushin-py`** (Python async wrapper): the wrapper's README says it is mainly for beta game data and that Wuthering Waves is "not planned". Its docs site was not reachable (404 on the GitHub Pages address), and `sr.yatta.moe` and `gi.yatta.moe` `/api/v2/en/banner` return 404. **No banner schedule was found there, so not used.**
- **Other async wrappers found by search:** `seriaati/genshin.py` (HoYoLAB/Miyoushe API, asyncio + pydantic) and `seriaati/enka-py` (showcase data). Neither is a banner-schedule source. Not used.
- **`api.ennead.cc/mihoyo`** root: codes only (`/codes` for Genshin, Star Rail, ZZZ, Honkai, Themis).
- `Ertezy/Gacha-hub-info` (= `Kitsudock-data`): already the hub feed (`hub.json`), used since v1.3.0.

## Evaluated but not integrated (and why)

| Candidate | Verdict |
|---|---|
| YouTube channel RSS (`/feeds/videos.xml?channel_id=`) | returned **404** during verification (even for Genshin's confirmed channel ID). YouTube links and thumbnails come from the official tweets and HoYoLAB posts instead |
| parse.bot marketplace APIs (prydwen / icy-veins / genshin.gg / hoyolab) | paid third-party scrapers, not verifiable; not needed for official data |
| `getGamePackages` (HoYoPlay legacy) | stale for Sophon games (see above) |
| Hoyotod/code · Hoyotod/redeem | fandom-scraper pattern (we call the MediaWiki API directly) · redeem automation (requires accounts; out of scope) |
| heartlog/Hoyocodes · promogacha.netlify.app | static sites. PromoGacha's GitHub JSON **is** used |
| chiraitori/HoYo_Code_Sender_Discord_Bot · Hum-Bao/hoyoverse-codes-backend · retvil/hoyo-code-monitor · lukascortes/gacha-codes-notifier | reference implementations; their sources are covered above (Hum-Bao's **published TXT lists** are used as a validator since v1.1) |
| MoonShadow1976 WW asset repos | manually maintained, last updated Jan 2026, so too stale for codes |
| DuolaD/HoYo_Versioncatcher | launcher-data repo; led us to the launcher endpoints |
| genshin.dev | character/game data API, not schedules or codes |
| gachabase.net · nanoka.cc · sr.yatta.moe · lunaris.moe · ambr.top | databases, listed in [CREDITS.md](CREDITS.md#community-databases--resources). No public schedule/banner API was verified, so **banner names come from official notices or `config/overrides.json`** |

## Games not yet released

- **Honkai: Nexus Anima**:
  - **Status:** no release date as of 2026-09. Two closed betas have run, including the
    *Evolution Test* on Jul 9–27, 2026.
  - **Configured now:** HoYoLAB gid 9, X `@HonkaiNA`, and the HoYoLAB livestream-code module
    (`hoyolab:9`), all with `enabled: false`.
  - **Switching it on:** use `ENABLE_GAMES=hna`.
  - **At launch:** add the HoYoPlay `game_id`, YouTube/Twitch, and seria / Open Gacha Codes
    once they support it.
- **ANANTA** (NetEase):
  - **Status:** global launch **2027‑01‑15** on PS5 / PC / iOS / Android, announced at gamescom
    ONL 2026. X `@Ananta_EN` is configured.
  - **Switching it on:** it turns on by itself on that date (`auto_enable_on`), or earlier with
    `ENABLE_GAMES=ananta`.
  - **Banners:** it has no gacha character unlocking, so the card hides banners.
