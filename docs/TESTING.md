# Testing Game-Express: is everything working?

Work through the steps in order. Every test runs from GitHub:
**Actions → Game-Express Monitor → Run workflow → `mode` = test** (the test bench has been built
into the Monitor since v1.4.0 — there is no separate Test workflow).

That workflow:

- never commits and never touches `state/state.json`;
- pings nobody unless you tick `ping`;
- works on the development repo too.

---

## 0. Before merging a PR

The PR's **CI — compile + offline tests** check must be green. It runs 67 offline tests, which
cover:

- the real official posts, which must reproduce your reference cards' timestamps;
- the golden cards, Discord limits, the code gate, 4★ TBA, fail-over, and the workflow files.

CI needs no secrets and no network.

## 1. Webhooks: are all channels connected?

Run **`test: webhooks`**.

| You should see | If not |
|---|---|
| **one green "✅ Game-Express webhook check" card per webhook**, listing what that channel receives. For example, your GI codes channel lists *Codes · Genshin Impact* | no card → the secret is missing or wrong. The **"1 · Resolved config"** step in the log shows `✓ DISCORD_WEBHOOK_CODES_GENSHIN` or `— none` for every game |
| log line `[DISCORD_WEBHOOK_…] 1 route(s): OK 200` | `FAILED 401/404` → the webhook was deleted; make a new one and update the secret |
| HNA / ANANTA marked *prepared (off)* | normal until launch; the secrets are still tested |

## 2. Sample cards: does it look right?

Run **`test: sample-cards`** (`kind: all`, `ping` off).

- **Schedule channel**: your 4 reference cards (GI 7.1, HSR 4.6, ZZZ, WW 3.7) labelled
  **🧪 [TEST]**.
- **Each codes channel**: its game's sample codes card, labelled 🧪 TEST.

Check each of these:

- [ ] The **buttons are inside the card**: schedule cards carry Youtube / Twitch / Source,
      codes cards carry one Redeem link per code and the `Citlali News` row underneath.
- [ ] The **timestamps show your local time** and "in 3 days" style relative times.
- [ ] **The emojis animate.** If you see `:name:` instead, give `@everyone` *Use External Emojis*
      in that channel, or change `EMOJI_*`.
- [ ] **Redeem buttons** open the official page with the code filled in (GI / HSR / ZZZ).
- [ ] **Ping**: run once more with `ping` ticked and check that the role is mentioned. The role
      must be mentionable, or the webhook needs *Mention All Roles*.

Delete the test cards afterwards. They are samples, not real announcements.

## 3. Live dry run: do all sources answer?

Run **`test: live-dry-run`**. It does a real run against every live source and builds and
validates the cards, but posts nothing and saves nothing. It looks back 30 days so there is
something to build.

Open the run → **Summary**:

- **`sources:`** lists every source with `N ok / M fail`. Healthy means most sources show `ok`.
  - One dead community source is fine, because every data point has fallbacks.
  - If *everything* fails, the source is having an outage; try again later.
- Lines like `📜 HSR 4.6: schedule card posted` mean the card **would be posted** (this is a dry
  run). The full card JSON is in the log.
  - To see a card, paste the JSON into [discohook.app](https://discohook.app).
- `⏳ GI: 2 new code(s) waiting for a second source: GS71XOXYLG (only ennead), …` → codes seen by
  only one source. They're correctly held back until another source confirms them.
- `🧊 HSR: 12 code(s) ignored — already expired` → codes some source still lists, but another
  source (or their *valid until* date) says they're dead. They're correctly never posted.
- **In a live dry run, the Special Program line is often missing from the cards.** Announcements
  older than a few days aren't in the feeds any more. In production the bot sees them when they
  are new; for an old version you can pin the time in `config/overrides.json`.
- `🕒 HSR 4.6: maintenance start, maintenance end estimated from Gacha Countdown — the official
  notice replaces it automatically` → no official maintenance notice yet, so the card shows the
  countdown site's prediction. Correct, and it disappears as soon as the notice is seen.
- `⚠️ HSR 4.7 phase 1: 4★ shown as TBA — 2 name(s) found, 3 expected` → the uncertain 4★ list was
  correctly replaced by TBA.
- `⏱️ run took …s` → typically 5–20 s.

## 4. Optional: real cards to a private test channel

1. Create a private channel and a webhook for it.
2. Add the secret **`DISCORD_WEBHOOK_TEST`**.
3. Run **`test: live-test-channel`**.

The *real current* cards, built from live data, go to that channel only, labelled 🧪 TEST. Use
this to check real data end-to-end before going live.

## 5. Go live

1. Set up cron-job.org by following [SCHEDULER.md](SCHEDULER.md), then press **TEST RUN**.
   Expect `204`.
2. Check the **first live run**. Its summary says it seeded the current announcements and codes
   **silently** (`🌱 … seeded silently`, no posts). This is correct.
   - To post what's current on that first run instead, set `BOOTSTRAP_POST=1` **before** it,
     then delete it.
   - **Already seeded?** Run the Monitor with `repost` set to an upcoming version from the
     summary (e.g. `starrail:4.6`). A card for a version that's already out (`genshin:7.1` after
     its update) is old news. A version that hasn't been announced yet (`genshin:7.2`) can't be
     reposted, and the summary explains why.
