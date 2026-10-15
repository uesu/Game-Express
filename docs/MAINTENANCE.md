# Maintenance Architecture & Safe Update Guide

This document is the canonical operational reference for Python runtime pinning, hashed dependency locks, CI verification gates, safe automated merges, and run-summary/persistence reporting in **Game-Express**.

Related guides:

- [Python Version Policy](PYTHON_VERSION.md)
- [Dependabot Guide](DEPENDABOT.md)
- [Testing & Verification](TESTING.md)
- [Security & Redaction](SECURITY.md)
- [Configuration Reference](CONFIGURATION.md)
- [Production Repo Setup](PROD-REPO-SETUP.md)

---

## 1. Single Runtime Pin (`.python-version`)

- `.python-version` at the repository root is the single source of truth for the CPython runtime (`3.14.8`).
- Every GitHub Actions workflow that runs Python ([`.github/workflows/ci.yml`](../.github/workflows/ci.yml), [`.github/workflows/monitor.yml`](../.github/workflows/monitor.yml), and [`.github/workflows/python_version_bump.yml`](../.github/workflows/python_version_bump.yml)) configures `actions/setup-python` with:
  ```yaml
  with:
    python-version-file: .python-version
    check-latest: false
  ```
- Floating pins such as `'3.x'` or `'3.14'` are forbidden in workflow files and rejected by `python .github/scripts/maintenance.py validate-workflows`.

---

## 2. Policy-Bounded Python Updates (`.github/maintenance.json` & `.github/scripts/maintenance.py`)

Runtime selection and linter compatibility are governed by [`.github/maintenance.json`](../.github/maintenance.json) and executed by [`.github/scripts/maintenance.py`](../.github/scripts/maintenance.py) (with [`.github/scripts/python_version_bump.py`](../.github/scripts/python_version_bump.py) retained as a thin compatibility adapter):

| Policy Key | Value | Purpose |
| --- | --- | --- |
| `supported_major` | `3` | Restricts selection to CPython 3.x |
| `min_minor` | `11` | Minimum supported Python minor line |
| `max_validated_minor` | `14` | Highest minor line validated against wheels, Ruff, and offline suites |
| `allow_minor_upgrades` | `false` | Restricts automated bumps to patch releases on the current minor line until explicitly enabled |
| `known_ruff_targets` | `["py311", "py312", "py313", "py314"]` | Supported Ruff `target-version` enum values |

### Ruff Target Clamping

If the selected Python minor ever exceeds Ruff's `target-version` enum, `maintenance.py` clamps `ruff.toml` to the highest supported Ruff target at or below the selected Python minor and documents the clamp in the pull-request body instead of writing an invalid `ruff.toml`.

### Publication Token (`BUMP_PAT`)

In [`.github/workflows/python_version_bump.yml`](../.github/workflows/python_version_bump.yml), the `select` and `validate` jobs run without repository secrets, and the `publish` job uses `secrets.BUMP_PAT || secrets.GITHUB_TOKEN` so pull requests opened with `BUMP_PAT` trigger normal `pull_request` CI runs before `maintenance_merge.yml` evaluates them.

---

## 3. Reproducible Hashed Dependency Locks

- Direct runtime dependency ranges live in [`requirements.in`](../requirements.in) and compile to the hash-locked [`requirements.txt`](../requirements.txt).
- Developer, linter, test, and lock-compiler dependencies (`pip==26.1.1`, `pip-tools==7.5.3`, `pytest`, `pyyaml`, `ruff`) live in [`requirements-dev.in`](../requirements-dev.in) (constrained via `-c requirements.txt`) and compile to [`requirements-dev.txt`](../requirements-dev.txt).
- Compile contract:
  ```bash
  CUSTOM_COMPILE_COMMAND="python -m piptools compile --generate-hashes --allow-unsafe --resolver=backtracking --strip-extras --output-file=requirements.txt requirements.in" \
    python -m piptools compile --generate-hashes --allow-unsafe --resolver=backtracking --strip-extras --output-file=requirements.txt requirements.in

  CUSTOM_COMPILE_COMMAND="python -m piptools compile --generate-hashes --allow-unsafe --resolver=backtracking --strip-extras --output-file=requirements-dev.txt requirements-dev.in" \
    python -m piptools compile --generate-hashes --allow-unsafe --resolver=backtracking --strip-extras --output-file=requirements-dev.txt requirements-dev.in
  ```
  Or run:
  ```bash
  python .github/scripts/maintenance.py lock-compile
  python .github/scripts/maintenance.py lock-check
  ```
