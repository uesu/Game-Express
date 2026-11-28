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
| Official X accounts | nitter RSS fleet `https://<instance>/<account>/rss` (28 entries, 27 live — `xcancel.com` is suspended; originally from News-Express round 13/14) | timeline (first 2 working instances merged) | fleet taken from News-Express |
| Tweet details | `https://nitter.cf/<account>/status/{id}/rss` (then `xitter.cf`, `teapawt.org`, `teapaw.org`, `teapawt.net`, `xitter.gq`, `nitter.gq`, when the account is known) → `https://api.fxtwitter.com/status/{id}` → `https://api.fixupx.com/status/{id}` → `https://api.vxtwitter.com/Twitter/status/{id}` | full text with expanded links, photos, exact timestamp; the winner is logged | ✅ all 4 reference tweets |
| Kuro official site (WW) | `https://hw-media-cdn-mingchao.kurogame.com/akiwebsite/website2.0/json/G152/en/{ArticleMenu,MainMenu}.json` + `…/article/{id}.json` | official articles incl. *Featured Resonator/Weapon Convene* banner notices; times are UTC+8 | ✅ (English menus are homepage **subsets**, so X stays primary for WW) |
| HoYoPlay launcher | `https://sg-hyp-api.hoyoverse.com/hyp/hyp-connect/api/getGameBranches?launcher_id=VYTpXlbWo8` | exact live version (`main.tag`) + pre-install availability (`pre_download`) | ✅ ZZZ `3.2.0` |
| HoYoPlay maintenance gate (GI / HSR / ZZZ) | `https://sg-cg-api.hoyoverse.com/hk4e_global/cg/gamer/api/getGlobalApplicationMaintenance` · `https://cg-hkrpg-api.mihoyo.com/hkrpg_cn/cg/gamer/api/getGlobalApplicationMaintenance` · `https://sg-cg-nap-api.hoyoverse.com/nap_global/cg/gamer/api/getGlobalApplicationMaintenance` (headers `x-rpc-app_version`, `x-rpc-client_type: 1`, `x-rpc-cg_game_biz`) | `data.application_maintenance` is an object while servers are closed and `null` once they reopen — the only machine signal for *Servers Live*; the launcher's `main.tag` flips at maintenance **start**, so it cannot serve. Same endpoint/headers/`game_biz` as [seriaati/hoyo-update-notifier](https://github.com/seriaati/hoyo-update-notifier) (`hun/utils.py`, live at [hun.seria.moe](https://hun.seria.moe/)) and [yeci226/ZZZ](https://github.com/yeci226/ZZZ) (`news/sources.ts`); Star Rail's global gateway is the shared `hkrpg_cn` host in both | read only inside `[maint start + 20 min, + 24 h]` for a posted card (`0` requests on idle days); unknown shapes are never read as "open" |
| Kuro in-game notices (WW) | `https://aki-gm-resources-back.aki-game.net/gamenotice/G153/6eb2a235b30d05efd77bedb5cf60999e/notice.json` | exact English `Patch Notes for Version <version>…` title + `startTimeMs` supplies an official early *Servers Live* time; launcher package versions are not reopening evidence | WW 3.8 live probe: 2026-11-12 09:00 UTC+8, corroborated by player access; read only inside the posted-maintenance live window |
| Kuro launcher (WW) | Global EN new protocol `…/launcher/game/50004_P7xcUZnEr1AXIGON25E6KjpOgTlVrg6e/G153/official/index.json` → `config.functionCode.background` → `official/background/{code}/en.json`; legacy `G153/50004_obOH…/index.json` + lazy `launcher/launcher/…/G153/index.json` → `G153/background/{hash}/en.json` fallback; EN `launcher/app/…/G153/official/information/en.json` carousel | new index provides resource-pack live/pre-download versions and version-window-owned dated `.mp4` / textless first-frame `.webp` assets; legacy keeps its first-seen memo and CDN `Last-Modified` attribution. The EN carousel image slide is a lower art tier only when its note explicitly matches the version; date-only PV/showcase slides are ignored. It is fetched only inside the launch-window gate. CN is deliberately unused. | News-Express #131 runner evidence (2026-11-10) confirms the v2 index/background/carousel and dated media; offline smoke guards cover fallback and ranking (`0` extra requests on idle polls) |

HoYoLAB game IDs: 1 HI3 · 2 Genshin · 6 Star Rail · 8 ZZZ · **9 Honkai: Nexus Anima** (already
wired for launch day).

