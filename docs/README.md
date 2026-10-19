# Game-Express documentation

Everything that does not belong in the [project README](../README.md). Start there for what
Game-Express is and how to set it up; come here for the detail.

For a development/production split, start with [production setup](PROD-REPO-SETUP.md).
Use [.env.example](../.env.example) as a local template only; `.env` and `.env.*`
are ignored except the tracked template. Never copy live state back over production on a code sync.

## Setting it up and running it

| Doc | What's in it |
|---|---|
| **[CONFIGURATION.md](CONFIGURATION.md)** | every secret/variable and game/override field; full official-news setup and behavior |
| **[SCHEDULER.md](SCHEDULER.md)** | the cron-job.org job that triggers the monitor, the classic token, poll-rate reasoning, private-repo limits |
| **[ROLLOUT.md](ROLLOUT.md)** | switching on the per-game schedule copies safely, one game at a time |
| **[TESTING.md](TESTING.md)** | the manual test bench, what you should see in Discord, the local commands |
| **[TROUBLESHOOTING.md](TROUBLESHOOTING.md)** | symptom → fix |

## Official news — third feature, off by default

The [root README's third feature](../README.md#3--official-news-optional-off-by-default)
is the short overview. The operational instructions live here:

| Reference | Covers |
|---|---|
| [Setup, variables and destination secrets](CONFIGURATION.md#official-news-explicit-opt-in-default-off) | explicit opt-in, all five game keys, default-off grouping, dedicated webhooks and routing |
| [Select two games / choose channel names](CONFIGURATION.md#selecting-two-games-and-choosing-channel-names) | easy subset setup, arbitrary webhook destinations, independence from schedule/codes |
| [Full-content paging and overflow](CONFIGURATION.md#full-content-paging-and-overflow) | fixed 7,000 eligibility, maximum two messages, per-message budgets, excerpts, Part versus Page and final controls |
| [Source-preserving formatting](CONFIGURATION.md#source-preserving-formatting) | compact lists, attached hyphens, marker spacing, unchanged source words/URLs |
| [Measured long-strip grouping](CONFIGURATION.md#optional-measured-long-strip-grouping--implemented) | switch off/on, ratio and gallery limits, measurement bounds, boundaries and safe fallback |
| [Coverage and safe verification](CONFIGURATION.md#source-coverage-and-safe-verification) | source/index limits, no backfill/state reset, offline versus live evidence |
| [Sources](SOURCES.md#optional-full-content-news-adapter-2026-10-18) / [testing](TESTING.md#official-news-offline-coverage-and-read-only-checks) | adapters, bounded media preflight/refresh/holds, offline checks and read-only verification |

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
| **[PROD-REPO-SETUP.md](PROD-REPO-SETUP.md)** | fresh-repository runtime manifest, state-preserving cutover, news settings, safe later syncs |
| **[changelog/](changelog/)** | every change, newest first — [current line](changelog/CHANGELOG.md) · [archive](changelog/CHANGELOG_ARCHIVE.md) |

## Credits and legal

| Doc | What's in it |
|---|---|
| **[CREDITS.md](CREDITS.md)** | the upstream projects this depends on, plus community databases |
| **[../PRIVACY_POLICY.md](../PRIVACY_POLICY.md)** · **[../TERMS_OF_SERVICE.md](../TERMS_OF_SERVICE.md)** | the legal pair |

---

**Changing the code?** Read **[../AGENTS.md](../AGENTS.md)** first — the invariants that must not
be "fixed", the exact verification commands, and the traps that have already broken a run.
