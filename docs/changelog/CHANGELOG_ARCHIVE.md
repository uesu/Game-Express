# Changelog archive — 1.0.0 → 1.7.0

The September 2026 history, kept verbatim and out of the way. Much of it describes
behaviour that later releases replaced (the Discord bot, the separate `test.yml`
workflow, the `dry_run` / `probe` dispatch inputs, hardcoded pre-install weekdays), so
read it as a record of *why* the current design looks the way it does — not as
instructions.

> Version numbers repeat in this range (two 1.3.0s, two 1.5.0s, two 1.6.0s). That is how
> they were published; entries are ordered by **date**, newest first.

Current releases: [CHANGELOG.md](CHANGELOG.md) · index: [README.md](README.md).

---

## 1.6.0 — 2026-09-27

**The pre-install lead is learned, not hardcoded**

- A missing pre-install timestamp is derived as **hours before maintenance start**, which carries
  both the day and clock time without brittle weekday arithmetic. Cold-start values reproduce the
  real 2026 notices (GI 43 h · HSR 88 h · ZZZ 42 h · WW 42 h).
- Every real pre-install/maintenance pair records its lead. Later versions use the per-game median;
  malformed values and leads above 14 days are ignored, and even-sized histories average their
  middle pair.
- Derived pre-install times remain labelled estimated and are never fed back into the history, so
  the fallback cannot validate itself. Official notices discovered through HoYoLAB, X/Nitter or
  Kuro replace the estimate automatically.

---

## 1.5.0 — 2026-09-27

**Deleted Discord cards heal themselves**

- Discord `404 / 10008 Unknown Message` on a schedule-card edit now means the original message was
  deleted: the current card is posted once and the replacement message id is adopted. The next run
  edits that replacement instead of retrying a dead id forever.
- Only a 404 takes that recovery path. A 400, 5xx or exhausted retry remains an error and never
  reposts; if the recovery post itself fails, the stale id is retained so the next run retries.
- The same production run established HSR 4.6's real pre-install lead as 88 hours (Thu 14:00 to
  Mon 06:00 UTC+8), now represented by the learned-hours model above rather than a weekday rule.

---

## 1.3.0 — 2026-09-27

**Card cleanup, banner lineups from a live feed, and proof the X lookup generalises**

- **Card cleanup:** removed redundant X button (the announcement tweet is already linked in the card title) while preserving buttons for non-X sources (HoYoLAB, official news page). Removed `🖼️ key art: …` and `Source: …` footer lines so the card footer stays clean.
- **Banner lineups from live feed (`hub.json`):** rate-up 5★ characters are filled from `ertezy.github.io/Kitsudock-data/hub.json` (rebuilt hourly, CC BY-SA 3.0; the project was renamed from Gacha-hub-info in Oct 2026 and the old URL now 404s) and phase-split around the version's release / maintenance timestamp. Sits at priority 5 (lowest in the monitor), only fills empty phases, refuses stale payloads (>14d), and can be disabled with `BANNER_FEED=0`.
- **Verified X announcement recall across eras:** verified 7/7 positive match across all captured program announcements spanning multiple wording families (GI Luna II, ZZZ 2.5, HSR 4.5/4.6, GI 7.1, ZZZ 3.2, WW 3.7).

---

## 1.7.0 — 2026-09-26

**The schedule card links the real announcement, and the Discord bot is gone**

- The announcement lookup now uses versions from the current run as well as state, so first runs and test runs recover the archived announcement and key art.
- Event, update-details and maintenance-notice titles are excluded from program matching; livestream URLs in `/live/`, `/shorts/` and `/embed/` now produce real thumbnails.
- Duplicate HoYoLAB artwork and alternate media renditions are collapsed, and incomplete banner lists no longer blank otherwise valid names.
- Wuthering Waves can use configured RSS/Atom mirrors, and tweet data falls back from fxtwitter to fixupx to vxtwitter.
- Program lookups run concurrently with each other and with countdown estimates.
- The Discord bot and all 24/7 self-hosting commands and files were removed; GitHub Actions is the only runtime.

---

## 1.6.0 — 2026-09-26

**Two modes, and the tests use real data**
- **The dialog is now just `mode` + what that mode needs.** `live` = the real monitor (`only`,
  `game`, `repost`). `test` = `webhooks` / `codes` / `schedule` / `all`. Gone: the `dry_run`
  input and the `probe` debug input (and the `gamexpress probe` command behind it).
- **The tests no longer post sample cards — they post what the sources really returned.** The
  `codes` test posts the real codes currently on the live sources to each game's own codes
  channel; the `schedule` test posts the real schedule card (the announcement's own link and key
  art, the livestream date/time, the maintenance timestamps and the banners). A sample card could
  hide a broken source; these cannot.
- Games that are not out yet (HNA, ANANTA) have no real code to fetch, so the codes test gives
  them example codes — `test-card --kind codes --unlaunched` (the games with `"released": false`).
