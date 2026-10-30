# Testing Game-Express: is everything working?

## Summary-output regression coverage

The existing smoke runner exercises `runner.py::write_summary` directly with
local fixtures: secret/annotation sanitization, append behavior, missing report
messages, source counts, elapsed time, dry-run wording and unwritable output.
Run it with the existing schedule and placeholder runners; no new report/test
file, live webhook or delivery-state reset is needed. A passing local summary
test does not establish later workflow commit/push success.

Work through the steps in order. Every test runs from GitHub:
**Actions → Game-Express Monitor → Run workflow → `mode` = test**.

**The tests use real data.** None of them posts a sample card: each one fetches the live sources
and shows what they really returned, so a wrong link, a wrong picture or a wrong timestamp is
visible *before* a real announcement goes out.

That workflow:

- posts to the **real** channels, labelled **🧪 TEST**, so you can tell a test card from a real
  one — and delete it;
- **never** commits and never touches `state/state.json`, so the live run still posts the real
  thing later (nothing is skipped as "already seen");
- **never edits a live card or its copy** — every test card is a *new* message, so a test can
  neither rewrite nor re-label what is already in the channel;
- pings nobody unless you tick `ping`;
- works on the development repo too.

---

## 0. Before merging a PR

The PR's **CI — compile + offline tests** check must be green. It runs every offline test file
through its own plain runner — `tests/test_smoke.py`, `tests/test_schedule_epithet_and_settled.py`
and `tests/test_gachawiki_placeholder.py` — which cover:

- the real official posts, which must reproduce your reference cards' timestamps;
- the golden cards, Discord limits, the code gate, 4★ TBA, fail-over, and the workflow files;
- the 2026-10-08 schedule-card regressions and the ZZZ 3.3 "Agent" placeholder guard.

CI needs no secrets and no network. A test file that is not wired into `ci.yml` (and into the
python-bump gate, which runs the same commands) fails
`test_ci_and_the_python_bump_gate_run_every_offline_test_file`, so none can go un-gated again.

A second job, **CI — advisory checks**, runs beside it and is **informational only** — it is
allowed to fail and can never block a merge:

