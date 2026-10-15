# Python Version Policy

See also: [Maintenance Architecture & Safe Update Guide](MAINTENANCE.md) · [Dependabot Guide](DEPENDABOT.md) · [Testing & Verification](TESTING.md)

## Exact Runtime Pin (`.python-version`)

Game-Express pins its CPython runtime in a single file at the repository root:

- [`.python-version`](../.python-version) → `3.14.8`

All GitHub Actions workflows that set up Python ([`.github/workflows/ci.yml`](../.github/workflows/ci.yml), [`.github/workflows/monitor.yml`](../.github/workflows/monitor.yml), and [`.github/workflows/python_version_bump.yml`](../.github/workflows/python_version_bump.yml)) read `.python-version` with `check-latest: false`:

```yaml
- name: Set up Python
  uses: actions/setup-python@5fda3b95a4ea91299a34e894583c3862153e4b97  # v7
  with:
    python-version-file: .python-version
    check-latest: false
```

Floating `'3.x'` or minor-only `'3.14'` workflow pins are not used, ensuring CI, scheduled monitor runs, and dependency compilation all execute on the exact same validated CPython release.

## Policy Bounds (`.github/maintenance.json`)

Candidate selection is controlled by [`.github/maintenance.json`](../.github/maintenance.json) and enforced by [`.github/scripts/maintenance.py`](../.github/scripts/maintenance.py) (with [`.github/scripts/python_version_bump.py`](../.github/scripts/python_version_bump.py) retained as a compatibility wrapper):

- `supported_major`: `3`
- `min_minor`: `11`
- `max_validated_minor`: `14`
- `allow_minor_upgrades`: `false`

While `allow_minor_upgrades` is `false`, the weekly bump workflow only selects newer stable patch releases on the validated `3.14.x` line (e.g. `3.14.9`) that publish a valid Linux `x64` archive in `actions/python-versions`, ignoring prereleases, yanked builds, and unvalidated newer minor lines (such as `3.15.x`).

## Ruff `target-version` Clamping

`maintenance.py` keeps `target-version` in [`ruff.toml`](../ruff.toml) aligned with the active Python minor, clamped to `known_ruff_targets` (`py311`–`py314`) and probed against the installed `ruff` binary. If a future Python minor exceeds Ruff's supported target enum, `ruff.toml` is clamped to the highest supported target at or below the selected Python minor and the PR body explains the clamp.

## Weekly Bump & Safe Auto-Merge Flow

1. [`.github/workflows/python_version_bump.yml`](../.github/workflows/python_version_bump.yml) runs Mondays at `08:00 UTC` (or via `workflow_dispatch`).
2. It runs `python .github/scripts/maintenance.py bump` to check `actions/python-versions`.
3. When a newer allowed release is available, it updates `.python-version` (and `ruff.toml` if needed), sets up the candidate Python version, recompiles/verifies hashed lockfiles (`requirements.txt` and `requirements-dev.txt`), and runs `python .github/scripts/ci.py verify` and `python .github/scripts/ci.py ruff`.
4. It opens or updates the `chore/python-bump` pull request using `secrets.BUMP_PAT` when configured (so standard `pull_request` CI runs automatically) or `github.token` otherwise (noting in the job summary that a close/reopen or manual CI dispatch is required before merge).
5. The bump workflow never self-merges; once `maintenance-ci` passes on `chore/python-bump`, [`.github/workflows/maintenance_merge.yml`](../.github/workflows/maintenance_merge.yml) verifies the actor, branch, file allowlist, and zero `.github/workflows/*` changes before enabling `SQUASH` auto-merge.