- **A test posts to the real channels, labelled 🧪 TEST, and never writes the state**, so the
  live run still posts the real thing later. `DISCORD_WEBHOOK_TEST` is no longer used (the
  private-test-channel mode is gone); the secret can be deleted.
- The live run is unchanged apart from losing `dry_run`: post what is new, edit silently when
  official info arrives, commit the state, and never post twice (state keys + payload hashes).

---

## 1.5.0 — 2026-09-26

**The dispatch form says which of the two things you are doing**
- **`mode` = `live` or `test`.** Still one workflow, but the Run-workflow dialog now opens with
  the choice between the real monitor and the manual test bench, every input is labelled for the
  mode it belongs to, and the steps are named `LIVE · …` / `TEST · …` so the log says which ran.
- **`only` is now the single "simplify" switch** for both modes (`all` / `schedule` / `codes`);
  the duplicate `kind` input is gone.
- **New live input `probe`** — debug ONE real schedule post, e.g. `starrail:4.6`. It prints what
  the lookback window saw, what is stored for that version, the program lookup tab by tab with
  the air time parsed out of the article text, **every image it found (ranked, with why the
  winner won)** and the card it would build. Read-only: nothing is posted or saved. Also on the
  CLI as `python -m gamexpress probe starrail:4.6`.
- The lookup is now one function (`runner.find_program`) shared by the monitor and the probe, so
  the debug report can never drift from what a real run does.
- cron-job.org is unaffected: it sends no inputs, so `mode` defaults to `live` and the pass is
  exactly what it was.

---

## 1.4.0 — 2026-09-25

**The test bench moves into the Monitor**
- **`test.yml` is gone; the manual test bench is now a mode of the Monitor workflow.** In
  *Actions → Game-Express Monitor → Run workflow*, pick `test` = `webhooks` / `sample-cards` /
  `live-dry-run` / `live-test-channel` / `offline-tests` / `full`. New inputs `kind` and `ping`
  came across unchanged.
- A test run is still safe everywhere: the **Run monitor** step and the **Commit state** step are
  both gated on `inputs.test == ''`, so a test never posts to the real channels and never writes
  `state/state.json` — and it still works on a dev repo with `ENABLED_FEATURES=none`
  (the job's `if` is now `vars.ENABLED_FEATURES != 'none' || inputs.test != ''`).
- cron-job.org keeps calling the same `monitor.yml` dispatch with no `test` input, so scheduled
  behaviour is byte-identical to before.

---

## 1.3.0 — 2026-09-25

**The schedule card shows the real announcement**
- **The card now shows the program announcement, not whichever post the run happened to see.**
  HSR 4.6 linked to the *Update and Maintenance Notice* and showed its Pompom cover, because the
  Special Program preview (article 46691962) was 11 days older and had fallen out of the lookback
  window. A new lookup finds the announcement on the **official news page** (or the HoYoLAB news
  list, paged back past the window) and uses its link, its key art and its air time.
- **A maintenance notice's own cover is no longer used as the card image** — it is not the
  program's key art. The notice stays as a Source link when nothing better is known.
- **Images are upgraded to the biggest rendition each source serves** (`gamexpress/media.py`):
  tweet photos get `?name=orig` (X serves `small` by default), nitter `/pic/` proxies are
  rewritten to `pbs.twimg.com`, and YouTube thumbnails go `hqdefault` → `maxresdefault`
  (1280×720). A URL that already asks for a size is left exactly as the source gave it.
- The air time from a recovered announcement is an official time, so a program that has already
  aired is still shown (`<t:…:F> or <t:…:R>` — "5 days ago"), and it never overwrites a time an
  official post already gave.
- `PROGRAM_MEDIA=0` switches the lookup off. `docs/SOURCES.md` lists the news pages and what each
  one is verified to serve.

---

## 1.2.0 — 2026-09-25

**Card buttons and maintenance estimates**
- **Codes card buttons cleaned up.** `Redeem Page`, `Youtube` and `Twitch` are gone from codes
  cards — the livestream buttons belong to the Special Program / Special Broadcast card, and
  `Redeem Page` was redundant next to one prefilled Redeem button per code.
- **New community row** after a separator: `Citlali News` → `https://discord.gg/HyrVP9wRXu` with
  the animated `starward11` emoji (`COMMUNITY_BUTTONS`, max 3, `none` = off).
- **Maintenance times are estimated when the official notice hasn't arrived yet** (countdown
  sites, lowest priority, marked with a 🕒 line on the card, replaced automatically).
- Time parsing understands named zones such as `8:00 AM EDT`.
- Docs: `docs/SOURCES.md` lists every countdown source; **60 offline tests**.

---

## 1.1.1 — 2026-09-25

**Fixes from the first live runs**
- **Expired codes are no longer mistaken for new ones.** The first live dry run showed 3 HSR +
  3 WW livestream codes that had expired on 2026-09-21 but were still listed as active. Wikis
  keep them under *Active*, PromoGacha never deletes, and Open Gacha Codes lags. The bot now:
  - reads *valid until* dates on the fandom wikis (all three table formats, with time zones);
  - treats a passed date as expired, whatever other sources say;
  - strikes the code through on already-posted cards.
