# Documentation

Every guide in this folder is linked from the [main README](../README.md); this page is the single-screen index.

| Guide | What it covers |
|---|---|
| **[MAINTENANCE.md](MAINTENANCE.md)** | **Canonical maintenance architecture** — `.python-version`, `.github/maintenance.json`, hashed `pip-tools` lockfiles (`requirements.in` / `requirements.txt` & `requirements-dev.in` / `requirements-dev.txt`), `maintenance-ci` gate, `maintenance_merge.yml`, and run-summary persistence reporting |
| **[CONFIGURATION.md](CONFIGURATION.md)** | Every secret, variable, per-game override, ping format (`role` / `everyone` / `here` / `none`), custom emoji, and `config/games.json` / `config/overrides.json` |
| **[SCHEDULER.md](SCHEDULER.md)** | Running the monitor every 5 minutes from **cron-job.org** (external `workflow_dispatch`), plus optional two-instance fail-over |
| **[PROD-REPO-SETUP.md](PROD-REPO-SETUP.md)** | Keeping a **production repo** (live Discord webhooks) and a **development repo** (tests, CI, Dependabot) in sync, and why the prod repo never holds `ci.yml` or `docs/` |
| **[ROLLOUT.md](ROLLOUT.md)** | First-time rollout checklist — verifying webhooks, seeding `state/state.json` without flooding Discord, and switching on cron-job.org |
| **[TESTING.md](TESTING.md)** | Offline regression suites (`tests/test_smoke.py`, `tests/test_schedule_epithet_and_settled.py`, `tests/test_gachawiki_placeholder.py`, `tests/test_maintenance.py`, `tests/test_run_summary.py`, `tests/test_configuration_contract.py`), `ci.py`, and the 1-click **Monitor → `mode = test`** bench in GitHub Actions |
| **[TROUBLESHOOTING.md](TROUBLESHOOTING.md)** | Symptom → cause → fix table for missing cards, unverified codes, stale mirrors, webhook 400/404s, and state-push conflicts |
| **[SOURCES.md](SOURCES.md)** | Every upstream source the monitor reads (HoYoPlay / Kuro launchers, HoYoLAB, official news pages, 21-instance nitter fleet, FxTwitter / vxTwitter, 5-source code quorum, game wikis) |
| **[BANNER_DATABASE.md](BANNER_DATABASE.md)** | How Phase I / Phase II character & weapon banners and their epithets are resolved from the official notices, game calendars, and MediaWiki Cargo / Module tables |
| **[TIMESTAMP-PATTERNS.md](TIMESTAMP-PATTERNS.md)** | How maintenance windows, livestream times, UTC offsets, and cold-start cadence estimates are parsed and converted to `<t:UNIX:F>` / `<t:UNIX:R>` |
| **[ACCURACY.md](ACCURACY.md)** | Priority rules that stop a lower-tier source or a reminder post from overwriting a confirmed official time, link, or key art |
| **[SECURITY.md](SECURITY.md)** | SHA-pinned Actions, `zizmor` + `actionlint` + `pip-audit`, response-size caps, webhook fingerprint hashing, and URL/token/header redaction |
| **[PYTHON_VERSION.md](PYTHON_VERSION.md)** | Exact `.python-version` (`3.14.8`) pin policy, `.github/maintenance.json` bounds, Ruff target clamping, and the weekly [`.github/workflows/python_version_bump.yml`](../.github/workflows/python_version_bump.yml) workflow |
| **[DEPENDABOT.md](DEPENDABOT.md)** | Weekly `pip` and `github-actions` update configuration ([`.github/dependabot.yml`](../.github/dependabot.yml)), cooldowns, grouping, and safe auto-merge via [`.github/workflows/maintenance_merge.yml`](../.github/workflows/maintenance_merge.yml) |
| **[CREDITS.md](CREDITS.md)** | Attribution for upstream APIs, community feeds, wikis, and sister project **News-Express** |
| **[changelog/CHANGELOG.md](changelog/CHANGELOG.md)** | Release history and dated maintenance notes (also indexed at [changelog/README.md](changelog/README.md)) |
