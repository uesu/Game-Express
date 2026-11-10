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
| `NITTER_RSS_TOKEN` | optional — the e-mailed token for the token-gated nitter and redlib mirrors (`https://nitter.miningtcup.me/`, `https://redlib.miningtcup.me` — the same secret News-Express uses). Empty only skips those mirrors |
| `REDDIT_FEED_TOKEN` | optional — private RSS / JSON feed link or token from `old.reddit.com/prefs/feeds/`: accepts `https://old.reddit.com/.rss?feed=<40-char-key>&user=<your_username>`, `https://www.reddit.com/.rss?feed=<40-char-key>&user=<your_username>`, `https://old.reddit.com/.json?feed=<40-char-key>&user=<your_username>`, `https://www.reddit.com/.json?feed=<40-char-key>&user=<your_username>`, `https://reddit.com/.rss?feed=…`, `https://old.reddit.com/?feed=…`, or `<40-char-key>&user=<your_username>` interchangeably (same format as News-Express; drives `[0] www.reddit.com` → `[1] old.reddit.com` authenticated RSS failover + circuit-broken `.json` fallback) |

| `DISCORD_BOT_TOKEN` | optional — the Reddit **intake reader** bot token (secret). Read-only bot in your server with *View Channel* + *Read Message History* on the intake channel and the *Message Content Intent*. Pair with the Variables below |
| `INTAKE_CHANNEL_ID` | optional (Variable) — id of the private Discord channel the *Gaming Express* Devvit relay writes its post records to (the same channel News-Express reads). With `DISCORD_BOT_TOKEN` set, a healthy relay is the Reddit listing and the redlib/reddit.com fleet is not contacted for served targets |
| `INTAKE_READER` | optional (Variable) — `primary` (default) \| `shadow` (read and report, old chain decides) \| `off` (never read). Rollback switch |
| `INTAKE_STALE_SECONDS` | optional — default `1800`; a newest relay record older than this means *stale* → old chain |
| `INTAKE_LOOKBACK_SECONDS` | optional — default `21600`; how far back the channel is read each run (newest-first, ≤ 800 messages) |

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
notifies nobody. Edits never ping in either channel: every PATCH re-sends the card with the
**same** mention permissions it was posted with, so the mention keeps rendering — and keeping it
rendered is what keeps the role colouring the whole message — without notifying anyone, because
Discord never notifies on an edit.

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
| `EMOJI_TITLE` | `<:ananta1:1558340472525693018>` | the scroll on every game's card headline, after the title link. `none` leaves the headline bare. Custom emoji render as long as your server can reach them: **your own server's** emoji always work via the webhook, and so do emoji from servers a helper bot (Discohook, Embed Generator) bridges by sitting in both your server and the emoji server — animated ones too. An emoji from a random bot's own server (the original `ananta2`, now deleted) has no bridge and posts as the raw `<:name:id>` text |
| `EMOJI_YOUTUBE` / `EMOJI_TWITCH` | the animated defaults | format `a:name:id` (animated), `name:id`, a unicode emoji, or `none` |
| `EMOJI_SOURCE` / `EMOJI_REDEEM` | `<a:starwardcat:1564242587987087420>` / 🎁 | emojis for the schedule card's third button (`Watch` / `Source`) and the Redeem button. These five are the only emoji settings — `EMOJI_BANNERS` was accepted but never rendered, and was removed. |
| `EXTRA_BUTTONS` | — | JSON list (max 3) of extra buttons on every card, e.g. a community invite |
| `COMMUNITY_BUTTONS` | `[{"label":"Citlali News","url":"https://discord.gg/HyrVP9wRXu","emoji":"a:starward11:1439878792653832253"}]` | the bottom row of a **codes** card (`none` = no row). Youtube / Twitch / Redeem Page are not shown there — they belong to the livestream card |
| `SHOW_LEGEND` | on | the `STC — Subject to Change • TBA — To be Announced` footer |

### What is monitored

| Name | Default | Meaning |
|---|---|---|
| `ENABLED_FEATURES` | `schedule,codes` | `schedule` · `codes` · `news` (also requires `NEWS_ENABLED`) · `none` (paused / cold standby) |
| `GAMES` | all enabled | allow-list, e.g. `genshin,starrail` |
| `ENABLE_GAMES` | — | switch prepared games on, e.g. `hna` or `hna,ananta` |
| `X_ENABLED` / `NITTER_INSTANCES` | on / built-in fleet | X monitoring on/off, or a custom nitter list |
| `REDDIT_ENABLED` / `REDDIT_INSTANCES` / `REDDIT_PROXIES` | on / built-in fleets | official Reddit + community code corroboration on/off, custom Reddit/Redlib frontend list, or custom `Discordbot/2.0` rich-embed proxy chain |
| `LOOKBACK_HOURS` | 72 | how far back official posts are considered |

### Accuracy and estimates

