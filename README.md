<div align="center">

# Game-Express

**Version-schedule announcements and redemption codes for six gacha games, posted to Discord as
Components V2 cards — with no server, no bot token and nothing to host.**

[![CI](https://github.com/uesu/Game-Express/actions/workflows/ci.yml/badge.svg)](https://github.com/uesu/Game-Express/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.14-3776AB?logo=python&logoColor=white&labelColor=2b2d31)](docs/PYTHON_VERSION.md)
[![Tests](https://img.shields.io/badge/tests-offline%20%C2%B7%20no%20secrets-3FB950?labelColor=2b2d31)](docs/TESTING.md)
[![Discord](https://img.shields.io/badge/posts%20to-Discord-5865F2?logo=discord&logoColor=white&labelColor=2b2d31)](https://discord.com/developers/docs/components/reference)

[Setup](#-setup) · [Configuration](docs/CONFIGURATION.md) · [Docs](docs/) ·
[Changelog](docs/changelog/CHANGELOG.md) · [Troubleshooting](docs/TROUBLESHOOTING.md)

</div>

---

Game-Express watches the official channels of **Genshin Impact**, **Honkai: Star Rail**,
**Zenless Zone Zero**, **Wuthering Waves**, **Honkai: Nexus Anima** and **ANANTA**. When a
Special Program is announced or a new redemption code appears, it posts one card — and then
keeps that card correct by editing it silently as official information arrives.

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

One card per game + version, triggered by an official *Special Program* / *Special Broadcast* /
livestream announcement or an update-maintenance notice.

```
<@&ROLE> Honkai: Star Rail Version 4.6 Schedule! 📜              ← ping line (only if a role is set)
┌───────────────────────────────────────────────────────────── (accent 14922399)
│ ## Honkai: Star Rail Version 4.6 Special Program               ← title, links to the video/post
│ <t:1789903800:F> or <t:1789903800:R>                           ← Discord timestamps
│ ※ In the event that the maintenance is extended, …
│ ─────────────
│ **Version 4.6 Banners (STC)**
│ ※ Re-runs: TBA
│ ✦ First Half/Phase: Pearl         - 4 Star Characters: TBA
│ ✦ Second Half/Phase: TBA          - 4 Star Characters: TBA
│ ─────────────
│ **Maintenance Details (STC)**
│ ✦ Pre-Install: <t:…:F>   ✦ Start: <t:…:F>   ✦ End: <t:…:F>   ✦ Compensation: Stellar Jade ×300
│ [ announcement image ]
│ ─────────────
│ [ Youtube ] [ Twitch ] [ HoYoLAB ]                             ← buttons INSIDE the card
│ -# STC — Subject to Change • TBA — To be Announced
└─────────────────────────────────────────────────────────────
```

- **Each game keeps its own format.** Wuthering Waves uses `"Special Broadcast"` in the title,
  shows maintenance before banners and adds the `※ 4 Star Characters:` summary line; Genshin's
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
  | the announcement's own link + key art | the official news page, then the paged-back HoYoLAB list | `PROGRAM_MEDIA=0` |

  Details: **[docs/ACCURACY.md → Filling the gaps](docs/ACCURACY.md#filling-the-gaps-before-the-official-notice)**.

### 2 · Redemption code card

One card per batch of new codes, in **that game's own codes channel**. New codes found in the
same run share a card.

```
<@&ROLE> Genshin Impact Redemption Codes! 🎁                       ← ping line (optional)
┌───────────────────────────────────────────────────────────── (game color)
│ ## 🎁 Genshin Impact Redemption Codes                     [game icon]
│ -# 2 new codes • detected <t:…:R>
│ ─────────────
│ ✦ `VESNAONPATROL`
│ -# Primogem ×40 • Mora ×20000 • Hero's Wit ×3
│ ✦ `EPIC2026`
│ -# 40 primogems, five hero's wit, and 20k mora
│ ─────────────
│ [ 🎁 VESNAONPATROL ] [ 🎁 EPIC2026 ]                    ← one Redeem button per code, INSIDE the card
│ ※ Tap a code to open the official redemption page with it filled in, or redeem in-game: …
│ ─────────────
│ [ <a:starward11> Citlali News ]                       ← community row, its own row (COMMUNITY_BUTTONS)
│ -# Source: PromoGacha, hoyo-codes.seria.moe (verified) • Codes expire — redeem soon.
└─────────────────────────────────────────────────────────────
```

- **GI / HSR / ZZZ**: every Redeem button opens the official page with the code prefilled.
  **Wuthering Waves** has no web redemption, so the card shows the in-game path instead
  (*Settings → Other Settings → Account → Redemption Code*, Union Level 2+).
- **Expired codes are struck through automatically.** When every source that still lists a posted
  code says it expired, the same message is edited silently: `~~CODE~~ · expired`, and its button
  is removed. No second ping. `CODES_MARK_EXPIRED=off` disables it.
- Codes only post after passing the [accuracy gate](#-how-it-decides-to-post).

> Want to see every card before touching Discord? `python -m gamexpress preview` →
> open `previews/index.html`.

---

## 🎮 Supported games

| Game | Status | Schedule sources | Code sources |
|---|---|---|---|
| Genshin Impact | ✅ on | HoYoLAB API (gid 2) → c3kay mirror · X `@GenshinImpact` · HoYoPlay launcher | HoYoLAB livestream module · official posts · seria + Hum-Bao (both redeem-validated) · Open Gacha Codes · ennead · fandom · PromoGacha |
| Honkai: Star Rail | ✅ on | HoYoLAB API (gid 6) → c3kay · X `@honkaistarrail` · HoYoPlay | same set |
| Zenless Zone Zero | ✅ on | HoYoLAB API (gid 8) → c3kay · X `@ZZZ_EN` · HoYoPlay | same set |
| Wuthering Waves | ✅ on | X `@Wuthering_Waves` · Kuro official site · Kuro launcher | official X posts · wuthering.gg (active/expired) · Open Gacha Codes · fandom · PromoGacha |
| Honkai: Nexus Anima | ✅ on · ⏳ not released yet | HoYoLAB API (gid 9) · X `@HonkaiNA` | HoYoLAB livestream module (gid 9) · X |
| ANANTA (NetEase) | ✅ on · ⏳ releases 2027‑01‑15 | X `@Ananta_EN` | X |

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

Six steps, about fifteen minutes. One repo can be both the code home and production — CI tests
every PR, and merging deploys it.

### 1 · Get the repo

Fork or clone it. **Public repos get unlimited free Actions minutes** — a private repo works
too, but it should run every 30 minutes instead of every 5
([why](docs/SCHEDULER.md#minutes-and-private-repositories)). A second instance repo for
fail-over is optional ([Reliability](#-reliability)).

### 2 · Create the Discord webhooks

*Channel → Edit Channel → Integrations → Webhooks → New Webhook → Copy Webhook URL.*
One for the schedule channel, and one per game codes channel.

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
| `NITTER_RSS_TOKEN` | *optional* — the same one as News-Express |

The same URL may be used for several secrets, for example one codes channel for every game.

### 4 · Add the variables

*… → Variables.* `PING_ROLE_ID` = your role ID — **leave it unset for no ping**, or set
`NO_PING=1`. The Youtube and Twitch emojis already default to the animated ones.
Everything else:
**[docs/CONFIGURATION.md](docs/CONFIGURATION.md)**.

### 5 · Test it

*Actions → **Game-Express Monitor** → Run workflow → `mode` = **test***, then `webhooks` →
`codes` → `schedule`. Each one posts **real** data labelled 🧪 TEST, never writes the state, and
pings nobody by default. Walkthrough: **[docs/TESTING.md](docs/TESTING.md)**.

### 6 · Go live with cron-job.org

Create one cron-job.org job per instance repo that calls the `workflow_dispatch` API every
5 minutes, using a GitHub **classic token** with the `repo` scope. Step by step:
**[docs/SCHEDULER.md](docs/SCHEDULER.md)**. GitHub's own `schedule:` is disabled in
`monitor.yml`, so two schedulers can never race.

### Then what?

**First real run = silent seed.** Current announcements and every existing code are recorded
without posting, so deploying never spams old items. The summary lists what was seeded
(`🌱 HSR 4.6: seeded silently`, `🌱 GI: seeded 34 existing codes`). To post what's current on the
very first run instead, set `BOOTSTRAP_POST=1` before that run.

**Already seeded and want a current card now?** Run the Monitor with `repost = starrail:4.6` (any
version shown in a summary). The card is posted as a new message and then kept up to date like
any other. If the Special Program aired before the bot was running, its time isn't in the feeds
any more, so the card leaves that line out — pin it in `config/overrides.json`
(`"program_ts": "2026-09-20T19:30:00+08:00"`).

---

## ⚙️ Configuration

**➡️ Full reference: [docs/CONFIGURATION.md](docs/CONFIGURATION.md)** — every secret, variable,
`games.json` field and `overrides.json` key.

The workflow passes **every** secret and variable to the app, so any of them works without
editing YAML. The ones worth knowing:

| Variable | Default | What it does |
|---|---|---|
| `PING_ROLE_ID` | *(unset)* | role(s) to ping. Unset = no ping |
| `ENABLED_FEATURES` | `schedule,codes` | `schedule` · `codes` · `none` (paused / cold standby) |
| `GAMES` / `ENABLE_GAMES` | all enabled / — | run a subset · switch prepared games on |
| `LOOKBACK_HOURS` | 72 | how far back official posts are considered |
| `CODES_MIN_SOURCES` | 2 | independent sources needed for an unverified code |
| `EDIT_ON_UPDATE` | on | silent in-place edits when official info arrives |
| `DRY_RUN` | off | build and log only, post nothing |

Webhook routing, most specific first:
`DISCORD_WEBHOOK_<FEATURE>_<GAME>` → `DISCORD_WEBHOOK_<FEATURE>` → `DISCORD_WEBHOOK_URL`.
`python -m gamexpress validate` prints which secret feeds which channel.

---

## 🎯 How it decides to post

**➡️ Full rules: [docs/ACCURACY.md](docs/ACCURACY.md).** The short version:

1. **Detect** — official posts from HoYoLAB, official X accounts and the Kuro site, filtered by
   per-game patterns. Recaps, replays, "has ended" and merch are ignored.
2. **Extract from official text only** — times need an explicit offset (`UTC+8`; `(server time)`
   is never trusted), versions come from `Version 4.6` / `Ver.4.6` / `V4.6`, banners only from
   quoted names following "5-star character" / "S-Rank Agent" / "5-star Resonator".
3. **Merge with provenance** — *overrides > official notice > official tweet > launcher signal >
   countdown estimate > learned pre-install fallback > banner feed*.
4. **Unknown is `TBA`**, banners always carry `(STC)`, and no estimate can overwrite an official
   value.
5. **Post once, then edit silently.** A deleted Discord message (`404 Unknown Message`) is
   re-posted once and the new id adopted; every other edit failure stays an error and never
   reposts.

**The code gate.** A code posts when **any one** of these is true: it comes from an **official**
source; a **redeem-validator** (seria or Hum-Bao, which try every code on a real account) says it
works and none says it expired; or **≥ `CODES_MIN_SOURCES` independent** community sources list
it as active and **none** lists it as expired. An explicit *valid until* date that has passed
beats every source that still lists the code. Anything else waits as *pending* for up to 14 days,
with the reason in the job summary.

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
> the real thing later. Delete the test cards when you are done with them.

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

Flags: `--dry-run --only --game --repost --kind --ping --out`.

---

## 🛡 Reliability

**Layer 1 — every data point has a fallback chain, inside every run.**

| Data | Chain |
|---|---|
| HoYoverse news | official HoYoLAB API → c3kay JSON-Feed mirror |
| X timelines | the built-in nitter fleet (18 mirrors; `NITTER_INSTANCES` overrides it). The first **two** working mirrors are merged, so a stale-but-200 mirror can't hide a tweet |
| Tweet details | FxTwitter → vxTwitter → RSS body |
| Codes | up to 8 sources per game (validators, APIs, wikis, official posts), fetched in parallel, behind the gate above |
| Version / pre-install | HoYoPlay `getGameBranches` / Kuro launcher index |

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

## 🧪 Testing & CI

**➡️ Full checklist: [docs/TESTING.md](docs/TESTING.md).**

| Gate | What it runs |
|---|---|
| **CI** (`ci.yml`, required) | install → `compileall` → `validate` → `tests/test_smoke.py` → preview render. **every test offline — no network, no secrets** |
| **CI — advisory checks** (never blocks a merge) | `pip-audit` (CVEs in `requirements.txt`), `actionlint` (workflow YAML), `zizmor` (workflow security), `ruff` (the same `ruff.toml` you run locally) |
| **Monitor test bench** (`mode = test`) | webhooks, real codes, or the real schedule card — against the live sources |

The offline suite pins real official posts captured on 2026-09-25 (which must reproduce the
reference cards' timestamps), golden JSON for the 4 converted cards, button nesting and Discord's
component/character limits, every code parser and the code gate, the 4★ TBA rules, silent edits,
stale-post suppression, fail-over, parallel fetching, and the workflow files themselves.

```bash
python tests/test_smoke.py                       # the full offline suite
UPDATE_GOLDEN=1 python tests/test_smoke.py       # after an INTENTIONAL card change
python -m gamexpress preview                     # open previews/index.html
```

---

## 📚 Documentation

| Doc | What's in it |
|---|---|
| **[docs/CONFIGURATION.md](docs/CONFIGURATION.md)** | every secret, variable, `games.json` field and `overrides.json` key |
| **[docs/ACCURACY.md](docs/ACCURACY.md)** | how a post becomes a card: detection, extraction, provenance, the code gate |
| **[docs/SOURCES.md](docs/SOURCES.md)** | every verified endpoint, with why it was chosen or rejected |
| **[docs/SCHEDULER.md](docs/SCHEDULER.md)** | the cron-job.org trigger, the classic token, how fast it can poll |
| **[docs/TESTING.md](docs/TESTING.md)** | the manual test bench and the local commands |
| **[docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md)** | symptom → fix |
| **[docs/SECURITY.md](docs/SECURITY.md)** | threat model: untrusted sources, secrets, workflow permissions |
| **[docs/TIMESTAMP-PATTERNS.md](docs/TIMESTAMP-PATTERNS.md)** | the release-rhythm study the estimates are calibrated on |
| **[docs/DEPENDABOT.md](docs/DEPENDABOT.md)** · **[docs/PYTHON_VERSION.md](docs/PYTHON_VERSION.md)** | dependency and interpreter upkeep |
| **[docs/PROD-REPO-SETUP.md](docs/PROD-REPO-SETUP.md)** | splitting into a private dev repo + a public production repo |
| **[docs/CREDITS.md](docs/CREDITS.md)** | upstream projects and community databases |
| **[AGENTS.md](AGENTS.md)** | the maintainer's mental model — read before changing code |

Index: **[docs/](docs/)**.

---

## 🗒 Changelog

**Latest — [2026-10-05](docs/changelog/CHANGELOG.md#2026-10-05) · *the README stops being a
history book, and the version number retires***

- The README went from 958 lines to 483: the configuration reference, accuracy rules,
  troubleshooting table and credits moved into [`docs/`](docs/), and the release history moved
  into [`docs/changelog/`](docs/changelog/).
- **No more version number.** `build_id()` reports the short `GITHUB_SHA` instead, so a run
  summary reads `### Game-Express 03c1668 — alpha (primary)` and points at the exact code that
  posted the card. A bump used to mean four files moving in lockstep; now there is nothing to
  bump and nothing to go stale.
- Dead fields removed (`Item.author`, `Settings.log_level`, `Game.publisher`, `FoundTime.has_tz`,
  and `app_version` on the heartbeat) — all written, never read.
- Stale facts swept repo-wide: the nitter fleet size, the 5-minute poll cadence, and every
  cross-reference that still pointed at the README's old changelog.

**➡️ Full history: [docs/changelog/](docs/changelog/)** —
[current entries](docs/changelog/CHANGELOG.md) (1.8.0 onward) ·
[archive](docs/changelog/CHANGELOG_ARCHIVE.md) (1.0.0 → 1.7.0).

Entries are **dated, not numbered** — releases up to `1.9.0` keep the numbers they shipped as.

---

## 📄 Legal & credits

- **[Privacy Policy](PRIVACY_POLICY.md)** · **[Terms of Service](TERMS_OF_SERVICE.md)**
- **Not affiliated** with HoYoverse, Kuro Games, NetEase or Discord. Game names and assets belong
  to their owners.
- This monitor is a thin layer over other people's work — [seriaati/hoyo-codes](https://github.com/seriaati/hoyo-codes),
  [Ertezy/Kitsudock-data](https://github.com/Ertezy/Kitsudock-data),
  [c3kay/hoyolab-rss-feeds](https://github.com/c3kay/hoyolab-rss-feeds),
  [Open Gacha Codes](https://github.com/torikushiii/OpenGachaCodes),
  [Hum-Bao/hoyoverse-codes](https://github.com/Hum-Bao/hoyoverse-codes),
  [PromoGacha](https://github.com/gripcrip-blip/codehub), the Fandom wikis and their editors,
  [nitter](https://github.com/zedeus/nitter) and every operator who keeps a public instance
  online, and [FxTwitter](https://github.com/FixTweet/FxTwitter). The full list, with licences
  and the community databases: **[docs/CREDITS.md](docs/CREDITS.md)**.
- **Sibling project:** [News-Express](https://github.com/uesu/News-Express) — same design,
  different beat.
