# Testing Game-Express: is everything working?

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

The PR's **CI — compile + offline tests** check must be green. It runs the whole offline suite, which
cover:

- the real official posts, which must reproduce your reference cards' timestamps;
- the golden cards, Discord limits, the code gate, 4★ TBA, fail-over, and the workflow files.

CI needs no secrets and no network.

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
| **Banners** show the real characters per phase (e.g. `Escoffier`, not `Tasteful Excellence`) | the `"Banner Title" Character` reader, if the banner notice is inside the lookback |
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
pip install -r requirements.txt pyyaml
python tests/test_smoke.py                 # the full offline suite
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

Counts: the CI runner `python tests/test_smoke.py` runs 251 tests (all must pass). `pytest -q tests` runs 269:
those 251, the 15 in `test_schedule_epithet_and_settled.py` and the 3 in `test_gachawiki_placeholder.py`.
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
| Add **HNA / ANANTA code sources** at launch (seria / Open Gacha Codes add new games quickly) | only official posts and X feed them today | small (`games.json` only) |
| Add a free uptime check (e.g. healthchecks.io) pinged at the end of each run | a second alarm besides cron-job.org emails | small |
| Re-check the nitter fleet every few months (as in News-Express) | nitter instances come and go; X is the main WW source | small |
| More games supported by Open Gacha Codes (Arknights: Endfield, Neverness to Everness) | the code API already has them | small (`games.json`) |
