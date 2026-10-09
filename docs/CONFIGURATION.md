# Configuration reference

Every switch Game-Express reads, in one place: repository **secrets**, repository **variables**,
and the two JSON files in [`config/`](../config).

The workflow passes **every** secret and variable to the app as JSON (`GE_SECRETS_JSON` /
`GE_VARS_JSON`), so any name on this page works **without editing any YAML**. Add it in
*Settings → Secrets and variables → Actions* and the next run picks it up.

`python -m gamexpress validate` — step 1 of every workflow run — prints the resolved result:
which secret feeds which channel, which ping applies, which emojis were parsed.

- [Secrets](#secrets)
- [Variables](#variables)
- [`config/games.json`](#configgamesjson)
- [`config/overrides.json`](#configoverridesjson)
- [Local `.env`](#local-env)

---

## Secrets

Sensitive — *Settings → Secrets and variables → Actions → **Secrets***.

| Name | Purpose |
|---|---|
| `DISCORD_WEBHOOK_SCHEDULE` | schedule cards |
| `DISCORD_WEBHOOK_CODES_GENSHIN` · `_STARRAIL` · `_HNA` · `_ZZZ` · `_WUWA` · `_ANANTA` | code cards, one channel per game |
| `DISCORD_WEBHOOK_CODES` | optional: codes of any game without its own secret |
| `DISCORD_WEBHOOK_URL` | optional catch-all fallback |
| `DISCORD_WEBHOOK_SCHEDULE_<GAME>` | optional per-game schedule channel, e.g. `DISCORD_WEBHOOK_SCHEDULE_WUWA` |
| `DISCORD_WEBHOOK_<FEATURE>_MIRROR_<GAME>` | optional — **copies** the card to a second channel as well, e.g. `DISCORD_WEBHOOK_SCHEDULE_MIRROR_ZZZ` (see *Fan-out* below) |
| `NITTER_RSS_TOKEN` | optional — the e-mailed token for the one token-gated nitter mirror, `https://nitter.miningtcup.me/` (the same secret News-Express uses). Empty only skips that mirror |

**Webhook routing**, most specific first:

```
DISCORD_WEBHOOK_<FEATURE>_<GAME>  →  DISCORD_WEBHOOK_<FEATURE>  →  DISCORD_WEBHOOK_URL
```

`<GAME>` is the game key **or** its short name: `GENSHIN`/`GI`, `STARRAIL`/`HSR`, `ZZZ`,
`WUWA`/`WW`, `HNA`/`NEXUSANIMA`, `ANANTA`. The same URL may be used for several secrets (for
example, one codes channel for every game). For a forum or thread channel, append
`?thread_id=<id>` to the webhook URL.

### Fan-out — the same card in two channels

The routing chain above is **first match wins**, so `DISCORD_WEBHOOK_SCHEDULE_ZZZ` *moves* the
ZZZ card out of the shared schedule channel. To have it in **both** places, add a mirror
instead:

```
DISCORD_WEBHOOK_<FEATURE>_MIRROR_<GAME>  →  DISCORD_WEBHOOK_<FEATURE>_MIRROR
```

| | |
|---|---|
| Example | `DISCORD_WEBHOOK_SCHEDULE_MIRROR_ZZZ` → `#schedule` **and** `#zzz-news` |
| `<GAME>` | same keys and short names as above (`GI`, `HSR`, `WW`, `NEXUSANIMA`, …) |
| Unset | no copy. Deliberately **no** `DISCORD_WEBHOOK_URL` fallback, so filling in the catch-all one day can never start double-posting every card into it |
| Same URL as the primary | detected and skipped — one card, not two |
| `FORCE_WEBHOOK` | switches the fan-out off entirely, so a test run can't reach a real game channel |

Both copies are **sent in the same pass from the same data**, then edited together while the
primary card remains editable (up to the 45-day freeze) — as TBA banners fill in and estimated
maintenance times are replaced by the official notice, the copy is corrected too. This is a
fan-out, not a Discord "follow": nothing lags, and nothing drifts. The card body is identical in
both channels; the ping is the only difference (see below).

The copy is a convenience, so it never blocks the real card. A broken game-channel webhook is
reported in the run summary (`⚠️ … copy failed`) and retried next run; it is never a run error,
and the schedule channel is served either way.

Adding the secret **backfills eligible cards** on the next run, not just future ones. A version
gets a brand-new copy only while `program_settled()` is false: the gate settles at 36 h past a
known program time or 12 h past a known maintenance start. The card must also be before
`CARD_FREEZE_D` (45 days past maintenance). An existing copy can still be edited while its
primary card is maintained, but a settled version never gets a new copy automatically; use
`repost = <game>:<version>` when you want one deliberately.

Removing the secret forgets the copy's message id. Re-adding it restores copies only for eligible
versions; it does not bypass the settled-version guard.

**Only the primary card pings.** The role is mentioned once, in the schedule channel; the copy
is built with no ping at all, so one announcement never notifies the same member twice. The
copy carries no mention *text* either, so it does not show a dead blue `@role` pill that
notifies nobody. Edits never ping in either channel.

---

## Variables

Not secret, one-click switches — *Settings → Secrets and variables → Actions → **Variables***.

### Pings

| Name | Default | Meaning |
|---|---|---|
| `PING_ROLE_ID` | *(unset)* | role ID(s) to ping. **Unset = no ping.** Comma-separate for several; `everyone` / `here` allowed |
| `PING_SCHEDULE` / `PING_CODES` | inherit | per-feature override; `none` = explicitly no ping |
| `PING_<FEATURE>_<GAME>` | inherit | e.g. `PING_SCHEDULE_GENSHIN=111…` |
| `NO_PING` | off | `1` = never ping, whatever the other ping variables say. `monitor.yml` sets it per run: `1` for a test started without ⑥, `0` otherwise (never blank — a blank value would be re-filled from a stale repo variable by the `GE_VARS_JSON` catch-all) |

**Where the mention appears.** Inside the card, not above it — on the legend line of a schedule
card (`-# STC — Subject to Change • TBA — To be Announced @role`) and on the count line of a
codes card (`-# 2 new codes • detected <t:…:R> @role`). Nothing floats above the container. If
`SHOW_LEGEND=0` removes the legend, the mention gets a small-text line of its own rather than
being dropped. A codes drop split across several messages mentions the role on **part 1 only**.

### Card appearance

| Name | Default | Meaning |
|---|---|---|
| `EMOJI_YOUTUBE` / `EMOJI_TWITCH` | the animated defaults | format `a:name:id` (animated), `name:id`, a unicode emoji, or `none` |
| `EMOJI_SOURCE` / `EMOJI_REDEEM` | *none* / 🎁 | emojis for the Source and Redeem buttons. These four are the only emoji settings — `EMOJI_BANNERS` was accepted but never rendered, and was removed. |
| `EXTRA_BUTTONS` | — | JSON list (max 3) of extra buttons on every card, e.g. a community invite |
| `COMMUNITY_BUTTONS` | `[{"label":"Citlali News","url":"https://discord.gg/HyrVP9wRXu","emoji":"a:starward11:1439878792653832253"}]` | the bottom row of a **codes** card (`none` = no row). Youtube / Twitch / Redeem Page are not shown there — they belong to the livestream card |
| `SHOW_LEGEND` | on | the `STC — Subject to Change • TBA — To be Announced` footer |

### What is monitored

| Name | Default | Meaning |
|---|---|---|
| `ENABLED_FEATURES` | `schedule,codes` | `schedule` · `codes` · `none` (paused / cold standby) |
| `GAMES` | all enabled | allow-list, e.g. `genshin,starrail` |
| `ENABLE_GAMES` | — | switch prepared games on, e.g. `hna` or `hna,ananta` |
| `X_ENABLED` / `NITTER_INSTANCES` | on / built-in fleet | X monitoring on/off, or a custom nitter list |
| `LOOKBACK_HOURS` | 72 | how far back official posts are considered |

### Accuracy and estimates

| Name | Default | Meaning |
|---|---|---|
| `COUNTDOWN_ESTIMATES` | on | `0` = never fill program / maintenance times from countdown sites |
| `PROGRAM_MEDIA` | on | `0` = never look the program announcement up — neither the official news page nor the tweet already cached in `config/program_announcements.json` (the card then keeps whatever the run's own feed showed) |
| `BANNER_FEED` | on | `0` = never fill banner lineups from `hub.json` |
| `BANNER_SEARCH` | on | `0` = never look banner notices up by title (HoYoLAB search, Kuro's article menu) — see [BANNER_DATABASE.md](BANNER_DATABASE.md#finding-the-notice-by-title) |
| `GACHA_WIKI` | on | `0` = never fill banner line-ups from the game wikis ([BANNER_DATABASE.md](BANNER_DATABASE.md)) |
| `CODES_MIN_SOURCES` | 2 | independent community sources needed for an unverified code |
| `CODES_MARK_EXPIRED` | on | strike through posted codes once every source lists them as expired |
| `EDIT_ON_UPDATE` | on | silent in-place edits when official info arrives |
| `POST_ON_MAINTENANCE_NOTICE` | on | a maintenance notice may also post the card — only for a version whose announcement is already known |

### Run behaviour

| Name | Default | Meaning |
|---|---|---|
| `DRY_RUN` | off | build and log only |
| `TEST_MODE` | off | cards get a 🧪 TEST label, the freshness/seed rules are skipped — a test run renders a settled version's card as a **new** message and never edits a live card, its copy, or publishes a replacement for an id that stopped resolving — and the state is never saved (the monitor's test modes set it) |
| `BOOTSTRAP_POST` | off | first run posts current items instead of seeding |
| `FORCE_WEBHOOK` | — | send **every** card to this one webhook URL. Testing only; it wins over all routing above |
| `STATE_PATH` | `state/state.json` | where the dedup state is read and written |
| `HTTP_TIMEOUT` | 20 | per-request timeout, seconds |
| `LOG_LEVEL` | `INFO` | Python log level for the run |

### Fail-over and automation

| Name | Default | Meaning |
|---|---|---|
| `INSTANCE_NAME` / `INSTANCE_ROLE` / `PEER_STATE_URL` / `HEARTBEAT_MINUTES` / `FAILOVER_AFTER_MINUTES` | alpha / primary / — / 1440 / 90 | two-instance fail-over, see [README → Reliability](../README.md#-reliability) |
| `AUTO_MERGE_DEPENDABOT` | — | `yes` = merge green Dependabot PRs automatically (dev repo only; [DEPENDABOT.md](DEPENDABOT.md)) |
| `AUTO_MERGE_PYTHON_BUMP` | — | `all` = merge a green, automated Python-version-bump PR automatically. `yes` deliberately does **not** merge here, so it is safe to set repo-wide ([PYTHON_VERSION.md](PYTHON_VERSION.md)) |

---

## `config/games.json`

Every setting lives in one place per game: name, color, X accounts, HoYoLAB game ID, launcher
ID, detection patterns, YouTube/Twitch buttons, code sources, redeem URL/hint, release cadence,
and card style (`title`, `maintenance_heading`, `maintenance_style` =
`start_end|range`, `maintenance_first`, `four_star_summary`, `four_star_label`, `banners_url`,
`show_banners`).

`four_star_count` is the number of rate-up 4★ characters one banner phase has (GI/HSR/WW 3,
ZZZ 2). Any list of another length is shown as TBA instead of published — that applies to an
official notice the reader is unsure about *and* to a wiki line-up
([BANNER_DATABASE.md](BANNER_DATABASE.md)). `four_star_label` renames the per-phase 4★ line;
ZZZ sets it to `4 Star Characters (Default)` because its A-Rank rate-ups are
player-customisable.

Two flags are deliberately separate:

| Flag | Means |
|---|---|
| `enabled` | **do we watch it.** `false` keeps a game prepared but silent |
| `released` | **is the game out.** A pre-release game is still monitored, it just has no real codes to fetch, so the test bench checks its card with sample data (`test-card --kind codes --unlaunched`) |

`auto_enable_on: "YYYY-MM-DD"` lets a prepared game switch itself on at launch.

Card text templates can use `{game}`, `{version}`, `{program}` and `{version_name}`. For example,
set `"title": "{game} Version {version} \"{version_name}\" {program}"` to include the version's
subtitle.

---

## `config/overrides.json`

Human-verified corrections. Overrides win over **every** automatic source, and the posted card is
edited (silently) on the next run. Use them for banners that are only shown as images, leaks
you've confirmed, or times you want pinned:

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

## Local `.env`

For running the CLI on your own machine, copy [`.env.example`](../.env.example) to `.env` and fill
it in — it carries the same names as this page, with the defaults inline. `.env` is gitignored.

```bash
cp .env.example .env
python -m gamexpress validate
```
