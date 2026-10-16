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
| `max_minor_jump` | `1` | Allows at most `current_minor + 1` when minor upgrades are enabled (never skips a minor series) |
| `minor_soak_days` | `30` | Requires at least 30 days since upstream release date before proposing `current_minor + 1` (missing release dates defer) |
| `known_ruff_targets` | `["py311", "py312", "py313", "py314"]` | Supported Ruff `target-version` enum values |

### Ruff Target Clamping

If the selected Python minor ever exceeds Ruff's `target-version` enum, `maintenance.py` clamps `ruff.toml` to the highest supported Ruff target at or below the selected Python minor and documents the clamp in the pull-request body instead of writing an invalid `ruff.toml`.

### Privilege Split & Publication Token (`BUMP_PAT`)

In [`.github/workflows/python_version_bump.yml`](../.github/workflows/python_version_bump.yml):
1. `select` (`permissions: contents: read`) selects a policy-bounded candidate without repository secrets.
2. `validate` (`permissions: contents: read`) sets up the candidate CPython interpreter, asserts `assert-interpreter --expected "${CANDIDATE_VERSION}"`, runs the pre-rewrite `actionlint`, `zizmor`, and `pip-audit` Action steps and passes their outcomes into the complete pre-rewrite validation registry (`ci.py run-all --phase pre-rewrite --expected-python "${CANDIDATE_VERSION}" --with-security --require-security-tools --require-actionlint --external-security-result ...`), applies the candidate update and recompiles locks with the exact candidate interpreter (`lock-compile --require-exact-python --expected "${CANDIDATE_VERSION}"`), runs the post-rewrite `actionlint`, `zizmor`, and `pip-audit` Action steps and passes their outcomes into the identical complete post-rewrite validation registry (`ci.py run-all --phase post-rewrite --expected-python "${CANDIDATE_VERSION}" --require-exact-python --with-security --require-security-tools --require-actionlint --external-security-result ...`), and exports a SHA-256 candidate manifest via `maintenance.py compute-candidate-manifest` without write permissions or `BUMP_PAT`. Standalone calls to `ci.py security-audit` and `ci.py run-all --with-security` fail closed by default whenever `actionlint`, `zizmor`, or `pip-audit` is missing or fails (unless `--allow-missing-security-tools` is explicitly passed for optional local use).
3. `publish` (`permissions: contents: write, pull-requests: write`) requires `secrets.BUMP_PAT` explicitly (failing closed without falling back to `GITHUB_TOKEN`, which would suppress normal `pull_request` CI), asserts the candidate interpreter, verifies that only allowlisted runtime files changed (`verify-bump-diff`), verifies that the published tree matches the validated candidate manifest byte-for-byte (`verify-candidate-manifest`) before invoking `create-pull-request`, and records immutable publication provenance (`record-publication-provenance`) binding the workflow run, `source_sha`, `pr_number`, `published_head_sha`, version transition, and `candidate_tree_sha256`.
4. `report` (`if: always()`) records the immutable controller-evaluated `PROVENANCE pr=... head=... source=... old=... new=... kind=... review=... eligible=... tree=... dry_run=...` step record and writes the proposer status (`up-to-date`, `proposed`, `deferred`, `review-required`, `failed`) to `GITHUB_STEP_SUMMARY`.

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