| Name | Default | Meaning |
|---|---|---|
| `COUNTDOWN_ESTIMATES` | on | `0` = never fill program / maintenance times from countdown sites |
| `PROGRAM_MEDIA` | on | `0` = never look the program announcement up — neither the official news page nor the tweet already cached in `config/program_announcements.json` (the card then keeps whatever the run's own feed showed) |
| `BANNER_FEED` | on | `0` = never fill banner lineups from `hub.json` |
| `BANNER_CALENDAR` | on | `0` = never read the official game calendars (api.ennead.cc) for banner names — see [BANNER_DATABASE.md](BANNER_DATABASE.md) |
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
| `AUTO_MERGE_DEPENDABOT` | — | `yes` = merge eligible green package-only Dependabot PRs; workflow changes wait for review (dev repo only; [DEPENDABOT.md](DEPENDABOT.md)) |
| `AUTO_MERGE_PYTHON_BUMP` | — | Legacy/ignored: all Python update PRs require attended review/merge. |

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
([BANNER_DATABASE.md](BANNER_DATABASE.md)). `four_star_summary` (WW) adds the `※ 4 Star
Characters:` roster line above the phases — a signal, not a slot: it appears only while it names
a 4★ that no per-phase line shows yet, and hides once both phase lists are in or when the wiki
knows no 4★ at all (the per-phase lines already read `TBA`). `four_star_label` renames the per-phase 4★ line;
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


### Setup classification and manual-only selectors

`BUMP_PAT` is an Actions **Secret**, never a Variable. Create it separately in each
repository that installs `python_version_bump.yml`, with repository access and Contents,
Pull requests and Workflows write permissions appropriate to the token type. It publishes
validated PRs, not unattended merges. A runtime-only production repository without that
workflow does not need it. The cron-job.org dispatch token is a different credential.
GitHub supplies `GITHUB_TOKEN`, `GITHUB_SHA` and `GITHUB_STEP_SUMMARY` automatically;
do not create them as application settings.

`REPOST` is the environment equivalent of the manual workflow `repost` input. It requests
a deliberate new schedule card (for example `starrail:4.6`); leave it unset in routine
scheduled runs. It is not a news replay/backfill switch. Test/force/bootstrap selectors
are not routine setup requirements; leave their defaults unless deliberately testing.

## Official news (explicit opt-in; default off)

**GitHub setup:** use Secrets for webhooks/tokens and Variables for switches. The workflow
merges `GE_SECRETS_JSON` and `GE_VARS_JSON`; no YAML edit is required per setting. Use
`mode=live`, `only=all` for ordinary production with news opted in; the UI offers no
news-only selection. CLI `--only news --dry-run` is a selector, not an opt-in.
For migration, preserve the current state and intended feature switches; do not reset a
baseline or add a second scheduler. See [production setup](PROD-REPO-SETUP.md).

Set repository **variable** `NEWS_ENABLED=1` only after reviewing the source and
preview. `NEWS_ENABLED=0` (the default) makes no news requests and adds no news
state on installations that have never enabled it. Disabling an already enabled
installation writes one `paused` control marker; subsequent disabled runs do not
churn news state. A successful source read after re-enabling establishes a new
silent baseline. A selector such as `ONLY=news` / `--only news` cannot enable it;
`ENABLED_FEATURES=none`, `off`, `standby`, or `0` wins over the switch.
A schedule/code-only selector does not count as toggling news off.

| Variable | Default | Meaning |
|---|---|---|
| `NEWS_ENABLED` | `0` | Explicit news opt-in; independent of the existing schedule/code defaults |
| `NEWS_GROUP_LONG_STRIPS` | `0` | Opt-in measured grouping; failure keeps article order |
| `NEWS_REVEAL_PING` | `0` | Opt-in heuristic character-reveal mentions for official news; excludes identified video, deduplicates characters and same source publication minute |
| `PING_NEWS_REVEAL` | — | The only reveal role setting: one role list (comma/space separated) used for **all** games. No `PING_ROLE_ID`/`PING_NEWS` inheritance and no per-game variant |
| `NEWS_TIMESTAMPS` | `0` | Opt-in render-time `<t:EPOCH:…>` conversion for exact TZ-qualified news dates/times |
| `NEWS_MEDIA_HEAL` | `1` | Media heal: when Discord's create/edit response returns a gallery tile or thumbnail with a `proxy_url` but no dimensions/content type (the client shows "Image not found"), the message is re-read after `NEWS_MEDIA_HEAL_DELAY` and, only if that tile is still cold, re-sent identically once. Nothing is persisted; dry-run never edits |
| `NEWS_MEDIA_HEAL_DELAY` | `6` | Grace period in seconds (0–60) before the re-read; one wait per game and run, not per card |
| `NEWS_EXPAND_FULL` | `0` | Opt-in multi-page full articles beyond 2 pages (bounded at `NEWS_EXPAND_MAX_PAGES = 12`, `NEWS_EXPAND_MAX_CHARS = 120000`, `NEWS_EXPAND_MAX_MEDIA = 120`) |
| `NEWS_GAMES` | `genshin,starrail,zzz,wuwa,hna` | Canonical game keys; removing a game pauses its existing news state |

Each run attempts all discovered eligible unposted articles in publication order,
without a fixed article-count cap or ten-attempt game cap. A failed article remains
retryable and does not prevent other eligible articles from being attempted. This
is not unlimited crawling or guaranteed same-run delivery: source pagination,
48-hour freshness/future holds, silent baselines, state capacity, media validation,
partial-delivery safeguards, Discord retries and job timeouts remain. By default
(`NEWS_EXPAND_FULL=0`), an article is still delivered in full: anything inside the
two-message / 7,000-character envelope keeps that exact layout, and a longer article is
**smart fitted** across up to `NEWS_DEFAULT_MAX_PAGES = 4` messages rather than being
truncated. Setting `NEWS_EXPAND_FULL=1` lifts that ceiling up to an explicit
12-page / 120,000-character / 120-media cap before excerpt fallback.

Migration: `NEWS_MAX_POSTS_PER_RUN` is retired and ignored. Remove a leftover
repository variable or local environment entry; it cannot enable a cap.

Use repository **secrets**, never variables, for the five destinations:

| Secret | Channel |
|---|---|
| `DISCORD_WEBHOOK_NEWS_GENSHIN` | `gi-news` |
| `DISCORD_WEBHOOK_NEWS_STARRAIL` | `hsr-news` |
| `DISCORD_WEBHOOK_NEWS_HNA` | `hna-news` |
| `DISCORD_WEBHOOK_NEWS_ZZZ` | `zzz-news` |
| `DISCORD_WEBHOOK_NEWS_WUWA` | `wuwa-news` |

Existing short game aliases also work. No `DISCORD_WEBHOOK_NEWS`, catch-all,
`FORCE_WEBHOOK`, or mirror fallback is used for news. A missing destination skips
source requests and baseline creation for that game; a changed destination is
held for operator review, not silently reposted. The existing workflow already
imports repository variables/secrets via its JSON blobs: no workflow edit,
scheduler change, new token, dependency or state file is required.

Official news delivery is strictly independent of schedule extraction, schedule
mirrors (`DISCORD_WEBHOOK_SCHEDULE_MIRROR_<GAME>`), redemption codes, and started
announcements (`MAINTENANCE_ENABLED`): Special Program / broadcast previews and
preload / maintenance notices remain eligible for full official-article delivery on
`DISCORD_WEBHOOK_NEWS_<GAME>` even when also consumed by schedule or when a user
intentionally points a schedule mirror at the same channel. Previously persisted
legacy records marked `{"status": "posted", "excluded": "schedule"}` stay completed
in place so rollout never triggers a historical repost flood without explicit
authorization, and `prune_news` advances `floor` before evicting aged records.
Removing the retired per-run article-count cap (`NEWS_MAX_POSTS_PER_RUN`) applies
only to how many eligible articles a run processes — when `NEWS_EXPAND_FULL` is
absent or `0`, the per-article **7,000-character / maximum-two-page policy and
labelled-excerpt fallback** remain completely intact. News cards are silent, with
Read Post, Citlali News and Donate. ANANTA remains an inactive source slot (no
verified adapter); Wangyue is excluded.

News defaults to article-order layout; optional measured grouping is described
below. Follow the full-content paging/excerpt rules below: limits are shared by
all containers in each message, and buttons occur only in the final container
of the final message. Line-leading `●` and `•` become Markdown `- ` bullets.
Unknown publication times are omitted, not fabricated.
HoYoLAB attribution uses the actual nickname when present, otherwise the configured
game name. Descriptive text links are masked once; self-labelled URLs stay bare;
button/media URL fields stay raw. Quill heading boundaries and compact bullet lists
are preserved. Unpadded `※`/`✦` get a following space; only consecutive `※` notes
receive added blank-line separation. A continuous media run is not split simply
at eight body units. Optional measured grouping is implemented below; slicing,
cropping, resizing or image removal remain forbidden.

Direct images/GIFs/videos included in the payload get a bounded GET/status/magic-byte
preflight. A failure refreshes the same official full article once; another failure
holds delivery for retry with an operational warning. No manual filename patches,
query stripping or screenshot substitutes. Preflight does not prove full downloads,
Discord fetching, codecs or playback. Grouping adds only the optional variable
documented below; no upload/proxy service is added.


A first valid discovery silently baselines at the run's time: no historical
flood. Later discoveries admit publication times after that floor within 48 hours.
Failed full-body fetches are retried while eligible; successful later articles do
not advance over those holes, and all discovered eligible articles are attempted in
publication order on each run. Confirmed message sends save progress atomically
in the existing `state/state.json`; retries resume after confirmed message IDs,
including legacy partial articles that age outside the discovery window. Legacy
partial signatures that differ under this layout are held for manual review, not
replayed or automatically reset.
A paused/re-enabled feature rebaselines fresh discovery, while retaining partial
progress to resume on subsequent runs. A source outage cannot establish a baseline.

Completed entries retain up to 30 days and share a 500-entry/game admission bound
with partial entries. Safe capacity cleanup removes only completed entries older
than 48 hours; age cleanup removes completed entries older than 30 days. Cleanup
advances a publication floor, preventing deleted dedup keys from resurrecting.
Partial entries are not evicted. If safe space cannot be made, admission defers
with a warning instead of deleting active protection. Retention is not an archive
or an unlimited outage-recovery promise. Preserve state; do not reset production
state to test or enable news.

Discord acceptance followed by a crash before saving/pushing state, ambiguous
network acknowledgements, or independent concurrent instances can still duplicate
messages. Peer merge imports compatible completed/partial delivery progress; it
does not provide a distributed transaction. Existing workflow serialization and
per-instance production states remain essential.


### Selecting two games and choosing channel names

Set `NEWS_ENABLED=1` and `NEWS_GAMES=genshin,wuwa` to select only those two
news adapters; leave the existing schedule/code game filters unchanged unless
intentionally restricting those features too. Unselected games make no news
source requests or deliveries. Supply the two corresponding news webhook secrets.
`gi-news`, `hsr-news`, `hna-news`, `zzz-news` and `wuwa-news` are suggested names,
not channel-name checks: each webhook can target any operator-chosen Discord
channel, and several games may share a destination if explicitly configured.
Dedicated secret names distinguish routing purposes, not mandatory channel names.

HoYoLAB's Official **Info**, **Events**, and **Notices** are all read; this is not
an Info-only feed. Ordinary service/payment notices, official giveaways, character
introductions, event details, Special Program previews, and preload/maintenance notices
all remain eligible for full official-article delivery on `DISCORD_WEBHOOK_NEWS_<GAME>`,
independent of schedule extraction or schedule mirrors. Existing legacy state records
already marked `"status": "posted"` stay completed without historical backfill.
Event start/end dates and "In Progress"/"Already Ended" badges are not new
publication times: existing old events are not reposted when enabled.


### Optional news-description timestamps (default off)

`NEWS_TIMESTAMPS=0` (default) bypasses the timestamp scanner completely (`0` parser
invocations), leaving rendered text byte-identical and making zero network calls.

Setting `NEWS_TIMESTAMPS=1` enables render-only conversion (`gamexpress/news_timestamps.py`)
after source-text normalization and immediately before pagination/sizing across the five
supported news games (`genshin`, `starrail`, `hna`, `zzz`, `wuwa`):

- **Timezone rules:** bare `UTC` and `GMT` resolve to `+00:00`, explicit source offsets
  (`UTC+8`, `UTC-4`, `(UTC+05:30)`, supported unambiguous abbreviations, etc.) always win,
  and `server time` uses the approved `UTC+8` fallback for news descriptions only
  (`gamexpress/timeparse.py` for schedule extraction remains untouched). Malformed or
  ambiguous timezone suffixes (`UTC+99`, `(CST)`, etc.) never partially match bare `UTC`,
  and timezone-less times stay untouched unless a shared trailing timezone qualifies both
  ends of a valid non-inverted range.
- **Missing years & rollover:** explicit years in source text are always authoritative.
  Yearless dates require `item.published_ts > 0` and resolve strictly to the unique
  calendar year within `±180` days (`YEARLESS_MAX_DELTA_DAYS = 180`) of `item.published_ts`
  — keeping recent past dates in `pub.year` (e.g. June 1 on an October 21 post stays in
  the same year), supporting genuine Dec ↔ Jan rollovers within `±180` days, leaving
  yearless dates outside `±180` days or missing `published_ts` untouched, and never
  repairing inverted yearless ranges by adding a year.
- **Safety exclusions:** existing `<t:…>` tokens, URLs, inline backticks, fenced code
  blocks, date-only phrases, `"After the Version X.Y update"` clauses, approximate durations
  and invalid, inverted or half-qualified ranges are left completely untouched without
  converting half of a range. Source `Item` fields and raw HTML/captures are never mutated.

### Full-content paging and overflow

Keep fitting full articles unchanged in one message (possibly multiple containers).
By default (`NEWS_EXPAND_FULL=0`), one message is tried first. When normalized source
text plus title/byline once is `<= 7,000` characters, at most two actual messages are
permitted, each validating independently against `4,000` text characters / `40`
components / `1–10` gallery items. A longer article is **smart fitted** with the same
validation and the same payload shape, page after page, up to
`NEWS_DEFAULT_MAX_PAGES = 4`; only what cannot fit inside that ceiling falls back to the
one-container labelled excerpt with a single lead image. Nothing in the JSON structure,
the official HTML or the sources changes: title/byline plus cover on page one,
`-# Page N` plus divider on every continuation, and the three buttons on the last page.

The fit is markdown-safe and loss-free: paragraphs are kept whole, and a paragraph that
does not fit the room still open on the page is continued in the next message at a
boundary that never splits a link, a bold run or a bracket. Concatenating the pages
reproduces the article text exactly, so no sentence is silently dropped.

That also covers an article between `4,000` and `7,000` characters written as one long
paragraph with no blank line: the two-page layout is tried first (and keeps its exact
bytes), and when it cannot cut safely the smart fitter continues the paragraph at a word
boundary instead of truncating the article. Page labels stay truthful when the reveal
mention reflows page one: a card that was numbered `1..N` is renumbered `1..N+1` in
delivery order, while a single-message card never gains a label.

When `NEWS_EXPAND_FULL=1` is explicitly enabled, the 2-page / 7,000-character policy
ceiling is lifted up to an explicit operational safety bound (`NEWS_EXPAND_MAX_PAGES = 12`,
`NEWS_EXPAND_MAX_CHARS = 120000`, `NEWS_EXPAND_MAX_MEDIA = 120`):

- Every emitted page still validates independently against Discord's limits (`4,000` text
  characters, `40` components, `1–10` media gallery items).
