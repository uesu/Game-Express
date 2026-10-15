# Dependabot & Dependency Locking Guide

See also: [Maintenance Architecture & Safe Update Guide](MAINTENANCE.md) · [Python Version Policy](PYTHON_VERSION.md) · [Security & Redaction](SECURITY.md)

## Hashed Dependency Locks (`pip-tools`)

Game-Express separates human-maintained version ranges from committed, hash-pinned lockfiles:

- [`requirements.in`](../requirements.in) → direct runtime dependency ranges (`aiohttp`, `feedparser`, `python-dotenv`, `typing-extensions`).
- [`requirements.txt`](../requirements.txt) → exact direct and transitive runtime versions with `--hash=sha256:...` digests compiled by `pip-tools==7.5.3` and `pip==26.1.1`.
- [`requirements-dev.in`](../requirements-dev.in) → developer, test, linter, and compiler toolchain pins (`-c requirements.txt`, `pip==26.1.1`, `pip-tools==7.5.3`, `pytest`, `pyyaml`, `ruff`).
- [`requirements-dev.txt`](../requirements-dev.txt) → exact hashed dev/test lockfile constrained against `requirements.txt` so test dependencies never drift from or replace runtime packages.

### Regenerating & Checking Locks

```bash
python .github/scripts/maintenance.py lock-compile
python .github/scripts/maintenance.py lock-check
```

Workflows install dependencies in frozen hash-verified mode:

```bash
python -m pip install --require-hashes --only-binary=:all: -r requirements.txt -r requirements-dev.txt
```

## Dependabot Configuration (`.github/dependabot.yml`)

[`.github/dependabot.yml`](../.github/dependabot.yml) configures weekly Monday `06:00 UTC` checks for two ecosystems:

1. **`pip` (`/`):**
   - `open-pull-requests-limit: 10`
   - `versioning-strategy: increase-if-necessary`
   - `cooldown`: `default-days: 3`, `semver-major-days: 7`
   - `groups`: `minor-and-patch` (`minor`, `patch`) and `major` (`major`)
2. **`github-actions` (`/`):**
   - Updates full 40-character commit SHAs and `# vX.Y.Z` version comments in `.github/workflows/*.yml`
   - `open-pull-requests-limit: 10`
   - `cooldown`: `default-days: 3`, `semver-major-days: 7`
   - `groups`: `minor-and-patch` (`minor`, `patch`) and `major` (`major`)

## Auto-Merge Policy (`maintenance_merge.yml`)

Dependabot auto-merge is handled by [`.github/workflows/maintenance_merge.yml`](../.github/workflows/maintenance_merge.yml) (not `ci.yml`):

- When repository variable `AUTO_MERGE_DEPENDABOT=yes` is set, `maintenance_merge.yml` evaluates PR metadata using `.github/maintenance.json` and `.github/scripts/maintenance.py` from the trusted `main` base commit.
- **`pip` PRs** (`dependabot[bot]` on `dependabot/pip/*` touching only `requirements.in`, `requirements.txt`, `requirements-dev.in`, `requirements-dev.txt`) are eligible for `SQUASH` auto-merge once `maintenance-ci` succeeds.
- **`github-actions` PRs** modify `.github/workflows/*.yml` and are intentionally **excluded from auto-merge** by `.github/maintenance.json` (`forbidden_path_prefixes: [".github/workflows/"]`) so workflow changes always receive explicit human review.
