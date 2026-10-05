# Changelog

Every Game-Express release, newest first. The log used to live at the bottom of the project
README; it now lives here so the README can stay a manual instead of a history book.

| File | Holds |
|---|---|
| **[CHANGELOG.md](CHANGELOG.md)** | the current release line — **1.8.0 → 1.9.0** (October 2026). These entries still describe the code on `main`. |
| **[CHANGELOG_ARCHIVE.md](CHANGELOG_ARCHIVE.md)** | **1.0.0 → 1.7.0** (September 2026). History only: much of it was replaced by later releases. |

The latest release is also summarised in the
[project README](../../README.md#-changelog).

---

## Releases

| Version | Date | Headline |
|---|---|---|
| [`1.9.0`](CHANGELOG.md#190--2026-10-02) | 2026-10-02 | the run stops waiting on a hung mirror, and the dead weight is gone |
| [`1.8.1`](CHANGELOG.md#181--2026-10-01) | 2026-10-01 | Python 3.14 |
| [`1.8.0`](CHANGELOG.md#180--2026-10-01) | 2026-10-01 | future Python bumps, faster installs, two advisory scans |
| [`1.6.0`](CHANGELOG_ARCHIVE.md#160--2026-09-27) | 2026-09-27 | the pre-install lead is learned, not hardcoded |
| [`1.5.0`](CHANGELOG_ARCHIVE.md#150--2026-09-27) | 2026-09-27 | deleted Discord cards heal themselves |
| [`1.3.0`](CHANGELOG_ARCHIVE.md#130--2026-09-27) | 2026-09-27 | card cleanup, banner lineups from a live feed, and proof the X lookup generalises |
| [`1.7.0`](CHANGELOG_ARCHIVE.md#170--2026-09-26) | 2026-09-26 | the schedule card links the real announcement, and the Discord bot is gone |
| [`1.6.0`](CHANGELOG_ARCHIVE.md#160--2026-09-26) | 2026-09-26 | two modes, and the tests use real data |
| [`1.5.0`](CHANGELOG_ARCHIVE.md#150--2026-09-26) | 2026-09-26 | the dispatch form says which of the two things you are doing |
| [`1.4.0`](CHANGELOG_ARCHIVE.md#140--2026-09-25) | 2026-09-25 | the test bench moves into the Monitor |
| [`1.3.0`](CHANGELOG_ARCHIVE.md#130--2026-09-25) | 2026-09-25 | the schedule card shows the real announcement |
| [`1.2.0`](CHANGELOG_ARCHIVE.md#120--2026-09-25) | 2026-09-25 | card buttons and maintenance estimates |
| [`1.1.1`](CHANGELOG_ARCHIVE.md#111--2026-09-25) | 2026-09-25 | fixes from the first live runs |
| [`1.1.0`](CHANGELOG_ARCHIVE.md#110--2026-09-25) | 2026-09-25 | per-game code channels, cron-job.org, Test workflow |
| [`1.0.0`](CHANGELOG_ARCHIVE.md#100--2026-09-25) | 2026-09-25 | initial release |

> Version numbers repeat before 1.8.0 (two 1.3.0s, two 1.5.0s, two 1.6.0s) — that is how they
> were published. Entries are ordered by **date**, not by number.

---

## Adding a release

1. Bump `__version__` in [`gamexpress/__init__.py`](../../gamexpress/__init__.py) — it is printed
   in every run summary.
2. Add a `## x.y.z — YYYY-MM-DD` section at the **top** of [CHANGELOG.md](CHANGELOG.md), followed
   by a bold one-line headline.
3. Add the row to the table above.
4. Grep the docs for any count, cadence or flag the release changed
   (`README.md`, `AGENTS.md`, `docs/*.md`) — see
   [AGENTS.md § Conventions](../../AGENTS.md#8-conventions).

Entries are written for a reader who was not there: say what changed, and say *why* — the
incident, the measurement or the broken run that caused it.
