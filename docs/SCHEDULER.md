# Scheduler: cron-job.org → GitHub Actions (every 10 minutes)

Game-Express uses the same setup as News-Express. [cron-job.org](https://cron-job.org) (free) calls
GitHub's **workflow_dispatch API** every 10 minutes, and each call starts one
**Game-Express Monitor** run.

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
   - **Execution schedule**: **Every 10 minutes**. On the custom schedule, select minutes
     `0,10,20,30,40,50` of every hour.
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
   silently stopping the bot.
5. **Save**, open the job, and click **TEST RUN** (or *Perform test run*).

**Expected result:** **`204 No Content`**. Within a few seconds, the instance repo's **Actions** tab
shows a *Game-Express Monitor* run labelled *"Manually run by \<you\>"*.

### Two instances (fail-over)

Create **one job per instance repo**, and never one for a development copy (a repo that must
never post). Such a copy has the variable `ENABLED_FEATURES=none`, so even an accidental trigger
is skipped there.

| Job | URL repo | Schedule | Repo variables |
|---|---|---|---|
| `Game-Express alpha` | alpha (primary) | minutes `0,10,20,30,40,50` | `INSTANCE_NAME=alpha`, `HEARTBEAT_MINUTES=60`, `PEER_STATE_URL=<bravo raw state URL>` |
| `Game-Express bravo` | bravo (standby) | minutes `5,15,25,35,45,55` (offset by 5) | `INSTANCE_NAME=bravo`, `INSTANCE_ROLE=standby`, `PEER_STATE_URL=<alpha raw state URL>`, `FAILOVER_AFTER_MINUTES=150` |

The raw state URL looks like this:
`https://raw.githubusercontent.com/<OWNER>/<REPO>/main/state/state.json` (public repos only).

- **bravo stays passive while alpha is healthy.** It only imports alpha's posted keys.
- **bravo takes over** once alpha's heartbeat is older than `FAILOVER_AFTER_MINUTES`.
  - This happens if alpha's cron job is paused, its token expired, or its Actions are down.
  - bravo never takes over if it can't read alpha's state, so a typo can't cause double posts.
- The 5-minute offset means one of the two repos checks for news every 5 minutes during a
  fail-over.

---

## Step 3: check it's running

- **cron-job.org → the job → History**: a row every 10 minutes with **204**.
- **GitHub → instance repo → Actions → Game-Express Monitor**: a green run every 10 minutes.
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

## Minutes and private repositories

**Public repositories** get unlimited free GitHub Actions minutes, so every 10 minutes costs
nothing.

**Private repositories** on GitHub Free include **2,000 minutes a month**. Every run counts as
at least one full minute, although a Game-Express run takes only about 20–60 s.

| cron-job.org schedule | Runs a month | Private repo |
|---|---|---|
| every 10 minutes | about 4,320 | ❌ over the limit: Actions stops for the rest of the month (around day 14) |
| every 30 minutes (minutes `0,30`) | about 1,440 | ✅ fits, with room left for CI and the monitor's test bench |

So a private repo should run **every 30 minutes**. Livestream codes usually stay valid for about
a day, so that is still fast enough. The classic token's `repo` scope already covers private
repos. Your account's **Billing** page shows the minutes used.
