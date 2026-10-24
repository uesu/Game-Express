# AGENTS.md — orientation for AI agents and future sessions

Documentation housekeeping: verify Setup, .env.example and ignore rules against current
config/workflow behavior. Keep root features under What it posts, detailed instructions in
docs, update docs/README.md, and keep root Legal & credits LAST. Never publish live secrets,
reset state, change schedules, or promise a no-op/repair merely because docs changed.

## Attended workflow updates

Eligible package-only Dependabot PRs retain opt-in auto-merge. Any PR changing
`.github/workflows/` (including a rename from that directory) waits for manual
review/merge. All Python update PRs are also attended; the legacy
`AUTO_MERGE_PYTHON_BUMP` variable is ignored. Do not auto-approve GitHub security
holds. After a live-workflow update, confirm a real monitor run starts/completes;
a successful dispatch or PR CI is not proof of live execution. A hold can still
occur: this policy reduces unattended exposure, not the security gate itself.

### Evidence-Driven Maintenance, Acceptance and Workspace Hygiene

Continue the specified existing PR with concise diffs and no extra standalone audit markdown files.

- Establish the task, assigned branch, current PR/base/head and dirty work before editing. Preserve unrelated changes and authorization boundaries.
- Inspect actual references, complete relevant diffs, shared helpers and affected callers. Distinguish observed facts, inference, raw captures, reconstructions, screenshots, author reports and independently executed evidence.
- Implement the smallest complete generic correction. Preserve existing defaults, source wording/order/media and unrelated behavior. Avoid unrequested rewrites, cosmetic churn, global unescaping and broad new frameworks.
- Test actual decisions with mocked external boundaries. Assert outgoing content/media/link slots, request counts, results and durable state where relevant. No vacuous checks, skipped critical assertions, permissive alternatives or weakened coverage.
- Run focused tests followed by documented relevant suites and final-head CI. Record exact commands/results/revision. Distinguish required checks from advisory jobs, committed coverage from ad-hoc checks, and stored baselines from actual baseline execution.
- Measure performance reproducibly when required. Separate CPU work from network/pacing costs. Do not promise zero overhead or live reliability.
- Keep active developer documentation, examples, `AGENTS.md` and acceptance reports consistent with committed code, tests, defaults, bounds and limitations. Preserve provenance and historical evidence. Respect production documentation exclusions.
- Return **READY TO MERGE**, **CHANGES REQUIRED** or **REVIEW BLOCKED** for each PR. Tie acceptance to the exact head and disclose author-session versus independent review. Fixed findings do not automatically establish complete review; acceptance is not deployment authorization or a zero-bug warranty.
- Keep resolved findings closed absent contradictory evidence. Review incremental changes without unnecessarily restarting unrelated work. Do not manufacture blockers from optional nits or maintain an endless acceptance loop.
- Reuse bounded task-scoped temporary artifacts. Avoid repeated clones, archives, generated previews and duplicated logs. Inspect capacity early and retain concise durable context with exact revisions, commands, results, blockers and next actions.
- Clean only verified disposable task-owned artifacts after inspecting status, ownership and retention needs. Never remove the repository root, `.git`, dirty user work, tracked fixtures, source captures, state or durable handoffs/evidence. No broad destructive cleanup as a capacity workaround.
- If a snapshot/storage/tool limit blocks execution, report whether commands ran. Do not repeat identical blocked calls or claim writes/deletions succeeded. Request platform intervention or use a compact handoff when safe cleanup is impossible. Never promise automatic cross-session memory or unlimited storage.
- Separate editing, committing/pushing, PR updates, merging, deployment, workflow dispatch, live API writes, state resets and production switch changes. Obtain the required authorization for each.
- Update the PR title, PR body, and benchmarks **only** when those specific items actually changed; if nothing changed, keep them as-is so full prior details remain completely visible. Always publish session comments, verification results, and findings directly in the PR thread as well so every change preserves complete details for future reference.

## Operational summary output

Use the existing `runner.py::write_summary`; do not introduce a second reporting
module or lifecycle wrapper. Keep source counts/timing, sanitize summary and
annotation text, and let output-write failure remain best effort. An empty
report does not prove source health or absence of eligible items. Local state
save/application completion cannot certify the workflow's later commit/push.
Keep reporting tests in the existing smoke runner; preserve cards, source order,
announcement/code eligibility, timing and state behavior.

Read this **before changing anything**. It is the short version of how Game-Express works, which
behaviours are deliberate (and must not be "fixed"), how to verify a change, and which traps have
already cost a broken run. `README.md` is the user-facing manual and `docs/` is its reference
material; this file is the maintainer's mental model.

Last updated **2026-10-24**.

---

## 1. What this repository is

A **GitHub-Actions-only** monitor. No server, no daemon, no Discord bot, no container.
`.github/workflows/monitor.yml` is dispatched by cron-job.org every 5 minutes; one run fetches
official sources, decides whether anything is new, posts **Discord Components V2** cards through
**webhooks**, commits its state, and exits. A run takes ~25 s end to end (~5–6 s of that is the
Python).

