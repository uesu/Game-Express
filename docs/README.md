# Game-Express documentation

Everything that does not belong in the [project README](../README.md). Start there for what
Game-Express is and how to set it up; come here for the detail.

## Setting it up and running it

| Doc | What's in it |
|---|---|
| **[CONFIGURATION.md](CONFIGURATION.md)** | every secret, variable, `games.json` field and `overrides.json` key |
| **[SCHEDULER.md](SCHEDULER.md)** | the cron-job.org job that triggers the monitor, the classic token, poll-rate reasoning, private-repo limits |
| **[ROLLOUT.md](ROLLOUT.md)** | switching on the per-game schedule copies safely, one game at a time |
| **[TESTING.md](TESTING.md)** | the manual test bench, what you should see in Discord, the local commands |
| **[TROUBLESHOOTING.md](TROUBLESHOOTING.md)** | symptom → fix |

## How it works

| Doc | What's in it |
|---|---|
| **[ACCURACY.md](ACCURACY.md)** | how a post becomes a card: detection, extraction, provenance, the code gate |
| **[SOURCES.md](SOURCES.md)** | every verified endpoint, with why it was chosen or rejected |
| **[BANNER_DATABASE.md](BANNER_DATABASE.md)** | where banner line-ups come from: the wiki readers, the precedence order, how an official notice is read, and how a TBA fills itself in |
| **[TIMESTAMP-PATTERNS.md](TIMESTAMP-PATTERNS.md)** | the release-rhythm study the speculation and the estimates are calibrated on |
| **[SECURITY.md](SECURITY.md)** | threat model: untrusted sources, secret handling, workflow permissions |

## Maintenance

| Doc | What's in it |
|---|---|
| **[DEPENDABOT.md](DEPENDABOT.md)** | what Dependabot watches, and the opt-in auto-merge |
| **[PYTHON_VERSION.md](PYTHON_VERSION.md)** | the automated Python-version bump workflow |
| **[PROD-REPO-SETUP.md](PROD-REPO-SETUP.md)** | splitting into a private dev repo + a public production repo |
| **[changelog/](changelog/)** | every release, newest first — [current line](changelog/CHANGELOG.md) · [archive](changelog/CHANGELOG_ARCHIVE.md) |

## Credits and legal

| Doc | What's in it |
|---|---|
| **[CREDITS.md](CREDITS.md)** | the upstream projects this depends on, plus community databases |
| **[../PRIVACY_POLICY.md](../PRIVACY_POLICY.md)** · **[../TERMS_OF_SERVICE.md](../TERMS_OF_SERVICE.md)** | the legal pair |

---

**Changing the code?** Read **[../AGENTS.md](../AGENTS.md)** first — the invariants that must not
be "fixed", the exact verification commands, and the traps that have already broken a run.