- **More accurate wiki parsing:**
  - Genshin rows that hold several codes are split;
  - Star Rail rows with nested `{{Item List}}` keep their dates;
  - the stray `TERMINOLOGYINFOBOX` "code" is gone.
- **PromoGacha counts as its upstream.** It counts as seria or fandom, and its stale copies are
  ignored.
- **Cleaner rewards.** Open Gacha Codes `Unknown reward (hash)` entries and duplicate reward
  lines are dropped.
- **Shorter summaries.** Expired codes are counted in one line; codes waiting for a second
  source are listed in one line.
- **Schedule cards:**
  - no more misleading `Special Program: TBA` once the update is known (the program already
    aired);
  - `repost` now explains when a version isn't tracked (e.g. an unannounced `genshin:7.2`);
  - the first run notes versions that are already out.
- **Dependabot:**
  - auto-merge moved into `ci.yml` as a job that runs after the tests (the separate
    `workflow_run` workflow never fired);
  - no custom labels (they had to exist first);
  - only PRs for versions outside the allowed range.
- **One repo can be production.** The docs no longer tell you to set `ENABLED_FEATURES=none` on
  this repo; that variable is only for a development copy. [SCHEDULER.md](../SCHEDULER.md)
  explains private repos: 2,000 free Actions minutes a month means a 30-minute schedule.
- **Tests are hermetic again.** The bot test read the repo's `state/state.json`, so it failed
  (on `main` too) as soon as the Monitor had committed real codes. It now uses its own state.
- **Test bench:** `offline-tests` installs discord.py + PyYAML so no check is skipped.
  `x.yuuki.sh` (403 on GitHub runners) moved to the end of the nitter fleet. **55 offline
  tests.**

---

## 1.1.0 — 2026-09-25

**Per-game code channels, cron-job.org, Test workflow**
- **Per-game codes webhooks** for all 6 games (`DISCORD_WEBHOOK_CODES_GENSHIN` · `_STARRAIL` ·
  `_HNA` · `_ZZZ` · `_WUWA` · `_ANANTA`, short names like `_HSR` / `_WW` work too).
- **Scheduler = cron-job.org.** GitHub's native `schedule:` is disabled in `monitor.yml`
  (News-Express style); every secret is wired explicitly; actions bumped to v7.
- **Game-Express Test workflow**: webhook check, labelled sample cards, live dry run, live cards
  to a test channel, offline tests. It never commits and pings nobody by default.
- **4★ = TBA when unsure**: exact expected count, name plausibility, and a sticky
  disagreement rule.
- **Codes**: new sources (Hum-Bao validator, Open Gacha Codes, wuthering.gg for Wuthering
  Waves), expired-code detection (an expired flag vetoes a post; posted codes are struck
  through silently), shared-backend sources counted once, and the reason for every pending
  code in the summary.
- **Speed**: all sources are fetched in parallel with a connection cap and per-request
  timeouts; the nitter fleet is probed in batches; run time is shown in the summary.
- **Prepared games**: `ENABLE_GAMES` variable; ANANTA switches itself on at its announced
  launch (2027-01-15); HNA gets the HoYoLAB livestream-code module (gid 9).
- `check-webhooks` command, `test-card --ping` (no ping by default, 🧪 TEST label),
  `validate` shows which secret feeds which channel, and `preview` writes an HTML page.
- Optional Dependabot auto-merge (off unless `AUTO_MERGE_DEPENDABOT=yes`), grouped weekly
  Dependabot PRs. New docs: SCHEDULER, TESTING, DEPENDABOT. 47 offline tests.

---

## 1.0.0 — 2026-09-25

**Initial release**
- **Schedule announcements** for GI / HSR / ZZZ / WW, with HNA and ANANTA prepared.
  - Pattern-triggered and posted once per version, then silent in-place edits as official
    maintenance, pre-install, banner and override data arrives.
  - The 4 reference cards were converted to Components V2 with the buttons nested inside the
    container.
- **Code poster** with an official / verified / 2-source accuracy gate, a silent first-run seed,
  pending codes, and per-code prefilled Redeem buttons.
- **Sources**: HoYoLAB official API + c3kay fallback, official X via a 15-instance nitter fleet +
  FxTwitter/vxTwitter, the Kuro site, HoYoPlay `getGameBranches`, the Kuro launcher, seria,
  ennead, the fandom API, and PromoGacha.
- **Operations**:
  - a queued workflow with a fresh branch checkout, and state commits even after partial failure;
  - all secrets and variables are auto-exposed, so per-game overrides need no YAML edits;
  - two-instance auto fail-over with shared dedup;
  - `test-card`, `preview` and `validate` commands, and a GitHub job summary with source health.
- **Bot mode** (`/codes`, `/schedule`, `/status`) plus free-hosting guides and deploy files.
- **33 offline tests** (real-post fixtures + golden cards), run as the CI gate.

