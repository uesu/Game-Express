# AGENTS.md — orientation for AI agents and future sessions

Read this **before changing anything**. It is the short version of how Game-Express works, which
behaviours are deliberate (and must not be "fixed"), how to verify a change, and which traps have
already cost a broken run. `README.md` is the user-facing manual and `docs/` is its reference
material; this file is the maintainer's mental model.

Last updated **2026-10-09**.

---

## 1. What this repository is

A **GitHub-Actions-only** monitor. No server, no daemon, no Discord bot, no container.
`.github/workflows/monitor.yml` is dispatched by cron-job.org every 5 minutes; one run fetches
official sources, decides whether anything is new, posts **Discord Components V2** cards through
**webhooks**, commits its state, and exits. A run takes ~25 s end to end (~5–6 s of that is the
Python).

Two features, independent: **`schedule`** (version/Special-Program cards) and **`codes`**
(redemption-code cards). Six games: `genshin`, `starrail`, `zzz`, `wuwa`, `hna`, `ananta`.

**There is no Discord bot and there must not be one.** A bot existed long ago; it was removed in
v1.7.0, the last hosting artefact (`.dockerignore`) went in PR #20, and the legal docs were
cleaned of slash-command language in v1.9.0. `gamexpress/discord.py` is an HTTP webhook client —
nothing more. Do not add `discord.py`, a token, a gateway, or any always-on process.

---

## 2. Repo map

| Path | Role |
|---|---|
| `gamexpress/__main__.py` | CLI: `run`, `test-card`, `check-webhooks`, `preview`, `validate` |
| `gamexpress/runner.py` | builds `Ctx` (settings, games, state, fetcher, webhook, X client), fail-over, run summary |
| `gamexpress/schedule.py` (1.1k lines) | the brain: picks the announcement, parses times, builds/edits the schedule card |
| `gamexpress/codeposter.py` | the code gate (families, validators, min-sources), posts/edits code cards |
| `gamexpress/cards.py` | Components V2 payload builders + `validate_payload` (`CODES_PER_CARD = 10`) |
| `gamexpress/discord.py` | webhook POST/PATCH, 429/5xx retries, `WEBHOOK_SPACING = 1.2 s` pacing |
| `gamexpress/http.py` | shared `aiohttp` fetcher, `MAX_PARALLEL = 12`, per-source health counters |
| `gamexpress/state.py` | `state/state.json` (`SCHEMA = 1`): posted keys, message ids, bootstrap flags, heartbeat |
| `gamexpress/config.py` | `Settings` (env) + `Game` (games.json) + `game_is_on` / `active_games` |
| `gamexpress/sources/*` | one module per upstream: `twitter` (nitter fleet + FxEmbed), `hoyolab`, `kuro`, `codes`, `launcher`, `bannerfeed`, `gachawiki`, `countdown`, `newspage` |
| `gamexpress/{media,textutil,timeparse,samples,preview_html}.py` | image URL normalisation, HTML→text, date/time parsing, sample cards, local preview |
| `config/games.json` | per-game config (see §4) · `config/overrides.json` human corrections · `config/program_announcements.json` discovered tweet ids |
| `tests/test_smoke.py` | the main suite: every test offline — no network, no secrets |
| `tests/test_schedule_epithet_and_settled.py` | the 2026-10-08 schedule regressions; also runs standalone in a checkout with no dependencies installed |
| `docs/` | the manual, indexed in `docs/README.md`: `CONFIGURATION`, `ACCURACY`, `SOURCES`, `BANNER_DATABASE`, `SCHEDULER`, `ROLLOUT`, `TESTING`, `TROUBLESHOOTING`, `SECURITY`, `TIMESTAMP-PATTERNS`, `DEPENDABOT`, `PYTHON_VERSION`, `PROD-REPO-SETUP`, `CREDITS` |
| `docs/changelog/` | `CHANGELOG.md` (1.8.0 →) + `CHANGELOG_ARCHIVE.md` (1.0.0 – 1.7.0) + an index; full history is here, while the README carries only the latest-entry summary. |
| `.github/workflows/` | `monitor.yml` (production), `ci.yml` (tests + advisory job), `python_version_bump.yml` |

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
   rejects control characters, and percent-encodes parentheses so a `)` cannot close a markdown
   link early and inject a phishing line. `link_button()` returning `None` is deliberate: drop
   one button, still post the card. See `docs/SECURITY.md` §2.
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
13. **Never commit secrets.** Webhooks and the nitter token are repository secrets; the state file
   stores only a 12-char non-reversible webhook fingerprint.
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
.venv/bin/python tests/test_smoke.py        # must end N/N, 0 failed — the plain runner is what CI uses
.venv/bin/python -m pytest -q tests         # pytest must also pass
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
| Hung nitter mirror | `asyncio.gather` waited the full 12 s timeout (run #217: 16.2 s vs 5 s) | fixed in v1.9.0; see invariant #8 |
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
  **top** of `docs/changelog/CHANGELOG.md` and its row in `docs/changelog/README.md`; refresh
  the summary under *Changelog* in `README.md` when the change is worth a reader's attention.
  Entries up to `1.9.0` keep the numbers they shipped as — **never renumber history.**
- **Docs are part of the change.** If a count, a cadence, a flag or a workflow step changes,
  grep for it across `README.md`, `AGENTS.md`, `docs/**.md` and `.github/workflows/*.yml` before
  trusting any single copy — the same fact tends to be written down in half a dozen places.
  **Prefer phrasing that cannot rot** ("the full offline suite") over a number that has to be
  maintained everywhere: the test count used to appear in seven files and is now written down in
  none. The README is a **manual**: deep reference belongs in `docs/`, history belongs in
  `docs/changelog/`.
- **Comments explain *why*, including the incident that caused the line.** That style is why this
  repo is debuggable; keep it.
- **Branch/PR**: work on a branch, open a PR, let `test` go green. Never push to `main` directly;
  `monitor.yml` runs from `main`, so a bad merge posts to real Discord channels.
