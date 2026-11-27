# Research dossier — the new-game probe, and the two code sources that were rejected (2026-11-27)

This file records a **probe**, not a roadmap promise: every line below was checked against live
bytes on 2026-11-27, and every claim names the evidence that proves it (committed under
`tests/fixtures/probes/`, or a specific file and line in an upstream repository). Nothing here is
inferred from a search result, a screenshot or another project's README.

The rule this dossier is written to: **a source joins the monitor only when it is both independent
and reliably available.** "Usually answers" is not enough — the monitor's contract is a correct card
on *every* run, and a source that hangs, 404s or half-renders is worse than no source at all,
because it makes the other sources look silent.

| Question | Answer | Integrated? |
|---|---|---|
| `crimsonwitch.com` as a code source | **No** — it is ennead's own upstream, and its availability is not guaranteed | **No** (see §2) |
| `heartlog/Hoyocodes` | **No** — a client-side UI over `api.ennead.cc`, already covered | **No** (see §3) |
| NTE — codes | `ogc:nte` is a known game that currently answers `[]` | Not yet (§4 why) |
| NTE — feature 3 (news) | **Feasible** — static, server-rendered article HTML with pagination | Not yet (§4 why) |
| Endfield — codes | `ogc:endfield` answers 5 live codes with rewards | Not yet (§4 why) |
| Endfield — feature 3 (news) | **Blocked** — the CMS needs an undocumented `appCode` | No (§5) |
| Silver Palace — feature 3 | **Blocked** — the SSR payload carries no news entries | No (§6) |

**Nothing in the production path changed in this pass.** No game was added to `config/games.json`,
no source kind was added to `sources/codes.py`, and no card, gate, ranking, expiry, dedupe,
corroboration or posting behaviour moved. The one shipped change is the operator-invoked,
read-only probe job described in §7.

## 1 · How the probe was run

The sandbox that wrote this file has **no outbound HTTPS**, so every fetch went through the
dispatch-only `source-probe` job in [`.github/workflows/ci.yml`](../.github/workflows/ci.yml):

```bash
gh workflow run ci.yml --ref <branch> \
  -f urls=$'https://example.com/a\nhttps://example.com/b' \
  -f mode=save -f pattern=initialCodes -f max_bytes=120000
```

`mode=save` commits the response bytes to `tests/fixtures/probes/<host>_<path>.body.txt` with a
matching `.url.txt`, so the evidence is reviewable instead of living in a log that expires.
`mode=report` (the default) prints status, size and the `pattern` hits without committing anything.
The job is dispatch-only, never runs on `push`/`pull_request`, takes `contents: write` only for
`mode=save`, uses fixed public URLs (no secrets, no redirects, bounded sizes and timeouts) and is
**not** a merge gate.

## 2 · Crimson Witch — rejected (not an independent witness)

`https://www.crimsonwitch.com/codes/{Genshin_Impact,Honkai_Star_Rail,Zenless_Zone_Zero}` is a
Next.js App Router page. Its codes are readable server-side — they ride in the RSC stream as
`self.__next_f.push([1,"…"])` chunks whose decoded text carries a structured `initialCodes` array
(`code`, `added`, `expires`, `rewards[{item,qty}]`, `region_locked`) — and the probe captured 5 live
Genshin codes and 2 live ZZZ codes that way
(`tests/fixtures/probes/www.crimsonwitch.com_codes_*.body.txt`).

**Readable is not the same as admissible.** Two verified reasons sank it:

1. **It is not a second witness — it is `ennead`'s first one.** `api.ennead.cc` is served by
   `torikushiii/hoyoverse-api`, and that repository's collectors fetch Crimson Witch *themselves*.
   At revision `85be7728`:
   `src/scraper/sources/genshin/mod.rs` declares
   `const CRIMSON_WITCH_URL: &str = "https://www.crimsonwitch.com/codes/Genshin_Impact";`, joins
   `crimson_witch::scrape(&global.http_client, CRIMSON_WITCH_URL)` into a `tokio::join!` beside the
   fandom, game8 and hoyolab collectors, and stores the result under the source name
   `"crimson_witch"`. `src/scraper/sources/starrail/mod.rs` and
   `…/zenless/mod.rs` do the same for their games.

   So `ennead` and `crimsonwitch` are **one data lineage**. A `crimsonwitch:` source would re-read
   ennead's own upstream, and any row it produced would be ennead quoting itself as a second opinion — the exact
   double-count `SOURCE_FAMILY` exists to prevent (`ogc` → `ennead`, codehub → its upstream). Giving
   it a family of its own would have been a bug, not a feature.