- Source text and media order, unique-cover deduplication, native MP4/WebM cover suppression,
  link-only video covers, `Page N` headers, non-repeated title/byline and final-container-only
  3-button controls (`Read Post`, `Citlali News`, `Donate`) are preserved across all pages.
- Overlong paragraphs inside a block split only on safe newline/sentence/whitespace
  boundaries outside Markdown links, inline code and unbalanced `**` bold spans.
- If an article exceeds `NEWS_EXPAND_MAX_PAGES = 12` (`NEWS_EXPAND_MAX_CHARS = 120000`,
  `NEWS_EXPAND_MAX_MEDIA = 120`) or contains an indivisible single unit
  exceeding single-message limits, rendering degrades cleanly to an explicitly labelled
  `Excerpt — …` single card rather than truncating silently or claiming to be full.
- Confirmed per-page message IDs save after each send; official-news and maintenance-alert
  `POST`s pass `stop_on_ambiguous=True` so if a webhook `POST` returns HTTP `2xx` without a
  parseable `message_id` or fails after dispatch ambiguously, it stops after 1 attempt, marks
  `ambiguous = True`, and holds rather than blindly re-posting duplicates (existing `schedule`
  and `codes` callers retain baseline `stop_on_ambiguous=False` retries).


### Source-preserving formatting

