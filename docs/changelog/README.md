# Changelog

Every Game-Express change, newest first. The log used to live at the bottom of the project
README; it now lives here so the README can stay a manual instead of a history book.

| File | Holds |
|---|---|
| **[CHANGELOG.md](CHANGELOG.md)** | current entries — **1.8.0 (October 2026) onward**. These still describe the code on `main`. |
| **[CHANGELOG_ARCHIVE.md](CHANGELOG_ARCHIVE.md)** | **1.0.0 → 1.7.0** (September 2026). History only: much of it was replaced by later releases. |

The newest entry is also summarised in the
[project README](../../README.md#-changelog).

## Dated, not numbered

Version numbers were retired on **2026-10-05**. Bumping one meant four files had to move in
lockstep — `gamexpress/__init__.py`, `CHANGELOG.md`, this index and the README summary — and
missing any one of them left the repo contradicting itself.

Builds now identify themselves by commit: `build_id()` reports the short `GITHUB_SHA`, so a run
summary reads `### Game-Express 03c1668 — …` and points at the exact code that posted the card.
A dated entry, its index row and the README's latest summary are the whole ritual; no version
number is bumped.

Releases up to and including `1.9.0` keep their numbers — that is what they shipped as, and
nothing is renumbered after the fact.

---

## Entries

| Entry | Date | Headline |
|---|---|---|
| [2026-10-10](CHANGELOG.md#2026-10-10) | 2026-10-10 | the card's own style: `EMOJI_TITLE` puts the server's `<:ananta1:…>` on every headline (and `parse_emoji` stops misreading names that start with "a"), full display names render on every banner line while the stored data keeps each source's form, the WuWa 4★ summary auto-hides once both phases are filled, the edit line names the banner keys that moved and who wrote them, locks are announced with their witnesses, and the WuWa banner-search warning stops firing on a merely empty menu |
| [2026-10-09](CHANGELOG.md#2026-10-09) | 2026-10-09 | the banner reader learns the ZZZ X dialect (a quoted channel title is never a character; the live 3.3 card heals itself), a posted Special Program card keeps its announcement (link, key art, air time) and prefers the X post, banners lock on confirmation (an official notice, or the hub and the wiki agreeing) with a three-hour wiki budget for TBA blocks, a single tweet is read from nitter.cf first, a deleted copy says it was deleted, and a retirement names the message it retired |
| [2026-10-08](CHANGELOG.md#2026-10-08) | 2026-10-08 | a card that should never have existed, plus the wrong art, the wrong link and no air time |
| [2026-10-06](CHANGELOG.md#2026-10-06) | 2026-10-06 | banner line-ups fill themselves in from the game wikis — plus a countdown fix and a documentation accuracy sweep |
| [2026-10-05](CHANGELOG.md#2026-10-05) | 2026-10-05 | the README stops being a history book, and the version number retires |
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

## Adding an entry

1. Add a `## YYYY-MM-DD` section at the **top** of [CHANGELOG.md](CHANGELOG.md), followed by a
   bold one-line headline.
2. Add its row to the table above, newest first.
3. Update the project's README [Changelog summary](../../README.md#-changelog) to describe the
   new latest entry.
4. Grep the docs for any count, cadence or flag the change affects
   (`README.md`, `AGENTS.md`, `docs/*.md`) — see
   [AGENTS.md § Conventions](../../AGENTS.md#8-conventions).

Entries are written for a reader who was not there: say what changed, and say *why* — the
incident, the measurement or the broken run that caused it.
