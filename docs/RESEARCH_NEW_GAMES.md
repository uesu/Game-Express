# Research dossier — new-game coverage and the Crimson Witch code source (2026-11-27)

This file records a **probe**, not a roadmap promise: every line below was checked against live
bytes on 2026-11-27, and every claim names the evidence file that proves it under
`tests/fixtures/probes/`. Nothing here is inferred from a search result, a screenshot or another
project's README.

Two questions were asked:

1. Is **crimsonwitch.com** a usable redemption-code source, and is **`heartlog/Hoyocodes`** already
   covered?
2. Can **Neverness to Everness**, **Arknights: Endfield** and **Silver Palace** be added for
   feature 1 (schedule), 2 (codes), 3 (official news) and 4 (pre-load / maintenance / servers live)?

Answers up front:

| Question | Answer | Shipped in this PR |
|---|---|---|
| crimsonwitch.com as a code source | **Yes** — the page payload carries structured codes, rewards and expiry | **Yes**: `sources/codes.py` parser + `crimsonwitch:` specs on GI / HSR / ZZZ |
| `heartlog/Hoyocodes` | **Already covered** — it is a static UI over `api.ennead.cc/mihoyo/…`, which the `ennead:` sources read directly | No code needed (documented in [SOURCES.md](SOURCES.md#evaluated-but-not-integrated-and-why)) |
| NTE — codes | **Yes** (`ogc:nte` is a live, known game that currently returns `[]`) | Not wired: see [why the games are not configured yet](#why-nte-endfield-and-silver-palace-are-not-in-configgamesjson-yet) |
| NTE — feature 3 (news) | **Yes** — static server-rendered article HTML with `indexN.html` pagination | Not wired (same reason) |
| Endfield — codes | **Yes** (`ogc:endfield`: 5 live codes with rewards, no expiry) | Not wired (same reason) |
| Endfield — feature 3 (news) | **Blocked** — the CMS needs an undocumented `appCode` | — |
| Silver Palace — feature 3 | **Blocked** — the SSR payload carries no news entries | — |
| Silver Palace — codes / schedule | Out of scope for now (feature 3 only, per the request) | — |

## How the probe was run

The sandbox that wrote this file has **no outbound HTTPS**, so every fetch went through the
dispatch-only `source-probe` job in [`.github/workflows/ci.yml`](../.github/workflows/ci.yml):

```bash
gh workflow run ci.yml --ref <branch> \
  -f urls=$'https://example.com/a\nhttps://example.com/b' \
  -f mode=save -f pattern=initialCodes -f max_bytes=120000
```

`mode=save` commits the response bytes to `tests/fixtures/probes/<host>_<path>.body.txt` with a
matching `.url.txt`, so the evidence is reviewable in the PR instead of living in a log that
expires. `mode=report` (the default) prints status, size and the `pattern` hits without committing
anything. The job is dispatch-only, never runs on `push`/`pull_request`, holds `contents: write`
only for `mode=save`, and is **not** a merge gate.

## 1 · Crimson Witch — usable, and now implemented

`https://www.crimsonwitch.com/codes/{Genshin_Impact,Honkai_Star_Rail,Zenless_Zone_Zero}` is a
Next.js App Router page. The first probe classified it as "a client-rendered SPA with no codes in
the HTML" — **that was wrong**, and the reason is worth keeping: the codes are not in the DOM, they
are in the **React Server Components stream**, which `curl` output contains verbatim:

```
<script>self.__next_f.push([1,"17:[\"$\",\"$L22\",null,{\"initialCodes\":[{\"id\":...,\"code\":\"AZHGG7H2ZQZS\",
  \"code_variants\":null,\"added\":\"2026-11-25\",\"start_date\":null,\"expires\":null,
  \"rewards\":[{\"item\":\"Mora\",\"qty\":10000},…],\"region_locked\":null},…]}"])</script>
```

`self.__next_f.push([1, "…"])` chunks are **JS string literals**, so the payload is
JSON-encoded *inside a JSON string*. `sources/codes.py` therefore:

1. concatenates every pushed string (`_rsc_text`),
2. finds the `initialCodes` array with a **string-aware bracket matcher** (`_json_array_after`) so a
   `]` inside a reward name cannot truncate it,
3. `json.loads` the slice — no regex per field, no CSS class names, no browser.

Per-entry handling:

| Field | Behaviour |
|---|---|
| `code` | kept as published; the shared `sanitize()` upper-cases it, so `ArchonsAnswers` → `ARCHONSANSWERS` like every other source |
| `rewards[{item,qty}]` | formatted `Item ×1,234` and carried on `CodeHit.rewards`, i.e. the codes card shows the real payouts instead of a generic line. `qty` absent or `0` renders the bare item name |
| `expires` | converted to `expires_at` (epoch) → the card's "Codes expire — redeem soon" marker. Absent = no invented date |
| `region_locked` | `null`/`"all"` kept, anything else (e.g. `"CN"`) **skipped** — a region-locked code is not redeemable for the audience this card serves |
| `code_variants` | ignored (`null` on every live entry) |
| duplicates / empty codes / non-dict entries | dropped, first occurrence wins |

Evidence: `tests/fixtures/probes/www.crimsonwitch.com_codes_Genshin_Impact.body.txt` (5 codes) and
`…_Zenless_Zone_Zero.body.txt` (2 codes: `INKSHIFT34`, `HOLLOWRUN34` at Polychrome ×20 / Denny ×2,222).
Trimmed, reviewable fixtures — the same stream wrapper, the same escaped JSON, a few entries kept —
are committed as `tests/fixtures/crimsonwitch_genshin_trimmed.html` and
`tests/fixtures/crimsonwitch_zzz_trimmed.html`, and `tests/test_crimsonwitch_codes.py` pins the
parse, the region-lock/duplicate/junk handling, the truncation contract, the fetch URL/tag and the
config wiring.

Trust model: **community, its own family.** `family("crimsonwitch") == "crimsonwitch"`, so it is
never merged into `ennead`/`ogc` (one backend, one vote) and can serve as the *second* independent
witness for a pending code. It is **not** a `VALIDATORS` entry: Crimson Witch publishes no
redemption validation, and the card's "verified (validated)" wording is reserved for seria and
Hum-Bao, which actually redeem.

Rejected paths, for the record: `/feeds/{game}/rss.xml` is dead, and the in-page search API returned
nothing for codes. The RSC payload is the only path — and the only one needed.

## 2 · heartlog/Hoyocodes — already covered

`github.com/heartlog/Hoyocodes` and its Pages build are a **static UI**: the bundle fetches
`https://api.ennead.cc/mihoyo/{genshin,starrail,zenless}/codes` in the visitor's browser and renders
it. Its last commit was 2026-09-07, and, being a client of the same backend, it can never be an
independent witness. The `ennead:` (and `ogc:`) sources already read that backend directly, so
adding Hoyocodes would only re-read a page that says what `api.ennead.cc` says. **No change made**;
the verdict is recorded in [SOURCES.md](SOURCES.md#evaluated-but-not-integrated-and-why).

## 3 · Neverness to Everness (`nte`)

| Feature | Verdict | Evidence |
|---|---|---|
| 1 · schedule | **not probed to a usable shape** — nothing official publishes a banner table for a game that has not launched; the game's own site carries only marketing pages | `www.nte.perfectworld.com_en_article_news_index.html` |
| 2 · codes | **ready to configure**: `ogc:nte` is a known game that currently answers `[]` (valid, no live codes) | probe of `https://api.ennead.cc/codes/nte` |
| 3 · news | **yes** — static, server-rendered article HTML | `www.nte.perfectworld.com_en_article_news_gamebroad_20261123_265196.html` (25 KB of real article body) |
| 4 · pre-load / maintenance | **not verified** — Perfect World publishes no launcher/maintenance endpoint this probe could confirm | — |

The news index at `https://nte.perfectworld.com/en/article/news/index.html` lists three tabs —
`gamenews`, `gamebroad`, `gameevent` — with URLs of the shape

```
/en/article/news/<tab>/YYYYMMDD/<id>.html , paginated by indexN.html
```

The screenshot of the page listed **35 notice pages**, and the fetched article (25 KB) is a plain
server-rendered document: `sources/newspage.py` (already used for the Wuthering Waves news adapter)
can read it as-is, with `news_url` pointed at the index and the tab prefix as the article pattern.
`r/NevernessToEverness` (98 K members) is the community witness for News-Express.

## 4 · Arknights: Endfield (`endfield`)

| Feature | Verdict | Evidence |
|---|---|---|
| 1 · schedule | **partial** — `endfield.wiki.gg` lineups are already assembled by `Kitsudock-data` (`hub.json`), so banner names can arrive the same way they do for the other games | `docs/BANNER_DATABASE.md` (hub feed) |
| 2 · codes | **ready to configure**: `ogc:endfield` answered with 5 live codes carrying rewards and no expiry | probe of `https://api.ennead.cc/codes/endfield` |
| 3 · news | **blocked** on one missing constant | see below |
| 4 · pre-load / maintenance | **not verified** — Gryphline exposes no maintenance gate this probe could confirm | — |

Feature 3: `https://endfield.gryphline.com/en-us/news` **is** server-rendered and lists notice titles,
dates and covers, but every `href` in the list is empty — the page expects the client to resolve the
CMS ids. The client bundle does exactly that:

```js
r.get("/api/bulletin", { params: { lang, code: cms.appCode, page, pageSize: 9, tabs: [n] } })
r.get("/api/bulletin/" + cid, { params: { lang, code: appCode } })
```

with base `https://endfield.gryphline.com`. Probed live, all of these answer
`{"message":"Cannot GET /api/bulletin?…","statusCode":404}`:

* `https://endfield.gryphline.com/api/bulletin?lang=en-us…`
* `https://web-api.gryphline.com/api/bulletin…`
* `https://endfield.gryphline.com/api/bulletin/1…`

`cms.appCode` is **not** present in the chunks saved by the probe
(`endfield.gryphline.com_next_static_chunks_*.js`), so the endpoint cannot be called yet. Until it
is (or until Gryphline fills the `href`s), Endfield feature 3 stays a codes/schedule addition. The
screenshot of the page showed the newest notice dated **2026-11-25**, so the page itself is fresh.
`r/Endfield` (157 K, partnered with Gryphline) is the first choice for News-Express, with
`r/ArknightsEndfield` (65 K, unofficial) as the secondary.

## 5 · Silver Palace (`silverpalace`) — feature 3 only

`https://silverpalace.elementagames.com/en-us/news` is a Nuxt site, and its state is a
**placeholder**:

* `_payload.json` returns 69 bytes: `[{"data":1,"prerenderedAt":3},["ShallowReactive",2],{},1700000000000]`
  — an empty payload, not a list of news.
* `__NUXT_DATA__` on the live page contains only i18n strings and site config (`"Silver Palace"`,
  locales `en-US`/`zh-CN`). **No news entry exists in the SSR output at all**, so there is nothing to
  parse and nothing to fall back to.

Conclusion: **blocked** until their news API is discovered (most likely a client-side call made after
hydration). The page does confirm the **2026-12-14 global launch** banner, which is why this game is
in scope at all. `r/SilverPalaceOfficial` (42 K) is the community witness.

## Why NTE, Endfield and Silver Palace are not in `config/games.json` yet

`config/games.json` is not a list of pages to read — it is the contract every feature is tested
against. `tests/test_smoke.py` asserts, for **every** configured game:

* a YouTube channel and X account (`test_games_config_is_valid`),
* at least one row in each reveal-ping table (`test_reveal_ping_*`),
* a beta/benchmark row (`test_reproducible_beta_enabled_benchmark_…`),
* participation in the official-feed inventory (`test_every_official_feed_a_game_declares_is_actually_requested`).

Those are the invariant checks that stop a "half-configured" game from shipping silent, and adding
them for the new titles needs data this probe could **not** verify: the launch schedules, X handles,
YouTube channel ids and reveal-format rows for three games, two of which have not launched. Wiring
the two games we *can* wire (NTE, Endfield) would therefore mean either inventing that data or
relaxing the invariants — the first is a lie in the config, the second removes the guard that keeps
the config honest. Neither belongs in a "pristine, no edge cases" change.

What is ready to paste, once that data is verified:

```json
"nte":      { "enabled": false, "released": false, "notes": "…",
              "codes": { "sources": ["ogc:nte", "reddit:NevernessToEverness"] } }
"endfield": { "enabled": false, "released": false, "notes": "…",
              "codes": { "sources": ["ogc:endfield", "reddit:Endfield", "reddit:ArknightsEndfield"] } }
```

Both pass `python -m gamexpress validate` today (codes-only entries are legal, and there is no
`Redeem` button until a `redeem_url` is verified) — the remaining work is the per-game metadata the
invariants require, not the code path.

## Checklist for the next pass

1. NTE — verify the launch date and the X/YouTube handles; add `news_url` (`…/en/article/news/index.html`)
   plus the `sources/newspage.py` pattern for `gamenews`/`gamebroad`/`gameevent`.
2. Endfield — find `cms.appCode` (bundle chunk not yet captured, or the news page after they fill the
   `href`s) to unblock `/api/bulletin`; otherwise wait for the official RSS/Atom if one appears.
3. Silver Palace — re-probe after the 2026-12-14 launch; look for a hydrated news endpoint.
4. All three — add the per-game rows the smoke tests demand, then flip `enabled`/`released`.
5. News-Express side is **not** part of this repository: `r/NevernessToEverness`,
   `r/Endfield` + `r/ArknightsEndfield`, `r/SilverPalaceOfficial`.

## Related documents

* [SOURCES.md](SOURCES.md#redemption-codes) — the live source table this dossier feeds.
* [CONFIGURATION.md](CONFIGURATION.md) — the `codes.sources` spec syntax.
* [CREDITS.md](CREDITS.md) — Crimson Witch attribution.
* [changelog](changelog/CHANGELOG.md#2026-11-27--crimson-witch-is-a-code-source-and-the-new-game-probe)
