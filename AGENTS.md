# AGENTS.md — orientation for AI agents and future sessions

Read this **before changing anything**. It is the short version of how Game-Express works, which
behaviours are deliberate (and must not be "fixed"), how to verify a change, and which traps have
already cost a broken run. `README.md` is the user-facing manual; this file is the maintainer's
mental model.

Last updated **2026-10-03** for **v1.9.0**.

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
| `gamexpress/sources/*` | one module per upstream: `twitter` (nitter fleet + FxEmbed), `hoyolab`, `kuro`, `codes`, `launcher`, `bannerfeed`, `countdown`, `newspage` |
| `gamexpress/{media,textutil,timeparse,samples,preview_html}.py` | image URL normalisation, HTML→text, date/time parsing, sample cards, local preview |
| `config/games.json` | per-game config (see §4) · `config/overrides.json` human corrections · `config/program_announcements.json` discovered tweet ids |
| `tests/test_smoke.py` | **the** test suite: 135 offline tests, no network, no secrets |
| `.github/workflows/` | `monitor.yml` (production), `ci.yml` (tests + advisory job), `python_version_bump.yml` |

---

## 3. Invariants — deliberate behaviour, do not "fix"

1. **`monitor.yml` must keep `cancel-in-progress: false`.** A run can sit between "posted to
   Discord" and "state committed"; cancelling there causes a double post. `ci.yml` *does* cancel —
   that is fine and intentional.
2. **GitHub's native `schedule:` stays disabled.** Two schedulers raced in News-Express and
   double-posted. cron-job.org is the single trigger.
3. **The first run for a new game/feature seeds silently.** `BOOTSTRAP_POST` off = record what
   exists, post nothing. Never "fix" this into a backfill.
4. **Posting is once per (game, version) / per code**, then *silent edits* of the same message id.
   The state's message ids are what make an edit possible — never clear them casually.
5. **Official times win; estimates are labelled.** Countdown sites and the banner feed may fill a
   gap, but the card says so, and a real official time always replaces them.
6. **Ranking beats speed in the nitter fleet.** `_probe_batch` may stop waiting early, but only
   once enough *higher-ranked* mirrors have answered (plus the `NITTER_GRACE` cap). Do not
   "simplify" it to first-two-to-respond: mirror order is a quality ranking.
7. **The advisory CI job must never gate a merge** (`continue-on-error: true` on every step). Only
   the `test` job is a required check.
8. **No new runtime dependencies** without a very good reason. The whole app runs on `aiohttp`,
   `feedparser`, `python-dotenv`.
9. **Never commit secrets.** Webhooks and the nitter token are repository secrets; the state file
   stores only a 12-char non-reversible webhook fingerprint.
10. **No LICENSE file is wanted** — this is a personal-use repository (owner's decision,
    2026-10-03). Do not add one "for completeness".

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
.venv/bin/python tests/test_smoke.py        # 135/135 — the plain runner is what CI uses
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
| `astral-sh/*@vN` | **Astral publishes no floating major tag.** `setup-uv@v9` and `ruff-action@v4` both failed with *"unable to find version"*, killing the job at **Set up job** — before `continue-on-error` can apply | pin astral actions to a full `vX.Y.Z`; `test_astral_actions_are_pinned_to_a_full_version_tag` enforces it |
| zizmor suppressions | `# zizmor: ignore[rule]` on the *preceding* line is unreliable | put it as a **trailing comment on the exact reported line** |
| `cache: 'pip'` after the uv switch | warns on every run about a missing `~/.cache/pip` | removed in PR #21; uv has its own cache |
| `setup-uv` with no `version:` | fetches the version manifest over the network every run | `version: latest-known` |
| Hung nitter mirror | `asyncio.gather` waited the full 12 s timeout (run #217: 16.2 s vs 5 s) | fixed in v1.9.0; see invariant #6 |
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
- **Hash-pin all actions** (supply-chain). Rejected: it conflicts with the Dependabot tag-pin
  policy documented in `.github/zizmor.yml` and with a workflow assertion test.
- `MAX_PARALLEL > 12`, shorter retry backoff: rejected, upstream politeness.

---

## 8. Conventions

- **Versioning**: bump `gamexpress/__init__.py::__version__` *and* add a dated `### x.y.z — YYYY-MM-DD`
  section at the **top** of the README changelog. The version appears in every run summary.
- **Docs are part of the change.** If a count, a cadence, a flag or a workflow step changes, grep
  for it across `README.md` and `docs/*.md` — the test count in particular appears in five files.
- **Comments explain *why*, including the incident that caused the line.** That style is why this
  repo is debuggable; keep it.
- **Branch/PR**: work on a branch, open a PR, let `test` go green. Never push to `main` directly;
  `monitor.yml` runs from `main`, so a bad merge posts to real Discord channels.
