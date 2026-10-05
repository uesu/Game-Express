# Changelog — current release line

Releases from **1.8.0** onward: the Python 3.14 runtime, the automated version-bump
workflow, and the 1.9.0 performance and hardening pass. This is the history that still
describes the code on `main`.

Older releases (1.0.0 – 1.7.0, September 2026) live in
[CHANGELOG_ARCHIVE.md](CHANGELOG_ARCHIVE.md). Start at the
[changelog index](README.md).

---

## 1.9.0 — 2026-10-02

**The run stops waiting on a hung mirror, and the dead weight is gone**

- **A stalled nitter mirror no longer costs the run its whole timeout.** Each batch of mirrors is
  still requested in parallel in fleet order, but the batch now **stops the moment the winners are
  decided** and cancels the stragglers instead of awaiting the slowest one (`asyncio.gather` →
  `asyncio.wait(FIRST_COMPLETED)` + cancel, in `XClient._probe_batch`). This is the difference
  between run **#217 (16.2 s, `nitter.cf -> TimeoutError`)** and runs #215/#216/#218 (4.9–6.0 s):
  in a reproduction of exactly that run the timeline fetch went from **12.01 s to 0.06 s** with a
  byte-identical result. Cancelling also returns the `Fetcher`'s global request slot immediately,
  so the HoYoLAB / Kuro / code requests queued behind it start sooner.
  - The *selection* is deliberately unchanged — **ranking still beats speed**. A mirror is only
    dropped once enough **higher-ranked** mirrors have answered, never just because it was
    slower, so the merged timeline is the one the old code would have produced.
  - A hung mirror that outranks the answers still gets a grace window, but `NITTER_GRACE` = 1.5 s
    instead of the full 12 s timeout (**12.01 s → 1.56 s** in that worst case).
  - A probe that raises is now logged and treated as a dead mirror instead of propagating out of
    the run.
- **The rate-limit gap is no longer charged after the last post.** Discord's webhook bucket still
  gets its 1.2 s of spacing between two requests, but the wait now happens *before* a request
  instead of after a successful one — so a run that posts `n` cards pays `n-1` gaps instead of
  `n`, and a run that posts a single card pays none at all (**−1.2 s on every posting run**).
- **Install step no longer phones home for a uv version.** Both workflows pass
  `version: latest-known` to `astral-sh/setup-uv`: with no version and no `uv.toml`/`pyproject.toml`
  the action had to fetch `astral-sh/versions`' manifest over the network on **every** run (0.3–4 s
  in runs #215–#218) and install whatever uv was published minutes earlier, unverified.
  `latest-known` is the newest uv whose checksum ships inside the pinned action: no manifest
  lookup, checksum-verified download, and uv only moves when Dependabot bumps the action through
  the usual green-CI gate.
- **CI cancels superseded runs** (`concurrency` + `cancel-in-progress` in `ci.yml` only — never in
  `monitor.yml`, where a cancelled run could post twice), and both read-only checkouts now use
  `persist-credentials: false`.