Keep Part 1/2 and Part 2/2 for containers in one message, and Page 1/Page 2 for
separate messages. Never repeat title/byline/lead on continuation pages. All three
custom-emoji controls appear only at the end of the final container of the final
message, including single-message layouts with multiple containers.

Compact consecutive numeric, circled-number, alphabetic and square (`■`) entries
without rewriting words/markers or crossing ordinary paragraph/section boundaries.
HTML list items with nested paragraphs must keep `- ` attached to their first
visible text, and multi-op Quill headings/lists accumulate inline runs on the same
line before applying heading bolding or bullet prefixes. Inline Quill/HTML emphasis
preserves outer horizontal spaces and blank lines per paragraph without spanning
`****` across color-split runs or blank lines, unwraps bold/emphasis-wrapped
self-labelled or visible-URL anchors into clean bare URLs (closing any open bold span
before bare URLs), flattens nested bold heading links into `**[label](url)**`, and
escapes literal CMS `*` footnotes/multipliers (`\*`) outside URLs. Correct converter
boundaries, not source-specific wording. Marker spacing only pads existing `※`/`✦`;
never insert a missing source marker to match a screenshot. Preserve source
HTML/API/mirror responses and exact media URLs.

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

### Source coverage and safe verification

HoYoLAB discovery/full-body adapters cover GI (gid 2), HSR (6), HNA (9) and
ZZZ (8), including Official Info, Events and Notices. Descriptive HTML/Quill news
anchor labels with square brackets serialize cleanly via `news_link()` without
visible escape backslashes while keeping bare/self-labelled URLs and non-link
bracketed headings unchanged. WuWa discovery is limited
to the current official English index; it is not historical archive discovery.
A manually trimmed capture cannot establish a complete article's length or prove
current direct official-host ingestion. Historical maintenance examples remain
schedule-routed; presentation changes do not reroute or backfill them.

