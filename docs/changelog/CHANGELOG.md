# Changelog — current entries

## 2026-10-29 — Timing phrases, reveal dedup and edit safety

- Read the HoYoverse reminder form `The game will be updated and maintained at <date> (UTC+8)`
  (`maintained`, no "maintenance" noun) and windows whose end is only a clock
  (`begins at 06:00 (UTC+8) and ends at 11:00 (UTC+8)`, including the midnight case). End-only
  sentences about events or compensation still never become a maintenance start.
- Resolve a clock-only extension (`extended to 14:00 (UTC+8)`) on the notice's own day, and adopt
  the replacement date of a reschedule that quotes the abandoned window. `will not be postponed`
  is not a postponement.
- Collapse a token-prefix full-name variant of the *same* reveal inside a 12-hour window
  (`Agent Record | Evelyn` then `Agent Record | Evelyn Chevalier`) so one Agent pings once;
  different characters that merely share a word still ping.
- Hold a backstage CMS edit instead of publishing a truncated card when re-attaching a retained
  reveal mention now needs a continuation page or no longer fits.
- Accept trailing-slash and `/watch/` YouTube player URLs when rendering the visible watch link.

## 2026-10-29 — Follow-up regression guards

- Exclude non-official and Miliastra-authored reveal candidates, recognize quoted Star Rail series without a pipe, and exclude YouTube privacy-enhanced embedded videos. Tests are requirement-derived reconstructions, not historical accuracy evidence.
- Add explicit-timing milestone boundary and persisted-restart tests across all six configured games. Make workflow summary-output failure best effort without hiding persistence failures.

## 2026-10-29 — Optional character reveal mentions

- Add default-off, dedicated role mentions for recognized official-news character reveals; exclude recognized video and other non-reveals, deduplicate retained characters and the same publication minute, and preserve pings in different minutes. Detection is heuristic, not guaranteed for unknown formats or incomplete historic rosters. See configuration for limits and ambiguous-delivery handling.

## 2026-10-29 — News YouTube watch links

- Render verified YouTube player, watch, shorts, live and short-link media as a visible canonical YouTube watch URL in the existing article position. Preserve numeric start offsets; leave non-YouTube media fallback links and playable native videos unchanged. No unrelated YouTube video is inferred when the original source does not provide one.
- Add offline coverage for the HSR player URL, all configured games, both timestamp and expanded-page settings, source immutability, untrusted hosts and non-YouTube/native media.

## 2026-10-29 — Maintenance timing safeguards and actionable persistence summary

- Parse labelled maintenance ranges before single timestamps, including explicit end dates and supported cross-day / dual-offset ranges. Reject invalid offset minutes.
- Recognize supported extension and TBA postponement notices; retain official timing evidence across maintenance-only runs and route-compatible peer merges. Suppress cadence estimates while a recognized postponement is active, and allow newer authoritative reschedules. A delay with no recognized notice cannot be inferred automatically.
- Permit bounded silent timing corrections through the active window independently of the six-hour media-upgrade window and its retry budget. Preserve Kuro `bg_hash` as a corroborating signed-URL renewal binder.
- Report the workflow's observed state-persistence result in the run summary; include regression tests for persistence and failure paths. The Twitter video-size change remains separate from this repository.

## 2026-10-27 — Redlib Tier-1 fleet expansion (24 → 27) and inline-video / crosspost media parity

- Expand `DEFAULT_REDDIT` from `24` to `27` entries (`0` deletions) by adding three verified working clearnet Redlib instances to Tier 1: `https://r.naa.gg` (`Nachtalb/redlib` GraphQL engine), `https://redlib.thepixora.com` (`PR #603` GraphQL comments patch), and `https://redlib.r4fo.com`, while explicitly excluding `https://redlib.cow.rip` (Cloudflare + custom verification wall).
- Harden `gamexpress/sources/reddit.py` (`redlib_media_to_reddit`, `parse_redlib_html`, `parse_reddit_rss`, `parse_reddit_json`, and `resolve_post`) to extract rich-text inline `/link/<post>/video/<id>/player` and `media_metadata` `RedditVideo` / `Image` / `AnimatedImage` media and unwrap `crosspost_parent_list` / `crosspost_parent` records on Arctic Shift fallbacks.

## 2026-10-25 — CI annotation hygiene, zizmor action pin alignment, and beta post-merge edge-case hardening

- Fix CI & sync-gate error annotations across `uesu/Game-Express` and `uesu/8mqzv4k2n7c` while keeping `runs-on: ubuntu-latest` for automatic runner OS updates: update `actions/setup-python` to `6d4fd22b20465ccc0f7354476588e8df7c9ca0e0` (`# v7.1.0`), pin exact `# vX.Y.Z` tag comments on all workflow actions so `zizmor` exits `0` instead of `13`, include `sync_prod.yml` in `python_version_bump.py`, and capture simulated `::error::` workflow commands in `tests/test_smoke.py` with a runner-wide command-leak guard.
- Harden feature-5 (`beta`) post-merge edge cases without touching features 1–4 runtime code: compare CN/CHS vs EN prose percentages as order-independent multisets so clause word order and English ordinals (`1st-Hit` vs `第一段`) never emit false lag notes, preserve immediate retry (`last_poll` unstamped) on transient Discord HTTP failures (`will retry`) and clear stale `paused` markers on resume, surface pure slot-skill renames in `diff_kits`, pack long equipment-only items onto Page 1 alongside the patch header, split HSR `Planar Ornaments Changes` vs `Relics & Ornaments` headings independently, and preserve `ambiguous` circuit-breaker holds across `BETA_FORMAT_EPOCH` peer merges in both directions.

## 2026-10-25 — Beta Prime Formatting Style, active-beta gating, media galleries, and CN/CHS cross-check

- Gate beta discovery against each game's live version cycle (manifest `live`/`hotfix`, version config, and confirmed past maintenance schedules) so finished or already-live betas (e.g. GI `7.1.53` on live `7.1`, HSR `4.6.54` on live `4.6`) skip immediately with zero changelog or detail requests while active betas (e.g. ZZZ `3.4.1`, WuWa `3.8.1`) publish normally. Handle gachabase HTTP 403 / access-denied blocks cleanly without warning spam.
- Upgrade beta Discord Components V2 rendering to Prime Formatting Style across GI, HSR, ZZZ, and WuWa: full game-name patch headers, structured character/equipment metadata headers, synthesized **Kit Overview** summaries, nested `* **[TAG]**` skill bullets with `[REWORK]` slot-rename/rewrite detection, deduplicated inline `**(Keyword)**` definitions, zero `>` blockquotes, zero `*(cont.)*` continuation headers, and clean `-# <Game Name> <Version> Beta • Page n/N` footers.
- Strip client markup and unresolved formula placeholders across all namespaces (`<IconMap:...>`, `<size=...>`, `<SapTag=...>`, `<te href=...>`, console/fallback layout tags, `{0}`/`#{...}`/`{CAL:...}`), resolve verified `static.nanoka.cc` character/weapon/LC/W-Engine art plus multi-item galleries (6-icon HSR Eidolons, Planar Ornaments, Relics, Artifacts, Drive Discs) with persisted gallery locks, cross-check `/zh/` when EN lags behind CN/CHS, and bump `BETA_FORMAT_EPOCH = 2` for a one-time state reset across protected production records and peer merges. Features 1–4 remain untouched.

## 2026-10-25 — Encore secondary beta API backup

- Extend the existing current-build WuWa character/weapon fallback with Encore's documented legacy `https://api.encore.moe/en` server after an unusable primary response. Both endpoints' current beta metadata and normalized Lily/Lullaby output were compared directly.
- Keep each server's metadata/detail/metadata reads together, exact version/ID and batch checks, and three-call reservation per server inside existing local/shared budgets (at most six Encore calls per item). Healthy nanoka adds no Encore traffic; successful primary Encore adds no backup traffic. Retain prior delivery, snapshots, images, feature isolation, settings and dependencies.
- Add two offline regressions for recovery parity, invalid/unavailable/changing responses, request bounds and durable settlement. Assess additional asset references without wiring unrelated placeholder artwork or unverified release data into beta cards.

## 2026-10-25 — Gachabase HTML revision discovery

- Fix a live response-format mismatch: gachabase returns server-rendered HTML to the monitor, while the original parser accepted only Markdown. Read both formats so changed existing IDs are discovered instead of silently falling back to manifest-new IDs.
- Preserve revision order, dates, categories, same-item diff links and explicit quiet markers; ignore scripts/styles, navigation and foreign links. Warn on unreadable changelogs. No extra HTTP calls, dependencies, settings or changes to features 1–4.
- Add a reduced public-layout fixture and offline regression; recheck live GI/HSR/ZZZ changelogs and nanoka/Encore rendering without Discord writes.

## 2026-10-25 — Future Encore build transition coverage

- Verify a synthetic 4.0 resource-version transition, stale fallback hold, matching retry, valid cards and durable quiet settlement. Clarify that released characters remaining in the Encore beta catalog are not automatically new beta characters. No runtime, configuration or benchmark behavior changed.

## 2026-10-25 — Content-driven beta pages without display truncation

- Support beta batches with five, ten or more pages according to readable content. Split long equipment effects instead of truncating them, render every parameter row and preserve all changed/removed skill, stat and equipment lines. Remove the prior compact-diff display caps; source request/item budgets and bounded snapshot retention remain unchanged.
- Split oversized whitespace-free text with guaranteed progress, including long character introductions/stat blocks. Continue equipment with labelled headings, retain source links and show each equipment image once. Every page independently validates; pings remain first-page-only.
- Add offline regressions for 5/12/21-page delivery, failure/restart after ten confirmed pages, durable page IDs, final-only settlement, complete output across all four games and bounded lossless token splitting. Changed partial payload signatures still require reconciliation; no saved IDs are cleared.

## 2026-10-25 — Encore beta API fallback for WuWa

- Correct the earlier research-only assessment: Encore’s frontend/API support explicit `?v=Beta`, omitted from the supplied OpenAPI export. Confirm Hsin and Suoming details plus current beta metadata and capture relevant public API fields for offline tests.
- Use Encore only for missing/unreadable current nanoka WuWa character/weapon details, with exact resource-version matching, stable metadata before/after, item-ID validation and existing local/shared request bounds. Link fallback items to Encore beta pages, retain provider/build metadata, and suppress cross-provider inline direction. Historical discovery remains nanoka-driven; no new settings or dependencies.
- Render published Lv.10 skill values, six chain nodes, stat bonuses, explicit Lv.90 properties and labelled weapon refinement values. Retain unavailable-value labels and existing image validation/locking. Document active-source credits and the observed API contract and limits. Earlier dated research conclusions below are historical and superseded by this live verification.

## 2026-10-25 — Truthful bounded beta comparisons and source credits

- Add a full-content digest alongside bounded readable snapshots. Unchanged long descriptions no longer produce false cards; changes beyond the stored text limit produce a labelled full current snapshot. Legacy records without a full digest rebaseline once without invented before/after values.
- Preserve removed stat/equipment lines when a replacement block has fewer new lines. Add failing-before-fix regressions, including persisted state and payload validation.
- Restructure credits around active sources, tools and research references; document the confirmed Game/News development and production repository map. Encore remains a research reference because its supplied API contract lacks beta revision history.

## 2026-10-25 — Live beta equipment schemas and restart-safe batches

- Capture current public Light Cone, relic, Genshin weapon and WuWa weapon fields in offline regressions. Handle HSR list-based promotion stats, substitute equipment parameters, normalize source formatting tags and nested localized equipment names, and display WuWa percentage units correctly. Label missing source parameters instead of inventing values.
- Preserve an unfinished beta source build across manifest advances. Persist a payload signature with page progress; hold changed or legacy unsigned partial payloads and conflicting peer signatures for operator reconciliation. A changed candidate batch or newly quiet source cannot silently bypass a partial delivery.
- Existing default-off routing, five-second page pacing, image preflight, and schedule/codes/news/maintenance behavior remain covered by the repository suites. Live source reads are separate from offline fixture evidence; no Discord posting is part of these checks.

## 2026-10-25 — Enabled-beta full-pipeline harness and safe multi-page hand-off

- **Full enabled-feature harness (`gamexpress/beta_harness.py`, `gamexpress/__main__.py`, `tests/test_smoke.py`):** replace the earlier renderer-only interpretation of `python -m gamexpress benchmark --beta-enabled` with a deterministic **actual `BETA_ENABLED=1` monitor pass**. It covers all released beta games (GI, HSR, ZZZ and WuWa) through manifest/changelog or manifest fallback discovery, each namespace parser, character + weapon + relic/echo baselines, image preflight, Components V2 validation, webhook delivery, state settlement, retained revisions, deduplication and an explicit quiet revision. The JSON report separates this semantic evidence in `beta_enabled_fixture.pipeline` from the eight supplemental renderer microbenchmark rows in `render_microbenchmarks`.
- **No production mutation hidden in the test:** the harness has in-memory fetcher/webhook/state collaborators and exposes their fixture-call and state-save counts. It asserts **zero live** source requests, Discord posts and physical state writes while still testing state-save boundaries; it never mutates process environment or production feature settings.
- **Five-second multi-page beta pacing (`gamexpress/beta.py`, `gamexpress/runner.py`):** after every successful beta page, production now waits exactly **5 seconds** before the next unsent page. It persists the successful message id before that wait, adds no trailing delay after the final page, and never adds a resume-boundary delay before a page that was already pending from a previous run. `Ctx.sleep` is an optional injected async collaborator, so offline tests record intended delays rather than waiting in real time. Targeted coverage proves happy-path placement/count, failed and ambiguous first-page no-delay holds, and resumed-page behavior.
- **Ambiguity and identity edge hardening (`gamexpress/beta.py`, `gamexpress/beta_harness.py`, `tests/test_smoke.py`):** an indeterminate Discord beta POST is now a persisted circuit breaker across later scheduler invocations, not merely an in-run warning: it cannot resend page one until an operator reconciles that batch. Candidate and snapshot state now preserve item role as part of a key only when needed, so an upstream character, weapon, and relic sharing one numeric id cannot alias an art lock, baseline, or bounded probe. The full enabled harness and targeted regressions prove both cases.
- **Source review boundary:** the supplied Encore v2 OpenAPI reference remains documented but is not added as a beta poll source because its current-resource contract still lacks a documented beta/history cursor. The structured nanoka manifest remains the safe revision authority, including explicit numeric WuWa singular-path fallbacks. The broader Reddit/Twitter material was audited separately; it does not justify changing Game-Express beta source priority or touching private monitor repositories from this branch.

## 2026-10-25 — Beta revision-diff hardening: full-kit baselines, hotfix-safe build walking, exact inline values, and quiet-revision safety