2. **Its availability is not guaranteed.** One volunteer-run tracker; during the probe its RSS
   (`/feeds/{game}/rss.xml`) was dead and the in-page search returned nothing for codes. The page
   answered on the prober's runs, but a monitor cannot be built on "it answered twice on a good
   day" — a source that is intermittent turns into a silent gap plus a failed-source line on every
   card.

Verdict: **not integrated**, and no configuration references it. The reverse direction is the honest
one — the codes still reach a card through `ogc`/`ennead`, which is where they come from.

## 3 · heartlog/Hoyocodes — already covered, nothing to add

`github.com/heartlog/Hoyocodes` and its Pages build are a **static UI**: the bundle fetches
`https://api.ennead.cc/mihoyo/{genshin,starrail,zenless}/codes` in the visitor's browser and renders
it. Last commit 2026-09-07. It is a client of the same backend the `ennead:`/`ogc:` sources already
read directly, so it can never be an independent witness, and adding it would only re-read a page
that says what `api.ennead.cc` says.

The ranking is unaffected by design: `ennead`/`ogc` keep their single vote and the community
Reddit listing keeps its witness role (`CODES_MIN_SOURCES = 2`, one family = one vote). **No change
made.**

## 4 · Neverness to Everness (`nte`)

| Feature | Verdict | Evidence |
|---|---|---|
| 1 · schedule | **not verified** — no official banner table was found for a title that has not launched | `www.nte.perfectworld.com_en_article_news_index.html` |
| 2 · codes | **ready to configure** — `ogc:nte` is a known game that currently answers `[]` (valid, simply no live codes) | probe of `https://api.ennead.cc/codes/nte` |
| 3 · news | **feasible** — static, server-rendered article HTML | `www.nte.perfectworld.com_en_article_news_gamebroad_20261123_265196.html` (25 KB of real article body) |
| 4 · pre-load / maintenance | **not verified** — Perfect World publishes no endpoint this probe could confirm | — |

The news index at `https://nte.perfectworld.com/en/article/news/index.html` lists three tabs —
`gamenews`, `gamebroad`, `gameevent` — with URLs of the shape

```
/en/article/news/<tab>/YYYYMMDD/<id>.html , paginated by indexN.html
```

The page's screenshot listed **35 notice pages**, and the fetched article is a plain
server-rendered document, so `sources/newspage.py` (already used for the Wuthering Waves news
adapter) can read it as-is with `news_url` pointed at the index. `r/NevernessToEverness` (98 K
members) is the community witness for News-Express.

## 5 · Arknights: Endfield (`endfield`)

| Feature | Verdict | Evidence |
|---|---|---|
| 1 · schedule | **partial** — `endfield.wiki.gg` line-ups already travel through `Kitsudock-data` (`hub.json`), the same path the other games use | [BANNER_DATABASE.md](BANNER_DATABASE.md) |
| 2 · codes | **ready to configure** — `ogc:endfield` answered with 5 live codes carrying rewards and no expiry | probe of `https://api.ennead.cc/codes/endfield` |
| 3 · news | **blocked** on one missing constant | below |
| 4 · pre-load / maintenance | **not verified** — Gryphline exposes no maintenance gate this probe could confirm | — |

Feature 3: `https://endfield.gryphline.com/en-us/news` **is** server-rendered and lists titles,
dates and covers, but every `href` in the list is empty — the page expects the client to resolve the
CMS ids. The client bundle does that:

```js
r.get("/api/bulletin", { params: { lang, code: cms.appCode, page, pageSize: 9, tabs: [n] } })
r.get("/api/bulletin/" + cid, { params: { lang, code: appCode } })
```

with base `https://endfield.gryphline.com`. Probed live, all of these answer
`{"message":"Cannot GET /api/bulletin?…","statusCode":404}`:

* `https://endfield.gryphline.com/api/bulletin?lang=en-us…`
* `https://web-api.gryphline.com/api/bulletin…`
* `https://endfield.gryphline.com/api/bulletin/1…`

