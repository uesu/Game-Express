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
4. Opens a PR (via [`peter-evans/create-pull-request`](https://github.com/peter-evans/create-pull-request))
   labelled `python-bump`, which triggers the normal `ci.yml` `pull_request` run — the exact same
   163-test / compile / `validate` / preview gate every Dependabot PR goes through.

## It never merges blind

A `python-bump` PR only merges automatically when **all** of these hold (job
`automerge-python-bump` in `ci.yml`):

- the PR carries the `python-bump` label (so this can never be confused with a Dependabot PR, or
  any other automated PR that might exist in the future);
- the `test` job (163 offline tests, compile, `validate`, preview) passed **on that exact
  commit** — a later push invalidates a stale approval, same rule as Dependabot auto-merge;
- the repository **variable** `AUTO_MERGE_PYTHON_BUMP` is set to `yes`.

Leave the variable unset (the default) and the workflow only ever opens the PR for you to read
and merge by hand — nothing is merged without a human unless you opt in.

**Recommended:** leave `AUTO_MERGE_PYTHON_BUMP` unset for at least the *first* bump this produces
(Python 3.15 is expected around October 2027). A brand-new Python *feature* release is the
riskiest moment for any third-party dependency to have caught up; reviewing that one PR by hand
costs a minute and costs nothing if it's clean. Turn auto-merge on afterwards if you'd rather not
look at these at all.

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
