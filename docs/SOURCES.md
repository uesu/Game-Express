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

Wuthering Waves (Kuro) and ANANTA (NetEase) have no HoYoLAB circle — WW is covered by the Kuro
official site / launcher + X + `r/WutheringWaves`, while ANANTA is covered by official X
(`@Ananta_EN`), verified official Reddit (`u/AnantaOfficial` + `r/AnantaOfficial`), and Fandom
(`ananta:Redemption_Code`), with NetEase / ANANTA CDN hosts (`easebar.com`, `anantagame.com`,
`netease.com`, `163.com`) allowlisted for media attachment downloads. `MAINTENANCE_GAMES=all`
expands to all 6 games (`ALL_MAINTENANCE_GAMES`: `genshin`, `starrail`, `zzz`, `wuwa`, `hna`,
`ananta`), whereas `NEWS_GAMES=all` covers the 5 games with structured official HoYoLAB / Kuro
news feeds (`DEFAULT_OPTIONAL_GAMES`). The HoYoLAB API is used rather than web pages because
it returns the same posts as structured JSON, with no HTML or JavaScript to scrape.
| HoYoLAB post (official) | `…/getPostFull?gids={gid}&post_id={id}` | full body (`content` HTML, or `structured_content` when `content == "en-us"`) + images | ✅ HSR 46814308 (quirk), GI 46604275 |
| c3kay JSON-Feed (mirror, fallback) | `https://feeds.c3kay.de/{genshin,starrail,zenless}.json` | JSON Feed 1.1 with full `content_html`, refreshed every 30 min | ✅ |
| Official X accounts | nitter RSS fleet `https://<instance>/<account>/rss` (27 entries, 26 live — `xcancel.com` is suspended; originally from News-Express round 13/14) | timeline (first 2 working instances merged) | fleet taken from News-Express |
| Tweet details | `https://nitter.cf/<account>/status/{id}/rss` (then `xitter.cf`, `teapawt.org`, `teapaw.org`, `teapawt.net`, `xitter.gq`, `nitter.gq`, when the account is known) → `https://api.fxtwitter.com/status/{id}` → `https://api.fixupx.com/status/{id}` → `https://api.vxtwitter.com/Twitter/status/{id}` | full text with expanded links, photos, exact timestamp; the winner is logged | ✅ all 4 reference tweets |
| Kuro official site (WW) | `https://hw-media-cdn-mingchao.kurogame.com/akiwebsite/website2.0/json/G152/en/{ArticleMenu,MainMenu}.json` + `…/article/{id}.json` | official articles incl. *Featured Resonator/Weapon Convene* banner notices; times are UTC+8 | ✅ (English menus are homepage **subsets**, so X stays primary for WW) |
| HoYoPlay launcher | `https://sg-hyp-api.hoyoverse.com/hyp/hyp-connect/api/getGameBranches?launcher_id=VYTpXlbWo8` | exact live version (`main.tag`) + pre-install availability (`pre_download`) | ✅ ZZZ `3.2.0` |
| Kuro launcher (WW) | `https://prod-alicdn-gamestarter.kurogame.com/launcher/game/G153/50004_obOHXFrFanqsaIEOmuKroCcbZkQRBC7c/index.json` + lazy `…/launcher/launcher/50004_…/G153/index.json` → `…/G153/background/{hash}/en.json` | live version (`default.version`), `predownload`, and global launcher `.mp4` / first-frame `.webp` on `aki-game.net` / `aki-game.com` | verified against real 2026 `G153` manifests (`0` extra requests on idle polls) |

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

The hot path has been re-ranked by live runs ever since; every rotation is dated in the comment
block above `DEFAULT_NITTER` in `gamexpress/config.py` and in `docs/changelog/`. Since rotation
#6 (2026-10-15) all four hot-path slots carry positive runner evidence: `nitter.cf` (6/6 handles,
every run), `xitter.cf` (the same machine as `nitter.cf`, an answerer across its whole tenure),
`nitter.meowing.monster` (6/6 in run #2323; listed IPv6-only on d420 while the runners are
IPv4-only, so it may lose a `NITTER_GRACE` race on a handle but never the quorum) and the
token-gated `nitter.miningtcup.me` (6/6). That round's ranking rule, which every later rotation
inherits: **no member that blocks GitHub Actions / Azure datacenter IPs sits above one that
doesn't.** Rotation #7 (2026-10-22) keeps all four runner-proven hosts in Batch 1 (`nitter.cf` and
`xitter.cf` untouched at slots 1–2, `nitter.meowing.monster`, `nitter.miningtcup.me`), seats four
8/8 union-verified mirrors across Batch 2 (`teapawt.org` 426 ms, `teapaw.org` 488 ms, `teapawt.net`
462 ms — official `.org`/`.net` sibling domains of `4cuck/teapawt` with explicit scraping permission
and `/status/<id>/rss` feeds — plus `nitter.mie.foundation` from `shitter/shitter`'s working list as
an independent `TRIAL`), and seats `xitter.gq` (450 ms) and `nitter.gq` (455 ms) from `status.d420.net`
at the head of Batch 3 ahead of `nitter.freedit.eu` (8/8) and `nitter.gravitywell.xyz` (5/8,
deterministic `User not found` gaps), all costing zero requests while the hot path is healthy.