Before opting in, use [the existing verification commands](TESTING.md#official-news-offline-coverage-and-read-only-checks)
and review [source limits](SOURCES.md#optional-full-content-news-adapter-2026-10-18).
Offline previews/tests validate payload construction, not live source availability,
Discord media access, codecs, delivery or thumbnail readability. Keep news off
until the operator explicitly approves opt-in. Review partial-delivery holds;
never reset delivery state merely to test. No new scheduler, tokens or upload
service are needed. Keep each installation's state and secrets independent.

## Pre-load & maintenance started (explicit per-game opt-in; default off)

`MAINTENANCE_ENABLED=0` (default) makes zero extra requests and adds no maintenance
entries to `state/state.json`. Activating the fourth feature requires **both**
`MAINTENANCE_ENABLED=1` **and** an explicit non-empty `MAINTENANCE_GAMES` list,
plus a dedicated per-game webhook secret for each opted-in game:

| Setting | Kind | Default | Meaning |
|---|---|---|---|
| `MAINTENANCE_ENABLED` | Variable | `0` | Master switch; disabled unless explicitly truthy (and overridden by `ENABLED_FEATURES=none/off/standby/0`) |
| `MAINTENANCE_GAMES` | Variable | *(empty)* | Required explicit per-game opt-in list (e.g. `all` or `genshin,starrail,zzz,wuwa,hna,ananta`); empty activates nothing |
| `DISCORD_WEBHOOK_MAINTENANCE_<GAME>` | Secret | *(unset)* | Dedicated per-game channel webhook (`GENSHIN`, `STARRAIL`, `HNA`, `ZZZ`, `WUWA`, `ANANTA` + aliases); no generic/catch-all/mirror/`FORCE_WEBHOOK` fallback |
| `PING_MAINTENANCE_<GAME>` / `PING_MAINTENANCE` | Variable | `none` | Optional per-game or feature role ping on **Pre-Load Started** and **Maintenance Started** (`<@&ROLE>`); **Servers Live is always silent** |

Behavior and safety invariants (`gamexpress/maintenance.py`):

- **Independent milestones & separate state:** posts `Pre-Load Started`,
  `Maintenance Started` and `Servers Live` independently per `(game, version)` on the existing
  5-minute poll cycle. `state["maintenance"][game]` tracks `preload`, `maintenance` and `live`
  separately from `schedule`, `codes` and `news`, and merges across fail-over peers.
- **Servers Live — signals and guards (`live`):** two signals, no clock. (1) The publisher's
  completion notice or tweet (`schedule.MAINT_COMPLETE_RE`: *update maintenance has been
  completed / concluded*, *Update Completion Notice*, *servers are now online*, *can now log in*;
  a stated clock such as `completed at 10:42 (UTC+8)` is used when present, otherwise the post
  time) → provenance `official`. Future-tense quotes inside the maintenance preview (*compensation
  … after the update maintenance is finished*) are rejected by the clause check. (2) HoYoPlay
  games only: the client maintenance gate `getGlobalApplicationMaintenance`
  (`gamexpress/sources/launcher.py::MAINT_STATUS`, headers `x-rpc-app_version` /
  `x-rpc-client_type: 1` / `x-rpc-cg_game_biz`) read once per run while a version is inside
  `[maint_start_ts + LIVE_MIN_DOWNTIME_S (20 min), maint_start_ts + LIVE_WINDOW_S (24 h)]` and
  its `Maintenance Started` card is `posted`; the first `null` after the flag was seen set for
  that version (`state["maintenance"][game]["maint_api"]`) is the reopening → provenance
  `observed`, with a one-line note on the card. Non-zero `retcode`, a missing key or a wrong
  shape is *unknown* and changes nothing; a `null` that was never preceded by a set flag never
  posts. Idle days cost `0` gate requests. Both signals are accepted only inside the same window,
  only for a `Maintenance Started` card this install posted (versions joined midway are seeded
  `live` together with `maintenance`), and once per version. An official notice arriving after a
  gate-detected card upgrades it silently through the timing-correction budget (no repost, no
  re-ping). The same moment rewrites the `Maintenance Started` card's `End Time` to the actual
  reopening (`end_actual`, silent `PATCH`, `timing_edit_*` budget) and the scheduled end is never
  restored afterwards. `REPOST=<game>:<version>:live` re-sends a single card on demand.
- **Silent baseline on first enable:** on first activation (or re-enable after pause),
  already-passed milestones and live/settled versions are marked `seeded` silently
  without posting historical announcements.
- **Strict precedence:** official notices/tweets/Reddit (`rank 38–50`, including inferred
  epithet versions such as `"Luna II"` and unnumbered `"1.0"` launch notices for pre-release
  games) → explicit `config/overrides.json` entries (supporting both Unix epochs and ISO-8601
  strings with timezone offsets, plus `image` pins at the top of Tier 4) → persisted
  first-observed launcher pre-download availability (`observed_preinstall_ts`, retained
  across polls/restarts and rendered with explicit observation wording rather than claiming
  a published start time) → refined non-cadence `schedule` estimates (`countdown` sources
  for 5-week / 7-week shifted patches) → documented cadence predictions (`rank 9`, clearly
  marked estimated). Holiday-shifted
  official notices always override cadence predictions, observations and stale overrides;
  HNA and ANANTA never invent an unverified cadence, and unknown `maint_end_ts` omits `End Time`
  rather than guessing.
- **Components V2 card & 5-tier media priority:** single container (`flags: 32768`)
  with `[SHORT - VERSION] Pre-Load Started` / `Maintenance Started` / `Servers Live`; the optional
  configured role mention appears only on the first two milestones (`Servers Live` is always silent).
  Cards show `Date Time` (`<t:…:f>`) + `Hour Time` (`<t:…:R>`) or `End Time` (`<t:…:t>`),
  optional version-verified gallery ((1) matching-version launch video `.webm`/`.mp4`,
  (2) matching-version launcher artwork/WebP, (3) WuWa launcher carousel art with a matching version note,
  (4) matching-version Special Program art, (5) omitted cleanly), and the Citlali News section footer.
  WuWa reads the global English new-protocol index/background first (dated assets must fall inside
  the version's launch window), then the legacy slot; the carousel is fetched only inside that
  existing window gate. CN is deliberately unused. Launch version identity is
  separated from selected tier so prompt initial artwork posts can silently `PATCH` to
  matching-version launch video inside `LATE_MEDIA_EDIT_WINDOW_S` (`6 h` / `21,600 s`) while
  rejecting Phase II swaps. Signed Kuro `?auth_key=…` URLs keep query parameters intact and expire.
- **Exact post-delivery refresh & retry bounds (`gamexpress/maintenance.py`):**
  - *Time window:* strictly `0 <= now - posted_at <= LATE_MEDIA_EDIT_WINDOW_S` (`6 * 3600 = 21,600 s` / `6 h` from `posted_at`); polls after `6 h` perform `0` health checks, `0` candidate lookups, and `0` `PATCH` edits.
  - *Failed-edit limit (`MAX_LATE_MEDIA_ATTEMPTS = 3`):* counts only failed `ctx.webhook.edit(...)` calls (`not res.ok`), tracked in `entry["edit_attempts"]`; read-only checks do not increment it, and reaching `3` stops further checks/edits for that milestone.
  - *Counter reset:* only a succeeding `ctx.webhook.edit(...)` (`res.ok is True`) resets `entry["edit_attempts"] = 0` and commits the staged state.
  - *Check cadence:* evaluated at most once per scheduled `maintenance.run(ctx)` execution (existing 5-minute poll schedule — no in-run loops), memoized per run (`verified_cache`) so each distinct URL is checked at most once per poll (`0` HTTP checks on already-expired `auth_key=` timestamps), and skipping `hoyoplay_basic_info` completely when `cur_tier == 1` is healthy and no authoritative timestamp upgrade applies.
  - *Separate succeeded-edit cap (`MAX_LATE_EDITS = 6`):* tracked monotonically in `entry["edit_count"]` (never reset), capping total succeeded silent `PATCH` edits per posted milestone across upgrades, renewals, and fallbacks.

## Beta kit & revision-diff cards (feature 5 — explicit opt-in; default off)

The fifth feature publishes a game's **beta** revision: a full kit overview for each
newly revealed character and new weapons / W-Engines / light cones / disc drives /
relic sets / echo sets on first observation, then compact source-backed revision diffs for
later builds. It retains the prior readable kit in bounded state, so a later change can show
`~~old~~ → **new**` inline rather than re-posting an entire kit.

Full-content digests suppress unchanged long kits even when retained text is clipped.
The digest trims whitespace on both sides, so a padded or blank source line is never mistaken for
a clipped block: only a real clip (a line over 1 400 characters, a block over 160 lines, the
60 000-character budget, or a capped field such as the 240-character title) marks a snapshot
`truncated`.
If changed content exceeds retained limits, or a legacy snapshot lacks a full-content digest,
the next inspected revision uses a labelled full `[CHANGED]` snapshot without invented inline
direction. Retained text limits and state pruning stay bounded. A full snapshot with no comparable
baseline never borrows the diff voice: its paragraph says the card is the whole kit and that
`Nothing is marked as up or down`.

An item can move without a readable value moving: an agent reclassified (`Sword → Rectifier`), a
rarity raised, a faction corrected, an entry renamed. Those fields are compared as well, so a
metadata-only revision still produces a card — a `Profile Changes` block of
`[ADJUSTMENT]` / `[CHANGED]` lines — and never records the item as delivered while posting nothing.
Against the **released** live build only two-sided fields are compared, because the released
reader does not publish every field the beta one does and a one-sided absence would read as a
change. If the stored signature moved but no text, classification field or visual asset did, the
card carries an explicit `[CHANGED]` note instead of disappearing.

WuWa also has a bounded Encore API beta detail fallback for missing/unreadable current-build
characters and weapons. It uses explicit `?v=Beta`, an exact `ResVer` match and unchanged
`GameVer`/`ResVer`/`Changelist` before/after the detail read. The primary Encore endpoint is
tried before its official legacy backup; each server attempt reserves three calls under the
existing limits, at most six logical JSON reads per item, each keeping its existing retry
policy. An early failure still consumes that attempt's reservation. No setting is added.
Healthy nanoka data needs no extra calls, and a
successful primary Encore read never contacts the backup.
See [the source contract](SOURCES.md#encore-beta-api-fallback-for-wuwa) for historical and media limits.

`BETA_ENABLED` is **off by default**. Disabled, the feature makes **zero** requests and
adds nothing to `state/state.json`. It never posts to a schedule or codes channel:
routing is dedicated (`DISCORD_WEBHOOK_BETA_<GAME>` > `DISCORD_WEBHOOK_BETA` >
`DISCORD_WEBHOOK_NEWS_<GAME>`), with no catch-all, mirror or `FORCE_WEBHOOK` fallback.

| Setting | Kind | Default | Meaning |
|---|---|---|---|
| `BETA_ENABLED` | Variable | `0` | Master switch; disabled unless explicitly truthy (and overridden by `ENABLED_FEATURES=none/off/standby/0`) |
| `BETA_GAMES` | Variable | `genshin,starrail,zzz,wuwa` | Game allow-list. `all` resolves to the same four — **Honkai: Nexus Anima and ANANTA are excluded until they ship**; `none` switches it off |
| `DISCORD_WEBHOOK_BETA_<GAME>` | Secret | *(unset)* | Dedicated per-game channel (`GENSHIN`, `STARRAIL`, `ZZZ`, `WUWA` + short aliases `GI`, `HSR`, `WW`) |
| `DISCORD_WEBHOOK_BETA` | Secret | *(unset)* | Shared beta channel for any opted-in game without its own secret |
| `DISCORD_WEBHOOK_NEWS_<GAME>` | Secret | *(unset)* | Last resort: that game's existing news channel (e.g. `zzz-news`). Never the schedule/codes catch-all |
| `PING_BETA_<GAME>` / `PING_BETA` | Variable | *(unset = silent)* | Role ping on the **first page only**. `PING_ROLE_ID` is deliberately **not** inherited |
| `BETA_MIN_POLL_MINUTES` | Variable | `30` | Minimum interval between changelog re-checks (`0` = every run). A quiet beta costs one manifest GET; a run inside the floor logs `beta: source check skipped — polled <n>m ago, floor is <n>m` so a monitor run with no beta card says why |
| `BETA_MAX_CHARACTERS` | Variable | `4` | New-character cards in one bounded batch; remaining items resume next run |
| `BETA_MAX_CHANGES` | Variable | `8` | Existing-character revision cards in one bounded batch (`0` intentionally suppresses them) |
| `BETA_MAX_EQUIPMENT` | Variable | `12` | Weapons / W-Engines / light cones / disc drives / relics / echoes in one bounded batch |
| `BETA_MAX_REQUESTS` | Variable | `48` | Hard HTTP ceiling for the whole feature in one run; uninspected items remain pending |

Changing the destination is safe and needs no state edit. Adding `DISCORD_WEBHOOK_BETA_<GAME>` after
beta had been posting through that game's news channel moves the next card to the new channel and
records the move in the run summary (`destination changed — new cards post to
DISCORD_WEBHOOK_BETA_<GAME>`). The one case that still stops is a **half-posted card**: if a page
of an earlier batch is already in the old channel, the move is held with
`destination changed while N delivery is unfinished; reconcile it before posting to the new channel`,
because a retry would split one card across two channels.

Where the data comes from (`gamexpress/beta.py`, see [SOURCES.md](SOURCES.md#beta-kit--revision-diff-sources-2026-10-24)):

- **`https://static.nanoka.cc/manifest.json`** — one small JSON naming each game's `latest`,
  `live`, ordered `available` data builds, and ids that are new in the current beta. Candidate
  builds at or behind the game's live `major.minor` cycle (resolved from manifest `live`/`hotfix`,
  version config, and confirmed past schedule maintenance) are skipped immediately before any
  changelog or detail request, preventing finished/live betas from posting. Active builds walk
  one retained step at a time rather than jumping past a hotfix.
- **the game's beta changelog** — `https://<game>.gachabase.net/changelog/beta?lang=en`
  for GI / HSR / ZZZ; its matching revision supplies item/diff links and CN-lag advisories.
  HTTP 403 / access-denied blocks degrade cleanly to nanoka's manifest without warning spam.
  The rendered page is only one of two views of the same data: when it cannot be read, the
  SvelteKit `/changelog/beta/__data.json` stream is parsed instead, and the per-build character /
  weapon / relic listings are diffed so new, renamed or re-specced items are still found.
  **When the changelog is blocked on every route**, the listings cannot say which skill text
  changed, so a per-item probe compares each listed item's detail for the previous and the current
  build (icon and image keys ignored). It has its own cap, `BETA_PROBE_MAX_REQUESTS` (400 per
  revision, not `BETA_MAX_REQUESTS`); the result is saved on the revision, so a deferred revision
  does not re-probe, and the run summary states how many items were checked. This is the one case
  that fans out across every item; the no-fan-out rule below still holds whenever the changelog
  is readable. A
  revision whose sections are not streamed at all is skipped rather than reported as "no
  changes", and the run summary records that coverage was narrower (`beta-changelog 0/3`,
  `beta-data 15/0` in the source counts) instead of quietly printing a shorter card.
  If a hotfix heading has no listed entries, the runner probes only manifest-new and
  already-snapshotted ids; it does **not** fan out across every character. Wuthering Waves has
  no structured changelog endpoint, so it remains manifest-driven; its `ww.nanoka.cc/diff` URL
  is a human resource link, never a poll target.
- **`https://static.nanoka.cc/<game>/<live build>/{en}/<kind>/<id>.json`** — the build players
  already run, read **once per item** as the diff baseline for anything that is already released.
  From the second post of a revision onward a card is a diff, not a re-print: the item is compared
  with the build players have (or with its own retained beta snapshot, which is the same thing one
  revision later), and only the blocks that moved appear — `~~old~~ → **new**`, tagged `[BUFF]` /
  `[NERF]`, a new skill or mechanic as `[NEW]`, wording-only edits as `[TEXT FIX]`. A block that
  disappeared is stated once, `**[CHANGED]** Removed from this revision — ~~excerpt~~`, with a count
  of the retired lines instead of quoting them all, so a later post gets shorter rather than
  longer. A retained snapshot that can no longer be compared (a legacy record with no
  full-content digest, a clipped baseline, a changed provider) is replaced by the released build
  as the baseline rather than becoming a "full current kit" rebaseline. This also covers a
  same-cycle hotfix (`7.1` live vs `7.1.53` beta). Costs one request per item, once — the beta
  snapshot becomes the baseline from the next revision on — it is skipped when the live build does
  not serve that item (an unreleased character has no live kit), which keeps the labelled full
  snapshot. The read is only attempted while the run keeps **8 requests** of headroom for the
  batch's images; below that the item is **deferred to the next run** instead of being re-printed
  whole (`patch.more`), and a `BETA_MAX_REQUESTS` too small to ever fund a baseline (under 10)
  keeps the old full snapshot rather than stalling forever. When nothing moved against the
  released build, no card is posted for that item and the run summary says why
  (`beta kit matches the released … kit — no value change to post`). An item the source cannot
  describe at all is recorded once so the batch can settle (WuWa weapons are deferred instead,
  because their source does answer later) and the run summary names it —
  `beta: weapon id … has no readable text in this build; recorded as seen` — so a skipped item is
  never a silent one.
- **Direction follows the kit, not the arrow.** `[BUFF]` / `[NERF]` are decided by what the value
  does in play: a cheaper Ultimate or EX cost, a shorter cooldown / charge time, or an easier
  trigger requirement is a buff although the number fell, and `DMG taken reduced by 30% → 40%` is a
  buff for the same reason. Where the tag contradicts the number the card says why in one clause
  (`*(cheaper to use)*`, `*(the skill comes back later)*`). A threshold, duration, stack count,
  range or chance can move either way, so those stay a plain `[CHANGED]` with no direction — the
  guide's "unsure? drop the directional tag" rule. A name / reaction / keyword / type swap is
  `[CHANGED]`; prose alone is `[TEXT FIX]`.
- **A mixed-build revision says so on the card.** Upstream sometimes publishes one build inside
  another's revision: on 2026-10-30 ZZZ served 3.4.2 material inside the 3.4.1 hotfix 19997538 and
  said so in its own changelog and news comment. Two game-agnostic signals put one `**Note:**` line
  under the header — the changelog flagging itself (`Partial data`, `Mixed data`, `Datamined`,
  `take it with a grain of salt`, …; a generic "values may change" beta banner is not a flag), or a same-version hotfix that renames or adds far more blocks
  than a hotfix normally does. The note names the reliable part (*the point values*) and calls
  renames and new mechanics provisional; it never withholds the card and never invents a reason.
  The run summary repeats it (`mixed-data caveat on the card`).
- **A diff card explains itself before it lists anything.** The paragraph under the header is prose,
  not another changelog: a verdict (`comes out ahead` / `is toned down` / `is rebalanced` / `is
  renamed … rather than rebalanced` / `gains new material`), where the movement actually lands
  (`most of the movement is in Deathless Revival and Life Severing`), what arrived
  (`[Burning Attack] is new here`), and what was left alone (`The other 14 blocks are untouched and
  read exactly as they do on the released 3.3 kit.`). `and nothing was nerfed` is only written when
  every measured number really did move up; a value the diff could not read keeps the paragraph
  silent rather than optimistic. A revision that is mostly renames carries
  `**Note:** this is largely a terminology pass — N blocks changed only in wording`, so a rename
  sweep never reads as a rework. Revised weapons and discs get one sentence in the same voice
  (`**Nirvana Plume** gets stronger in this revision — nothing nerfed. The biggest change is its
  Anomaly Proficiency bonus.`). No extra request: the paragraph is built from the diff already on
  the card.
- **`https://static.nanoka.cc/<game>/<revision>/{en,zh}/<kind>/<id>.json`** — the kit / weapon /
  set detail. English (`en`) is read first; Chinese (`zh`) is queried within the same bounded
  `BETA_MAX_REQUESTS` ceiling only when EN shows lag markers (`???`, `[TBD]`, `/-`), an upstream
  changelog warns to double-check Chinese, or an EN revision appears unchanged against the prior
  snapshot while CN updated its multipliers.

Safety invariants:

- **No invented numbers and no guessed direction.** Values come straight from the structured
  export, with raw client markup (`<IconMap:...>`, `<size=...>`, `<SapTag=...>`, `<te href=...>`,
  console layout fallbacks, and unresolved `{0}` / `#{...}` placeholders) stripped cleanly.
  With a retained before/after baseline, clear cases may use `[BUFF]` / `[NERF]` (for example,
  a damage multiplier rising or a cooldown falling), structurally rewritten or renamed slot
  skills surface as `[REWORK]`, ambiguous mechanics remain `[CHANGED]`, wording-only changes
  `[TEXT FIX]`, and type/category moves `[ADJUSTMENT]`. Without a baseline the card is a full
  `[NEW]` / `[CHANGED]` snapshot, never a fabricated diff.
- **Image & gallery lock.** Verified splash-art, weapon/LC/W-Engine icons, 6-icon HSR Eidolon
  galleries, and multi-piece Planar/Relic/Artifact/Drive Disc galleries are stored in
  `state["beta"][game]["locked_images"]` and reused. Locked URLs are never re-verified, so a
  settled item stops generating media traffic.
- **Format-epoch migration (`BETA_FORMAT_EPOCH = 2`).** Pre-epoch-2 persisted beta records are
  cleared once (while holding any ambiguous circuit-breaker batch and preserving route metadata,
  and ignoring older-epoch peer snapshots on failover merge) so protected production state can
  repost active betas cleanly in Prime Formatting Style without re-posting on later runs.
- **Idempotent, resumable build batches.** State stores the exact source build, a bounded full
  snapshot per item, and a per-batch message cursor. Large revisions resume their next bounded
  item batch rather than duplicating an earlier page. An ambiguous Discord outcome is a persisted
  circuit breaker across later runs—not an automatic retry—until an operator reconciles that
  batch, so an uncertain page-one POST cannot become a duplicate. Snapshot/candidate identity is
  role-aware if upstream numeric ids collide, preventing a character, weapon, and relic from
  sharing an image lock or baseline. An explicit upstream “No tracked changes detected” build
  advances silently (except on a cold opt-in, which intentionally publishes the current reveal
  once).
- **Late entries and honest coverage.** GachaBase can render a fresh revision over several
  minutes, so a revision that has *just* posted is re-read for entries its first read did not
  list: at most `BETA_LATE_RECHECKS` (2) extra reads inside `BETA_LATE_RECHECK_H` (3) hours, and
  only for character / weapon / relic entries absent from that build's `processed` set. Once that
  window closes the revision is final and costs no request. A settled revision is never re-read
  through the version-comparison path, so a quiet poll costs one manifest GET as before. When the
  changelog listed more tracked items than the card delivered, the run summary ends with
  `; changelog listed N item(s)` — a coverage gap is visible without opening the log.
- **Fail-over aware.** `state["beta"]` merges across peers so a standby never double-posts.
- **Bounded pages and delivery gap.** Long kits split into sequential Components V2 containers,
  each independently inside Discord's 4,000-character and 40-component limits, labelled
  `Page n/N`. After a successful page, production waits a fixed **five seconds** before the next
  unsent page. It never adds a trailing wait after the final page, and a restart begins its first
  unsent page without replaying a previous-run gap. This is intentionally a fixed safety rule,
  not an environment knob.

### Offline enabled-beta full-pipeline harness

Use `python -m gamexpress benchmark --iterations 300 --beta-enabled` to exercise feature 5
without opting in a real monitor. The command constructs an isolated in-memory
`BETA_ENABLED=1` / `BETA_GAMES=genshin,starrail,zzz,wuwa` context and executes the actual
manifest → changelog/manifest fallback → detail parser → image preflight → Components V2 renderer
→ webhook delivery → state-settlement path for **all four** released beta games. It deliberately
covers long multi-page full kits, character/weapon/relic baselines, retained-revision diffs,
deduplication, an explicit quiet revision, a failed first page, an ambiguous first page plus its
blocked replay, and a resume boundary. Its injected sleeper records every intended five-second
page gap instead of making the suite wait.

The JSON report is `beta_enabled_fixture.pipeline`: it records fixture collaborator calls and
state-save transitions while asserting **zero live** source requests, Discord posts and physical
state writes. `beta_enabled_fixture.render_microbenchmarks` keeps the eight synthetic new/revision
renderer timing rows as a supplemental performance measurement. The command never changes the
process environment or production settings; the normal default-off benchmark remains its original
12 news/parity timing cases.

## Discord webhook versus bot delivery

Incoming webhooks remain the appropriate simple outbound transport here; they do
not make delivery unlimited or inherently faster than a bot REST request. Discord
uses per-route/resource buckets (including webhook ID/token) and global limits;
different webhooks can have independent buckets, not guaranteed total isolation.
Official docs specify a default bot global limit of 50 requests/second; requests
without an Authorization header have their global limit applied by IP. Neither
that ceiling nor frequently quoted per-webhook numbers promise message throughput.
Use actual response headers and Retry-After/retry_after, not a hard-coded quota.
[1](https://docs.discord.com/developers/topics/rate-limits)

The current client deliberately spaces outgoing requests globally by 1.2 seconds,
even across separate game webhooks, and has bounded 429 retries. The cap removal
does not change that transport behavior. Existing long retry_after values are
clamped to 30 seconds per sleep; full header-aware/bucket-aware pacing and long-wait
handling are separate follow-up work, not claimed as implemented by this change.
For normal official-news volume, poll interval/source availability, media checks
and runner startup can matter more than choosing webhook versus bot. No measured
webhook-versus-bot latency benchmark was performed.

References: [1](https://docs.discord.com/developers/topics/rate-limits),
[5](https://github.com/discord/discord-api-docs/blob/main/developers/topics/rate-limits.mdx),
[10](https://discord.com/developers/docs/resources/webhook).

### Beta page counts

Beta page count follows readable content, with no fixed five- or ten-page maximum. Character
text, equipment effects, all published parameter rows and all changed/removed blocks continue
across as many validated Components V2 messages as needed. Every message stays within the
4,000-character / 40-component limits, with a `Page n/N` footer and first-page-only ping.
`BETA_MAX_CHARACTERS`, `BETA_MAX_CHANGES` and `BETA_MAX_EQUIPMENT` limit items fetched per
batch, not pages or skill changes within an item. Request budgets and bounded snapshot storage
remain unchanged. Incomplete prior snapshots still yield labelled full current kits.

A successful page's ID is saved before the five-second gap to the next page. A confirmed failure
after page ten resumes at page eleven; snapshots and the revision cursor settle only after the
entire batch succeeds. Ambiguous POSTs hold for reconciliation. Larger cards need more Discord
requests and pacing time; no live throughput guarantee is implied. Upgrading the renderer during
an existing partial delivery can change its payload signature and trigger the same reconciliation
hold described below; preserve the saved message IDs.

### Beta partial-delivery reconciliation

A beta batch stores its exact payload signature and source version with confirmed page IDs.
On restart, finish that source version before newer manifest builds. If content, media,
settings or batch membership changes after a page was confirmed, delivery holds for operator
reconciliation. Legacy partial batches without a signature also hold; do not clear their
message IDs automatically. Inspect the actual Discord messages and retained source build
before repairing state. Quiet source output cannot settle an unfinished delivery.

### Character reveal mentions

Two settings, no more: `NEWS_REVEAL_PING=1` turns it on and the single `PING_NEWS_REVEAL`
role list applies to **all six games** (there is no per-game variant and no inheritance from
`PING_ROLE_ID` or `PING_NEWS`). It also requires enabled official news. It checks existing
fetched articles; no additional source requests are made. Announcements in the
same **source publication minute** within a game share one ping; different minutes are not subject
to a cooldown.
Recognized follow-up profiles for retained character names are suppressed. A form suffix is the
same character (`Rover: Aero` and `Rover: Electro` share one key), and only corroborated full-name
aliases collapse within 12 hours (`Evelyn` / `Evelyn Chevalier`); names that merely share a word
(`March` / `March 7th`, `Saber` / `Saber Alter`, `Herta` / `The Herta`) stay distinct. Tracking
retains up to 200 names and timestamps per game and can be seeded from known schedule reruns; it is
not a complete historical roster. Ambiguous first-page delivery is held and treated as already pinged
for deduplication until manually reconciled. If the mention cannot fit the existing card, the
original article is sent without that ping and a warning is reported; its structure is not changed.
Matching is heuristic: new formats and unknown
video representations can be missed. ANANTA has no configured official-news adapter.

### Turning the optional mentions on

Both mentions ship **off**, so a default deployment stays silent; each is one switch plus one
role list, and nothing else changes.

1. **Character reveal** (`NEWS_REVEAL_PING`) — needs official news to be running. Add the
   variable `NEWS_REVEAL_PING=1` and the variable `PING_NEWS_REVEAL` holding the role ID(s) for
   all six games (comma-separated, `everyone` / `here` allowed). Do not point it at
   `PING_ROLE_ID` — it is deliberately not inherited, and no `PING_NEWS_REVEAL_<GAME>` exists.
   It fires only on a *character announcement reveal* (Genshin `◆` dossier, HSR
   `Extraterrestrial Satellite Communication`, ZZZ `Agent Record`, WuWa `Profile Reveal`, HNA /
   ANANTA dossier series) — not on maintenance notices, events, codes, schedules, outfits,
   reruns, showcases, previews, web events or gag comics. Verify with one reveal: the mention sits
   on the card's legend line, `PING_NEWS_REVEAL` set to `none` silences it again.
2. **Beta revision card** (`PING_BETA`) — needs `BETA_ENABLED=1` and a non-empty `BETA_GAMES`.
   Add `PING_BETA` (all opted-in games) or `PING_BETA_<GAME>` (`GENSHIN`, `STARRAIL`, `ZZZ`,
   `WUWA`, plus `GI` / `HSR` / `WW`). It pings on the **first page only** of a batch, once per
   revision; `PING_ROLE_ID` is not inherited. Unset means silent — which is the state a beta run
   needs no code change to reach. `python -m gamexpress validate` prints the resolved state on the
   `beta=` line (`ping=configured` or `ping=off (no PING_BETA set)`), so the switch can be checked
   without waiting for a revision.

Neither setting adds a source request, a poll or a card: they only add (or withhold) the mention
on cards that are already being rendered.
