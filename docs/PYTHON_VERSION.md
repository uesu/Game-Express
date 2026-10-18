# Keeping the Python version current

CI, the live monitor and the bump bootstrap use exact CPython **3.14.8** pins.
A patch no longer changes implicitly through a `3.14` series selector.

The existing weekly/manual `python_version_bump.yml` and script read the stable
Linux x64 builds in actions/python-versions. They prefer a newer current-series
patch; otherwise they consider the next minor series. Numeric version comparison
handles patches such as .9 and .10 correctly. Prereleases, skipped minor series
and major migrations are not automatically proposed.

Before publishing, the workflow installs the candidate interpreter, requires
prebuilt wheels, and runs compilation, config validation, all three offline test
runners and preview rendering. Missing interpreter/wheels or failing gates defer
the proposal. Every dependent gate checks that its prerequisites succeeded.

Only existing allowlisted workflow pins and, when supported, Ruff's major/minor
target are rewritten. Missing files in a runtime-only instance are skipped.
Generated PRs require review of current runtime documentation before merging;
the script never blindly rewrites README, docs or dated history.

## Attended merges

All Python patch and minor update PRs require human review/merge. Detection,
validation and publication remain automatic. AUTO_MERGE_PYTHON_BUMP is a legacy
variable: yes/all/unset no longer change behavior, and no settings change is
required to enforce this policy. Major-version migrations remain deliberate work.

Dependabot still handles package/action updates. With AUTO_MERGE_DEPENDABOT=yes,
its eligible package-only PRs can merge after tests, but PRs changing workflow
files (including renamed/deleted workflow paths) wait for attended merging.

This policy reduces unnoticed interruptions, not GitHub's security controls.
After merging/copying a live-workflow update, confirm its next run executes.
If GitHub flags it, a writer must review it before approving. Cron dispatches
alone do not prove the monitor ran; never auto-approve a security warning.

## Publication credentials

Keep BUMP_PAT in Actions secrets, with access to this repository and Contents,
Pull requests and Workflows write permissions as required by the token type.
A classic token uses repo/workflow scopes. Never commit or print its value.
Retain the existing repository setting permitting Actions PR creation. Missing,
expired or insufficient credentials require attention; this policy does not
bypass permissions or branch rules. A PAT-published PR can trigger ordinary CI;
the workflow also validates the candidate before the PR exists.

To stop automatic proposals, disable the bump workflow in Actions. Do not delete
posting state or modify the live monitor's scheduler to stop update proposals.