Four independent features: **`schedule`** (version/Special-Program cards) and **`codes`**
(redemption-code cards) on by default, plus explicit opt-in **`news`** (`NEWS_ENABLED=1`, full
official articles for five games) and **`maintenance`** (`MAINTENANCE_ENABLED=1` +
`MAINTENANCE_GAMES`, independent `Pre-Load Started` and `Maintenance Started` cards). Six games:
`genshin`, `starrail`, `zzz`, `wuwa`, `hna`, `ananta`.

**There is no Discord bot and there must not be one.** A bot existed long ago; it was removed in
v1.7.0, the last hosting artefact (`.dockerignore`) went in PR #20, and the legal docs were
cleaned of slash-command language in v1.9.0. `gamexpress/discord.py` is an HTTP webhook client —
nothing more. Do not add `discord.py`, a token, a gateway, or any always-on process.

---

## 2. Repo map

| Path | Role |
|---|---|
| `gamexpress/__main__.py` | CLI: `run`, `test-card`, `check-webhooks`, `preview`, `speculate`, `validate`, `benchmark` |
| `gamexpress/runner.py` | builds `Ctx` (settings, games, state, fetcher, webhook, X client, Reddit client), fail-over, `run_news`, `maintenance.run`, run summary |
| `gamexpress/schedule.py` (the largest module by far) | the brain: picks the announcement, parses times, locks banners, speculates a cycle, builds/edits the schedule card |
| `gamexpress/codeposter.py` | the code gate (families, validators, min-sources), posts/edits code cards |
| `gamexpress/maintenance.py` | fourth feature (off by default): independent `Pre-Load Started` & `Maintenance Started` cards, `official > override > observed > cadence` precedence, 4-tier version-verified launch media, corroborated signed URL renewal/fallback, silent seed & bounded late `PATCH` |
| `gamexpress/news_timestamps.py` | single-pass `O(N)` render-only news timestamp converter (`NEWS_TIMESTAMPS`, off by default) |
| `gamexpress/cards.py` | Components V2 payload builders (`schedule`, `codes`, `news`, `maintenance`) + `validate_payload` |
| `gamexpress/discord.py` | webhook POST/PATCH, 429/5xx retries, `WEBHOOK_SPACING = 1.2 s` pacing |
| `gamexpress/http.py` | shared `aiohttp` fetcher, `MAX_PARALLEL = 12`, per-source health counters |
| `gamexpress/state.py` | `state/state.json` (`SCHEMA = 1`): posted keys, message ids, bootstrap flags, heartbeat |
| `gamexpress/config.py` | `Settings` (env) + `Game` (games.json) + `game_is_on` / `active_games` |
| `gamexpress/sources/*` | one module per upstream: `twitter` (nitter fleet + FxEmbed), `reddit` (Redlib fleet + `reddit.com` feed token + rich-embed proxies), `hoyolab`, `kuro`, `codes`, `launcher`, `bannerfeed`, `calendarfeed`, `gachawiki`, `banner_search`, `countdown`, `newspage` |
| `gamexpress/{models,media,textutil,timeparse,samples,preview_html}.py` | the `Item` / `CodeHit` dataclasses, image URL normalisation, HTML→text, date/time parsing, sample cards, local preview |
| `config/games.json` | per-game config (see §4) · `config/overrides.json` human corrections · `config/program_announcements.json` discovered tweet ids |
| `tests/test_smoke.py` | the main suite: every test offline — no network, no secrets |
| `tests/test_schedule_epithet_and_settled.py` · `tests/test_gachawiki_placeholder.py` | the 2026-10-08 schedule regressions (the first also runs in a checkout with no dependencies installed) and the ZZZ 3.3 "Agent" placeholder guard. Every test file has a plain runner and **every one is a CI gate** — `test_ci_and_the_python_bump_gate_run_every_offline_test_file` fails the moment a new file is not wired into `ci.yml` and the python-bump gate |
| `docs/` | the manual, indexed in `docs/README.md`: `CONFIGURATION`, `ACCURACY`, `SOURCES`, `BANNER_DATABASE`, `SCHEDULER`, `ROLLOUT`, `TESTING`, `TROUBLESHOOTING`, `SECURITY`, `TIMESTAMP-PATTERNS`, `DEPENDABOT`, `PYTHON_VERSION`, `PROD-REPO-SETUP`, `CREDITS` |
| `docs/changelog/` | `CHANGELOG.md` (1.8.0 →) + `CHANGELOG_ARCHIVE.md` (1.0.0 – 1.7.0) + an index; the full history lives here — the README's Changelog section is a pointer to it. |
| `.github/workflows/` | `monitor.yml` (production), `ci.yml` (tests + advisory job), `python_version_bump.yml`, `sync_prod.yml` (dev → prod sync) |

---

## 3. Invariants — deliberate behaviour, do not "fix"

