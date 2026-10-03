# Scheduler: cron-job.org → GitHub Actions (every 5 minutes)

Game-Express uses the same setup as News-Express. [cron-job.org](https://cron-job.org) (free) calls
GitHub's **workflow_dispatch API** on a fixed interval, and each call starts one
**Game-Express Monitor** run. **Recommended interval: every 5 minutes** on a public repo — see
[How fast can it poll?](#how-fast-can-it-poll) for why 5 is the sweet spot and what happens
below it.

GitHub's own `schedule:` trigger is **disabled** (commented out) in
`.github/workflows/monitor.yml`, for two reasons:

- **The two schedulers race.** In News-Express, two runs checked out the same state and both
  posted the same item.
- **GitHub's schedule is unreliable under load.** It can start 15–60 minutes late or skip runs.

> **Only one scheduler per repo.** To go back to GitHub's schedule, uncomment the two
> `schedule:` lines in `monitor.yml` **and** pause the cron-job.org job.

---

## Step 1: make a GitHub classic personal access token (PAT)

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
   - **Execution schedule**: **Every 5 minutes**. On the custom schedule select minutes
     `2,7,12,17,22,27,32,37,42,47,52,57` — deliberately **off** the round `0,5,10…` marks, so the
     run does not land in the same second as every other scraper polling HoYoLAB and the nitter
     mirrors. (A private repo should use `0,30`; see [Minutes and private
     repositories](#minutes-and-private-repositories).)
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
| `Game-Express alpha` | alpha (primary) | minutes `2,7,12,17,22,27,32,37,42,47,52,57` | `INSTANCE_NAME=alpha`, `HEARTBEAT_MINUTES=60`, `PEER_STATE_URL=<bravo raw state URL>` |
| `Game-Express bravo` | bravo (standby) | the same minutes **+2** (`4,9,14,…`) | `INSTANCE_NAME=bravo`, `INSTANCE_ROLE=standby`, `PEER_STATE_URL=<alpha raw state URL>`, `FAILOVER_AFTER_MINUTES=150` |

The raw state URL looks like this:
`https://raw.githubusercontent.com/<OWNER>/<REPO>/main/state/state.json` (public repos only).

- **bravo stays passive while alpha is healthy.** It only imports alpha's posted keys.
- **bravo takes over** once alpha's heartbeat is older than `FAILOVER_AFTER_MINUTES`.
  - This happens if alpha's cron job is paused, its token expired, or its Actions are down.
  - bravo never takes over if it can't read alpha's state, so a typo can't cause double posts.
- The offset means the two repos never hit the same upstream in the same second, and during a
  fail-over the standby keeps the same 5-minute rhythm.

---

## Step 3: check it's running

- **cron-job.org → the job → History**: a row every 5 minutes with **204**.
- **GitHub → instance repo → Actions → Game-Express Monitor**: a green run every 5 minutes.
  - Open one run and read the **Summary**.
  - A normal quiet run says "nothing new" and lists source health, such as
    `hoyolab: 9 ok / 0 fail`.
- **Commits**: `auto: update state [skip ci]` appears only when something changed, plus a
  heartbeat about once an hour on alpha. Most runs commit nothing.
- **The first live run is a silent seed.** It records the current announcements and all existing
  codes without posting. After that, only new things are posted.

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
A trigger that arrives while a run is still going waits, and then checks out the newest state.
Nothing is posted twice and nothing is cancelled halfway.

## How fast can it poll?

Nothing in Game-Express is tied to a particular interval — no code or config change is needed to
go faster. The limits are these, with the numbers measured on real runs (2026-10-02/03):

| What | Measured | Head-room at 5 min |
|---|---|---|
| **Run duration, end to end** | **19–36 s** (median ~25 s: ~15 s runner setup + install, ~5–6 s of actual work) | a run occupies **~8 %** of a 5-minute slot |
| **Overlap** | impossible by construction: the `concurrency` group is `cancel-in-progress: false`, so a trigger that arrives mid-run queues and then checks out the newest state | safe at any interval ≥ 1 min |
| **GitHub Actions minutes** | public repo = **free and unlimited** | no cost |
| **`workflow_dispatch` API calls** | 12/hour at 5 min, against a 5,000/hour token limit | 0.2 % of the limit |
| **Upstream requests per run** | ~55–60 (HoYoLAB ×9, code APIs ×20, nitter ×~24 for six X accounts, plus Kuro / launcher / banner feed) | ≈ 17 k/day at 5 min, vs 8 k/day at 10 min |

**The only real constraint is upstream politeness, not GitHub.** HoYoLAB's API is unofficial, and
the nitter mirrors, `hoyo-codes.seria.moe`, `api.ennead.cc`, `feeds.c3kay.de` and `wuthering.gg`
are volunteer-run. Doubling the poll rate doubles the load you put on them, and a 429 or an IP
ban makes the monitor **slower**, not faster, because the source goes dark for hours.

| Interval | Average time to notice something new | Requests/day | Verdict |
|---|---|---|---|
| 10 min (previous) | ~5.4 min | ~8 k | safe, but slower than it needs to be |
| **5 min** | **~2.9 min** | ~17 k | ✅ **recommended** — the sweet spot |
| 3 min | ~1.9 min | ~28 k | acceptable *if* you watch the `sources:` line in the run summary for `429` / `TimeoutError` and back off when they appear |
| 2 min | ~1.4 min | ~41 k | not recommended: ~1 min of extra speed for 2.4× the upstream load |
| 1 min | ~0.9 min | ~83 k | ❌ no: 1,440 runs/day, near-certain rate-limiting of the community mirrors, and cron-job.org's free tier throttles |

Below ~5 minutes the gain shrinks fast (each halving buys progressively less, because a fixed
~25 s of runner setup and the announcement's own propagation delay dominate), while the load
grows linearly. **5 minutes is the recommended setting; 3 minutes is the floor worth defending.**

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
