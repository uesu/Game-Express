# Game-Express — Version Schedule Announcements + Code Poster → Discord

[![CI](https://github.com/uesu/Game-Express/actions/workflows/ci.yml/badge.svg)](https://github.com/uesu/Game-Express/actions/workflows/ci.yml)

Automated **version-schedule announcements** and a **redemption-code poster** for
**Genshin Impact · Honkai: Star Rail · Zenless Zone Zero · Wuthering Waves**, with
**Honkai: Nexus Anima** and **ANANTA (NetEase)** already prepared (switched off until they launch).

Everything is posted as **Discord Components V2 cards**, with the **buttons inside the card**,
the announcement image, **Discord timestamps** (every reader sees their own timezone),
**STC / TBA** markers and an **optional role ping**. It runs free on **GitHub Actions** (public
repos get unlimited minutes), triggered every 10 minutes by **[cron-job.org](https://cron-job.org)**,
with no server, no bot token and nothing to host or redeploy — merging to `main` **is** the
deploy, so every fix and improvement reaches the running poster on the next 10-minute run.

> Same architecture and lessons as [News-Express](https://github.com/uesu/News-Express):
> fallback chains for every source, dedup state committed to the repo, a queued (never
> cancelled) workflow, offline golden tests as the CI gate, and a two-instance fail-over.

---

## Contents
- [What it posts](#-what-it-posts)
- [Supported games](#-supported-games)
- [Setup — 6 steps (GitHub Actions + cron-job.org)](#-setup--6-steps-github-actions--cron-joborg)
- [Configuration reference](#-configuration-reference)
- [How it decides to post (accuracy rules)](#-how-it-decides-to-post-accuracy-rules)
- [Manual controls](#-manual-controls)
- [Redundancy: fallback chains + two-instance fail-over](#-redundancy-fallback-chains--two-instance-fail-over)
- [Testing & previews](#-testing--previews)
- [Troubleshooting](#-troubleshooting)
- [Data sources](#-data-sources)
- [Community databases & resources](#-community-databases--resources)
- [Privacy · Terms · Credits](#-privacy--terms--credits)
- [Changelog](#-changelog)

---

## 🃏 What it posts

### 1. Version schedule card: posted once per game + version, only on a pattern match

Triggered by an **official** post that matches a pattern: a *Special Program* / *Special
Broadcast* / livestream announcement, or an official update-maintenance notice. It never
posts on a timer.

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

- **Your four reference cards were converted 1:1.** Each game keeps its own format:
  - Wuthering Waves uses `"Special Broadcast"` in the title, shows maintenance before banners, uses `✦ Maintenance: <t:…:f> to <t:…:t>`, and has the `※ 4 Star Characters:` summary line.
  - Genshin's banner heading links to lunaris.moe/banners.
  - HSR's heading reads `Maintenance Details (STC)`.
- **The card stays accurate after posting.** When official information arrives later (the
  maintenance notice with pre-install/start/duration/compensation, pre-install going live in the
  official launcher, an official banner notice, or your edits in `config/overrides.json`), the
  **same message is edited silently**, with no second ping and no duplicate post.

**Maintenance times before the official notice (estimates).** The maintenance notice usually
arrives days after the Special Program, so until then the card can only show `TBA`. Since
**1.2.0** the monitor fills those gaps from community countdown sites
(`{game}-countdown.gengamer.in`, `gachacountdown.online`):

- an estimate is used **only** for a time that no official source has given yet, and it is
  replaced automatically the moment the official notice is seen (the same silent edit);
- the card says so: `🕒 maintenance start, maintenance end estimated from Gacha Countdown — the
  official notice replaces it automatically`, and the run summary carries the same line;
- `COUNTDOWN_ESTIMATES=0` switches it off, and a countdown site is only asked for a game that
  is actually missing a time (no request is wasted on a version that is already out).

**Pre-install time when the notice has not arrived (since 1.6.0).** If maintenance start is known
but no official source has published pre-install yet, the monitor derives one labelled
**estimated**. The fallback is not a fixed weekday rule: each real notice records its lead in
hours (`maintenance start - pre-install`), and later versions use that game's median. The median
handles shortened/extended patches and holiday moves without one bad parse dragging future
cards. On a fresh installation the verified 2026 leads are used once (GI 43 h · HSR 88 h · ZZZ
42 h · WW 42 h). A derived value never teaches the model, so a guess cannot confirm itself; an
official HoYoLAB, X/Nitter, Kuro, launcher or override value replaces it automatically.

**The announcement's own link and key art (since 1.3.0).** A run only sees posts inside its
lookback window, so a version that is already a week old can end up with a card that links to the
*Update and Maintenance Notice* — and shows that notice's cover — simply because the Special
Program announcement had scrolled out. Since **1.3.0** the monitor looks the announcement up:

- the **official news pages** (`genshin.hoyoverse.com/en/news`, `hsr.hoyoverse.com/en-us/news`,
  `zenless.hoyoverse.com/en-us/news`, `wutheringwaves.kurogames.com/en/main/news`) archive every
  announcement with its cover, and an article page carries the embedded stream — whose YouTube
  thumbnail is the program's own 1280×720 artwork;
- failing that, the **HoYoLAB news list is paged back** past the lookback window;
- images are always upgraded to the biggest rendition the source serves (tweet photo → `?name=orig`,
  YouTube → `maxresdefault`), and the card says where the key art came from
  (`🖼️ key art: HoYoLAB — the official announcement`);
- one lookup per version that still needs it, never for a version that is already live, and
  `PROGRAM_MEDIA=0` switches it off.

### 2. Redemption code card: posted once per code (also Components V2)

Each game posts to **its own codes channel** (`DISCORD_WEBHOOK_CODES_GENSHIN`, `…_STARRAIL`,
`…_HNA`, `…_ZZZ`, `…_WUWA`, `…_ANANTA`). New codes found in the same run share one card.

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
- **Expired codes are struck through automatically.** When every source that still lists a
  posted code says it expired, the same message is edited silently: `~~CODE~~ · expired`, and
  its button is removed. No second ping. Turn it off with `CODES_MARK_EXPIRED=off`.
- Codes are only posted after passing the accuracy gate (see
  [below](#-how-it-decides-to-post-accuracy-rules)). Screenshots of every card:
  `python -m gamexpress preview` → open `previews/index.html`.

---

## 🎮 Supported games

| Game | Status | Schedule sources | Code sources |
|---|---|---|---|
| Genshin Impact | ✅ on | HoYoLAB API (gid 2) → c3kay mirror · X `@GenshinImpact` · HoYoPlay launcher | HoYoLAB livestream module · official posts · seria + Hum-Bao (both redeem-validated) · Open Gacha Codes · ennead · fandom · PromoGacha |
| Honkai: Star Rail | ✅ on | HoYoLAB API (gid 6) → c3kay · X `@honkaistarrail` · HoYoPlay | same set |
| Zenless Zone Zero | ✅ on | HoYoLAB API (gid 8) → c3kay · X `@ZZZ_EN` · HoYoPlay | same set |
| Wuthering Waves | ✅ on | X `@Wuthering_Waves` · Kuro official site · Kuro launcher | official X posts · wuthering.gg (active/expired) · Open Gacha Codes · fandom · PromoGacha |
| Honkai: Nexus Anima | 💤 prepared (no release date yet) | HoYoLAB API (gid 9) · X `@HonkaiNA` | HoYoLAB livestream module (gid 9) · X |
| ANANTA (NetEase) | 💤 prepared · **turns on by itself on 2027‑01‑15** | X `@Ananta_EN` | X |

**Turning a prepared game on** needs no code change: set the variable `ENABLE_GAMES=hna` (or
`hna,ananta`), or set `"enabled": true` in `config/games.json`. ANANTA switches itself on at its
announced global launch date (`auto_enable_on` in `games.json`; delete that line if the date
moves). ANANTA has no character gacha, so its card hides the banner section.

---

## 🚀 Setup — 6 steps (GitHub Actions + cron-job.org)

1. **Get the repo.** The simplest setup is one repo that is both the code home and production.
   A second instance repo for fail-over is optional (see
   [Redundancy](#-redundancy-fallback-chains--two-instance-fail-over)). Public repos get
   unlimited free Actions minutes. A private repo works too, but it should run every 30 minutes
   instead of every 10 ([why](docs/SCHEDULER.md#minutes-and-private-repositories)).
2. **Create webhooks.** In Discord: *Channel → Edit Channel → Integrations → Webhooks → New
   Webhook → Copy Webhook URL*. One for the schedule channel, and one per game codes channel.
3. **Add the secrets** in *Settings → Secrets and variables → Actions → Secrets → New repository
   secret*:

   | Secret | Channel |
   |---|---|
   | `DISCORD_WEBHOOK_SCHEDULE` | version-schedule announcements (all games) |
   | `DISCORD_WEBHOOK_CODES_GENSHIN` | Genshin Impact codes |
   | `DISCORD_WEBHOOK_CODES_STARRAIL` | Honkai: Star Rail codes |
   | `DISCORD_WEBHOOK_CODES_HNA` | Honkai: Nexus Anima codes (used once the game is on) |
   | `DISCORD_WEBHOOK_CODES_ZZZ` | Zenless Zone Zero codes |
   | `DISCORD_WEBHOOK_CODES_WUWA` | Wuthering Waves codes |
   | `DISCORD_WEBHOOK_CODES_ANANTA` | ANANTA codes (used once the game is on) |
   | `NITTER_RSS_TOKEN` | *optional*: the same one as News-Express |

   The same URL may be used for several secrets (for example, one codes channel for every game).
4. **Add variables** (not secret) in *… → Variables*:
   - `PING_ROLE_ID` = `1296268365593186426` (**leave it unset for no ping**, or `NO_PING=1`)
   - the emojis already default to your animated ones
5. **Test.** *Actions → **Game-Express Monitor** → Run workflow → `mode` = **test***:
   `webhooks` → `codes` → `schedule`. Each one is explained in
   **[docs/TESTING.md](docs/TESTING.md)**. They post real data labelled 🧪 TEST, never write the
   state, and nobody is pinged by default.
6. **Go live with cron-job.org.** Create one cron-job.org job per instance repo that calls the
   `workflow_dispatch` API every 10 minutes, using a GitHub **classic token** with the `repo`
   scope. Step by step: **[docs/SCHEDULER.md](docs/SCHEDULER.md)**. GitHub's own `schedule:` is
   disabled in `monitor.yml`, so the two schedulers can never race.

**First real run = silent seed.** Current announcements and every existing code are recorded
without posting, so deploying never spams old items. The summary lists what was seeded
(`🌱 HSR 4.6: seeded silently`, `🌱 GI: seeded 34 existing codes`). To post what's current on
the very first run instead, set the variable `BOOTSTRAP_POST=1` before that run.

**Already seeded and want a current card posted now?** Run the Monitor with
`repost = starrail:4.6` (any version shown in a summary). The card is posted as a new message
and is then kept up to date like any other. If the version's Special Program aired before the
bot was running, its time isn't in the feeds any more, so the card simply leaves that line
out. You can pin it in `config/overrides.json` (`"program_ts": "2026-09-20T19:30:00+08:00"`).

---

## ⚙️ Configuration reference

### Secrets (sensitive)
| Name | Purpose |
|---|---|
| `DISCORD_WEBHOOK_SCHEDULE` | schedule cards |
| `DISCORD_WEBHOOK_CODES_GENSHIN` · `_STARRAIL` · `_HNA` · `_ZZZ` · `_WUWA` · `_ANANTA` | code cards, one channel per game |
| `DISCORD_WEBHOOK_CODES` | optional: codes of any game without its own secret |
| `DISCORD_WEBHOOK_URL` | optional catch-all fallback |
| `DISCORD_WEBHOOK_SCHEDULE_<GAME>` | optional per-game schedule channel, e.g. `DISCORD_WEBHOOK_SCHEDULE_WUWA` |
| `NITTER_RSS_TOKEN` | optional — the e-mailed token for the one token-gated nitter mirror, `https://nitter.miningtcup.me/` (same secret News-Express uses). Empty only skips that mirror |

Webhook routing: `DISCORD_WEBHOOK_<FEATURE>_<GAME>` → `DISCORD_WEBHOOK_<FEATURE>` → `DISCORD_WEBHOOK_URL`.
`<GAME>` is the game key or its short name: `GENSHIN`/`GI`, `STARRAIL`/`HSR`, `ZZZ`,
`WUWA`/`WW`, `HNA`/`NEXUSANIMA`, `ANANTA`. For a forum or thread channel, append
`?thread_id=<id>` to the webhook URL. `python -m gamexpress validate` (step 1 of every workflow
run) prints which secret feeds which channel.

### Variables (not secret)

These are one-click switches. The workflow passes **every** secret and variable to the app, so
any name below works without editing YAML.

| Name | Default | Meaning |
|---|---|---|
| `PING_ROLE_ID` | *(unset)* | role ID(s) to ping. **Unset = no ping.** Comma-separate for several; `everyone` / `here` allowed |
| `PING_SCHEDULE` / `PING_CODES` | inherit | per-feature override; `none` = explicitly no ping |
| `PING_<FEATURE>_<GAME>` | inherit | e.g. `PING_SCHEDULE_GENSHIN=111…` |
| `NO_PING` | off | `1` = never ping, whatever the other ping variables say |
| `EMOJI_YOUTUBE` / `EMOJI_TWITCH` | your animated emojis | format `a:name:id` (animated), `name:id`, a unicode emoji, or `none` |
| `EMOJI_SOURCE` / `EMOJI_REDEEM` | — / 🎁 | emojis for the Source and Redeem buttons |
| `EXTRA_BUTTONS` | — | JSON list (max 3) of extra buttons on every card, e.g. a community invite |
| `COMMUNITY_BUTTONS` | `[{"label":"Citlali News","url":"https://discord.gg/HyrVP9wRXu","emoji":"a:starward11:1439878792653832253"}]` | the bottom row of a **codes** card (`none` = no row). Youtube / Twitch / Redeem Page are not shown there — they belong to the livestream card |
| `COUNTDOWN_ESTIMATES` | on | `0` = never fill program / maintenance times from countdown sites |
| `PROGRAM_MEDIA` | on | `0` = never look the program announcement up on the official news page (the card then keeps whatever the run's own feed showed) |
| `BANNER_FEED` | on | `0` = never fill banner lineups from hub.json |
| `ENABLED_FEATURES` | `schedule,codes` | `schedule` · `codes` · `none` (paused / cold standby) |
| `GAMES` | all enabled | allow-list, e.g. `genshin,starrail` |
| `ENABLE_GAMES` | — | switch prepared games on, e.g. `hna` or `hna,ananta` |
| `DRY_RUN` | off | build and log only |
| `TEST_MODE` | off | cards get a 🧪 TEST label, the freshness/seed rules are skipped and the state is never saved (the monitor's test modes set it) |
| `BOOTSTRAP_POST` | off | first run posts current items instead of seeding |
| `EDIT_ON_UPDATE` | on | silent in-place edits when official info arrives |
| `POST_ON_MAINTENANCE_NOTICE` | on | if the program announcement was missed, post from the maintenance notice |
| `LOOKBACK_HOURS` | 72 | how far back official posts are considered |
| `CODES_MIN_SOURCES` | 2 | independent community sources needed for an unverified code |
| `CODES_MARK_EXPIRED` | on | strike through posted codes once every source lists them as expired |
| `SHOW_LEGEND` | on | the `STC — Subject to Change • TBA — To be Announced` footer |
| `X_ENABLED` / `NITTER_INSTANCES` | on / built-in fleet | X monitoring on/off, or a custom nitter list |
| `INSTANCE_NAME` / `INSTANCE_ROLE` / `PEER_STATE_URL` / `HEARTBEAT_MINUTES` / `FAILOVER_AFTER_MINUTES` | alpha / primary / — / 1440 / 90 | [fail-over](#-redundancy-fallback-chains--two-instance-fail-over) |
| `AUTO_MERGE_DEPENDABOT` | — | `yes` = merge green Dependabot PRs automatically (dev repo only; [docs/DEPENDABOT.md](docs/DEPENDABOT.md)) |

### `config/games.json` (per game)

Every setting lives in one place per game: name, color, X accounts, HoYoLAB game ID, launcher
ID, detection patterns, YouTube/Twitch buttons, code sources, redeem URL/hint, and card style
(`title`, `header`, `maintenance_heading`, `maintenance_style` = `start_end|range`,
`maintenance_first`, `four_star_summary`, `banners_url`, `show_banners`).

Templates can use `{game}`, `{version}`, `{program}` and `{version_name}`. For example, set
`"title": "{game} Version {version} \"{version_name}\" {program}"` to include the version's
subtitle.

### `config/overrides.json`: human-verified corrections

Overrides win over every automatic source, and the posted card is edited on the next run
(silently). Use them for banners that are only shown as images, leaks you've confirmed, or
times you want pinned:

```json
{
  "starrail": {
    "4.7": {
      "banners": { "phase1": ["Name"], "phase1_4": ["A", "B", "C"], "phase2": ["Name"], "reruns": ["X", "Y"] },
      "maint_start_ts": "2026-11-09T06:00:00+08:00"
    }
  }
}
```

Edit it straight on GitHub (✏️ button). An empty list shows `TBA`.

---

## 🎯 How it decides to post (accuracy rules)

1. **Detect**: official posts are read from HoYoLAB, official X accounts and the Kuro site, then
   filtered by per-game patterns (`special program`, `special broadcast`, maintenance /
   pre-install notices, banner notices, explicit "redemption code" posts). Posts that aren't
   announcements are ignored: recaps, replays, "has ended", merch.
2. **Extract, from official text only**:
   - **Program time** comes from the post's datetime with an explicit offset: `UTC+8`,
     `UTC-4`, `GMT+8`. `(server time)` is never trusted, because it differs per region.
     Missing years are inferred from the post date (`December 19 at 19:30 (UTC+8)`).
   - **Version**: `Version 4.6` / `Ver.4.6` / `V4.6`. Genshin tweets that only say "the new
     version" get the number from the matching HoYoLAB post, or from the official launcher's
     live version + 0.1.
   - **Maintenance**: pre-install, start, and end (end comes from an explicit end time, a range
     like `04:00 - 11:00 (UTC+8)`, or "estimated to take 5 hours"). Compensation deadlines and
     event end dates are never mistaken for maintenance.
   - **Banners**: only quoted names that directly follow "5-star character" / "S-Rank Agent" /
     "5-star Resonator" (and the 4★ equivalents) in official banner notices. Weapons never
     match.
   - **4★ characters are TBA unless certain.** The names are shown only when the official
     notice lists exactly the expected number of rate-up 4★ (GI 3 · HSR 3 · ZZZ 2 · WW 3), every
     name looks like a real name, and no official source disagrees. Otherwise the card shows
     `4 Star Characters: TBA` and the job summary says why. Once two official posts disagree,
     that phase stays TBA until you confirm the names in `config/overrides.json`.
3. **Merge with provenance.** Priority is *overrides > official notice > official tweet >
   launcher signal > countdown estimate > learned pre-install fallback > banner feed*.
4. **Unknown values are TBA, and banners always carry (STC).** Countdown and learned pre-install
   values are explicitly labelled estimated; neither can overwrite an official value.
5. **Post once** per game + version (`state/state.json`), then **edit silently** when data
   changes. If a moderator deleted the original Discord message, a `404 Unknown Message` causes
   one fresh post whose new message id is adopted; every other edit failure remains an error and
   never reposts. Announcements that are already stale (the program aired more than 36 h ago with
   no pending maintenance) are recorded, not posted.

**Verified against real posts.** The parsers reproduce the exact timestamps of your reference
cards from the official posts:
- GI 7.1 program: `1789214400`
- GI 7.1 pre-install / maintenance start: `1789959600` / `1790114400` (43 h)
- HSR 4.6 pre-install / maintenance: `1790229600` / `1790546400` → `1790564400` (88 h)
- ZZZ 3.2 pre-install: `1788753600` (42 h before maintenance)
- WW 3.7 pre-install / broadcast: `1790560800` / `1789815600` (42 h before maintenance)

**Code gate.** A code is posted when **any one** of these is true:
1. it comes from an **official** source: the HoYoLAB livestream module, or an official X /
   HoYoLAB post that explicitly lists redemption codes;
2. a **redeem-validator** (hoyo-codes.seria.moe or Hum-Bao, which both try every code on a real
   account) reports it working, and no validator reports it expired;
3. at least `CODES_MIN_SOURCES` (default **2**) *independent* community sources list it as
   active **and no source lists it as expired**.
   - Open Gacha Codes and ennead count as one source, because they share a backend.
   - PromoGacha copies seria and the wikis, so it counts as whichever of those it copied.
   - The other independent sources are fandom and wuthering.gg.

**Expiry dates come first.** If a source gives an explicit *valid until* date and that date
has passed, the code is expired, no matter who else still lists it. This matters because:
- wiki editors often leave 24-hour livestream codes under *Active* for days;
- aggregators never delete anything.

A posted code whose date passes is struck through on the card silently.

Anything else waits as *pending* for up to 14 days and is posted the moment a second source
confirms it. The job summary lists those codes with the reason (`only fandom`). It counts the
already-expired ones in one line (`🧊 HSR: 12 code(s) ignored — already expired`) instead of
listing each. Glued-together codes, placeholders and unmapped reward icons are filtered out
before the gate.

---

## 🕹 Manual controls

**Actions → Game-Express Monitor → Run workflow.** One input decides everything: **`mode`**.

| `mode` | What it is |
|---|---|
| `live` *(default)* | **the real monitor.** cron-job.org triggers exactly this — it sends no inputs at all. It fetches the official sources, posts a card when something new matches, edits it silently when official info arrives, and commits the state. Nothing new → it posts nothing |
| `test` | **check it with real data.** Every test fetches the live sources and posts what they really returned, labelled 🧪 TEST — so a wrong link, a wrong picture or a wrong timestamp is visible *before* a real announcement goes out |

#### `mode = live`

| Input | Effect |
|---|---|
| `only` | everything / only `schedule` announcements / only `codes` |
| `game` | one game key |
| `repost` | post a version card again as a **new** message, e.g. `starrail:4.6`. Only versions the monitor has already seen in an official post work, so an unannounced `genshin:7.2` can't be reposted yet. The summary says so, and lists the tracked versions |

Nothing is ever posted twice: each card is remembered in `state/state.json` by its key **and** by
a hash of its payload, so a re-run can neither re-post nor rewrite an unchanged card. Code sources
are fetched once per run and shared between games (`CodeSources` cache), and the fetcher caps
concurrent requests, so a run costs a handful of HTTP calls.

#### `mode = test`

| `test` | What you get — all real, all labelled 🧪 TEST, state never saved |
|---|---|
| `webhooks` | one small green "✅ connected" card per webhook, listing which game/feature cards that channel receives. Checks all 6 per-game codes secrets |
| `codes` | the **real codes that are on the live sources right now**, posted to each game's own codes channel. Games that are not out yet (HNA, ANANTA) have no real code to fetch, so they get example codes |
| `schedule` | the **real schedule card** for the version that is out now: the announcement's own link and key art, the livestream date/time, the maintenance timestamps and the banners — exactly what a live run would post |
| `all` | webhooks → codes → schedule |

`game` narrows any of them to one game; `ping` (off by default) adds your role ping.

> A test posts to the **real** channels and never writes the state — so the live run still posts
> the real thing later. Delete the test cards when you are done with them.

**CLI** (local runs and debugging): `python -m gamexpress <command>`

| Command | What it does |
|---|---|
| `run` | one pass (what GitHub Actions uses) |
| `check-webhooks [--kind …] [--game …]` | one "connected" card per unique webhook (no ping) |
| `test-card [--kind …] [--game …] [--ping] [--unlaunched]` | post the sample cards, labelled 🧪 TEST (no ping unless `--ping`). `--unlaunched` keeps only the games that are not out yet, which have nothing real to fetch |
| `preview` | writes `previews/index.html` (a Discord-like preview of every card) + the JSON for [Discohook](https://discohook.app) |
| `validate` | prints the resolved routing (which secret feeds which channel), pings and emojis, and checks every sample card against Discord's limits |

Flags: `--dry-run --only --game --repost --kind --ping --out`.

---

## 🛡 Redundancy: fallback chains + two-instance fail-over

**Layer 1: every data point has a fallback chain inside every run.**

| Data | Chain |
|---|---|
| HoYoverse news | official HoYoLAB API → c3kay JSON-Feed mirror |
| X timelines | 15-instance nitter fleet (first **two** working instances are merged, so a stale-but-200 mirror can't hide a tweet) |
| Tweet details | FxTwitter → vxTwitter → RSS body |
| Codes | up to 8 sources per game (validators, APIs, wikis, official posts), fetched in parallel, with the gate above |
| Version / pre-install | HoYoPlay `getGameBranches` / Kuro launcher index |

A dead source is logged, shown in the job summary, and skipped. Sources are fetched in
parallel (max 12 connections, per-request timeouts), so a run takes seconds even when several
hosts are down. If every announcement source of a game is down, the summary says so, and the
next run re-reads the last `LOOKBACK_HOURS` (72 h), so nothing is missed.

**Layer 2: two instances with automatic fail-over and shared dedup.**

| Instance | Variables |
|---|---|
| **alpha** (primary) | `INSTANCE_NAME=alpha`, `HEARTBEAT_MINUTES=60`, `PEER_STATE_URL=<bravo's raw state URL>` |
| **bravo** (standby) | `INSTANCE_NAME=bravo`, `INSTANCE_ROLE=standby`, `PEER_STATE_URL=https://raw.githubusercontent.com/<owner>/<alpha-repo>/main/state/state.json`, `FAILOVER_AFTER_MINUTES=150` |

- Use the **same webhook secrets** in both instances.
- Every run, each instance imports the other's posted keys. The standby stays passive while the
  primary's heartbeat is fresh, and starts posting automatically when it goes stale.
- The standby never fails over faster than 2.5× the primary's heartbeat interval, and never when
  the peer state can't be read. So a misconfiguration can't cause double posts.
- When alpha comes back it imports bravo's posts and edits bravo's cards (same webhook), so
  nothing is posted twice.

**One repo or several.** One repo can be the code home and production at once: CI tests every
PR before you merge, and merging deploys it. You can also follow the News-Express convention of
a development repo plus instance repos (alpha / bravo). Only a development copy that must never
post gets the variable `ENABLED_FEATURES=none`. The monitor is then skipped even if something
triggers it, while a manual `test` run of the monitor still works there. Never set it on the
repo that posts.

**Scheduler: cron-job.org, one job per instance repo.** GitHub's native `schedule:` is
disabled (commented out) in `monitor.yml`, exactly like News-Express, because two schedulers
on one repo race each other. cron-job.org calls the `workflow_dispatch` API every 10 minutes.
The concurrency queue plus the fresh branch checkout make an overlapping trigger safe. Setup,
the classic token, fail-over timing and the response codes: **[docs/SCHEDULER.md](docs/SCHEDULER.md)**.

---

---

## 🧪 Testing & previews

**➡️ Full checklist: [docs/TESTING.md](docs/TESTING.md)**. It covers what to click, what you
should see in Discord, and how to tell that the whole thing is working.

- **Monitor test bench** (`monitor.yml`, `mode` = `test`): webhooks, real codes, or the real
  schedule card — every test fetches the live sources, so what you see in Discord is what a live
  run would post (see [Manual controls](#-manual-controls)).
- **CI** (`.github/workflows/ci.yml`) runs on every PR and every push to `main`: install,
  compile, `validate`, `tests/test_smoke.py`, and a preview render. That's **67 offline tests
  with no network and no secrets**:
  - real official posts captured on 2026-09-25, which must reproduce your reference cards'
    timestamps;
  - golden JSON for the 4 converted cards (`tests/fixtures/golden/`);
  - button nesting, component and character limits, ping and emoji resolution, TEST labels;
  - all code parsers (real API captures), the code gate (families, validators, expired veto),
    the expired-code edit, pending and bootstrap logic, the 4★ TBA rules, silent edits,
    stale-post suppression, fail-over, per-game codes webhooks, prepared-game switches,
    parallel fetching, and the workflow files themselves (no native schedule, secrets wired).
- `UPDATE_GOLDEN=1 python tests/test_smoke.py` refreshes the golden cards after an
  **intentional** design change.
- `python -m gamexpress preview` → open `previews/index.html` to see every card, or paste a JSON
  file into Discohook.

---

## 🚨 Troubleshooting

| Symptom | Fix |
|---|---|
| Nothing posted for days | Normal. It posts only on official announcements and new codes. Check the job summary: *"nothing new"* plus source health. |
| First Monitor runs posted nothing | Correct: the first run per game is a **silent seed** (`🌱 … seeded silently`). Use `repost = starrail:4.6` to post a current card now |
| `repost` posted nothing | the version isn't tracked yet (not announced, or never seen). The summary says `version … isn't tracked` and lists the ones that are |
| `400 … components` in the log | a card broke a Discord limit. `python -m gamexpress validate` pinpoints it (CI also catches this) |
| No ping | `PING_ROLE_ID` unset or `none`; the role must be mentionable, or the webhook needs *Mention @everyone, @here and All Roles* |
| Emojis show as `:name:` | the webhook's channel needs *Use External Emojis* for `@everyone`, or change `EMOJI_*` |
| Card not edited after an override | the card must have been posted by a webhook with the same URL (the fingerprint is stored) |
| `every code source was unreachable` | a transient outage. The next run catches up because codes are compared against the state, not the time |
| X silent | nitter fleet down. The HoYoLAB / Kuro sources still work; add `NITTER_RSS_TOKEN` or a fresh `NITTER_INSTANCES` |
| cron-job.org shows **401** | the token expired or is wrong: make a new classic token (`repo` scope) and paste it into the job's header ([docs/SCHEDULER.md](docs/SCHEDULER.md)) |
| cron-job.org shows **404** | wrong owner / repo / file name in the URL, or the token can't see the repo |
| cron-job.org shows **422** | the branch in the body doesn't exist (`{"ref":"main"}`) or the workflow has no `workflow_dispatch` |
| Runs are skipped (grey) | the variable `ENABLED_FEATURES=none` is set. That's only for a development copy; remove it on the repo that posts |
| A code isn't posted | it's *pending*: only one source has it, or a source lists it as expired. The job summary shows the reason. Official / redeem-validated codes post immediately |
| `4 Star Characters: TBA` although the names are known | the official text didn't list exactly the expected number, or two posts disagreed. Put the names in `config/overrides.json`; the card is edited on the next run |
| `webhooks` test shows ✗ / `not a webhook URL` | the secret holds something else (a channel link, extra spaces). Copy the webhook URL again |
| Workflow stopped after 60 days | GitHub pauses idle repos. The daily heartbeat commit prevents this; re-enable it in the Actions tab if it happened |

---

## 📡 Data sources

The full verified endpoint list, with why each one was chosen or rejected, is in
**[docs/SOURCES.md](docs/SOURCES.md)**. It covers HoYoLAB `getNewsList` / `getPostFull` /
livestream `material`, c3kay feeds, HoYoPlay `getGameBranches`, the Kuro site and launcher JSON,
hoyo-codes.seria.moe, Hum-Bao/hoyoverse-codes, Open Gacha Codes (api.ennead.cc), wuthering.gg,
the fandom MediaWiki API, PromoGacha `codes.json`, FxTwitter / vxTwitter, and the nitter fleet.

---

## 📚 Community databases & resources

<details><summary><b>Solaris — Wuthering Waves</b></summary>

- **Discover Wuthering Waves Lore**: https://wutheringwaves.notion.site/
- **The Shorekeeper (Team Management)**: https://cyzed.com/
- **Wuthering Waves Database**: https://encore.moe/
- **Guides or Builds, Tier Lists, Detailed Information**: https://www.prydwen.gg/wuthering-waves/ · [game8.co/games/Wuthering-Waves](https://game8.co/games/Wuthering-Waves/archives/457465)
- **Character Builds, Tier List, Echoes, Guides, Weapons and their Background Information**: https://wutheringlab.com/
- **Provides Detailed Data to Help Players Navigate the Game World more Efficiently**: https://wuthering.gg/map
- **Built by Wuthering Waves' experienced theorycrafting & speedrunning community**: https://tethys.gg/
- **Official Wiki**: https://wutheringwaves.fandom.com/
- **More**: https://wuthering.gg/ · https://arabwuwa.com/ · https://wuwa.akademiya.app/en · https://wuwatracker.com/characters · https://wuwacompanion.com/en/database · https://www.prydwen.gg/wuthering-waves/characters
</details>

<details><summary><b>New Eridu — Zenless Zone Zero</b></summary>

- **Database for everything in Zenless Zone Zero**: https://zzz.gachabase.net/?lang=en&branch=beta
- **Guides or Builds, Tier Lists, Detailed Information**: https://www.prydwen.gg/zenless/ · https://www.icy-veins.com/zenless-zone-zero/ · https://www.icy-veins.com/zenless-zone-zero/tier-list · [game8.co/games/Zenless-Zone-Zero](https://game8.co/games/Zenless-Zone-Zero/archives/522597)
- **Information Related to Zenless Zone Zero**: https://zzz.honeyhunterworld.com/?lang=EN · https://zzz-run-archive.onrender.com/
- **Official Wiki**: https://zenless-zone-zero.fandom.com/
</details>

<details><summary><b>Genshin Impact</b></summary>

https://ambr.top/en · https://lunaris.moe/ · https://e-teyvat.vxnus.xyz/ · https://gensh.honeyhunterworld.com/?lang=EN · https://www.icy-veins.com/genshin-impact/ · https://www.icy-veins.com/genshin-impact/tier-list · https://www.prydwen.gg/genshin-impact/characters
</details>

<details><summary><b>Honkai: Star Rail</b></summary>

https://hsr.gachabase.net/ · https://www.huroka.com/ · https://hsr.yatta.top/en · https://starrail.honeyhunterworld.com/?lang=EN · https://www.icy-veins.com/honkai-star-rail/ · https://www.prydwen.gg/star-rail/characters/ · https://sk.theherta.com/ · [game8.co/games/Honkai-Star-Rail](https://game8.co/games/Honkai-Star-Rail/archives/404256)
</details>

<details><summary><b>All HoYoverse + Wuthering Waves · more databases</b></summary>

- **The definitive database for all HoYoverse and Wuthering Waves (Release, Beta & CBT)**: https://gachabase.net/ · https://nanoka.cc/
- **More Database**: https://endfield.teamstardust.org/ · https://silver.teamstardust.org/ · https://www.ntegame.com/ · https://irminsul.gg/ · https://perlica.moe/ · https://endfieldtools.dev/ · https://anantacodex.com/
</details>

---

## 📄 Privacy · Terms · Credits

- **[Privacy Policy](PRIVACY_POLICY.md)** and **[Terms of Service](TERMS_OF_SERVICE.md)**.
- **Not affiliated** with HoYoverse, Kuro Games, NetEase or Discord. Game names and assets belong
  to their owners.
- **Credits**:
  - [seriaati/hoyo-codes](https://github.com/seriaati/hoyo-codes) and [hoyo-update-notifier](https://github.com/seriaati/hoyo-update-notifier) (the verified code API and the Sophon/launcher endpoints)
  - [c3kay/hoyolab-rss-feeds](https://github.com/c3kay/hoyolab-rss-feeds)
  - [RSSHub](https://github.com/DIYgod/RSSHub) (Kuro endpoints)
  - [gripcrip-blip/codehub · PromoGacha](https://github.com/gripcrip-blip/codehub)
  - [DuolaD/HoYo_Versioncatcher](https://github.com/DuolaD/HoYo_Versioncatcher)
  - [api.ennead.cc](https://api.ennead.cc/) and [Open Gacha Codes](https://github.com/torikushiii/OpenGachaCodes)
  - [Hum-Bao/hoyoverse-codes](https://github.com/Hum-Bao/hoyoverse-codes) (redeem-validated code lists)
  - [wuthering.gg](https://wuthering.gg/codes)
  - [FxTwitter](https://github.com/FixTweet/FxTwitter)
  - the nitter instance operators
  - [News-Express](https://github.com/uesu/News-Express)

---

## 🗒 Changelog

### 1.6.0 — 2026-09-27 · the pre-install lead is learned, not hardcoded

- A missing pre-install timestamp is derived as **hours before maintenance start**, which carries
  both the day and clock time without brittle weekday arithmetic. Cold-start values reproduce the
  real 2026 notices (GI 43 h · HSR 88 h · ZZZ 42 h · WW 42 h).
- Every real pre-install/maintenance pair records its lead. Later versions use the per-game median;
  malformed values and leads above 14 days are ignored, and even-sized histories average their
  middle pair.
- Derived pre-install times remain labelled estimated and are never fed back into the history, so
  the fallback cannot validate itself. Official notices discovered through HoYoLAB, X/Nitter or
  Kuro replace the estimate automatically.

### 1.5.0 — 2026-09-27 · deleted Discord cards heal themselves

- Discord `404 / 10008 Unknown Message` on a schedule-card edit now means the original message was
  deleted: the current card is posted once and the replacement message id is adopted. The next run
  edits that replacement instead of retrying a dead id forever.
- Only a 404 takes that recovery path. A 400, 5xx or exhausted retry remains an error and never
  reposts; if the recovery post itself fails, the stale id is retained so the next run retries.
- The same production run established HSR 4.6's real pre-install lead as 88 hours (Thu 14:00 to
  Mon 06:00 UTC+8), now represented by the learned-hours model above rather than a weekday rule.

### 1.3.0 — 2026-09-27 · card cleanup, banner lineups from a live feed, and proof the X lookup generalises

- **Card cleanup:** removed redundant X button (the announcement tweet is already linked in the card title) while preserving buttons for non-X sources (HoYoLAB, official news page). Removed `🖼️ key art: …` and `Source: …` footer lines so the card footer stays clean.
- **Banner lineups from live feed (`hub.json`):** rate-up 5★ characters are filled from `ertezy.github.io/Gacha-hub-info/hub.json` (rebuilt hourly, CC BY-SA 3.0) and phase-split around the version's release / maintenance timestamp. Sits at priority 5 (lowest in the monitor), only fills empty phases, refuses stale payloads (>14d), and can be disabled with `BANNER_FEED=0`.
- **Verified X announcement recall across eras:** verified 7/7 positive match across all captured program announcements spanning multiple wording families (GI Luna II, ZZZ 2.5, HSR 4.5/4.6, GI 7.1, ZZZ 3.2, WW 3.7).

### 1.7.0 — 2026-09-26 · the schedule card links the real announcement, and the Discord bot is gone

- The announcement lookup now uses versions from the current run as well as state, so first runs and test runs recover the archived announcement and key art.
- Event, update-details and maintenance-notice titles are excluded from program matching; livestream URLs in `/live/`, `/shorts/` and `/embed/` now produce real thumbnails.
- Duplicate HoYoLAB artwork and alternate media renditions are collapsed, and incomplete banner lists no longer blank otherwise valid names.
- Wuthering Waves can use configured RSS/Atom mirrors, and tweet data falls back from fxtwitter to fixupx to vxtwitter.
- Program lookups run concurrently with each other and with countdown estimates.
- The Discord bot and all 24/7 self-hosting commands and files were removed; GitHub Actions is the only runtime.

### 1.6.0 — 2026-09-26 · two modes, and the tests use real data
- **The dialog is now just `mode` + what that mode needs.** `live` = the real monitor (`only`,
  `game`, `repost`). `test` = `webhooks` / `codes` / `schedule` / `all`. Gone: the `dry_run`
  input and the `probe` debug input (and the `gamexpress probe` command behind it).
- **The tests no longer post sample cards — they post what the sources really returned.** The
  `codes` test posts the real codes currently on the live sources to each game's own codes
  channel; the `schedule` test posts the real schedule card (the announcement's own link and key
  art, the livestream date/time, the maintenance timestamps and the banners). A sample card could
  hide a broken source; these cannot.
- Games that are not out yet (HNA, ANANTA) have no real code to fetch, so the codes test gives
  them example codes — `test-card --kind codes --unlaunched`.
- **A test posts to the real channels, labelled 🧪 TEST, and never writes the state**, so the
  live run still posts the real thing later. `DISCORD_WEBHOOK_TEST` is no longer used (the
  private-test-channel mode is gone); the secret can be deleted.
- The live run is unchanged apart from losing `dry_run`: post what is new, edit silently when
  official info arrives, commit the state, and never post twice (state keys + payload hashes).

### 1.5.0 — 2026-09-26 · the dispatch form says which of the two things you are doing
- **`mode` = `live` or `test`.** Still one workflow, but the Run-workflow dialog now opens with
  the choice between the real monitor and the manual test bench, every input is labelled for the
  mode it belongs to, and the steps are named `LIVE · …` / `TEST · …` so the log says which ran.
- **`only` is now the single "simplify" switch** for both modes (`all` / `schedule` / `codes`);
  the duplicate `kind` input is gone.
- **New live input `probe`** — debug ONE real schedule post, e.g. `starrail:4.6`. It prints what
  the lookback window saw, what is stored for that version, the program lookup tab by tab with
  the air time parsed out of the article text, **every image it found (ranked, with why the
  winner won)** and the card it would build. Read-only: nothing is posted or saved. Also on the
  CLI as `python -m gamexpress probe starrail:4.6`.
- The lookup is now one function (`runner.find_program`) shared by the monitor and the probe, so
  the debug report can never drift from what a real run does.
- cron-job.org is unaffected: it sends no inputs, so `mode` defaults to `live` and the pass is
  exactly what it was.

### 1.4.0 — 2026-09-25 · the test bench moves into the Monitor
- **`test.yml` is gone; the manual test bench is now a mode of the Monitor workflow.** In
  *Actions → Game-Express Monitor → Run workflow*, pick `test` = `webhooks` / `sample-cards` /
  `live-dry-run` / `live-test-channel` / `offline-tests` / `full`. New inputs `kind` and `ping`
  came across unchanged.
- A test run is still safe everywhere: the **Run monitor** step and the **Commit state** step are
  both gated on `inputs.test == ''`, so a test never posts to the real channels and never writes
  `state/state.json` — and it still works on a dev repo with `ENABLED_FEATURES=none`
  (the job's `if` is now `vars.ENABLED_FEATURES != 'none' || inputs.test != ''`).
- cron-job.org keeps calling the same `monitor.yml` dispatch with no `test` input, so scheduled
  behaviour is byte-identical to before.

### 1.3.0 — 2026-09-25 · the schedule card shows the real announcement
- **The card now shows the program announcement, not whichever post the run happened to see.**
  HSR 4.6 linked to the *Update and Maintenance Notice* and showed its Pompom cover, because the
  Special Program preview (article 46691962) was 11 days older and had fallen out of the lookback
  window. A new lookup finds the announcement on the **official news page** (or the HoYoLAB news
  list, paged back past the window) and uses its link, its key art and its air time.
- **A maintenance notice's own cover is no longer used as the card image** — it is not the
  program's key art. The notice stays as a Source link when nothing better is known.
- **Images are upgraded to the biggest rendition each source serves** (`gamexpress/media.py`):
  tweet photos get `?name=orig` (X serves `small` by default), nitter `/pic/` proxies are
  rewritten to `pbs.twimg.com`, and YouTube thumbnails go `hqdefault` → `maxresdefault`
  (1280×720). A URL that already asks for a size is left exactly as the source gave it.
- The air time from a recovered announcement is an official time, so a program that has already
  aired is still shown (`<t:…:F> or <t:…:R>` — "5 days ago"), and it never overwrites a time an
  official post already gave.
- `PROGRAM_MEDIA=0` switches the lookup off. `docs/SOURCES.md` lists the news pages and what each
  one is verified to serve.

### 1.2.0 — 2026-09-25 · card buttons and maintenance estimates
- **Codes card buttons cleaned up.** `Redeem Page`, `Youtube` and `Twitch` are gone from codes
  cards — the livestream buttons belong to the Special Program / Special Broadcast card, and
  `Redeem Page` was redundant next to one prefilled Redeem button per code.
- **New community row** after a separator: `Citlali News` → `https://discord.gg/HyrVP9wRXu` with
  the animated `starward11` emoji (`COMMUNITY_BUTTONS`, max 3, `none` = off).
- **Maintenance times are estimated when the official notice hasn't arrived yet** (countdown
  sites, lowest priority, marked with a 🕒 line on the card, replaced automatically).
- Time parsing understands named zones such as `8:00 AM EDT`.
- Docs: `docs/SOURCES.md` lists every countdown source; **60 offline tests**.

### 1.1.1 — 2026-09-25 · fixes from the first live runs
- **Expired codes are no longer mistaken for new ones.** The first live dry run showed 3 HSR +
  3 WW livestream codes that had expired on 2026-09-21 but were still listed as active. Wikis
  keep them under *Active*, PromoGacha never deletes, and Open Gacha Codes lags. The bot now:
  - reads *valid until* dates on the fandom wikis (all three table formats, with time zones);
  - treats a passed date as expired, whatever other sources say;
  - strikes the code through on already-posted cards.
- **More accurate wiki parsing:**
  - Genshin rows that hold several codes are split;
  - Star Rail rows with nested `{{Item List}}` keep their dates;
  - the stray `TERMINOLOGYINFOBOX` "code" is gone.
- **PromoGacha counts as its upstream.** It counts as seria or fandom, and its stale copies are
  ignored.
- **Cleaner rewards.** Open Gacha Codes `Unknown reward (hash)` entries and duplicate reward
  lines are dropped.
- **Shorter summaries.** Expired codes are counted in one line; codes waiting for a second
  source are listed in one line.
- **Schedule cards:**
  - no more misleading `Special Program: TBA` once the update is known (the program already
    aired);
  - `repost` now explains when a version isn't tracked (e.g. an unannounced `genshin:7.2`);
  - the first run notes versions that are already out.
- **Dependabot:**
  - auto-merge moved into `ci.yml` as a job that runs after the tests (the separate
    `workflow_run` workflow never fired);
  - no custom labels (they had to exist first);
  - only PRs for versions outside the allowed range.
- **One repo can be production.** The docs no longer tell you to set `ENABLED_FEATURES=none` on
  this repo; that variable is only for a development copy. [SCHEDULER.md](docs/SCHEDULER.md)
  explains private repos: 2,000 free Actions minutes a month means a 30-minute schedule.
- **Tests are hermetic again.** The bot test read the repo's `state/state.json`, so it failed
  (on `main` too) as soon as the Monitor had committed real codes. It now uses its own state.
- **Test bench:** `offline-tests` installs discord.py + PyYAML so no check is skipped.
  `x.yuuki.sh` (403 on GitHub runners) moved to the end of the nitter fleet. **55 offline
  tests.**

### 1.1.0 — 2026-09-25 · per-game code channels, cron-job.org, Test workflow
- **Per-game codes webhooks** for all 6 games (`DISCORD_WEBHOOK_CODES_GENSHIN` · `_STARRAIL` ·
  `_HNA` · `_ZZZ` · `_WUWA` · `_ANANTA`, short names like `_HSR` / `_WW` work too).
- **Scheduler = cron-job.org.** GitHub's native `schedule:` is disabled in `monitor.yml`
  (News-Express style); every secret is wired explicitly; actions bumped to v7.
- **Game-Express Test workflow**: webhook check, labelled sample cards, live dry run, live cards
  to a test channel, offline tests. It never commits and pings nobody by default.
- **4★ = TBA when unsure**: exact expected count, name plausibility, and a sticky
  disagreement rule.
- **Codes**: new sources (Hum-Bao validator, Open Gacha Codes, wuthering.gg for Wuthering
  Waves), expired-code detection (an expired flag vetoes a post; posted codes are struck
  through silently), shared-backend sources counted once, and the reason for every pending
  code in the summary.
- **Speed**: all sources are fetched in parallel with a connection cap and per-request
  timeouts; the nitter fleet is probed in batches; run time is shown in the summary.
- **Prepared games**: `ENABLE_GAMES` variable; ANANTA switches itself on at its announced
  launch (2027-01-15); HNA gets the HoYoLAB livestream-code module (gid 9).
- `check-webhooks` command, `test-card --ping` (no ping by default, 🧪 TEST label),
  `validate` shows which secret feeds which channel, and `preview` writes an HTML page.
- Optional Dependabot auto-merge (off unless `AUTO_MERGE_DEPENDABOT=yes`), grouped weekly
  Dependabot PRs. New docs: SCHEDULER, TESTING, DEPENDABOT. 47 offline tests.

### 1.0.0 — 2026-09-25 · initial release
- **Schedule announcements** for GI / HSR / ZZZ / WW, with HNA and ANANTA prepared.
  - Pattern-triggered and posted once per version, then silent in-place edits as official
    maintenance, pre-install, banner and override data arrives.
  - The 4 reference cards were converted to Components V2 with the buttons nested inside the
    container.
- **Code poster** with an official / verified / 2-source accuracy gate, a silent first-run seed,
  pending codes, and per-code prefilled Redeem buttons.
- **Sources**: HoYoLAB official API + c3kay fallback, official X via a 15-instance nitter fleet +
  FxTwitter/vxTwitter, the Kuro site, HoYoPlay `getGameBranches`, the Kuro launcher, seria,
  ennead, the fandom API, and PromoGacha.
- **Operations**:
  - a queued workflow with a fresh branch checkout, and state commits even after partial failure;
  - all secrets and variables are auto-exposed, so per-game overrides need no YAML edits;
  - two-instance auto fail-over with shared dedup;
  - `test-card`, `preview` and `validate` commands, and a GitHub job summary with source health.
- **Bot mode** (`/codes`, `/schedule`, `/status`) plus free-hosting guides and deploy files.
- **33 offline tests** (real-post fixtures + golden cards), run as the CI gate.