1. **`monitor.yml` must keep `cancel-in-progress: false`.** A run can sit between "posted to
   Discord" and "state committed"; cancelling there causes a double post. `ci.yml` *does* cancel —
   that is fine and intentional.
2. **Actions stay SHA-pinned.** `uses: owner/repo@<40-char sha>  # vX.Y.Z`. Never "tidy" a pin
   back into a tag — tags are mutable and have been weaponised (CVE-2025-30066). Dependabot
   maintains both halves.
3. **Scraped URLs go through `cards.safe_url()`, always.** Everything a card links to comes
   from somebody else's server. `safe_url` keeps http(s)-only, strips nothing silently but
   rejects control characters, caps URLs at `SAFE_URL_MAX = 1024`, and percent-encodes
   parentheses so a `)` cannot close a markdown link early and inject a phishing line.
   `link_button()` additionally enforces Discord's stricter `BUTTON_URL_MAX = 512` limit and
   returns `None` deliberately so an oversized or invalid link drops only that button (and
   empty Action Rows are never emitted), still posting the card. See `docs/SECURITY.md` §2.
4. **GitHub's native `schedule:` stays disabled.** Two schedulers raced in News-Express and
   double-posted. cron-job.org is the single trigger.
5. **The first run for a new game/feature seeds silently.** `BOOTSTRAP_POST` off = record what
   exists, post nothing. Never "fix" this into a backfill.
6. **Only an announcement opens a schedule card, and an already-aired programme never opens one.**
   A *Special Program* / *Special Broadcast* creates the card; maintenance, pre-install and banner
   notices may only fill in a card that already exists (`fresh_maint` requires a `program_ts` or
   `program_seen`). A version whose programme is in the past is tracked and kept current but never
   carded — the creation gate consults `program_settled()`, which settles on the air time **or** on
   `maint_start_ts + 12 h`, because a record opened by a notice never has an air time. That is what
   keeps every version released before this bot was deployed (Genshin 7.1, Wuthering Waves 3.7) out
   of the channel. `mode=test` and `REPOST=<game>:<version>` are the only two overrides. Both gates
   have tests that fail without them, in `tests/test_smoke.py` and
   `tests/test_schedule_epithet_and_settled.py` — do not "simplify" either away.
7. **Posting is once per (game, version) / per code**, then *silent edits* of the same message id.
   The state's message ids are what make an edit possible — never clear them casually. A
   `404`/`10008` means an id stopped resolving, not that a human deleted anything: a
   still-current card is re-created once, a settled one is dropped and never published again.
   The settled-card branch drops the primary id from the record and still names it in the summary
   using local `mid`. For a settled mirror,
   a recorded copy id that returns 404 is named in `🗂 … copy <id> was deleted (Discord 10008)`;
   if no copy id was recorded, the shorter `— already out` line is used. These are report
   phrasings: the response establishes that the id no longer resolves, not who removed it. Keep
   both lines covered by `test_a_settled_program_is_never_re_created_on_a_live_run` and
   `test_a_deleted_game_channel_copy_says_which_message_vanished`. A test run never edits a live
   card or its copy — it renders a new marked one. The
   optional fan-out copy (`DISCORD_WEBHOOK_<FEATURE>_MIRROR_<GAME>`) obeys the same rule with its
   own `mirror_message_id`, and is edited in the same pass as the original so the two can never
   disagree. Three things about it are deliberate: it has **no `DISCORD_WEBHOOK_URL` fallback**
   (an unnamed mirror must stay off, or filling in the catch-all would double-post everything
   into it); a failed copy is **reported, never an error** — the real card must not depend on a
   convenience channel; and the copy is built with an **empty `Ping()`** so one announcement
   never notifies the same role twice. Never "simplify" that by reusing the primary's payload.
8. **The mention lives INSIDE the container.** A card payload is exactly one top-level
   component. The ping rides on the legend line of a schedule card and the `… detected …` line
   of a codes card — never on a separate Text Display above the card. `_payload()` takes no
   top-line argument; if you find yourself adding one back, you are undoing this. Keep the
   empty-`Ping()` escape hatch working: it must strip the mention *text* as well as the
   `allowed_mentions` entry, or a copy renders a dead blue pill that notifies nobody.
9. **Official times win; estimates are labelled.** Countdown sites and the banner feed may fill a
   gap, but the card says so, and a real official time always replaces them.
10. **Ranking beats speed in the nitter fleet.** `_probe_batch` may stop waiting early, but only
   once enough *higher-ranked* mirrors have answered (plus the `NITTER_GRACE` cap). Do not
   "simplify" it to first-two-to-respond: mirror order is a quality ranking.
   By-id tweet lookups follow the same order: `XClient.tweet()` asks nitter.cf (then xitter.cf) first
   when the account is known, and FxTwitter only after nitter cannot answer or the post has a `t.co`
   link. A status mirror that fails `STATUS_FAIL_LIMIT` times in one run is skipped for the rest of it.