3. From then on, new codes and announcements are posted automatically.

## 6. Healthy-system checklist (check weekly, or when in doubt)

- [ ] cron-job.org **History**: `204` every 10 minutes (per instance).
- [ ] **Actions**: green *Game-Express Monitor* runs every 10 minutes. Red = open it; the summary
      says why.
- [ ] **alpha commits a heartbeat** (`auto: update state`) at least once an hour
      (`HEARTBEAT_MINUTES=60`).
- [ ] **Codes appear within ~10 minutes** of a livestream (official codes skip the 2-source
      rule).
- [ ] **Schedule cards appear** after an official *Special Program / Broadcast* post, and are
      **edited silently** once the maintenance notice arrives: pre-install, start, end and
      compensation fill in with no second ping.

## 7. Fail-over drill (optional, about 3 hours)

1. **Pause** alpha's cron-job.org job.
2. After `FAILOVER_AFTER_MINUTES` (150), bravo's run summary says it took over. It posts
   anything new, with no duplicates, because it imported alpha's posted list.
3. **Resume** alpha. It imports bravo's posts; bravo goes quiet again on its own.

## 8. Local testing (optional, for developers)

```bash
pip install -r requirements.txt pyyaml
python tests/test_smoke.py                 # 67 offline tests
python -m gamexpress validate              # routing, pings, card limits
python -m gamexpress preview               # previews/index.html = every card, Discord-style
python -m gamexpress probe starrail:4.6    # debug ONE real schedule post (read-only)
DRY_RUN=1 TEST_MODE=1 BOOTSTRAP_POST=1 STATE_PATH=/tmp/s.json python -m gamexpress run
```

---

## 9. One card looks wrong? Debug it with `probe`

**Actions → Game-Express Monitor → Run workflow → `mode` = live → `probe` = `starrail:4.6`.**
(Locally: `python -m gamexpress probe starrail:4.6`.) It is read-only — nothing is posted, edited
or saved — and it prints four sections:

| Section | What it tells you |
|---|---|
| **1 · what the lookback window saw** | every official post in the last `LOOKBACK_HOURS`, and which ones matched the version. This is what built the card you have |
| **2 · what is stored now** | the card as it stands: its `title_url`, its source, its picture, its air time and maintenance time |
| **3 · the program lookup** | the official news page tab by tab, then the HoYoLAB fallback; the air time parsed out of the article text; **every image found, ranked, each with why it won** and which one the card will show |
| **4 · the card** | the exact fields the lookup would change (`old → new`) and the finished card JSON — paste it into [discohook.app](https://discohook.app) to see it |

Typical reads:

- *Section 2 links to `…/news/<notice-id>` and section 3 finds a Special Program article* → the
  card was built from the Update Notice. The next run replaces the link and the picture
  automatically (the `PROGRAM_MEDIA` lookup, described in the README under *Version schedule
  card*).
- *Section 3's first image is a `fastcdn.hoyoverse.com` cover but you expected the livestream
  art* → the article has no embedded YouTube player, so there is no 1280×720 thumbnail to prefer.
- *Section 3 says "no program announcement found by EITHER source"* → the version is not on the
  official news page yet; nothing is changed and the card keeps what it has.

---

## What to improve next (suggestions)

| Idea | Why | Effort |
|---|---|---|
| **4★ / banner names from official notices only** (current) → fill gaps with `config/overrides.json` | HoYoverse often shows banners only as images; overrides are the reliable fix, and the card is edited silently | 1 min per version |
| Add **HNA / ANANTA code sources** at launch (seria / Open Gacha Codes add new games quickly) | only official posts and X feed them today | small (`games.json` only) |
| Add a free uptime check (e.g. healthchecks.io) pinged at the end of each run | a second alarm besides cron-job.org emails | small |
| A **LICENSE** file (e.g. MIT) | makes reuse and forking clear | trivial |
| Re-check the nitter fleet every few months (as in News-Express) | nitter instances come and go; X is the main WW source | small |
| More games supported by Open Gacha Codes (Arknights: Endfield, Neverness to Everness) | the code API already has them | small (`games.json`) |
