<div align="center">

# 🎮 Game-Express

**Version-schedule announcements and redemption codes for six gacha games, plus optional
official news and pre-load/maintenance alerts — posted to Discord as Components V2 cards,
with no server or bot token.**

[![CI](https://github.com/uesu/Game-Express/actions/workflows/ci.yml/badge.svg)](https://github.com/uesu/Game-Express/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.14.10-3776AB?logo=python&logoColor=white&labelColor=2b2d31)](docs/PYTHON_VERSION.md)
[![Tests](https://img.shields.io/badge/tests-offline%20%C2%B7%20no%20secrets-3FB950?labelColor=2b2d31)](docs/TESTING.md)
[![Discord](https://img.shields.io/badge/posts%20to-Discord-5865F2?logo=discord&logoColor=white&labelColor=2b2d31)](https://discord.com/developers/docs/components/reference)

[Setup](#-setup) · [Configuration](docs/CONFIGURATION.md) · [Docs](docs/) ·
[Changelog](docs/changelog/CHANGELOG.md) · [Troubleshooting](docs/TROUBLESHOOTING.md)

</div>

---

Game-Express watches the official channels of **Genshin Impact**, **Honkai: Star Rail**,
**Zenless Zone Zero**, **Wuthering Waves**, **Honkai: Nexus Anima** and **ANANTA**. When a
Special Program is announced or a new redemption code appears, it posts one card — and then
keeps that card correct by editing it silently as official information arrives. Independent,
off-by-default features can also post full official news articles for five supported games
(with optional Discord `<t:…>` timestamps and expanded multi-page rendering) and live
**Pre-Load Started** / **Maintenance Started** / **Servers Live** alerts per game.

It runs entirely on **GitHub Actions** (free and unlimited on public repos), triggered every
5 minutes by **[cron-job.org](https://cron-job.org)**. There is nothing to deploy: merging to
`main` **is** the deploy.

> Same architecture and lessons as **[News-Express](https://github.com/uesu/News-Express)**:
> fallback chains for every source, dedup state committed to the repo, a queued (never
> cancelled) workflow, offline golden tests as the CI gate, and a two-instance fail-over.

## ✨ Highlights

- **Never posts on a timer.** A card exists because an *official* post matched a pattern.
- **Posted once, then corrected silently.** No second ping, no duplicate, no stale card.
- **Honest about what it doesn't know.** Unknowns are `TBA`; estimates are labelled as estimates
  and are replaced the moment an official value lands.
- **A code must earn its place** — official, redeem-validated, or two independent sources that
  all agree it is still live.
- **No single point of failure.** Every data point has a fallback chain, and a second instance
  can take over automatically.
- **No server, no bot token, no container.** Webhooks and a scheduled workflow, nothing else.

## 📖 Contents

- [What it posts](#-what-it-posts)
- [Supported games](#-supported-games)
- [Setup](#-setup)
- [Configuration](#-configuration)
- [How it decides to post](#-how-it-decides-to-post)
- [Running it](#-running-it)
- [Reliability](#-reliability)
- [Testing & CI](#-testing--ci)
- [Documentation](#-documentation)
- [Changelog](#-changelog)
- [Legal & credits](#-legal--credits)

> **Working on the code (human or AI)?** Start with **[AGENTS.md](AGENTS.md)** — the maintainer's
> mental model: invariants that must not be "fixed", the exact verification commands, and the
> traps that have already broken a run.

---

## 🃏 What it posts

### 1 · Version schedule card

One card per game + version. **Only an official *Special Program* / *Special Broadcast* /
livestream announcement can open one** — maintenance, pre-install and banner notices fill in the
card that announcement opened, silently, and never create one of their own. A programme that has
already aired is recorded and kept current, but never carded: versions released before this bot
existed stay out of the channel.

```
┌───────────────────────────────────────────────────────────── (accent 14922399)
│ ## Honkai: Star Rail Version 4.6 Special Program               ← title, links to the video/post
│ <t:1789903800:F> or <t:1789903800:R>                           ← Discord timestamps
│ ※ In the event that the maintenance is extended, …
│ ─────────────
│ **Version 4.6 Banners (STC)**
│ ✦ First Half/Phase: Pearl         - 4 Star Characters: TBA
│ ✦ Second Half/Phase: TBA          - 4 Star Characters: TBA
│ ─────────────
│ **Maintenance Details (STC)**
│ ✦ Pre-Install: <t:…:F>   ✦ Start: <t:…:F>   ✦ End: <t:…:F>   ✦ Compensation: Stellar Jade ×300
│ [ announcement image ]
│ ─────────────
│ [ Youtube ] [ Twitch ] [ HoYoLAB ]                             ← buttons INSIDE the card
│ -# STC — Subject to Change • TBA — To be Announced <@&ROLE>    ← ping (only if a role is set)
└─────────────────────────────────────────────────────────────
```

- **Each game keeps its own format.** Wuthering Waves uses `"Special Broadcast"` in the title,
  shows maintenance before banners and adds the `※ 4 Star Characters:` summary line; a banner
  outside the phases (WuWa's Reverb Convene, Genshin's Chronicled Wish) gets its own
  `※ Starpath Reverbs II: Camellya, Roccia, Phoebe, Brant` line above them; Genshin's
  banner heading links to lunaris.moe; HSR's heading reads `Maintenance Details (STC)`. All four
  reference cards were converted 1:1 and are pinned by golden tests.
- **The card stays accurate after posting.** When the maintenance notice arrives, pre-install
  goes live in the launcher, an official banner notice lands, or you edit
  `config/overrides.json`, the **same message is edited silently** — no second ping, no
  duplicate.
- **Gaps are filled, and labelled.** Until the official notice exists, three fallbacks keep the
  card useful — each one marked on the card and replaced automatically:

  | Gap | Filled from | Off switch |
  |---|---|---|
  | maintenance start / end | community countdown sites | `COUNTDOWN_ESTIMATES=0` |
  | pre-install | that game's **median observed lead** in hours, learned from real notices | — |
  | the announcement's own link + key art | the X post first, then the paged-back HoYoLAB list, then the official news page, then the news-feed mirror, then official Reddit | `PROGRAM_MEDIA=0` |

  Details: **[docs/ACCURACY.md → Filling the gaps](docs/ACCURACY.md#filling-the-gaps-before-the-official-notice)**.
  Once the card is posted, its link, key art and air time are locked to the announcement that opened
  it. When X and HoYoLAB both carry the announcement, the lock goes to the X post, and a card that was
  locked to HoYoLAB while X could not be read moves once to the X post. Banners settle once confirmed (an official
  notice, or any two reputable sources agreeing (the community hub, the official calendar, the wiki)), and the maintenance details keep updating
  ([ACCURACY.md → Once posted](docs/ACCURACY.md#once-posted-the-card-keeps-its-announcement)).

### 2 · Redemption code card

One card per batch of new codes, in **that game's own codes channel**. New codes found in the
same run share a card.

```
┌───────────────────────────────────────────────────────────── (game color)
│ ## <a:starwarddonut> Genshin Impact Redemption Codes      [card artwork]
│ -# 2 new codes • detected <t:…:R> <@&ROLE>                ← ping (optional)
│ ─────────────
│ ✦ VESNAONPATROL                   [ <a:starwardthink> Redeem ]  ← the code's own button, on its row
│ -# Primogem ×40 • Mora ×20000 • Hero's Wit ×3
│ ✦ EPIC2026                        [ <a:starwardthink> Redeem ]
│ -# 40 primogems, five hero's wit, and 20k mora
│ ─────────────
│ ※ Tap a code to open the official redemption page with it filled in (log in first)
│ -# Source: PromoGacha, hoyo-codes.seria.moe (verified) • Codes expire — redeem soon
│ ─────────────
│ **Citlali News**                  [ <a:starward11> Citlali News ]   ← footer (COMMUNITY_BUTTONS)
│ -# Delivering news and official updates
└─────────────────────────────────────────────────────────────
```

- **GI / HSR / ZZZ**: each `Redeem` button opens the official page with *that* code prefilled — the
  button sits on the code's own row, not in a row of buttons underneath. **Wuthering Waves** has no
  web redemption, so its codes are plain lines and the card shows the in-game path instead
  (*Settings → Other Settings → Account → Redemption Code*, Union Level 2+).
- **Codes are never wrapped in backticks** — `✦ NS4DU8AAGXBP` is a code you can select and copy, not
  a code block, and the hint plus the source share one quiet block under the list.
- **Card artwork**: the game's own icon by default; set `CODES_THUMBNAIL` (or `codes.thumbnail` for
  one game in [`config/games.json`](config/games.json)) to use your own image or GIF instead.
  The headline emoji and the Redeem-button emoji are `EMOJI_REDEEM` / `EMOJI_REDEEM_BUTTON`
  (defaults: `<a:starwarddonut:1483083005361913959>` and `<a:starwardthink:1573969377038958644>`).
- **Expired codes are struck through automatically.** When every source that still lists a posted
  code says it expired, the same message is edited silently: `~~CODE~~ · expired`, and its button
  is removed. No second ping. `CODES_MARK_EXPIRED=off` disables it.
- At most **10 codes per card**; a bigger drop continues on a second card (`part 2/2`) and only
  part 1 pings.
- Codes only post after passing the [accuracy gate](#-how-it-decides-to-post).

> Want to see every card before touching Discord? `python -m gamexpress preview` →
> open `previews/index.html`.

---

### 3 · Official news

Full retrievable official articles for **Genshin Impact, Honkai: Star Rail, Honkai:
Nexus Anima, Zenless Zone Zero and Wuthering Waves**, sent to explicitly configured
news webhooks. Conservative stop-and-hold recovery is explicitly enabled for official
news and maintenance alerts. Existing schedule/code retry behavior remains at the
pre-PR baseline (`stop_on_ambiguous=False` by default); ANANTA news is inactive and
Wangyue is excluded.

Optional `NEWS_REVEAL_PING=1` with one `PING_NEWS_REVEAL` role adds heuristic
static-character reveal mentions to the byline, with retained-character and
publication-minute deduplication. Wuthering Waves is excluded (`reveal_ping: false` in
`config/games.json`): its own site repeats the reveal the twitter/X pipeline already
delivers as a card, and that pipeline has no reveal ping yet, so Feature 3 posts that news
silently while the hoyoverse games keep the ping.
It is off by default; see
[configuration and limitations](docs/CONFIGURATION.md#official-news-on-by-default).

- **Source-order content & independent policies:** one full message when it fits;
  by default (`NEWS_EXPAND_FULL=0`), the **7,000-character / maximum-two-page
  per-article policy** remains intact (1 message when fitting → up to 2 validated
  pages within 7,000 normalized chars → 1 labelled excerpt message with at most one
  lead image and Read Post for the full source). Removing the retired per-run
  article-count cap (`NEWS_MAX_POSTS_PER_RUN`) only allows processing all newly
  published articles per poll and does **not** remove the default-off 7,000 / 2-page
  per-article policy. Setting `NEWS_EXPAND_FULL=1` lifts that per-article ceiling
  up to an explicit `12`-page / `120,000`-char / `120`-media safety bound (increasing media validation
  `GET`s, message count, webhook `POST`s, and pacing proportionally).
- **Independent feature eligibility:** schedule extraction/mirrors, codes, official
  news, and started alerts are independent — Special Program, broadcast, preload, and
  maintenance notices remain eligible for official news delivery whenever news is on,
  while legacy `status: "posted"` state entries remain deduplicated without backfill.
- **On by default, still a switch:** news runs without any configuration. Set
  `NEWS_ENABLED=0` to turn it off completely (`ENABLED_FEATURES=none` still pauses
  everything); `NEWS_GAMES` narrows the games as before.
- **Optional native timestamps (`NEWS_TIMESTAMPS=1`, off by default):** converts
  exact timezone-qualified dates/times in rendered news bodies (plus `server time`
  on `UTC+8`) into Discord `<t:EPOCH:…>` tags without touching source payloads,
  URLs, inline/fenced code, date-only phrases or schedule extraction.
- **Source-preserving formatting:** preserves Quill/HTML spacing, blank lines, and
  multi-op headings/bullet lists, coalesces adjacent emphasis spans without stray
  `****` markers, emits self-labelled or visible-URL links as clean bare URLs instead
  of Discord-blocked `[**https://…**](https://…)` masked links, unwraps double-bolded
  heading links (`**[label](url)**`), and escapes literal `*` footnotes/multipliers
  without altering upstream HTML, JSON, API calls, or source adapters.
- **Controls at the end:** all three custom-emoji buttons occur only in the final
  container of the final message, followed by one small line under them —
  *"It takes time, tools, hosting and ongoing maintenance to keep the news working…"* —
  which is part of the card, never split across messages, and never counted as article text.
  Part labels identify containers; Page labels identify separate messages.
- **Optional measured long strips:** default article-order galleries remain
  unchanged. Opt-in grouping combines only qualifying consecutive strips; failed
  measurements keep the original layout. No cropping, slicing or media removal.
- **Explicit opt-in, no backfill:** enabling silently establishes a baseline;
  it does not repost old articles. Missing media can hold delivery after one
  official refresh. This is not a live Discord playback guarantee.

Use the **[official-news setup and full instructions](docs/CONFIGURATION.md#official-news-on-by-default)**
for all variables, per-game secrets, selecting two games, paging/excerpt rules,
optional timestamp conversion, expanded articles, measured grouping, retries and safe verification. See also the
**[source limits](docs/SOURCES.md#optional-full-content-news-adapter-2026-10-18)**
and **[offline/live-check distinction](docs/TESTING.md#official-news-offline-coverage-and-read-only-checks)**.

---

### 4 · Pre-load, maintenance started & servers live

Three independent milestone alerts per version — **`Pre-Load Started`**,
**`Maintenance Started`** and **`Servers Live`** — for explicitly enabled games, using the
existing 5-minute scheduler and dedicated per-game webhooks (`DISCORD_WEBHOOK_MAINTENANCE_<GAME>`).
Works standalone or alongside schedule, codes and news without modifying existing cards.

```
┌─────────────────────────────────────────────────────────────
│ ## [ZZZ - 3.3] Pre-Load Started <a:starwardlove:…><a:starwardspark3:…>
│ <@&ROLE>                                                       ← optional per-game ping
│ ─────────────
│ ※ **Date Time:** <t:1792382400:f> ※ **Hour Time:** <t:1792382400:R> <a:gearfinal:…>
│ [ version-verified launch video / artwork (optional) ]
│ <a:starwardsleepywink:…> **Citlali News**          [ <a:starwardyayy:…> ]
│ -# Delivering news and official updates
└─────────────────────────────────────────────────────────────
```

- **Separate milestones & silent baseline:** enabling seeds already-passed
  milestones silently and tracks `preload` and `maintenance` separately in
  `state/state.json`, so first activation never reposts settled versions and
  `Pre-Load Started` never suppresses `Maintenance Started` (which renders
  `※ **Date Time:** <t:START:f> ※ **End Time:** <t:END:t>` when `end_ts` is known,
  or omits `End Time` cleanly when unknown).
- **Servers Live (third card):** always silent (no role mention or notification), and never
  clock-derived. It posts when the publisher says the servers are back — the completion notice / tweet
  (`Version X.Y update maintenance has been completed`, `Update Completion Notice`,
  `… can now log in`) — or, for HoYoPlay games, when the
  client's own maintenance gate (`getGlobalApplicationMaintenance`, the endpoint
  [hoyo-update-notifier](https://github.com/seriaati/hoyo-update-notifier) runs in production)
  flips from *in maintenance* to *open* after it was seen set for that version. Both are accepted
  only between `maintenance start + 20 min` and `+ 24 h`, only for a `Maintenance Started` card
  this install posted itself, and once per version. The card reuses the version's locked launch
  media and `Hour Time` (`<t:…:R>`); a gate-detected card carries a one-line note until the
  official notice upgrades it silently. The same moment rewrites the `Maintenance Started`
  card's `End Time` to the actual reopening (silent `PATCH`, timing-correction budget).
- **Source precedence:** official notices/tweets → explicit `config/overrides.json` →
  persisted first-observed launcher pre-download signal (explicitly marked observed,
  never moving `now`) → documented cadence predictions (clearly marked estimated; no
  invented HNA cadence or fabricated end time when unknown).
- **Version-verified launch media:** prefers (1) matching-version launch video,
  (2) matching-version launch artwork/WebP, (3) matching-version official X/Twitter
  or HoYoLAB program artwork, or (4) cleanly omits media — locking launch identity
  against Phase II swaps while allowing bounded silent `PATCH` upgrades
  (`tier 2/3/4 → tier 1`), corroborated same-asset signed URL renewal (`auth_key=`
  query intact), or fallback to matching-version artwork / omitted media inside
  `LATE_MEDIA_EDIT_WINDOW_S`.

Full setup and safeguards: **[docs/CONFIGURATION.md → Pre-load & maintenance started](docs/CONFIGURATION.md#pre-load--maintenance-started-on-by-default-per-game-opt-in)**.

---

### 5 · Beta kit & revision-diff cards (optional; off by default)

While a version is in beta, the community databases publish a new **revision** (v2, v3, …)
every few days. This feature watches those revisions and posts one batch per new revision to
that game's own channel (`DISCORD_WEBHOOK_BETA_<GAME>` → `DISCORD_WEBHOOK_BETA` →
`DISCORD_WEBHOOK_NEWS_<GAME>` — never a schedule or codes channel).

```
┌─────────────────────────────────────────────────────────────
│ ## [ZZZ - 3.4.1 Beta] Patch Notes: Rev. 19834130 → 19851435
│ Resource: [gachabase](https://zzz.gachabase.net/changelog/beta?lang=en) / [nanoka](https://zzz.nanoka.cc/diff)
│ ─────────────
│ [ splash art ]
│ ## Robin
│ **Attribute:** Ether | **Specialty:** Defense | **Rarity:** 5-Star (S-Rank)
│ **Base Stats (Lv. 60):** HP 8,754 | ATK 750 | DEF 706 | Impact 90 | CRIT Rate 5% | CRIT DMG 50%
│ **Kit Overview:** Robin is an Ether Defense Agent whose kit revolves around [Robin Shield],
│   [Aftershock], pairing squad utility with responsive follow-up triggers.
│
│ ## Core Passive & Additional Ability
│ * **[CHANGED] Core Passive:**
│   * Grants all squad members a [Robin Shield] equal to **24%** MAX HP …
│   * **(Aftershock)**: Triggered off-field when active squad members land Heavy Attacks …
│ ─────────────
│ -# Zenless Zone Zero 3.4.1 Beta • Page 1/3           [ Citlali News ↗ ]
└─────────────────────────────────────────────────────────────
```

- **Active-beta gating.** Before fetching changelogs or item JSONs, the monitor compares each
  game's candidate beta build against its live cycle (manifest `live`/`hotfix`, version config,
  and confirmed past schedule maintenance). Finished or already-live beta builds (for example,
  `7.1.53` when `7.1` is live, or `4.6.54` when `4.6` is live) are skipped immediately with
  zero changelog/detail traffic.
- **What it posts (Prime Formatting Style).** Newly observed active betas render clean Components V2
  cards without blockquotes or continuation headers: a synthesized **Kit Overview**, structured
  metadata headers (element/attribute, path/weapon/specialty, rarity, formatted Lv. max stats and
  stat bonuses), nested `* **[TAG]**` skill/mechanic bullets with bracketed `[State]` terms and
  inline `**(Keyword)**` definitions, single-item splash/weapon media plus multi-item galleries
  (such as 6-icon HSR Eidolons and multi-piece Planar/Relic/Artifact/Drive Disc sets), and later
  revision diffs (`[BUFF]`, `[NERF]`, `[CHANGED]`, `[ADJUSTMENT]`, `[REWORK]`, `[TEXT FIX]`).
- **Revision discovery & bilingual CN/CHS cross-check.** Gachabase Markdown and server-rendered
  HTML both identify changed existing items; HTTP 403 / access-denied responses fall back cleanly
  to nanoka's active-beta manifest without warning spam. When an EN beta build lags behind CN
  (`???`, `[TBD]`, `/-` incomplete ratios, unchanged EN parameters on a new revision, or an
  upstream changelog note advising to double-check Chinese), the monitor reads `/zh/` within the
  bounded request ceiling to decide whether anything changed. When only CN changed, the card shows
  the CN text as it is, with a note. CN text is never merged into EN text.
- **A source comparison on every card.** Each changed item links its own revision diff — Encore's
  version comparison for WuWa (`/diff?firstVer=Beta_3.8.1&secondVer=Beta_3.8.3&route=character&id=1512`),
  gachabase's for Genshin, Star Rail and ZZZ — built only from the two patches the card compared.
  The link is a citation the reader can check; it costs no request and never changes the card.
- **Content-driven pages.** Beta cards can use five pages, ten or more, according to the
  readable content in each batch; there is no fixed beta page cap. Long equipment effects,
  character text, parameter rows and revision changes continue seamlessly on validated pages
  without `*(cont.)*` banners. Only page one pings. Request/item budgets still bound source work
  across resumable batches.
- **Actual inline diffs, without guessing.** When an old and new value are both present, the card
  renders the source text intact around an inline diff such as `~~200%~~ → **240%**`, while
  structurally rewritten or renamed slot skills surface as `[REWORK]` with `~~previous~~` context.
  `[BUFF]` / `[NERF]` are emitted only for unambiguous mechanics (for example, higher damage or
  lower cooldown); ambiguous, wording-only, and category moves stay `[CHANGED]` / `[TEXT FIX]` /
  `[ADJUSTMENT]`. A block that did not move is omitted outright — never listed as `No changes.`
  — and the header names the comparison itself (`Patch Notes: Rev. 3.8.1 → 3.8.3`, or
  `Rev. 19834130 → 19851435` when only the build moved). A cold start never fabricates a
  baseline. Full-content digests keep unchanged long kits quiet; when exact comparison is
  genuinely unavailable the card says so once and prints a labelled full snapshot instead.
- **Hotfix-safe and quiet-safe.** Static `available` builds are walked in order, so a run does
  not jump over a v2/v3 hotfix. If a changelog revision is blank, only already-snapshotted and
  manifest-new IDs are rechecked; an explicit “No tracked changes detected” revision advances
  silently without an empty Discord post. A cold opt-in still posts the current reveal instead
  of losing it to a quiet micro-hotfix.
- **Off by default, and bounded when it is on.** `BETA_ENABLED=1` is required.
  `BETA_MIN_POLL_MINUTES` (default `30`) and `BETA_MAX_CHARACTERS` /
  `BETA_MAX_CHANGES` / `BETA_MAX_EQUIPMENT` / `BETA_MAX_REQUESTS` bound polling, cards and
  requests. Disabled, the feature makes **zero** requests.
- **WuWa beta fallback.** If nanoka lacks a readable current-build character or weapon,
  Encore’s `?v=Beta` API can supply it after matching resource-version and stable-build checks.
  Its official legacy endpoint is a backup if the primary Encore read fails, within the same
  request budget; [source details](docs/SOURCES.md#encore-beta-api-fallback-for-wuwa).
- **HNA and ANANTA are excluded** until they ship — `BETA_GAMES` defaults to the four released
  games and `all` resolves to the same four.
- **It stops on its own.** A verified splash-art URL is locked in state and never re-fetched.
  Per-revision batches persist their own resume cursor, so a bounded batch continues without a
  duplicate page; once all batches settle, that revision generates no further traffic. After a
  successful multi-page beta card, the monitor waits **five seconds before the next page only**
  (never after the final page); a restart resumes its first unsent page immediately.
- **Offline enabled-feature harness.** `python -m gamexpress benchmark --beta-enabled` keeps the
  production default off, but runs an isolated `BETA_ENABLED=1` monitor pass for **GI, HSR, ZZZ
  and WuWa** through manifest/changelog discovery, every namespace parser, image preflight,
  Components V2 validation, multi-page delivery/pacing, retained revisions, deduplication, quiet
  revisions, and failed/ambiguous/resume delivery paths. Its collaborators are in-memory only:
  it makes **zero live** source HTTP requests, Discord posts and physical state writes while still
  proving state-save transitions. Renderer timings are a supplemental section of the report, not
  the feature test itself.

Full setup, variables and safeguards:
**[docs/CONFIGURATION.md → Beta kit & revision-diff cards](docs/CONFIGURATION.md#beta-kit--revision-diff-cards-feature-5--explicit-opt-in-default-off)**.
Sources: **[docs/SOURCES.md → Beta kit & revision-diff sources](docs/SOURCES.md#beta-kit--revision-diff-sources-2026-10-24)**.

---

## 🎮 Supported games

| Game | Status | Schedule sources | Code sources |
|---|---|---|---|
| Genshin Impact | ✅ on | HoYoLAB API (gid 2) → c3kay mirror · X `@GenshinImpact` · HoYoPlay launcher · Reddit `u/genshinimpact` backup | HoYoLAB livestream module · official posts · seria + Hum-Bao (both redeem-validated) · Open Gacha Codes · ennead · fandom · PromoGacha · `r/Genshin_Impact` witness |
| Honkai: Star Rail | ✅ on | HoYoLAB API (gid 6) → c3kay · X `@honkaistarrail` · HoYoPlay · Reddit `u/HonkaiStarRail` backup | same set (`r/HonkaiStarRail` witness) |
| Zenless Zone Zero | ✅ on | HoYoLAB API (gid 8) → c3kay · X `@ZZZ_EN` · HoYoPlay · Reddit `u/ZZZ_Official` backup | same set (`r/ZZZ_Official` witness) |
| Wuthering Waves | ✅ on | X `@Wuthering_Waves` · Kuro official site · Kuro launcher · `r/WutheringWaves` official-flair backup | official X/Reddit posts · wuthering.gg (active/expired) · Open Gacha Codes · fandom · PromoGacha · `r/WutheringWaves` witness |
| Honkai: Nexus Anima | ✅ on · ⏳ not released yet | HoYoLAB API (gid 9) · X `@HonkaiNA` · Reddit `u/HonkaiNexusAnima` backup | HoYoLAB livestream module (gid 9) · fandom · `r/HonkaiNexusAnima` witness · official X/Reddit |
| ANANTA (NetEase) | ✅ on · ⏳ releases 2027‑01‑15 | X `@Ananta_EN` · Reddit `u/AnantaOfficial` backup | fandom · `r/AnantaOfficial` witness · official X/Reddit |

**All six are monitored**, including the two that are not out yet, so a pre-release Special
Program is caught the moment it is announced. Enabling a game is never retroactive: its **first
run seeds silently**, so nothing old is posted.

- `enabled` = *do we watch it*. `released` = *is the game out*. Separate on purpose: an
  unreleased game is watched, but it has no real codes to fetch, so the test bench checks its
  card with sample data (`test-card --kind codes --unlaunched`).
- To switch a game **off**, set `"enabled": false` in `config/games.json` — or run a subset with
  the `GAMES` variable. `ENABLE_GAMES=hna,ananta` is the no-merge way to switch prepared games on
  from the repo's Variables page; ANANTA also keeps `auto_enable_on: 2027-01-15` as a safety net.
- Neither pre-release game has a Twitch channel yet, so their cards simply have no Twitch button.
  ANANTA has no character gacha, so its card hides the banner section.

---

## 🚀 Setup

Game-Express is the development home: code, docs, tests and CI stay here. A separate
production repository runs the monitor. Merging here does **not** deploy there; upload the
reviewed runtime files separately. Full manifest and cutover:
[production setup](docs/PROD-REPO-SETUP.md).

### 1 · Get the repo

Create an empty production repository; no fork or shared Git history is required. Copy the
whole `gamexpress/` package, three config JSON files, current state, requirements, monitor
workflow, `.gitignore` and policy files using the [manifest](docs/PROD-REPO-SETUP.md#1-the-file-manifest).
Public standard hosted runners avoid private-repository minute allowances; private production
needs a cadence/budget review ([scheduler guide](docs/SCHEDULER.md#minutes-and-private-repositories)).
A second *live instance* is optional; the development repository is not a standby by default.

### 2 · Create the Discord webhooks

*Channel → Edit Channel → Integrations → Webhooks → New Webhook → Copy Webhook URL.*
One for the schedule channel and one per enabled game codes channel. Optional schedule mirrors
copy schedule cards to game channels; optional official news uses separate dedicated per-game
webhooks. They are independent features, even if you choose the same destination channel.

### 3 · Add the secrets

*Settings → Secrets and variables → Actions → Secrets → New repository secret.*

| Secret | Channel |
|---|---|
| `DISCORD_WEBHOOK_SCHEDULE` | version-schedule announcements (all games) |
| `DISCORD_WEBHOOK_CODES_GENSHIN` | Genshin Impact codes |
| `DISCORD_WEBHOOK_CODES_STARRAIL` | Honkai: Star Rail codes |
| `DISCORD_WEBHOOK_CODES_HNA` | Honkai: Nexus Anima codes |
| `DISCORD_WEBHOOK_CODES_ZZZ` | Zenless Zone Zero codes |
| `DISCORD_WEBHOOK_CODES_WUWA` | Wuthering Waves codes |
| `DISCORD_WEBHOOK_CODES_ANANTA` | ANANTA codes |
| `NITTER_RSS_TOKEN` | *optional* — the same token as News-Express; unlocks **both** `nitter.miningtcup.me` (X) and `redlib.miningtcup.me` (Reddit/Redlib) |
| `REDDIT_FEED_TOKEN` | *optional* — from `old.reddit.com/prefs/feeds/`: paste `<40-char-key>&user=<your_username>` or any full `.rss?feed=…` / `.json?feed=…` link on `old.reddit.com`, `www.reddit.com`, or `reddit.com` (same as News-Express; drives `[0] www.reddit.com` → `[1] old.reddit.com` fast path + `.json` fallback) |
| `DISCORD_BOT_TOKEN` | *optional, Reddit intake reader (2026-11-02)* — token of a Discord bot that is in your server with **View Channels** + **Read Message History** on the intake channel and the **Message Content Intent** enabled; read-only (REST `GET /channels/<id>/messages`), nothing is ever written through it. Same secret name as News-Express, so one bot serves both repos. With Variable `INTAKE_CHANNEL_ID` it makes the Devvit relay the primary Reddit listing; unset = the redlib/reddit.com chain exactly as before |
| `INTAKE_QUIET_TARGETS` | *optional, Variable (2026-11-20)* — `1` lets a healthy relay answer "no new post" for a target it has no record of, **once it has already listed another target of the same kind** for this deployment (a subreddit for `r/…`, an account for `u/…`); the redlib/reddit.com fleet is then not contacted for that target and the summary shows `quiet (no new post) r/…`. Off by default — enable it only when the relay polls every subreddit and publisher account you track. See [SOURCES.md §Reddit intake](docs/SOURCES.md) |
| `BUMP_PAT` | *required only where the Python bump workflow is installed* — a repository-scoped PAT with **Contents, Pull requests and Workflows: read and write**, subject to token type and repository policy. See [docs/PYTHON_VERSION.md](docs/PYTHON_VERSION.md#publication-credentials) |

Create only destinations you intend to use; ANANTA is not a verified official-news adapter.
Optional schedule mirror secrets are `DISCORD_WEBHOOK_SCHEDULE_MIRROR_<GAME>`.
For news, use dedicated secrets `DISCORD_WEBHOOK_NEWS_GENSHIN`,
`DISCORD_WEBHOOK_NEWS_STARRAIL`, `DISCORD_WEBHOOK_NEWS_HNA`,
`DISCORD_WEBHOOK_NEWS_ZZZ`, and `DISCORD_WEBHOOK_NEWS_WUWA`.
For pre-load/maintenance started cards, use dedicated secrets
`DISCORD_WEBHOOK_MAINTENANCE_<GAME>`. Neither feature uses the generic webhook,
`FORCE_WEBHOOK` or mirror fallback.
See [the full secret reference](docs/CONFIGURATION.md).

The same URL may be used for several secrets, for example one codes channel for every game.

### 4 · Add the variables

*… → Variables.* `PING_ROLE_ID` = your role ID — **leave it unset for no ping**, or set
`NO_PING=1`. The Youtube and Twitch emojis already default to the animated ones.
Leave `ENABLED_FEATURES` unset for the usual `schedule,codes` production defaults.
Reddit backup (`REDDIT_ENABLED=1` by default) backs up `schedule` automatically when X or
primary APIs degrade and adds an unverified 2nd-witness family (`reddit:<Subreddit>`) for
`codes`; set `REDDIT_ENABLED=0` to turn all Reddit fetching off with zero HTTP calls.
Official news is on by default (`NEWS_ENABLED=0` turns it off); `NEWS_GAMES` selects games,
`NEWS_TIMESTAMPS=0` / `NEWS_EXPAND_FULL=0` / `NEWS_GROUP_LONG_STRIPS=0` keep default
rendering unless switched to `1`. Each run attempts all discovered,
eligible unposted articles in publication order, with no fixed article-count cap. For only GI and WuWa news, use `NEWS_GAMES=genshin,wuwa`
and their two dedicated secrets; this does not restrict schedule/codes.
Pre-load/maintenance started cards are on by default (`MAINTENANCE_ENABLED=0` turns them
off) and activate per game as soon as `MAINTENANCE_GAMES` names the target keys alongside
dedicated `DISCORD_WEBHOOK_MAINTENANCE_<GAME>` secrets.
Canonical news keys: `genshin`, `starrail`, `hna`, `zzz`, `wuwa`.
See [full setup and switches](docs/CONFIGURATION.md#official-news-on-by-default).

Development safeguard: optional `ENABLED_FEATURES=none` skips live workflow runs; test mode
still posts to configured webhooks. Omit production webhooks from a strict development-only copy.
`AUTO_MERGE_PYTHON_BUMP` is legacy/ignored; remove it if present. Keep `BUMP_PAT` if using
the Python update workflow. Eligible package-only Dependabot auto-merge remains separately
opt-in with `AUTO_MERGE_DEPENDABOT=yes`; workflow-path updates require attended review.
Everything else: **[docs/CONFIGURATION.md](docs/CONFIGURATION.md)**.

### 5 · Test it

*Actions → **Game-Express Monitor** → Run workflow → `mode` = **test***, then `webhooks` →
`codes` → `schedule`. Each one posts **real** data labelled 🧪 TEST as new messages — it never
edits a live card, never writes the state, and pings nobody by default. These checks do not
post official-news samples or independently verify schedule mirrors/news destinations.
Use the offline news checks in the testing guide; do not reset state to force a test. Walkthrough:
**[docs/TESTING.md](docs/TESTING.md)**.

### 6 · Go live with cron-job.org

Create one cron-job.org job per instance repo that calls the `workflow_dispatch` API every
5 minutes, using a GitHub **classic token** with the `repo` scope. Step by step:
**[docs/SCHEDULER.md](docs/SCHEDULER.md)**. GitHub's own `schedule:` is disabled in
`monitor.yml`; do not enable both schedulers. For a move: pause the old cron job, let its
in-flight run finish and push state, copy the freshest `state/state.json` and
`config/program_announcements.json`, then replace the dispatch URL's repository name.
Ensure the dispatch token has access to the new repository and resume only the new target.
See [cutover order](docs/PROD-REPO-SETUP.md#6-cutover-order-no-double-post-no-missed-announcement).

### Then what?

**New empty state: first real run = silent seed.** A migrated installation must retain its
fresh production state and announcement cache; it continues those records instead of starting
from scratch. Copying state reduces duplicate risk but cannot coordinate two running repos.
With empty state, current announcements and every existing code are recorded
without posting, so deploying never spams old items. The summary lists what was seeded
(`🌱 HSR 4.6: seeded silently`, `🌱 GI: seeded 34 existing codes`). To post what's current on the
very first run instead, set `BOOTSTRAP_POST=1` before that run (schedule/codes only). Official news always establishes
its own silent discovery baseline; bootstrap does not backfill news.

**Already seeded and want a current card now?** Run the Monitor with `repost = starrail:4.6` (any
version shown in a summary). The card is posted as a new message and then kept up to date like
any other. `repost` is the only way to card a version whose programme has already aired, and it
is deliberate: the automatic path never does this. If the announcement scrolled out of the feeds,
its tweet is replayed from `config/program_announcements.json`, so the air time, the key art and
the announcement link come back anyway; a version that was never cached can still be pinned in
`config/overrides.json` (`"program_ts": "2026-09-20T19:30:00+08:00"`).

---

## 🔧 Configuration

**➡️ Full reference: [docs/CONFIGURATION.md](docs/CONFIGURATION.md)** — every secret, variable,
`games.json` field and `overrides.json` key.

The workflow passes **every** secret and variable to the app, so any of them works without
editing YAML. The ones worth knowing:

| Variable | Default | What it does |
|---|---|---|
| `PING_ROLE_ID` | *(unset)* | role(s) to ping. Unset = no ping |
| `ENABLED_FEATURES` | `schedule,codes` | schedule/code selection; `none` disables all live features, including news and maintenance |
| `NEWS_ENABLED` | `1` | on by default; `0` turns news off (unless globally disabled) |
| `NEWS_GAMES` | `genshin,starrail,zzz,wuwa,hna` | news subset, independent of schedule/codes |
| `NEWS_GROUP_LONG_STRIPS` | `0` | optional measured grouping; off retains article order |
| `NEWS_TIMESTAMPS` | `0` | optional `<t:EPOCH:…>` conversion in rendered news text |
| `NEWS_EXPAND_FULL` | `0` | optional multi-page full articles (up to 12 pages / 120,000 chars / 120 media) |
| `NEWS_MEDIA_HEAL` / `NEWS_MEDIA_HEAL_DELAY` | `1` / `6` | after delivery, re-read a card whose create response left a tile unresolved and re-send it identically once if it is still cold (Discord's "Image not found"); `0` disables |
| `PING_SCHEDULE` / `PING_CODES` | inherit `PING_ROLE_ID` | per-feature ping override; `none` = explicitly no ping |
| `PING_MAINTENANCE` / `PING_BETA` | *(unset = silent)* | optional role ping on Pre-Load Started / Maintenance Started and beta cards; Servers Live is always silent; `PING_ROLE_ID` is deliberately **not** inherited |
| `NEWS_REVEAL_PING` + `PING_NEWS_REVEAL` | `0` / *(unset)* | opt-in character-reveal ping; one role list for every game that takes it, no per-game variable (Wuthering Waves is excluded in `config/games.json`) |
| `MAINTENANCE_ENABLED` | `1` | on by default; `0` turns `Pre-Load Started` / `Maintenance Started` / `Servers Live` off |
| `MAINTENANCE_GAMES` | *(empty)* | explicit per-game list (`all` or game keys) required to activate maintenance alerts |
| `BETA_ENABLED` | `0` | explicit opt-in for beta kit / revision-diff cards (feature 5) |
| `BETA_GAMES` | `genshin,starrail,zzz,wuwa` | beta subset; `all` resolves to the same four (HNA and ANANTA excluded until launch) |
| `BETA_MIN_POLL_MINUTES` | `30` | minimum interval between beta changelog re-checks |
| `BETA_MAX_REQUESTS` | `48` | hard HTTP ceiling for the whole beta feature per run |
| `GAMES` / `ENABLE_GAMES` | all enabled / — | run a subset · switch prepared games on |
| `LOOKBACK_HOURS` | 72 | how far back official posts are considered |
| `CODES_MIN_SOURCES` | 2 | independent sources needed for an unverified code |
| `EDIT_ON_UPDATE` | on | silent in-place edits when official info arrives |
| `DRY_RUN` | off | build and log only, post nothing |

Webhook routing, most specific first:
`DISCORD_WEBHOOK_<FEATURE>_<GAME>` → `DISCORD_WEBHOOK_<FEATURE>` → `DISCORD_WEBHOOK_URL`.
This fallback chain is for schedule/codes only; news and maintenance require their own dedicated
per-game secrets. Beta cards have one extra step —
`DISCORD_WEBHOOK_BETA_<GAME>` → `DISCORD_WEBHOOK_BETA` → that game's `DISCORD_WEBHOOK_NEWS_<GAME>` —
so beta posts into the news channel until you give it one of its own; moving it later is picked up
automatically by the next card. `python -m gamexpress validate` prints resolved routing. Repository
variables and secrets are merged from workflow JSON blobs; no per-variable YAML wiring is needed.

---

## 🎯 How it decides to post

**➡️ Full rules: [docs/ACCURACY.md](docs/ACCURACY.md).** The short version:

1. **Detect** — official posts from HoYoLAB, official X accounts, the Kuro site, and the official
   Reddit backup (`REDDIT_ENABLED=1`), filtered by per-game patterns. Recaps, replays,
   "has ended" and merch are ignored.
2. **Extract from official text only** — schedule clocks need an explicit offset (`UTC+8`; `(server time)`
   is never rendered as a clock timestamp, only used to match an unnumbered banner's active version/phase),
   versions come from `Version 4.6` / `Ver.4.6` / `V4.6` (plus epithet notices like `"Luna II"`,
   unnumbered `"1.0"` pre-release launch notices, and active-phase Convene / Wish posts), and banners only
   from names following "5-star character" / "S-Rank Agent" / "5-star Resonator" — bare after the tier
   phrase, or bare after a closing quote in the epithet shape, uniting co-running sibling 5★ banners
   that share the same boosted 4★ lineup and never publishing a quoted *channel* title after the game's
   gacha-mode phrase (`Signal Search`, `Event Wish`, `Convene`, …).
3. **Merge with provenance** — *overrides > official notice > official tweet > official Reddit >
   launcher signal > countdown estimate > learned pre-install / cadence fallback > official
   calendar > game wiki > banner feed*.
4. **Unknown is `TBA`**, banners always carry `(STC)`, and no estimate can overwrite an official
   value.
5. **Only an announcement opens a card.** A *Special Program* / *Special Broadcast* creates it;
   maintenance, pre-install and banner notices only fill it in. A programme that already aired is
   tracked, never posted — so a version that shipped before the bot was deployed cannot surface
   as new. `repost` remains the deliberate override.
6. **Post once, then edit silently.** If the stored message id no longer resolves
   (`404 Unknown Message`) the card is re-created once and the new id adopted — but never for a
   version whose programme is already over. Every other edit failure stays an error and never
   reposts.

**The code gate.** A code posts when **any one** of these is true: it comes from an **official**
source (HoYoLAB livestream module or official X / HoYoLAB / Reddit post); a **redeem-validator**
(seria or Hum-Bao, which try every code on a real account) says it works and none says it
expired; or **≥ `CODES_MIN_SOURCES` independent** community families (e.g. `ennead`/`ogc`,
`fandom`, `wuthering.gg`, `reddit`) list it as active and **none** lists it as expired (preserving
cached rewards and prior pending witnesses across transient single-poll upstream outages). An
explicit *valid until* date that has passed beats every source that still lists the code. Anything
else waits as *pending* for up to 14 days, with the current reason in the job summary.

---

## 🕹 Running it

**Actions → Game-Express Monitor → Run workflow.** One input decides everything: **`mode`**.

| `mode` | What it is |
|---|---|
| `live` *(default)* | **the real monitor.** cron-job.org triggers exactly this — it sends no inputs at all. Fetches the official sources, posts a card when something new matches, edits it silently when official info arrives, and commits the state. Nothing new → it posts nothing |
| `test` | **check it with real data.** Every test fetches the live sources and posts what they really returned, labelled 🧪 TEST — so a wrong link, picture or timestamp is visible *before* a real announcement goes out |

<details>
<summary><b><code>mode = live</code> inputs</b></summary>

| Input | Effect |
|---|---|
| `only` | everything / only `schedule` announcements / only `codes` |
| `game` | one game key |
| `repost` | post a version card again as a **new** message, e.g. `starrail:4.6`. Only versions the monitor has already seen in an official post work, so an unannounced `genshin:7.2` can't be reposted yet — the summary says so and lists the tracked versions |

Nothing is ever posted twice: each card is remembered in `state/state.json` by its key **and** by
a hash of its payload, so a re-run can neither re-post nor rewrite an unchanged card. Code sources
are fetched once per run and shared between games, and the fetcher caps concurrent requests, so a
run costs a handful of HTTP calls.

</details>

<details>
<summary><b><code>mode = test</code> inputs</b></summary>

| `test` | What you get — all real, all labelled 🧪 TEST, state never saved |
|---|---|
| `webhooks` | one small green "✅ connected" card per webhook, listing which game/feature cards that channel receives. Checks all 6 per-game codes secrets |
| `codes` | the **real codes on the live sources right now**, posted to each game's own codes channel. Games that are not out yet (HNA, ANANTA) have no real code to fetch, so they get example codes |
| `schedule` | the **real schedule card** for the version that is out now: the announcement's own link and key art, the livestream date/time, the maintenance timestamps and the banners — exactly what a live run would post |
| `all` | webhooks → codes → schedule |

`game` narrows any of them to one game; `ping` (off by default) adds your role ping **to the test
cards only**. A live run pings according to `PING_SCHEDULE` / `PING_ROLE_ID` whatever this switch
says.

> A test posts to the **real** channels and never writes the state — so the live run still posts
> the real thing later. Every test card is a **new** message: a test run never edits a live card
> or its copy, so it can neither rewrite nor re-label what is already in the channel. Delete the
> test cards when you are done with them.

</details>

### CLI

For local runs and debugging: `python -m gamexpress <command>`

| Command | What it does |
|---|---|
| `run` | one pass (what GitHub Actions uses) |
| `validate` | prints the resolved routing, pings and emojis, and checks every sample card against Discord's limits |
| `preview` | writes `previews/index.html` (a Discord-like preview of every card) + the JSON for [Discohook](https://discohook.app) |
| `check-webhooks [--kind …] [--game …]` | one "connected" card per unique webhook (no ping) |
| `test-card [--kind …] [--game …] [--ping] [--unlaunched]` | post the sample cards, labelled 🧪 TEST. `--unlaunched` keeps only the games with `"released": false` |
| `speculate [--game …] [--verbose] [--now <unix>]` | read-only: what the bot would predict for each game's next version, the confidence, and the real dates it is anchored on |
| `benchmark [--iterations N] [--json] [--beta-enabled]` | offline microbenchmark for timestamp formatting/scanning and short vs multi-page news rendering; `--beta-enabled` additionally runs an isolated full enabled-beta pipeline harness for GI, HSR, ZZZ and WuWa (fixture collaborators only: no live network/webhook/disk write) and then reports supplemental beta renderer timings |

Flags: `--dry-run --only --game --repost --kind --ping --out --unlaunched --verbose --now --beta-enabled`.

---

## 🛡 Reliability

**Layer 1 — every data point has a fallback chain, inside every run.**

| Data | Chain |
|---|---|
| HoYoverse news | official HoYoLAB API → c3kay JSON-Feed mirror |
| X timelines | the built-in nitter fleet (28 entries, 27 live — `xcancel.com` is suspended and kept last as a dead entry; `NITTER_INSTANCES` overrides the list). The first **two** working mirrors are merged, so a stale-but-200 mirror can't hide a tweet |
| Tweet details | nitter.cf → xitter.cf → teapawt.org → teapaw.org → teapawt.net → xitter.gq → nitter.gq by id (when the account is known) → FxTwitter → fixupx → vxTwitter → the nitter text. A status mirror that fails twice in one run is skipped for the rest of it |
| Reddit backup & code witness | built-in Reddit/Redlib fleet (27 entries across Tier-1 dual-path mirrors + Tier-2 listing-only mirrors + Tier-3 token/legacy tail, plus 3 proxies `vxreddit.com` → `embedez.com` → `embeddit.deltandy.me` and `arctic-shift.photon-reddit.com` archive; optional `REDDIT_FEED_TOKEN` drives `[0] www.reddit.com` → `[1] old.reddit.com` 1-request RSS fast path + `.json` fallback; `REDDIT_ENABLED=0` disables all Reddit HTTP calls) |
| Codes | up to 10 sources per game (validators, APIs, wikis, community witnesses, official posts), fetched in parallel, behind the gate above |
| Version / pre-install / launch media | HoYoPlay `getGameBranches` + `getAllGameBasicInfo` / Kuro `G153` game & launcher background indexes (the version-less Kuro background is attributed when it is seen and dated by the CDN `Last-Modified`) |

A dead source is logged, shown in the job summary, and skipped. Everything is fetched in parallel
(max 12 connections, per-request timeouts), so a run takes seconds even when several hosts are
down. If every announcement source of a game is down, the summary says so and the next run
re-reads the last `LOOKBACK_HOURS` — nothing is missed.

**Layer 2 — two instances, automatic fail-over, shared dedup.**

| Instance | Variables |
|---|---|
| **alpha** (primary) | `INSTANCE_NAME=alpha`, `HEARTBEAT_MINUTES=60`, `PEER_STATE_URL=<bravo's raw state URL>` |
| **bravo** (standby) | `INSTANCE_NAME=bravo`, `INSTANCE_ROLE=standby`, `PEER_STATE_URL=https://raw.githubusercontent.com/<owner>/<alpha-repo>/main/state/state.json`, `FAILOVER_AFTER_MINUTES=150` |

- Use the **same webhook secrets** in both instances.
- Every run, each instance imports the other's posted keys. The standby stays passive while the
  primary's heartbeat is fresh, and starts posting automatically when it goes stale.
- The standby never fails over faster than 2.5× the primary's heartbeat interval, and never when
  the peer state can't be read — so a misconfiguration cannot cause double posts.
- When alpha comes back it imports bravo's posts and edits bravo's cards (same webhook).

**One repo or several.** One repo can be the code home and production at once: CI tests every PR,
and merging deploys it. You can also follow the News-Express convention of a development repo
plus instance repos (alpha / bravo) — see [docs/PROD-REPO-SETUP.md](docs/PROD-REPO-SETUP.md).
Only a development copy that must never post gets `ENABLED_FEATURES=none`; a manual `test` run
still works there. **Never set it on the repo that posts.**

**Scheduler.** GitHub's native `schedule:` is disabled (commented out) in `monitor.yml`, exactly
like News-Express, because two schedulers on one repo race each other. cron-job.org calls the
`workflow_dispatch` API every 5 minutes; the concurrency queue plus the fresh branch checkout
make an overlapping trigger safe. **[docs/SCHEDULER.md](docs/SCHEDULER.md)**.

---

The existing `runner.py::write_summary` reports application outcomes, source
counts and elapsed time. Summary/annotation text is sanitized best effort, but
operators should still review retained output before sharing it. An empty report
is not proof of healthy sources or no eligible items. The summary precedes the
workflow's repository commit/push; check that later step for persistence. Summary
output failure does not add a report file or change posting/state behavior.

Runtime updates use exact CPython **3.14.10** pins. Python update proposals are
validated automatically but always merged while an operator is available.
Package-only Dependabot auto-merge remains opt-in; workflow-file updates wait
for review. See [Python policy](docs/PYTHON_VERSION.md). A live-workflow update
can still need GitHub approval; confirm the next real execution after merging.

## 🧪 Testing & CI

**➡️ Full checklist: [docs/TESTING.md](docs/TESTING.md).**

| Gate | What it runs |
|---|---|
| **CI** (`ci.yml`, required) | install → `compileall` → `validate` → every `tests/test_*.py` through its plain runner → preview render. **every test offline — no network, no secrets** |
| **CI — advisory checks** (never blocks a merge) | `pip-audit` (CVEs in `requirements.txt`), `actionlint` (workflow YAML), `zizmor` (workflow security), `ruff` (the same `ruff.toml` you run locally) |
| **Monitor test bench** (`mode = test`) | webhooks, real codes, or the real schedule card — against the live sources |

The offline suite pins real official posts captured on 2026-09-25 (which must reproduce the
reference cards' timestamps), golden JSON for the 4 converted cards, button nesting and Discord's
component/character limits, every code parser and the code gate, the 4★ TBA rules, silent edits,
stale-post suppression, fail-over, parallel fetching, and the workflow files themselves.

```bash
python tests/test_smoke.py                       # the main offline suite (what CI runs first)
python -m pytest -q tests                        # every test file in one go
UPDATE_GOLDEN=1 python tests/test_smoke.py       # after an INTENTIONAL card change
python -m gamexpress preview                     # open previews/index.html
```

---

## 📚 Documentation

| Doc | What's in it |
|---|---|
| **[docs/CONFIGURATION.md](docs/CONFIGURATION.md)** | every secret/variable and game/override field; full official-news setup, paging, grouping and delivery safeguards |
| **[docs/ACCURACY.md](docs/ACCURACY.md)** | how a post becomes a card: detection, extraction, provenance, the code gate |
| **[docs/SOURCES.md](docs/SOURCES.md)** | every verified endpoint, with why it was chosen or rejected |
| **[docs/BANNER_DATABASE.md](docs/BANNER_DATABASE.md)** | where banner line-ups come from: the wiki readers, the precedence order, how an official notice is read, how a TBA fills itself in, and when a name locks |
| **[docs/SCHEDULER.md](docs/SCHEDULER.md)** | the cron-job.org trigger, the classic token, how fast it can poll |
| **[docs/TESTING.md](docs/TESTING.md)** | the manual test bench and the local commands |
| **[docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md)** | symptom → fix |
| **[docs/SECURITY.md](docs/SECURITY.md)** | threat model: untrusted sources, secrets, workflow permissions |
| **[docs/TIMESTAMP-PATTERNS.md](docs/TIMESTAMP-PATTERNS.md)** | the release-rhythm study the estimates are calibrated on |
| **[docs/DEPENDABOT.md](docs/DEPENDABOT.md)** · **[docs/PYTHON_VERSION.md](docs/PYTHON_VERSION.md)** | dependency and interpreter upkeep |
| **[docs/PROD-REPO-SETUP.md](docs/PROD-REPO-SETUP.md)** · **[docs/ROLLOUT.md](docs/ROLLOUT.md)** | splitting into a private dev repo + a public production repo, and the order to roll a change out in |
| **[docs/CREDITS.md](docs/CREDITS.md)** | upstream projects and community databases |
| **[AGENTS.md](AGENTS.md)** | the maintainer's mental model — read before changing code |

Index: **[docs/](docs/)**.

---

## 🗒 Changelog

Latest release and current changes are documented in
[`docs/changelog/CHANGELOG.md`](docs/changelog/CHANGELOG.md).

Historical records are preserved in
[`docs/changelog/CHANGELOG_ARCHIVE.md`](docs/changelog/CHANGELOG_ARCHIVE.md).

---

## 📄 Legal & credits

- **[Privacy Policy](PRIVACY_POLICY.md)** · **[Terms of Service](TERMS_OF_SERVICE.md)**
- **Not affiliated** with HoYoverse, Kuro Games, NetEase or Discord. Game names and assets belong
  to their owners.
- This monitor is a thin layer over other people's work — [seriaati/hoyo-codes](https://github.com/seriaati/hoyo-codes),
  [Ertezy/Kitsudock-data](https://github.com/Ertezy/Kitsudock-data),
  [c3kay/hoyolab-rss-feeds](https://github.com/c3kay/hoyolab-rss-feeds),
  [torikushiii/hoyoverse-api](https://github.com/torikushiii/hoyoverse-api) (`api.ennead.cc`) and
  [Open Gacha Codes](https://github.com/torikushiii/OpenGachaCodes),
  [Hum-Bao/hoyoverse-codes](https://github.com/Hum-Bao/hoyoverse-codes),
  [PromoGacha](https://github.com/gripcrip-blip/codehub),
  [DuolaD/HoYo_Versioncatcher](https://github.com/DuolaD/HoYo_Versioncatcher),
  [TwintailTeam/game-manifests](https://github.com/TwintailTeam/game-manifests) and
  [TomyJan/GenshinImpact-Client-Version](https://github.com/TomyJan/GenshinImpact-Client-Version),
  [DynamiByte](https://github.com/DynamiByte) (HoyoPlay and Wuthering Waves launcher API notes,
  with [Cheu3172/Wuwa-Web-Request](https://github.com/Cheu3172/Wuwa-Web-Request)) and
  the [gengamer.in](https://genshin-countdown.gengamer.in/) and
  [gachacountdown.online](https://gachacountdown.online/) countdowns, the Fandom wikis and their
  editors, [nitter](https://github.com/zedeus/nitter), [redlib](https://github.com/redlib-org/redlib)
  (and [mitchross/redlib](https://github.com/mitchross/redlib)),
  and [eddrit](https://github.com/corenting/eddrit) and every operator who keeps a public instance
  online, [FxEmbed / FxTwitter](https://github.com/FxEmbed/FxEmbed), and
  [BetterTwitFix / vxTwitter](https://github.com/dylanpdx/BetterTwitFix). The full list, with
  active beta sources, tools, research references and licences: **[docs/CREDITS.md](docs/CREDITS.md)**.
- **Sibling project:** [News-Express](https://github.com/uesu/News-Express) — same design,
  different beat.
