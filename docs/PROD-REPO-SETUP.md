# Splitting Game-Express into a private dev repo + an obscure public prod repo

Target shape:

| Repo | Visibility | Runs the monitor? | Holds |
|---|---|---|---|
| `uesu/Game-Express` | **private** | no (kill-switched) | everything: code, tests, docs, CI, Dependabot |
| `uesu/<random-name>` | **public** | **yes**, every 5 min | 33 runtime files + state |

---

## 0. Read this before anything else: the prod repo must be PUBLIC

This is not a style preference, it is billing.

- **Public repos: GitHub Actions is free and unlimited.**
- **Private repos: billed per minute, rounded UP to a whole minute per job.**

The monitor run takes ~20 s, so every dispatch costs **1 billed minute**. At a 5-minute
cadence that is 288 runs/day ≈ **8,640 minutes/month**, against 2,000 free on the Free plan
(3,000 on Pro). A private prod repo stops running about six days into every month.

So: random unguessable name + public = free unlimited Actions, and the obscurity is the
privacy. The *dev* repo going private is free — CI only runs on pull requests, a few minutes
a week.

Nothing sensitive ends up in the public repo. Webhook URLs live in repository **secrets**
(never in files), and `state/state.json` was checked: it holds payload hashes and Discord
**message IDs** only — no webhook URLs, no tokens. Message IDs are not secrets.

---

## 0b. The dev repo has unmerged work — merge that first

`main` on GitHub does **not** yet contain everything described here. Two stacks sat outside it,
and they overlap in `gamexpress/config.py` and `tests/test_smoke.py`, so they could not be
separated file-by-file:

| stack | files |
|---|---|
| nitter source notes | `docs/SOURCES.md`, part of `gamexpress/config.py`, part of `tests/test_smoke.py` |
| timestamp speculation | `config/games.json`, `gamexpress/schedule.py`, `gamexpress/__main__.py`, rest of `config.py`, rest of `test_smoke.py`, `docs/SCHEDULER.md`, `docs/TIMESTAMP-PATTERNS.md`, `docs/ACCURACY.md`, `README.md`, `docs/TESTING.md` |

They ship together: **PR #26 on `uesu/Game-Express` is the superset of both stacks**, so merging
that one PR completes `main` — nothing else needs applying. (Both stacks were also captured as
`game-express-speculation.patch`, a scratch patch that is deliberately **not** committed; PR #26's
diff is byte-identical to it, and the patch file exists only as a recovery path if a checkout
ever loses the branch — the sandbox's git history reset twice during development. Use one route
or the other, never both.)

It was verified by checking out a pristine `origin/main` into a scratch worktree, applying the
patch, and running the full gate on the result: compileall, `validate`, **the whole test suite**,
preview render and `ruff` all pass. PR #26 carries exactly that tree and is green on the same
gate plus GitHub's own CI.

**Do the dev repo first, then prod.** Copying an unmerged working tree straight into prod means
prod runs code that `main` has never seen, and the next dev→prod sync (§8) silently reverts it.

### Step 1 — on Game-Express: merge PR #26

One click on GitHub; no session is needed. `main` is then complete. If the PR ever had to be
rebuilt from the patch instead, a new coding session pointed at `uesu/Game-Express` would get:

> Apply `game-express-speculation.patch` from the repo root onto a fresh branch, run the full CI
> gate (`python -m compileall -q gamexpress tests`, `python -m gamexpress validate`,
> `python tests/test_smoke.py`, `python -m gamexpress preview --out /tmp/previews`,
> `ruff check gamexpress/ tests/`), confirm the whole suite passes, then push the branch and open a
> pull request.

Either way, land **one** of them — the PR is the patch, so doing both double-applies.

### Step 2 — a new session on the prod repo

Create the empty public prod repo on GitHub first, then open a second session pointed at it with:

> This repo is the production deployment of the public repo `uesu/Game-Express`. Clone
> `https://github.com/uesu/Game-Express` into a temp folder, copy in ONLY the runtime manifest
> from its `docs/PROD-REPO-SETUP.md` §1 (the `gamexpress/` package, `config/games.json`,
> `config/overrides.json`, `config/program_announcements.json`, `state/.gitkeep`,
> `state/state.json`, `requirements.txt`, `.gitignore`, `.github/workflows/monitor.yml`,
> `PRIVACY_POLICY.md`, `TERMS_OF_SERVICE.md`), write the 3-line prod README from §2, then open a
> pull request. Do not copy `tests/`, `docs/`, `ci.yml`, `ruff.toml`, `AGENTS.md`, `README.md`,
> or any `PR-*` / `*.patch` scratch file.

