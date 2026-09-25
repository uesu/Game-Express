# Game-Express — Version Schedule Announcements + Code Poster → Discord

[![CI](https://github.com/uesu/Game-Express/actions/workflows/ci.yml/badge.svg)](https://github.com/uesu/Game-Express/actions/workflows/ci.yml)

Automated **version-schedule announcements** and a **redemption-code poster** for
**Genshin Impact · Honkai: Star Rail · Zenless Zone Zero · Wuthering Waves**, with
**Honkai: Nexus Anima** and **ANANTA (NetEase)** already prepared (switched off until they launch).

Everything is posted as **Discord Components V2 cards**, with the **buttons inside the card**,
the announcement image, **Discord timestamps** (every reader sees their own timezone),
**STC / TBA** markers and an **optional role ping**. It runs free on **GitHub Actions** with no
server and no bot token. An optional **Discord bot** mode (slash commands) can run on a free
host.

> Same architecture and lessons as [News-Express](https://github.com/uesu/News-Express):
> fallback chains for every source, dedup state committed to the repo, a queued (never
> cancelled) workflow, offline golden tests as the CI gate, and a two-instance fail-over.

---

## Contents
- [What it posts](#-what-it-posts)
- [Supported games](#-supported-games)
- [Setup — 5 steps (GitHub Actions)](#-setup--5-steps-github-actions)
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

### 2. Redemption code card: posted once per code

`🎁 Genshin Impact Redemption Codes`: each code with its rewards, plus a **Redeem button per
code that opens the official page with the code already filled in** (GI / HSR / ZZZ). Wuthering
Waves shows the in-game redemption hint instead. Codes are only posted after passing the
accuracy gate (see [below](#-how-it-decides-to-post-accuracy-rules)).

---

## 🎮 Supported games

| Game | Status | Schedule sources | Code sources |
|---|---|---|---|
| Genshin Impact | ✅ on | HoYoLAB API (gid 2) → c3kay mirror · X `@GenshinImpact` · HoYoPlay launcher | HoYoLAB livestream module · seria (verified) · ennead · fandom · PromoGacha · official posts |
| Honkai: Star Rail | ✅ on | HoYoLAB API (gid 6) → c3kay · X `@honkaistarrail` · HoYoPlay | same set (`hkrpg`) |
| Zenless Zone Zero | ✅ on | HoYoLAB API (gid 8) → c3kay · X `@ZZZ_EN` · HoYoPlay | same set (`nap`) |
| Wuthering Waves | ✅ on | X `@Wuthering_Waves` · Kuro official site · Kuro launcher | official X posts · fandom · PromoGacha |
| Honkai: Nexus Anima | 💤 prepared | HoYoLAB API (gid 9) · X `@HonkaiNA` | X (add more at launch) |
| ANANTA (NetEase) | 💤 prepared (launches 2027‑01‑15) | X `@Ananta_EN` | X (add more at launch) |

To turn a prepared game on, set `"enabled": true` in `config/games.json`. No code change is
needed. ANANTA is not a character gacha, so its card hides the banner section.

---

## 🚀 Setup — 5 steps (GitHub Actions)

1. **Get the repo.** Use this repo, or create your instance repos from it (see
   [Redundancy](#-redundancy-fallback-chains--two-instance-fail-over)).
2. **Create webhooks.** In Discord: *Channel → Edit Channel → Integrations → Webhooks → New
   Webhook → Copy URL*. Make one for the schedule channel and one for the codes channel (one
   channel for both works too).
3. **Add secrets.** Go to *Settings → Secrets and variables → Actions → Secrets*:
   - `DISCORD_WEBHOOK_SCHEDULE`
   - `DISCORD_WEBHOOK_CODES`
   - optional: `NITTER_RSS_TOKEN` (the same one as News-Express)
4. **Add variables** (optional, and not secret). Go to *… → Variables*:
   - `PING_ROLE_ID` = `1296268365593186426` (**leave it unset for no ping**)
   - the emojis are already set to your animated ones by default
5. **Test, then go live.** Open *Actions → Game-Express Monitor → Run workflow*:
   - `test_card = all` posts your 4 reference cards plus sample code cards so you can check the
     look.
   - `dry_run = true` does a full real run without posting.
   - After that, the 10-minute schedule is already active.

**First real run = silent seed.** Current announcements and every existing code are recorded
without posting, so deploying never spams old items. To post what's current on the first run,
set the variable `BOOTSTRAP_POST=1` once.

---

## ⚙️ Configuration reference

### Secrets (sensitive)
| Name | Purpose |
|---|---|
| `DISCORD_WEBHOOK_SCHEDULE` | schedule cards |
| `DISCORD_WEBHOOK_CODES` | code cards |
| `DISCORD_WEBHOOK_URL` | optional fallback for both |
| `DISCORD_WEBHOOK_<FEATURE>_<GAME>` | optional per-game channel, e.g. `DISCORD_WEBHOOK_CODES_WUWA` |
| `NITTER_RSS_TOKEN` | optional token for the token-gated nitter instance |
| `DISCORD_BOT_TOKEN` | bot mode only |

Webhook routing: `DISCORD_WEBHOOK_<FEATURE>_<GAME>` → `DISCORD_WEBHOOK_<FEATURE>` → `DISCORD_WEBHOOK_URL`.
For a forum or thread channel, append `?thread_id=<id>` to the webhook URL.

### Variables (not secret)

These are one-click switches. The workflow passes **every** secret and variable to the app, so
any name below works without editing YAML.

| Name | Default | Meaning |
|---|---|---|
| `PING_ROLE_ID` | *(unset)* | role ID(s) to ping. **Unset = no ping.** Comma-separate for several; `everyone` / `here` allowed |
| `PING_SCHEDULE` / `PING_CODES` | inherit | per-feature override; `none` = explicitly no ping |
| `PING_<FEATURE>_<GAME>` | inherit | e.g. `PING_SCHEDULE_GENSHIN=111…` |
| `EMOJI_YOUTUBE` / `EMOJI_TWITCH` | your animated emojis | format `a:name:id` (animated), `name:id`, a unicode emoji, or `none` |
| `EMOJI_SOURCE` / `EMOJI_REDEEM` | — / 🎁 | emojis for the Source and Redeem buttons |
| `EXTRA_BUTTONS` | — | JSON list (max 3) of extra buttons on every card, e.g. a community invite |
| `ENABLED_FEATURES` | `schedule,codes` | `schedule` · `codes` · `none` (paused / cold standby) |
| `GAMES` | all enabled | allow-list, e.g. `genshin,starrail` |
| `DRY_RUN` | off | build and log only |
| `BOOTSTRAP_POST` | off | first run posts current items instead of seeding |
| `EDIT_ON_UPDATE` | on | silent in-place edits when official info arrives |
| `POST_ON_MAINTENANCE_NOTICE` | on | if the program announcement was missed, post from the maintenance notice |
| `LOOKBACK_HOURS` | 72 | how far back official posts are considered |
| `CODES_MIN_SOURCES` | 2 | community sources needed for an unverified code |
| `SHOW_LEGEND` | on | the `STC — Subject to Change • TBA — To be Announced` footer |
| `X_ENABLED` / `NITTER_INSTANCES` | on / built-in fleet | X monitoring on/off, or a custom nitter list |
| `INSTANCE_NAME` / `INSTANCE_ROLE` / `PEER_STATE_URL` / `HEARTBEAT_MINUTES` / `FAILOVER_AFTER_MINUTES` | alpha / primary / — / 1440 / 90 | [fail-over](#-redundancy-fallback-chains--two-instance-fail-over) |

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
- it comes from an **official** source: the HoYoLAB livestream module, or an official X /
  HoYoLAB post that explicitly lists redemption codes;
- **hoyo-codes.seria.moe** reports it redeem-validated (`OK`);
- at least `CODES_MIN_SOURCES` (default **2**) independent community sources agree (ennead /
  fandom / PromoGacha).

Single-source codes wait as *pending* for up to 14 days and are posted the moment a second
source confirms them.

---

## 🕹 Manual controls

**Actions → Game-Express Monitor → Run workflow:**

| Input | Effect |
|---|---|
| `dry_run` | real run, logs the card JSON, never posts or commits |
| `only` | `schedule` or `codes` |
| `game` | one game key |
| `test_card` | post the **sample cards** (your 4 reference cards + code cards) to check the look |
| `repost` | force a **new** post of a tracked version, e.g. `genshin:7.2` |

**CLI** (local, VPS or bot host): `python -m gamexpress <command>`

| Command | What it does |
|---|---|
| `run` | one pass (what GitHub Actions uses) |
| `loop` | run forever every `LOOP_MINUTES` |
| `bot` | slash commands + loop |
| `test-card [--kind schedule\|codes]` | post the sample cards |
| `preview` | write the sample payload JSON to `previews/` for [Discohook](https://discohook.app) |
| `validate` | prints the resolved routing, pings and emojis, and checks every sample card against Discord's limits |

Flags: `--dry-run --only --game --repost`.

---

## 🛡 Redundancy: fallback chains + two-instance fail-over

**Layer 1: every data point has a fallback chain inside every run.**

| Data | Chain |
|---|---|
| HoYoverse news | official HoYoLAB API → c3kay JSON-Feed mirror |
| X timelines | 15-instance nitter fleet (first **two** working instances are merged, so a stale-but-200 mirror can't hide a tweet) |
| Tweet details | FxTwitter → vxTwitter → RSS body |
| Codes | up to 6 sources per game, with the gate above |
| Version / pre-install | HoYoPlay `getGameBranches` / Kuro launcher index |

A dead source is logged, shown in the job summary, and skipped.

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
development repo, set the variable `ENABLED_FEATURES=none` (or disable the workflow in the
Actions tab). Scheduled runs are then skipped entirely, while manual `test_card` / `dry_run`
runs still work.

**More punctual triggers.** GitHub can delay `schedule:` runs. Like News-Express, you can add a
free [cron-job.org](https://cron-job.org) job that calls the `workflow_dispatch` API every 10
minutes. The concurrency queue plus the fresh branch checkout make overlapping triggers safe.

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

- **CI** (`.github/workflows/ci.yml`) runs on every PR: install, compile, `validate`, then
  `tests/test_smoke.py`. That's **33 offline tests with no network and no secrets**:
  - real official posts captured on 2026-09-25, which must reproduce your reference cards'
    timestamps;
  - golden JSON for the 4 converted cards (`tests/fixtures/golden/`);
  - button nesting, component and character limits, ping and emoji resolution;
  - the code gate, pending and bootstrap logic, silent edits, stale-post suppression, fail-over,
    and a check that an identical re-run doesn't rewrite the state file.
- `UPDATE_GOLDEN=1 python tests/test_smoke.py` refreshes the golden cards after an
  **intentional** design change.
- `python -m gamexpress preview` writes the JSON to paste into Discohook.
- `python -m gamexpress test-card` posts the samples to your real channels.

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
| Schedule workflow stopped after 60 days | GitHub pauses idle repos. The daily heartbeat commit prevents this; re-enable it in the Actions tab if it happened |

---

## 📡 Data sources

The full verified endpoint list, with why each one was chosen or rejected, is in
**[docs/SOURCES.md](docs/SOURCES.md)**. It covers HoYoLAB `getNewsList` / `getPostFull` /
livestream `material`, c3kay feeds, HoYoPlay `getGameBranches`, the Kuro site and launcher JSON,
hoyo-codes.seria.moe, api.ennead.cc, the fandom MediaWiki API, PromoGacha `codes.json`,
FxTwitter / vxTwitter, and the nitter fleet.

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
  - [api.ennead.cc](https://api.ennead.cc/)
  - [FxTwitter](https://github.com/FixTweet/FxTwitter)
  - the nitter instance operators
  - [News-Express](https://github.com/uesu/News-Express)

---

## 🗒 Changelog

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