- **Real retained-kit diffs (`gamexpress/beta.py`, `gamexpress/models.py`, `gamexpress/cards.py`, `gamexpress/state.py`):** save a bounded readable-kit snapshot only after a successful card batch, then compare the next static build block-by-block. Changed output now keeps source wording around inline value diffs such as `~~**200%**~~ → **240%**`, carries full-kit and revision-diff links, reports additions/removals/renames/reclassification safely, and emits `[BUFF]` / `[NERF]` only where the before/after value and an unambiguous mechanic rule establish direction. Everything ambiguous remains `[CHANGED]`; text-only edits remain `[TEXT FIX]`; cold starts are full snapshots rather than fabricated diffs.
- **ZZZ 3.4.1 hotfix resilience:** walk `manifest.available` builds in order rather than jumping from a known revision to `latest`. A blank `v3.4.1 Rev. 19850203` changelog heading rechecks only manifest-new and previously snapshotted IDs, so a Sunbringer hotfix still yields a source-linked revision card without a scan of every agent. A generated fallback link uses the same documented `prev=beta_3.4.1_19842923&cur=beta_3.4.1_19850203` shape when a blank heading supplies no entry URL.
- **Quiet and bounded state semantics:** an explicit upstream `No tracked changes detected` build advances silently with no empty Discord post or detail/media GETs; a cold opt-in still posts the currently-new beta reveal once. Bounded batches retain per-batch message IDs plus processed-item keys, resume the next item batch without duplicate pages, and only advance the source-build cursor once every deferred item has settled. Media fallback candidates are preflighted and then image-locked exactly once.
- **Full-text/value parser cleanup:** HSR `#N[i]` templates now substitute the published skill parameters (and clearly flag a genuinely unpublished parameter), GI `F…P` formats render as percentages instead of raw ratios, WW `{0}` chain placeholders resolve from their supplied values, ZZZ stat tables are attached to their matching skill, and mechanic definitions sit directly under the skill that invokes them.
- **Offline verification:** add six targeted regression tests to the existing beta suite (now **30** feature-5 test functions): blank-hotfix revision walking with a truthful inline value diff and generated source link; explicit quiet revision with zero kit/media reads; HSR parameter substitution plus structured numeric diff markup; a hard request-budget check that reserves both detail and media preflight calls; a multi-game assertion that `BETA_MAX_REQUESTS` is one feature-wide ceiling rather than a per-game multiplier; and a dry-run full delivery/settlement pass across GI / HSR / ZZZ / WuWa. All fixtures remain offline.
- **WuWa manifest-fallback delivery (`gamexpress/beta.py`):** preserve each internally generated manifest candidate's explicit numeric id before parsing source URLs. This closes the singular `ww.nanoka.cc/character/<id>/` / `weapon/<id>/` URL edge case that the gachabase-style plural URL extractor could otherwise drop silently; new WuWa characters, weapons and echoes now take the same bounded fallback/detail/delivery path as GI / HSR / ZZZ.
- **Enabled-feature benchmark coverage (`gamexpress/__main__.py`, `tests/test_smoke.py`, docs):** `python -m gamexpress benchmark --beta-enabled` now creates a separate in-memory `BETA_ENABLED=1` / `BETA_GAMES=genshin,starrail,zzz,wuwa` setting, renders and validates new-kit plus retained-baseline revision cards for **GI, HSR, ZZZ and WuWa** (8 timed cases / 16 current payloads, including one gallery per character/item), and records zero source HTTP, Discord webhook and state-write activity. The standard 12-case default-off news/parity benchmark is unchanged. The supplied Encore API v2 reference was assessed but is intentionally not polled: its published current-resource schema lacks a documented beta/revision history contract, so nanoka remains the safe manifest-driven WuWa source.

## 2026-10-24 — Beta kit & revision-diff cards (feature 5, off by default), dedicated per-game channels, and bounded beta polling