- **Two more informational checks** in the `advisory-checks` job, which still can never block a
  merge: [`zizmorcore/zizmor`](https://github.com/zizmorcore/zizmor) (static security review of the
  workflow YAML — the repo is clean, with three documented, justified ignores in
  `.github/zizmor.yml` and inline) and [`astral-sh/ruff-action`](https://github.com/astral-sh/ruff-action)
  (the same `ruff.toml` used locally, so a lint regression shows up on the PR without gating it).
- **Dead weight removed** (no behaviour change): `cards.notice_payload`, `Game.redeem_page` and the
  three `redeem_page` entries in `config/games.json` (left over from the "Redeem Page" button
  dropped in 1.3.0), `CodeHit.hard_expired`, `SourceHealth.last_ok_ts` (written on every request,
  never read), and the duplicate `nitter_pic_to_twimg` in `sources/twitter.py` — it now reuses
  `media.nitter_pic_to_twimg`, which also handles the `ext_twvideo_thumb/` prefix the copy missed.
  `codeposter._post` now chunks with `cards.CODES_PER_CARD` instead of a hardcoded `10`, so the
  card size and the chunk size can never drift apart.
- **Honkai: Nexus Anima and ANANTA are switched on** (2026-10-02), months before release, so a
  pre-release Special Program, livestream or code is caught the moment it is announced — the
  first run for a newly enabled game seeds silently, so nothing old is posted. Their official
  YouTube channels (`@HonkaiNA`, `@Ananta_Game`) are wired up; neither has a Twitch channel, so
  their cards simply have no Twitch button, and ANANTA still hides the banner section.
  - New `"released"` flag in `games.json`, separate from `"enabled"`: *watched* and *out* are
    different facts. `test-card --unlaunched` now selects "not released" instead of "not enabled",
    so the sample-card test bench keeps working for games that are monitored but unreleased.
- **Every GitHub Action is now pinned to a commit SHA** (`@3d3c42e…  # v7`) instead of a
  movable tag — the `tj-actions/changed-files` compromise of March 2025 (CVE-2025-30066)
  repointed every tag of a popular action at code that dumped secrets into ~23 000 repos' logs,
  and the related `reviewdog/action-setup` compromise (CVE-2025-30154) hit the org whose
  actionlint action runs in this CI. Dependabot updates SHA pins and their version comments, so
  patches still arrive as PRs.
- **Invisible-character sanitising:** `strip_invisible()` drops C0/C1 controls, zero-width
  characters and bidi overrides in `clean_text()` and again in `cards.text()`, so scraped text
  cannot render as something other than what it says.
- **Hardening against a hostile source** (`docs/SECURITY.md`, new): every scraped URL now goes
  through `cards.safe_url()` — http(s) only, no control characters, parentheses encoded — so a
  taken-over mirror can neither smuggle an extra `[FREE CODES](…)` link into a card nor kill a
  real announcement with a `javascript:` button (that one button is dropped instead). Response
  bodies are capped at 8 MiB, and one game can post at most 5 code cards per run, with the
  remainder following on the next run.
- **Source-coverage guard:** a new test asserts that every game with a HoYoLAB circle is read on
  **all three official tabs** (`page_sort=notices|events|news` = `type=1|2|3`, so 12 requests per
  run across GI/HSR/ZZZ/HNA) and that every enabled game's X account is probed across the nitter
  fleet, `nitter.cf` first — including the two new accounts `@HonkaiNA` and
  `@Ananta_EN`. Dropping a sort or a gid now fails CI instead of quietly missing announcements.
- **The recommended poll interval is now 5 minutes, not 10** — halving the average time-to-post
  with no code change. `docs/SCHEDULER.md` gains a measured *How fast can it poll?* section: runs
  take 19–36 s (≈8 % of a 5-minute slot), overlap is impossible by construction, GitHub is free
  for public repos, and the real limit is politeness toward volunteer-run upstreams. 3 minutes is
  the floor worth defending; 1 minute is not recommended.
- **[AGENTS.md](../../AGENTS.md)** — a maintainer/AI orientation guide: repo map, the invariants that
  must not be "fixed", exact verification commands, measured performance numbers, and the traps
  that have already broken a run (astral-sh tag pins, zizmor suppression placement, the hung
  mirror, the pip cache).
- **Docs caught up with the code:** the privacy policy no longer mentions slash commands or a
  self-hosted runtime (the Discord bot was removed in 1.7.0 — GitHub Actions is the only runtime),
  and the terms no longer claim the Service "never estimates" when a labelled countdown/banner-feed
  estimate is exactly what a card shows before the official notice lands.
- 163 offline tests (new regression tests pin the stop-waiting behaviour, the webhook spacing,
  SHA pinning for every action, the three-tab HoYoLAB coverage, hostile-source handling, and
  that an unsorted feed full of old announcements still posts only the newest one),
  `ruff check .`,
  `python -m gamexpress validate` and `python -m gamexpress preview` all green.

---

## 1.8.1 — 2026-10-01

**Python 3.14**

- **The monitor now runs on Python 3.14** (`.github/workflows/ci.yml` and `monitor.yml` pin
  `python-version: '3.14'`, matching [python.org's current stable release, 3.14.8](https://www.python.org/downloads/release/python-3148/)).
  Pinning the *minor* version only (not `'3.14.8'`) means GitHub's runners keep picking the newest
  3.14.x bugfix release on their own — no PR needed for a patch release, the same trick already
  used for 3.11 before it. Python 3.11 reaches end of active support around October 2027; 3.14 is
  supported into **October 2030**.
  - Verified safe before merging: the three runtime dependencies (`aiohttp`, `feedparser`,
    `python-dotenv`) already ship Python 3.14 wheels/classifiers, and a full repo scan found zero
    uses of any stdlib API removed or deprecated between 3.9 and 3.14 (no `datetime.utcnow()`,
    no `collections.Mapping`, no dead-battery modules, no old asyncio loop APIs, etc.).
  - `ruff.toml`'s `target-version` is now `py314` to match; `ruff check .` is unchanged (0 issues)
    under both the old and new target.
  - **Dependabot cannot bump this for you** — `python-version` is a workflow input, not a tracked
    package ecosystem, so the *next* Python feature release (3.15, ~October 2027) would have
    needed the same one-line manual edit in both workflow files (and `ruff.toml`) by hand — see
    **1.8.0** below, which automates exactly that.
- No functional changes: all 131 offline tests, `ruff check .`, `python -m gamexpress validate`
  and `python -m gamexpress preview` are unaffected.

---

## 1.8.0 — 2026-10-01

**Future Python bumps, faster installs, two advisory scans**

- **New: `.github/workflows/python_version_bump.yml`.** Weekly (and on demand), it compares the
  pinned Python series against [`actions/python-versions`](https://github.com/actions/python-versions)'
  own release manifest — the exact list `actions/setup-python` installs from — and opens a PR the
  moment a newer *stable* series is actually available, instead of waiting for a human to notice.
  It never merges blind: the PR only auto-merges when it carries the `python-bump` label, the full
  131-test CI gate is green on that exact commit, **and** the repository variable
  `AUTO_MERGE_PYTHON_BUMP=yes` is set — unset by default, so today this only ever opens the PR for
  review. Full design, safety reasoning, and the one-time "allow Actions to open PRs" setting it
  needs: [docs/PYTHON_VERSION.md](../PYTHON_VERSION.md).
- **Faster installs in CI and in the 10-minutely monitor run**, both switched from `pip` to
  [`astral-sh/setup-uv`](https://docs.astral.sh/uv/guides/integration/github/)'s `uv pip install`
  (same `requirements.txt`, same resolved packages — just a much faster resolver/installer). The
  monitor workflow runs every 5 minutes, so this is the install path where the speed actually
  matters day to day.
- **Two new informational-only checks**, added as a separate `advisory-checks` job in `ci.yml`
  that can never block a merge (`continue-on-error: true` on both steps):
  - [`pypa/gh-action-pip-audit`](https://github.com/pypa/gh-action-pip-audit) scans
    `requirements.txt` against the PyPA known-vulnerability database on every PR;
  - [`reviewdog/action-actionlint`](https://github.com/reviewdog/action-actionlint) statically
    checks the workflow YAML itself (typos, bad expressions, shellcheck of `run:` blocks) —
    actionlint has no first-party GitHub Action of its own, this reviewdog wrapper is the
    documented way to run it in CI.
- **Housekeeping:** removed `.dockerignore` (the repo has never had a `Dockerfile`) and the
  `DISCORD_WEBHOOK_TEST=` line in `.env.example` (README already noted it's no longer used, since
  the live-test-channel workflow was retired). Fixed three stale "N offline tests" mentions in
  the docs that still said 55/67 instead of the current 131.
- No functional changes to the monitor itself: all 131 offline tests, `ruff check .`,
  `python -m gamexpress validate` and `python -m gamexpress preview` are unaffected.

