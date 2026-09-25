# Dependabot: do we need it?

**Short answer: it's optional. The monitor runs fine without it.** It is set up the same way as
News-Express: it stays on in the development repo, and auto-merge is available but off by
default.

## What it does

Once a week (Monday), Dependabot checks two things. When there is something new, it opens
**one pull request** per group:

| Group | Watches | Example PR |
|---|---|---|
| `deps(python)` | `requirements.txt`, `requirements-bot.txt` | `aiohttp` 3.x → 4.0 |
| `deps(actions)` | the actions used in `.github/workflows/*` | `actions/checkout` v7 → v8 |

The **CI** workflow tests every Dependabot PR: install, compile, validate, and the 47 offline
tests. Nothing reaches `main` until you merge it, or until auto-merge does (see below).

## Why it's optional

- **Python packages** are version *ranges* (`aiohttp>=3.9,<4`). Every run already installs the
  newest compatible bug-fix release, with no PR needed. Dependabot only matters when a new
  *major* version comes out.
- **GitHub Actions** are pinned to major versions (`@v7`). They keep working for a long time;
  GitHub announces deprecations months in advance. A Dependabot PR is simply the easiest way to
  follow them.

## Recommended setup

| Repo | Dependabot | Auto-merge |
|---|---|---|
| **uesu/Game-Express** (development) | on (`.github/dependabot.yml`) | optional: variable `AUTO_MERGE_DEPENDABOT=yes` |
| **instance repos** (alpha / bravo) | not needed. Delete `.github/dependabot.yml` there, or ignore its PRs | off |

Instance repos get updates the same way as any other change: copy the updated files from the
development repo (or *Sync fork* if they are forks).

## Auto-merge (opt-in)

`.github/workflows/dependabot_auto_merge.yml` does nothing unless the repository variable
**`AUTO_MERGE_DEPENDABOT=yes`** exists. When it is set, a Dependabot PR is squash-merged only
if all of these hold:

- the PR was opened by `dependabot[bot]`;
- the **CI** workflow finished **successfully** for the PR's latest commit;
- the PR is open, not a draft, and GitHub reports it mergeable;
- every check on that commit is green (success / skipped / neutral).

The workflow never checks out or runs PR code with write access.

**To enable it:** *Settings → Secrets and variables → Actions → Variables → New repository
variable* → `AUTO_MERGE_DEPENDABOT` = `yes`. Delete the variable to turn it off again.

**To turn Dependabot off completely:** delete `.github/dependabot.yml`. You can also turn off
*Settings → Code security → Dependabot version updates*.