That session can reach GitHub, so it can push and open the PR for you. **Nothing in this flow
touches the Game-Express working tree** — step 2 only reads a clone of it.

Then come back here for §3 (secrets), §4 (state), §6 (cutover order) and §9 (rollback), which are
still manual: an agent cannot set your repository secrets or your cron-job.org schedule.

---

> **Nothing in this guide changed when the timestamp speculation feature landed.** It adds no
> new file, no new secret and no new variable — the per-game rhythm lives inside
> `config/games.json`, which is already on the copy list. The read-only
> `python -m gamexpress speculate` command works in prod as soon as the files are there.

## 1. The file manifest — exactly 33 files

### Copy to prod (runtime)

```
gamexpress/                      24 .py files — the whole package
  __init__.py  __main__.py  cards.py  codeposter.py  config.py  discord.py
  http.py  media.py  models.py  preview_html.py  runner.py  samples.py
  schedule.py  state.py  textutil.py  timeparse.py
  sources/__init__.py  bannerfeed.py  codes.py  countdown.py  hoyolab.py
          kuro.py  launcher.py  newspage.py  twitter.py
config/games.json                game definitions, X accounts, code sources
config/overrides.json            manual corrections
config/program_announcements.json  discovered tweet ids — the workflow commits to this
state/.gitkeep
state/state.json                 what has been posted (see §4 — copy it, do not start empty)
requirements.txt
.github/workflows/monitor.yml    the only workflow prod needs
.gitignore
```

### Also copy (public-facing, not runtime)

```
PRIVACY_POLICY.md
TERMS_OF_SERVICE.md
```

**Why:** if your Discord developer portal links to
`github.com/uesu/Game-Express/blob/main/PRIVACY_POLICY.md`, those links **404 the moment the
repo goes private**. Either move them to the public repo and update the two links in the
Discord portal, or publish them somewhere else (Gist, site). Don't leave them dangling.

### Leave behind (dev only)

```
tests/                     38 files — the suite, fixtures, golden cards
docs/                      the whole manual: CONFIGURATION, ACCURACY, SOURCES, SCHEDULER,
                           TESTING, TROUBLESHOOTING, SECURITY, TIMESTAMP-PATTERNS,
                           DEPENDABOT, PYTHON_VERSION, CREDITS, PROD-REPO-SETUP and
                           changelog/  (this guide lives in docs/ too — it describes
                           the move, it is not part of what gets moved)
.github/workflows/ci.yml           PRs happen in dev
.github/workflows/python_version_bump.yml
.github/scripts/python_version_bump.py
.github/dependabot.yml
ruff.toml
README.md                  write a 3-line prod README instead (see §2)
.env.example
PR-*.md  PR-*.txt  *.patch  PULL-REQUEST.md   scratch files
game-express-speculation.patch     carried the feature into dev; prod never needs it
AGENTS.md
```

### The copy command

Run from a clean checkout of dev `main`:

```bash
cd /path/to/Game-Express
git checkout main && git pull

mkdir -p /tmp/prod && cd /tmp/prod && rm -rf ./* .github 2>/dev/null
cd /path/to/Game-Express
cp -r --parents \
  gamexpress \
  config/games.json config/overrides.json config/program_announcements.json \
  state/.gitkeep state/state.json \
  requirements.txt .gitignore \
  .github/workflows/monitor.yml \
  PRIVACY_POLICY.md TERMS_OF_SERVICE.md \
  /tmp/prod/

find /tmp/prod -name '__pycache__' -type d -exec rm -rf {} + 2>/dev/null
find /tmp/prod -type f | wc -l     # expect 35 (33 runtime + 2 policy files)
```

---

## 2. Create the prod repo

```bash
cd /tmp/prod
git init -b main
gh repo create uesu/<random-name> --public --source=. --remote=origin \
  --description "automation" --disable-wiki
printf '%s\n' '# automation' > README.md    # keep it boring and uninformative
git add -A && git commit -m "init" && git push -u origin main
```