`cms.appCode` is **not** in the chunks the probe captured
(`endfield.gryphline.com_next_static_chunks_*.js`), so the endpoint cannot be called yet. The page
itself is fresh — its newest notice was dated **2026-11-25**. `r/Endfield` (157 K, partnered with
Gryphline) is the first choice for News-Express, `r/ArknightsEndfield` (65 K, unofficial) the
secondary.

## 6 · Silver Palace — feature 3 only, blocked

`https://silverpalace.elementagames.com/en-us/news` is a Nuxt site whose state is a **placeholder**:

* `_payload.json` returns 69 bytes: `[{"data":1,"prerenderedAt":3},["ShallowReactive",2],{},1700000000000]`
  — an empty payload, not a list of news.
* `__NUXT_DATA__` on the live page contains only i18n strings and site config (`"Silver Palace"`,
  locales `en-US`/`zh-CN`). **No news entry exists in the SSR output at all**, so there is nothing to
  parse and nothing to fall back to.

**Blocked** until their (almost certainly post-hydration) news API is discovered. The page does
confirm the **2026-12-14 global launch**, which is why the title is in scope at all.
`r/SilverPalaceOfficial` (42 K) is the community witness.

## 7 · What actually shipped: the probe job

The only production-file change in this pass is the manual probe: a `source-probe` job in `ci.yml`
(`mode=summary|links|grep|raw|save`, `workflow_dispatch` only), so a candidate endpoint can be
*proven* from a runner when a development sandbox cannot reach the vendor host. It is read-only for
every mode except `save`, it never posts to Discord, never writes state, and never gates a merge.
Its `actions/checkout` is pinned to a commit SHA like every other `uses:` in this repository.

## 8 · Why NTE and Endfield are not in `config/games.json` yet

`config/games.json` is not a list of pages to read — it is the contract every feature is tested
against. `tests/test_smoke.py` asserts, for **every** configured game:

* a YouTube channel and X account (`test_games_config_is_valid`),
* at least one row in each reveal-ping table (`test_reveal_ping_*`),
* a beta/benchmark row (`test_reproducible_beta_enabled_benchmark_…`),
* participation in the official-feed inventory (`test_every_official_feed_a_game_declares_is_actually_requested`).

Those guards are what stop a half-configured game from shipping silent. Adding the new titles needs
metadata this probe could **not** verify — launch schedules, X handles, YouTube channel ids and
reveal-format rows for three titles, one of which has not launched. Wiring the two that *can* be
wired (NTE, Endfield) means either inventing that data or relaxing the invariants; the first is a lie
in the config, the second removes the guard that keeps the config honest. (This was not theoretical:
adding the entries made exactly those four checks fail.)

Ready to paste once the metadata is verified:

```json
"nte":      { "enabled": false, "released": false,
              "codes": { "sources": ["ogc:nte", "reddit:NevernessToEverness"] } }
"endfield": { "enabled": false, "released": false,
              "codes": { "sources": ["ogc:endfield", "reddit:Endfield", "reddit:ArknightsEndfield"] } }
```

Both pass `python -m gamexpress validate` today (codes-only entries are legal, and there is no
`Redeem` button until a `redeem_url` is verified).

## 9 · Checklist for the next pass

1. NTE — verify launch date and the X/YouTube handles; add `news_url` (`…/en/article/news/index.html`)
   plus the `sources/newspage.py` pattern for `gamenews`/`gamebroad`/`gameevent`.
2. Endfield — find `cms.appCode` to unblock `/api/bulletin`, or wait for the official RSS/Atom if one
   appears.
3. Silver Palace — re-probe after the 2026-12-14 launch; look for a hydrated news endpoint.
4. All three — add the per-game rows the smoke tests demand, then flip `enabled`/`released`.
5. News-Express side is **not** part of this repository: `r/NevernessToEverness`,
   `r/Endfield` + `r/ArknightsEndfield`, `r/SilverPalaceOfficial`.

## Related documents

* [SOURCES.md](SOURCES.md#evaluated-but-not-integrated-and-why) — the rejection rows this dossier
  feeds.
* [CONFIGURATION.md](CONFIGURATION.md) — the `codes.sources` spec syntax.
* [changelog](changelog/CHANGELOG.md#2026-11-27--probe-verdicts-two-code-sources-rejected-and-the-new-game-findings)
  — the entry for this change.