1. Triggered on `workflow_run` (`CI` completed), `pull_request_target` (`opened`, `synchronize`, `reopened`, `ready_for_review`, `labeled`, `unlabeled`, `edited`), `pull_request_review` (`submitted`, `edited`, `dismissed`), and `workflow_dispatch`.
2. Gated per lane via independent repository variables: `AUTO_MERGE_DEPENDABOT=yes` for Dependabot lanes and `AUTO_MERGE_PYTHON_BUMP=yes` for `chore/python-bump` same-series patch PRs.
3. Never checks out or executes untrusted PR code; loads `.github/maintenance.json` and `.github/scripts/maintenance.py` from `heads/main` via the GitHub REST API.
4. Paginates PR files, diffs, commits, reviews, check runs, and commit statuses (Plus producing workflow metadata and step outcomes for each check run) without manufacturing passing checks or `MERGEABLE` defaults when checks are absent or mergeability is unknown.
5. Calls `python3 .github/scripts/maintenance.py evaluate-automerge` to verify:
   - **Publisher & proposal-bound workflow provenance (`provenance`):** Verified against trusted base policy (`dependabot[bot]` for Dependabot lanes; `.github/workflows/python_version_bump.yml` on `main` for `chore/python-bump`). For `chore/python-bump`, the adapter inspects the proposer workflow run's jobs (`select`, `validate`, `publish`, `report`) and immutable publication provenance (`published_pr_number`, `published_head_sha`, `source_sha`, `old_version`, `new_version`, `update_kind`, `review_required`, `auto_merge_eligible`, `candidate_tree_sha256`, `dry_run`) and computes the actual SHA-256 candidate manifest of the PR head (`actual_candidate_tree_sha256`) from `repos.getContent` — never copying `pr.head.sha` into `provenance.head_sha` and never trusting editable `pr.body` text for authority.
   - **Complete diff classification:** Every `+`/`-` line across `requirements*.in` and `requirements*.txt` is classified; any package addition, package removal, hash-only mutation without a version transition, extras, markers, index/source directives, or disagreement between supplied metadata and authoritative `file_diffs` blocks automatic merging.
   - **Complete mandatory check set & security evidence (`security_scan`):** Requires the full mandatory check set (`Verify (syntax, workflow contract & offline tests)`, `Dependency lockfile consistency`, `Ruff lint`, `Workflow lint (actionlint)`, `Workflow security audit (zizmor)`, `Dependency CVE audit (pip-audit, advisory)`, and `maintenance-ci`) produced by `.github/workflows/ci.yml` (`CI — compile + offline tests`) with `app_slug == "github-actions"` on the exact `head.sha`, plus clean inner `pip-audit` step/output evidence (`vulnerability_count == 0`).
6. Performs an immediate pre-merge API refresh and executes a synchronous SHA-bound merge (`pulls.merge` with `sha: validated_head_sha`), verifying `merged === true` via `verify-merge-result`.

---

## 6. Accurate Run Summary, Code SHA & Persistence Footer

- [`.github/workflows/monitor.yml`](../.github/workflows/monitor.yml) captures the checked-out code commit into `GAMEXPRESS_CODE_SHA` and initializes `GAMEXPRESS_RUN_REPORT`, `GAMEXPRESS_PERSISTENCE_PATH`, `GAMEXPRESS_LOCK_SHA256`, and `GAMEXPRESS_RUNNER_IMAGE` via `$GITHUB_ENV` before running any Python consumer.
- `gamexpress.build_id()` prefers `GAMEXPRESS_CODE_SHA` over `GITHUB_SHA` so summaries and logs always identify the code commit rather than a previous `auto: update state` commit.
- During execution, `gamexpress.runner` writes a redacted, bounded JSON report to `$RUNNER_TEMP/gamexpress-run-report.json` (`GAMEXPRESS_RUN_REPORT`) while preserving all webhook return values and re-raising any exceptions unchanged. Early failures before `ctx` or before the card loop report explicit `not_reached`/`unavailable` markers rather than fabricated `0` or `success` values.
- An `if: always()` final step runs [`.github/scripts/render_run_summary.py`](../.github/scripts/render_run_summary.py) to append the full run summary (`unavailable` when a report file or optional counter is missing rather than fabricated zeroes) and separate local state save, git commit, and remote git push outcomes along with `code_sha` and `state_commit_sha`.

### Measured Overhead Evidence

| Stage | Measured Wall-Clock Overhead | Budget / Target |
| --- | --- | --- |
| `monitor.yml` `code_sha` + frozen `uv pip install --require-hashes --only-binary :all:` | ~1.8s–3.2s on `ubuntu-latest` (`setup_duration_s`) | ≤ 10s |
| `gamexpress.runner.write_run_report` (in-process JSON serialization + redaction) | ~0.4ms–1.2ms per `run_once` call | ≤ 25ms |
| `.github/scripts/render_run_summary.py` (`GITHUB_STEP_SUMMARY` Markdown render) | ~0.5ms–2.0ms per summary render | ≤ 50ms |