| Check | What it looks at |
|---|---|
| [`pip-audit`](https://github.com/pypa/gh-action-pip-audit) | known CVEs in `requirements.txt` |
| [`actionlint`](https://github.com/reviewdog/action-actionlint) | workflow YAML correctness |
| [`zizmor`](https://github.com/zizmorcore/zizmor) | workflow *security* (credential persistence, injection, over-provisioned secrets). Policy and the three justified ignores live in `.github/zizmor.yml` and in inline `# zizmor: ignore[...]` comments |
| [`ruff`](https://github.com/astral-sh/ruff-action) | the same `ruff.toml` lint you run locally, annotated inline on the PR diff |

## 1. Webhooks: are all channels connected?

Run **`test: webhooks`**.

| You should see | If not |
|---|---|
| **one green "✅ Game-Express webhook check" card per webhook**, listing what that channel receives. For example, your GI codes channel lists *Codes · Genshin Impact* | no card → the secret is missing or wrong. The **Show resolved config** step in the log shows `✓ DISCORD_WEBHOOK_CODES_GENSHIN` or `— none` for every game |
| log line `[DISCORD_WEBHOOK_…] 1 route(s): OK 200` | `FAILED 401/404` → the webhook was deleted; make a new one and update the secret |
| HNA / ANANTA listed like any other game | both are switched **on** since 2026-10-02 even though they are not released; their code channels are checked with sample cards (`--unlaunched`) because there is nothing real to fetch yet |

## 2. Codes: do the real sources return the real codes?

Run **`test: codes`** (`ping` off). It does a real run of the codes feature against every live
source, looking back 30 days, and posts what it really found.

- **Each codes channel** gets its game's card, labelled **🧪 [TEST]**, with the codes that are
  actually redeemable right now.
- **HNA and ANANTA** are not out yet, so there is nothing real to fetch — they get **example
  codes** instead, purely to prove the card and the channel work.

Check each of these:

- [ ] The **codes are real** — try one in the game. A made-up code means a source is returning
      stale data.
- [ ] The **Redeem buttons** open the official page with the code filled in (GI / HSR / ZZZ).
- [ ] The **buttons are inside the card**, and the `Citlali News` row sits underneath.
- [ ] **The emojis animate.** If you see `:name:` instead, give `@everyone` *Use External Emojis*
      in that channel, or change `EMOJI_*`.
- [ ] **Nothing was saved**: run the live monitor afterwards and the same codes are still posted
      for real.

Also read the run **Summary** while you are here:

- `⏳ GI: 2 new code(s) waiting for a second source: GS71XOXYLG (only ennead), …` → codes seen by
  only one source, correctly held back until another source confirms them.
- `🧊 HSR: 12 code(s) ignored — already expired` → codes some source still lists, but another
  source (or their *valid until* date) says they are dead. Correctly never posted.
- `sources:` lists every source with `N ok / M fail`. One dead community source is fine (every
  data point has fallbacks); if *everything* fails, that source is having an outage.

## 3. Schedule: is the real announcement card right?

Run **`test: schedule`** (`ping` off). It does a real run of the schedule feature and posts the
real card for the version that is out now — labelled 🧪 TEST.

This is the test to run **before a Special Program airs**, because it shows exactly what the live
run would post:

| On the card | What to check |
|---|---|
| **Title link** | it opens the **Special Program / Broadcast announcement itself** — an official X post or a HoYoLAB / official-site article, both are correct — and **not** the *Update and Maintenance Notice*. If it opens a notice, the program article was not found; see below |
| **Key art** | the program's own artwork, and a big one: a YouTube `maxresdefault` thumbnail (1280×720) or a full-size tweet photo — not a small cover from somebody else's post |
| **Livestream line** | `… or in 3 days` — the date/time must be **your** local time and the right moment (compare with the announcement). For a programme that has already aired it reads `… a month ago`, which is correct: the bench renders the version that is out **now**, even when a live run would no longer open a card for it ([ACCURACY.md](ACCURACY.md) rule 6) |
| **Maintenance block** | pre-install, start, end and compensation, each as a real Discord timestamp. `estimated from Gacha Countdown` means no official notice yet — correct, and it is replaced automatically when the notice is seen |
| **Banners** | the 5★ and 4★ names for each phase. **TBA** means no official banner post was in the 30-day window — the honest answer, and pinning the names in `config/overrides.json` fills it in. A name locks once two sources confirm it, and an override locks it alone |
| **Buttons** | YouTube / Twitch / Source, inside the card |

### Checking a card for a version that is already out (e.g. Genshin 7.1)

A live run never opens a card for a version whose programme has already aired (rule 6 above), so
the bench is how you look at one. **Actions → Game-Express Monitor → Run workflow → `mode` =
`test`, `test` = `schedule`, `game` = `genshin`, `ping` = off.**

The step starts from an **empty state** with a **30-day lookback** and fetches everything live, so
the card it builds is what a live run would post — posted as a **new** 🧪 TEST message you delete
afterwards. Nothing live is touched: not the existing card, not its copy in the game channel.

| On that TEST card | What it proves |
|---|---|
| **Livestream line** shows the real air time (e.g. `Saturday, September 12, 2026 8:00 PM`, `a month ago`) | the announcement was found — the thing a notice-built card loses |
| **Title link** opens the Special Program announcement, not the maintenance article | same lookup |
| **Key art** is the program's artwork, not the *Update Details* cover | same lookup |
| **Maintenance block** shows pre-install / start / end / compensation | official values, unchanged |
| **Banners** show the real characters per phase (e.g. `Escoffier`, not `Tasteful Excellence`; `Phoenix`, not `Into the Flames of Life`) | the notice reader's dialect rules — the epithet shape and the channel shape (`CHANNEL_MODE`) — if the banner notice is inside the lookback |
| **Your live card and its copy are untouched; the TEST card is a separate message** | a test renders, it never repairs |
| Summary line `🛰️ GI 7.1: announcement found — programme airs …` | the repair, reported |

Then run **`mode = live`** once. For a version this bot has already carded, the announcement is
replayed from `config/program_announcements.json` and the existing card is **edited in place** —
`✏️ GI 7.1: schedule card updated — livestream time, banners, key art, link`, no new message. If
the stored card id no longer resolves (Discord `10008`), a settled version is never re-published:
the dead id is dropped and the summary names it — `🗂 … its card is not re-created (message <id>
no longer resolves — Discord 10008 — …)`. `repost = genshin:7.1` is the way back if you want one
anyway.

If the title link or the picture is wrong:

- The card is built from whatever official post the run saw. When the Special Program preview is
  older than the lookback window, the monitor looks it up on the **official news page** (then the
  HoYoLAB list) and replaces the link, the key art and the air time — see
  [ACCURACY.md](ACCURACY.md#the-announcements-own-link-and-key-art). `PROGRAM_MEDIA=0` switches that off.
- Once posted, the link and key art are locked to the announcement that opened the card (X preferred)
  ([ACCURACY.md](ACCURACY.md#once-posted-the-card-keeps-its-announcement)). A card that already
  points at the wrong post is corrected by pinning `title_url` and `image` in
  `config/overrides.json`. The next run edits the card in place.
- A version this monitor has carded before is repaired from `config/program_announcements.json`:
  the announcement's tweet id is committed with the state, so a test run — which starts from an
  empty state — resolves it by id and the air time, the link and the key art all come back
  together. A missing **Livestream line** means that lookup found nothing, not that the card
  chose to hide the date.
- A `fastcdn.hoyoverse.com` cover instead of the livestream art means the article has no embedded
  YouTube player, so there is no 1280×720 thumbnail to prefer.
- `⚠️ … 4★ shown as TBA — 2 name(s) found, 3 expected` → the uncertain 4★ list was correctly
  replaced by TBA.

## 4. Go live

1. Set up cron-job.org by following [SCHEDULER.md](SCHEDULER.md), then press **TEST RUN**.
   Expect `204`.
2. Check the **first live run**. Its summary says it seeded the current announcements and codes
   **silently** (`🌱 … seeded silently`, no posts). This is correct.
   - To post what's current on that first run instead, set `BOOTSTRAP_POST=1` **before** it,
     then delete it.
   - **Already seeded?** Run the Monitor with `repost` set to a tracked version from the summary
     (e.g. `starrail:4.6`). It is the deliberate override: it posts a card even for a version
     that is already out (`genshin:7.1` after its update), which the automatic path never does.
     A version that hasn't been announced yet (`genshin:7.2`) can't be reposted, and the summary
     explains why.
3. From then on, new codes and announcements are posted automatically.

## 5. Healthy-system checklist (check weekly, or when in doubt)

- [ ] cron-job.org **History**: `204` every 5 minutes (per instance).
- [ ] **Actions**: green *Game-Express Monitor* runs every 5 minutes. Red = open it; the summary
      says why.
- [ ] **alpha commits a heartbeat** (`auto: update state`) at least once an hour
      (`HEARTBEAT_MINUTES=60`).
- [ ] **Codes appear within ~10 minutes** of a livestream (official codes skip the 2-source
      rule).
- [ ] **Schedule cards appear** after an official *Special Program / Broadcast* post, and are
      **edited silently** once the maintenance notice arrives: pre-install, start, end and
      compensation fill in with no second ping.
- [ ] **Nothing else ever opens a card.** A maintenance, pre-install or banner notice on its own
      must never produce a post, and neither must a version whose programme already aired — those
      show up in the summary as `🗂 … already out` or a silent `tracked`, never in the channel.
- [ ] **No duplicates**: the same code or announcement is never posted twice, and an unchanged
      card is never re-sent (state keys + payload hashes).

## 6. Fail-over drill (optional, about 3 hours)

1. **Pause** alpha's cron-job.org job.
2. After `FAILOVER_AFTER_MINUTES` (150), bravo's run summary says it took over. It posts
   anything new, with no duplicates, because it imported alpha's posted list.
3. **Resume** alpha. It imports bravo's posts; bravo goes quiet again on its own.

## 7. Local testing (optional, for developers)

```bash
pip install -r requirements.txt pyyaml pytest
python tests/test_smoke.py                 # the main offline suite (golden cards, parsers, workflows)
python tests/test_schedule_epithet_and_settled.py   # the 2026-10-08 schedule regressions
python tests/test_gachawiki_placeholder.py          # the ZZZ 3.3 "Agent" placeholder guard
python -m pytest -q tests                  # the same three files in one go
python -m gamexpress validate              # routing, pings, card limits
python -m gamexpress preview               # previews/index.html = every card, Discord-style
ruff check .                               # same ruff.toml the advisory job uses
zizmor .github/workflows/                  # same config the advisory job uses (.github/zizmor.yml)
DRY_RUN=1 TEST_MODE=1 BOOTSTRAP_POST=1 STATE_PATH=/tmp/s.json python -m gamexpress run
```

The announcement lock and the X-first source order are pinned by the regression tests at the end of
`tests/test_smoke.py`, from `test_the_announcement_that_opened_a_card_keeps_its_link_and_key_art` to
`test_a_dead_nitter_status_mirror_is_not_waited_on_for_every_tweet`, and the countdown test
`test_a_countdown_estimate_is_replaced_by_the_official_notice_in_every_game` that follows them.

The banner lock is pinned by the tests from `test_an_official_notice_locks_on_its_own_and_a_later_different_one_is_logged_not_applied`
to `test_a_banner_lock_holds_in_every_game_and_maintenance_still_moves`. The correction rules have their own
tests: `test_a_community_lock_is_corrected_by_a_later_official_notice`,
`test_the_feed_follows_its_own_correction_and_a_silent_wiki_never_withdraws_it`,
`test_the_wiki_corrects_a_feed_value_but_never_an_official_one` and
`test_a_locked_phase_holding_a_banner_title_is_corrected_and_unlocked`. The traffic rules are
`test_an_incomplete_block_is_stamped_and_read_at_most_hourly_so_the_state_changes_once_an_hour` and
`test_a_complete_but_unconfirmed_block_is_rechecked_every_six_hours_and_a_settled_one_never`, plus
`test_an_unchanged_derived_preinstall_is_not_re_stamped_every_run`, which keeps the state file still, and
`test_a_failed_wiki_read_is_not_retried_every_run_for_a_complete_block`, which keeps a down wiki from being hit on every run.
`test_the_shipped_zzz_33_override_repairs_the_card_that_was_switched` loads `config/overrides.json`
itself. If one of them fails after a change to `merge()`, `apply_banner_feed()` or `apply_gacha_wiki()`, the lock is
what you broke.

The notice reader's dialects are pinned in section E of `tests/test_schedule_epithet_and_settled.py`
(the ZZZ 3.3 X-channel bug of 2026-10-09): `test_zzz_x_channels_tweets_yield_agents_not_channel_titles`
(the two real tweets, via the trimmed `api.fxtwitter.com` fixtures `fx_zzz_3_3_channels_phase1/2.json`),
`test_zzz_hoyolab_channels_notices_keep_reading_bare_agents` (the V3.2 HoYoLAB notices,
fixtures `hoyolab_zzz_46604530/46863847_full.json`, reading exactly as before),
`test_channel_mode_phrase_never_publishes_a_channel_title` (every game's mode phrase, quoted
agent, unreadable-name fallback, the Genshin and Star Rail traps, the WuWa list),
`test_zzz_and_wuwa_bare_lists_survive_the_channel_cut` and
`test_the_wrong_zzz_33_banners_heal_from_the_same_posts` (the live record with the wrong channel
titles, healed in place by re-reading the same two posts, lock unmoved). If one of them fails
after a change to `extract_banner()` or `bare_names()`, the reader is what you broke.

Counts: each plain runner ends with its own `N/N passed` line and every one must be `N/N`; `pytest -q tests`
runs the three files together (the totals are not written down anywhere on purpose — they rot).
The title-search tests sit in `tests/test_smoke.py` before `main()`: title matching (`test_banner_title_match_is_exact_on_version_phase_and_prefix`),
the HSR 4.6 Phase I outside-lookback case, fan-repost rejection, the HoYoLAB search versus `getNewsList` fallback,
the budget and throttle (`test_banner_search_budget_settled_never_frozen_never_and_two_clocks`), the `gather_banner_search` integration, WuWa's Kuro discovery
(fixture `5318`), and the ZZZ bare Phase I title (`test_zzz_bare_phase_one_*`), and the ZZZ 4★ and WuWa 4★ extraction.

`TEST_MODE=1` labels the cards 🧪 TEST and skips the state file; `DRY_RUN=1` builds and logs them
without posting. Locally the two are the equivalent of the workflow's test modes.

---

## What to improve next (suggestions)

| Idea | Why | Effort |
|---|---|---|
| **4★ / banner names from official notices and the wiki** (current) → fill gaps with `config/overrides.json` | HoYoverse often shows banners only as images; overrides are the reliable fix, and the card is edited silently | 1 min per version |
| Add **seria / Open Gacha Codes** for HNA / ANANTA at launch | Fandom wikis, official X/Reddit, and community Reddit witnesses already feed them today (plus `hoyolab:9` on HNA); validator APIs add new games after launch | small (`games.json` only) |
| Add a free uptime check (e.g. healthchecks.io) pinged at the end of each run | a second alarm besides cron-job.org emails | small |
| Re-check the nitter fleet every few months (as in News-Express) | nitter instances come and go; X is the main WW source | small |
| More games supported by Open Gacha Codes (Arknights: Endfield, Neverness to Everness) | the code API already has them | small (`games.json`) |


## Official news: offline coverage and read-only checks

Current throughput regressions cover more than 20 completed articles across games,
more than ten attempts with early failures, publication ordering despite an old
attempt cursor, continuation to later games, failed-article retry without reset,
future/stale holds, repeat-run dedup and ignored legacy cap settings. These are
constructed runner cases, not source captures or live deliveries. Existing
500-record admission safety and source-pagination bounds remain covered.


The existing smoke runner now covers news opt-in/no-fallback routing, the five
games, official list/full-body shapes, ordered HTML/Quill content, GIF/video
links, full fitting articles / single-container labelled overflow excerpts,
final-container-only emoji buttons, omitted unknown timestamps, list/heading
formatting, `●`/`•` bullet conversion, overflow-only half-word excerpts,
masked links/self-labelled URLs, real-fixture heading boundaries, publisher
fallback preservation, nested/adjacent bold spans and media boundaries,
closing-star padding, idempotent marker/list spacing, nine-image single-container
retention without regrouping, bounded media preflight, XML-error rejection, preserved queries,
redirect rejection, official-refresh recovery and unresolved-media holds. Silent
baselines, single-message retries, legacy partial holds, source failure isolation,
peer progress and safe cleanup remain covered.
The normal three runners and pytest remain the automatic gates; no new test file
or workflow is introduced.

`python -m gamexpress preview --kind news --out <scratch-directory>` builds clearly
labelled **offline samples** for the five games. These are not live articles or
playback evidence. News samples are deliberately excluded from `test-card all`;
`test-card --kind news` posts nothing. `TEST_MODE` does not post news.

For an explicitly opted-in installation, `python -m gamexpress run --only news
--dry-run` uses read-only source requests and in-memory delivery progress; no
Discord sends or state persistence occur. On an uninitialised state it demonstrates
only baseline discovery, not a complete article or later delivery. Read the
source/full-response body and media independently before enabling production;
never erase an existing baseline or copy development state into a live repository
to force a test. Official-host read-only verification and Discord playback remain
separate from offline test success. No production posts were made during implementation.


## Current official-news paging policy (supersedes earlier one-message-only wording)

Keep fitting full articles unchanged in one message (possibly multiple containers).
By default (`NEWS_EXPAND_FULL=0`), if that fails, permit at most two actual messages
when normalized source text plus title/byline once is `<= 7,000` characters and both
payloads validate independently against 4,000 text characters / 40 components /
1–10 gallery items. When `NEWS_EXPAND_FULL=1`, full articles expand across multiple
validated pages up to `NEWS_EXPAND_MAX_PAGES = 12` (`NEWS_EXPAND_MAX_CHARS = 120000`,
`NEWS_EXPAND_MAX_MEDIA = 120`),
degrading to a clearly labelled `Excerpt — …` single message only if the safety bound
is exceeded or a single indivisible block cannot fit.

### Reproducible offline benchmark (`python -m gamexpress benchmark`)

Run `.venv/bin/python -m gamexpress benchmark --iterations 300` (add `--json` for
machine-readable output) to inspect exact git revision + clean-tree provenance,
Python/platform details, fixture sizes (`short=341c`, `medium=4,926c` 2-page `<=7,000`
policy, `long=12,348c` + `18` media), default-off parity & timestamp-parser bypass
checks, separated derived/mocked protocol counts vs measured local CPU timings
(`median`/`mean`/`p95` µs), and higher expanded-mode media/webhook/pacing costs.

To exercise feature 5 while preserving its production default, add `--beta-enabled`:

```bash
.venv/bin/python -m gamexpress benchmark --iterations 300 --beta-enabled --json
```

That flag constructs a separate in-memory `BETA_ENABLED=1`,
`BETA_GAMES=genshin,starrail,zzz,wuwa` context and runs the **actual enabled beta monitor path**
for each released game: manifest/changelog or manifest fallback discovery, all four detail parsers,
image preflight, Components V2 validation, multi-page send/state settlement, retained revision
comparison, deduplication and explicit quiet-revision handling. The deterministic fixture also
exercises failed and ambiguous first-page holds plus a resumed multi-page batch. Its injected
sleeper records the exact five-second gaps required only between newly successful pages, so the
suite does not idle five real seconds.

Read `beta_enabled_fixture.pipeline` in JSON output for this semantic evidence: fixture source and
webhook collaborator counts plus state-save transitions, while `live_source_requests`,
`live_webhook_posts` and `physical_state_writes` are all zero. It does **not** opt in the monitor,
mutate the process environment, query a live database, send Discord traffic or write a state file.
`beta_enabled_fixture.render_microbenchmarks` separately retains the eight synthetic new/revision
renderer timing cases (with per-item galleries); those timings supplement rather than replace the
full feature harness. The default command remains the existing 12-case default-off news benchmark.


The variable-beta-page regressions additionally exercise **5, 12 and 21 actual renderer pages**,
including a failure on page eleven, a disk reload after ten confirmed messages, exact remaining
page delivery without duplicates, persisted IDs before every send, first-page-only pings and
settlement only after the final page. Complete-output fixtures validate all four released games
with more than ten pages, all 24 parameter rows, long equipment text in order, 14 changed skill
blocks plus a removed block, and all stat/effect changes. Oversized unbroken character/stat/equipment
text must split without loss, an oversized payload or a loop. Boundaries stay mocked; these checks
do not certify live Discord playback. See [beta page counts](CONFIGURATION.md#beta-page-counts).



### Latest layout corrections: 7,000 eligibility / final-container controls

This is the current rendering rule across all five games. The eligibility ceiling
is now 7,000 normalized source-text characters including title/byline once, with
at most two actual Discord messages; every message must independently validate
against the unchanged 4,000 text-character and 40-component caps. Failure to fit
safely in two messages still uses the existing one-container/one-lead excerpt.
All three custom-emoji buttons appear only at the end of the final container of
the final message, including one-message/multi-container articles. Keep Part 1/2
and Part 2/2 for containers in one message, Page 1/Page 2 for separate messages.
Compact consecutive square (■) entries like numbered lists. HTML list items
containing nested paragraphs must keep '- ' attached to their first visible text;
fix parser block boundaries, not source-specific wording. Source HTML/API/mirror
responses and media URLs remain untouched. Schedule extraction/mirrors never suppress
eligible official news articles, while existing `"status": "posted"` state records and
`floor` watermarks prevent historical backfill without state resets.
The one integrated HTML contains the main previews and complete browser-only
long-strip laboratory; optional backend grouping is implemented below.

Backend grouping regressions cover both modes on all five games, image-header
formats, bounded reads/redirects, failures/deadlines, strict ratios, lead/final
images, mixed media, all boundaries, ten-item caps, immutable source items/order,
validated budgets, unchanged excerpts, runner delivery and partial-signature holds.


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
mid-partial delivery without reviewing that hold. Conservative stop-and-hold recovery
is explicitly enabled for official news and maintenance alerts. Existing schedule/code
retry behavior remains at the pre-PR baseline (`stop_on_ambiguous=False` by default
across `schedule`, `codes`, and CLI `WebhookClient.send()` callers). Specifically,
for `runner.run_news` (`stop_on_ambiguous=True`) and `maintenance.run` (`stop_on_ambiguous=True`),
indeterminate webhook `POST` outcomes (response timeouts after dispatch, post-connect
socket resets, `2xx` response-body read errors, or `2xx` responses lacking `"id"`) return
`ambiguous=True` immediately after 1 attempt without blind retry
(`test_correction_6_ambiguous_post_no_replay_and_state_durability` and
`test_final_acceptance_baseline_parity_shared_callers_and_template`), preserving
confirmed `messages` IDs in `state.json` and holding across restarts and peer merges
while keeping definite pre-send connection errors, `429` rate-limit backoff, explicit
`4xx` rejections, and idempotent `PATCH` edits intact.
No state reset or old-post edits.
Discord controls thumbnail cropping; neither header measurements, HTML previews
nor passing offline tests prove live media decoding/readability or delivery.

### Captured live beta equipment and restart regressions

`test_feature5_captured_live_equipment_schemas_render_values_without_tokens` uses
`tests/fixtures/beta/*_live.json`, captured from the recorded public source URLs on
2026-10-25. Fixtures retain relevant source fields (large unrelated fields and intermediate
WuWa levels are omitted). It checks HSR promotion lists and refinement/set parameters,
Genshin published weapon ATK, WuWa percentage units and missing-parameter labels, and nested
localized names. These are offline regressions, not proof of live Discord rendering.

`test_feature5_partial_delivery_holds_changed_payload_and_batch_after_restart` reloads a
real temporary state file after one confirmed page and one failed page. It checks that a
newer manifest cannot skip the unfinished source build and that changed content or batch
membership cannot reuse the old page cursor. Peer merge tests also reject conflicting
payload signatures.

### Bounded snapshot comparison regressions

`test_feature5_long_snapshot_comparison_tracks_full_content_without_false_diffs` exercises
actual build/settlement and a disk state round-trip: unchanged clipped character/equipment
text stays quiet, suffix-only changes remain visible, legacy records rebaseline conservatively,
and rendered payloads remain valid. `test_feature5_replaced_blocks_preserve_surplus_removed_lines`
covers removal of surplus old stat/equipment lines within a replacement block. Both reproduced
failures before repair; the existing numeric-direction tests continue to cover complete baselines.

`test_feature5_ww_3_8_3_second_revision_is_a_real_before_after_not_a_kit_dump` reproduces run
#2880: a 40-line Forte Circuit, two revisions, and a disk round-trip. It asserts the 3.8.3 card
diffs instead of reprinting (the golden `~~74.28%~~ → **63.62%**` pair, the untouched 40 lines
absent, the unchanged RC4 block omitted entirely), that the header reads `Rev. 3.8.1 → 3.8.3`,
and that every page still validates. `test_feature5_clipped_snapshot_rebuilds_the_previous_revision_instead_of_a_kit_dump`
plants a legacy 32-line-capped snapshot and proves the previous revision is rebuilt for the diff;
`test_feature5_rebuild_that_matches_the_current_kit_is_not_a_baseline` serves the current kit on
the old revision path and proves the card stays a labelled full snapshot rather than an empty
"no changes" post. `test_feature5_header_range_uses_versions_then_build_ids_and_never_fakes_a_pair`
covers the version pair, the same-version build-id pair and the fallback.

### Encore beta fallback regression coverage

Captured `encore_{hsin,suoming,lily,weapon}_live.json` fixtures retain relevant API fields and
source URLs/build metadata (2026-10-25). Unused fields are removed; property rows retain only
Lv.1 and Lv.90. Tests cover actual bounded build fallback for character/weapon, valid payloads,
Lv.10 array selection, HTML cleanup, chain text, unavailable values, correct beta links and
provider metadata, healthy primary zero-extra-call behavior, version mismatch, changing build,
malformed metadata, wrong item identity, older revision rejection and both request ceilings.
The actual-build regression failed against c54da29 before the adapter was present. Hsin and
Suoming fixtures demonstrate readable beta API skills/attributes and all six chain nodes;
they do not reconstruct their historical beta revisions.

Two secondary-endpoint regressions reuse the shared captured display schema, independently
compared against both live server responses. They cover unavailable/unreadable/changing primary
responses recovering through the legacy server with identical payloads and snapshots, healthy
primary zero-backup traffic, same-server metadata bracketing, wrong versions/IDs, changing builds,
batch consistency, local/shared request boundaries and durable quiet settlement after reload.
Both tests failed before the secondary endpoint was implemented. Live API schema/metadata checks
remain separate from these offline tests; no Discord writes are used.

A synthetic future `4.0.1` lifecycle test starts from live `3.7`, holds stale Encore
`3.8.1`, retries the same manifest after a matching update, validates the rendered payloads,
and round-trips settlement through disk to prove repeat runs stay quiet. Released Hsin/Suoming
IDs are not requested when absent from manifest new IDs and retained snapshots. This tests
version-independent behavior; the fixture reuses Lily's captured kit and is not real 4.0 data.

Gachabase HTML regression: `test_feature5_gachabase_html_revisions_and_changed_existing_ids`
uses a reduced SSR fixture to cover changed existing IDs, relative links/entities, category and
diff pairing, script/style exclusion, blank versus explicit quiet revisions, and error pages.
Public-source smoke checks are separate read-only checks, never part of the offline suite.

## 2026-10-29 update verification

Author-session verification on Python 3.11.2, based on main `5f20422` and the
implementation reviewed from draft PR #83 (`e581968`). The current session stays
on `arena/fb3eb040-game-express`; it does not modify that earlier PR's branch.

- `python -m compileall -q gamexpress tests .github/scripts`, `python -m gamexpress validate`,
  `python -m gamexpress preview --out <temporary-directory>`, `ruff check .`, and
  `git diff --check` passed.
- Standalone smoke: **506/506**, schedule regressions: **20/20**, placeholder:
  **3/3**; `python -m pytest -q`: **529 passed**. These are overlapping runner
  totals, not 1,058 distinct tests.
- New guards exercise unofficial/Miliastra authors, historical quoted title
  reconstructions, privacy-enhanced YouTube video exclusion, and best-effort
  workflow-summary writes. All-six-game milestone tests use explicit operator
  timings with cadence disabled, mocked source/webhook boundaries, exact
  pre-start/start decisions and real temporary state reloads. Existing tests
  separately cover cadence, official precedence, extensions and postponements.
- Read-only GitHub API checks found successful production runs: Game
  `40832660096`, Twitter `40832670145`, Reddit `40832659879`. Downloading their
  logs failed at the Actions log host under this environment's network policy;
  successful run status is **not** a complete log/annotation or delivery audit.
- Replayed production state blob `53e4aed12dcbe1386c9fb49e9c8379ff3112c9f1`
  through `maintenance.resolve_version_plans` at `2026-10-29T12:00:00Z`, without
  new official inputs or overrides. Upcoming **estimated** preload/maintenance
  starts (UTC): GI Nov 2 03:00 / Nov 3 22:00; HSR Nov 9 06:00 / Nov 10 22:00;
  WuWa Nov 10 02:00 / Nov 11 20:00; ZZZ Nov 30 04:00 / Dec 1 22:00. HNA and
  ANANTA produced no dates. This proves retained-state decisions, not current
  upstream availability, enabled production destinations or future delivery.

### Local CPU benchmarks (not live latency)

Executed `python -m gamexpress benchmark --iterations 100 --json` against both
an isolated `git archive 5f20422` export and the updated tree on the same host.
Selected medians in microseconds (base → updated):

| Case | Base | Updated |
|---|---:|---:|
| Short news, default off | 96.16 | 96.05 |
| Medium news, two pages | 572.28 | 573.94 |
| Long news, expansion off | 1791.71 | 1795.37 |
| Long news, expansion on | 2274.52 | 2300.72 |
| Long news, expansion + timestamps | 6831.73 | 6734.98 |

Default-off output parity passed; timestamp converter calls when disabled: zero.
A separate 10,000-call `classify_character_reveal` measurement on the reconstructed
`Extraterrestrial Satellite Communication | Ellen` static-title fixture measured
26.55 µs median / 50.72 µs p95. Production-state resolver replay medians over
100 calls/game were GI 215.85, HSR 211.44, ZZZ 125.19, WuWa 99.74, HNA 2.40,
ANANTA 2.42 µs. Timed regions performed no HTTP, webhook or production writes.
Small differences are host noise, not an end-to-end speed guarantee.

**Release limits:** historical 2,179-post precision/recall figures from the linked
report are not independently reproduced; unfamiliar future formats and incomplete
rosters remain heuristic limitations. No production workflow dispatch, Discord
playback test, production sync or merge was performed. Twitter's optional 350 MiB
handoff remains separate and off by default; higher limits are not proof of proxy
playback reliability. Final-head CI and workflow annotations must be reviewed on
the PR before release.

### 2026-10-29 follow-up — timing phrases, reveal dedup and edit safety

Verification for the delta on top of the revision above (same offline suite, Python 3.11.2).

- `python -m compileall -q gamexpress tests .github/scripts`, `ruff check .`,
  `python -m gamexpress validate`, `python -m gamexpress preview --out <temp>` passed.
- Standalone smoke **512/512**; `python -m pytest -q tests` **535 passed** (overlapping
  totals, not 1,047 distinct tests). Schedule regressions and the placeholder guard unchanged.
- New guards and the requirement each pins (each fails on the pre-delta code):
  `test_maintenance_window_phrasings_are_read_for_every_game` (`updated and maintained at …`,
  clock-only end after a dated start, clock-only extension, reschedule that quotes the abandoned
  window, `will not be postponed`, all six game keys);
  `test_reveal_ping_edit_guard_skips_reflow_and_lost_mention_instead_of_truncating` (a CMS edit
  that would need a continuation page is held, not published truncated);
  `test_reveal_ping_collapses_a_full_name_variant_but_not_a_different_character` (corroborated
  aliases collapse; `March` / `March 7th` and `Saber` / `Saber Alter` do not);
  `test_reveal_ping_form_names_collapse_to_one_character_after_a_real_commit` (form suffixes and
  the legacy `Profile Reveal:` separator).
  The YouTube test now also covers trailing-slash and `/watch/` player URLs.
- Real-corpus replay (read-only clones, no network at test time, not committed):
  - **Wuthering Waves**, all **712** official Kuro website articles
    (`TheLovinator1/wutheringwaves`, 2023-02 → 2026-10):
    **97** classifier matches over **57** unique characters (`61` `Profile Reveal` — including the
    15 archived `Profile Reveal:` titles, `34` `Stars Intertwined`, `2` `Resonator Reveal`).
    Every match is a reveal-series title — **0** title-series false positives and **0** unmatched
    labelled titles. `Rover: Aero` / `Rover: Electro` share one key, as do
    `Yangyang: Xuanling` / `Yangyang`.
  - **Genshin Impact**, **1,185** in-game notices (`KQM-git/GINews`, 2020 → 2026):
    **0** matches — no `◆` bullet list, version notice or top-up notice is mistaken for a reveal.
  - Corpora are unlabelled outside their own series titles; these are precision/recall proxies
    against publisher titles, not the earlier report's 2,179-post figures.
  - Cost: 141 µs/article (WuWa) and 167 µs/article (Genshin) including HTML body extraction on
    this host, with zero HTTP inside the classifier.
- `python -m gamexpress benchmark --iterations 300` on the clean head (Python 3.11.2):
  short news default-off **93.06 µs** median, medium two-page **588.02 µs**, long
  expansion-off **1738.38 µs**, long expansion-on **2256.49 µs**, both-on **6522.99 µs**;
  token formatting 1.60 µs, `strftime` 16 epochs 26.64 µs. Default-off invariants:
  `output_equal=True`, `main_1e071d8_sha256_equal=True`, timestamp-parser calls when
  disabled **0**, extra HTTP/webhook **0**. Protocol counts stay at 1 message / 1 media GET
  / 1 POST for short news, 2 / 1 / 2 for the medium fixture and 4 / 18 / 4 with expansion on.
  `--beta-enabled` (local-only) still renders 16 pages with 0 live HTTP and 0 webhook posts.
- Read-only production replay of the live state blob at `2026-10-29T12:00:00Z`, with no live
  inputs and no writes: the four released games resolve an upcoming **estimated** preload /
  maintenance pair (UTC) — GI Nov 2 03:00 / Nov 3 22:00, HSR Nov 9 06:00 / Nov 10 22:00,
  WuWa Nov 10 02:00 / Nov 11 20:00, ZZZ Nov 30 04:00 / Dec 1 22:00; every settled milestone
  stays outside the 12 h delivery window, `postponed=False`, and HNA/ANANTA produce no dates.
- Live production observation (not a test): the three prod repositories' latest runs are green
  (Game `40838508714`, Twitter `40838524872`, Reddit `40838516409`). Their check-run annotations
  contain only GitHub's Ubuntu-migration notice — no warning or error annotation. This is a
  status/annotation check, not a delivery or playback audit.
- Run summary location: `test_run_summary_never_writes_into_the_operator_notes_folder` proves the
  monitor never reads or writes `polishing and refining/`, that the live commit step stays plain
  shell staging only `state/state.json` and `config/program_announcements.json`, and that it always
  publishes its own persistence result (`unchanged` / `pushed`) for the summary step.
- Credit hygiene is now pinned: the documentation-hygiene test asserts that `docs/CREDITS.md`
  keeps the [HoyoPlay](https://gist.github.com/DynamiByte/0ad250bbe1930e2736a6d4e6e842bcb2) and
  [WuWa launcher](https://gist.github.com/DynamiByte/d839bf9f671c975b6666d0f6e6634641) endpoint
  notes and [Cheu3172/Wuwa-Web-Request](https://github.com/Cheu3172/Wuwa-Web-Request), so the
  launcher adapters can never silently lose their attribution. A host sweep of the runtime code
  (113 hosts) found no other uncredited provider: the remainder are Discord's CDN, the jsDelivr
  mirror of an already-credited code list, a short-link resolver, the donate button, video-host
  exclusions and a test-only `fixture.invalid`.
- The CMS-edit guard retries instead of abandoning: a held edit is applied on the next run once the
  article fits again (`test_reveal_ping_edit_guard_skips_reflow_and_lost_mention_instead_of_truncating`).
- `tools/live_news_probe.py` (developer tool, read-only: no webhooks, secrets or state writes)
  repeatedly checks one game's current discovery window for reveal matches and mention fit.
  The suite only verifies that it exists and rejects a missing or unknown game argument, so a
  test run never reaches the network.
- Limits: no live-source availability and no Discord playback test were performed in this
  session; unfamiliar publisher formats and incomplete historic rosters remain heuristic.
