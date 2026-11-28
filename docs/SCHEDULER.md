# Scheduler: cron-job.org → GitHub Actions (operator-selected interval)

Game-Express uses the same setup as News-Express. [cron-job.org](https://cron-job.org) (free) calls
GitHub's **workflow_dispatch API** on a fixed interval, and each call starts one
**Game-Express Monitor** run. Choose the interval in cron-job.org; no code change is required.
The current live setup uses ten minutes. Shorter intervals improve typical detection latency but
increase upstream load and Actions runs; see [How fast can it poll?](#how-fast-can-it-poll).

GitHub's own `schedule:` trigger is **disabled** (commented out) in
`.github/workflows/monitor.yml`, for two reasons:

- **The two schedulers race.** In News-Express, two runs checked out the same state and both
  posted the same item.
- **GitHub's schedule is unreliable under load.** It can start 15–60 minutes late or skip runs.

> **Only one scheduler per repo.** To go back to GitHub's schedule, uncomment the two
> `schedule:` lines in `monitor.yml` **and** pause the cron-job.org job.

---

## Step 1: make a GitHub classic personal access token (PAT)

For least-privilege dispatch, a fine-grained token restricted to the production
repository with **Actions: read and write** is also an option. The classic-token
walkthrough below remains supported. Use an Authorization header appropriate to
your token (for example `Bearer <token>` for fine-grained dispatch); never put a
real token in tracked files or chat. The scheduler token is separate from
`BUMP_PAT`, which publishes Python workflow-update PRs.

On migration, pause this job, wait for the old monitor/state push to finish,
copy the latest state and announcement cache, then change only the dispatch URL's
repository name and token permissions as needed. Resume one target only. Repository
names do not confer access; a fine-grained token must explicitly include the new repo.

The token lets cron-job.org press "Run workflow" for you. One classic token works for all of your
repos. If your News-Express token has the `repo` scope, you can reuse it and skip this step.

1. GitHub → your avatar → **Settings** → **Developer settings** (bottom of the left menu) →
   **Personal access tokens** → **Tokens (classic)** → **Generate new token** →
   **Generate new token (classic)**.
2. **Note**: `cron-job.org Game-Express`.
3. **Expiration**:
   - Pick **Custom** and choose a date about a year away, then set a calendar reminder.
   - *No expiration* also works, but it is less safe if the token ever leaks.
   - When the token expires, cron-job.org starts showing **401** (see Step 4).
4. **Scopes**: tick **`repo`**. GitHub's API docs require it for "create a workflow dispatch
   event". Nothing else is needed.
5. **Generate token**, then **copy it now**. It starts with `ghp_` and GitHub shows it only once.

The token lives **only inside cron-job.org**. Do not add it to the repo, a secret, or chat.

---

## Step 2: create the cron-job.org job (one per instance repo)

1. Sign up or log in at https://cron-job.org → **Dashboard** → **Create cronjob**.
2. **Common** tab:
   - **Title**: `Game-Express alpha`
   - **URL**:
     ```
     https://api.github.com/repos/<OWNER>/<INSTANCE-REPO>/actions/workflows/monitor.yml/dispatches
     ```
     Example: `https://api.github.com/repos/uesu/<alpha-repo>/actions/workflows/monitor.yml/dispatches`
   - **Execution schedule**: choose your preferred interval, for example every 10 minutes.
     A custom offset (such as `2,12,22,32,42,52`) avoids the round ten-minute marks. Check
     cost and quotas separately for private repos; see [Minutes and private repositories](#minutes-and-private-repositories).
3. **Advanced** tab:
   - **Request method**: `POST`
   - **Headers** (add each with **+**):

     | Key | Value |
     |---|---|
     | `Authorization` | `token ghp_yourTokenHere` |
     | `Accept` | `application/vnd.github+json` |
     | `Content-Type` | `application/json` |
     | `X-GitHub-Api-Version` | `2026-03-10` *(optional)* |

   - **Request body**: `{"ref":"main"}`. This must be the instance repo's default branch.
   - **Timeout**: the default is fine, because GitHub answers in under a second.
4. **Notifications** tab: turn on **"execution of the cronjob fails"** and **"the cronjob will be
   disabled because of too many failures"**. An expired token then emails you instead of
   silently stopping the monitor.
5. **Save**, open the job, and click **TEST RUN** (or *Perform test run*).

**Expected result:** **`204 No Content`**. Within a few seconds, the instance repo's **Actions** tab
shows a *Game-Express Monitor* run labelled *"Manually run by \<you\>"*.

### Two instances (fail-over)

Create **one job per instance repo**, and never one for a development copy (a repo that must
never post). Such a copy has the variable `ENABLED_FEATURES=none`, so even an accidental trigger
is skipped there.

| Job | URL repo | Schedule | Repo variables |
|---|---|---|---|
| `Game-Express alpha` | alpha (primary) | e.g. minutes `2,12,22,32,42,52` | `INSTANCE_NAME=alpha`, `HEARTBEAT_MINUTES=60`, `PEER_STATE_URL=<bravo raw state URL>` |
| `Game-Express bravo` | bravo (standby) | the same example minutes **+2** (`4,14,24,…`) | `INSTANCE_NAME=bravo`, `INSTANCE_ROLE=standby`, `PEER_STATE_URL=<alpha raw state URL>`, `FAILOVER_AFTER_MINUTES=150` |

The raw state URL looks like this:
`https://raw.githubusercontent.com/<OWNER>/<REPO>/main/state/state.json` (public repos only).

- **bravo stays passive while alpha is healthy.** It only imports alpha's posted keys.
- **bravo takes over** once alpha's heartbeat is older than `FAILOVER_AFTER_MINUTES`.
  - This happens if alpha's cron job is paused, its token expired, or its Actions are down.
  - bravo never takes over if it can't read alpha's state, so a typo can't cause double posts.
- The offset reduces simultaneous upstream requests, and during a fail-over the standby keeps
  the same chosen rhythm. Candidate news is a separate gated prototype; its experimental
  shared-ledger standby requires explicit setup and has not been validated in production.

---

## Step 3: check it's running

- **cron-job.org → the job → History**: a row at your selected interval with **204**.
- **GitHub → instance repo → Actions → Game-Express Monitor**: a green run at your selected interval.
  - Open one run and read the **Summary**.
  - A normal quiet run says "nothing new" and lists source health, such as
    `hoyolab: 9 ok / 0 fail`.
- **Commits**: `auto: update state [skip ci]` appears only when something changed, plus a
  heartbeat about once an hour on alpha. Most runs commit nothing.
- **Existing schedule and code paths seed on their first live run.** Candidate news is different:
  its gated, attended first installation queues available history when backfill is approved. Do
  not initialize or enable it without release review and an explicit backfill plan.

---

## Step 4: response codes

| cron-job.org shows | Meaning | Fix |
|---|---|---|
| **204** | triggered ✔ | — |
| **401** Bad credentials | token wrong, expired or revoked | make a new classic token (Step 1) and replace the `Authorization` header value; keep the `token ` prefix |
| **403** | token lacks the `repo` scope, or a GitHub rate limit | regenerate with `repo`; rate limits clear by themselves |
| **404** Not Found | wrong owner / repo / workflow file name, or the token's account can't see the repo | check the URL: `…/repos/<OWNER>/<REPO>/actions/workflows/monitor.yml/dispatches` |
| **422** Unprocessable | the branch in the body doesn't exist, or the workflow has no `workflow_dispatch` | body `{"ref":"main"}` must match the default branch; merge the PR first |
| **204** but no run appears | Actions are disabled in the repo | *Settings → Actions → General → Allow all actions*; also check the Actions tab isn't showing "workflows disabled" |
| run appears but is **skipped** (grey) | repository variable `ENABLED_FEATURES=none` | correct only on a development copy; delete it on the repo that posts |

**Can runs overlap?** No. `monitor.yml` has a concurrency group with `cancel-in-progress: false`.
A trigger that arrives while a run is still going may wait and then check out the newest state.
GitHub keeps at most one pending run per concurrency group and may replace an older pending run;
this is not a distributed lock or a guarantee against duplicates after crashes.

## How fast can it poll?

Nothing in Game-Express is tied to a particular interval — no code or config change is needed to
go faster. The limits are these, with the numbers measured on real runs (2026-10-02/03):

| What | Measured | Head-room at 5 min |
|---|---|---|
| **Run duration, end to end** | **19–36 s** (median ~25 s: ~15 s runner setup + install, ~5–6 s of actual work) | a run occupies **~8 %** of a 5-minute slot |
| **Overlap** | one running job per repository concurrency group; a newer queued run may replace an older pending run | monitor for delays and holds |
| **GitHub Actions minutes** | public repo = **free and unlimited** | no cost |
| **`workflow_dispatch` API calls** | 12/hour at 5 min, against a 5,000/hour token limit | 0.2 % of the limit |
| **Upstream requests per run** | ~55–65 (HoYoLAB ×9, code APIs & Reddit community witnesses, nitter ×2 per handle across six X accounts, plus Kuro / launcher / banner feed) | ≈ 17–19 k/day at 5 min, vs 8–9 k/day at 10 min |

**The only real constraint is upstream politeness, not GitHub.** HoYoLAB's API is unofficial, and
the nitter mirrors, `hoyo-codes.seria.moe`, `api.ennead.cc`, `feeds.c3kay.de` and `wuthering.gg`
are volunteer-run. Doubling the poll rate doubles the load you put on them, and a 429 or an IP
ban makes the monitor **slower**, not faster, because the source goes dark for hours.

| Interval | Average time to notice something new | Requests/day | Verdict |
|---|---|---|---|
| 10 min | ~5.4 min | ~8 k | current chosen interval; lower request load |
| 5 min | ~2.9 min | ~17 k | faster typical detection, roughly twice the request load |
| 3 min | ~1.9 min | ~28 k | acceptable *if* you watch the `sources:` line in the run summary for `429` / `TimeoutError` and back off when they appear |
| 2 min | ~1.4 min | ~41 k | not recommended: ~1 min of extra speed for 2.4× the upstream load |
| 1 min | ~0.9 min | ~83 k | ❌ no: 1,440 runs/day, near-certain rate-limiting of the community mirrors, and cron-job.org's free tier throttles |

Below ~5 minutes the gain shrinks fast (each halving buys progressively less, because a fixed
~25 s of runner setup and the announcement's own propagation delay dominate), while the load
grows linearly. Select the interval that fits your needs and monitor source rate limits.

If you do go below 5 minutes, watch for these in the run summary and back off if they show up:

- `nitter: … fail (… 429)` or a rising fail count on `codes:seria` / `codes:ennead`;
- `⚠️ <GAME>: no announcement source answered this run` appearing regularly rather than rarely.

## Minutes and private repositories

**Public repositories** get unlimited free GitHub Actions minutes, so a 5-minute interval costs
nothing.

**Private repositories** on GitHub Free include **2,000 minutes a month**. Every run counts as
at least one full minute, although a Game-Express run takes only about 20–60 s.

| cron-job.org schedule | Runs a month | Private repo |
|---|---|---|
| every 5 minutes | about 8,640 | ❌ far over the limit (Actions stops around day 7) |
| every 10 minutes | about 4,320 | ❌ over the limit: Actions stops for the rest of the month (around day 14) |
| every 30 minutes (minutes `0,30`) | about 1,440 | ✅ fits, with room left for CI and the monitor's test bench |

So a private repo should run **every 30 minutes**. Livestream codes usually stay valid for about
a day, so that is still fast enough. The classic token's `repo` scope already covers private
repos. Your account's **Billing** page shows the minutes used.

## Speculated timestamps (version cadence)

When a version has been named but nobody has published its dates yet, the bot fills the gaps from
that game's own release rhythm instead of showing four `TBA` lines. Those values are written at
`PRIORITY["pattern"]` — below *every* real source — so an official notice replaces them the moment
it appears, and the card says so in its footer:

> 🕒 program time, pre-install, maintenance start, maintenance end estimated from version cadence —
> the official notice replaces it automatically

The rhythm lives in `config/games.json` under each game's `cadence` block. Nothing is hard-coded:

```json
"cadence": {
  "days": 42,                 // median gap between maintenance starts
  "maint_weekday": "Wed",     // the day maintenance usually begins
  "maint_time": "06:00",      // publisher local time (UTC+8)
  "maint_hours": 5,           // typical downtime (Kuro runs 7)
  "program_weekday": "Fri",   // livestream / special program day
  "program_time": "20:00",
  "program_lead_days": 12,    // how far before maintenance the program airs
  "confidence": "high",       // high | medium | low — see docs/TIMESTAMP-PATTERNS.md
  "anchor_version": "7.1",    // cold-start anchor, used only until state has 2 real dates
  "anchor_ts": 1790114400
}
```

Delete the block and that game is never speculated about. A malformed value falls back to the
documented default rather than raising.

**Once the installation has seen two real maintenance notices** it stops using `days` and
`maint_weekday` and uses its own observed median gap and modal weekday instead — the same way
pre-install leads are already learned. Speculated values are excluded from that history, so a
guess can never become its own evidence.

**Shortened and holiday-shifted patches** are the known weak spot. Genshin has not missed a
42-day beat in 20 versions and is predicted to the minute; Star Rail, ZZZ and Wuthering Waves
compress and stretch around Chinese New Year (HSR went 58 days, then 28) and land exactly right
between 46 % and 74 % of the time. That is what the `confidence` field is for. The full
measurement, the backtest and the forecast for each game are in
[docs/TIMESTAMP-PATTERNS.md](TIMESTAMP-PATTERNS.md).

To see what would be posted without posting anything:

```bash
python -m gamexpress speculate            # every game
python -m gamexpress speculate --verbose  # plus the real dates it is anchored on
python -m gamexpress speculate --game genshin --now 1791000000
```