Both launcher URLs, the `launcher_id` value, Kuro's `<appId>_<appKey>/<gameId>` path, the
`launcher-config` endpoint and the rotating `functionCode.background` hash are documented in
[DynamiByte's HoyoPlay](https://gist.github.com/DynamiByte/0ad250bbe1930e2736a6d4e6e842bcb2) and
[Wuthering Waves](https://gist.github.com/DynamiByte/d839bf9f671c975b6666d0f6e6634641) endpoint
notes (the WuWa notes credit
[Cheu3172/Wuwa-Web-Request](https://github.com/Cheu3172/Wuwa-Web-Request) for most of the original
discovery). The notes are attribution for the endpoint shape only: every field Game-Express reads is
validated live against the current response, and `background/{hash}` is re-read from
`functionCode.background` each time rather than hard-coded.

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
Rotation #8 (2026-11-06, operator-directed on both monitors) puts the whole `4cuck/teapawt` family
first — its README lists exactly seven public instances, live on `status.d420.net`, with explicit
scraping permission: Batch 1 is `nitter.cf`, `xitter.cf` (untouched), `nitter.gq`, `xitter.gq`;
Batch 2 is `teapawt.org`, `teapaw.org`, `teapawt.net` plus the new `nitter.mizuki.st` (`TRIAL`:
operator-verified bodies, generated by and linking to `nitter.meowing.monster`, i.e. that backend
behind a different edge); Batch 3 opens with the demoted `nitter.meowing.monster` (run #4399: HTTP 502
/ 429 while teapawt answered) and token-gated `nitter.miningtcup.me`, then `nitter.mie.foundation` and
`nitter.freedit.eu`. Nothing deleted (27 → 28). Batch 1 is now single-origin, so a healthy run sends
its 4 parallel probes per handle to the teapawt origin; a teapawt outage costs one `NITTER_TIMEOUT`
before Batch 2 and a second before the independent bench in Batch 3.

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

## Research: Crimson Witch, Hoyocodes and prospective games (2026-11-27)

**Research only, not an enabled feature or reliability certification.** The production monitor,
source ranking, voting, targets and state are unchanged. Web-page observations below came from a
page-fetching service, not this repository's HTTP client or a GitHub Actions runner. A single
observation cannot prove freshness, uptime, complete pagination, or successful redemption.

The attended private expanded-card test [run 46014528959](https://github.com/uesu/Game-Express/actions/runs/46014528959)
posted 14 test messages without production state. The user subsequently confirmed that the
shown Endfield GIFs animate and the text format looked good. In the [read-only comparison
run 46024433163](https://github.com/uesu/Game-Express/actions/runs/46024433163), the same fixed
Endfield `1340` article was an excerpt in default mode but complete across six expanded pages;
`3840`, NTE `252469`, and Silver `1`/`120` were not excerpted in either tested mode. These
are fixed-article observations, not proof for all future articles. The inactive candidate-only
YouTube fallback verifies maximum-resolution thumbnail dimensions/signature first and falls
back when unavailable; native images/video remain preferred. It is not wired into production.

The user separately authorized a full **private-channel** historic test. A fixed read-only snapshot
observed 103 NTE, 143 Endfield and 21 Silver Palace articles. Test-only JSON journals in three
[PR comments](https://github.com/uesu/Game-Express/pull/174) persist the queue and page intents;
they contain no webhook, token or raw Discord message ID (IDs are keyed hashes). Only one
non-cancelling Actions job sends at a time. Every unknown delivery or unconfirmed journal update
holds the entire test, and no automatic retry is permitted. Ordering across sources is by UTC
calendar date; the day-only sources cannot prove within-day chronology. The private test includes
earlier sample articles intentionally. It does not write production state, and a finite snapshot
cannot prove that an upstream listing never omitted an item. The attended test stopped on
[batch 46076148028](https://github.com/uesu/Game-Express/actions/runs/46076148028); the user-provided
log confirmed the batch sent 11 pages before a `DeliveryHold`. The journals showed 62 completed
articles with no page in flight. Read-only [diagnostic 46088726143](https://github.com/uesu/Game-Express/actions/runs/46088726143)
identified the next article, Silver 34, as a 112,270-character body containing a very long
ideographic-comma-separated token. The renderer now safely splits such plain lists at their commas,
without dropping characters, and still holds unknown unsplittable tokens or formatting. In the
private test only, the page cap was raised to a bounded 120. [Diagnostic 46088975034](https://github.com/uesu/Game-Express/actions/runs/46088975034)
confirmed full rendering across 32 pages and media preflight; 4,260 separators survived rendering.
The journaled private queue was resumed, paced and oldest-first. It later stopped at
[batch 46090849744](https://github.com/uesu/Game-Express/actions/runs/46090849744) before Endfield
4494: the source had an unmatched literal `]` that prevented safe pagination. The Endfield adapter
escapes unmatched brackets without changing balanced links; [diagnostic 46091136496](https://github.com/uesu/Game-Express/actions/runs/46091136496)
rendered the whole article in four pages and preflighted its media. Another hold preceded NTE 261919,
whose official CDN path contained an unencoded space. Only official NTE CDN path spaces are now
percent-encoded, without relaxing generic URL validation; [diagnostic 46091741693](https://github.com/uesu/Game-Express/actions/runs/46091741693)
confirmed render and media preflight.

The private historic test subsequently **completed**: the journals confirmed 103/103 NTE,
143/143 Endfield and 21/21 Silver Palace articles, with no pending or partial articles. The last
batch was [46096334852](https://github.com/uesu/Game-Express/actions/runs/46096334852). The
separate Taygedo correction is not included in those counts. Day-only timestamps still cannot
establish exact same-day publication order, and the snapshot does not prove upstream completeness.
Production remains gated and the private test is not evidence of complete production/failover readiness.

NTE article 252478 contained literal double tildes, which Discord interpreted as a strikethrough
across paragraphs. NTE parsing now escapes literal tildes in prose while preserving actual HTML
strike markup and URLs; unrelated sources retain their previous behavior. The user-authorized
[correction 46088897298](https://github.com/uesu/Game-Express/actions/runs/46088897298) sent one
corrected card, with an independent durable journal and no change to production state.

The owner requests initial production catch-up oldest to newest, recording confirmed delivery.
The candidate pipeline checks two complete listing walks, adapts details to the existing card
renderer, uses exact dedicated webhook routes, and queues every observed ID oldest first. Numeric
ID is only a deterministic same-day tie-break, not evidence of publication time. Two matching scans
reduce but cannot eliminate source pagination races.

An experimental monitor path and Git checkpoint are under a **hard-coded release gate**: no
candidate discovery or posts occur there, even if `NEWS_CANDIDATES_BACKFILL=1` is configured. Its
prototype uses a separate detached-worktree Git ledger to checkpoint write-ahead intent and
confirmed IDs via same-branch push/ref checks,
uses one-shot Discord POSTs, limits a source to one article / three pages per run, and requires full
expanded output (holding rather than sending a safety-limit excerpt). Local mocked runner and bare
Git tests do not establish production correctness. End-of-job persistence/rebase interactions,
ambiguous Git/Discord outcomes, concurrent workflows and cross-repository failover still require
validation and an operational reconciliation procedure before removing the gate. A single-repo
Actions concurrency group is not a distributed lock. No backlog or production state change has
been performed. Existing game news routing and behavior remain unchanged.

A [private candidate pipeline test](https://github.com/uesu/Game-Express/actions/runs/46033400200)
used three previously untested articles (NTE 252471, Endfield 3857, Silver Palace 7). Four
messages were confirmed; the two-page Endfield article resumed from an isolated local bare-Git
JSON ledger after page one. The pinned test is now locked against reruns. This is real Discord
but **not** a real GitHub remote or production/failover test. The separate earlier NTE 252469
max-resolution test was not repeated. Automated reconciliation tests now hold ambiguous pages and
verify a human-reviewed resolution against the exact article, page, route and payload signature.
An `absent` decision requires independently established non-delivery, not merely an unknown outcome;
the corrected record must be durably checkpointed before resuming. An operator-facing workflow and
production-grade recovery procedure remain unfinished. Local bare-Git tests show the gated runner
can checkpoint separately, a stale writer holds, and a normal state commit can rebase over the
candidate ledger without changing it. Production sync protects `state/candidate_news.json` from
creation, modification or deletion; it is not provisioned automatically. A controlled
[development-branch GitHub probe](https://github.com/uesu/Game-Express/actions/runs/46037384333)
confirmed real pushes/ref verification, a stale writer hold and two simulated pages in a separate
throwaway ledger, without Discord or monitor-state writes. Its `restart=pass` annotation means
resumption between coordinator calls in the same process, **not** a new-process restart; that
stronger case is only locally tested. The probe ledger was removed after the run. This is not
production or cross-repository failover validation, and the release gate remains closed.

The gated prototype also requires an explicitly nominated `NEWS_CANDIDATES_AUTHORITY_REPOSITORY`
and `NEWS_CANDIDATES_AUTHORITY_BRANCH`, matching primary role, Actions repository/ref, allowed event,
and HTTPS origin. This permits a primary with a configured standby, but deliberately never allows
the standby to send automatically: a repo-local concurrency group cannot coordinate failover.
These checks reduce accidental dual writers; they do not prove distributed exclusion. A local
checkpointed reconciliation primitive validates an operator's decision and persists it without
sending, but no operational UI or independent proof of delivery is supplied. All writers must be
paused for human review and an uncertain Git checkpoint must be inspected before any retry.

Silver Palace article 7 exposed a duplicated lead image: the cover and first body image had
different URLs but were byte-identical 1626×500 JPEGs. Its separate 800×444 `banner_img` is the
listing artwork, not the missing article image ([read-only comparison](https://github.com/uesu/Game-Express/actions/runs/46036322461)).
The candidate renderer now compares complete, bounded official-host image responses and drops only
a cover proven byte-identical to the first body image, retaining body order. On comparison failure
or distinct content it keeps both; this is not perceptual deduplication. The corrected
[private card](https://github.com/uesu/Game-Express/actions/runs/46036854435) sent exactly once
with one body image and unchanged production state; the test is locked against reruns.

- [Crimson Witch](https://www.crimsonwitch.com/codes): its Genshin, Star Rail and ZZZ pages
  displayed active code/reward sections and links to RSS feeds (`/feeds/genshin/rss.xml`,
  `/feeds/star%20rail/rss.xml`, `/feeds/zzz/rss.xml`). A page fetch of the Star Rail feed failed;
  its format and runner reachability remain unverified. The screenshot's Genshin code also
  appeared on the Genshin page; that is an observation, not proof of how that card was sourced.
  At [hoyoverse-api revision 85be772](https://github.com/torikushiii/hoyoverse-api/tree/85be77283263da21affa66edf31e040c06c75f74/src/scraper/sources),
  its `genshin`, `starrail`, and `zenless` collectors each call a shared Crimson Witch scraper.
  This establishes a possible upstream dependency, not that a specific live Ennead item came from
  Crimson Witch. Counting a direct copy as an independent witness risks double counting. **No new
  direct scraper, ranking change, or additional source vote was added.**
- [Hoyocodes](https://github.com/heartlog/Hoyocodes/tree/9bb1e889d4bfc620afb1e3d290e5f286b913498d)
  is a frontend that fetches `/mihoyo/{game}/codes` from Ennead, not another independent backend.
  The existing `ennead:genshin`, `ennead:starrail` and `ennead:zenless` sources already read
  those same endpoints; `ogc` and `ennead` count as one family. The page fetcher returned
  active/inactive JSON for all three on 2026-11-27, including the screenshot's Genshin and ZZZ
  examples. The site itself and the monitor's live execution were not exercised end-to-end here,
  nor can current uptime or code validity be guaranteed.
- [Open Gacha Codes](https://github.com/torikushiii/OpenGachaCodes/tree/172cf88a0cc7c2b413291c7bb212e8de3d1104a0)
  documents `https://api.ennead.cc/codes/endfield` and `/codes/nte`. On 2026-11-27 the page
  fetcher returned five Endfield rows and an empty NTE array. Empty does not distinguish truly
  no active codes from missing or stale coverage. The published collector uses Game8 plus
  Mobalytics for Endfield and Game8 for NTE; they are not independent witnesses from their own
  downstream aggregator. Endfield and NTE guides describe **in-game** redemption, not a verified
  prefilled official web redemption URL. Compare [Endfield](https://game8.co/games/Arknights-Endfield/archives/571509)
  and [NTE](https://game8.co/games/Neverness-to-Everness/archives/593718); expiry claims can
  conflict or be stale, so do not equate a 200 response with usable live codes.
- Official news candidates: [Endfield](https://endfield.gryphline.com/en-us/news),
  [NTE](https://nte.perfectworld.com/en/article/news/index.html), and
  [Silver Palace](https://silverpalace.elementagames.com/en-us/news). The page fetcher rendered
  the listings; NTE exposed dated article links and a paginated list, and one article was fetched.
  The rendered Endfield and Silver Palace listings did not expose article links in that output.
  NTE's list had only three entries per page in this observation; a first-page-only poll can lose
  articles. Two NTE list pages also passed fixed-URL HTML structure checks on
  [runner 45961114831](https://github.com/uesu/Game-Express/actions/runs/45961114831).
  An inactive `nte_candidate.py` parses displayed calendar days rather than URL creation dates,
  validates canonical article paths and bodies, and compares two bounded complete listing walks.
  It is not a registered production source or proof of an atomic upstream snapshot. The capture
  and screenshot show article `265053` displayed as 2026-11-20 although its path has 20261113;
  no publication hour or timezone should be inferred from either value. User screenshots and
  the supplied `nte.txt` contain three article HTML documents: the 2024-08-30 trailer has a
  YouTube iframe, the 2026-11-09 maintenance notes have one body image, and the 2026-05-26
  special-program recap has ten body images. Those counts are structural, not Discord playback
  proof. The bounded development-only media inventory scans candidate article bodies without
  fetching embedded media, following redirects, writing fixtures or printing content; it is
  exploratory and does not enable a production reader.
- **Endfield CMS discovery:** [jino9492/subculture-calendar](https://github.com/jino9492/subculture-calendar)
  documents the official `web-news.gryphline.com/api/bulletin` endpoint and
  `code=arknights_endfield_official`. A separate page-fetching service returned `code: 0` from
  [English page 1](https://web-news.gryphline.com/api/bulletin?lang=en-us&code=arknights_endfield_official&page=1&pageSize=20)
  and [page 2](https://web-news.gryphline.com/api/bulletin?lang=en-us&code=arknights_endfield_official&page=2&pageSize=20)
  on 2026-11-27. Page 1 had 20 rows, `current: 1`, `pageSize: 20`, `total: 143`, with `cid`,
  `tab`, `displayTime`, `cover` and `brief`. Its sticky rows precede newer non-sticky rows, so
  **never stop pagination simply at the first old row**. Detail requests for
  [7011](https://web-news.gryphline.com/api/bulletin/7011?lang=en-us&code=arknights_endfield_official)
  and [0740](https://web-news.gryphline.com/api/bulletin/0740?lang=en-us&code=arknights_endfield_official)
  returned corresponding article data; `cid` is a string and leading zeroes must be preserved.
  This corrects the earlier assessment that the CMS host and app code were unknown. It is
  **not** evidence of production Fetcher or GitHub-runner reachability, complete pagination,
  safe media rendering, fidelity of the article body, or an implemented news adapter. The
  read-only research probe includes listing pages and detail URLs. On GitHub-hosted runner
  [45961114831](https://github.com/uesu/Game-Express/actions/runs/45961114831), fixed-URL
  structural checks for two list pages and two details passed; a separate
  [run 45961382489](https://github.com/uesu/Game-Express/actions/runs/45961382489) successfully
  exercised a complete bounded listing and detail 0740 through the production `Fetcher` and
  the unregistered prototype `sources/endfield.py`. The latter run's required CI test failed
  on the production-manifest file count, subsequently corrected; the candidate step itself passed.
  Log downloads were unavailable here, so no raw response fixtures were captured. A single run
  does not establish uptime, publication completeness, article/media fidelity, bootstrap or
  operational readiness. The prototype fails closed on pagination drift, duplicate IDs, invalid
  shapes or a greater than 20-page listing. It is not selected by `run_news` and no game is enabled.
- **Maintenance candidates:** Endfield's [pre-download and update notice](https://endfield.gryphline.com/en-us/news/3835)
  states that pre-download is available, plus Asia and Americas/Europe maintenance windows with
  explicit UTC offsets. Its version is given by name, not a numeric version. NTE's official
  [1.5 patch notes](https://nte.perfectworld.com/en/article/news/gamenews/20261109/264948.html)
  state a scheduled 06:00–11:00 (UTC+8) maintenance and note it may finish early or late.
  Scheduled end is not evidence servers actually opened; parsing, version identity, source
  ingestion and false-positive tests are still needed before feature 4 is safe to activate.
  [NTE's launch pre-download notice](https://nte.perfectworld.com/en/article/news/gamenews/20260424/261919.html)
  states it is live but describes the initial release, not proof of recurring update pre-downloads.
- **Silver Palace news API:** [logreus-cloud/genshinflex #53](https://github.com/logreus-cloud/genshinflex/issues/53)
  documents `server/index.php/home/news_list` and `news_detail` on the official site. The separate
  page-fetching service returned `code: 0` for [English page 1](https://silverpalace.elementagames.com/server/index.php/home/news_list?lang=en-us&page=1),
  [page 2](https://silverpalace.elementagames.com/server/index.php/home/news_list?lang=en-us&page=2),
  and [detail id 120](https://silverpalace.elementagames.com/server/index.php/home/news_detail?lang=en-us&id=120).
  Page 1 returned three rows and `total_page: 7`; page 2 was not strictly date-sorted. The
  observed `publish_date` is day-only: converting it to midnight then using the existing
  timestamp floor risks silently skipping same-day additions. Determine timezone, publication
  precision and an ID-aware safe baseline before implementing. Body markup/media fidelity and
  safe delivery remain unverified. Fixed-URL runner structural checks
  passed for two pages and one detail in [run 45961114831](https://github.com/uesu/Game-Express/actions/runs/45961114831);
  this confirms neither ongoing availability nor completeness, nor the timestamp semantics.
  `sources/silverpalace.py` is an **unregistered listing and detail prototype**. It makes two bounded
  complete walks, validates IDs and calendar dates without inventing a publication instant, and
  rejects drift, ambiguous empty pages and duplicate IDs. Matching walks reduce some races but
  do not prove an atomic upstream snapshot. The detail experiment checks matching ID, title and
  day, requires the observed exact cover host, and passes content to the existing block parser;
  The user's browser screenshot shows the official article route `en-us/newsDetail?id=120`
  alongside detail 120; the prototype now constructs that fixed-host route from the validated ID.
  One example does not prove all links. It does not verify body fidelity, validate embedded media
  or redirects, post to Discord, or integrate with the runner. In [run 45983530944](https://github.com/uesu/Game-Express/actions/runs/45983530944),
  the production Fetcher completed two walks (21 rows) and parsed matching detail 120 (one
  block); that is a single structural observation, not article fidelity or delivery proof.
  An independent, unregistered
  `day_news_candidate.py` tests a possible ID-based silent baseline and retry queue without
  converting date-only values into timestamps. It queues newly observed IDs even when their
  displayed dates are old, retains pending items if they disappear, fails closed at a fixed ID
  cap or on route/state mismatch, and needs a complete valid source snapshot. This explicitly
  favors not silently dropping backdated arrivals over avoiding historical backfills. It has no
  webhook, state-persistence or multi-message partial-delivery integration, and cannot resolve
  webhook-accepted/state-save-failed ambiguity. The eventual operational policy and tests must
  be reviewed before activation; unchanged timestamp-floor behavior remains in use elsewhere.
- [Elementa's official press release](https://www.elementagames.com/en-us/newsDetail/?id=14)
  states that Silver Palace launches globally **December 14, 2026 (UTC+8)**, matching the
  screenshot. Launch hour was not established. Treat feature 3 as the requested candidate,
  not permission to activate the other features automatically.
- Reddit candidates: [r/Endfield](https://www.reddit.com/r/Endfield/) describes itself as
  community-run and partnered with Gryphline in the supplied screenshot; partnership does not
  make every author official. [r/ArknightsEndfield](https://www.reddit.com/r/ArknightsEndfield/)
  is unofficial; [r/NevernessToEverness](https://www.reddit.com/r/NevernessToEverness/) and
  [r/SilverPalaceOfficial](https://www.reddit.com/r/SilverPalaceOfficial/) describe themselves as
  official in the screenshots. Independent account verification is still needed; these labels
  do not make every poster official. [News-Express #160](https://github.com/uesu/News-Express/pull/160)
  added four Game-Express communities to Devvit defaults, and [#161](https://github.com/uesu/News-Express/pull/161)
  split the 19 defaults across `subreddits` and `subredditsAdditional`. Supplied screenshots show
  Devvit v0.0.14 uploaded and installed in r/GamingExpressRelay, both settings accepted, polls
  reporting 19 subs and zero failed fetches, and Discord intake records for NevernessToEverness,
  Endfield, ArknightsEndfield and SilverPalaceOfficial. These are examples of relay delivery,
  not evidence of Game-Express consuming those records or continual per-target health. Merged defaults
  and aggregate polling alone do not prove every target is healthy. The optional
  `INTAKE_QUIET_TARGETS=1` infers coverage by kind, not by each target. No subreddit,
  official-author allowlist, or trust rule was added to Game-Express.

**Before implementation:** establish stable official listing/detail contracts, complete bounded
pagination, UTC/timezone and media handling, safe bootstrap, outage/partial-response semantics and
mocked end-to-end card/state tests. For schedule and maintenance, establish official program,
version, preload and maintenance/server signals independently (including false-positive prevention);
for codes, validate source families, availability, expiry, corroboration and in-game redemption.
The supplied production configuration inventory has no dedicated news/code/maintenance webhook
secrets for these three games and no new game entries in the feature selection variables. The
schedule mirror is optional; the primary schedule webhook is shared. Do not change secrets or
production switches until reviewed and configured by the operator.

The manual `Source research probe (manual, read-only)` workflow runs fixed target groups from
`tools/source_research_probe.py` and `tools/live_candidate_probe.py`; `--self-test` is offline.
They request fixed public URLs, report bounded structural counts (not raw content), follow no
redirects, use no secrets, and never touch Discord or state. The limited Reddit fleet and Endfield
prototype run through existing reader code; they are not representative of authenticated or
redirect-following production traffic. It is a **reconnaissance** tool, not a parser, correctness test,
continuous monitor, or proof that any source is ready. HTTP failures fail the job; malformed
shapes and empty lists are printed for human review, not silently accepted as validated data.
The workflow was registered by probe-only [PR #172](https://github.com/uesu/Game-Express/pull/172)
and dispatched on main in [run 45972342468](https://github.com/uesu/Game-Express/actions/runs/45972342468).
The run's official source groups succeeded, but the job failed on three Crimson Witch RSS 404s.
The draft branch no longer runs that unrelated, unintegrated group in its standard workflow; the
old failures remain valid observations, and the explicit diagnostic is still available in the
probe script. The main workflow retains the old step until the draft is reviewed and merged.
Removing this unrelated check does not make other sources healthy: candidate probe statuses such as
`unavailable`, `empty` and `rejected` are informational and do not themselves fail the job.
Select the intended branch when dispatching. A successful dispatch is not evidence the probe ran
or that a future run will succeed. In
[runner 45964838716](https://github.com/uesu/Game-Express/actions/runs/45964838716) three fixed
observed image URLs, one per game, returned HTTP 200 with recognized image signatures, but the
Endfield prototype's actual rendered payload failed existing production media preflight. A later
user screenshot shows all three fixed image links rendered when manually pasted into Discord; that
is not a bot/webhook payload test, video test, redirect-safety guarantee or proof that Endfield's
existing production preflight accepts its CDN. Required CI passed; the temporary research job failed because three Crimson
Witch RSS endpoints returned 404, and its separate steps continued to completion.

## Evaluated but not integrated (and why)

| Candidate | Verdict |
|---|---|
| YouTube channel RSS (`/feeds/videos.xml?channel_id=`) | returned **404** during verification (even for Genshin's confirmed channel ID). YouTube links and thumbnails come from the official tweets and HoYoLAB posts instead |
| parse.bot marketplace APIs (prydwen / icy-veins / genshin.gg / hoyolab) | paid third-party scrapers, not verifiable; not needed for official data |
| `getGamePackages` (HoYoPlay legacy) | stale for Sophon games (see above) |
| Hoyotod/code · Hoyotod/redeem | fandom-scraper pattern (we call the MediaWiki API directly) · redeem automation (requires accounts; out of scope) |
| heartlog/Hoyocodes · promogacha.netlify.app | Hoyocodes is an Ennead frontend (same backend already used); PromoGacha's GitHub JSON **is** used |
| chiraitori/HoYo_Code_Sender_Discord_Bot · Hum-Bao/hoyoverse-codes-backend · retvil/hoyo-code-monitor · lukascortes/gacha-codes-notifier | reference implementations; their sources are covered above (Hum-Bao's **published TXT lists** are used as a validator since v1.1) |
| MoonShadow1976 WW asset repos | manually maintained, last updated Jan 2026, so too stale for codes |
| DuolaD/HoYo_Versioncatcher | launcher-data repo; led us to the HoYoPlay launcher endpoints |
| TwintailTeam/game-manifests · TomyJan/GenshinImpact-Client-Version | launcher-manifest repos documenting Kuro's `G153` global launcher index and `background/{hash}/en.json` schemas (`sources/kuro.py`) |
| [DynamiByte launcher-API notes](https://github.com/DynamiByte) | primary documentation of the endpoints used above (`hyp/hyp-connect/api` + `launcher_id`, Kuro `G153` index, `launcher-config`, `background/{hash}/en.json`); attributed in [CREDITS.md](CREDITS.md#launcher-api-research) |
| genshin.dev | character/game data API, not schedules or codes |
| gachabase.net · nanoka.cc · sr.yatta.moe · lunaris.moe · ambr.top | databases, listed in [CREDITS.md](CREDITS.md#community-databases-and-research). No public schedule/banner API was verified, so **banner names come from official notices, `Kitsudock-data` (`hub.json`), the `api.ennead.cc` calendars, the Fandom wikis, or `config/overrides.json`** |

## Reddit intake reader — the Devvit relay is the listing (2026-11-02)

`sources/reddit_intake.py` sits in front of the fleet below. The *Gaming Express* Devvit app
(News-Express `devvit/gaming-express`, installed on Reddit's Developer Platform under the owner's
account) polls `/new` of the six official subreddits plus the verified publisher accounts with
Reddit's own API **every 5 minutes** — the app build live today; the pending 0.0.11 update
(Devvit 0.15.6, News-Express PR #154) polls **every 3 minutes** — and writes one fenced-JSON record
per new post (`id, sub, title, permalink, url, created, author, flair, distinguished, spoiler,
nsfw, score, comments, removed, xpost, media[], body, bodyTruncated`) into a private Discord
channel shared with News-Express. Nothing in this section depends on the exact cadence: the reader
measures freshness on the newest relay message (`INTAKE_STALE_SECONDS`), so a faster poll only
makes the relay answer sooner.

- **One read per run** (`GET /channels/<INTAKE_CHANNEL_ID>/messages`, bot token in the
  `Authorization` header only, newest-first `before=` paging, ≤ 8 × 100 messages, 6 h window);
  messages that are not relay records (other bots) are skipped. `RedditClient._gather_listing()`
  asks the reader first: a healthy relay (`ok` = at least one record, newest record younger than
  `INTAKE_STALE_SECONDS`) with records for the target **is** the listing — 0 fleet requests. Any
  other state, or a target with no record in the window, runs the fleet exactly as before.
- **Same dict shape** as `parse_reddit_json()` / `parse_redlib_html()` (`images`, `videos` as
  `v.redd.it/<id>/CMAF_720.mp4` for the muxed proxy chain, `links`, `flair`, `distinguished`), so
  the official rule, `items()`, `program_post()` and `community_codes()` are untouched; relay
  entries additionally carry `relay: True`, `body_truncated` (bodies above the relay's message
  budget arrive cut; `resolve_post()` fills them in as for any empty-text entry) and
  `relay_complete` (relay 0.0.8: nothing cut, parent named — such an entry IS the post, and
  `items()` / `program_post()` never call `resolve_post()` for it).
- **Body media (News-Express round 115 / PR #148):** an inline "GIF" in Reddit's rich-text editor
  is stored as the shorthand `![gif](<media-id>)` — no CDN URL, no extension — and the Devvit post
  payload has no equivalent in `media[]`. The reader resolves that form to
  `https://i.redd.it/<media-id>.gif` and merges it with the bare `i.redd.it` / `preview.redd.it`
  URLs of the same body **in source order**, after the record's own `media[]`; the ordinary dedupe
  collapses a reference the relay already listed. The rule stays conservative on purpose: only an
  explicit `gif` marker with an id-shaped target (5–64 chars of `[A-Za-z0-9_-]`) becomes media, so
  `![image](…)` and any other markdown target are never guessed into a URL. This is media
  discovery only — no new gate, and `text`, `links` and the official rule are unchanged.
- **Settings** (shared names with News-Express, passed through `GE_SECRETS_JSON`/`GE_VARS_JSON`):
  secret `DISCORD_BOT_TOKEN`, Variables `INTAKE_CHANNEL_ID`, `INTAKE_READER=primary|shadow|off`,
  `INTAKE_STALE_SECONDS=1800`, `INTAKE_LOOKBACK_SECONDS=21600`, `INTAKE_QUIET_TARGETS=0`. The step
  summary carries one `📡 reddit intake: …` line whenever Reddit was consulted.
- **Quiet targets (`INTAKE_QUIET_TARGETS=1`, off by default):** with a healthy relay, a target that
  has no record in the window is *quiet* — `[]` ("no new post") instead of `None` ("let the fleet
  fetch it"), so a run that served some subreddits makes **0** redlib / reddit.com requests for the
  rest, and the summary says so (`quiet (no new post) r/…`). This is the News-Express round-105
  rule (its summary calls the same state `quiet, not missing; no archive attempt`): the relay polls
  every target every 5 minutes, so absence in a *fresh* relay is evidence, not a failed fetch.
  Two guards keep it honest — the relay must be `ok`/`primary` (never `shadow`, `off`, `stale`,
  `empty` or error), and it must already list **another target of the same kind** among this run's
  own targets (`r/…` for subreddits, `u/…` for publisher accounts, a removed post still counts).
  Otherwise the per-target fallback runs exactly as before, because a relay that lists none of this
  engine's targets may simply not poll them — silence there would be a missed post. Quiet targets
  stay *reachable* (they answered), so no "source unreachable" warning appears for them.
- **Scope — one channel, two engines (News-Express PRs #100 / #107).** The relay's default
  `subreddits` is twelve names: the six **leak** subreddits for News-Express
  (`AnantaLeaks`, `Genshin_Impact_Leaks`, `HonkaiNexusAnimaLeaks`, `HonkaiStarRail_leaks`,
  `WutheringWavesLeaks`, `Zenlesszonezeroleaks_`) **and** the six **official** subreddits for
  Game-Express (`Genshin_Impact`, `HonkaiStarRail`, `ZZZ_Official`, `WutheringWaves`,
  `HonkaiNexusAnima`, `AnantaOfficial`), plus the verified `officialUsers` feeds (default
  `genshinimpact`, `HonkaiStarRail`, `HonkaiNexusAnima`; dormant ZZZ / ANANTA accounts and
  Wuthering Waves are covered by their subreddit via flair). Game-Express's own scope is the six
  official subreddits, its `reddit_official` accounts and any `reddit:<sub>` code source —
  **never a leak subreddit**. `runner.reddit_targets()` builds exactly that set, and the quiet
  mode trusts only records inside it: leak traffic in the shared channel proves the relay is
  alive, never that one of these targets is quiet.
- **Failure diagnostics (News-Express round 116 / PR #146):** a Discord `429` on the channel
  history is the one failure where the failing page and the rate-limit headers decide the next
  move, so the summary names both —
  `relay http_429 (rate limited on history page 3 — retry-after=5, x-ratelimit-scope=user, …)`.
  The values come straight from `Retry-After` / `X-RateLimit-Scope` / `-Global` / `-Remaining` /
  `-Bucket` when Discord sent them and are omitted otherwise. This is evidence, **not** a retry
  policy: the status stays `http_429`, the per-target fallback runs as for any other error, and
  nothing waits longer or asks again because of the values. The other failures keep their wording
  (`http_401` bot token rejected, `http_403` missing channel permissions, `http_404` unknown
  channel id, `http_5xx` the raw status).
- **Read window vs the relay's horizon:** `INTAKE_LOOKBACK_SECONDS=21600` (6 h) bounds the
  paginated Discord history, and News-Express round 116 capped *its own* freshness, pending and
  re-check retention at 5 h. This engine keeps its 6 h read window on purpose — its schedule and
  code windows are wider (72 h), the relay's re-checks all fall inside 6 h, and shortening the read
  would only drop late records. The setting is read through the shared name, so a deployment that
  wants News-Express's 5 h figure can set `INTAKE_LOOKBACK_SECONDS=18000` without a code change.
- **Complete source (relay 0.0.7 / 0.0.8):** each record message also carries `record.json` (full
  body, every media URL, crosspost parent) — fetched from `cdn.discordapp.com` only for cut
  records and crossposts, ≤ 10 per run, no token — and the relay re-checks delivered posts
  (~5 min / 30 min / 2 h / 5 h — News-Express round 116 shortened the tail's 6 h / 24 h steps; the
  app build live today still re-checks through 24 h, and either schedule is safe here because a
  re-check only ever describes a record the 6 h read window already listed) in batched `v: 2`
  update messages: removed or deleted →
  not listed, approved → the complete record is re-sent and listed, edited → re-sent record
  (`revision` ≥ 2, `resent` = why) supersedes. Nothing in the fleet below is needed for a
  relay-served target.
- **Why first:** Reddit retires RSS on 2026-11-13, removes unregistered access on 2027-01-12 and
  is moving to a logged-in-only site; the fleet below stays as the automatic fallback.

## Reddit & Redlib fleet (2026-10-22)

`sources/reddit.py` integrates Reddit and Redlib across all six configured games (`r/Genshin_Impact` / verified `u/genshinimpact`, `r/HonkaiStarRail` / verified `u/HonkaiStarRail`, `r/ZZZ_Official` / verified `u/ZZZ_Official`, `r/WutheringWaves` with `official: []` because live `u/WutheringWaves` is an unrelated 2022 squatter account, `r/HonkaiNexusAnima` / verified `u/HonkaiNexusAnima`, and `r/AnantaOfficial` / verified `u/AnantaOfficial`) under strict role separation and zero-waste request discipline:

- **Official publisher accounts (`game.reddit_official`)** act purely as a failover backup for `schedule` and `codes` (`PRIORITY["reddit"] = 38`, `LOCK_RANK["reddit"] = 1`): when X and primary APIs (`HoYoLAB`/`Kuro`) succeed on a game, `_gather_game()` makes **`0` `/user/<official>` HTTP requests**; if either degrades, it fails over in the same run automatically, merges same-author comments under image posts, rewrites `/img/` / `/preview/` / `/vid/` paths back to permanent `redd.it` URLs, and upgrades back to X as soon as X recovers.
- **Community subreddit listings (`reddit:<Subreddit>` in `codes.sources`)** emit unverified `CodeHit(code, "reddit", None)` witnesses (`family("reddit") == "reddit"`). A single unverified community post never passes `CODES_MIN_SOURCES = 2` alone (`status = "pending"`), while providing a fast second independent witness alongside `fandom`, `seria`, `humbao`, `ennead`/`ogc`, or `wuthering.gg` (including pre-launch `hna` and `ananta`). When `REDDIT_FEED_TOKEN` is set in Secrets, both `/r/<sub>/new.rss` and `/user/<acct>/submitted.rss` use a **1-request direct `[0] www.reddit.com` → `[1] old.reddit.com` fast path** plus circuit-broken `.json` fallback (`0` Redlib mirror hits unless first-party Reddit fails).
- **Ordered `DEFAULT_REDDIT` fleet (`27` entries, `REDDIT_BATCH = 3`, stopping at `REDDIT_WORKING = 2` answers):**
  1. Tier 1 — Active healthy dual-path + token-gated tier (`[0..11]`, zero unauthenticated `403`s on GitHub Actions IPs): `https://redlib.mint.lgbt` (`0.36.0` `0baefabf` Shreddit scraper), `https://reddit.idevicehacked.com` (`0.40.0` `848f3013`), `https://redlib.reallyaweso.me`, `https://r.naa.gg` (`Nachtalb/redlib` GraphQL engine), `https://redlib.thepixora.com` (`PR #603` GraphQL comments patch), `https://redlib.r4fo.com`, `https://redlib.catsarch.com`, `https://snoo.habedieeh.re`, token-gated `https://redlib.miningtcup.me` (`NITTER_RSS_TOKEN`), `https://redlib.tiekoetter.com`, `https://redlib-1.privadency.com`, `https://redlib-2.privadency.com`.
  2. Tier 2 — Verified `/new` (+ `/user/`) listing-only tier (`[12..18]`, skipped on `/comments/` lookups via `REDDIT_LISTING_ONLY`): `https://redlib.ducks.party` (`v0.40.0`, skipped on `/user/` via `REDDIT_SUB_LISTING_ONLY`), `https://reddit.jeremyh.xyz`, `https://redlib.jeikobu.net`, `https://red.artemislena.eu`, `https://rl.awy.one`, `https://redlib.freedit.eu`, `https://redlib.utilibre.org`.
  3. Tier 3 — Token-promoted official origins & demoted/legacy fallback tail (`[19..26]`, placed strictly last — zero requests while Tier 1 answers; nothing deleted): `https://www.reddit.com` (promoted to slot `0` 1-request fast path when `REDDIT_FEED_TOKEN` is set), `https://old.reddit.com`, `https://redlib.vanillax.me` (demoted on `2026-10-24` after HTTP `200` `The backend server is having issues` error body), `https://redlib.privacyredirect.com` (demoted on `2026-10-23` after upstream `403` error page), `https://eddrit.com`, `https://redlib.privadency.com`, `https://safereddit.com`, `https://redlib.nadeko.net`.
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
First try one full message. A fitting card is a single container, so the 4,000 text-character / 40-component
limits are message-wide and are packed to the cap before any second message is used. Long articles are smart fitted across pages (up to
`NEWS_DEFAULT_MAX_PAGES = 4`) before any excerpt is considered. Legacy note: on overflow,
<=7,000 normalized characters
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
`※` note paragraphs. Consecutive `-` bullets stay compact. A card that fits one
message is never split into `-# Part n/m` containers, and an uninterrupted media run
is not a reason to split anywhere. By default individual
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

Keep fitting full articles unchanged in one message **and one container**.
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
message. One-message articles put the buttons in that single container. Articles
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
the final message, and a single-message card has exactly one container to hold
them. One message is one container whenever the whole card fits; only separate
messages carry Page 1/Page 2 labels, and `-# Part n/m` containers are retired
(2026-11-18).
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

When a game is explicitly listed in `MAINTENANCE_GAMES` (feature 4 is on by default;
`MAINTENANCE_ENABLED=0` switches it off),
`gamexpress/maintenance.py` resolves optional launch media from structured official
endpoints and existing caches only (never headless browsers or HTML scraping):

| Game(s) | Structured source | Priority assets & safeguards |
|---|---|---|
| GI / HSR / ZZZ / HNA | HoYoPlay `getAllGameBasicInfo` (`hyp-api.hoyoverse.com`) + existing HoYoLAB / X Special Program cache | (1) version-matched `.webm`/`.mp4` background clip, (2) version-matched `.webp`/image background, (4) `overrides.json` / Special Program key art, (5) omit gallery; tier 3 is reserved for the WuWa carousel. Version/launch lock separates selected tier so late launch video upgrades initial artwork inside `LATE_MEDIA_EDIT_WINDOW_S` (including opaque shortlink `bg["id"]` rotations within `[-11d, +7d]`) while blocking prior-version and Phase II swaps |
| Wuthering Waves | Global English Kuro new-protocol index/background and launcher information carousel; legacy `G153` launcher remains fallback | (1) matching-version `.mp4` clip keeping signed `?auth_key=…` query parameters intact, (2) matching-version textless first-frame artwork, (3) carousel image only when `carouselNotes` names the matching version (unlabeled PV/showcase slides are rejected), (4) `overrides.json` / Special Program key art, or (5) omit gallery. Dated background assets must fall inside that version's launch window; legacy URLs retain first-seen memo + CDN `Last-Modified` validation. Signed URLs expire and renew inside `LATE_MEDIA_EDIT_WINDOW_S` (`6 h` / `21,600 s`, `MAX_LATE_MEDIA_ATTEMPTS = 3` consecutive failed `PATCH` calls reset on `res.ok`, `MAX_LATE_EDITS = 6` total succeeded `PATCH` calls, per-run URL check deduplication) only when corroborating source metadata binds the exact asset. CN is deliberately unused. |
| ANANTA | Official X (`@Ananta_EN`) + verified official Reddit (`u/AnantaOfficial`) + `config/overrides.json` / `program_announcements.json` (`easebar.com`, `anantagame.com`, `netease.com`, `163.com`, `pbs.twimg.com`, `redd.it` allowlisted) | Tier 4 (`overrides.json` `image` pin → Special Program / launch key art; tier 3 is reserved for the WuWa carousel) → Tier 5 clean gallery omission until NetEase publishes a structured global launcher background API |


## Beta kit & revision-diff sources (2026-10-24)

Feature 5 (`BETA_ENABLED=1`) reads structured JSON plus Markdown or server-rendered changelog HTML from community
databases that publish beta revisions. The 2026-10-25 response-format repair replaces the
earlier no-HTML-parsing assumption: public changelog headings/cards are parsed with the
standard-library HTML parser. No headless browser, authentication or additional endpoint is
needed. Verified 2026-10-24; the
blank-heading / hotfix behavior and Sunbringer `19850203` source-link shape were rechecked
2026-10-25.

| Purpose | Endpoint | Shape |
|---|---|---|
| Revision probe | `https://static.nanoka.cc/manifest.json` | ~1 KiB. Per game: `latest`, ordered `available`, `live`, and `new` → `character` / `weapon` / `lightcone` / `relicset` / `equipment` / `echo` ids. Builds whose `major.minor` is `<=` the game's live cycle are filtered out before any changelog/detail read; active builds walk in order so hotfixes are not skipped |
| Revision contents | `https://zzz.gachabase.net/changelog/beta?lang=en` (also `gi.` / `hsr.`) | Markdown, server-rendered HTML (`h2` revision headings, `h3` categories, item/diff links, CN-lag advisories), or SvelteKit `data:{revisions:[...]}` home-page hydration (`/?lang=en`); when GachaBase returns HTTP 403 across endpoints, falls back cleanly to `static.nanoka.cc` manifest + intra-cycle `{prev,cur}/character.json` index diffing. An explicit `No tracked changes detected` heading is a silent cursor advance once a current-epoch baseline exists |
| Before/after diff | `https://zzz.gachabase.net/diff/agents/1601/sunbringer?prev=beta_3.4.1_19842923&cur=beta_3.4.1_19850203&lang=en` | Linked from a changelog entry or deterministically surfaced from a retained before/after build; it is **not fetched** by the monitor — readable structured JSON snapshots create the card's inline diff |
| Character kit | `https://static.nanoka.cc/<game>/<revision>/{en,zh}/character/<id>.json` | One bounded `en` GET per newly revealed or already-snapshotted candidate (including ZZZ `passive.level` Core Passive & Additional Ability, named Mindscape Cinema titles, and `potential_detail` Potential Awakening), plus a `zh` cross-check when EN lags (`???`, `[TBD]`, `/-`, missing CN sections, changelog CN-lag advisory, or unchanged EN multipliers on a new revision) |
| Weapon / W-Engine / light cone | `https://static.nanoka.cc/<game>/<revision>/{en,zh}/{weapon,lightcone}/<id>.json` | Stats (including ZZZ max-modification substat scaling from `rand_property` + `stars`) + inline `S1–S5` / `R1–R5` refinement/superimposition scaling (`6%/7%/8%/9%/10%`, falling back cleanly to `S1` / `R1` when tiers `2..5` are missing, unclear, or zero-padded), `zh` parameter cross-check for `[value unavailable]` / `[TBD]` / `???`, and zero-request `zh` listing name fallback (`<zh> (ID <id>)`) when `en` is unlocalized |
| Bangboo | `https://static.nanoka.cc/zzz/<revision>/{en,zh}/bangboo/<id>.json` | Skill numbers resolved through `skill_prop`; prose keys dropped rather than printed (see the table above) |
| Disc drive / relic set / artifact / echo | `https://static.nanoka.cc/<game>/<revision>/{en,zh}/{equipment,relicset,artifact,echo}/<id>.json` | 2-piece / 4-piece set bonuses and verified per-piece icon galleries (GI artifacts live in one `artifact.json`) |
| Verified static media | `https://static.nanoka.cc/assets/{gi,hsr,zzz,ww}/...webp` | Exact per-namespace asset paths (`avatardrawcard`, `rank/_dependencies/textures/..._Rank_{1..6}`, `lightconemaxfigures`, `relicfigures/IconRelic_{id}_{slot}`, `UI_Gacha_AvatarImg_*`, `UI_Gacha_EquipIcon_*`, ZZZ `icon`/`icon2`/listing stems, and ID-verified WuWa nanoka assets). Missing/404 assets omit cleanly; newly uploaded single images, fallback-icon-to-splash promotions, and `1..N` gallery additions publish visual-asset updates on subsequent revisions and lock in `locked_images` |
| Listing index | `https://static.nanoka.cc/<game>/<revision>/{weapon,equipment,lightcone,relicset,echo}.json` | One GET per kind per revision: rarity, max ATK and substat name for every id, so the card never has to guess them |

Diff-link routes are the sites' own path segments, captured 2026-10-30 from the served
changelog pages rather than guessed: `characters|weapons|artifacts` (Genshin),
`characters|lightcones|relics|planar-ornaments` (Star Rail — a planar set has its own route,
a cavern relic set lives under `relics`), `agents|w-engines|drive-discs|bangboo` (ZZZ). WuWa has no
gachabase route at all, so its comparison link is Encore's `diff` page instead.

The `__data.json` stream behind those pages groups items under per-game key names, also captured
2026-10-30: ZZZ `agents|wEngines|bangboo|driveDiscs`, Star Rail
`characters|lightcones|relics|planarOrnaments`, Genshin `characters|weapons|artifacts`. Every one
of them has to stay in `gamexpress/beta.py::_DATA_SECTIONS`, because a key that is absent drops
that whole group in silence — which is how a Star Rail stream kept only its `relics` and a
Genshin stream produced no revision at all.

Two listed groups have no card kind: Genshin's `materials`/`items` (a material has no kit worth
carding) and any route the code does not recognise — that case is a reported warning, never a
silent skip. ZZZ's `bangboo` used to be the third; it is a card now.

A Bangboo is a real first-class record, not an agent variant — captured from the served pages on
2026-10-30/31 (`/bangboo` index and the pages for Charley 54024, Booltergeist 53021, Ariel 54023,
Ultra Jake 54022 and Overtimeboo 53014): an S/A rank, a promotion stat block
(HP · ATK · DEF · Impact · CRIT Rate · CRIT DMG · PEN Ratio · Anomaly Proficiency), promotion
materials, three skills labelled a / b / c (Active Skill, Additional Ability, Bangboo Chain Attack)
each with its own attribute table and a shared `Skill Table`, and its own `Version Diff` picker. The
listing is read from `zzz/<revision>/bangboo.json`.

**The per-item file is confirmed.** `https://static.nanoka.cc/zzz/3.4.1+19997538/en/bangboo/54023.json`
was opened directly on 2026-10-31 and returns the record — so the path is
`zzz/<revision>/{en,zh}/bangboo/<id>.json`, the same layout as every other kind, and the field names
below are the served ones rather than a followed pattern. (A DevTools trace of
`zzz.nanoka.cc/bangboo/<id>` shows the page loading its document, JS, CSS and `_app/version.json`
with no per-item JSON: nanoka server-renders the Bangboo page, which is why a capture of the page
could not show the file.) `tests/fixtures/beta/zzz_bangboo_54023.json` is that record verbatim, and
the test built on it asserts the values against the gachabase page. A record that arrives in an
unexpected shape still fails loudly instead of guessing: the run reports
`has no readable text in this build (<full url>)` naming the file it could not read.

The file is `zzz/<revision>/{en,zh}/bangboo/<id>.json`, laid out as:

| Field | Holds |
|---|---|
| `rarity` | raw `2..4`; the zzz `+1` mapping makes `4` the five-star S rank the site prints |
| `stats` | base HP / ATK / DEF plus `break_stun` (Impact) and the Lv. 1 growth rates |
| `level` | promotion ranks `"1"`..`"6"`, each with `level_min`/`level_max`, `materials`, and `extra` (CRIT Rate / CRIT DMG) |
| `skill` | `a`/`b`/`c` = Active Skill / Additional Ability / Bangboo Chain Attack; each has `{"1".."N": {name, desc, property, param}}` |
| `skill_prop` | the numeric table some `param` slots point at: `{main, growth, format}` per `Prop` id |

**`param` is a mixed list, not a list of pointers.** It is pipe-separated and parallel to
`property`, and a slot is one of two things: a `{Skill:<id>, Prop:<id>}` pointer into `skill_prop`,
or a literal the build already wrote out *for that level*. Ariel's Active Skill at Lv. 6 is
`9.6% HP|4 Energy|20%|{Skill:5402301, Prop:1001}|{Skill:5402301, Prop:1002}|28s` — three buffs and
a cooldown as literals, two multipliers as pointers. A literal is read as-is, never grown: the same
row is `6.6% HP` at Lv. 1 and `12% HP` at Lv. 10 because the file says so. `property` can also be
longer than `param` (Ariel lists 7 names for 6 slots); the overflow is ignored, and a name or value
that is still a localization key drops only its own pair, keeping every other row aligned.

The description opens with the skill type it belongs to (`"Active Skill Flies high into the air…"`),
so that prefix is stripped before printing — the card already labels the line — and a multi-paragraph
description is collapsed onto one line so a bullet cannot break out of its own block.

`skill_prop` is where a *pointer* gets its number: `value(level) = (main + growth x (level - 1)) /
100`, and `format` is the literal unit printed after it — `%`, `% HP`, `Energy`. Every row in these
files is fixed-point hundredths (`80000` -> 800%, `660` -> 6.6%, `275` -> 2.75), and the unit is
spaced only when it is a word (`9.6% HP`, `4 Energy`, `24s`). A build that ships a .NET placeholder
instead (`"{0:0.#%} HP"`) is read the same way: the sign comes from inside the braces, the rest
after them. A value that ever arrives already fractional is used as-is rather than divided a
second time.

Three Bangboo confirm the arithmetic from both sides. Charley: `80000` + `8000 x 5` = **1200%** at
Lv. 6, 439.5% / 1,618.5% / 231% for the other rows. Booltergeist: nanoka opens at Lv. 1 (480% /
281%, 834% / 119%) and gachabase prints Lv. 6 (720% / 421.5%, 1251% / 178.5%). Ariel: 772% -> 1158%
and 828% -> 1242% at the same 10% growth, plus the value shapes that are *not* percentages —
`6.6% HP` -> `9.6% HP`, `2.75 Energy` -> `4 Energy`, and a flat `20%` that does not move because its
growth is 0. Ariel also shows the widest row set so far: five attributes on one skill (three buffs,
DMG, Daze) against Charley's two.

The level is the one gachabase displays, **6 / 1 / 6** (`_ZZZ_BANGBOO_SKILL_LEVEL`: the two
upgradeable skills, then the ability with no upgrade track), on both an S-rank and an A-rank
Bangboo. It is not the block's length: the sliders run to the table's own length (10 / 5 / 10 here)
while the displayed value stays 6 / 1 / 6, and nanoka simply starts every slider at 1. A block that
publishes fewer levels than the cap is read at its own last level rather than inventing one.

**Released stays released.** Four of the five captured Bangboo shipped before 3.4.1 — Ariel in
3.1, Ultra Jake in 3.0, Booltergeist in 2.8, Overtimeboo in 1.7 — so a 3.4.1 entry for any of them
is a rebalance. The manifest's `new` list is a claim, not proof (nanoka keeps an item there while
it keeps changing), so before an equipment card may say `[NEW]` the **live build's own listing**
is consulted: an id it already carries is demoted to a change and goes through
`_released_equipment`, printing `~~1158%~~ → **1200%**` for the row that moved with every unchanged
skill left out. If the live build lists the item but its old record cannot be read, the card falls
back to the plain snapshot note ("no direction is inferred") rather than a reveal. Only an id the
live build does not have — Charley 54024, the one genuine 3.4.1 addition — prints its kit once as
`[NEW]`. Cost: one listing GET per role per run, and only when the manifest claims something new.

**Two fields, two meanings.** `sub_type` holds the item's *substat* on every reader except WuWa's
Encore one, where it holds the weapon type and is deliberately copied into `weapon_class` — that
copy is what stops `**Substat:**` from repeating the class already in the badge
(`S-Rank W-Engine — Defense` … `**Substat:** HP%`). The metadata report labels `sub_type` "Substat"
to match the card's own row, and skips it when it is that copy, so a WuWa reclassification prints
one `Weapon class changed from ~~Sword~~ → **Rectifier**` instead of two lines saying the same
thing.

**A group nobody carded is named, not dropped.** The `__data.json` reader only reads the keys in
`_DATA_SECTIONS`; any other list on a revision (a group gachabase starts streaming later, such as
Genshin's materials) used to vanish at parse time with nothing downstream able to notice. It is now
carried through as `unknown_groups` and reported once per run —
`changelog lists group(s) with no card kind (materials) — not read` — the same way an unkinded
entry on the page path already was.

The prose is translated in some builds and not others — Booltergeist ships real English ("Cursed
Spotlight", "Specialty Scare Actor", "Mischief Maker on the Loose"), while Charley ships
localization keys (`Bangboo_Desc_54024`, `Bangboo_ActiveSkill_Title_54024`). A key is dropped,
never printed: a translated block renders `Active Skill — Cursed Spotlight: <text>`, one with a
title only renders `Active Skill — <title>`, one with text only `Active Skill: <text>`, and a block
that is keys on every side prints `-# Additional Ability: only localization keys in this build —
omitted until translated.` plus the single note `-# Some skill text is still untranslated in this
build; only the skill table is shown.` `{0}`-style placeholders in the prose are filled from the
values already resolved for that row, so a filled number never shows as `{0}` or as the
`[value unavailable]` fallback. A cooldown is whatever the build says it is: a literal (`28s` on
Ariel, printed with the rest) or a bare key (`Bangboo_ActiveSkill_Property_CD_54024` on Charley,
dropped without disturbing the rows after it). CN text is never merged into EN text: a keyed slot stays as it is, and a CN-only change is posted
as CN text with a note.

Stats are the page's max-promotion line, and only what the file states exactly: `break_stun` 103 →
Impact, `crit` 500 + the max-rank `extra` 4500 → `5,000 / 100` = **50%** CRIT Rate, `crit_dmg` →
100%, `pen_ratio` → 0%, `element_abnormal_power` 110 → Anomaly Mastery. Every S-rank Bangboo on the
two sites shares that block (Charley and Ariel are both 4,210 / 8,863 / 666 — 103 / 50% / 100% / 0%
/ 110), so it is printed once per card and never guessed from the level table. The two sites name that last
field differently — gachabase "Anomaly Mastery", nanoka "Anomaly Proficiency" — and the card uses
gachabase's, because that is the page its link opens. HP/ATK/DEF are **not** printed: both pages
level-scale them (Charley 4,210 / 8,863 / 666, Booltergeist 3,827 / 6,570 / 781 at Lv. 60) and no
factor fits those against `stats` + `level[]` (`level[].hp_max` sums to 3,500 against 4,210 while
the ATK blocks sum to 10,803 against 8,863), so they are left out rather than approximated. Rank
follows the same zzz `+1` mapping as everything else: raw `4` is the **S-Rank** of `ID: 54024`, raw
`3` the **A-Rank** of Booltergeist. The card is `[NEW]` when the manifest's `new.bangboo` lists the
id, and its heading is the `Bangboo` kind label (`set_kind` stays empty, so no `*Bangboo*` line
repeats under it). Nanoka's per-version diff feed
(`ww/3.8.1/diff/en.json`, `/diff#anchor` pages elsewhere) is deliberately not read: the card's
diff is computed from two retained snapshots, which is what lets it print `~~old~~ → **new**`
per value.

Per-game namespaces and labels are declared in `config/games.json` (`beta.nanoka`,
`beta.changelog`) and mapped in `gamexpress/beta.py::NANOKA_KINDS`:

| Game | `nanoka` | Changelog | Character | Weapon | Set |
|---|---|---|---|---|---|
| Genshin Impact | `gi` | `gi.gachabase.net/changelog/beta` | Characters | Weapons | Artifacts |
| Honkai: Star Rail | `hsr` | `hsr.gachabase.net/changelog/beta` | Characters | Light Cones | Relics & Ornaments |
| Zenless Zone Zero | `zzz` | `zzz.gachabase.net/changelog/beta` | Agents | W-Engines | Drive Discs |
| Wuthering Waves | `ww` | *(none — manifest-driven)* | Resonators | Weapons | Echoes |

**Wuthering Waves** has no gachabase site, so its revision comes from the manifest's
`new` lists alone. That is the correct scope there: the manifest says exactly what is
new in `latest`; the public pair-by-pair comparison lives on Encore instead (see
[Encore's version comparison page](#encore-version-comparison-page-wuwa) below). Each internal fallback
also keeps that manifest id explicitly rather than reparsing it from the human-facing singular
`ww.nanoka.cc/character/<id>/`, `weapon/<id>/` or `relic/<id>/` URL; this keeps new WuWa
characters, weapons and echoes on the same bounded detail/delivery path as the other games.

### Encore version comparison page (WuWa)

Encore also publishes a **version-comparison page** that is exactly the per-revision diff
Wuthering Waves otherwise lacks. Its own UI builds this query (observed 2026-10-30):

```
https://encore.moe/diff?firstGameVer=3.8.0&secondGameVer=3.8.0
        &firstVer=Beta_3.8.2&secondVer=Beta_3.8.3&route=character&id=1512&lang=en
```

`firstVer` / `secondVer` are the beta **patch** versions (`Beta_<x.y.z>`), `firstGameVer` /
`secondGameVer` the game version each patch belongs to (`3.8.x` → `3.8.0`), `route` is one of
`character | weapon | echo | term` (the type list the served compare page renders, captured
2026-10-30), and `id` is the numeric item id. `https://encore.moe/diff?lang=en` is the same tool
without a comparison selected. Echoes also have their own pages,
`https://encore.moe/echo/<id>?lang=en` (436 linked from the served echo index).

**Only the labels Encore has indexed resolve.** The page answers four distinct ways, all
observed 2026-10-31 against real ids:

| query | result |
|---|---|
| `3.8.0` / `Beta_3.8.2` vs `Beta_3.8.3`, echo `6000038` | renders the item and its changes |
| `3.8.0` / `Beta_3.8.3` vs `Beta_3.8.3` | renders the item's full current text (both sides equal) |
| `3.8.0` / `Beta_3.8.4` vs `Beta_3.8.4` | `Comparison failed: API error: 404` — a patch it has not crawled |
| `3.8.0` / `Beta_3.8.0` vs `Beta_3.8.3` | `No comparison data available` — a label it never offers |

Under `3.4.0` its picker offers `Release_3.4.13` only, so `Beta_3.4.0`/`Beta_3.4.1` — labels
nobody can choose — also answer 404. **Nanoka's revision numbers are not that list**, so the card
does not guess with them: `beta._encore_diff_url` builds the query from Encore's *own* current
beta, the `GameVer`/`ResVer` pair `/new?v=Beta` reports (`3.8.0` / `3.8.3` as of this capture).
With no earlier beta to name (first post of an item) it compares that patch with itself; that
form is in the picker by construction, renders for character, weapon and echo alike (all three
opened), and — because it needs no earlier patch — it also covers an item that is `[NEW]` in the
revision being posted, which previously had no link at all.

**Within one cycle, each beta is compared with the one before it.** A cycle is one game version
(`GameVer`, e.g. `3.8.0`), and its betas are the patches Encore lists under that version:
`Beta_3.8.1`, `Beta_3.8.2`, `Beta_3.8.3`. The card compares the beta it is posting with the beta
last posted, both under the same `GameVer`: `3.8.1 → 3.8.2`, then `3.8.2 → 3.8.3`. Both were
checked live on 2026-10-31 — Lily's Basic Attack Stage 1 changed between them, and the
`3.8.2 → 3.8.3` page shows that change. `Beta_3.8.0`, the base the beta started from, is not in
the picker, so the first beta of a cycle has nothing earlier to compare with and links to its
own text.

**Never across a game version.** A released build (3.7) or the previous cycle's beta is a
different build, not an earlier patch of this one. `Beta_3.7.3 vs Beta_3.8.3` is that mistake,
and the code does not produce it: a different `GameVer` on the previous side means the link
and the card's content both start a fresh baseline. Encore's comparison is only meaningful
inside one cycle.

**Released characters use the same link.** The link works for any item id, not only new ones.
A released character that later gets a buff or fix is still reported through the normal
revision diff, and the link opens Encore's comparison for that item across the two betas.

**Future versions: no code path names a version.** Verified only by simulation so far — same-cycle bumps and cycle changes both build the expected link through the card path (`test_feature5_a_new_game_version_links_across_the_cycle_change`). The live pages for a cycle that does not exist yet cannot be checked. `GameVer`/`ResVer` are read live on every run and the
previous pair comes from the snapshot the same reader wrote, so `4.0.0` / `Beta_4.0.2` builds the
same URL as `3.8.0` / `Beta_3.8.3`. Nothing in this path, or in the nanoka listing/detail paths or
the gachabase changelog path, is pinned to a version: revisions come from the manifest and the
streamed changelog, and item paths carry no version at all. Echo **sets** are not a separate card
kind for WuWa — they are rendered inside each echo's own comparison, which is where they appear on
the page (verified above).

The read behind it is **one small GET per run**, taken lazily at the first item that needs a
link, cached for the rest of the run, and skipped entirely when the request budget is spent — a
link must never cost the card it decorates. If it cannot be read, the link falls back to the two
revisions the card compared (`beta._encore_pair_url`), i.e. exactly what shipped before, so a
failed metadata read degrades the link instead of removing it. The card renders it as the
standard `[Revision diff](…)` link: Encore for WuWa, gachabase for the other three
(`beta._diff_url`).

**Limitations.** The destination is a client-side page, not a documented JSON endpoint: the bot
links to it and never scrapes it, so it adds no schedule and no content dependency — one
metadata read, described above, is the only cost. It is not used to discover changed ids — WuWa
revision scope still comes from the nanoka manifest. The query grammar is observation evidence
from the site's own URLs, not a published contract; if Encore changes it, the link degrades to
its landing page and the card content is unaffected. All four types are offered by the page
itself, so a WuWa echo links its `echo` comparison; `term` (the glossary) is not a card kind and
is refused rather than guessed.

### Encore beta API fallback for WuWa

Encore **does expose beta data**. The supplied OpenAPI export omits the `v` selector;
inspection of the live site's frontend and API on 2026-10-25 confirmed:

- `https://api-v2.encore.moe/api/en/new?v=Beta` returns `GameVer`, `ResVer` and
  `Changelist`, followed by new-content IDs.
- `.../character/<id>?ver=latest&v=Beta` returns character skills, level values, stat
  bonuses, resonance chains and properties; `.../weapon/<id>?ver=latest&v=Beta` returns
  weapon effects/refinement values and properties. Hsin (`1311`) and Suoming (`1312`)
  were confirmed in the beta character list and detail responses. Both are released characters;
  presence in that full catalog does not make them new beta announcements. The inspected current
  beta metadata was `3.8.0` / `3.8.1` / `9162983`; this is observation evidence, not a fixed
  value in code.

Feature 5 uses this API **only as a missing/unreadable character or weapon detail fallback**
for the manifest's current WuWa build. Nanoka still selects ordered revisions and IDs.
Try `https://api-v2.encore.moe/api/en` first, then the documented official legacy server
`https://api.encore.moe/en` if the primary read is unusable. The legacy path has no `/api` prefix.
Both were verified with matching beta metadata and identical normalized Lily/Lullaby display
fields on 2026-10-25; this adds endpoint redundancy within Encore, not an independent data authority.
Each server attempt reserves three calls in both existing request limits: beta metadata, detail,
then beta metadata again, all on that same server. Even an early failure consumes its full
reservation; both attempts together permit at most six `get_json` calls per item, each
retaining the existing one-retry policy for HTTP failures. A successful
primary read adds zero backup requests. `ResVer` must exactly equal the selected current nanoka version;
all three metadata fields must remain unchanged across the read, and the returned item ID
must match. If neither server passes these checks within the budget, the item stays deferred.
An older retained revision cannot use either server. A healthy nanoka detail makes zero Encore
requests. No release endpoint or unqualified API fallback is used.

Character attributes use the published Lv.10 array position; properties use explicit Lv.90
rows only. Weapon effects retain the API's refinement 1–5 values and label them accordingly.
Unpublished parameters remain marked unavailable. HTML is converted to readable text. Each
fallback item links to its Encore beta page and retains provider/build metadata in its bounded
snapshot. A provider switch produces a full labelled snapshot rather than a misleading diff
between different schemas. Media still uses the existing verified/locked path; Encore's raw
asset paths are not guessed into splash-art URLs.

This complements the nanoka timeline. It does not independently poll every Encore changelist,
reconstruct historical Encore builds, provide an echo fallback, or claim that matching resource
versions make two publishers' data identical. Metadata bracketing is a best-effort consistency
check of the mutable current API, not an atomic historical snapshot. Earlier documentation
classifying Encore as research-only was based on the incomplete OpenAPI export and is superseded
by this observed beta selector and bounded integration.

The additional asset references were assessed for backups on 2026-10-25. The inspected Lily
response points to Ciaccona/Xiakong art and Lullaby's icon to weapon `21030056`; the inspected
`WW_Asset_Webp` folder has no `21030076` icon. Returning HTTP 200 cannot establish correct item
art. The inspected `ZenlessAssetScrape` index has no beta-marked rows or current `1601`/`1661`
entries, while `WW_Data`'s published branches/README stop at release 3.7. These sources do not
currently fill the verified current-beta gap, so no speculative asset lookup, release-data
fallback or extra polling is added. Encore echo detail has additional nested IDs/set fields
requiring a separate validated adapter; it is not treated as interchangeable character/weapon data.

What is deliberately **not** done:

- **No official splash-art API call per character.** The HoYo content API
  (`sg-public-api-static.hoyoverse.com/content_v2_user/.../getContent`) does serve
  `new-chara-cover-inner`, but its `iAppId` differs per title and the database's
  character ids do **not** match the official `iInfoId`s (nanoka `1661` vs official
  `166651`), so any mapping would be a guess. The card uses the database's own art,
  which is present for every named entry.
- **No direction is inferred from one snapshot.** Once two retained structured snapshots
  exist, only unambiguous value semantics receive `[BUFF]` / `[NERF]`; ambiguous values stay
  `[CHANGED]`, and text-only edits `[TEXT FIX]`. This is why the monitor retains the previous
  readable kit instead of attempting to scrape a rendered diff page.
- **Placeholder images are dropped.** `cdn.gachabase.net/.../missing.webp` is the
  database saying it has no art yet — it is filtered out and the gallery is omitted
  cleanly rather than posting a broken image. Known static nanoka art conventions are only
  used after the same bounded media preflight, then their URL is locked.
- **Unlocalised backend keys never reach a card.** Strings like `TestKey_PlaceHolder`,
  `Robin_Skill_Normal_Title` and `EquipmentSuit_34300_name` are recognised and dropped
  (`gamexpress/beta.py::_is_key`), so an unfinished localisation shows as "no text yet"
  instead of a wall of internal identifiers.

### Verified skill-level caps, curves & offline client-schema references (2026-10-27)

Client skill-level caps and stat curves are enforced at build time in `gamexpress/beta.py`
so unused raw client padding rows (`Lv. 15` / `Lv. 20`) never leak into rendered multipliers:

| Game | Base (E0 / C0 / M0 / S0) caps rendered on cards |Dupes (`+levels`) | Raw table padding ignored | Equipment & curve notes |
|---|---|---|---|---|
| Wuthering Waves | `Lv. 10` (`Normal Attack`, `Resonance Skill`, `Forte Circuit`, `Resonance Liberation`, `Intro Skill`); `Outro Skill` & `Tune Break` unleveled | `S1–S6`: `+0` skill levels | Rows `11–20` in `param[0]` | `lvData.format` / Encore `Description` units (`s`, ` HP`, ` DEF`) preserved; Echoes evaluated at max `Rank 5` (`skill.param[-1]`), Sonata `set[n].param` interpolated |
| Zenless Zone Zero | `Lv. 12` combat skills (`main + growth × 11`) + `Core Skill F` (`passive.level` max rank, `extra_level.6` flat bonuses) | **M3** `+2` (`Lv. 14`), **M5** `+2` (`Lv. 16` max); **M6** `+0` | Rows `13–16` at M0 | `prop=12101` flat Base ATK strictly separated from `12102` `ATK%`; `Armorer` (`7`), `Wind` (`204`), `Lumiflux` (`300`) enum fallbacks built in |
| Honkai: Star Rail | `Lv. 6` (`Basic ATK` / `普攻`, `Memosprite Skill/Talent` / `忆灵`), `Lv. 10` (`Skill`, `Ultimate`, `Talent`, `Elation Skill`, `Assist Skill`), `Lv. 1` (`Technique` / `秘技`) | **E3/E5**: `Lv. 7` Basic/Memosprite, `Lv. 12` Skill/Ult/Talent/Elation | Rows `8–10` & `13–15` | `#n[f1]`/`[f2]` float formatters + `{RUBY_*}` furigana stripping; EN & `/zh/` slots share identical caps |
| Genshin Impact | `Lv. 10` (`Normal Attack`, `Elemental Skill`, `Elemental Burst`); `Lv. 1` for single-level alternate sprints | **C3/C5**: `+3` (`Lv. 13`) | Rows `14–15` | `Lv. 90` weapon substats computed from `sub_prop_value × 4.594` (`GROW_CURVE_CRITICAL_{101,201,301}`) when listing omits substat percentage |

Additional community and client-table repositories (`seriaati/hb-data`, `gi.yatta.moe` /
`sr.yatta.moe`, `HomDGCat`, `Mar-7th/StarRailRes`, `malu-no996/ZenlessData`,
`d4rkOfficial/wuwa-afyg-tool`, `everbird/ww-dps-sim`, and `t.me/s/nanoka_news`) were audited
on 2026-10-27. Mutable latest-only endpoints (`gi.yatta.moe/api/v2`, `sr.yatta.moe/api/v2`)
cannot serve immutable historical revision diffs, and multi-hundred-MB raw git dumps
(`hb-data` upstream repositories) are unsuitable for low-cost scheduled runs; instead, their
verified client curves, property IDs, markup grammars (`<Term:...>`, `<highlight>`, `{RUBY_*}`),
and enum tables are baked directly into `gamexpress/beta.py` with **zero extra HTTP requests**.


### Feature 3 follow-up: bounded fidelity audit and SKPORT (2026-11-27)

In [read-only audit 46119240484](https://github.com/uesu/Game-Express/actions/runs/46119240484),
the observed NTE and Silver Palace listings contained 103 and 21 articles respectively; every
body parsed, and all 118 distinct body-media URLs responded to bounded signature inspection.
No NTE body media in that snapshot was GIF-signature data. Twelve Silver URLs had GIF signatures
although their path ended in `.jpg`, including all 9 body images in Silver article 93 and all 3
in article 99. We retain the publisher URL and rely on media bytes/MIME, not extension; this
is not a guarantee about future media or Discord rendering. The NTE 262101 and 262255 samples
preserved 660 and 521 masked UIDs in source order with separators; 262998 put its Important Notes
heading and first note on the same page. A later read-only audit checked all 30 observed account
notices. These checks do not establish upstream completeness.

The public [SKPORT Endfield community](https://www.skport.com/game/endfield) mixes user posts
with SKPORT promotional material. The inspected public page/static script did not establish an
accessible, documented community feed with reliable official-publisher authorship. The community
[SKPORT API documentation](https://github.com/AixLnyt/skport-api-docs) describes game/account and
wiki APIs, not a verified official-post feed. No SKPORT adapter, login, account token collection,
or official-source assumption is added. An enhancement would first need an authorized public
feed, durable post IDs, official-author verification, pagination/completeness checks and terms
review; community posts would need a separately labelled opt-in source.

The official [ZZZ Sunbringer EP HoYoLAB post](https://www.hoyolab.com/article/47586861) contains
a YouTube embed represented in structured content as a video but no native article image/video.
[Read-only audit 46119433799](https://github.com/uesu/Game-Express/actions/runs/46119433799)
verified the fallback thumbnail without posting. This fallback is allowed for official HoYoLAB and
Kuro articles as well as the three inactive candidates, only when no native image/video (or
unavailable-native-video marker) is present; actual thumbnail bytes and dimensions are checked.

#### Silver Palace Discord animation investigation

The prior byte-signature audit established source GIF data, **not Discord playback**. The user
confirmed the direct CDN URLs appeared static in Discord despite animating on the official site.
A subsequent [header probe](https://github.com/uesu/Game-Express/actions/runs/46121800531) showed
GIF-signature media served with `Content-Type: image/jpeg`; this mismatch is a plausible cause,
not proof of Discord's internal behavior. Observed samples are about 8–20 MB, so uploading each
unchanged may exceed a destination's upload limit. Two private Components V2 attachment experiments
were posted for visual evaluation: article 99's original bytes as `image/gif` (105 frames,
960×540), and a size-reduced article 93 GIF (75 frames, 480×270, 8 fps). Discord accepted the
99 attachment and reported `image/gif` for its gallery item. Acceptance and frame count do not
prove the Discord client animates it; user verification is pending. The temporary research-only
FFmpeg executable is supplied by `imageio-ffmpeg` and is not a production dependency or conversion
pipeline. No production media or delivery behavior has been changed for this experiment.