Being polite about it matters: these are volunteer-run mirrors and `status.d420.de` asks
outright that they not be scraped. The design already keeps the cost low — the loop stops at
the first two answers, so a healthy run spends 2 requests per handle, not 27.

A mirror that stops answering is **demoted, never deleted**. `x.n0g.xyz` returned HTTP 404 then
429 on every handle in three consecutive live runs, so it sits at the very end of the fleet as a
backup instead of being cut — and because the loop above breaks once two instances have answered,
a demoted mirror costs no requests at all until the mirrors ahead of it degrade. The same applies
to `nitter.kareem.one`, `nitter.netbub.com`, `xcopy.uk`, `xcancel.com` and `x.yuuki.sh`: a host may
simply be blocking GitHub's runners while answering fine from a VPS — `nitter.kareem.one` and
`xcopy.uk` both serve a clean feed off-runner and answer the runners with HTTP 403 (xcopy on
24/24 fetches across four Azure regions, runs #2662–#2665, the trial verdict of 2026-10-15).

Single tweets are read **from nitter.cf first** when the account is known: `XClient.tweet()` asks the
nitter status feed (`nitter.cf`, `xitter.cf`, `teapawt.org`, `teapaw.org`, `teapawt.net`, `xitter.gq`, `nitter.gq`) for that post. FxTwitter is asked
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
| HoYoLAB livestream module (official) | `…/community/painter/wapi/circle/channel/guide/material?game_id={2,6,8,9}` → `data.modules[].exchange_group.bonuses[].exchange_code` | **official**: posts immediately | ✅ (empty outside livestreams, as expected) |
| hoyo-codes.seria.moe | `https://hoyo-codes.seria.moe/codes?game={genshin,hkrpg,nap}` | **redeem-validator** (`status: OK` = works, `NOT_OK` = counted as an *expired* flag) | ✅ 9 GI codes, all OK (2026-09-25) |
| Hum-Bao/hoyoverse-codes *(v1.1)* | `https://raw.githubusercontent.com/Hum-Bao/hoyoverse-codes/main/{GENSHIN,HSR,ZZZ}.txt` → jsDelivr mirror | **redeem-validator**: a daily job redeems every code on a US account and keeps only working ones | ✅ updated daily (~20:18 UTC) |
| Open Gacha Codes *(v1.1)* | `https://api.ennead.cc/codes/{genshin,starrail,zenless,wuwa}` | community (**confirming only**: noisy, includes glued-together and stale codes, which are filtered) | ✅ incl. Wuthering Waves |
| api.ennead.cc (legacy) | `https://api.ennead.cc/mihoyo/{genshin,starrail,zenless}/codes` (`active` → active, `inactive` → *expired* flag) | community, **same backend as Open Gacha Codes = counted as one source** | ✅ |
| wuthering.gg *(v1.1)* | `https://wuthering.gg/codes` (HTML table: code · COPY/Expired · rewards · date) | community (WW), provides **expired** flags | ✅ (only WUTHERINGGIFT active on 2026-09-25) |
| Fandom wikis (MediaWiki API, all 6 games) | `https://{wiki}.fandom.com/api.php?action=query&prop=revisions&titles={page}&rvprop=content&rvslots=main&format=json` | community. Expired rows and **passed *valid until* dates** give an *expired* flag; a passed date beats every other source *(v1.1.1)*; cited `<ref>…</ref>`, `{{Code\|…}}`/`{{Copy\|…}}` templates, and multi-line VisualEditor cells parse cleanly | ✅ **all six wikis configured** — GI `Promotional_Code` · HSR `Redemption_Code` · ZZZ `Redemption_Code` · WW `Redemption_Code` · HNA `Redemption_Code` · ANANTA `Redemption_Code`. GI's live `Active Codes` section is pinned as a fixture (11 codes, CN-only `YuanShen` dropped, `VesnaOnPatrol` normalised to upper case) |
| PromoGacha data | `https://raw.githubusercontent.com/gripcrip-blip/codehub/main/data/codes.json` → jsDelivr mirror | **aggregator**: every entry says where it was copied from (`hoyo-codes` = seria, `Fandom Wiki` = fandom, `Open Gacha Codes` / `api.ennead.cc` = ennead), and entries are never removed. It counts as that upstream — never as an extra independent source — and stale copies are ignored *(v1.1.1)* | ✅ |
| Reddit community listings (`reddit:<Subreddit>`) | `/r/{Genshin_Impact,HonkaiStarRail,ZZZ_Official,WutheringWaves,HonkaiNexusAnima,AnantaOfficial}/new` via `REDDIT_FEED_TOKEN` (`www.reddit.com` → `old.reddit.com`) or `DEFAULT_REDDIT` | **community witness** (`SOURCE_FAMILY["reddit"] = "reddit"`): never posts alone; corroborates pending codes alongside an independent second family (`CODES_MIN_SOURCES = 2`) | ✅ all 6 subreddits live-verified (`2026-10-22`) |
| Official posts | X / HoYoLAB / official Reddit text that explicitly lists "Redemption Codes" | **official**: posts immediately | extraction tested on real tweets & OP comments (no false positives) |

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
| 6 | **Reddit official backup** *(v2.1)* | Redlib dual-path HTML (`/user/<account>` + `/r/<sub>/new` + `/r/<sub>/comments/<id>/`) + JSON/HTML proxy chain | clean backup when X / HoYoLAB / official site miss; upgrades automatically once X returns |

**Reddit / Redlib fleet & trust separation (`gamexpress/sources/reddit.py` + `gamexpress/config.py`, `2026-10-24`):**

- **Tier 1 — Active healthy dual-path + token-gated tier (`9` hosts — Batch 1 + dual-path backups, zero unauthenticated `403` waste on GitHub Actions):** `https://redlib.mint.lgbt` (Redlib `0.36.0` `0baefabf` Shreddit build, full `/new` + `/user/` + `/comments/`), `https://reddit.idevicehacked.com` (Redlib `0.40.0` `848f3013`, full `/new` inline gallery + `/user/` + `/comments/`), `https://redlib.reallyaweso.me` (full `/new` + `/user/` + `/comments/` `200 OK` with multi-image galleries), `https://redlib.catsarch.com`, `https://snoo.habedieeh.re` (Redlib `v3.0.0`, `/new` + `/user/` + `1080p` CMAF), token-gated `https://redlib.miningtcup.me` (`NITTER_RSS_TOKEN`), `https://redlib.tiekoetter.com`, `https://redlib-1.privadency.com`, and `https://redlib-2.privadency.com`.
- **Tier 2 — Verified `/new` (+ `/user/`) listing-only tier (`7` hosts — skipped on `/comments/` in `REDDIT_LISTING_ONLY`):** `https://redlib.ducks.party` (`v0.40.0` `/new` listing with inline gallery carousels; skipped on `/user/` via `REDDIT_SUB_LISTING_ONLY`), `https://reddit.jeremyh.xyz` (`redlib-instances#118`), `https://redlib.jeikobu.net` (`0.36.0`), `https://red.artemislena.eu`, `https://rl.awy.one`, `https://redlib.freedit.eu`, and `https://redlib.utilibre.org`.
- **Tier 3 — Token-promoted official origins & demoted/legacy tail (`8` hosts — placed strictly last so healthy runs make `0` tail requests, nothing deleted):** `https://www.reddit.com` (promoted to slot `0` with `?feed=` when `REDDIT_FEED_TOKEN` is set; unauthenticated Actions IPs otherwise receive `403`), `https://old.reddit.com`, `https://redlib.vanillax.me` (demoted on `2026-10-24` after HTTP `200` `The backend server is having issues` error body), `https://redlib.privacyredirect.com` (demoted from slot `#2` on `2026-10-23` after upstream `403` error page on `/comments/` & `/user/`), and degraded legacy mirrors (`https://eddrit.com`, `https://redlib.privadency.com`, `https://safereddit.com`, `https://redlib.nadeko.net`).
- **Verified publisher accounts vs community subreddits (`config/games.json`):** `genshin` (`u/genshinimpact`, `r/Genshin_Impact`), `starrail` (`u/HonkaiStarRail`, `r/HonkaiStarRail`), `zzz` (`u/ZZZ_Official`, `r/ZZZ_Official`), `wuwa` (`official: []`, `r/WutheringWaves` — `u/WutheringWaves` on live Reddit is an unrelated 2022 squatter account, and `Item.official` on subreddit fallbacks requires `is_verified_reddit_author()` rather than a public user-selectable flair), `hna` (`u/HonkaiNexusAnima`, `r/HonkaiNexusAnima`), and `ananta` (`u/AnantaOfficial`, `r/AnantaOfficial`). Verified publisher/moderator Reddit code hits carry source `"reddit_official"` (`verified=True`, rendered as `Official Reddit` on code cards), while community `reddit:<sub>` code hits remain unverified (`SOURCE_FAMILY["reddit"] = "reddit"`, rendered as `Reddit`) and require independent second-family corroboration (`CODES_MIN_SOURCES = 2`). Schedule and item provenance labels render `"reddit"` / `reddit.com` links accurately as `"Reddit"`.
- **Single-post JSON/HTML proxy chain (`DEFAULT_REDDIT_PROXIES`):** `https://www.vxreddit.com` → `https://embedez.com` → `https://embeddit.deltandy.me` (supporting both Mastodon-style JSON/OpenGraph metadata and v2 `<script id="discord:component-embed" type="application/json">` HTML embeds, preferring muxed video+audio streams over un-muxed `v.redd.it` video streams), with `https://arctic-shift.photon-reddit.com` as last-resort archive lookup.

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
| `pbs.twimg.com/media/X?format=jpg&name=large` | preserved as-is (`twimg_orig` never rewrites an explicit size), while `_same_file()` & `rank()` deduplicate it against `X.jpg?name=orig` and pick `name=orig` when both appear |
| `nitter.<instance>/pic/media%2FX.jpg` | `https://pbs.twimg.com/media/X.jpg?name=orig` |
| `i.ytimg.com/vi/ID/hqdefault.jpg` | `…/maxresdefault.jpg` (1280×720 instead of 480×360) |
| `fastcdn.hoyoverse.com/content-v2/…` | unchanged — already the full-size article cover |

Ranking puts the program's own artwork first: a livestream thumbnail, then a full-size tweet
photo, then an article cover. Nothing is ever rewritten to a host the source did not give us.

**The third `Watch` button** (`cards.py`) is automatic and game-agnostic: the first two buttons
are always the game's *channel* pages (Youtube, Twitch), and when the announcement post itself
links one specific livestream video — HSR 4.6 and WW 3.7 carried `youtube.com/live/…` — a
`Watch` button for that video is added. Genshin 7.1 and ZZZ 3.3 announced their programmes
without a link in the post, so their cards have no third button; nothing is missing. The card's
title always links the announcement post itself, never the stream.

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
- The same reader also knows the ZZZ X dialect, where the quoted string is the channel and the
  bare word the agent (`S-Rank Agent Phoenix Signal Search "Into the Flames of Life"`): a bare
  name ends where the game's gacha-mode phrase begins (`CHANNEL_MODE`), so a quoted channel
  title is never published as a character (2026-10-09; see
  [BANNER_DATABASE.md → How an official notice is read](BANNER_DATABASE.md#how-an-official-notice-is-read-extract_banner)).
  The hub did not know the 3.3 channel titles yet, so its cross-check could not catch the first
  wrong reading — the parser fix is the repair, and the card healed by re-reading the same posts.

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
**no** ZZZ 3.3 HoYoLAB post existed on 2026-10-09; Star Rail 4.6 Phase II stays hub/calendar-sourced and unlocked.
ZZZ 3.3's names come from the official X channel tweets instead — `ZZZ_EN` posted
`V3.3 Limited-Time Channels (Phase I)` (`2108524400761061839`) and `(Phase II)` (`2108524541022818638`) at
11:46 UTC on 2026-10-09, read through the nitter timeline and verified against `api.fxtwitter.com` and
`api.vxtwitter.com` the same day. The bot read the quoted channel titles as the agents until the
`CHANNEL_MODE` fix later that day; the tweets now yield Phoenix, Velina and Severian, Norma.

The sandbox cannot reach `bbs-api-os.hoyolab.com` with `curl` (TLS reset); the endpoint was checked through the
page fetcher, and so were the ennead calendars. The production reachability of the search endpoint is therefore verified only by the first live run
(see the log line below), and the `getNewsList` fallback covers it if the search is refused.

**Evaluated on 2026-10-09 (requested by the operator's links):**

- **`torikushiii/hoyoverse-api`** (Rust, AGPL-3.0; public instance `api.ennead.cc/mihoyo`). Its `/mihoyo/{game}/calendar`
  endpoints return the in-game event calendar with banners: `version`, the characters or weapons, and start and end times.
  Checked through the page fetcher: `genshin/calendar`, `starrail/calendar` and `zenless/calendar` all answer. The
  root `/mihoyo` lists only the code endpoints, so the calendar is not in its endpoint list.
  - **Used since 2026-10-09** as a banner source (`sources/calendarfeed.py`): 5★ and 4★ (A-rank) names per phase,
    names only, asked on the title-search budget. Any two of hub, calendar and wiki that agree lock a name.
  - Genshin 7.1 Phase I: both banners (`Character Event Wish` Vesna, `Character Event Wish 2` Vodyanitsa; Diona, Faruzan, Chongyun at 4★) match the post. End 2026-10-13 17:59 UTC+8, matching the post.
  - ZZZ 3.2 Phase II (Roxy, Promeia; Corin, Billy): start 2026-09-30 12:00 and end 2026-10-20 14:59 UTC+8, matching the post.
  - Star Rail 4.6: Pearl and Evanescia, and the Qingque/Xueyi/Misha 4★ lists match the posts. **Mortenax Blade (4.6 Phase II) is already listed** with start 1792580400 (2026-10-21 19:00 UTC+8, the same stamp as the hub). Star Rail stamps run about 7 hours later than the posts' "server time".
  - ZZZ 3.3 Phase I **is listed** (checked 2026-10-09, after the channel tweets): Phoenix and Velina at S-rank, Seth and Manato at A-rank, starting 1792544400 — the names the X tweets gave, plus the 4★ pair the tweets do not carry. Phase II is not listed yet.
  - Not yet listed on 2026-10-09: Genshin 7.1 Phase II.
  - **Status: integrated via `sources/calendarfeed.py` (`PRIORITY["calendar"] = 7`).** Counted as one of the three independent confirmation groups alongside `feed` (`hub.json`) and `wiki` (`gachawiki.py`).
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
| DuolaD/HoYo_Versioncatcher | launcher-data repo; led us to the HoYoPlay launcher endpoints |
| TwintailTeam/game-manifests · TomyJan/GenshinImpact-Client-Version | launcher-manifest repos documenting Kuro's `G153` global launcher index and `background/{hash}/en.json` schemas (`sources/kuro.py`) |
| genshin.dev | character/game data API, not schedules or codes |
| gachabase.net · nanoka.cc · sr.yatta.moe · lunaris.moe · ambr.top | databases, listed in [CREDITS.md](CREDITS.md#community-databases--resources). No public schedule/banner API was verified, so **banner names come from official notices, `Kitsudock-data` (`hub.json`), the `api.ennead.cc` calendars, the Fandom wikis, or `config/overrides.json`** |

## Reddit & Redlib fleet (2026-10-22)

`sources/reddit.py` integrates Reddit and Redlib across all six configured games (`r/Genshin_Impact` / verified `u/genshinimpact`, `r/HonkaiStarRail` / verified `u/HonkaiStarRail`, `r/ZZZ_Official` / verified `u/ZZZ_Official`, `r/WutheringWaves` with `official: []` because live `u/WutheringWaves` is an unrelated 2022 squatter account, `r/HonkaiNexusAnima` / verified `u/HonkaiNexusAnima`, and `r/AnantaOfficial` / verified `u/AnantaOfficial`) under strict role separation and zero-waste request discipline:

- **Official publisher accounts (`game.reddit_official`)** act purely as a failover backup for `schedule` and `codes` (`PRIORITY["reddit"] = 38`, `LOCK_RANK["reddit"] = 1`): when X and primary APIs (`HoYoLAB`/`Kuro`) succeed on a game, `_gather_game()` makes **`0` `/user/<official>` HTTP requests**; if either degrades, it fails over in the same run automatically, merges same-author comments under image posts, rewrites `/img/` / `/preview/` / `/vid/` paths back to permanent `redd.it` URLs, and upgrades back to X as soon as X recovers.
- **Community subreddit listings (`reddit:<Subreddit>` in `codes.sources`)** emit unverified `CodeHit(code, "reddit", None)` witnesses (`family("reddit") == "reddit"`). A single unverified community post never passes `CODES_MIN_SOURCES = 2` alone (`status = "pending"`), while providing a fast second independent witness alongside `fandom`, `seria`, `humbao`, `ennead`/`ogc`, or `wuthering.gg` (including pre-launch `hna` and `ananta`). When `REDDIT_FEED_TOKEN` is set in Secrets, both `/r/<sub>/new.rss` and `/user/<acct>/submitted.rss` use a **1-request direct `[0] www.reddit.com` → `[1] old.reddit.com` fast path** plus circuit-broken `.json` fallback (`0` Redlib mirror hits unless first-party Reddit fails).
- **Ordered `DEFAULT_REDDIT` fleet (`24` entries, `REDDIT_BATCH = 3`, stopping at `REDDIT_WORKING = 2` answers):**
  1. Tier 1 — Active healthy dual-path + token-gated tier (`[0..8]`, zero unauthenticated `403`s on GitHub Actions IPs): `https://redlib.mint.lgbt` (`0.36.0` `0baefabf` Shreddit scraper), `https://reddit.idevicehacked.com` (`0.40.0` `848f3013`), `https://redlib.reallyaweso.me`, `https://redlib.catsarch.com`, `https://snoo.habedieeh.re`, token-gated `https://redlib.miningtcup.me` (`NITTER_RSS_TOKEN`), `https://redlib.tiekoetter.com`, `https://redlib-1.privadency.com`, `https://redlib-2.privadency.com`.
  2. Tier 2 — Verified `/new` (+ `/user/`) listing-only tier (`[9..15]`, skipped on `/comments/` lookups via `REDDIT_LISTING_ONLY`): `https://redlib.ducks.party` (`v0.40.0`, skipped on `/user/` via `REDDIT_SUB_LISTING_ONLY`), `https://reddit.jeremyh.xyz`, `https://redlib.jeikobu.net`, `https://red.artemislena.eu`, `https://rl.awy.one`, `https://redlib.freedit.eu`, `https://redlib.utilibre.org`.
  3. Tier 3 — Token-promoted official origins & demoted/legacy fallback tail (`[16..23]`, placed strictly last — zero requests while Tier 1 answers; nothing deleted): `https://www.reddit.com` (promoted to slot `0` 1-request fast path when `REDDIT_FEED_TOKEN` is set), `https://old.reddit.com`, `https://redlib.vanillax.me` (demoted on `2026-10-24` after HTTP `200` `The backend server is having issues` error body), `https://redlib.privacyredirect.com` (demoted on `2026-10-23` after upstream `403` error page), `https://eddrit.com`, `https://redlib.privadency.com`, `https://safereddit.com`, `https://redlib.nadeko.net`.
  4. Newly discovered candidates that were runner-refused (`403`), challenge-walled, JS-interstitial (`Still trying to load your page…`), `502`/`503` / clearnet-discontinued, duplicate `302` aliases, spoofs, honeypots, or non-JSON SPA viewers were excluded completely and are never added to `DEFAULT_REDDIT`.
- **`DEFAULT_REDDIT_PROXIES` (`Discordbot/2.0` rich-embed chain):** `https://www.vxreddit.com` (muxed video+audio primary) -> `https://embedez.com` (`proxy.embedez.com` 1080p audio-muxed fallback) -> `https://embeddit.deltandy.me` (supports both live v1 Mastodon `/api/v1/statuses/<id>` JSON and the still-unfinished v2 `<script id="discord:component-embed" type="application/json">` format, keeping raw un-muxed `v.redd.it` fallback video behind `vxreddit` and `embedez`), with `https://arctic-shift.photon-reddit.com` retained only as a last-resort JSON archive fallback.

## Games not yet released

- **Honkai: Nexus Anima**:
  - **Status:** pre-release (`enabled: true, released: false` since `2026-10-02` so pre-launch Special Programs are caught immediately). Two closed betas have run, including the *Evolution Test* on Jul 9–27, 2026.
  - **Configured now:** HoYoLAB gid 9, X `@HonkaiNA`, official Reddit `u/HonkaiNexusAnima`, HoYoLAB livestream-code module (`hoyolab:9`), Fandom `honkai-nexus-anima/Redemption_Code`, `reddit:HonkaiNexusAnima` community witness, and HoYoLAB official news (`NEWS_GAMES` slot `hna`).
  - **At launch:** flip `released` to `true`, set `four_star_count`, and add HoYoPlay `game_id`, YouTube/Twitch, and seria / Open Gacha Codes once they support it.
- **ANANTA** (NetEase):
  - **Status:** global launch **2027‑01‑15** on PS5 / PC / iOS / Android, announced at gamescom ONL 2026 (`enabled: true, released: false`, with `auto_enable_on: "2027-01-15"` retained as a safety net).
  - **Configured now:** X `@Ananta_EN`, official Reddit `u/AnantaOfficial`, Fandom `ananta/Redemption_Code`, and `reddit:AnantaOfficial` community witness.
  - **Banners:** it has no gacha character unlocking, so the card hides banners.


## Optional full-content news adapter (2026-10-18)

News reuses the configured HoYoLAB gids 2 / 6 / 8 / 9 and the **official**
`getNewsList` tabs 1/3/2, then `getPostFull`. It never takes a community search
result or truncated list preview as an article. All three tab reads must be
valid before establishing a baseline. Discovery is bounded to three pages of
20/tab with `last_id`, stopping when the trailing row passes the publication
window; an ignored/repeated cursor or still-in-window saturated final page fails
closed and warns rather than asserting complete coverage. Unknown/malformed
responses retry without advancing a checkpoint.

Wuthering Waves reads the English official `MainMenu.json` `article` index and
full `article/{id}.json`. This matches RSSHub's current English adapter. The
index is a **current homepage subset**, not a guaranteed complete historical
archive; unlisted official articles cannot be discovered by this adapter. The
optional schedule/banner mirrors are not silently promoted to news authority.
Publication time uses the official index's UTC+8 `startTime`, falling back to
`createTime` only when `startTime` is absent or empty.

Full HTML/Quill blocks retain text/media order and heading/list readability.
First try one full message. Multiple containers share the message-wide 4,000
text-character / 40-component limits. On overflow, <=7,000 normalized characters
may use at most two independently validated pages; otherwise send one labelled
excerpt container, at most one lead image, and Read Post for the full original.
Overflow keeps half the words of the already budget-fitting opening excerpt;
fitting articles are not shortened. Normalize line-leading `●`/`•` (including
bold-wrapped markers) to Markdown `- ` bullets; do not replace symbols mid-prose.
Retain descriptive HTML/Quill links as one masked link, and bare/self-labelled
URLs as bare URLs; URL fields are never Markdown-wrapped. Quill heading conversion
must retain its preceding newline so the prior link cannot absorb the heading.
Fallback publisher label is the configured game name only when nickname is absent.
Balance adjacent/nested HTML bold spans, including across media boundaries, so
Markdown markers do not leak into the message. Pad a closing `✦` when it touches
the preceding word, without changing already-spaced markers.
Add a space after unpadded `※`/`✦`, but add blank lines only between consecutive
`※` note paragraphs. Consecutive `-` bullets stay compact. Uninterrupted media
runs do not split at the eight-unit readability threshold. By default individual
galleries remain unchanged. Optional backend measured grouping is described below;
source order remains unchanged. No cropping/slicing or repeated per-image warnings. Three custom-emoji
buttons appear only in the final container; unknown publication times are omitted.
GIFs stay GIFs; direct MP4/WebM use galleries; external players/HLS remain source
links. Explicit HoYoLAB cover metadata supplies a separate opening banner when
available; a trimmed fixture with no cover metadata is not complete-cover evidence.

Included direct media receives a bounded HTTPS GET/status/MIME/magic-byte check
using official host families, with redirect validation. URLs/queries are preserved.
HTTP 403, 200 XML/HTML error bodies and unrecognised media signatures fail closed.
A failure triggers one fresh official full-article fetch and rerender, then a
second preflight. If unresolved, hold for retry with an operational warning; do
not post a broken gallery or mark it delivered. No guessed filename, arbitrary
proxy, screenshot substitute, manual article-specific correction or new dataset.
This checks a short response prefix, not the complete media file or Discord's
ability to fetch/play it. Native VOD still chooses the highest supplied resolution.
Unsupported host/signature/codec cases can defer and need runner evidence before
expanding the allowlist. Empty/mismatched full articles and unsafe metadata defer.
Legacy multipart signatures changed by this layout are held, not replayed.

Verification here: existing captured GI full-post fixture plus synthetic HNA,
Quill/video and Kuro-shape fixtures; read-only RSSHub source and Wuthering Waves
mirror HTML inspection. Official HoYoLAB/Kuro hosts are not reachable from this
sandbox, so current HNA feed behavior, official full-media availability and actual
Discord playback **are not live-verified**. Do not interpret earlier source-table
checkmarks as verification of this new feature. Before enabling a production
copy, obtain read-only source evidence from that runner; posting/state resets or
deployment still require separate approval. HuTao and Tausendsassa were references,
not replacements for Game-Express; no pre-delivery seen marking or description
truncation was copied from them.


### User-supplied web and media evidence (2026-10-18)

Thirteen supplied browser screenshots show the Official Info/Events/Notices
pages for GI (2/27), HSR (6/39), ZZZ (8/47), and HNA (9/90002), plus Kuro's
English news page. This establishes visible HNA official-page content and the
intended web scope; it does not independently verify getNewsList/getPostFull
responses, event metadata shapes, pagination, or full-body retrieval.
The API mapping remains Info/news=3, Events=2, Notices=1 in this implementation.

The user also confirmed Discord display of ten supplied Kuro media URLs
(three JPGs and seven GIFs) associated with article 5644. A regression test
validates preserving those exact URLs/order in Components V2 payloads without
converting GIFs to stills. That is payload validation plus user-reported media
playback, not an automated Discord-posting or official article-fetch test.
Article 5644 was not available in the inspected GitHub mirror tree, and the
sandbox cannot contact the official Kuro/CDN hosts. Therefore direct retrieval
and full article-to-delivery behavior for 5644 remain untested here; do not
confuse the earlier mirrored-article 5625 parser test with this article.


## Current official-news paging policy (supersedes earlier one-message-only wording)

Keep fitting full articles unchanged in one message (possibly multiple containers).
By default (`NEWS_EXPAND_FULL=0`), if that fails, permit at most two actual messages
when normalized source text plus title/byline once is <=7,000 characters and both
payloads validate independently against 4,000 text characters / 40 components /
1–10 gallery items (setting `NEWS_EXPAND_FULL=1` lifts that ceiling up to an explicit
`12`-page / `120,000`-character / `120`-media cap before excerpt fallback).
Preserve complete wording and source media order. Prefer source block boundaries;
use safe paragraph boundaries only for larger text blocks. Never split a link or
unbalanced bold span. If packing fails, use the existing one-container excerpt
with at most one lead image; never publish a partial full-article proposal.
Paged messages: title/byline and lead only once at the start, then Page 1 / Page 2
labels and dividers; three custom-emoji buttons only at the end of the final
message. One-message articles also put buttons in the final container. Articles
above the ceiling or unpageable within two messages keep the approved half-fitting
word excerpt. Never truncate fitting full articles or modify official API HTML.
Retain confirmed per-message progress, no-repost handling, media preflight and
refresh/holds. No new scheduler or delivery-state reset. Historical incomplete
captures are not full-source length evidence. Pagination is tested across all
five game keys with synthetic boundary inputs, not five live integrations.


### Latest layout corrections: 7,000 eligibility / final-container controls

This is the current rendering rule across all five games. The eligibility ceiling
is now 7,000 normalized source-text characters including title/byline once, with
at most two actual Discord messages; every message must independently validate
against the unchanged 4,000 text-character and 40-component caps. Failure to fit
safely in two messages still uses the existing one-container/one-lead excerpt.
All three custom-emoji buttons appear only at the end of the final container of
the final message, including one-message/multi-container articles. Keep Part 1/2
and Part 2/2 for containers in one message, Page 1/Page 2 for separate messages.
Compact consecutive square (■) entries like numbered lists. HTML list items
containing nested paragraphs must keep '- ' attached to their first visible text;
the policy. Source HTML/API/mirror responses and media URLs remain untouched.
Schedule classification/mirrors never suppress eligible official news articles, while
existing `"status": "posted"` records and `floor` watermarks prevent historical backfill.
The one integrated HTML contains the main previews and complete browser-only
long-strip laboratory; optional backend grouping is implemented below.


### Optional measured long-strip grouping — implemented

`NEWS_GROUP_LONG_STRIPS=0` (default) keeps article-order galleries exactly as before,
with no measurement requests. Set repository Variable `NEWS_GROUP_LONG_STRIPS=1`
to enable the backend grouping pass for all five official-news game keys. This
setting does not enable news, change destinations, or affect schedule/codes.
The existing workflow imports repository Variables; no workflow edit is needed.

After normal media availability preflight and any one official refresh, read
original PNG/GIF/JPEG/WebP header dimensions using allowlisted HTTPS GETs only:
at most four request hops, 8 seconds total per measurement, 256 KiB per response,
at most 40 distinct URLs and 20 seconds total per article. Reads stop as soon as
header dimensions are known; no decoding, transformation, upload or dependency.
Unsupported/truncated formats (including video/AVIF), failed/unknown dimensions,
or the article measurement deadline keep the original layout without holding an
otherwise deliverable article. All included media must have known dimensions.
Normal availability failure still holds/retries independently of this option.

A qualifying strip has height/width strictly greater than 3.5. Merge only runs of
at least two consecutive single-item galleries inside the same container, up to
ten items per grouped gallery. Insert a divider before each group unless one
already precedes it. A measured long-strip lead may join an adjacent qualifying
run; normal-aspect leads/final images remain separate. Do not cross text, existing
separators, containers, messages, or existing multi-item galleries. Mixed GIF/image
runs retain exact source item fields, bytes (never downloaded in full for editing),
URLs, duplicates and order. No article-specific exemptions or guessed dimensions.

Validate every proposed message against 4,000 text characters / 40 components /
1–10 gallery items and verify flattened media URL order/count; otherwise retain
the original layout. Do not repack pages or modify titles, Part/Page labels,
final-container buttons, full-content eligibility or the one-lead overflow excerpt.
The existing partial-delivery signature guard holds changed layouts for manual
review rather than replaying already confirmed pages. Do not toggle layout modes
mid-partial delivery without reviewing that hold. No state reset or old-post edits.
Discord controls thumbnail cropping; neither header measurements, HTML previews
nor passing offline tests prove live media decoding/readability or delivery.


## Structured launch media for Pre-Load & Maintenance Started (2026-10-21)

When `MAINTENANCE_ENABLED=1` and a game is explicitly listed in `MAINTENANCE_GAMES`,
`gamexpress/maintenance.py` resolves optional launch media from structured official
endpoints and existing caches only (never headless browsers or HTML scraping):

| Game(s) | Structured source | Priority assets & safeguards |
|---|---|---|
| GI / HSR / ZZZ / HNA | HoYoPlay `getAllGameBasicInfo` (`hyp-api.hoyoverse.com`) + existing HoYoLAB / X Special Program cache | (1) version-matched `.webm`/`.mp4` background clip, (2) version-matched `.webp`/image background, (3) `overrides.json` / Special Program key art, (4) omit gallery; version/launch lock separates selected tier so late launch video upgrades initial artwork inside `LATE_MEDIA_EDIT_WINDOW_S` (including opaque shortlink `bg["id"]` rotations within `[-11d, +7d]`) while blocking prior-version and Phase II swaps |
| Wuthering Waves | Kuro global launcher `G153/index.json` + lazy `background/{hash}/en.json` (`aki-game.net` / `aki-game.com` `.mp4` + `firstFrameImage` `.webp`) + structured website/article JSON (`hw-media-cdn-mingchao.kurogame.com`) + Special Program X/Kuro art | (1) version-matched `.mp4` clip keeping signed `?auth_key=…` query parameters intact and rejecting prior-version URLs when `en.json` lags behind `default.version`; signed URLs expire and renew inside `LATE_MEDIA_EDIT_WINDOW_S` (`6 h` / `21,600 s`, `MAX_LATE_MEDIA_ATTEMPTS = 3` consecutive failed `PATCH` calls reset on `res.ok`, `MAX_LATE_EDITS = 6` total succeeded `PATCH` calls, per-run URL check deduplication) only when corroborating source metadata (`hash`/`md5`/`size`+`full_version`) binds the exact launch asset (never bare host/path alone), otherwise falling back to (2) matching-version artwork, (3) `overrides.json` / Special Program key art, or (4) cleanly omitting media without durable mirroring |
| ANANTA | Official X (`@Ananta_EN`) + verified official Reddit (`u/AnantaOfficial`) + `config/overrides.json` / `program_announcements.json` (`easebar.com`, `anantagame.com`, `netease.com`, `163.com`, `pbs.twimg.com`, `redd.it` allowlisted) | Tier 3 (`overrides.json` `image` pin → Special Program / launch key art) → Tier 4 clean gallery omission until NetEase publishes a structured global launcher background API |