- Frozen installation contract:
  ```bash
  python -m pip install --require-hashes --only-binary=:all: -r requirements.txt -r requirements-dev.txt
  ```

---

## 4. CI Gate (`maintenance-ci`) & Blocking vs. Advisory Split

[`.github/workflows/ci.yml`](../.github/workflows/ci.yml) delegates commands through [`.github/scripts/ci.py`](../.github/scripts/ci.py) and separates deterministic blocking checks from external advisory checks:

- **Deterministic blocking checks:**
  - `test` (`python .github/scripts/ci.py verify` — bytecode compilation, workflow pin contract, and all offline test suites under `tests/test_*.py`)
  - `lock-check` (`python .github/scripts/ci.py lock-check` — hash completeness, constraint alignment, and zero lockfile drift)
  - `ruff` (`python .github/scripts/ci.py ruff`)
  - `actionlint` (`reviewdog/action-actionlint`)
  - `zizmor` (`zizmorcore/zizmor-action`)
- **External advisory check:**
  - `pip-audit` (`pypa/gh-action-pip-audit` against live OSV advisories; reported in the summary without causing transient network/feed outages to block deterministic CI)
- **Final aggregate check (`maintenance-ci`):**
  - Runs under `if: always()` and succeeds if and only if every blocking check succeeded.

---

## 5. Dedicated Safe Auto-Merge Workflow (`maintenance_merge.yml`)

Auto-merge is decoupled from `ci.yml` and `python_version_bump.yml` and handled exclusively by [`.github/workflows/maintenance_merge.yml`](../.github/workflows/maintenance_merge.yml):

1. Triggered on `pull_request_target` (`opened`, `synchronize`, `reopened`, `ready_for_review`) targeting `main`.
2. Never checks out or executes untrusted PR code; loads `.github/maintenance.json` and `.github/scripts/maintenance.py` from `pr.base.sha` via the GitHub API.
3. Calls `python3 .github/scripts/maintenance.py evaluate-automerge` to verify:
   - same-repository PR targeting `main`;
   - trusted automation actor (`dependabot[bot]` for `dependabot/*`, or `github-actions[bot]` / `uesu` for `chore/python-bump`);
   - zero modifications under `.github/workflows/`;
   - every changed file matches the lane allowlist in `.github/maintenance.json`;
   - PR is open, non-draft, mergeable, and has passing `maintenance-ci`.
4. Enables GitHub GraphQL `enablePullRequestAutoMerge` (`SQUASH`) only when all checks pass.

---

## 6. Accurate Run Summary, Code SHA & Persistence Footer

- [`.github/workflows/monitor.yml`](../.github/workflows/monitor.yml) captures the checked-out code commit into `GAMEXPRESS_CODE_SHA` before running the monitor or creating any state commit.
- `gamexpress.build_id()` prefers `GAMEXPRESS_CODE_SHA` over `GITHUB_SHA` so summaries and logs always identify the code commit rather than a previous `auto: update state` commit.
- During execution, `gamexpress.runner` writes a redacted, bounded JSON report to `$RUNNER_TEMP/gamexpress-run-report.json` (`GAMEXPRESS_RUN_REPORT`).
- An `if: always()` final step runs [`.github/scripts/render_run_summary.py`](../.github/scripts/render_run_summary.py) to append the full run summary and final persistence outcome (`saved_and_pushed`, `no_changes`, `skipped_test_mode`, `skipped_after_run_failure`, `push_failed`, or `push_skipped`) along with both `code_sha` and `state_commit_sha`.
