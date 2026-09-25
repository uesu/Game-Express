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
| Tweet details | `https://api.fxtwitter.com/status/{id}` → `https://api.vxtwitter.com/Twitter/status/{id}` | full text with expanded links, photos, exact timestamp | ✅ all 4 reference tweets |
| Kuro official site (WW) | `https://hw-media-cdn-mingchao.kurogame.com/akiwebsite/website2.0/json/G152/en/{ArticleMenu,MainMenu}.json` + `…/article/{id}.json` | official articles incl. *Featured Resonator/Weapon Convene* banner notices; times are UTC+8 | ✅ (English menus are homepage **subsets**, so X stays primary for WW) |
| HoYoPlay launcher | `https://sg-hyp-api.hoyoverse.com/hyp/hyp-connect/api/getGameBranches?launcher_id=VYTpXlbWo8` | exact live version (`main.tag`) + pre-install availability (`pre_download`) | ✅ ZZZ `3.2.0` |
| Kuro launcher (WW) | `https://prod-alicdn-gamestarter.kurogame.com/launcher/game/G153/50004_obOHXFrFanqsaIEOmuKroCcbZkQRBC7c/index.json` | live version (`default.version`) + `predownload` | structure from WW downloader configs |

HoYoLAB game IDs: 1 HI3 · 2 Genshin · 6 Star Rail · 8 ZZZ · **9 Honkai: Nexus Anima** (already
wired for launch day).

**Why `getGameBranches` and not `getGamePackages`:** the legacy package list is stale for games
that moved to Sophon downloads. On 2026-09-24 it still reported GI 5.5.0 while the live game was
7.1.

## Redemption codes

| Source | Endpoint | Trust | Status |
|---|---|---|---|
| HoYoLAB livestream module (official) | `…/community/painter/wapi/circle/channel/guide/material?game_id={2,6,8}` → `data.modules[].exchange_group.bonuses[].exchange_code` | **official**: posts immediately | ✅ (empty outside livestreams, as expected) |
| hoyo-codes.seria.moe | `https://hoyo-codes.seria.moe/codes?game={genshin,hkrpg,nap}` | **redeem-validated** (`status: OK`): posts immediately | ✅ |
| api.ennead.cc | `https://api.ennead.cc/mihoyo/{genshin,starrail,zenless}/codes` (`active` list only) | community | ✅ |
| Fandom wikis (MediaWiki API) | `https://{wiki}.fandom.com/api.php?action=query&prop=revisions&titles={page}&rvprop=content&rvslots=main&format=json` | community | same query seria + PromoGacha use |
| PromoGacha data | `https://raw.githubusercontent.com/gripcrip-blip/codehub/main/data/codes.json` | community (incl. Wuthering Waves) | ✅ (repo cloned; daily GHA) |
| Official posts | X / HoYoLAB text that explicitly lists "Redemption Codes" | **official**: posts immediately | extraction tested on real tweets (no false positives) |

**Gate:** official, or seria-verified, or ≥ `CODES_MIN_SOURCES` (2) community sources.

## Evaluated but not integrated (and why)

| Candidate | Verdict |
|---|---|
| YouTube channel RSS (`/feeds/videos.xml?channel_id=`) | returned **404** during verification (even for Genshin's confirmed channel ID). YouTube links and thumbnails come from the official tweets and HoYoLAB posts instead |
| parse.bot marketplace APIs (prydwen / icy-veins / genshin.gg / hoyolab) | paid third-party scrapers, not verifiable; not needed for official data |
| `getGamePackages` (HoYoPlay legacy) | stale for Sophon games (see above) |
| Hoyotod/code · Hoyotod/redeem | fandom-scraper pattern (we call the MediaWiki API directly) · redeem automation (requires accounts; out of scope) |
| heartlog/Hoyocodes · promogacha.netlify.app | static sites. PromoGacha's GitHub JSON **is** used |
| chiraitori/HoYo_Code_Sender_Discord_Bot · Hum-Bao/hoyoverse-codes(-backend) · retvil/hoyo-code-monitor | reference implementations; their sources are covered above |
| DuolaD/HoYo_Versioncatcher | launcher-data repo; led us to the launcher endpoints |
| genshin.dev | character/game data API, not schedules or codes |
| gachabase.net · nanoka.cc · sr.yatta.moe · lunaris.moe · ambr.top | databases, listed in README → resources. No public schedule/banner API was verified, so **banner names come from official notices or `config/overrides.json`** |

## Games not yet released

- **Honkai: Nexus Anima**: HoYoLAB gid 9 + X `@HonkaiNA` are configured (`enabled: false`). At
  launch, add the HoYoPlay `game_id`, YouTube/Twitch and code sources.
- **ANANTA** (NetEase, launches 2027‑01‑15): X `@Ananta_EN` is configured (`enabled: false`).
  It is not a character gacha, so the card hides banners.