Then **Settings → Actions → General**:

| Setting | Value | Why |
|---|---|---|
| Actions permissions | Allow all actions | the workflow pins 3 third-party actions by SHA |
| **Workflow permissions** | **Read and write** | **mandatory** — the last step pushes `state/state.json` back. New repos default to read-only and the push fails with 403 |
| Allow Actions to create/approve PRs | off | not needed in prod |

Also **Settings → General → Features**: turn off Issues, Projects, Wiki. Less surface, less
to look at.

---

## 3. Secrets and variables

### Secrets (Settings → Secrets and variables → Actions → Secrets)

Copy the **values** from the dev repo — GitHub never shows them again, so pull them from your
password manager or re-copy each webhook from Discord (Channel → Edit → Integrations →
Webhooks).

| Secret | Required | Notes |
|---|---|---|
| `DISCORD_WEBHOOK_SCHEDULE` | yes | version/program cards |
| `DISCORD_WEBHOOK_CODES_GENSHIN` | yes | |
| `DISCORD_WEBHOOK_CODES_STARRAIL` | yes | |
| `DISCORD_WEBHOOK_CODES_ZZZ` | yes | |
| `DISCORD_WEBHOOK_CODES_WUWA` | yes | |
| `DISCORD_WEBHOOK_CODES_HNA` | yes | |
| `DISCORD_WEBHOOK_CODES_ANANTA` | yes | |
| `NITTER_RSS_TOKEN` | optional | only unlocks `nitter.miningtcup.me` — but that mirror is **1 of your 2 proven answerers**, so treat it as required |
| `DISCORD_WEBHOOK_CODES` | optional | catch-all for games without their own channel |
| `DISCORD_WEBHOOK_URL` | optional | global catch-all |

`github_token` appears in the logs' `GE_SECRETS_JSON` blob — that is GitHub's automatic token,
not something you create.

### Variables (same page → Variables)

| Variable | Prod value | Notes |
|---|---|---|
| `PING_SCHEDULE` | `none` | current dev value; change if you want a role pinged |
| `ENABLED_FEATURES` | **do not set** | default is `schedule,codes`. Setting it to `none` is the kill switch — never on prod |
| `AUTO_MERGE_DEPENDABOT` | **do not copy** | dev-only, there is no Dependabot in prod |
| `AUTO_MERGE_PYTHON_BUMP` | **do not copy** | dev-only |

Emojis need no variables — `EMOJI_YOUTUBE` / `EMOJI_TWITCH` fall back to the defaults baked
into `gamexpress/config.py`, which is where your current values already live.

---

## 4. The state file is the thing that prevents a re-post storm

`state/state.json` is what makes the monitor idempotent: every posted card is recorded by key
**and** by a hash of its payload.

- **Copy it.** Carrying it over means prod continues exactly where dev stopped — and because
  the stored Discord message IDs come with it, `EDIT_ON_UPDATE` can still silently edit cards
  that the *old* repo posted. Same webhooks, same messages.
- Starting empty would not spam (the first run silently seeds, it does not post history), but
  you would lose the ability to edit existing cards, and the seed boundary could swallow an
  announcement that was mid-flight.
- Copy it **after** pausing the scheduler (§6), so it cannot go stale between copy and cutover.

`config/program_announcements.json` matters for the same reason — it holds discovered tweet
IDs so a card can be re-rendered later, after the nitter timeline has rolled past it.

---

## 5. Kill the dev repo's ability to post

In the **dev** repo: Settings → Secrets and variables → Actions → Variables →

```
ENABLED_FEATURES = none
```

`monitor.yml` gates the whole job on `vars.ENABLED_FEATURES != 'none' || inputs.mode == 'test'`,
so every live run is skipped even if something triggers it by accident — while `mode=test`
runs still work, which is exactly what you want in dev.

Do this **before** the first prod live run. Two repos posting from the same webhooks would
double-post; they do not share state.

You can also delete the webhook secrets from dev, but then `mode=test` stops working there.
The variable is the better switch.

---

## 6. Cutover order (no double post, no missed announcement)

