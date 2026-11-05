# Changelog

Latest: [X: link / app card artwork is not tweet media](CHANGELOG.md#2026-11-05--x-link--app-card-artwork-is-not-tweet-media).

Previous: [News: multi-line article titles render as one link](CHANGELOG.md#2026-11-05--news-multi-line-article-titles-render-as-one-link).

Previous: [Feature 4: third card "Servers Live" + actual End Time on the maintenance card](CHANGELOG.md#2026-11-04--feature-4-third-card-servers-live--actual-end-time-on-the-maintenance-card).

Previous: [Reddit: the Devvit relay is the primary listing (intake reader)](CHANGELOG.md#2026-11-02--reddit-the-devvit-relay-is-the-primary-listing-intake-reader).

Previous: [Beta: translation removed; CN shown as CN; source order](CHANGELOG.md#2026-11-02--beta-translation-removed-cn-shown-as-cn-source-order).

Previous: [Beta: per-item probe when the changelog is blocked](CHANGELOG.md#2026-11-01--beta-per-item-probe-when-the-changelog-is-blocked).

Previous: [Beta: ZZZ 3.4.2 card polish (subtext, placeholder names)](CHANGELOG.md#2026-11-01--beta-zzz-342-card-polish-subtext-placeholder-names).

Previous: [Beta: moving the beta channel no longer silences the feature](CHANGELOG.md#2026-10-30--beta-moving-the-beta-channel-no-longer-silences-the-feature).

Previous: [Beta: direction follows the kit, and mixed-build revisions say so](CHANGELOG.md#2026-10-30--beta-direction-follows-the-kit-and-mixed-build-revisions-say-so).

Previous: [Beta: released kits are diffs, and the card explains itself](CHANGELOG.md#2026-10-30--beta-released-kits-are-diffs-and-the-card-explains-itself).

Previous: [Timing phrases, reveal dedup and edit safety](CHANGELOG.md#2026-10-29--timing-phrases-reveal-dedup-and-edit-safety).

Previous: [Follow-up regression guards](CHANGELOG.md#2026-10-29--follow-up-regression-guards).

Previous: [Optional character reveal mentions](CHANGELOG.md#2026-10-29--optional-character-reveal-mentions).

Previous: [News YouTube watch links](CHANGELOG.md#2026-10-29--news-youtube-watch-links).

Previous: [Maintenance timing safeguards and actionable persistence summary](CHANGELOG.md#2026-10-29--maintenance-timing-safeguards-and-actionable-persistence-summary).

Previous: [Redlib Tier-1 fleet expansion (24 → 27) and inline-video / crosspost media parity](CHANGELOG.md#2026-10-27--redlib-tier-1-fleet-expansion-24--27-and-inline-video--crosspost-media-parity).

Previous: [CI annotation hygiene, zizmor action pin alignment, and beta post-merge edge-case hardening](CHANGELOG.md#2026-10-25--ci-annotation-hygiene-zizmor-action-pin-alignment-and-beta-post-merge-edge-case-hardening).

Previous: [Beta Prime Formatting Style, active-beta gating, media galleries, and CN/CHS cross-check](CHANGELOG.md#2026-10-25--beta-prime-formatting-style-active-beta-gating-media-galleries-and-cnchs-cross-check).

Previous: [Encore secondary beta API backup](CHANGELOG.md#2026-10-25--encore-secondary-beta-api-backup).

Previous: [Gachabase HTML revision discovery](CHANGELOG.md#2026-10-25--gachabase-html-revision-discovery).

Previous: [Future Encore build transition coverage](CHANGELOG.md#2026-10-25--future-encore-build-transition-coverage).

Previous: [Content-driven beta pages without display truncation](CHANGELOG.md#2026-10-25--content-driven-beta-pages-without-display-truncation).

Previous: [Encore beta API fallback for WuWa](CHANGELOG.md#2026-10-25--encore-beta-api-fallback-for-wuwa).

Previous: [Truthful bounded beta comparisons and source credits](CHANGELOG.md#2026-10-25--truthful-bounded-beta-comparisons-and-source-credits).

Previous: [Live beta equipment schemas and restart-safe batches](CHANGELOG.md#2026-10-25--live-beta-equipment-schemas-and-restart-safe-batches).

Every Game-Express change, newest first. The log used to live at the bottom of the project
README; it now lives here so the README can stay a manual instead of a history book.

| File | Holds |
|---|---|
| **[CHANGELOG.md](CHANGELOG.md)** | current entries — **1.8.0 (October 2026) onward**. Unreleased sections describe proposed changes, not proof of deployment. |
| **[CHANGELOG_ARCHIVE.md](CHANGELOG_ARCHIVE.md)** | **1.0.0 → 1.7.0** (September 2026). History only: much of it was replaced by later releases. |

## Dated, not numbered

Version numbers were retired on **2026-10-05**. Bumping one meant four files had to move in
lockstep — `gamexpress/__init__.py`, `CHANGELOG.md`, this index and the README summary — and
missing any one of them left the repo contradicting itself.

Builds now identify themselves by commit: `build_id()` reports the short `GITHUB_SHA`, so a run
summary reads `### Game-Express 03c1668 — …` and points at the exact code that posted the card.
A dated entry and its index row are the whole ritual; no version number is bumped.

Releases up to and including `1.9.0` keep their numbers — that is what they shipped as, and
nothing is renumbered after the fact.

---

## Entries

| Entry | Date | Headline |
|---|---|---|
| [2026-10-27](CHANGELOG.md#2026-10-27--redlib-tier-1-fleet-expansion-24--27-and-inline-video--crosspost-media-parity) | 2026-10-27 | expand `DEFAULT_REDDIT` `24 → 27` (`r.naa.gg`, `redlib.thepixora.com`, `redlib.r4fo.com` in Tier 1; exclude `redlib.cow.rip`, nothing deleted) and extract rich-text inline `/link/<post>/video/<id>/player` + `media_metadata` media and Arctic Shift crosspost parents across `gamexpress/sources/reddit.py` |
| [2026-10-25](CHANGELOG.md#2026-10-25--ci-annotation-hygiene-zizmor-action-pin-alignment-and-beta-post-merge-edge-case-hardening) | 2026-10-25 | fix CI/advisory error annotations (`zizmor` `setup-python` `# v7.1.0` + exact `# vX.Y.Z` comments, `sync_prod.yml` Python bump coverage, `test_smoke.py` `::error::` stdout capture & command-leak guard while retaining `runs-on: ubuntu-latest` for automatic runner updates) and harden beta post-merge edge cases (CN/EN word-order-safe `%` comparison, transient Discord retry `last_poll`, pure slot-skill renames, Page-1 equipment packing, HSR Planar diff headings, and cross-epoch `ambiguous` peer-merge preservation) |
| [2026-10-25](CHANGELOG.md#2026-10-25--beta-prime-formatting-style-active-beta-gating-media-galleries-and-cnchs-cross-check) | 2026-10-25 | polish feature-5 beta cards across GI, HSR, ZZZ and WuWa: active-beta gating against live cycles, Prime Formatting Style (synthesized kit overview, metadata header, nested `* **[TAG]**` bullets, `[REWORK]` slot-rename/rewrite diffs, zero blockquotes/`*(cont.)*` headers, clean `-# <Game> <Ver> Beta • Page n/N` footer), markup/placeholder stripping, verified `static.nanoka.cc` art + multi-icon galleries, clean gachabase HTTP 403 fallback, `/zh/` CN cross-check, and one-time `BETA_FORMAT_EPOCH = 2` state reset |
| [2026-10-25](CHANGELOG.md#2026-10-25--enabled-beta-full-pipeline-harness-and-safe-multi-page-hand-off) | 2026-10-25 | replace the renderer-only interpretation of `benchmark --beta-enabled` with a deterministic, all-four-game actual `BETA_ENABLED=1` monitor harness; record semantic pipeline evidence separately from supplemental renderer timings; and apply a fixed, restart-safe five-second wait between successful beta pages only |
| [2026-10-25](CHANGELOG.md#2026-10-25--beta-revision-diff-hardening-full-kit-baselines-hotfix-safe-build-walking-exact-inline-values-and-quiet-revision-safety) | 2026-10-25 | harden feature-5 beta cards: retain readable full-kit baselines for honest `~~old~~ → **new**` diffs, conservative `[BUFF]` / `[NERF]` direction tags, ordered static-build walking, blank-hotfix fallback (including ZZZ `3.4.1 Rev. 19850203` Sunbringer source links), explicit quiet-build silent advance, resumable bounded batches, static art fallback locks, parameter-template cleanup across HSR / GI / WW, and WuWa singular-path manifest fallback delivery |
| [2026-10-24](CHANGELOG.md#2026-10-24--beta-kit--revision-diff-cards-feature-5-off-by-default-dedicated-per-game-channels-and-bounded-beta-polling) | 2026-10-24 | add beta kit & revision-diff cards as feature 5 (`BETA_ENABLED`, off by default): full new-character kits with real numbers, new weapons / W-Engines / light cones / disc drives / relic and echo sets, and `[CHANGED]` entries for older characters a revision touched; dedicated `DISCORD_WEBHOOK_BETA_<GAME>` routing with no catch-all, `PING_BETA*` ping isolation, bounded polling (`BETA_MIN_POLL_MINUTES`, `BETA_MAX_*`) over `nanoka.cc` + `gachabase.net`, image locking, revision idempotence and peer merge |
| [2026-10-24](CHANGELOG.md#2026-10-24--automated-development-to-production-repository-sync-sync_prodyml--sync_prodpy-redlib-fleet-expansion-22--24-nitter-reserve-seat-concurrency-pacing-redlib-v0400-video-rewrite-and-schedule-banner-cleanup) | 2026-10-24 | add automated dev → prod sync workflow & tree synchronizer (`.github/workflows/sync_prod.yml`, `.github/scripts/sync_prod.py` → `uesu/8mqzv4k2n7c`, protecting `state/state.json`, union-merging `config/program_announcements.json`, and retrying safely across concurrent 5-minute monitor commits); expand `DEFAULT_REDDIT` `22 → 24` (`redlib.reallyaweso.me` in Tier 1 dual-path + `redlib.ducks.party` `v0.40.0` in Tier 2 `REDDIT_LISTING_ONLY`/`REDDIT_SUB_LISTING_ONLY`; `redlib.vanillax.me` demoted to Tier 3, nothing deleted); pace Nitter batch reserve seats (`NITTER_RESERVE_PARALLEL = 2`); rewrite Redlib `v0.40.0` `/vid/<id>/<CMAF\|DASH\|HLS>/<res>.mp4` paths; strip inline `[[...]]` wiki links (`[[Furina]] & Valeriy` → `Furina & Valeriy`), heal persisted state, and remove `※ Re-runs:` from schedule cards |
| [2026-10-23](CHANGELOG.md#2026-10-23--official-news-quillhtml-inline-emphasis-self-labelled-url-multi-op-headinglist-and-asterisk-formatting-fixes) | 2026-10-23 | formatting-only official-news Markdown fixes (`gamexpress/textutil.py`, `gamexpress/preview_html.py`, zero source/API/JSON changes): preserve spaces & blank lines across color-split Quill bold spans (`47174982`), coalesce adjacent emphasis runs, unwrap bold/visible-URL links to clean bare URLs outside `**...**`, flatten `**[**label**](url)**` heading/adjacent links to `**[label](url)**`, accumulate multi-op Quill headings & bullet lists, split HTML emphasis across block/overlap boundaries, and escape literal CMS `*` notes across all configured games |
| [2026-10-23](CHANGELOG.md#2026-10-23--repository-wide-lf-line-ending-normalization-and-gitattributes-enforcement) | 2026-10-23 | enforce `* text=auto eol=lf` via `.gitattributes` and normalize all tracked text files to `LF` across `main` and production |
| [2026-10-23](CHANGELOG.md#2026-10-23--redlib-fleet-expansion-17--22-mitchrossredlib-v236-support-and-reddit-parsertrust-hardening) | 2026-10-23 | expand `DEFAULT_REDDIT` `17 → 22` (`redlib.mint.lgbt` `0.36.0` Shreddit + `reddit.idevicehacked.com` `0.40.0` leading Tier 1; `reddit.jeremyh.xyz`, `redlib.jeikobu.net`, `redlib.vanillax.me` in Tier 2 `REDDIT_LISTING_ONLY`; `redlib.privacyredirect.com` demoted to Tier 3 tail, nothing deleted); support `mitchross/redlib` `v2.3.6` HTML, reject disguised HTTP `200` Redlib/`502` error pages, filter `.onion` links, preserve cross-linked overview self-comments, and guard `Item.official` against public flair spoofing |
| [2026-10-23](CHANGELOG.md#2026-10-23--full-4-feature--6-game-audit-fixes-and-real-wuthering-waves-g153-launcher-media-support) | 2026-10-23 | real Wuthering Waves global (`G153`) launcher `.mp4` / `.webp` support (`aki-game.net` / `aki-game.com`); epithet (`"Luna II"`) & `"1.0"` launch inference, ISO-8601 override parsing, `seen_media` peer sync & shortlink Tier-2 → Tier-1 upgrades; `512`-char link-button & non-empty Action Row guards across all 4 features; pending code `gate` sync & transient-outage witness/reward retention; full 22-doc & changelog sync |
| [2026-10-22](CHANGELOG.md#2026-10-22--live-maintenance-crash-hotfix-stage-fault-isolation-and-end-to-end-anantahna-hardening) | 2026-10-22 | fix live `maintenance.resolve_version_plans` / `schedule.merge` `None` extract crash; add `try ... finally` stage persistence + per-game fault isolation without advancing heartbeat on error; self-heal malformed `State` & upstream JSON sub-slots; expand `MAINTENANCE_GAMES=all` to all 6 games incl. `ananta`, honor official Reddit maintenance timestamps (`PRIORITY["reddit"] = 38`), allowlist NetEase/`ANANTA` media CDNs, and distinguish `Official Reddit` vs community `Reddit` |
| [2026-10-22](CHANGELOG.md#2026-10-22--reddit--redlib-fleet-rotation-7-teapawt-tld-expansion--miefoundation-and-live-banneredge-case-hardening) | 2026-10-22 | 17-host Reddit/Redlib fleet + 3 rich-embed proxies + `REDDIT_FEED_TOKEN` (`.rss`/`.json` `www.reddit.com` → `old.reddit.com` fast path) across all 6 games; rotation #7 (`27` entries, `26` live across `.cf`/`.org`/`.net`/`.gq` `teapawt` siblings + `nitter.mie.foundation`); live banner, webhook/token redaction, HTML-entity config parsing, and documentation/credits polish |
| [2026-10-21](CHANGELOG.md#2026-10-21--optional-news-timestamps-pre-loadmaintenance-started-cards-and-expanded-full-articles) | 2026-10-21 | default-off render-time news `<t:…>` timestamps (`NEWS_TIMESTAMPS`), independent per-game `Pre-Load Started` & `Maintenance Started` Components V2 alerts (`MAINTENANCE_ENABLED` / `MAINTENANCE_GAMES`), expanded multi-page news articles (`NEWS_EXPAND_FULL`), ambiguous-POST hold protection, and reproducible `benchmark` CLI |
| [2026-10-20](CHANGELOG.md#2026-10-20--news-article-count-cap-removal) | 2026-10-20 | attempt all discovered eligible news in publication order; retire count/attempt caps and stale settings, preserve safety guards |
| [2026-10-20](CHANGELOG.md#2026-10-20--news-gif-mime-compatibility) | 2026-10-20 | signature-gated bare GIF MIME compatibility in shared news preflight/dimensions; original animated media preserved, safeguards unchanged |
| [2026-10-19](CHANGELOG.md#2026-10-19--wuwa-news-publication-time) | 2026-10-19 | dedicated WuWa news uses official publication start instead of draft creation; real Lucilla regression and protected baseline/future/dedup behavior |
| [2026-10-19](CHANGELOG.md#2026-10-19--news-video-cover-layout) | 2026-10-19 | omit redundant lead covers for full native-video news; retain explicit body media, link-only covers and excerpt leads |
| [2026-10-19](CHANGELOG.md#2026-10-19--news-cdn-preflight-compatibility-and-diagnostics) | 2026-10-19 | news media preflight accepts a well-formed offset-zero HTTP 206 prefix and `application/octet-stream` only alongside recognized media signatures, logs host/status/MIME/first-12-bytes rejections without signed queries, and pins the user-captured ZZZ 47133580 video/cover in a regression; host/redirect/status/signature protection and official refresh/hold behavior are unchanged, and the actual live CDN rejection cause plus Discord delivery remain unverified |
| [2026-10-19](CHANGELOG.md#2026-10-19) | 2026-10-19 | documentation follow-up: feature 3 in What it posts, detailed news instructions in docs, updated indexes and Legal & credits last; no runtime changes |
| [2026-10-18](CHANGELOG.md#2026-10-18--opt-in-official-news) | 2026-10-18 | opt-in official HoYoLAB & Kuro news delivery, source-order HTML/Quill blocks, bounded media preflight, measured strip grouping, silent baseline & bounded retention |
| [2026-10-18](CHANGELOG.md#2026-10-18--attended-workflow-updates) | 2026-10-18 | attended workflow & Python update merges, exact CPython `3.14.8` pins, and opt-in package-only Dependabot auto-merge |
| [2026-10-17](CHANGELOG.md#2026-10-17--application-only-scope) | 2026-10-17 | sanitized `write_summary` diagnostics and updated privacy/terms disclosures without new runtime files |
| [2026-10-15](CHANGELOG.md#2026-10-15) | 2026-10-15 | rotation #6: xcopy.uk trial verdict — 403 to the runners, 24/24 across 4 Azure regions (runs #2662–#2665), demoted beside kareem.one; operator-directed runner-proven hot path (nitter.cf, xitter.cf, meowing, miningtcup); freedit.eu (8/8 union handles) and gravitywell.xyz (5/8, complementary gaps) join the fallbacks — fleet 19 → 21, nothing deleted; housekeeping: every `tests/test_*.py` file is now a CI gate (23 regressions ran only under pytest before) with a guard test, two dead code paths removed (`passes_gate`, unused `WikiDialect` fields), and the stale words in AGENTS.md, TESTING.md, SECURITY.md, SOURCES.md, TIMESTAMP-PATTERNS.md, ruff.toml and `.env.example` corrected |
| [2026-10-14](CHANGELOG.md#2026-10-14) | 2026-10-14 | rotation #5: xcopy.uk — 8/8 monitored handles body-verified with nitter.cf parity, on the shitter fork's working list — trials nitter slot 2; meowing.monster (dark ~8 h, revived 5/6 from the runners, IPv6-slow) takes the head of the fallbacks, demoted not deleted, no ledger move |
| [2026-10-13](CHANGELOG.md#2026-10-13) | 2026-10-13 | a display-only card edit (`banners_display`) finally names itself in the run summary, and `shitter.thepixora.com` is demoted out of the nitter every-run batch after its runner verdict (HTTP 403 on all six handles), with `tw.eir-nya.gay` promoted into the vacated slot; the README's Changelog section becomes a pointer to the full changelog (the ritual is two parts now: the entry and its index row) and the never-working Configuration Contents anchor is fixed (⚙️ + U+FE0F → 🔧); rotation #4 ends eir-nya's one-run slot-4 trial (HTTP 200 with 0 entries on all six handles, run #2323) — xitter.cf, which answered from the runners before its 2026-10-03 redundancy demotion, warms slot 4 while eir-nya waits in the fallbacks |
| [2026-10-10](CHANGELOG.md#2026-10-10) | 2026-10-10 | the card's own style: `EMOJI_TITLE` puts the server's `<:ananta1:…>` on every headline (and `parse_emoji` stops misreading names that start with "a"), full display names render on every banner line while the stored data keeps each source's form, the WuWa 4★ summary auto-hides once both phases are filled, the edit line names the banner keys that moved and who wrote them, locks are announced with their witnesses, and the WuWa banner-search warning stops firing on a merely empty menu |
| [2026-10-09](CHANGELOG.md#2026-10-09) | 2026-10-09 | the banner reader learns the ZZZ X dialect (`CHANNEL_MODE`: a quoted channel title is never a character; the live 3.3 card heals itself and the official calendar fills A-rank Phase I) |
| [2026-10-09](CHANGELOG.md#2026-10-09-1) | 2026-10-09 | banner names lock on any two reputable sources (hub, official calendar, wiki) with a three-hour wiki budget for TBA blocks, a posted Special Program card keeps its announcement (link, key art, air time) and prefers the X post, single tweets read nitter.cf first, a deleted copy says it was deleted, and a retirement names the message it retired |
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
3. Grep the docs for any count, cadence or flag the change affects
   (`README.md`, `AGENTS.md`, `docs/*.md`) — see
   [AGENTS.md § Conventions](../../AGENTS.md#8-conventions).

Entries are written for a reader who was not there: say what changed, and say *why* — the
incident, the measurement or the broken run that caused it.
