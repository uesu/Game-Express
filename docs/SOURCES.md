# Data sources — what is used, why, and how it was verified

Everything marked ✅ was **fetched live on 2026-09-25** while building v1.0. The response
shapes are pinned by the fixtures in `tests/fixtures/`. Every source is optional at runtime:
a dead source is logged and skipped, and the next one in the chain is used.

## Schedule & announcements

| Source | Endpoint | Gives | Status |
|---|---|---|---|
| HoYoLAB news list (official) | `https://bbs-api-os.hoyolab.com/community/post/wapi/getNewsList?gids={2,6,8,9}&page_size=15&type={1,2,3}` | titles + truncated text of Notices (1) / Events (2) / Info (3) | ✅ found "Version 4.6 Update and Maintenance Notice" |
| HoYoLAB post (official) | `…/getPostFull?gids={gid}&post_id={id}` | full body (`content` HTML, or `structured_content` when `content == "en-us"`) + images | ✅ HSR 46814308 (quirk), GI 46604275 |
| c3kay JSON-Feed (mirror, fallback) | `https://feeds.c3kay.de/{genshin,starrail,zenless}.json` | JSON Feed 1.1 with full `content_html`, refreshed every 30 min | ✅ |
| Official X accounts | nitter RSS fleet `https://<instance>/<account>/rss` (15 instances, from News-Express round 13/14) | timeline (first 2 working instances merged) | fleet taken from News-Express |
| Tweet details | `https://api.fxtwitter.com/status/{id}` → `https://api.fixupx.com/status/{id}` → `https://api.vxtwitter.com/Twitter/status/{id}` | full text with expanded links, photos, exact timestamp; the winner is logged | ✅ all 4 reference tweets |
| Kuro official site (WW) | `https://hw-media-cdn-mingchao.kurogame.com/akiwebsite/website2.0/json/G152/en/{ArticleMenu,MainMenu}.json` + `…/article/{id}.json` | official articles incl. *Featured Resonator/Weapon Convene* banner notices; times are UTC+8 | ✅ (English menus are homepage **subsets**, so X stays primary for WW) |
| HoYoPlay launcher | `https://sg-hyp-api.hoyoverse.com/hyp/hyp-connect/api/getGameBranches?launcher_id=VYTpXlbWo8` | exact live version (`main.tag`) + pre-install availability (`pre_download`) | ✅ ZZZ `3.2.0` |
| Kuro launcher (WW) | `https://prod-alicdn-gamestarter.kurogame.com/launcher/game/G153/50004_obOHXFrFanqsaIEOmuKroCcbZkQRBC7c/index.json` | live version (`default.version`) + `predownload` | structure from WW downloader configs |

HoYoLAB game IDs: 1 HI3 · 2 Genshin · 6 Star Rail · 8 ZZZ · **9 Honkai: Nexus Anima** (already
wired for launch day).

**Why `getGameBranches` and not `getGamePackages`:** the legacy package list is stale for games
that moved to Sophon downloads. On 2026-09-24 it still reported GI 5.5.0 while the live game was
7.1.

## X (Twitter) fetching — no X API account

Timelines come from the public nitter fleet, with `nitter.cf` and `xitter.cf` first. Four
instances are probed in parallel and the first two that answer are merged; a mirror returning
HTTP 200 with zero entries is treated as a bot check and skipped. The token-gated
`https://nitter.miningtcup.me/` mirror alone needs `NITTER_RSS_TOKEN`.

Tweet data uses the fallback chain **fxtwitter → fixupx → vxtwitter**. FxTwitter and fixupx are
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
| Fandom wikis (MediaWiki API) | `https://{wiki}.fandom.com/api.php?action=query&prop=revisions&titles={page}&rvprop=content&rvslots=main&format=json` | community. Expired rows and **passed *valid until* dates** give an *expired* flag; a passed date beats every other source *(v1.1.1)* | ✅ all three table formats re-checked 2026-09-25 (GI multi-code rows, HSR `{{Item List}}` rows, WW wikitable with `Valid until: … (PT)`) |
| PromoGacha data | `https://raw.githubusercontent.com/gripcrip-blip/codehub/main/data/codes.json` → jsDelivr mirror | **aggregator**: every entry says where it was copied from (`hoyo-codes` = seria, `Fandom Wiki`), and entries are never removed. It counts as that upstream, and stale copies are ignored *(v1.1.1)* | ✅ |
| Official posts | X / HoYoLAB text that explicitly lists "Redemption Codes" | **official**: posts immediately | extraction tested on real tweets (no false positives) |

## Official news pages + media (v1.3.0 — the announcement's own link and key art)

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
is the lowest priority in the monitor, so an estimate is used only when no official source has
given that time, and it is replaced — with the 🕒 line on the card — the moment the official
notice is seen. `COUNTDOWN_ESTIMATES=0` switches the feature off.

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
| gachabase.net · nanoka.cc · sr.yatta.moe · lunaris.moe · ambr.top | databases, listed in README → resources. No public schedule/banner API was verified, so **banner names come from official notices or `config/overrides.json`** |

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