11. **The advisory CI job must never gate a merge** (`continue-on-error: true` on every step). Only
   the `test` job is a required check.
12. **No new runtime dependencies** without a very good reason. The whole app runs on `aiohttp`,
   `feedparser`, `python-dotenv`.
13. **Never commit secrets.** Webhooks, `NITTER_RSS_TOKEN` and `REDDIT_FEED_TOKEN` are repository
   secrets; the state file stores only a 12-char non-reversible webhook fingerprint.
14. **No LICENSE file is wanted** — this is a personal-use repository (owner's decision,
    2026-10-03). Do not add one "for completeness".
15. **A posted Special Program card keeps its announcement.** The first post that gives an air time
   sets `announcement_locked`, and `announcement_source` / `announcement_ts` record which post. From
   then on `merge()` and `apply_program_media()` never move the card's title link, source buttons, key
   art, air time or programme and version names. Only an estimated air time may be replaced, and maintenance keeps updating. The lock goes to the highest `LOCK_RANK` (X 3 over HoYoLAB / Kuro 2
   over news 1), then the earliest post. A card locked to a lower rank moves **once**, to a higher-rank
   post with the same air time that was published no later than the lock. A giveaway never upgrades.
   Records without the flag are locked by `program_seen` or `media_from`, and get no upgrade. Do not
   restore a per-run rebuild from the lookback window: that is how ZZZ 3.3's giveaway took the card on
   2026-10-09. The tests that pin this run from `test_the_announcement_that_opened_a_card_keeps_its_link_and_key_art`
   to `test_a_countdown_estimate_is_replaced_by_the_official_notice_in_every_game` in
   `tests/test_smoke.py`, listed in `docs/TESTING.md`. Known limit: the first program post seen locks the
   card, so a same-window giveaway seen before the announcement still wins. It is documented in
   `docs/ACCURACY.md`, not fixed.
16. **Banners lock on confirmation, and the lock is final against the weaker source.** An official notice
   (`official`) locks its 5★ or 4★ name alone when it parses cleanly. The reader is dialect-aware, for every
   game: a name is read straight after the star-tier phrase, a bare name ends where the game's gacha-mode
   phrase begins (`schedule.CHANNEL_MODE` — signal search, event wish, event warp, convene, …), and a quote
   after that phrase is a channel title, never a character (ZZZ 3.3's X posts quote the channel and name the
   agent bare; 2026-10-09). A hub name (`feed`), an official-calendar name
   (`calendar`, `sources/calendarfeed.py`) and a wiki name (`wiki`) lock once any two of them agree, for 5★ and 4★
   (A-rank) alike and for every game. The calendar is names only, its 4★ lists need the exact rate-up count,
   and `calendar_due()` / `calendar_ts` / `BANNER_CALENDAR=0` govern its requests. An override locks alone. The confirmation is `schedule._confirm()`, the
   lock is `data["banners_settled"]`, and the rule lives in `_official_owned` and `_official_may_write`
   (the owner is the priority that wrote the name). Official names are final against later official notices:
   a different one is logged as a conflict, not applied, and two clean official 4★ lists that disagree
   become TBA. The hub corrects only the hub, the wiki corrects the hub but never an official name, and a
   silent source never erases a value it did not write. A hub title in a phase is corrected even when locked.
   `reruns` and the 4★ summary lock only with the wiki and their phase inputs. Maintenance is not part of this
   and keeps its native behaviour. Traffic: `wiki_recheck_due()` reads an incomplete block (still TBA) at most
   every `WIKI_INCOMPLETE_H` (3) hours, a complete unconfirmed block at most every `WIKI_RECHECK_H` (6), and
   every answered read is stamped (`banners_checked_ts`), so the state file changes at most once per interval.
   Do not put a per-run wiki read back: an incomplete block read on every five-minute run was 288 requests
   a day for the pinned ZZZ 3.3 card.
