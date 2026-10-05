# Dependabot: do we need it?

**Short answer: it's optional. The monitor runs fine without it.** It is set up the same way as
News-Express: it stays on in the development repo, and auto-merge is available but off by
default.

## What it does

Once a week (Monday), Dependabot checks two things. When there is something new, it opens
**one pull request** per group:

| Group | Watches | Example PR |
|---|---|---|
| `deps(python)` | `requirements.txt` | `aiohttp` 3.x → 4.0 |
| `deps(actions)` | the actions used in `.github/workflows/*` | `actions/checkout` v7 → v8 |

The **CI** workflow tests every Dependabot PR: install, compile, validate, and the full offline
tests. Nothing reaches `main` until you merge it, or until auto-merge does (see below).

- **Python PRs are rare on purpose** (`versioning-strategy: increase-if-necessary`). The ranges
  in `requirements.txt` already allow every compatible release, and each run installs the
  newest one. So Dependabot only opens a PR when a release falls outside the range, like
  aiohttp 4.0.
- **No custom labels.** Dependabot adds its default `dependencies` label and creates it
  itself. The first PR (#2) warned that custom labels didn't exist yet; they were simply
  skipped, and the update itself was fine.

## Why it's optional

- **Python packages** are version *ranges* (`aiohttp>=3.14.3,<4`). Every run already installs the
  newest compatible bug-fix release, with no PR needed. Dependabot only matters when a new
  *major* version comes out.
- **GitHub Actions** are pinned to full commit SHAs with a `# v7` style comment — a tag can be
  repointed at malicious code (that is exactly what happened to `tj-actions/changed-files` in
  March 2025, CVE-2025-30066), a SHA cannot. Dependabot updates the SHA *and* the comment, so
  this costs nothing in maintenance and gains patch-level visibility that a floating major tag
  hides. They keep working for a long time;
  GitHub announces deprecations months in advance. A Dependabot PR is simply the easiest way to
  follow them.

## Recommended setup

| Repo | Dependabot | Auto-merge |
|---|---|---|
| **uesu/Game-Express** (code home; can also be production) | on (`.github/dependabot.yml`) | optional: variable `AUTO_MERGE_DEPENDABOT=yes` |
| **instance repos** (alpha / bravo) | not needed. Delete `.github/dependabot.yml` there, or ignore its PRs | off |

Instance repos get updates the same way as any other change: copy the updated files from the
development repo (or *Sync fork* if they are forks).

## Auto-merge (opt-in)

The last job of `.github/workflows/ci.yml` (**Dependabot auto-merge (opt-in)**) does nothing
unless the repository variable **`AUTO_MERGE_DEPENDABOT=yes`** exists.

It used to be a separate `workflow_run` workflow. That trigger never fired in production
(2026-09-25), so it is now a job that simply waits for the test job. When the variable is set,
a Dependabot PR is merged only if all of these hold:

- the PR was opened by `dependabot[bot]`;
- the **test** job of CI passed for exactly this commit (the merge is pinned to the tested
  commit, so a newer push waits for its own CI run);
- the PR is open, not a draft, and GitHub accepts the merge (squash, or whichever merge style
  your repo allows).

For Dependabot PRs GitHub gives workflows a read-only token. The auto-merge job raises it with
the `permissions` key for that one job, which GitHub explicitly allows. The job never checks
out the PR's code.

**To enable it:** *Settings → Secrets and variables → Actions → Variables → New repository
variable* → `AUTO_MERGE_DEPENDABOT` = `yes`. Delete the variable to turn it off again.

**To turn Dependabot off completely:** delete `.github/dependabot.yml`. You can also turn off
*Settings → Code security → Dependabot version updates*.

**Note:** the Python interpreter version itself (`python-version: '3.14'`) is invisible to
Dependabot — it's a plain string in workflow YAML, not a tracked ecosystem file.
`python_version_bump.yml` covers that one gap on its own schedule, and it does **not** use the
job described above: a PR it opens carries the built-in `GITHUB_TOKEN`, which GitHub refuses to
let trigger further workflows, so no CI check can ever appear on it. It therefore runs the same
gate itself, under the new interpreter, before the PR exists, and merges from there behind
`AUTO_MERGE_PYTHON_BUMP=yes`. See [docs/PYTHON_VERSION.md](PYTHON_VERSION.md).

That restriction does **not** apply to Dependabot, which GitHub does let trigger workflows — so
the `test` job really does run on a Dependabot PR, and the gate above is real.
