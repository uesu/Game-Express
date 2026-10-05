# Keeping the Python version current

**Dependabot cannot do this one job.** It watches `requirements.txt` (a tracked
`package-ecosystem: pip`) and the `uses: actions/...@vN` lines in workflows (a tracked
`package-ecosystem: github-actions`) — see [docs/DEPENDABOT.md](DEPENDABOT.md). The interpreter
itself, `python-version: '3.14'` inside `ci.yml` / `monitor.yml`, is just a plain string in
workflow YAML, not a file in either of those ecosystems, so it is invisible to Dependabot by
design. `.github/workflows/python_version_bump.yml` fills that one gap.

## What already happens automatically, with no workflow at all

`python-version:` is pinned to the **minor** series only (`'3.14'`, not `'3.14.8'`). GitHub's
hosted runners always install the newest available patch of that series, so a bugfix release
(3.14.8 → 3.14.9 → …) needs **zero** action from anyone — it is already as automatic as it gets.

## What the bump workflow does

Once a week (Monday, same day Dependabot checks), and on demand via *Actions → Python version
bump (auto) → Run workflow*:

1. Reads the manifest [`actions/python-versions`](https://github.com/actions/python-versions)
   itself publishes (`versions-manifest.json`) — the **exact list `actions/setup-python`
   downloads from**. Whatever this workflow proposes is therefore already installable on the
   runner the moment the PR opens; nothing is guessed from a release-announcement blog post.
2. Takes the newest series marked `stable: true` there with a Linux build (pre-releases /
   release candidates are excluded by that flag).
3. If it's newer than the currently pinned series, it edits `ci.yml` and `monitor.yml`, and
   tries bumping `ruff.toml`'s `target-version` too — but only after confirming the **installed**
   `ruff` actually recognises that target (`ruff check --target-version pyNEW`). A brand-new
   Python series sometimes ships a few weeks before Ruff adds a matching target; when that
   happens, `ruff.toml` is left untouched and the PR body says so, instead of writing a config
   value Ruff would reject.
4. **Proves the bump before proposing it.** It installs the new interpreter, requires every
   dependency to come from a **prebuilt wheel** (`--only-binary=:all:` — on the day a new series
   lands, `aiohttp` and its compiled friends have no matching ABI wheels yet), then re-runs CI's
   own gate — `compileall`, `validate`, the offline suite, the preview render — **under the new
   interpreter, on the already-rewritten tree**. If the interpreter will not install, if wheels
   are missing, or if a gate is red, nothing is proposed: the run logs a warning and next Monday
   tries again. A deferral, never a failure.

   Each of those three steps re-checks that the interpreter *actually* switched. If it did not,
   `python` would still be the old one and a green gate here would be a lie — so the chain stops
   instead of producing a PR that claims a validation it never did.
5. Only then opens a PR (via [`peter-evans/create-pull-request`](https://github.com/peter-evans/create-pull-request))
   labelled `python-bump`.

> **Why the gate lives in this workflow and not in `ci.yml`.** A PR opened with the built-in
> `GITHUB_TOKEN` does **not** trigger other workflows, so `ci.yml`'s `pull_request` trigger never
> fires on it and no check is ever posted. A `needs: test` gate over in `ci.yml` would wait
> forever — which is exactly why the old `automerge-python-bump` job could never run and has been
> removed. Validating here is also *strictly more informative*: `ci.yml` would have tested the
> **old** pin, this tests the new one.

## It never merges blind

A `python-bump` PR only merges automatically when **both** of these hold (the final step of
`python_version_bump.yml`):

- every dependency installed from a prebuilt wheel **and** `compileall` + `validate` + the
  offline suite + the preview render all passed under the **new** interpreter — the PR does not
  exist otherwise, so there is nothing to merge;
- the repository **variable** `AUTO_MERGE_PYTHON_BUMP` is set to **`all`**. `yes` is deliberately
  *not* enough here — see the box below.

Leave the variable unset, or set it to `yes`, and the workflow only ever opens the PR for you to
read and merge by hand — nothing is merged without a human unless you explicitly set `all`.

> **`yes` does NOT merge in this repo, on purpose.** One rule then holds everywhere:
>
> | value | News-Express family (pins `3.14.7`) | Game-Express (pins `3.14`) |
> |---|---|---|
> | unset | nothing auto-merges | nothing auto-merges |
> | `yes` | patch bumps auto-merge | **nothing auto-merges** — no patch PRs exist |
> | `all` | patch **and** series bumps auto-merge | series bumps auto-merge |
>
> Read it as *“`yes` = merge the routine bumps; `all` = also merge the new-series jump.”* Because
> this repo pins a **series** (`python-version: '3.14'`) and `setup-python` resolves patches by
> itself, there are no routine bumps here to merge — so `yes` correctly merges nothing. That is
> what lets you set `AUTO_MERGE_PYTHON_BUMP=yes` in **every** repo and still be certain a 3.15
> jump always waits for a human.

The merge tries squash, then merge, then rebase, and settles for a warning if the repository
has all three disabled. A proven-green bump should never show up as a red run because of a
repository setting.

**Recommended:** keep `AUTO_MERGE_PYTHON_BUMP` at `yes` (or unset) so the series bump always
waits for you. Python 3.15 is due around **October 2026**. A brand-new Python *feature* release
is the riskiest moment for any third-party dependency to have caught up; reading that one PR
costs a minute and costs nothing if it's clean. Set `all` afterwards if you'd rather not look at
these at all.

## One-time setup this needs

*Settings → Actions → General → Workflow permissions → "Allow GitHub Actions to create and
approve pull requests."* GitHub blocks a workflow from opening its own PRs until this is turned
on — the same kind of one-time repository setting as the classic PAT in
[docs/SCHEDULER.md](SCHEDULER.md).

## Why this can't quietly break the live monitor

- It can only ever propose a version GitHub's own tooling already considers installable — not a
  guess based on a release date.
- It can't merge without a fully green run of the real test suite, and only when you've opted in.
- Merging to `main` is what deploys (per the README's "Setup" section) — so even an auto-merged
  bump only reaches the running monitor on its next scheduled run, same as any other change.
- Worst case it's ever wrong: it's one commit, revertable exactly like a Dependabot bump.

## To turn it off completely

Delete `.github/workflows/python_version_bump.yml` (and, if you'd set it, the
`AUTO_MERGE_PYTHON_BUMP` repository variable). The interpreter version then only changes when you
edit `python-version:` yourself.