17. **Banner notices are found by title, for the card's version, whatever their age.** `sources/banner_search.py`
   fills the title templates in `config/games.json` (`banner_titles`, `{v}` = version, `{p}` = phase). HoYoLAB
   keyword search answers first (one request per phase, only posts by `official_uid`), and the paged official
   news list is the fallback; Wuthering Waves reads Kuro's own article menu, with the GitHub Atom mirror only as a
   fallback. Matching is exact on version and phase (`7.1` is not `7.10`, Phase I is not Phase II), and a fan
   repost never counts. A hit is only a candidate for the normal merge: the names are still read from the body,
   and invariant 16 still decides. It runs only through `schedule.banner_search_due()`: a card whose phases are final never (`banner_phases_done()`: each phase's 5★ and 4★ locked), a
   frozen card never, an incomplete block every 3 h, a complete unconfirmed block every 6 h, stamped in
   `banners_search_ts` (its own clock). `BANNER_SEARCH=0` switches it off. No fetcher means no request and no stamp.
---

## 4. Config model you must understand

`config/games.json` — per game:

- **`enabled`** = *do we monitor it*. **`released`** = *is the game out*. They are **separate**.
  `hna` and `ananta` are `enabled: true, released: false` (switched on 2026-10-02 so pre-release
  programs are caught). `released: false` is what `test-card --unlaunched` selects, because an
  unreleased game has no real codes to fetch.
- `auto_enable_on: "YYYY-MM-DD"` — a prepared game switches itself on at launch (kept on `ananta`
  as a safety net even though it is already enabled).
- `youtube` / `twitch` — optional link buttons. Empty `twitch` is a *fact* about HNA and ANANTA,
  not a gap; `cards.py` only renders a button when the field is filled.
- `codes.sources`, `hoyolab.gid`, `x_accounts`, `program_patterns`, `card.show_banners`,
  `four_star_count`.

Environment/variables are resolved in `config.load_settings` with a documented precedence
(`DISCORD_WEBHOOK_<FEATURE>_<GAME>` > `_<FEATURE>` > `DISCORD_WEBHOOK_URL`; same shape for pings).
`monitor.yml` passes **all** repo variables as `GE_VARS_JSON` and all secrets as `GE_SECRETS_JSON`,
so a newly added variable works without touching the workflow.

---

## 5. How to verify a change (exact commands)

```bash
uv venv --python 3.11 && uv pip install -r requirements.txt pyyaml ruff pytest vulture
.venv/bin/python -m compileall -q gamexpress tests .github/scripts
.venv/bin/ruff check .                      # ruff.toml is authoritative
.venv/bin/python tests/test_smoke.py        # must end N/N, 0 failed — the plain runners are what CI uses
.venv/bin/python tests/test_schedule_epithet_and_settled.py
.venv/bin/python tests/test_gachawiki_placeholder.py
.venv/bin/python -m pytest -q tests         # pytest must also pass (all three files in one go)
.venv/bin/python -m gamexpress validate     # routing, pings, card limits -> "config OK"
.venv/bin/python -m gamexpress preview --out /tmp/previews
zizmor .github/workflows                    # 0 findings; config in .github/zizmor.yml
DRY_RUN=1 STATE_PATH=/tmp/s.json .venv/bin/python -m gamexpress run   # end-to-end, posts nothing
```

- **`pyyaml` must be installed** or the workflow-assertion tests silently skip (and a test-count
  claim becomes wrong).
- **Golden cards**: after an *intentional* card change, `UPDATE_GOLDEN=1 python tests/test_smoke.py`.
- **A new behaviour needs a test that fails on the old code.** Prove it:
  `git stash push -- <file>` → run → expect `N-1/N` → `git stash pop`.
- Timing-based tests must have fat margins (CI runners are noisy). Existing ones allow ≥3× slack.

---

## 6. Traps that have already broken a run

| Trap | What happens | Rule |
|---|---|---|
| `astral-sh/*@vN` | **Astral publishes no floating major tag.** `setup-uv@v9` and `ruff-action@v4` both failed with *"unable to find version"*, killing the job at **Set up job** — before `continue-on-error` can apply | every action is SHA-pinned now, with `# vX.Y.Z` in the comment; `test_every_action_is_pinned_to_a_commit_sha_with_a_readable_version_comment` enforces both |
| zizmor suppressions | `# zizmor: ignore[rule]` on the *preceding* line is unreliable | put it as a **trailing comment on the exact reported line** |
| `cache: 'pip'` after the uv switch | warns on every run about a missing `~/.cache/pip` | removed in PR #21; uv has its own cache |
| `setup-uv` with no `version:` | fetches the version manifest over the network every run | `version: latest-known` |
| Hung nitter mirror | `asyncio.gather` waited the full 12 s timeout (run #217: 16.2 s vs 5 s) | fixed in v1.9.0; see invariant #10 |
| Hardcoded chunk size | `codeposter` chunked by `10` while cards used `CODES_PER_CARD` | always import the constant |
| Python 3.14 locally | sandboxes usually cannot download it (TLS proxy); CI pins 3.14 | develop on 3.11, let CI prove 3.14 |
| `actionlint` locally | `actionlint-py` needs a Go toolchain; it will not install | rely on CI's advisory job + `yaml.safe_load` |

---

## 7. Performance notes (measured, v1.9.0)

- Nitter batch early stop: **12.01 s → 0.06 s** on a hung-mirror run; worst case (the hung mirror
  outranks the answers) **12.01 s → 1.56 s** via `NITTER_GRACE`.
- Webhook pacing before (not after) a request: **−1.2 s** on every run that posts.
- `uv` vs `pip` for this `requirements.txt`: **4.5 s → 0.06 s** warm, identical package set.
- Per run: ~55–60 upstream requests, `MAX_PARALLEL = 12`. At the 5-minute cadence that is ~17 k
  requests/day against mostly volunteer-run infrastructure — **politeness, not GitHub, is the
  limit**. See `docs/SCHEDULER.md` → *How fast can it poll?*

### Ideas not yet done (deliberately)

- **Conditional requests (ETag / `If-Modified-Since`)** for `c3kay`, the banner feed, the
  jsDelivr/raw code lists and the Kuro launcher index — the biggest remaining win at a 5-minute
  cadence, but it needs live sources to validate, so do it with real-network testing, not blind.
- **Remember last-known-good nitter mirrors in state** to cut probe count ~50 %. Rejected for now
  because it reorders a quality ranking; if attempted, keep fleet order as the tiebreak.
- ~~**Hash-pin all actions**~~ — **done in v1.9.0.** The earlier rejection ("it conflicts with
  Dependabot") was wrong: Dependabot has updated SHA pins *and* their version comments since
  2022, and a floating major tag actually hides patch/minor movement from it. See
  `docs/SECURITY.md` §5 and CVE-2025-30066. The old reasoning, kept so it is not re-adopted:
  it was thought to conflict with the Dependabot tag-pin
  policy documented in `.github/zizmor.yml` and with a workflow assertion test.
- `MAX_PARALLEL > 12`, shorter retry backoff: rejected, upstream politeness.

---

## 8. Conventions

- **No version numbers — do not reintroduce one.** `build_id()` in `gamexpress/__init__.py`
  reports the short `GITHUB_SHA`, so every run summary already names the exact commit that
  produced it. The old `__version__` needed four files to move in lockstep and went stale the
  first time one was missed. To record a change, add a dated `## YYYY-MM-DD` section at the
  **top** of `docs/changelog/CHANGELOG.md` and its row in `docs/changelog/README.md`.
  Entries up to `1.9.0` keep the numbers they shipped as — **never renumber history.**
- **Docs are part of the change.** If a count, a cadence, a flag or a workflow step changes,
  grep for it across `README.md`, `AGENTS.md`, `docs/**.md` and `.github/workflows/*.yml` before
  trusting any single copy — the same fact tends to be written down in half a dozen places.
  **Prefer phrasing that cannot rot** ("the full offline suite") over a number that has to be
  maintained everywhere: the test count used to appear in seven files and is now written down in
  none. The README is a **manual**: deep reference belongs in `docs/`, history belongs in
  `docs/changelog/`.
- **README structure is an invariant.** Keep the root README a concise user manual,
  not an append-only handoff log. Every shipped feature must appear in its numbered
  "What it posts" section (schedule, codes, optional official news, optional pre-load &
  maintenance started). Put detailed setup, variables/secrets, rendering policies, media
  bounds and verification in existing `docs/` references; update `docs/README.md` with
  working links. Integrate corrections into the canonical section instead of appending
  "latest" or "supersedes earlier" policy dumps. Keep **Legal & credits as the final root
  README section**, preserve its existing links/attribution, and never append a feature
  beneath it. Keep changelog entries newest-first with a matching row in
  `docs/changelog/README.md`; do not put current-policy appendices after old history.
  Verify touched paths/anchors, headings, defaults and duplicate/stale statements.
  Passing CI or an apply check is not proof of a fully audited manual or bug-free
  runtime. Distinguish exact-file equality, functional checks and live evidence.
- **Comments explain *why*, including the incident that caused the line.** That style is why this
  repo is debuggable; keep it.
- **Branch/PR**: work on a branch, open a PR, let `test` go green. Never push to `main` directly;
  `monitor.yml` runs from `main`, so a bad merge posts to real Discord channels.


## Optional official-news invariants

- Preserve the pending attended-automation/application changes; implement only
  the newest delta in existing files, with the existing smoke/CI gates.
- `NEWS_ENABLED` defaults off; feature selection alone cannot enable news and
  global disable wins. Five dedicated destinations, no catch-all/force/mirror fallback.
- Official news, schedule, schedule mirrors, codes, and preload/maintenance started
  alerts are strictly independent features: Special Program previews, broadcasts,
  pre-installation notices, and version maintenance notices remain eligible for
  official news delivery under normal news validation/deduplication rules even when
  consumed by schedule, mirrored to `DISCORD_WEBHOOK_SCHEDULE_MIRROR_<GAME>`, or
  used by `maintenance`. Existing legacy `state["news"]` records carrying
  `{"status": "posted", "excluded": "schedule"}` stay completed in place so
  historical articles are never mass-reposted on rollout without explicit operator
  authorization. No Wangyue; ANANTA has no verified news adapter.
- Never substitute a list preview for a failed full fetch. Use one message when
  full text/media fits; otherwise <=7,000 normalized chars may use at most two
  independently validated pages. Unpageable/longer articles use one labelled
  excerpt container with at most one lead image.
  Halve the words of the already budget-fitting opening excerpt, not half of the
  complete source; fitting articles are not shortened. Normalize line-leading
  `●`/`•` to Markdown `- ` bullets, including bold-wrapped markers.
  No continuation flood or gallery-only mode. Emoji buttons only in the final
  container of the final message; omit unknown publication times. Preserve list/heading readability.
- Preflight only included direct media with a bounded official-host GET/signature
  check. Refresh the official full article once on failure; if still unresolved,
  hold/retry without marking delivered. Never guess filenames, strip required URL
  queries, use screenshot substitutes, or claim this proves Discord playback.
  Do not invent engagement stats.
- Keep link labels/destinations separate via `textutil.news_link()`: preserve balanced
  depth-1 `[...]` spans unescaped inside `` `[label](url)` ``, emit unmatched/outer-nested
  brackets outside linked spans as `\[` / `\]` (splitting across multiple link spans where
  needed or falling back to escaped brackets plus bare `url` when no linkable text exists),
  and keep bare self-labelled/visible-URL links (including bold/emphasis-wrapped URLs in
  Quill or HTML such as `47174982`) and raw button/media URL fields as plain bare URLs
  outside `**...**`. Never capture the next section in a link; retain outer spaces/blank
  lines on inline Quill runs and accumulate multi-op Quill headings/lists before formatting.
- HTML and Quill emphasis conversion must balance nested/adjacent spans across color runs,
  block tags, and media boundaries without emitting literal stray `**`/`****` or double-bolded
  `**[**label**](url)**` heading links, lift leading whitespace out before opening emphasis,
  and escape literal CMS `*` footnotes/multipliers (`\*`) outside URLs. Pad both sides of
  decorative closing `✦` markers only when missing; retain source emphasis, not source HTML styling.
- Missing HoYoLAB publisher nickname falls back to the configured game name;
  supplied nicknames are preserved. This is fallback metadata, not a hardcoded author.
- Add spaces after unpadded `※`/`✦`; blank lines only between consecutive `※` notes,
  not before every footnote. Keep consecutive Markdown bullets compact. Never
  split one continuous media run merely at the eight-unit readability threshold.
- Optional measured long-strip grouping is approved and implemented with
  `NEWS_GROUP_LONG_STRIPS` (default off). Cropping/slicing/filtering/removal remain
  forbidden. Existing program key-art aspect checks do not drop news images.
- Silent first/re-enable baseline; persist confirmed multipart progress only.
  Keep retry holes, bounded state and a safe publication floor before evicting
  completed IDs. Never evict partial progress to admit new posts.
- No news test-bench posting or production-state reset. Verify official sources
  read-only before opt-in; fixture/preview success is not live-source or playback proof.
  Wuthering Waves' English current index is not a full historical archive.
- HuTao/Tausendsassa are references only. No new files, dependency/workflow changes,
  PR creation, merge, deployment, secret/settings mutation or posting without approval.


## Current official-news paging policy (supersedes earlier one-message-only wording)

Keep fitting full articles unchanged in one message (possibly multiple containers).
By default (`NEWS_EXPAND_FULL=0`), if that fails, permit at most two actual messages
when normalized source text plus title/byline once is <=7,000 characters and both
payloads validate independently against 4,000 text characters / 40 components /
1–10 gallery items (the 7,000 ceiling is default policy; explicit `NEWS_EXPAND_FULL=1`
lifts it up to the bounded `12`-page / `120,000`-character / `120`-media cap before
falling back to a labelled single-container excerpt).
Preserve complete wording and source media order. Prefer source block boundaries;
use safe paragraph boundaries only for larger text blocks. Never split a link or
unbalanced bold span. If packing fails, use the existing one-container excerpt
with at most one lead image; never publish a partial full-article proposal.
Paged messages: title/byline and lead only once at the start, then Page 1 / Page 2
labels and dividers; three custom-emoji buttons only at the end of the final
message. One-message articles also put buttons in the final container. Articles
above the ceiling or unpageable within two messages keep the approved half-fitting
word excerpt. Never truncate fitting full articles or modify official API HTML.
Retain confirmed per-message progress, no-repost handling, media preflight and
refresh/holds. No new scheduler or delivery-state reset. Historical incomplete
captures are not full-source length evidence. Pagination is tested across all
five game keys with synthetic boundary inputs, not five live integrations.


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
responses and media URLs remain untouched. A historical maintenance notice remains
schedule-routed: a length allowance does not make it eligible for news/backfill.
The one integrated HTML contains the main previews and complete browser-only
long-strip laboratory; optional backend grouping is implemented below.


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


## Optional news timestamps, pre-load/maintenance alerts & expanded full articles (2026-10-21)

All three additions are **disabled by default** and strictly opt-in via environment /
repository Variables:

- **`NEWS_TIMESTAMPS=0` (default):** bypasses `gamexpress/news_timestamps.py` completely
  (`0` parser calls, `0` extra HTTP requests, byte-identical output). When `1`, converts
  exact TZ-qualified date-times (including bare `UTC`/`GMT` at `+00:00`, explicit
  `UTC±H[:MM]` / named offsets, and news-only `server time` fallback at `UTC+8`) to
  `<t:EPOCH:f>` after text normalization and before sizing/pagination. Explicit years are
  always authoritative; yearless dates require `published_ts > 0` and resolve strictly
  within an exact `±180`-day window (`YEARLESS_MAX_DELTA_DAYS = 180`) around `published_ts`
  (keeping recent past dates in `pub.year`, supporting genuine Dec ↔ Jan rollovers within
  `±180` days, leaving ambiguous dates outside `±180` days untouched, and never adding a
  year to inverted ranges). In two-endpoint ranges, `_resolve_range_tzs` inherits a valid
  trailing zone only when the first endpoint omits its timezone and rejects the entire range
  verbatim if either endpoint carries an invalid or ambiguous explicit zone, without mutating
  `Item`, raw HTML, or `timeparse.py`.
- **`MAINTENANCE_ENABLED=0` + `MAINTENANCE_GAMES=""` (default):** `gamexpress/maintenance.py`
  posts independent `Pre-Load Started` and `Maintenance Started` Components V2 cards to
  dedicated `DISCORD_WEBHOOK_MAINTENANCE_<GAME>` webhooks (with optional `PING_MAINTENANCE_<GAME>`
  / `PING_MAINTENANCE`), seeding settled milestones silently on first activation, enforcing
  `official > override > persisted first-observed launcher signal (labelled observed) > cadence`
  precedence (no invented HNA cadence or unknown end time), separating version/launch identity
  lock from selected media tier across 4 priority tiers against Phase II swaps, and bounding
  post-delivery media checks/edits strictly to `0 <= now - posted_at <= LATE_MEDIA_EDIT_WINDOW_S`
  (`6 h` / `21,600 s`, once per scheduled poll with per-run `verified_cache` URL deduplication),
  `MAX_LATE_MEDIA_ATTEMPTS = 3` consecutive failed `PATCH` calls (`edit_attempts`, reset to `0` on
  `res.ok`), and `MAX_LATE_EDITS = 6` total succeeded `PATCH` edits (`edit_count`, monotonic).
- **`NEWS_EXPAND_FULL=0` (default):** independent of `main`'s removed per-run article-count cap
  and independent of `NEWS_GROUP_LONG_STRIPS`; preserves the exact per-article 1-message /
  `<= 7,000`-char max-2-page / halved-word labelled excerpt policy. When `1`, expands full
  articles across multiple independently validated pages up to `NEWS_EXPAND_MAX_PAGES = 12`
  (`NEWS_EXPAND_MAX_CHARS = 120000`, `NEWS_EXPAND_MAX_MEDIA = 120`), with explicitly labelled
  excerpt fallback if exceeded and
  `SendResult.ambiguous` holds on indeterminate webhook `POST` outcomes (adding media validation
  `GET`s, webhook `POST`s, and inter-page pacing proportional to media and page count).
- **Shared `WebhookClient` recovery policy (`gamexpress/discord.py`):** Conservative
  stop-and-hold recovery is explicitly enabled for official news and maintenance alerts.
  Existing schedule/code retry behavior remains at the pre-PR baseline. Specifically,
  `runner.py:run_news` (ordinary single-card, `<=7,000` 2-page, excerpt, and
  `NEWS_EXPAND_FULL=1` multi-page articles) and `maintenance.py:run` (`Pre-Load Started` /
  `Maintenance Started` alerts) pass `stop_on_ambiguous=True` explicitly, stopping blind
  replay after 1 `POST` attempt and returning `SendResult(..., ambiguous=True)` while
  preserving definite pre-send connection retries, explicit `4xx` rejection handling, `429`
  `Retry-After` backoff, `5xx` retries, and idempotent `PATCH` edits; existing `schedule`
  (`schedule.py` primary `POST`, `404`-recovery repost, and mirror `POST`), `codes`
  (`codeposter.py`), and CLI (`__main__.py` `test-card`/`check-webhooks`) callers leave
  `stop_on_ambiguous=False` by default and retain their exact pre-PR baseline retry and
  `SendResult` behavior. Keep default-off formatting/pagination parity, authorized
  independent official-news delivery, news/maintenance recovery hardening, and preserved
  `schedule`/`codes` behavior clearly distinct.

Run `.venv/bin/python -m gamexpress benchmark --iterations 300` (or add `--json`) on any clean
revision to reproduce the exact SHA-stamped `median`/`mean`/`p95` offline CPU timings across all
12 cases (`short=341c+1img`, `medium=4926c+1img <=7000`, `long=12348c+18imgs`), default-off
parity checks (`output_equal=True`, `main_1e071d8_sha256_equal=True`,
`timestamp_parser_calls=0`, `extra_feature_http_or_webhook=0`),
and mocked/derived protocol counts (`short(off)=1 msg / 1 media GET / 1 POST`,
`medium<=7000(off)=2 msgs / 1 media GET / 2 POSTs (+1.2s min pacing)`,
`long>7000(off)=1 excerpt msg / 1 media GET / 1 POST`,
`long>7000(expand_full=1)=4 msgs / 18 media GETs / 4 POSTs (+3.6s min pacing)`).
