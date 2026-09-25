# Game-Express — Version Schedule Announcements + Code Poster → Discord

[![CI](https://github.com/uesu/Game-Express/actions/workflows/ci.yml/badge.svg)](https://github.com/uesu/Game-Express/actions/workflows/ci.yml)

Automated **version-schedule announcements** and a **redemption-code poster** for
**Genshin Impact · Honkai: Star Rail · Zenless Zone Zero · Wuthering Waves**, with
**Honkai: Nexus Anima** and **ANANTA (NetEase)** already prepared (switched off until they launch).

Everything is posted as **Discord Components V2 cards**, with the **buttons inside the card**,
the announcement image, **Discord timestamps** (every reader sees their own timezone),
**STC / TBA** markers and an **optional role ping**. It runs free on **GitHub Actions** (public
repos get unlimited minutes), triggered every 10 minutes by **[cron-job.org](https://cron-job.org)**,
with no server and no bot token. An optional **Discord bot** mode (slash commands) can run on a
free host.

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
- [Discord bot + free hosting](#-discord-bot--free-hosting)
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
│ [ Youtube ] [ Twitch ] [ HoYoLAB / X Post ]                    ← buttons INSIDE the card
│ -# STC — Subject to Change • TBA — To be Announced • Source: HoYoLAB
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
│ [ Redeem Page ] [ Youtube ] [ Twitch ]
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

1. **Get the repo.** Production runs in your public instance repos (alpha / bravo, see
   [Redundancy](#-redundancy-fallback-chains--two-instance-fail-over)); this repo is the
   development home. Public repos get unlimited free Actions minutes.
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
   | `DISCORD_WEBHOOK_TEST` | *optional*: a private test channel for the Test workflow |
   | `NITTER_RSS_TOKEN` | *optional*: the same one as News-Express |

   The same URL may be used for several secrets (for example, one codes channel for every game).
4. **Add variables** (not secret) in *… → Variables*:
   - `PING_ROLE_ID` = `1296268365593186426` (**leave it unset for no ping**, or `NO_PING=1`)
   - the emojis already default to your animated ones
5. **Test.** *Actions → **Game-Express Test** → Run workflow*:
   `webhooks` → `sample-cards` → `live-dry-run`. Each mode is explained in
   **[docs/TESTING.md](docs/TESTING.md)**. Nothing is committed and nobody is pinged by default.
6. **Go live with cron-job.org.** Create one cron-job.org job per instance repo that calls the
   `workflow_dispatch` API every 10 minutes, using a GitHub **classic token** with the `repo`
   scope. Step by step: **[docs/SCHEDULER.md](docs/SCHEDULER.md)**. GitHub's own `schedule:` is
   disabled in `monitor.yml`, so the two schedulers can never race.

**First real run = silent seed.** Current announcements and every existing code are recorded
without posting, so deploying never spams old items. To post what's current on the first run,
set the variable `BOOTSTRAP_POST=1` once.

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
| `DISCORD_WEBHOOK_TEST` | optional: private channel for the Test workflow's `live-test-channel` mode |
| `NITTER_RSS_TOKEN` | optional token for the token-gated nitter instance |
| `DISCORD_BOT_TOKEN` | bot mode only |

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
| `ENABLED_FEATURES` | `schedule,codes` | `schedule` · `codes` · `none` (paused / cold standby) |
| `GAMES` | all enabled | allow-list, e.g. `genshin,starrail` |
| `ENABLE_GAMES` | — | switch prepared games on, e.g. `hna` or `hna,ananta` |
| `DRY_RUN` | off | build and log only |
| `TEST_MODE` | off | cards get a 🧪 TEST label, the freshness/seed rules are skipped and the state is never saved (the Test workflow sets it) |
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
   launcher signal*.
4. **Unknown values are TBA, and banners always carry (STC). Nothing is estimated or guessed.**
5. **Post once** per game + version (`state/state.json`), then **edit silently** when data
   changes. Announcements that are already stale (the program aired more than 36 h ago with no
   pending maintenance) are recorded, not posted.

**Verified against real posts.** The parsers reproduce the exact timestamps of your reference
cards from the official posts:
- GI 7.1 program: `1789214400`
- GI 7.1 maintenance: `1790114400` → `1790132400`
- HSR 4.6 pre-install: `1790229600`
- HSR 4.6 maintenance: `1790546400` → `1790564400`
- WW 3.7 broadcast: `1789815600`

**Code gate.** A code is posted when **any one** of these is true:
1. it comes from an **official** source: the HoYoLAB livestream module, or an official X /
   HoYoLAB post that explicitly lists redemption codes;
2. a **redeem-validator** (hoyo-codes.seria.moe or Hum-Bao, which both try every code on a real
   account) reports it working, and no validator reports it expired;
3. at least `CODES_MIN_SOURCES` (default **2**) *independent* community sources list it as
   active **and no source lists it as expired**. Open Gacha Codes and ennead count as one
   source because they share a backend; the others are fandom, PromoGacha and wuthering.gg.

Anything else waits as *pending* for up to 14 days and is posted the moment a second source
confirms it. The job summary shows why each code is waiting (`only ogc`,
`listed as expired by seria`, …). Glued-together codes, placeholders and codes with lowercase
fan text are filtered out before the gate.

---

## 🕹 Manual controls

**Actions → Game-Express Test → Run workflow** (safe on production; never commits):

| `test` | What happens |
|---|---|
| `webhooks` | one small green "✅ connected" card per webhook, listing which game/feature cards that channel receives. Checks all 6 per-game codes secrets |
| `sample-cards` | your 4 reference schedule cards + one codes card per game, labelled 🧪 TEST, sent to the real channels |
| `live-dry-run` | a full real run: every source fetched, cards built and validated, shown in the log and summary. Nothing posted or saved |
| `live-test-channel` | like `live-dry-run`, but posts the real current cards (labelled 🧪 TEST) to the `DISCORD_WEBHOOK_TEST` channel |
| `offline-tests` | the CI test suite |
| `full` | offline-tests → webhooks → sample-cards → live-dry-run |

Inputs `kind` (all / schedule / codes), `game` and `ping` (off by default) narrow it down.

**Actions → Game-Express Monitor → Run workflow** (the production run; cron-job.org calls it):

| Input | Effect |
|---|---|
| `dry_run` | real run, logs the card JSON, never posts or commits |
| `only` | `schedule` or `codes` |
| `game` | one game key |
| `repost` | force a **new** post of a tracked version, e.g. `genshin:7.2` |

**CLI** (local, VPS or bot host): `python -m gamexpress <command>`

| Command | What it does |
|---|---|
| `run` | one pass (what GitHub Actions uses) |
| `loop` | run forever every `LOOP_MINUTES` |
| `bot` | slash commands + loop |
| `check-webhooks [--kind …] [--game …]` | one "connected" card per unique webhook (no ping) |
| `test-card [--kind …] [--game …] [--ping]` | post the sample cards, labelled 🧪 TEST (no ping unless `--ping`) |
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
- The [bot mode](#-discord-bot--free-hosting) can be the standby too: it answers `/codes` and
  `/schedule` from the imported state and takes over if Actions stops.

**Development repo vs. instance repos.** Following the News-Express convention, this repo is
the development and PR home, and production runs in the instance repos (alpha / bravo). In the
development repo, set the variable `ENABLED_FEATURES=none`: the monitor is then skipped even if
something triggers it, while the **Game-Express Test** workflow still works.

**Scheduler: cron-job.org, one job per instance repo.** GitHub's native `schedule:` is
disabled (commented out) in `monitor.yml`, exactly like News-Express, because two schedulers
on one repo race each other. cron-job.org calls the `workflow_dispatch` API every 10 minutes.
The concurrency queue plus the fresh branch checkout make an overlapping trigger safe. Setup,
the classic token, fail-over timing and the response codes: **[docs/SCHEDULER.md](docs/SCHEDULER.md)**.

---

## 🤖 Discord bot + free hosting

The GitHub Actions setup needs **no bot and no hosting**. For a 24/7 process with slash commands
(`/codes`, `/schedule`, `/status`), run:

```bash
pip install -r requirements-bot.txt
python -m gamexpress bot        # needs DISCORD_BOT_TOKEN
```

**➡️ Step-by-step guides in [docs/HOSTING.md](docs/HOSTING.md)** cover creating the bot, then
deploying to Oracle Cloud Always Free, Koyeb, Render, Railway, or Docker anywhere. `Dockerfile`,
`deploy/docker-compose.yml`, `deploy/game-express.service` (systemd), `render.yaml` and
`Procfile` are included: drop in the repo and it's live.

> Run **one poster per set of channels**. Either use Actions, or use the bot with
> `INSTANCE_ROLE=standby` + `PEER_STATE_URL` (recommended), or set `ENABLED_FEATURES=none` on
> one of them.

---

## 🧪 Testing & previews

**➡️ Full checklist: [docs/TESTING.md](docs/TESTING.md)**. It covers what to click, what you
should see in Discord, and how to tell that the whole thing is working.

- **Game-Express Test workflow** (`.github/workflows/test.yml`): webhooks, sample cards, live
  dry run, live cards to a test channel, or everything at once (see
  [Manual controls](#-manual-controls)).
- **CI** (`.github/workflows/ci.yml`) runs on every PR and every push to `main`: install,
  compile, `validate`, `tests/test_smoke.py`, and a preview render. That's **47 offline tests
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
| `400 … components` in the log | a card broke a Discord limit. `python -m gamexpress validate` pinpoints it (CI also catches this) |
| No ping | `PING_ROLE_ID` unset or `none`; the role must be mentionable, or the webhook needs *Mention @everyone, @here and All Roles* |
| Emojis show as `:name:` | the webhook's channel needs *Use External Emojis* for `@everyone`, or change `EMOJI_*` |
| Card not edited after an override | the card must have been posted by a webhook with the same URL (the fingerprint is stored) |
| `every code source was unreachable` | a transient outage. The next run catches up because codes are compared against the state, not the time |
| X silent | nitter fleet down. The HoYoLAB / Kuro sources still work; add `NITTER_RSS_TOKEN` or a fresh `NITTER_INSTANCES` |
| cron-job.org shows **401** | the token expired or is wrong: make a new classic token (`repo` scope) and paste it into the job's header ([docs/SCHEDULER.md](docs/SCHEDULER.md)) |
| cron-job.org shows **404** | wrong owner / repo / file name in the URL, or the token can't see the repo |
| cron-job.org shows **422** | the branch in the body doesn't exist (`{"ref":"main"}`) or the workflow has no `workflow_dispatch` |
| Runs are skipped (grey) | the variable `ENABLED_FEATURES=none` is set: correct on the dev repo, remove it on instance repos |
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

- **[Privacy Policy](PRIVACY_POLICY.md)** and **[Terms of Service](TERMS_OF_SERVICE.md)**. You can
  also use these as the URLs in the Discord Developer Portal for bot mode.
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
  Dependabot PRs. New docs: SCHEDULER, TESTING, DEPENDABOT. **47 offline tests.**

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