1. **Pause the cron-job.org job** that points at `Game-Express`. The monitor is now stopped.
2. **Copy the freshest state**: `git pull` dev `main`, then run the §1 copy command.
3. **Create the prod repo** (§2), push, set Actions permissions.
4. **Add secrets + variables** (§3).
5. **Dev repo**: set `ENABLED_FEATURES=none` (§5), then flip it to **private**.
6. **Prod smoke tests** — Actions → Game-Express Monitor → Run workflow:
   - `mode=test`, `test=webhooks` → one "✅ connected" card per channel. Any missing or
     misnamed secret shows up here. Never writes state.
   - `mode=test`, `test=schedule` → the real current card with real art and timestamps.
   - Delete the 🧪 TEST cards afterwards.
7. **First live run**: `mode=live`, `only=all`. Expect "nothing new" plus either a state commit
   or `state unchanged — nothing to commit`. Both are correct.
8. **cron-job.org**: create the new job (or edit the old one):
   - URL `https://api.github.com/repos/uesu/<random-name>/actions/workflows/monitor.yml/dispatches`
   - headers and body exactly as in `docs/SCHEDULER.md`
   - the token: a **fine-grained PAT scoped to the one prod repo** with *Actions: Read and
     write* is tighter than the classic `repo` token and works for dispatch. Classic `repo`
     also works if you'd rather reuse the existing one.
   - Resume. Watch for **204** in the job History.
9. **Delete or leave paused** the old cron job. Never let both run.

A gap of a few minutes during cutover is harmless: `LOOKBACK_HOURS=72` means the first prod
run still sees anything announced in the last three days.

---

## 7. Gotchas specific to this split

**The bot's User-Agent points at a repo that will 404.**
`gamexpress/http.py:16`:

```python
BOT_UA = "Game-Express/1.1 (+https://github.com/uesu/Game-Express)"
```

Once dev is private, every site you fetch sees a dead link. Two options — pick one and change
it in **dev** so both repos stay in sync:

- point it at a neutral contact you don't mind publishing (a Discord invite), **or**
- point it at the new public repo — but that leaks the "random" name in an HTTP header to
  every site the monitor touches, which defeats the obscurity.

I'd use the Discord invite.

**`PEER_STATE_URL` two-instance failover stops working against a private repo.** It fetches
`raw.githubusercontent.com/...` unauthenticated. If you ever want dev as a standby, both
instance repos have to be public.

**No CI in prod.** Nothing validates a bad edit there. Treat prod as deploy-only: never hand-edit
it, always change dev → green CI → sync.

**The state commit is `[skip ci]`** and `ci.yml` isn't in prod anyway, so the auto-commits
cost nothing.

**`concurrency: cancel-in-progress: false`** must stay false — a run can sit between "posted to
Discord" and "state committed", and cancelling there allows a re-post.

---

## 8. Keeping prod in sync afterwards

Prod will drift from dev by one file: the workflow keeps committing `state/state.json` and
`config/program_announcements.json`. So sync code **into** prod, never the reverse.

```bash
# in dev, on green main
cd /path/to/Game-Express && git checkout main && git pull

git clone https://github.com/uesu/<random-name>.git /tmp/prodsync
cd /tmp/prodsync
rm -rf gamexpress .github/workflows/monitor.yml
cp -r /path/to/Game-Express/gamexpress .
cp /path/to/Game-Express/config/games.json config/
cp /path/to/Game-Express/config/overrides.json config/
cp /path/to/Game-Express/requirements.txt .
mkdir -p .github/workflows && cp /path/to/Game-Express/.github/workflows/monitor.yml .github/workflows/
find . -name '__pycache__' -type d -exec rm -rf {} + 2>/dev/null

git add -A && git diff --cached --stat        # review before pushing
git commit -m "sync: <dev commit sha>" && git push
```

Note it **never** copies `state/state.json` or `config/program_announcements.json` — those
belong to prod now.

Tag the dev commit you shipped (`git tag prod-2026-10-03 && git push --tags`) so "what is
running right now" is always answerable.

---

## 9. Rollback

Everything is reversible in two moves: pause the prod cron job, remove
`ENABLED_FEATURES=none` from dev, repoint the cron URL at `Game-Express`. Copy
`state/state.json` back from prod first, or dev will re-seed and you'll lose edit-ability on
the cards prod posted.