- **Beta kit & revision-diff cards — feature 5 (`gamexpress/beta.py`, `gamexpress/cards.py`, `gamexpress/models.py`, `gamexpress/config.py`, `gamexpress/state.py`, `gamexpress/runner.py`, `gamexpress/__main__.py`, `config/games.json`):** an independent, **off-by-default** feature that publishes a game's beta revision to that game's own channel as Discord Components V2 cards. One batch per new revision contains (1) a full kit overview for every character that is **new** in the beta version — every skill with its numbers, the mindscape / constellation / resonance chain, and the mechanic glossary the kit references; (2) the new weapons, W-Engines, light cones, disc drives, relic sets and echo sets, each as its own block; and (3) the older characters a revision touched, tagged `[CHANGED]` with a link to the before/after diff. Long kits split automatically into sequential containers labelled `Page n/N`, each independently inside Discord's 4,000-character and 40-component limits, and only the first page ever carries a role mention.
- **Opt-in, per-game, and scoped to games that have shipped:** `BETA_ENABLED=1` is required, `BETA_GAMES` defaults to the four released games (`genshin`, `starrail`, `zzz`, `wuwa`) and `all` resolves to the same four — **Honkai: Nexus Anima and ANANTA are excluded until they launch**. Routing is dedicated (`DISCORD_WEBHOOK_BETA_<GAME>` > `DISCORD_WEBHOOK_BETA` > `DISCORD_WEBHOOK_NEWS_<GAME>`) with no catch-all, mirror or `FORCE_WEBHOOK` fallback, so enabling it can never leak a beta card into a schedule or codes channel. `PING_BETA_<GAME>` > `PING_BETA` is the only source of its ping; `PING_ROLE_ID` is deliberately not inherited.
- **Bounded and polite by construction:** discovery is one small `https://static.nanoka.cc/manifest.json` GET (naming each game's newest revision and the ids new in it) plus that game's beta changelog (`https://<game>.gachabase.net/changelog/beta?lang=en` for GI/HSR/ZZZ; Wuthering Waves has no gachabase site and is driven by the manifest's `new` lists alone), then at most one detail JSON per new entry from `https://static.nanoka.cc/<game>/<revision>/en/<kind>/<id>.json`. `BETA_MIN_POLL_MINUTES` (default `30`) gates re-checks, and `BETA_MAX_CHARACTERS` / `BETA_MAX_CHANGES` / `BETA_MAX_EQUIPMENT` / `BETA_MAX_REQUESTS` (defaults `4` / `8` / `12` / `48`) clamp every run; every value is clamped to a safe range so a typo can never mean "unbounded". Disabled, the feature makes zero requests and writes nothing to `state/state.json`.
- **Initial no-invention guard:** every value is read straight from the database export. A first-seen or otherwise baseline-less changed entry is `[CHANGED]`, never a guessed `[BUFF]` or `[NERF]`; the 2026-10-25 follow-up adds conservative directional tags only after retaining both structured snapshots. Unlocalised backend keys (`TestKey_PlaceHolder`, `Robin_Skill_Normal_Title`, `EquipmentSuit_34300_name`) and the databases' own `missing.webp` placeholder are recognised and dropped, so an unfinished localisation or an unnamed item omits its gallery cleanly instead of posting internal identifiers or a broken image.
- **Image lock — a finished card stops generating traffic:** a splash-art URL resolved for an entry is stored in `state["beta"][game]["locked_images"]` and reused; a locked image is never re-fetched or re-verified.
- **Idempotent, resumable and fail-over aware:** one card set per `(game, revision)`; a later run that sees the same revision posts nothing. A partial delivery resumes from the stored message ids instead of re-posting, an ambiguous Discord outcome is held rather than retried, and `state["beta"]` merges across peers through `State.merge_peer(..., include_beta=True)` so a standby never double-posts. `State.prune_beta()` bounds the new state block (16 revisions, 80 snapshots, 80 locked images per game).
- **Offline test coverage (`tests/test_smoke.py`, `tests/fixtures/beta/`):** 28 new assertions covering default-off behaviour and the opt-in matrix, HNA/ANANTA exclusion, dedicated routing with no catch-all, ping isolation, changelog and manifest parsing, per-game kit builders (ZZZ Lv. 60 stats cross-checked against the database's own rendered block — `HP 8754 / ATK 750 / DEF 706`; HSR Lv. 80 `base + add × 79`; Wuthering Waves Lv. 90; Genshin Impact talents, passives and constellations), equipment rendering, automatic paging and validation, first-page-only pings, budget clamping, revision idempotence, image locking, peer merge, pruning, end-to-end runs with and without a webhook, `validate` diagnostics, and preview-only sample cards. Nothing in the feature is tested against the live network.

## 2026-10-24 — Automated development-to-production repository sync (`sync_prod.yml` + `sync_prod.py`), Redlib fleet expansion (22 → 24), Nitter reserve-seat concurrency pacing, Redlib v0.40.0 video rewrite, and schedule banner cleanup

- **Automated dev → prod repository sync (`.github/workflows/sync_prod.yml`, `.github/scripts/sync_prod.py`, `docs/PROD-REPO-SETUP.md`):** add a gated GitHub Actions workflow (`on: push: branches: [main]` + `workflow_dispatch` with `dry_run`, `skip_ci`, and `target_repos` inputs) and deterministic tree synchronizer that validates the full offline test suite (`compileall`, `gamexpress validate`, `tests/test_smoke.py`, `tests/test_schedule_epithet_and_settled.py`, `tests/test_gachawiki_placeholder.py`, `gamexpress preview`) before atomically syncing the runtime subset (`gamexpress/`, `tests/`, `.github/scripts/`, `config/games.json`, `config/overrides.json`, `.github/workflows/{ci,monitor,python_version_bump}.yml`, `.github/dependabot.yml`, `.github/zizmor.yml`, `.gitignore`, `requirements.txt`, `ruff.toml`, `state/.gitkeep`) to `uesu/8mqzv4k2n7c`. Strictly protects `state/state.json` and `placeholder/`, union-merges `config/program_announcements.json` so live-discovered tweet IDs in production survive alongside new dev entries, excludes dev-only documentation and `sync_prod.yml` itself from production, retries with `git fetch` + `reset --hard FETCH_HEAD` if a 5-minute monitor commit lands concurrently, and falls back to non-workflow file sync with a clear warning if the token (`secrets.PROD_SYNC_PAT || secrets.BUMP_PAT`) lacks `workflow` scope.
- **Redlib fleet expansion & re-ranking (`gamexpress/config.py`, `gamexpress/sources/reddit.py` — `22` → `24` entries, nothing deleted):** add `https://redlib.reallyaweso.me` to Tier 1 (`[2]`, live-verified `200 OK` across `/r/<sub>/new`, `/user/<acct>`, and `/r/<sub>/comments/<id>/` with full multi-image galleries and comments) and `https://redlib.ducks.party` (`v0.40.0`, `200 OK` `/r/<sub>/new` listing with inline gallery carousels) to Tier 2 (`REDDIT_LISTING_ONLY` + `REDDIT_SUB_LISTING_ONLY` so `/comments/` and `/user/` skip it with `0` wasted requests), and demote `https://redlib.vanillax.me` to Tier 3 after live HTTP `200` `"The backend server is having issues"` error responses, keeping Reddit strictly behind Official APIs and X/Nitter.
- **Nitter reserve-seat concurrency pacing (`gamexpress/sources/twitter.py`):** bound simultaneous in-flight requests to batch reserve seats (`idx >= needed`, such as slot 3 `nitter.meowing.monster` when `needed == 2`) across concurrent game tasks via `NITTER_RESERVE_PARALLEL = 2` (`self._reserve_sem`). When all 6 games run in parallel, `nitter.cf` and `xitter.cf` execute at full 6-way speed (`~540 ms`) while at most 2 games probe `nitter.meowing.monster` concurrently — preventing the 6-request simultaneous burst that triggered `HTTP 429` on `/HonkaiNA/rss` and `/Ananta_EN/rss` and cancelling the remaining queued reserve tasks as soon as the primary quorum answers, while pacing all 6 games cleanly (2 at a time) if a primary seat fails.
- **Redlib `v0.40.0` `/vid/<id>/<CMAF|DASH|HLS>/<res>.mp4` URL rewrite fix (`gamexpress/sources/reddit.py`):** normalize `/vid/<id>/CMAF/1080.mp4`, `/vid/<id>/DASH/720.mp4`, and `/vid/<id>/HLS/720.mp4` (`redlib.mint.lgbt`, `reddit.idevicehacked.com`, `redlib.ducks.party`, `redlib.reallyaweso.me`) to `https://v.redd.it/<id>/<CMAF|DASH|HLS>_<res>.mp4` in `redlib_media_to_reddit()` and extend `UNMUXED_REDDIT_VIDEO_RE` to include `HLS_` so un-muxed Redlib video streams are recognized and upgraded to audio-muxed `vxreddit` / `embedez` streams.
- **Schedule banner `[[...]]` wiki-link cleanup, state healing, and `※ Re-runs:` removal (`gamexpress/sources/gachawiki.py`, `gamexpress/schedule.py`, `gamexpress/cards.py`):** replace `_LINK.fullmatch(value)` in `gachawiki.clean_name()` with inline `_LINK.sub(...)` + HTML entity unescaping + stray `[[`/`]]` stripping so compound wiki annotations such as Genshin Impact `7.2`'s `([[Furina]] & Valeriy)` render cleanly as `Furina & Valeriy`; heal any previously persisted `[[...]]` banner names in `schedule.merge()` and `cards.names()` on the next run even when `wiki_recheck_due()` is throttled or phases are settled; and remove the `※ Re-runs:` line from `cards.banners_block()` across all games while keeping `reruns` in `data["banners"]` so upstream sources, JSON schemas, and sibling debut/rerun ordering remain untouched.

## 2026-10-23 — Official news Quill/HTML inline emphasis, self-labelled URL, multi-op heading/list, and asterisk formatting fixes

- **Quill & HTML inline emphasis, link, list, heading, and literal-asterisk rendering (`gamexpress/textutil.py`, `gamexpress/preview_html.py` — formatting-only; upstream HTML/JSON/APIs/sources untouched):** fix all inline Markdown serialization bugs exposed live on HoYoLAB Genshin Impact article `47174982` (`Monitor #39937163763`) and harden future posts across all configured games (`genshin`, `starrail`, `zzz`, `hna`, `wuwa`, `ananta`): (1) preserve leading/trailing horizontal spaces and blank lines (`\n\n`) per line inside Quill inline runs instead of calling `.strip()` across color-split bold spans (`**Airs on 10/23/2026 at 8:00 AM (UTC-4) >>>**`, `**Take part in the event and get a chance to win Intertwined Fate ×10!**`, `**Event Duration: 10/23/2026 – 10/27/2026 23:59 (UTC+8)**`, `**Results: 10/30/2026**`) and coalesce adjacent `**...**` spans across both Quill and HTML; (2) unwrap bold/emphasis-wrapped self-labelled or visible-URL anchors (`<a><strong>https://…</strong></a>` and Quill `{"link": url, "bold": true}`) into clean bare URLs while closing any surrounding open `**...**` span (`**Twitch:** https://hoyo.link/QnTT3DRQa`), avoiding Discord's anti-phishing masked-link rejection (`[**https://…**](https://…)`); (3) flatten nested bold heading and adjacent bold links into single outer bold spans (`**[>>> Click Here to Participate <<<](https://x.com/…)**`) instead of `**[**…**](url)**`; (4) accumulate consecutive Quill string ops on the active text block so multi-op Quill headings bold the entire heading line and multi-op Quill lists place `- ` at the true line start; (5) lift leading whitespace before opening inline emphasis in `_NewsHTML.handle_data()`, split emphasis cleanly across `<p>`/`<div>`/`<br>` block boundaries and overlapping HTML tags (`<em>`/`<i>`, `<s>`/`<del>`, `<hr>`), and escape literal CMS `*` footnotes/multipliers (`\*`) outside URLs across both Discord payloads and `preview_html.py`. All existing fixture and `benchmark` SHA-256 baseline digests remain bit-identical (`main_baseline_sha256_equal = True`).

## 2026-10-23 — Repository-wide `LF` line-ending normalization and `.gitattributes` enforcement

- **Line-ending parity & `.gitattributes` guard (`* text=auto eol=lf`):** normalize tracked text files to `LF` (`109 / 109` files across `main` and production) so cross-platform checkouts never reintroduce mixed `CRLF`/`LF` diffs.

## 2026-10-23 — Redlib fleet expansion (17 → 22), mitchross/redlib v2.3.6 support, and Reddit parser/trust hardening

- **Redlib fleet expansion & live re-ranking (`gamexpress/config.py`, `gamexpress/sources/reddit.py` — `17` → `22` entries, nothing deleted):** add 5 newly verified live public Redlib instances (`https://redlib.mint.lgbt` on `0.36.0` `0baefabf` Shreddit scraper and `https://reddit.idevicehacked.com` on `0.40.0` `848f3013` leading Tier 1 with `200 OK` across `/r/<sub>/new`, `/user/<acct>`, and `/r/<sub>/comments/<id>/`; `https://reddit.jeremyh.xyz`, `https://redlib.jeikobu.net`, and `https://redlib.vanillax.me` in Tier 2 `REDDIT_LISTING_ONLY`) and demote `https://redlib.privacyredirect.com` to Tier 3 tail after live `403` error responses on `/new` and `/comments/`, keeping all existing hosts intact and keeping Reddit strictly behind Official APIs and X/Nitter.
- **Custom fork HTML support, HTTP `200` error-page rejection, `.onion` filtering, overview self-comment preservation, and flair-spoof protection (`gamexpress/sources/reddit.py`):** (1) extend `parse_redlib_html()` to parse `mitchross/redlib` `v2.3.6` (`redlib.vanillax.me`) standalone `<a class="post_title">`, header-level `<a class="post_flair">`, and `<div class="post_media_preview">` thumbnails while ignoring empty shell blocks; (2) harden `is_challenge_or_error_page()` and `_fetch_listing_on()` against Redlib `error.html` (`<div id="error"`, `<title>Error:`), split-heading `502`/`503`/`504` gateway error pages, clearnet shutdown pages, and non-feed/non-listing HTML bodies so disguised HTTP `200` error pages return `None` instead of consuming `REDDIT_WORKING` quorum slots or short-circuiting the `REDDIT_FEED_TOKEN` chain; (3) strip Redlib `v0.40.0` `.onion` rewrites from extracted `links` and preserve multi-link official overview self-comments when cross-linking earlier threads; and (4) restrict `Item.official` on subreddit fallbacks via `is_verified_reddit_author()` so public user-selectable `"Official News"` / `"Official Media"` flairs cannot spoof single-source `reddit_official` redemption codes on `codeposter.py` while keeping verified publisher/moderator accounts and `schedule` / `program_post` behavior intact. Synchronize `README.md`, `.env.example`, `docs/SOURCES.md`, `docs/SECURITY.md`, `docs/ACCURACY.md`, `docs/CREDITS.md`, and changelog indexes.

## 2026-10-23 — Full 4-feature & 6-game audit fixes and real Wuthering Waves `G153` launcher media support

- **Wuthering Waves (`G153`) global launcher background video & wallpaper support (`gamexpress/sources/kuro.py`, `gamexpress/http.py`, `gamexpress/maintenance.py`):** add `parse_launcher_background()` and lazy `launcher_media()` for Kuro's real global launcher config (`launcher/launcher/50004_…/G153/index.json` → `functionCode.background` → `background/{bg_hash}/en.json`), allowlist Kuro's official `aki-game.net` and `aki-game.com` media CDNs in `_news_media_prefix()`, parse compact `/YYYYMMDD/` upload dates alongside `/YYYY/MM/DD/` and `/YYYY-MM-DD/`, and preserve `0` extra HTTP calls on idle polls and `schedule`/`codes` runs.
- **Cross-version bleed protection, shortlink Tier-2 → Tier-1 upgrades, peer failover sync & override key-art precedence (`gamexpress/maintenance.py`, `gamexpress/state.py`):** tighten `LAUNCH_MEDIA_MAX_BEFORE_S` (`14d` → `11d` for unversioned shortlinks, retaining `-10d` Special Program Friday uploads while rejecting shortened 5-week `-14d` prior Phase II wallpapers), record canonical asset locators observed on earlier versions (`seen_media`) and sync `seen_media` across `State.merge_peer(..., include_maintenance=True)` so stale wallpapers/videos never bleed across version boundaries even across primary → standby failover, permit Tier-2 `.webp` → Tier-1 `.webm`/`.mp4` upgrades within the launch window when HoYoPlay rotates opaque shortlink `bg["id"]` entries, and prioritize `overrides.json` `"image"` pins first in Tier 3 ahead of `program_announcements.json`.
- **Plan resolution, epithet/unnumbered Convene inference, sibling 5★ merge & tweet media deduplication fixes (`gamexpress/maintenance.py`, `gamexpress/schedule.py`, `gamexpress/media.py`):** parse ISO-8601 timestamp strings as well as numeric epochs via `schedule._to_ts()` in `resolve_version_plans()` (preventing `ValueError` on documented ISO overrides); extend `schedule.infer_versions()` to resolve unnumbered/epithet maintenance notices (such as Genshin Impact `Version "Luna II" Update Maintenance Preview`) across both `schedule` and `maintenance` via sibling notices, `version_name` / nearby timestamps in tracked records, `pre`, or `bump_minor(live)`, and to match unnumbered official Convene / Wish posts (such as `@Wuthering_Waves` status `2112740670930604168` `[Nine Deaths, One Unbent Heart] Featured Resonator Convene` seen live in `Monitor #916`) against co-running sibling banner extracts, `version_name`, or active tracked `maint_start_ts` windows (`banner_start_ts` used solely for version/phase matching and never rendered as a clock timestamp); unite co-running official 5★ banner posts within the same phase when they share an identical valid 4★ rate-up lineup (`["Suoming", "Lucilla", "Lynae"]` across Kuro `article/5668` + X `2112740670930604168`, or concurrent HoYoLAB/X Wish-1 + Wish-2 posts even at identical `published_ts`) with zero re-poll or post-age-out churn; default unnumbered pre-release launch notices (`HNA` / `ANANTA`) to `"1.0"`; preserve refined non-cadence `schedule` estimates (`countdown` sources on 5-week / 7-week shifted patches) ahead of generic `+42d` `predict_cycle()` math; and normalize `?format=<ext>` tweet photo URLs in `media._same_file()` while treating `name=large` as smaller than `name=orig` in `media.rank()`.
- **Cross-feature Components V2 button/row guards, pending redemption-code corroboration, upstream credits & repository-wide doc sync (`gamexpress/cards.py`, `gamexpress/codeposter.py`, `README.md`, `AGENTS.md`, `PRIVACY_POLICY.md`, `TERMS_OF_SERVICE.md`, `docs/*`):** enforce Discord's `512`-character link-button URL ceiling (`BUTTON_URL_MAX = 512`) and non-empty `1..5` Action Row validation across `link_button()`, `validate_payload()`, and `news_payloads()` so oversized button URLs never trigger `HTTP 400 Invalid Form Body` across `schedule`, `codes`, `news`, or `maintenance` cards; update `rec["gate"]` cleanly when `pending` code records gain same-family witnesses (matching live `state.json` `OKTCHX26J57Q`), preserve cached `rec["rewards"]`, and carry forward prior `pending` witnesses only when their upstream was unreachable (`None`) on the current poll without overriding active-removal or expiry signals; refresh upstream credits across `docs/CREDITS.md` and `README.md` (`FxEmbed/FxEmbed` replacing pre-rename `FixTweet/FxTwitter`, `torikushiii/hoyoverse-api`, `TwintailTeam/TwintailLauncher` & `TwintailTeam/game-manifests`, `TomyJan/GenshinImpact-Client-Version`, `gengamer.in` & `gachacountdown.online`, `corenting/eddrit`, `dylanpdx/BetterTwitFix`, `status.d420.net`, `Discohook`, `pytest`, `PyYAML`, `reviewdog/action-actionlint`, and full Fandom code + banner attribution); and synchronize all 22 repository Markdown files, changelog index anchors, legal effective dates (`October 23, 2026`), priority/media tables, and `PROD-REPO-SETUP.md` runtime counts with automated CI link/anchor/index assertions. Verified across all 4 features and all 6 games via offline unit/simulation fixtures; live Discord delivery of future patches remains unverified until upstream release windows occur.

## 2026-10-22 — Live maintenance crash hotfix, stage fault isolation, and end-to-end ANANTA/HNA hardening

- **Live maintenance crash fix (`gamexpress/maintenance.py`, `gamexpress/schedule.py`):** filter `None` entries from `ver_extracts` in `maintenance.resolve_version_plans()` and guard `schedule.infer_versions()`, `schedule.needs_program_lookup()`, `schedule.needs_media()`, and `schedule.merge()` against `None` or non-dict records, resolving the `AttributeError` when a classified post has no extractable schedule fields (`extract(game, item) -> None`).
- **Stage & per-game fault isolation + guaranteed persistence (`gamexpress/runner.py`, `gamexpress/schedule.py`, `gamexpress/maintenance.py`, `gamexpress/state.py`):** wrap top-level stages (`schedule`, `codes`, `maintenance`, `news`, `program_announcements.json`) in `_safe_step()` inside `try ... finally` so `state.prune()`, `state.save()`, and `write_summary()` always run even when an intermediate stage errors (preserving already-delivered state and emitting `$GITHUB_STEP_SUMMARY` diagnostics), while suppressing `state.heartbeat()` on `ctx.errors` so standby failover remains accurate; add per-game error boundaries across `schedule.run()`, `maintenance._ensure_inputs_for_games()`, `maintenance._run_game_maintenance()`, and single-article `runner.run_news()` fetches; persist silent news baseline immediately; and harden `State.load()` / accessors + upstream JSON parsers (`launcher`, `hoyolab`, `kuro`, `codes`, `bannerfeed`, `calendarfeed`) against malformed non-dict sub-records while preserving `textutil.news_blocks()` `ValueError` hold semantics.
- **End-to-end `ANANTA` (`ananta`) & `Honkai: Nexus Anima` (`hna`) audit fixes (`gamexpress/config.py`, `gamexpress/__main__.py`, `gamexpress/maintenance.py`, `gamexpress/http.py`, `gamexpress/models.py`, `gamexpress/codeposter.py`, `gamexpress/cards.py`):** expand `MAINTENANCE_GAMES=all` via `ALL_MAINTENANCE_GAMES` (`6` games: `genshin`, `starrail`, `zzz`, `wuwa`, `hna`, `ananta`) so setting `DISCORD_WEBHOOK_MAINTENANCE_ANANTA` activates `ananta` automatically while keeping `NEWS_GAMES=all` scoped to the 5 structured HoYoLAB/Kuro feed games (`DEFAULT_OPTIONAL_GAMES`); add `"ananta"` (`1.0`) to `sample_payloads("maintenance")`; lower official timestamp provenance threshold in `maintenance.resolve_version_plans()` from hardcoded `40` to `schedule.PRIORITY["reddit"]` (`38`) so verified official publisher Reddit posts (`u/AnantaOfficial`, `u/HonkaiNexusAnima`, `u/genshinimpact`, `u/HonkaiStarRail`, `u/ZZZ_Official`) qualify as official pre-install/maintenance timestamps; allowlist NetEase / `ANANTA` media hosts (`easebar.com`, `anantagame.com`, `netease.com`, `163.com`) in `_news_media_prefix()`; and render verified publisher `"reddit_official"` code hits as `Official Reddit` (`verified=True`) while keeping community `"reddit:<sub>"` unverified (`Reddit`) and mapping `"reddit"` / `reddit.com` links accurately across schedule/item provenance labels.

## 2026-10-22 — Reddit & Redlib fleet, Rotation #7 (teapawt TLD expansion + mie.foundation), and live banner/edge-case hardening

- **Reddit & Redlib integration across all six games (`gamexpress/sources/reddit.py`, `gamexpress/config.py`, `config/games.json`):** add ordered `DEFAULT_REDDIT` (`17` entries: `7` active dual-path Redlib hosts first — `redlib.catsarch.com`, `redlib.privacyredirect.com`, `snoo.habedieeh.re` v3.0.0, token-gated `redlib.miningtcup.me` sharing `NITTER_RSS_TOKEN`, `redlib.tiekoetter.com`, `redlib-1.privadency.com`, `redlib-2.privadency.com` — followed strictly last by `10` partial/runner-gated/legacy fallbacks costing `0` requests on healthy runs while omitting runner-refused/challenge/interstitial/broken/alias hosts), `DEFAULT_REDDIT_PROXIES` (`vxreddit.com` → `embedez.com` → `embeddit.deltandy.me` supporting Mastodon v1 JSON, OpenGraph tags, and unfinished v2 `<script id="discord:component-embed">` HTML while prioritizing muxed audio+video), and `DEFAULT_REDDIT_ARCHIVE` (`arctic-shift.photon-reddit.com`). Support optional `REDDIT_FEED_TOKEN` in all `.rss?feed=…`, `.json?feed=…`, and bare `<40-hex>&user=…` variants (`[0] www.reddit.com` → `[1] old.reddit.com` 1-request RSS fast path + circuit-broken `.json` fallback on both `/r/<sub>` and `/user/<acct>`), automatic zero-waste failover on `schedule` (`0` user-feed requests when X + primary APIs succeed), unverified `reddit:<Subreddit>` 2nd-witness corroboration on `codes` across all 6 games (alongside all 6 Fandom wikis including `hna` and `ananta`), `u_<account>` profile-post acceptance, crosspost `selftext` inheritance, OP-comment body/link/image merging across HTML/RSS/JSON, and desktop browser UA parity.
- **Security, credential hygiene & config edge-case hardening (`gamexpress/discord.py`, `gamexpress/http.py`, `gamexpress/runner.py`, `gamexpress/config.py`):** redact live Discord webhook paths across `discord.com` / `discordapp.com` / `canary.discord.com` / `ptb.discord.com` in live error/hold logs (`_redact_webhook`), scrub `user=`, `feed=`, `token=`, `auth_key=`, `key=`, `api_key=`, `access_token=`, and `Bearer` in logs and run summaries, and HTML-unescape `PING_*` / `EMOJI_*` values (`parse_ping`, `parse_emoji`) so pasted `&lt;@&amp;…&gt;` or `&lt;:…&gt;` strings never drop mentions or trigger Discord `400` rejections. Update all documentation, legal policies (`Effective date: October 22, 2026`), `.env.example`, and credits (including **[Arena AI](https://arena.ai/company/about)** · [@arena](https://x.com/arena?lang=en)).
- **Rotation #7 (`DEFAULT_NITTER` 21 → 27 entries, 26 live; nothing deleted):** live-verify all six newly added mirrors across all 8 union handles (`48/48` feeds on `2026-10-22`, `100%` top-tweet ID parity against `nitter.cf`/`xitter.cf`, zero refusals): `https://teapawt.org` (`426 ms` avg on `status.d420.net`, `100%` uptime), `https://xitter.gq` (`450 ms`, `100%`), `https://nitter.gq` (`455 ms`, `100%`), `https://teapawt.net` (`462 ms`, `100%`), and `https://teapaw.org` (`488 ms`, `100%`) from `4cuck/teapawt` (`status.d420.net` commit `145ca9eb`, explicit scraping permission + single-tweet `/<account>/status/<id>/rss`), plus `https://nitter.mie.foundation` from `codeberg.org/shitter/shitter/wiki/Instances` (`rev a75ff9fa14`, independent `shitter` instance with native `t.co` expansion). Keep `nitter.cf` (slot 1), `xitter.cf` (slot 2), `nitter.meowing.monster` (slot 3), and `nitter.miningtcup.me` (slot 4) as the four runner-proven Batch 1 hosts; seat `teapawt.org`, `teapaw.org`, `teapawt.net`, and `nitter.mie.foundation` (`TRIAL`) across Batch 2 (`slots 5–8`) and `xitter.gq`, `nitter.gq`, `nitter.freedit.eu`, `nitter.gravitywell.xyz` across Batch 3 (`slots 9–12`); extend `STATUS_MIRRORS` across `.cf`/`.org`/`.net`/`.gq`; parse `piped.video` YouTube rewrites in `textutil.youtube_id()`; and preserve `card_img/` query parameters in `media.nitter_pic_to_twimg()`.
- **Live upstream banner classification & self-healing fixes (`gamexpress/schedule.py`):** (1) add `channels?` to `DEFAULT_BANNER_RE` and scan both `item.title` and `item.text[:200]` in `classify()` so official ZZZ HoYoLAB notices (`47131668`, `"V3.3 Limited-Time Channels (Phase I)"`) are extracted at priority `50`; (2) recognize fullwidth/Unicode Roman numerals `Ⅰ`/`ⅰ` and `Ⅱ`/`ⅱ` in `PHASE1`/`PHASE2` for official Wuthering Waves Convene notices (`5546`, `5668`, `@Wuthering_Waves` X posts); and (3) self-clear stale `b_phase*_conflict` flags when re-reading an official post agrees via `_same_names()`, and allow `apply_banner_feed` / `apply_gacha_wiki` to fill an empty `phase*_4` slot left `TBA` by a single-post extraction count miss without loosening genuine two-post `"official sources disagree"` locks.

## 2026-10-21 — Optional news timestamps, pre-load/maintenance started cards, and expanded full articles

- **Addition 1 — `NEWS_TIMESTAMPS` (default `0`):** add single-pass `O(N)` render-only conversion (`gamexpress/news_timestamps.py`) of exact TZ-qualified date-times (including bare `UTC`/`GMT` at `+00:00`, explicit offsets, and news `server time` `UTC+8` fallback) into Discord `<t:EPOCH:f>` tags across `genshin`, `starrail`, `hna`, `zzz`, and `wuwa`, with exact `±180`-day yearless resolution around `published_ts`, conservative Dec/Jan rollover without repairing inverted ranges, and strict protection against partial conversion of invalid/ambiguous explicit endpoint zones, invalid/inverted/half-qualified ranges, URLs, code spans/blocks, existing `<t:…>` tags, date-only phrases, and `timeparse.py` schedule extraction. Disabled mode bypasses scanning completely (`0` parser calls, byte-identical output).
- **Addition 2 — `MAINTENANCE_ENABLED` + `MAINTENANCE_GAMES` (default off):** add independent `Pre-Load Started` and `Maintenance Started` Components V2 alerts (`gamexpress/maintenance.py`) routed strictly to dedicated `DISCORD_WEBHOOK_MAINTENANCE_<GAME>` secrets with optional `PING_MAINTENANCE_<GAME>` / `PING_MAINTENANCE`, silent first-enable baseline seeding, separate `preload` / `maintenance` dedup state and peer merge, `official > override > persisted first-observed launcher signal (labelled observed) > cadence` precedence (supporting holiday shifts without inventing HNA cadence or unknown end times), separated version/launch lock vs selected 4-tier media priority so late matching launch video upgrades initial artwork inside `LATE_MEDIA_EDIT_WINDOW_S` (`6 h` / `21,600 s`) while blocking Phase II swaps, corroborated signed Kuro `?auth_key=…` renewal (`MAX_LATE_MEDIA_ATTEMPTS = 3` consecutive failed `PATCH` calls reset on `res.ok`, `MAX_LATE_EDITS = 6` monotonic total succeeded `PATCH` calls, per-run URL check deduplication) with fallback to matching-version artwork or gallery omission and log/summary redaction, and honest state retention when a `PATCH` edit fails.
- **Addition 3 — `NEWS_EXPAND_FULL` (default `0`):** allow opt-in full-article expansion beyond 2 pages / 7,000 characters up to `NEWS_EXPAND_MAX_PAGES = 12` (`NEWS_EXPAND_MAX_CHARS = 120000`, `NEWS_EXPAND_MAX_MEDIA = 120`), validating every page against Discord component/character/gallery limits, preserving source media order, cover dedup, native vs link video behavior, `Page N` labels, and final-container-only buttons, with labelled excerpt fallback. Conservative stop-and-hold recovery is explicitly enabled for official news and maintenance alerts. Existing schedule/code retry behavior remains at the pre-PR baseline (`stop_on_ambiguous=False` by default on `WebhookClient.send()` across `schedule`, `codes`, and CLI callers, while `runner.run_news` — both ordinary and expanded — and `maintenance.run` pass `stop_on_ambiguous=True` so post-dispatch timeouts, socket drops, response-body read errors, or `2xx` responses missing `"id"`, distinct from definite pre-send connection errors, explicit `4xx` rejections, and `429` rate-limit retries, stop after 1 attempt and hold state durably).
- **Independent official news delivery & safe historical migration:** remove cross-feature suppression of Special Program, broadcast, preload, and version maintenance notices in `gamexpress/runner.py` (`run_news`) so schedule extraction/mirrors, codes, official news, and started alerts operate independently with separate stage-accurate reporting (`discovered`, `eligible`, `attempted`, `delivered`, `deferred/error`), while existing legacy `{"status": "posted", "excluded": "schedule"}` entries (such as Monitor #456 `genshin` `47151000`) stay completed in place without historical floods or state resets.
- **Real-world schedule, codes, news & idle-tick hardening:** (1) replay cached `program_announcements.json` seeds (and surface missing-seed notices via `announcement_gap`) when a schedule card still carries an estimated `program_ts` (`"program_ts" in estimated`), replacing sticky countdown estimates with official broadcast air times and media; (2) support Wuthering Waves `is set to begin/air/...`, `Broadcast Time: ...`, `Preview Livestream` / `Preview Live Stream`, `V3.x`, and unnumbered major-reveal X broadcasts in `config/games.json`, `gamexpress/schedule.py`, and `gamexpress/sources/twitter.py` while excluding post-stream `"has concluded"` recap notices; (3) stamp `config/overrides.json` provenance only when an override value or priority actually changes to eliminate 5-minute `state.json` commit churn; (4) strip `<ref>…</ref>` citations, `{{Code|…}}` / `{{Copy|…}}` templates, and multi-line VisualEditor cells in `gamexpress/sources/codes.py` (`parse_fandom`) so cited Wuthering Waves Fandom wiki rows corroborate pending `ogc` codes; and (5) filter malformed non-`http(s)://` CMS media attributes (`<img src="800" />` / invalid Quill embeds) in `gamexpress/textutil.py` across default, `NEWS_TIMESTAMPS=1`, and `NEWS_EXPAND_FULL=1` rendering.
- **Verification & benchmarks:** add `python -m gamexpress benchmark` offline microbenchmark command (reporting exact commit SHA, clean-tree status, Python/platform, fixture sizes across 1-msg / `<=7,000` 2-page / `>7,000` excerpt vs expanded regimes, default-off parser-bypass check, separated mocked protocol counts vs local CPU `median`/`mean`/`p95` µs timings), HTML `<video>` preview support, documentation updates across `.env.example`, `README.md`, `docs/*`, and `AGENTS.md`, and comprehensive offline regression tests covering all features. No workflow edits, dependency additions, state resets, or live Discord dispatches.

## 2026-10-20 — News article-count cap removal

- Remove the global completed-article cap and ten-attempt per-game cap. Each run attempts all discovered eligible unposted articles in publication order; legacy attempt cursor no longer rotates that order. Existing dedup, partial recovery, future/freshness/baseline, media holds, pagination/state-capacity bounds and message limits remain.
- Retire and ignore NEWS_MAX_POSTS_PER_RUN; remove active settings/examples/CLI references. Preserve its burst-control rationale in the follow-up handoff for a possible future reviewed reintroduction, not an active switch.
- Update current setup/testing docs and Discord rate-limit guidance. No webhook/bot migration, pacing algorithm change, state reset, scheduling change or production deployment.

## 2026-10-20 — News GIF MIME compatibility

- Normalize the observed bare `gif` Content-Type only alongside GIF87a/GIF89a signature bytes in the shared bounded news-media reader. Availability and optional dimensions agree; original GIF URLs/animation sources are unchanged across games.
- Pin HSR 47141115 user URL and the exact prefix logged in production #204/#205; simulated transport regressions retain MIME/signature/status/redirect/host/byte guards. Complete user article/list JSON is replayed through discovery, HTML/Quill comparison, exact eight-media rendering and simulated runner delivery/dedup. Complete GIF decode and live Discord delivery remain unverified. No new adapter, source activation, state reset or schedule change.

## 2026-10-19 — WuWa news publication time

- Dedicated Kuro news discovery uses official startTime rather than draft createTime, falling back only when startTime is absent/empty. Existing freshness/future/baseline/dedup controls remain.
- Regression replays exact captured Lucilla 5626 metadata/detail and original five images; offline runner covers delivery, duplicate suppression, silent baseline and future hold. No production state reset is required for the inspected WuWa floor.

## 2026-10-19 — News video cover layout

- Full/paged news with a playable native MP4/WebM no longer prepends a separate listing cover; explicit body images and media order remain intact. Exact cover/body-image duplicates are shown once. Shared renderer policy is game/source-independent; it does not enable new source adapters.
- Link-only media retains its cover, and oversized excerpts retain their existing single-lead policy.
- Regression covers the real ZZZ 47133580 capture plus synthetic cross-game/format, pagination and excerpt cases.

## 2026-10-19 — News CDN preflight compatibility and diagnostics

- Accept valid offset-zero HTTP 206 media prefixes and application/octet-stream only with recognized media signatures. Preserve host/redirect/status/signature protections and official refresh/hold behavior.
- Log rejection status or MIME/prefix without signed URL queries.
- Regression uses user-captured ZZZ 47133580 JSON; CDN responses are simulated. Actual live rejection cause and Discord delivery remain unverified.

## 2026-10-19

- Support documentation-free production in the fleet documentation smoke guard:
  always assert the configured fleet, check documentation when present, and reject
  partial/stale documentation. Report absent-documentation coverage explicitly.
  Add offline guards for absent, complete, partial and stale documentation.
  CI/Python bump workflows and application behavior are unchanged. Deploy the
  updated existing test file to production; no Markdown upload or state reset needed.

- Refresh Setup for a separate production repository, current news secrets/switches,
  JSON env wiring, safe tests, and state-preserving scheduler migration. Fix stale Python
  auto-merge comments in `.env.example`; keep attended workflow/Python review policy.
- Broaden local-secret/log/editor ignore patterns without ignoring the production state
  or announcement cache. No tracked file is untracked by ignore rules.
- Remove frozen runtime file counts and unconditional historical repair/no-op promises
  from the cutover guide; retain existing locks and original incident context.
- Documentation/template/ignore housekeeping only: no app, workflow, dependency, setting,
  scheduler, state or live-post changes. Nothing here confirms live delivery.

- Integrate optional official news as feature 3 under the root README's "What it
  posts" and mention it in the project introduction. Keep Legal & credits last,
  with its original attribution and legal links unchanged.
- Consolidate detailed official-news setup, paging, source-preserving formatting,
  measured-grouping bounds and safe verification in
  [CONFIGURATION.md](../CONFIGURATION.md#official-news-explicit-opt-in-default-off).
  Update [the docs index](../README.md#official-news--milestone-alerts--off-by-default).
  Remove repeated current-policy appendices from the README and the bottom of
  this changelog; retain dated historical entries unchanged.
- Record the documentation placement/link-check rule in AGENTS.md. This follow-up
  changes documentation only: no runtime, tests, workflow, settings, posting or
  state changes, and no new live-delivery claim.

## 2026-10-18 — Opt-in official news

- Add off-default HoYoLAB news for GI/HSR/HNA/ZZZ and Kuro's current English WW
  index, using dedicated per-game webhook secrets without destination fallback.
- Render full article-order Components V2 content in one message when it fits,
  otherwise at most two independently validated pages for <=7,000 normalized
  characters, or one labelled excerpt container/one lead for longer/unpageable input. Final-container-only custom-emoji buttons; no gallery-only mode.
  Preserve heading/list readability, convert line-leading `●`/`•` to Markdown
  bullets and omit unknown publication times. Overflow excerpts keep half the
  words of the already budget-fitting opening excerpt; fitting articles stay full.
- Add bounded official-media GET/signature preflight with one official-article
  refresh on failure; hold unresolved media instead of posting broken galleries.
  Prefix validation is not complete-download or Discord playback verification.
- Polish HTML/Quill links and heading boundaries; use game name only when
  publisher nickname is missing. Keep raw URL fields, compact bullet lists and
  conditional `※`/`✦` spacing. Keep uninterrupted media runs in one container
  when within message limits. Add optional measured long-strip grouping via
  `NEWS_GROUP_LONG_STRIPS` (default off); no cropping/slicing or source changes.
- Balance adjacent/nested bold spans rather than leaking literal Markdown
  markers, and pad both sides of decorative star headings when missing.
- Keep version/program announcements in schedule and codes/mirrors unchanged;
  ANANTA news remains inactive; Wangyue is excluded.
- Add silent baselines, confirmed per-part retry progress, compatible peer dedup
  and bounded cleanup with publication floors in the existing state file.
- Extend existing offline tests/preview/config/legal docs. No dependencies,
  workflows, new repository files, production posts or state resets. Current
  official-source availability/playback still requires read-only/live verification.

## 2026-10-18 — Attended workflow updates

- Keep eligible package-only Dependabot auto-merge; require attended merges for
  workflow-path updates, including renamed/deleted files. Fetch all PR file pages.
- Continue Python detection/validation/publication but remove Python auto-merging;
  the legacy AUTO_MERGE_PYTHON_BUMP variable is no longer consulted.
- Pin Game to exact CPython 3.14.8; prefer numeric current-patch updates, then
  the next minor. Update only existing allowlisted files and retain all gates.
- GitHub security approval can still be required; check real live execution
  after an attended update. No posting/state/scheduler or dependency-range change.

## 2026-10-17 — Application-only scope

- Improve existing runner summary output in place; no new reporting module or
  runtime file. Explain that repository commit/push happens later in the workflow.
- Clarify privacy/terms disclosures for retained logs/summaries and repository
  access; preserve attribution and warranty provisions.
- Sanitize existing runner summary/annotations and source-summary output;
  clarify that an empty report does not prove healthy sources or no eligible items.
- Leave dependency/Python/Dependabot/update automation and posting/state rules
  unchanged. Proposed code, not a claim of production deployment.

The history that still describes the code on `main`: the Python 3.14 runtime, the automated
version-bump workflow, the 1.9.0 performance and hardening pass, and everything dated since.

Older releases (1.0.0 – 1.7.0, September 2026) live in
[CHANGELOG_ARCHIVE.md](CHANGELOG_ARCHIVE.md). Start at the
[changelog index](README.md).

> **Entries are dated, not numbered.** Version numbers were retired on 2026-10-05 — see the
> entry below for why. Releases up to and including `1.9.0` keep their numbers because that is
> what they shipped as; nothing is renumbered after the fact.

---

## 2026-10-15

**Rotation #6: the xcopy.uk trial's verdict lands, and the hot path goes fully
runner-proven.** The first four post-merge runs delivered the verdict rotation #5 was
built for: xcopy.uk refused the runners with HTTP 403 on all six handles, every run,
across four Azure regions (runs #2662–#2665, 24/24 fetches) while its off-runner body
stayed clean — the exact kareem.one signature, and the rollback line the spec pre-wrote
was never needed because the operator went further: a new ranking rule for the round
(**no member that blocks GitHub Actions / Azure datacenter IPs sits above one that
doesn't**) and a new operator-directed head — nitter.cf, xitter.cf, meowing.monster,
miningtcup.me — the first time all four hot slots carry positive runner evidence.
The union-coverage test then filled the bench: **freedit.eu** joins as the fallback head
(the only host answering 8/8 union handles — all six game feeds plus TYPEII_EN and
PomPom_HonkaiSR — with nitter.cf parity on top tweet ids and zero refusals on record
anywhere) and **gravitywell.xyz** behind it (5/8 union; `User not found` on
GenshinImpact — first seen this round — plus the known Wuthering_Waves and HonkaiNA
gaps, deterministic and complementary to kareem.one's coverage). eir-nya keeps its
no-block status but seats behind the trials (the fleet's only measured runner
non-deliveries: grace losses, 200-with-0-entries, and 429s on every GE-handle probe
this round); thepixora's flapping 403 seats it below everyone who has never refused.
xcopy records its verdict beside kareem in the runner-refused tier — demoted, not
deleted, back up the day it answers the runners. Fleet 19 → 21; nothing deleted.

**Housekeeping: every test file becomes a CI gate, and the stale words go.** `ci.yml` ran only
`tests/test_smoke.py`; the 20 regressions in `test_schedule_epithet_and_settled.py` (the
2026-10-08 schedule-card faults that AGENTS.md invariants #6 and #15 lean on) and the 3 in
`test_gachawiki_placeholder.py` only ever ran under pytest, which CI does not install — a PR
could break them and merge green. Both now run through their own plain runners in `ci.yml`
and in the python-bump gate (which promises "the exact commands ci.yml runs"), the placeholder
test gained the runner and the `sys.path` line it needed to run standalone at all, and
`test_ci_and_the_python_bump_gate_run_every_offline_test_file` fails the moment a new test
file is not wired into both. `compileall` covers `.github/scripts` in CI as AGENTS.md §5 already
said it did. Dead code removed: `codeposter.passes_gate()` (a shim with one test caller, now
`gate()[0]`) and the `WikiDialect.banner_type` / `.category` fields nothing ever read. Words
that had rotted: `ruff.toml` claimed ruff is "not run in CI" (the advisory job has run it for
weeks); `docs/SECURITY.md` promised a `.bak` the state writer never made (it is `.tmp` +
`os.replace()`, and a corrupt file is moved aside as `state.corrupt.json`); `AGENTS.md` listed
a 1.1k-line `schedule.py` (it is twice that), a CLI without `speculate`, a sources map without
`banner_search` / `calendarfeed`, no `models.py`, no placeholder test file, and pointed the
hung-mirror trap at invariant #8 instead of #10; `docs/TESTING.md` carried a test count two
rotations stale (the convention says write none, so now it writes none); every line-number
reference in `docs/TIMESTAMP-PATTERNS.md` pointed hundreds of lines off and its §4 table still
showed HSR's pre-install lead as the un-fixed `88`; `docs/README.md`'s changelog row sat outside
its table; `docs/SOURCES.md` still described the 2026-10-03 hot path and listed
`nitter.meowing.monster` among the demoted; `.env.example` had no `EMOJI_TITLE`. `.ruff_cache/`
joins `.gitignore`. Nothing in `gamexpress/` changes behaviour.

## 2026-10-14

**Rotation #5: xcopy.uk trials nitter slot 2 after the full-coverage test; meowing.monster
— dark 8 hours, revived, IPv6-slow — takes the head of the fallbacks.** The fleet's
proven independent answerer went dark for ~8 hours (05:15–13:35 UTC,
`ClientConnectorError` on every handle, runs #2603–#2616), and a demotion spec was stopped
by its own pre-check when the host revived at ~13:35 (d420 healthy at 13:45, real entries
for 5/6 handles from the runners in run #2621). The operator then ordered every monitored
handle probed before deciding: **xcopy.uk answered 8/8 across the day** — all six game
feeds plus the two News-Express accounts, bodies read, top tweet ids matching the
nitter.cf controls (current, not stale), full fidelity on RTs, quotes, pinned tweets and
articles — while meowing's revival is real but structurally slow for GitHub's IPv4-only
runners (d420 lists the host IPv6; grace-race losses even after recovery). Slot 2 passes
to xcopy.uk as a TRIAL: the hot path's every-run probe is the only mechanism that turns
body evidence into a runner verdict, the quorum never depends on slot 2 (nitter.cf,
miningtcup.me and xitter.cf are three measured answerers), and the first run after merge
delivers the verdict — rollback is one line if the runners refuse it. meowing, a proven
answerer through one bad day, waits at the head of the fallbacks: zero requests while the
hot path is healthy, first backup, back up the day it outdelivers the trial. No ledger
moves — a dark day plus revival is a position change, not a verdict. The audit trail that
chose xcopy: nitter.pp.ua (98 % on d420) and nitter.poast.org refused the hand probe on
/rss outright — and the same-day fill-in sweep showed pp.ua's `/rss` serves
shitter.thepixora.com-generated bodies: an alias, never an independent candidate;
shi.meowing.de fronts a browser challenge; xnologin.com redirects to a
"RSS feed is disabled" page; nitter.privacyredirect.com errors; nitter.catsarch.com shut
down. Slots 1/3/4 untouched, nothing deleted.

## 2026-10-13

**A display-only card edit names itself.** `banners_display` joins `CARD_FIELDS`, so the
silent edit that lands the wiki's full display names now reads
`✏️ ZZZ 3.3: schedule card updated — display names` instead of saying nothing (run #1386
was the edit that had no words). Also: `shitter.thepixora.com` is demoted out of the nitter
every-run batch — HTTP 403 on all six handles from the Actions runners (run #2312) while
serving a clean body off-runner, the same signature that demoted `nitter.kareem.one`.
Position matters: `twitter.py` probes `fleet[:4]` every run, so a mirror only truly stops
costing requests once it sits at position 5 or later. thepixora lands there — the head of
the fallbacks, batch 2 — while `tw.eir-nya.gay` (not blocked, just loses the quorum race)
moves up into the vacated hot-path slot 4, since a merely-slow mirror can still win the race
some runs and a 403'd one never can. Demoted, not deleted, per the fleet rule — it moves
back up the day it answers again.

**The README's Changelog section becomes a pointer, and the broken Configuration anchor is
fixed.** The section no longer inlines the latest entry (−62 lines): it now links the full
changelog and the archive, News-Express style — no content was lost, every deleted bullet
already lived in `docs/changelog/`. The changelog ritual is two parts from here on: the dated
entry and its index row. Also: the Contents link `[Configuration](#-configuration)` never
scrolled anywhere — the `## ⚙️ Configuration` heading is U+2699 + U+FE0F, and GitHub's heading
ids keep the invisible variation selector, so the fragment matched nothing. The heading is
`## 🔧 Configuration` now and the link works; every other anchor in the README was already
correct.

**Rotation #4: eir-nya's slot-4 trial ends after one run; xitter.cf warms the slot.** The
first run after rotation #3 (#2323) measured the promoted mirror on all six handles:
`tw.eir-nya.gay` answered HTTP 200 with 0 entries every time — a body that parses to nothing,
the same uselessness it showed when it lost the NITTER_GRACE race on 2026-10-03, now measured
twice. `xitter.cf` moves up from the fallbacks into slot 4: it answered from the Actions
runners across its whole pre-2026-10-03 hot-path tenure (it was demoted then for being
nitter.cf's second domain, never for failing a probe), and slot 4's job is to answer — the
request count is unchanged either way, so the difference is that the fourth request now goes
to a mirror that delivers. eir-nya drops back to the fallbacks behind thepixora — demoted,
not deleted, per the fleet rule; it moves back up the day it delivers a real feed from the
runners.

## 2026-10-10

**The card's own style: an emoji on every headline, full names on every line, and a run summary
that says what actually happened**

Four quality-of-life changes, each validated against live data before shipping.

**1. The headline scroll is an emoji setting — and every game now carries `<:ananta1:…>`.** The
📜 that ended every schedule-card title is gone. The headline emoji is a setting like the button
emojis: `EMOJI_TITLE`, format `a:name:id` / `name:id` / a unicode emoji / `none`, and the default
is the server's own `ananta1` (`<:ananta1:1558340472525693018>`) on **every game's** card — the
same shape as the Youtube / Twitch buttons, which already carry the server's animated emojis.
`EMOJI_TITLE=none` leaves the headline bare. The emoji must be one the webhook's server can
reach (own server, or a server a helper bot like Discohook bridges by sitting in both); one
borrowed from a random bot's server posts as the raw `<:name:id>` text — the original `ananta2`
came from a bot's server and was replaced for exactly that reason. The `📜` in the run summary
(`📜 ZZZ 3.3: schedule card posted`) is untouched — that line lives in the GitHub log, where
Discord emoji syntax cannot render.

- **`parse_emoji` no longer misreads a name that starts with "a".** The animated marker needs
  its own colon now: `ananta1:1558…` is the STATIC `<:ananta1:…>`, not an animated
  `<a:nanta1:…>`. Any `EMOJI_*` value whose name begins with "a" was affected.

**2. Full display names on the card, when the data carries them.** The official notice writes
`Phoenix`, the wiki `Phoenix Reffaella`, and the ZZZ 3.3 card showed both forms at once (short
phase lines, full re-runs line). Each wiki read now also builds `banners_display`, a
`{short: full}` map from the debut roster and channel list — the same prefix rule the debut
detection already uses — and the card maps every banner line through it at render time.

- **Render-time only.** The stored banner data, the provenance, the confirmation and lock
  machinery and every comparison are untouched — those keep the short form exactly as each
  source wrote it. One silent in-place edit shows the full names (the map is part of the card
  data, so the payload hash moves once); if the wiki corrects a full name, the next re-check
  follows.
- **Data-gated, so automatically per-game.** The false-positive sweep across the captured
  version pages: genshin 7.1 / starrail 4.6 / wuwa 3.7 produce empty maps (single-name wikis);
  zzz 3.2 maps `Claret → Claret Flint`, `Roxy → Roxy Ifrita Pryce` — exactly what the golden
  3.2 card already shows, because the *wiki* wrote those phases. One card style, whichever
  source filled the data.
- The live capture is pinned as `tests/fixtures/gachawiki/version_zzz_3_3.wiki`, and the
  line-up it yields is exactly what run #1349 stored.

**3. The WuWa `※ 4 Star Characters:` summary auto-hides once both phases carry their lists.**
The summary is the pre-notice 4★ signal (the wiki knows the full roster before any phase
notice exists, and often names phase 2's 4★s early); once both per-phase lines are filled it is
their union — the same names one line up — so it hides on the same silent edit that filled the
second phase. Symmetric with the existing `※ Confirmed:` rule. The golden cards are unchanged
(their phase lines are TBA).

**4. The run summary answers "what happened to this card?" on its own.**

- **The edit line names the banner keys that moved, and who wrote them** — the writers are the
  prov witness groups: `✏️ ZZZ 3.3: schedule card updated — banners (reruns ← wiki)` (run
  #1349's line said only `— banners`). A withdrawn key renders bare (`reruns`).
- **Locks are announced.** A witness settling a name changes no field, so it used to happen in
  total silence: `🔒 ZZZ 3.3: phase1_4 locked (calendar + wiki)` now says who settled what.
- **The WuWa banner-search warning no longer fires when the Kuro menu merely answered with
  nothing published yet** (that is the pre-notice normal, now INFO with that context); the
  WARNING is reserved for the menu being unreachable with the mirror also empty.

Also: the third `Watch` button is documented (SOURCES.md + TROUBLESHOOTING.md row) — it appears
when the announcement post itself links the livestream video, and Genshin 7.1 / ZZZ 3.3 simply
did not; and BANNER_DATABASE documents the two name forms and the display map. New tests pin
all of it (272 in the CI runner, 295 under `pytest`); the golden cards are unchanged.

---

## 2026-10-09

**The banner reader learns the ZZZ X dialect: a quoted channel title is never a character**

ZZZ posts its channels on X in a dialect the reader had never seen: the bare word is the agent
and the quoted string is the channel — `S-Rank Agent Phoenix Signal Search "Into the Flames of
Life"`. The bare-name reader did not know that `Signal Search` is prose naming the channel, so
it rejected the whole run as too long and the quoted fallback published the channel title as the
5-star agent. From the 11:50 UTC run the live ZZZ 3.3 card showed `Into the Flames of Life,
Graceful Gale` (Phase I) and `Answers in the Wind, Outlier of Prodigies` (Phase II), both 4★
lines TBA.

- **A bare name ends where the gacha-mode phrase begins.** `schedule.CHANNEL_MODE` names the mode
  phrase of every game — `signal search`, `exclusive channel`, `limited-time channels`, `event
  wish`, `event warp`, `character event`, `featured resonator`, `convene`, … — the vocabulary of
  `config/games.json` `banner_patterns`. `bare_names()` and `extract_banner()` cut the run there,
  quote-aware (`_cut_channel_mode()`): a quoted span that *follows* the mode phrase is the
  channel's name, while a quoted name that merely *contains* a mode word (`"Event Wish"` fed as
  a name) still reads as a name.
- **The quoted fallback refuses a channel title too.** A quote that follows a mode phrase is
  never published as a character, even when the bare name cannot be read at all.
- **The fix is game-wide, not a ZZZ override.** The two real V3.3 tweets (fixtures
  `fx_zzz_3_3_channels_phase1.json` / `fx_zzz_3_3_channels_phase2.json`, captured from
  `api.fxtwitter.com` on 2026-10-09) now read Phoenix, Velina and Severian, Norma. The V3.2
  HoYoLAB notices (fixtures `hoyolab_zzz_46604530_full.json` / `hoyolab_zzz_46863847_full.json`)
  read exactly as before, and the Genshin, Star Rail and WuWa dialects are pinned unchanged by
  the existing regression tests.
- **The live card heals itself.** Re-reading the same two posts (same source, same timestamps,
  still inside the 72-hour lookback) rewrites both phases through the same-post path in
  `merge()`; the settled lock never moved. `state/state.json` now carries the healed names with
  `payload_hash` deliberately left stale, so the next run still edits the card in place.
- **The calendar fills the 4★ line.** `api.ennead.cc/mihoyo/zenless/calendar` now lists the 3.3
  Phase I banner (Phoenix, Velina; Seth, Manato at A-rank), so `4 Star Characters (Default)`
  fills from it once due. Phase II's A-ranks stay TBA until the calendar or the wiki lists them.
- Tests: 266 in the CI runner, 289 under `pytest` — the five new ones in section E of
  `tests/test_schedule_epithet_and_settled.py`.

---

## 2026-10-09

**Banner names lock on any two reputable sources, the official calendar is a source, and 4★ / A-rank lists follow the same rule**

- **Any two sources agree and the name locks**, for every game and for 4★ and A-rank lists as well as 5★. The
  sources are the community hub, the official game calendar (new), and the game wiki. Official notices still lock alone.
- **Official calendar** (`sources/calendarfeed.py`, `api.ennead.cc/mihoyo/{genshin,starrail,zenless}/calendar`).
  It fills empty phases with names only, never times, and it is asked on the title search's budget (`calendar_due()`,
  stamp `calendar_ts`, one request per game per run). The 4★ rule is the wiki's: exactly the game's rate-up count, else TBA.
  `BANNER_CALENDAR=0` switches it off.
- **HSR 4.6 Phase II (Mortenax Blade)** is filled from the hub and the calendar, and locks once both name her.
  It no longer waits for an official post. The earlier "hub-only until an official post" line is superseded.
- **Stop rule.** The title search and the calendar stop watching a card once its phases are final: phase 1 and phase 2 each have their 5★ and 4★ lists locked. A card with no phase-2 names yet keeps being watched, and the freeze still applies. Re-runs and the 4★ summary stay on the wiki's own schedule.
- **Wuthering Waves 3.7 Phase 1 is pinned to all three names** (Hsin, Chisa, Iuno) in `config/overrides.json`, human-verified
  against the hub and game8's 3.7 page. Phase 1 locked on two names without Hsin, and a locked phase never grows.
  Phase 2 (Suoming, Lynae, Lucilla) is not pinned and still comes from the sources.
- **The announcement lock is written down.** A card locked by the legacy markers (`program_seen` / `media_from`) now stores `announcement_locked`, so the lock no longer rests on a marker that could be cleared.
- **Quieter Kuro log.** An empty Kuro banner menu is logged at info. Only when the GitHub mirror is also empty is it a warning.
- **Calendar log** now counts the 4★ lists it read as well as the 5★ banners.
- Tests: 266 in the CI runner, 284 under `pytest`.

---

**A posted Special Program card keeps its announcement: link, key art and air time are locked**

ZZZ 3.3's card was rebuilt at 05:00 UTC on 2026-10-09 from whatever program posts were still in the
72-hour lookback. The announcement (posted 2026-10-05) had scrolled out, so a same-day giveaway that
repeated the air time became the only match, and the card's title link and key art switched to it.
The log said `schedule card updated — key art, link`, and nothing in the code remembered which post
had opened the card.

- **The announcement is recorded once, then locked.** The first post that gives an air time sets
  `announcement_locked`. From then on the title link, the source buttons, the key art, the air time
  and the programme and version names belong to that post. Only an *estimated* air time can still be
  replaced by an official one. Records written before the flag are locked when they carry
  `program_seen` or `media_from`, and keep their link.
- **A teaser with no air time does not lock.** The real announcement can still take the card, and
  its air time.
- **The explicit flag wins** over the legacy keys.
- **Maintenance keeps updating; banners settle once confirmed.** Pre-install, start and end times and
  compensation still update, and an official value replaces the `🕒 estimated from version cadence` line as
  before. Banner names are covered by the next entry.
- **ZZZ 3.3 is pinned to the X post.** The card was built from the HoYoLAB article `46972907` (its air
  time was recorded from that article, at priority 50). `config/overrides.json` now pins the official X
  announcement `2106957553435312559` as the link, and its photo `HTxU4O3W4AAGolV` as the key art, because
  the lock prefers X. The photo was not checked visually at the time (both image hosts returned HTTP 500
  from the build sandbox), so check the card once. The next run edits the card in place, silently. A `title_url` override
  now names its button after the host it points to (`HoYoLAB`, not the broken record's `X Post`) and
  drops the post it replaces.
- **X is the preferred lock.** When X and HoYoLAB both carry the announcement, the lock goes to the X
  post (`schedule.LOCK_RANK`: X 3, HoYoLAB and Kuro 2, news 1). A HoYoLAB lock taken while X was unreadable
  moves **once** to the X post, when that post has the same air time and was published no later than the
  lock. A giveaway never upgrades a lock, and records without the new keys get no upgrade.
- **Countdown estimates work the same in all six games.** The estimate-to-official replacement is pinned
  for every game, not just ZZZ.
- **Known limit: the first program post seen locks the card.** The cross-game check passes when the
  announcement is seen first, in all six games. When a same-window giveaway is seen first, it locks the
  card in all six. This is documented, not fixed.
- **Open: a reschedule.** A locked card does not follow HoYoverse moving a programme. Pin
  `program_ts` in `config/overrides.json` by hand until that is decided.

The regression tests in `tests/test_smoke.py`, from `test_the_announcement_that_opened_a_card_keeps_its_link_and_key_art`
to `test_a_countdown_estimate_is_replaced_by_the_official_notice_in_every_game`, pin this.

**Single tweets are read from nitter.cf first.** A tweet fetched by id used to try FxTwitter first. It now asks
`nitter.cf` (then `xitter.cf`) for the post's status feed, which reaches back weeks: the ZZZ 3.2 announcement from
2026-08-24 resolved there on 2026-10-09. FxTwitter is still asked when nitter can't answer, and when the post has a
`t.co` link, because nitter leaves those unexpanded and the YouTube stream link is read from the expanded URL.
A nitter photo address `/pic/https%3A%2F%2Fpbs…` now resolves to `pbs.twimg.com` as well as the older `/pic/media%2F…`
form, so the key art is no longer served through a nitter proxy.

A status mirror that fails twice in one run (`STATUS_FAIL_LIMIT = 2`) is skipped for the rest of that run. A
dead `nitter.cf` used to be waited on for every tweet. Two dead mirrors and five tweets now make 4 requests
instead of 10.

**Banners lock on confirmation; until then the feed and the wiki can still correct them**

Banner names kept changing after they looked right, and an official notice could not settle a name on its own.
Now an official notice locks its 5★ or 4★ name when it parses cleanly. A community hub name and a wiki name
lock once they agree. An override locks alone.

- **Locked names do not move.** A locked name is recorded in `banners_settled`. The hub and the wiki
  never change it. An official name is final against later official notices too: a different one is logged once
  as a conflict and not applied. The one exception is a 4★ list: two clean official lists that disagree become
  TBA with a warning. A doubtful 4★ reading never blanks a locked list. Re-reading the same post after a parser
  fix still heals its own name.
- **Unlocked names can still change.** The hub follows its own later reading. The wiki corrects a hub name but
  never an official one. An official notice replaces a hub or wiki name and locks it. A hub title held in a
  phase (a banner name, never a character) is corrected even when locked, and the correction is unlocked again.
  A silent source never erases a value it did not write.
- **The wiki-derived fields lock with their inputs.** Re-runs and the 4★ summary lock only once the wiki names
  them and their phase lists are already locked. The 4★ summary must equal both phases' lists, and a re-run must
  be a name featured in a phase. The early-tier `※ Confirmed:` line never locks.
- **The wiki is read on a budget.** An incomplete banner block (still TBA) is read at most every three hours
  (`WIKI_INCOMPLETE_H`). Before this it was read on every five-minute run: the ZZZ 3.3 card, which the override
  pins, cost 288 wiki requests a day. It now costs 8. A complete block with an unconfirmed name is read at most
  every six hours (`WIKI_RECHECK_H`), a fully locked block is never read, and a card past its freeze is never
  read. Every answered read is stamped in the state, and so is a failed one, so a wiki that is down is not
  retried on every run.
- **Maintenance is unchanged.** Official maintenance times still replace the estimate, as before. A later
  official notice can still correct them.
- **Fixed: an unchanged derived pre-install was re-stamped on every run.** `derive_preinstall()` wrote a new
  provenance clock each run, so the state file changed, and committed, every five minutes for nothing. Measured
  on the same simulated day, the state file was rewritten on 287 of 288 runs before this and on none after.
- **Known limit:** a 4★ or re-run name that only the wiki gives stays open until an official notice or the hub
  confirms it. Genshin 7.1 is in that state, so the wiki is read every six hours until the freeze.

**A deleted copy says it was deleted, and a retirement names the message it retired**

The first live run on the merged code (`#1062`, 2026-10-09 02:26 UTC+8) found the Genshin 7.1 card
and its `#gi-news` copy both deleted by hand, retired both records, and reported it — in two lines
that read the same whether a message was removed or never existed. Those are different stories: one
is a fan-out that stopped at a `404`, the other is a fan-out that may never have been wired.

- `🗂 GI 7.1: … copy not created — copy <message id> was deleted (Discord 10008) and a settled
  version is not re-posted`. A copy that never existed keeps the shorter `— already out` wording,
  and both are asserted to print **once** (the retirement guard is what makes the second run quiet).
- `🗂 GI 7.1: already out — its card is not re-created (message <message id> no longer resolves —
  Discord 10008 — …)`: the retirement branch drops the stored id, so the summary is the only place
  it will ever appear again.
- Both clauses are load-bearing: remove either and its test fails.

### The title link may come from X or HoYoLAB — whichever carries the announcement

The ZZZ 3.3 card linked `hoyolab.com/article/46972907` (it now links the X post); the Genshin 7.1 card links
`x.com/GenshinImpact/status/2096810691021689205`. Both are the announcement itself, so both are
correct — the rule this changelog introduced says the link must be the announcement and never the
*Update and Maintenance Notice*, and says nothing about which platform publishes it. ACCURACY.md and
TESTING.md now state that explicitly, and TROUBLESHOOTING.md explains both `🗂` lines above.

---

**Banner notices are found by title for every game and version; WuWa and ZZZ 4★ extraction fixed**

The lookback window (72 h) could not see HSR 4.6 Phase I, posted 2026-09-27, so its names stayed on the hub
feed. The title search now asks the official sources for the card's own version whatever the notice's age.

- **Title templates per game** (`banner_titles` in `config/games.json`) and an exact matcher (`sources/banner_search.py`):
  `7.1` ≠ `7.10`, Phase I ≠ Phase II, `V3.2` = `Version 3.2`, and fan reposts never count.
- **Official sources only**: HoYoLAB search for Genshin, Star Rail and ZZZ (by `official_uid`), falling back to the
  paged official news list; Kuro's article menu for Wuthering Waves, with the GitHub mirror as the last fallback.
- **Budget**: `schedule.banner_search_due()`, with its own clock (`banners_search_ts`). Settled never; frozen never;
  incomplete every 3 h; unconfirmed every 6 h. `BANNER_SEARCH=0` switches it off.
- **Extraction**: WuWa's *receive boosted* and ZZZ's *have significantly boosted* now end the name list, so Sanhua and
  Nicole are read; the default-agent pair `Name (…) & Name (…)` splits into two names.
- **Verified** against the real posts: WuWa 3.6 Phase I, ZZZ 3.2 Phase I and II, Genshin 7.1 Phase I and II, and HSR 4.6
  Phase I by title. HSR 4.6 Phase II (Mortenax Blade) stays hub-sourced and unlocked; no official post yet.
- **ZZZ Phase I with no suffix**: ZZZ 3.1 Phase I was posted as `V3.1 Limited-Time Channels`. The template
  `V{v} Limited-Time Channels` (Phase I only) now finds it, and every template feeds one newest-per-phase pick.
- **Tests**: 251 in the CI runner (`tests/test_smoke.py`), 269 under `pytest`.

## 2026-10-08

**One Genshin 7.1 card exposed five faults — a card that should never have existed, plus the wrong
art, the wrong link and no air time**

### A programme that already aired never opens a card

- **The creation gate now consults `program_settled()`.** A schedule card *announces* — a version
  whose programme is already in the past is history, posted long ago by somebody else. That is
  every version this bot was deployed after (Genshin 7.1, Wuthering Waves 3.7, …). It is still
  tracked and its record kept current, and a card the bot genuinely posted still receives its
  silent corrections (the edit path returns long before the gate), but a **new** one is never
  opened for it. Genshin 7.1 was announced 2026-09-07, aired 09-12 and shipped 09-23 — yet on
  2026-10-08 a Phase II notice drove an edit of a message id that had never resolved, the edit
  404'd, and a brand-new card was published. `settled` was previously consulted **only** on the
  404 arm, so the gate could not see it.
- **This is also what makes the cached recovery safe.** Handing a long-past programme its
  `program_ts` must not let a six-hour-wide maintenance notice promote it into a fresh post.
- `mode=test` (which still renders the latest real card from an empty state) and
  `REPOST=<game>:<version>` remain the only two overrides — the rule is a default, not a cage.
  The first card this bot genuinely published, the **Zenless Zone Zero 3.3 Special Program**,
  was posted on 2026-10-05 for a programme that airs on 10-09: still ahead, so never settled, and
  it posts exactly as before — a test pins that.

### The card that was built from the wrong post

- **A maintenance notice no longer opens a schedule card.** A card exists because an official
  *Special Program* / *Special Broadcast* was announced; the notice then *fills it in* — that is
  the whole silent-edit design. Genshin 7.1 was opened by its *Update Details* notice on
  2026-09-25, two days after its own maintenance, so it shipped with the notice's cover as key
  art, the notice's URL as its title link and **no air-time line at all** (`cards.py` prints
  nothing rather than a misleading `TBA`). `fresh_maint` now requires a `program_ts` or a
  `program_seen` before a notice may post anything.
- **A version whose record never got its announcement is looked up once more — when the tweet is
  already cached.** `needs_program_lookup()` stood down 12 h after maintenance, which left such
  a version broken for ever: every run carried the wrong picture and the wrong link forward in
  `data`. With the id present in `config/program_announcements.json` the lookup now runs again —
  one `fxtwitter` call that succeeds and sets `media_from`, so it happens once and stops — until
  `CARD_FREEZE_D` closes the card. A version with no cached id behaves exactly as before.
- **A stored id that stops resolving no longer produces a card for a version that is already
  out.** `program_settled()` reads the maintenance date as well as `program_ts` (the same 12 h
  horizon `needs_program_lookup()` uses), because a record opened by a notice never has a
  `program_ts`. Without it, the 7.1 edit 404'd and the card was published **and** copied into
  `#gi-news`, fifteen days after the version shipped.
- **A `404`/`10008` is not evidence of a deletion.** It only says the stored id no longer
  resolves — the message may have been removed, or it may never have existed on this webhook at
  all, which is precisely the Genshin 7.1 case: the card players had was posted by a different
  bot before this one was deployed. So on a settled version the id is dropped and nothing is
  published (`its card is not re-created`); on a version still in the news the old behaviour
  stands — one fresh post whose new id is adopted.
- **TEST_MODE is no longer exempt from that rule** — not because the exemption caused the
  2026-10-08 card (it did not; see *A `404` comment no longer blames test mode* below), but
  because an exemption that re-creates a card for a programme that aired a month ago has no
  honest use. A test run that genuinely wants one asks with `REPOST=<game>:<version>`, which
  bypasses the branch entirely — and after this release a test run never reaches that branch at
  all, because it no longer edits live messages. The data correction is merged and saved either
  way.
- **The game-channel copy obeys the same rule.** `_sync_mirror()` refuses to *create* a copy for
  a settled version (editing an existing one still works, as always), records the refusal in
  `mirror_retired`, and a successful `REPOST` lifts both retirements so the new card keeps
  receiving its silent corrections.
- **`extract_banner` reads `"Epithet" Name`.** Genshin titles the wish banner and *then* names
  the character — the 5-star character `"Tasteful Excellence" Escoffier` — so the quoted span is
  the *banner's* name. `QUOTED_FIRST` used to claim the whole clause, and 7.1 shipped
  `phase2 = ["Tasteful Excellence"]` and `phase2_4 = ["Ode and Oblation", "Golden Vow",
  "Coordinates of Clear Frost"]` instead of Escoffier / Dahlia, Candace, Mika. The bare name
  after a closing quote now wins; notices that really quote the character, and bare-name notices
  (HSR), are untouched.
- **After merging**, Genshin 7.1 keeps the card it already has and is repaired **in place**: one
  `fxtwitter` call for the cached tweet, then a silent `PATCH` of the existing message and its
  mirror. The card gains its air time (`Saturday, September 12, 2026 8:00 PM` GMT+8) and the
  programme's own key art, its title points at the announcement, and **no new message is
  posted**. No already-aired version — 7.1, Wuthering Waves 3.7 or any other — can produce a new
  card again without an explicit `REPOST=`.

### The test bench, and seeing what a run actually did

- **A test run renders a card; it never repairs one.** `mode = test` promises "the REAL schedule
  card for the version that is out now … exactly what a live run would post", as a throwaway you
  delete afterwards — but for any version that had already been posted it took the *edit* path:
  it silently `PATCH`ed the **live** card (unlabelled — only the repost arm marks a card), stamped
  a 🧪 TEST banner onto the production copy in the game's channel, and then returned without ever
  posting the card the operator asked to see. The Actions dispatch escaped it (its `STATE_PATH`
  starts empty); a local `TEST_MODE=1` did not. A test run now renders one **new** message marked
  TEST, leaves every live card and copy untouched, and reports as much. A seeded version renders
  on the bench too.
- **A lookup that found nothing now reaches the summary.** Finding the announcement *is* the
  repair, and it used to be reported to the job log only — so a card stuck with no air time and
  no link looked exactly like a rendering bug, which is how 7.1 stayed wrong. Both outcomes are
  now in the step summary: `🛰️ GI 7.1: announcement found — programme airs Sat 12 Sep 2026 20:00
  UTC+8` and `🔍 GI 7.1: no Special Program announcement found …`. The lookup stops by itself the
  moment a source answers.
- **The two silent refusals say so.** A notice that correctly did **not** open a card, and a
  notice merged into a version that is **already out**, both look identical from outside — a run
  that posted nothing. Both now report once, keyed on the notice's own timestamp rather than
  every ten minutes.
- **An edit says what it edited.** `✏️ GI 7.1: schedule card updated` never said *what* changed,
  in the one feature that is deliberately invisible; it now reads `— banners, maintenance end`,
  so a silent edit can be confirmed from outside.
- **Two more silent states are now named.** A card that stops being edited because it is
  **frozen** (`CARD_FREEZE_D` = 45 days past maintenance) simply vanished from the summary, which
  is what "why has my card stopped updating?" looks like from outside — it now says
  `🧊 GI 7.1: card frozen — no more edits 45 days past maintenance`, once. And a card that can
  never be repaired — notice-built, past the 12 h lookup window, **no cached tweet id** to replay
  — now says `🩹 GI 7.1: … add one for this version in config/program_announcements.json and the
  next run repairs the card in place`, also once. That second one is the Genshin 7.1 state minus
  the cache: previously nothing anywhere admitted it existed.
- **`docs/TESTING.md` gained a worked example** for a version that is already out — which test to
  run, what the 🧪 TEST card must show (air time, announcement link, key art, banner names), why
  the live card and its copy stay untouched, and what the next live run will do.
- **A `404` comment no longer blames test mode.** Test mode was involved in neither half of what
  happened to Genshin 7.1. The record was opened by the maintenance path on 2026-09-25, which had
  no settled check; every re-appearance since came from the `404` arm of an ordinary live run —
  most recently run #1031 on 2026-10-08 at 13:20 UTC, whose summary line was
  `♻️ GI 7.1: deleted schedule card reposted after edit returned 404` with Discord code `10008`.
  That is the run this release makes impossible.

### Tests

- **New: `tests/test_schedule_epithet_and_settled.py`** — 14 regression tests for the parser, the
  settled rule and the cached recovery, runnable standalone
  (`python tests/test_schedule_epithet_and_settled.py`) in a checkout with no runtime
  dependencies installed, and under pytest.
- **`tests/test_smoke.py`** — the notice-replacement test re-pointed at the new policy (the
  announcement is now adopted *silently*), plus **eighteen new tests**: the notice guard in both
  directions, the already-aired rule and its `REPOST` override, the same rule proven on
  Wuthering Waves' Special Broadcast for both notice kinds, the ZZZ 3.3 over-fix guard
  (an upcoming programme must still post, with its air time), the cached recovery and the lookup
  that found nothing; the frozen card and the card that can never be repaired; the copy
  retirement, the copy that is still edited, the retired copy and the live copy a test run must
  reproduce without ever PATCHing; the `REPOST` revival, three identical re-runs costing no
  request, the summary lines that explain a silent refusal, the two halves of the test-run rule
  (a live run never re-creates; a test run never edits) — and the real live 7.1 record healing
  end to end. Two older tests were named better, so the file runs **205** where `main` ran 188 —
  including `test_a_test_run_still_posts_the_game_channel_copy_of_a_retired_card`, which asserted the half of the
  behaviour this entry forbids.
- **Docs restated for the two new rules**: the README's schedule-card section ("only an
  announcement opens one"), the `repost` note in *Then what?*, and the posting rules now split
  *only an announcement opens a card* / *a programme that already aired is history* /
  *post once, then edit silently*. `docs/ACCURACY.md` carries the same three rules (and the
  `"Epithet" Name` banner wording its parser needs), the cached recovery is spelled out under
  *The announcement's own link and key art*, `docs/TESTING.md`'s healthy-system checklist gains
  **nothing else ever opens a card** and its *Already seeded?* step now says `repost` is the
  override that cards an already-out version, `docs/CONFIGURATION.md` says what `TEST_MODE` and
  `PROGRAM_MEDIA` really do, and the index row for this entry matches its headline. The wording
  that called a `10008` a deletion is gone from the tests and comments too.

---

## 2026-10-06

**Banner line-ups fill themselves in from the game wikis — plus a countdown fix and a
documentation accuracy sweep**

### Banner line-ups from each game's own wiki

- **New reader: `gamexpress/sources/gachawiki.py`.** A banner slot nobody has officially
  announced yet used to print `TBA` until the livestream. All four games have a community wiki
  that documents the line-up the day the beta shows it, through the same MediaWiki API — no key,
  pure JSON. The reader speaks all four dialects (`Wish Pool`, `Warp Pool`,
  `Signal Search Pool`, `Convene/Pool`) and fills the blanks.
- **Blanks only, never an override.** `PRIORITY["gachawiki"] = 6` — above the community banner
  feed (5), below every official source and below `config/overrides.json`. An official notice
  can be *ahead* of the wiki, so the wiki never replaces one.
- **Two requests per game and version, and only while something is still TBA.**
  `schedule.banner_block_complete()` runs before any fetch, so a complete banner block costs
  zero traffic for ever — and a version whose card is already frozen is never asked about at
  all (`CARD_FREEZE_D`, now declared once and shared with the card-edit logic). Request 1 is the `Version/<X.Y>` page; request 2 is one batched
  `prop=revisions` over the dated banner pages it named.
- **Re-runs are a set difference** against the version's debut roster — never "this banner title
  appeared before" (HSR reused `Indelible Coterie` 14 times with disjoint casts).
- **A 4★ list of the wrong length is dropped, not published.** Wiki placeholders
  (`Unknown Character` ×3) are filtered out as well.
- **ZZZ's 4★ line now reads `4 Star Characters (Default)`** — its A-Rank rate-ups are
  player-customisable ("Custom Search"), so the documented list is a default, not a guarantee.
  This is the only byte that changed in any golden card.
- **The early tier.** A version with a debut roster but no phase data yet prints
  `※ Confirmed: <names>` above `※ Re-runs: TBA`. `confirmed` is not part of the banner key set,
  so the line deletes itself on the silent edit that brings the real phase data in.
- **`GACHA_WIKI=0` switches the whole thing off**; no source, no requests. Documented in
  `.env.example`, `docs/CONFIGURATION.md` and the new
  [BANNER_DATABASE.md](../BANNER_DATABASE.md), which is now linked from both doc indexes.
- No new dependencies (standard-library `re` + the existing `Fetcher.get_json`), and the
  User-Agent `Game-Express (banner monitor)` carries no version number.

### Two real countdown misreads

- **A gengamer landing page is a *banner* countdown, not a version countdown.** Genshin's reads
  "7.1 **Banner** Countdown" and timed Skirk + Escoffier on Oct 13 — nowhere near 7.2's release,
  yet it was being wired to `maint_start_ts`. A non-program page must now carry an explicit
  version-release marker or it is ignored.
- **Those pages server-render every timer as `0 Days 0 Hours 0 Minutes 0 Seconds`** and fill
  them in with JavaScript. A zero delta meant "now"; it now means unknown. The guard lives in
  `parse_page()`, because `apply_estimates()`'s window accepts `ts == now`. A timestamp already
  in the past is refused too.

### Python bump script

- **The weekly summary said `current pin: unknown`.** The `old_version` output was only emitted
  on the bump path, so every "nothing to do" run — most of them — reported `unknown`. It is now
  emitted as soon as the pin is read, which also covers the manifest-failure path.
- **The bump PR body no longer claims checks cannot appear on it.** Since the workflow moved to
  `BUMP_PAT`, the PR is opened by a personal access token, so `ci.yml` fires on it normally.
  The inline gate is still what decides the PR is worth opening.

### The weekly bump no longer crashes in a documentation-free production repo

- **`current_pin()` read `ci.yml` unconditionally.** A production repo ships `monitor.yml` and
  nothing else, so the script died with `FileNotFoundError` before it did anything. It now
  reads the pin from whichever workflow is present, rewrites only the files that exist, and
  `bump_ruff_toml()` is a no-op without a `ruff.toml`.
- **`ALLOWED_WRITES` makes the blast radius explicit**: `ci.yml`, `monitor.yml`, `ruff.toml`
  and nothing else is ever opened for writing. No README, nothing under `docs/` — the failure
  mode that corrupted dated history entries in a sibling repository cannot happen here.
- **`add-paths` is now the script's own `changed_files` output** instead of a hard-coded list,
  so one workflow file serves dev and prod with no prod-only edit. `_out()` learned the
  heredoc form for multi-line values.
- **Nothing is proposed when nothing was rewritten** — an empty PR is no longer possible.
- `tests/test_smoke.py` builds a throwaway prod repo *and* a throwaway dev repo, runs the real
  script against a stubbed manifest, and asserts the Markdown is byte-identical afterwards and
  that no `.md` path ever reaches the staged set.
- `docs/PROD-REPO-SETUP.md` gained the dev-repo/prod-repo family model, the bump as an optional
  prod component, and a pre-sync check for the one way a sync can silently *downgrade*
  production's interpreter (GitHub disables a scheduled workflow after 60 days of inactivity).

### Documentation accuracy

- **`BUMP_PAT` is now documented where it is needed**: the full permission list and the
  `refusing to allow a GitHub App to create or update workflow …` failure it prevents in
  `docs/PYTHON_VERSION.md`, the secret tables in `README.md` and `docs/PROD-REPO-SETUP.md`, and
  the setup list in the workflow header. The secret is per-repository even when the token
  covers all repositories.
- **Five workflow comments** in `python_version_bump.yml` still described the pre-`BUMP_PAT`
  world ("a PR opened with GITHUB_TOKEN triggers no workflows"). Corrected — comments only, no
  behaviour change. `add-paths`, `permissions:`, the cron and `python-version: '3.14'` are
  untouched.
- **Python 3.15.0 is dated exactly**: 2026-10-09 (PEP 790), in both the doc and the workflow.
- **The nitter fleet count is now pinned to the code.** `docs/SECURITY.md` said 18 where the
  live fleet is 17, `README.md` said a bare 18 and `docs/SOURCES.md` still said 15. All three
  now read "18 entries, 17 live" (`xcancel.com` is suspended and kept last as a dead entry),
  and a test asserts those numbers against `config.DEFAULT_NITTER` so they cannot rot again.
  `docs/PROD-REPO-SETUP.md` no longer calls `NITTER_RSS_TOKEN` effectively required — with 8
  mirrors answering on 2026-10-06 and only the first two merged, it is useful, not required.
- **Stale facts fixed**: `docs/PYTHON_VERSION.md` no longer hard-codes News-Express's exact
  patch pin;
  `docs/CREDITS.md` linked to the suspended xcancel; `README.md` was missing three CLI flags
  (`--unlaunched --verbose --now`) and never linked `docs/ROLLOUT.md`.
- **The prod manifest would have shipped a broken repo** — it did not name the new module.
  Fixed (34 files / 26 `.py`), and the file-count check now comes with a `diff`-based package
  check that cannot go stale.

---

## 2026-10-05

**`yes` no longer merges a Python series bump — one rule across every repo**

- **The merge gate now requires `all`.** `python_version_bump.yml` previously merged on
  `AUTO_MERGE_PYTHON_BUMP == 'yes' || == 'all'`. It now requires `all` alone. Because this repo
  pins a **series** (`python-version: '3.14'`) and `setup-python` resolves patches by itself,
  every bump this workflow can propose is a new series — so `yes` was authorising exactly the
  one change that most deserves a human glance.
- **Why it matters beyond this repo.** The sibling News-Express repos pin the full `3.14.7` and
  read `yes` as *patch bumps only*, refusing a series jump. The same word therefore meant
  "merge the small ones" there and "merge the big one" here. One rule now holds everywhere:
  `yes` = auto-merge the routine bumps, `all` = also auto-merge the new-series jump. That makes
  `AUTO_MERGE_PYTHON_BUMP=yes` safe to set in **every** repo, with Python 3.15 always waiting
  for a human in all of them.
- **No behavioural change from the shipped state** — the variable was unset here, so nothing
  auto-merged before and nothing does now. Only the *configuration* became uniform.
- **A red bump still cannot reach the merge step**, unchanged: the PR is only created when the
  wheels gate plus `compileall` + `validate` + the offline suite + the preview render all passed
  under the **new** interpreter, and the merge step requires that PR to exist. A failure is a
  `::warning::` deferral that retries the following Monday.
- **Date correction: Python 3.15 is due around October 2026, not 2027.** 3.14.0 shipped
  2025-10-07, so 3.15 is the October 2026 release (actions/python-versions was publishing
  `3.15.0-rc.3` on this date). Two places said 2027: this workflow's header and
  `docs/PYTHON_VERSION.md`. The ANANTA `2027-01-15` launch dates elsewhere are unrelated and
  correct.

**The Python auto-bump can actually merge itself now**

- **The bump PR was waiting on a check that could never be posted.** `python_version_bump.yml`
  opens its PR with the built-in `GITHUB_TOKEN`, and GitHub deliberately does not trigger
  workflows for such PRs — so `ci.yml`'s `pull_request` run never fired, `test` never ran, and
  `automerge-python-bump` (`needs: test`) could never run either. The PR would have sat forever
  with zero checks, and `AUTO_MERGE_PYTHON_BUMP=yes` was a no-op. Latent rather than urgent: the
  pin is a *series* (`'3.14'`), so `setup-python` resolves patches on its own and the workflow
  only fires for 3.15 (expected ~October 2027).
- **The gate moved into the bump job, where it is strictly better.** Before opening anything,
  the job now installs the proposed interpreter and re-runs CI's own commands *under it*, on the
  tree it just rewrote — `compileall`, `validate`, the offline suite, the preview render. The
  old arrangement would have tested the **old** pin; this tests the new one.
- **Missing wheels defer instead of breaking.** Every dependency must install from a prebuilt
  wheel (`--only-binary=:all:`). On the day a new CPython series lands, `aiohttp` and its
  compiled dependencies have no matching ABI wheels yet, and pip would quietly fall back to
  building from source. No wheels, or a red gate, means no PR: a warning and a retry next
  Monday, not a failed run.
- **The merge happens in the same job**, right after the PR is created, still opt-in behind
  `AUTO_MERGE_PYTHON_BUMP=yes` (`all` accepted too, so copying the sibling repo's value cannot
  silently merge nothing — this repo pins a *series*, so every bump it proposes is a series
  bump). It tries squash → merge → rebase and degrades to a warning if the repository has all
  three disabled: a proven-green bump must never surface as a red run because of a settings
  toggle. `automerge-python-bump` is deleted from `ci.yml`. The Dependabot `automerge` job is
  untouched — Dependabot *can* trigger workflows, so that path was never affected.
- **Every gate re-checks that the interpreter actually switched.** `actions/setup-python` for
  the proposed version is soft-failed like the rest, so a version that will not install defers
  instead of going red — but that means `python` could still be the *old* interpreter, and a
  green gate would then be a lie. The wheel install, the gate run and the PR step all require
  it, so the chain stops rather than opening a PR claiming a validation it never performed.
- **No `${{ }}` reaches a shell.** Values are passed through `env:` instead, which is zizmor's
  `template-injection` audit and the standing convention in every other workflow here — the new
  steps would otherwise have been the only findings in the repo.
- **`docs/ROLLOUT.md`** — the step-by-step for switching on the per-game schedule copies, one
  game at a time, with the `Show resolved config` lines to read at each step and the backfill
  warning that makes the order matter.

**Every doc re-matched to the configuration that is actually running**

- **`PROD-REPO-SETUP.md` was describing a repo that no longer exists.** It opened by telling you
  to merge PR #26 and to apply `game-express-speculation.patch` before doing anything — both
  landed long ago and neither file is in the tree. That whole section is replaced by a green-tree
  check. Its file manifest was also off (`gamexpress/` is 25 `.py` files, not 24; `tests/` is 42,
  not 38), its scratch-file exclusion list still named `PR-*` / `*.patch` instead of `APPLY-*`,
  and its docs list did not mention `ROLLOUT.md`.
- **The six `DISCORD_WEBHOOK_SCHEDULE_MIRROR_*` secrets are now documented as part of the prod
  secret set.** They are live, so a prod repo built from the old table would have silently lost
  the per-game fan-out. The guide also now warns that `mode=test` / `test=webhooks` does **not**
  cover them — `check-webhooks` only walks the primary chain, so the `🪞` line in
  `Show resolved config` is the only real verification.
- **`PING_SCHEDULE` is no longer documented as `none`.** It carries a real role ID now. Both that
  guide and `ROLLOUT.md` gained the first-set-wins warning: the literal string `none` *counts as
  set*, so it beats a `PING_ROLE_ID` sitting beside it.
- **`ROLLOUT.md` records that the fan-out is fully switched on** (2026-10-05, all six games) and
  is kept as the reference procedure for standing up prod, or for a seventh game.
- **`DEPENDABOT.md` was quoting a dependency range the repo outgrew** (`aiohttp >=3.9,<4`; it is
  `>=3.14.3,<4`), and now explains why the Python bump cannot use the `ci.yml` gate while
  Dependabot can.
- **The billed-minutes estimate is measured, not guessed** — a whole monitor job is ~15 s
  (5.5 s of actual run), still one billed minute per dispatch.
- **The version number is gone from the User-Agent too.** `BOT_UA` still carried the old
  `/1.1` suffix — a hand-maintained number that stopped being maintained the day
  `__version__` was retired, so it sat frozen, announcing something untrue to every site the
  monitor touches. All three copies now drop it (`gamexpress/http.py`, `sources/codes.py`'s
  Fandom header, and `sources/twitter.py`'s `X_UA`). A bare product token is valid — RFC 9110
  makes the `/version` part optional — and it can never go stale. The contact URL, which is the
  half anyone reading a server log actually cares about, is unchanged.
- **Spent scaffolding deleted**: `APPLY-EMOJI.md` (documented the *rejected* emoji-inside-the-link
  form), `APPLY-COMPACT.md` and `APPLY-CARD-CHANGES.sh` — 480 KB of instructions for pull
  requests that merged days ago.

**The README stops being a history book, and the version number retires**

- **The README is a manual again.** It went from 958 lines to 483: the full configuration
  reference, the accuracy rules, the troubleshooting table and the credits moved into `docs/`,
  and the entire release history moved into `docs/changelog/`. What is left is current
  information only.
- **No more version number.** `gamexpress/__init__.py::__version__` is gone, replaced by
  `build_id()`, which reports the short `GITHUB_SHA`. A bump used to mean four files moving in
  lockstep — the app, this file, the changelog index and the README summary — and missing one
  left the repo contradicting itself. The commit is already exact, already automatic, and can
  never go stale. Run summaries now read `### Game-Express 03c1668 — alpha (primary)`, which
  points at the code that actually posted the card; outside Actions it reads `local`.
- **`app_version` dropped from the heartbeat.** It was written on every beat and never read
  back: the fail-over check only looks at `last_success` and `every_min`.
- **Dead fields removed** — `Item.author`, `Settings.log_level`, `Game.publisher` (and its six
  `games.json` keys) and `FoundTime.has_tz` were all written but never read. `Item.id` is kept
  deliberately: it is the post's identity and the test constructors pass it positionally.
- **Stale facts swept repo-wide** — the test count (141 → 163, in six files), the nitter fleet
  size (16 → 18), the poll cadence (10 → 5 minutes, including the commented-out fallback cron),
  and every cross-reference that still pointed at the README's old changelog.
- `ci.yml` pinned `reviewdog/action-actionlint` with a `# v1` comment while the SHA was
  v1.78.1; corrected, so zizmor reports no findings.

---

## 1.9.0 — 2026-10-02

**The run stops waiting on a hung mirror, and the dead weight is gone**

- **A stalled nitter mirror no longer costs the run its whole timeout.** Each batch of mirrors is
  still requested in parallel in fleet order, but the batch now **stops the moment the winners are
  decided** and cancels the stragglers instead of awaiting the slowest one (`asyncio.gather` →
  `asyncio.wait(FIRST_COMPLETED)` + cancel, in `XClient._probe_batch`). This is the difference
  between run **#217 (16.2 s, `nitter.cf -> TimeoutError`)** and runs #215/#216/#218 (4.9–6.0 s):
  in a reproduction of exactly that run the timeline fetch went from **12.01 s to 0.06 s** with a
  byte-identical result. Cancelling also returns the `Fetcher`'s global request slot immediately,
  so the HoYoLAB / Kuro / code requests queued behind it start sooner.
  - The *selection* is deliberately unchanged — **ranking still beats speed**. A mirror is only
    dropped once enough **higher-ranked** mirrors have answered, never just because it was
    slower, so the merged timeline is the one the old code would have produced.
  - A hung mirror that outranks the answers still gets a grace window, but `NITTER_GRACE` = 1.5 s
    instead of the full 12 s timeout (**12.01 s → 1.56 s** in that worst case).
  - A probe that raises is now logged and treated as a dead mirror instead of propagating out of
    the run.
- **The rate-limit gap is no longer charged after the last post.** Discord's webhook bucket still
  gets its 1.2 s of spacing between two requests, but the wait now happens *before* a request
  instead of after a successful one — so a run that posts `n` cards pays `n-1` gaps instead of
  `n`, and a run that posts a single card pays none at all (**−1.2 s on every posting run**).
- **Install step no longer phones home for a uv version.** Both workflows pass
  `version: latest-known` to `astral-sh/setup-uv`: with no version and no `uv.toml`/`pyproject.toml`
  the action had to fetch `astral-sh/versions`' manifest over the network on **every** run (0.3–4 s
  in runs #215–#218) and install whatever uv was published minutes earlier, unverified.
  `latest-known` is the newest uv whose checksum ships inside the pinned action: no manifest
  lookup, checksum-verified download, and uv only moves when Dependabot bumps the action through
  the usual green-CI gate.
- **CI cancels superseded runs** (`concurrency` + `cancel-in-progress` in `ci.yml` only — never in
  `monitor.yml`, where a cancelled run could post twice), and both read-only checkouts now use
  `persist-credentials: false`.
- **Two more informational checks** in the `advisory-checks` job, which still can never block a
  merge: [`zizmorcore/zizmor`](https://github.com/zizmorcore/zizmor) (static security review of the
  workflow YAML — the repo is clean, with three documented, justified ignores in
  `.github/zizmor.yml` and inline) and [`astral-sh/ruff-action`](https://github.com/astral-sh/ruff-action)
  (the same `ruff.toml` used locally, so a lint regression shows up on the PR without gating it).
- **Dead weight removed** (no behaviour change): `cards.notice_payload`, `Game.redeem_page` and the
  three `redeem_page` entries in `config/games.json` (left over from the "Redeem Page" button
  dropped in 1.3.0), `CodeHit.hard_expired`, `SourceHealth.last_ok_ts` (written on every request,
  never read), and the duplicate `nitter_pic_to_twimg` in `sources/twitter.py` — it now reuses
  `media.nitter_pic_to_twimg`, which also handles the `ext_twvideo_thumb/` prefix the copy missed.
  `codeposter._post` now chunks with `cards.CODES_PER_CARD` instead of a hardcoded `10`, so the
  card size and the chunk size can never drift apart.
- **Honkai: Nexus Anima and ANANTA are switched on** (2026-10-02), months before release, so a
  pre-release Special Program, livestream or code is caught the moment it is announced — the
  first run for a newly enabled game seeds silently, so nothing old is posted. Their official
  YouTube channels (`@HonkaiNA`, `@Ananta_Game`) are wired up; neither has a Twitch channel, so
  their cards simply have no Twitch button, and ANANTA still hides the banner section.
  - New `"released"` flag in `games.json`, separate from `"enabled"`: *watched* and *out* are
    different facts. `test-card --unlaunched` now selects "not released" instead of "not enabled",
    so the sample-card test bench keeps working for games that are monitored but unreleased.
- **Every GitHub Action is now pinned to a commit SHA** (`@3d3c42e…  # v7`) instead of a
  movable tag — the `tj-actions/changed-files` compromise of March 2025 (CVE-2025-30066)
  repointed every tag of a popular action at code that dumped secrets into ~23 000 repos' logs,
  and the related `reviewdog/action-setup` compromise (CVE-2025-30154) hit the org whose
  actionlint action runs in this CI. Dependabot updates SHA pins and their version comments, so
  patches still arrive as PRs.
- **Invisible-character sanitising:** `strip_invisible()` drops C0/C1 controls, zero-width
  characters and bidi overrides in `clean_text()` and again in `cards.text()`, so scraped text
  cannot render as something other than what it says.
- **Hardening against a hostile source** (`docs/SECURITY.md`, new): every scraped URL now goes
  through `cards.safe_url()` — http(s) only, no control characters, parentheses encoded — so a
  taken-over mirror can neither smuggle an extra `[FREE CODES](…)` link into a card nor kill a
  real announcement with a `javascript:` button (that one button is dropped instead). Response
  bodies are capped at 8 MiB, and one game can post at most 5 code cards per run, with the
  remainder following on the next run.
- **Source-coverage guard:** a new test asserts that every game with a HoYoLAB circle is read on
  **all three official tabs** (`page_sort=notices|events|news` = `type=1|2|3`, so 12 requests per
  run across GI/HSR/ZZZ/HNA) and that every enabled game's X account is probed across the nitter
  fleet, `nitter.cf` first — including the two new accounts `@HonkaiNA` and
  `@Ananta_EN`. Dropping a sort or a gid now fails CI instead of quietly missing announcements.
- **The recommended poll interval is now 5 minutes, not 10** — halving the average time-to-post
  with no code change. `docs/SCHEDULER.md` gains a measured *How fast can it poll?* section: runs
  take 19–36 s (≈8 % of a 5-minute slot), overlap is impossible by construction, GitHub is free
  for public repos, and the real limit is politeness toward volunteer-run upstreams. 3 minutes is
  the floor worth defending; 1 minute is not recommended.
- **[AGENTS.md](../../AGENTS.md)** — a maintainer/AI orientation guide: repo map, the invariants that
  must not be "fixed", exact verification commands, measured performance numbers, and the traps
  that have already broken a run (astral-sh tag pins, zizmor suppression placement, the hung
  mirror, the pip cache).
- **Docs caught up with the code:** the privacy policy no longer mentions slash commands or a
  self-hosted runtime (the Discord bot was removed in 1.7.0 — GitHub Actions is the only runtime),
  and the terms no longer claim the Service "never estimates" when a labelled countdown/banner-feed
  estimate is exactly what a card shows before the official notice lands.
- 163 offline tests (new regression tests pin the stop-waiting behaviour, the webhook spacing,
  SHA pinning for every action, the three-tab HoYoLAB coverage, hostile-source handling, and
  that an unsorted feed full of old announcements still posts only the newest one),
  `ruff check .`,
  `python -m gamexpress validate` and `python -m gamexpress preview` all green.

---

## 1.8.1 — 2026-10-01

**Python 3.14**

- **The monitor now runs on Python 3.14** (`.github/workflows/ci.yml` and `monitor.yml` pin
  `python-version: '3.14'`, matching [python.org's current stable release, 3.14.8](https://www.python.org/downloads/release/python-3148/)).
  Pinning the *minor* version only (not `'3.14.8'`) means GitHub's runners keep picking the newest
  3.14.x bugfix release on their own — no PR needed for a patch release, the same trick already
  used for 3.11 before it. Python 3.11 reaches end of active support around October 2027; 3.14 is
  supported into **October 2030**.
  - Verified safe before merging: the three runtime dependencies (`aiohttp`, `feedparser`,
    `python-dotenv`) already ship Python 3.14 wheels/classifiers, and a full repo scan found zero
    uses of any stdlib API removed or deprecated between 3.9 and 3.14 (no `datetime.utcnow()`,
    no `collections.Mapping`, no dead-battery modules, no old asyncio loop APIs, etc.).
  - `ruff.toml`'s `target-version` is now `py314` to match; `ruff check .` is unchanged (0 issues)
    under both the old and new target.
  - **Dependabot cannot bump this for you** — `python-version` is a workflow input, not a tracked
    package ecosystem, so the *next* Python feature release (3.15, ~October 2027) would have
    needed the same one-line manual edit in both workflow files (and `ruff.toml`) by hand — see
    **1.8.0** below, which automates exactly that.
- No functional changes: all 131 offline tests, `ruff check .`, `python -m gamexpress validate`
  and `python -m gamexpress preview` are unaffected.

---

## 1.8.0 — 2026-10-01

**Future Python bumps, faster installs, two advisory scans**

- **New: `.github/workflows/python_version_bump.yml`.** Weekly (and on demand), it compares the
  pinned Python series against [`actions/python-versions`](https://github.com/actions/python-versions)'
  own release manifest — the exact list `actions/setup-python` installs from — and opens a PR the
  moment a newer *stable* series is actually available, instead of waiting for a human to notice.
  It never merges blind: the PR only auto-merges when it carries the `python-bump` label, the full
  131-test CI gate is green on that exact commit, **and** the repository variable
  `AUTO_MERGE_PYTHON_BUMP=yes` is set — unset by default, so today this only ever opens the PR for
  review. Full design, safety reasoning, and the one-time "allow Actions to open PRs" setting it
  needs: [docs/PYTHON_VERSION.md](../PYTHON_VERSION.md).
- **Faster installs in CI and in the 10-minutely monitor run**, both switched from `pip` to
  [`astral-sh/setup-uv`](https://docs.astral.sh/uv/guides/integration/github/)'s `uv pip install`
  (same `requirements.txt`, same resolved packages — just a much faster resolver/installer). The
  monitor workflow runs every 5 minutes, so this is the install path where the speed actually
  matters day to day.
- **Two new informational-only checks**, added as a separate `advisory-checks` job in `ci.yml`
  that can never block a merge (`continue-on-error: true` on both steps):
  - [`pypa/gh-action-pip-audit`](https://github.com/pypa/gh-action-pip-audit) scans
    `requirements.txt` against the PyPA known-vulnerability database on every PR;
  - [`reviewdog/action-actionlint`](https://github.com/reviewdog/action-actionlint) statically
    checks the workflow YAML itself (typos, bad expressions, shellcheck of `run:` blocks) —
    actionlint has no first-party GitHub Action of its own, this reviewdog wrapper is the
    documented way to run it in CI.
- **Housekeeping:** removed `.dockerignore` (the repo has never had a `Dockerfile`) and the
  `DISCORD_WEBHOOK_TEST=` line in `.env.example` (README already noted it's no longer used, since
  the live-test-channel workflow was retired). Fixed three stale "N offline tests" mentions in
  the docs that still said 55/67 instead of the current 131.
- No functional changes to the monitor itself: all 131 offline tests, `ruff check .`,
  `python -m gamexpress validate` and `python -m gamexpress preview` are unaffected.
