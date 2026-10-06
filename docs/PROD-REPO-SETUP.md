# Splitting Game-Express into a private dev repo + an obscure public prod repo

Target shape:

| Repo | Visibility | Runs the monitor? | Holds |
|---|---|---|---|
| `uesu/Game-Express` | **private** | no (kill-switched) | everything: code, tests, docs, CI, Dependabot |
| `uesu/<random-name>` | **public** | **yes**, every 5 min | 34 runtime files + state |

---

## The family model this follows

After the split, **`Game-Express` stops being a bot and becomes a development repository** —
the place changes are written, reviewed and tested. It never posts again. That is exactly the
arrangement `News-Express` already has: development lives in the named repo, and the live bots
run from separate obscure production repos (currently two of them, for Twitter and for Reddit).

What that means in practice:

| | development repo | production repo |
|---|---|---|
| name | `Game-Express` — public today, **private** after the split | random, unguessable, **public** |
| posts to Discord | never (`ENABLED_FEATURES=none` + no webhooks) | yes, every 5 minutes |
| holds | code, tests, `docs/`, `README.md`, CI, Dependabot, this guide | the package, three config files, state, one workflow |
| Markdown in it | the whole manual | **none required** — see §1 |
| pull requests | all of them | none; it only receives syncs |

So treat anything below that mentions `docs/`, `README.md` or `tests/` as **development-repo
only**. The production repo is deliberately documentation-free: it is not read by people, it is
executed by a runner.

---

## 0. Read this before anything else: the prod repo must be PUBLIC

This is not a style preference, it is billing.

- **Public repos: GitHub Actions is free and unlimited.**
- **Private repos: billed per minute, rounded UP to a whole minute per job.**

A whole monitor job takes about 15 s end to end (measured 2026-10-05: 15 s of job, 5.5 s of
actual run), so every dispatch still costs **1 billed minute**. At a 5-minute
cadence that is 288 runs/day ≈ **8,640 minutes/month**, against 2,000 free on the Free plan
(3,000 on Pro). A private prod repo stops running about six days into every month.

So: random unguessable name + public = free unlimited Actions, and the obscurity is the
privacy. The *dev* repo going private is free — CI only runs on pull requests, a few minutes
a week.

Nothing sensitive ends up in the public repo. Webhook URLs live in repository **secrets**
(never in files), and `state/state.json` was checked: it holds payload hashes and Discord
**message IDs** only — no webhook URLs, no tokens. Message IDs are not secrets.

---

## 0b. Before you start: `main` must be green and current

Everything this guide describes is already on `main`. There is no pending stack to land first and
no scratch patch to apply — earlier revisions of this guide told you to merge PR #26 and to apply
`game-express-speculation.patch`; both landed long ago and neither file exists any more. Confirm
the tree is green in a clean checkout of `main`:

```bash
python -m compileall -q gamexpress tests
python -m gamexpress validate
python tests/test_smoke.py
python -m gamexpress preview --out /tmp/previews
ruff check .
```

**Do the dev repo first, then prod.** Copying an unmerged working tree straight into prod means
prod runs code that `main` has never seen, and the next dev→prod sync (§8) silently reverts it.

### A new session on the prod repo

Create the empty public prod repo on GitHub first, then open a second session pointed at it with:

> This repo is the production deployment of the public repo `uesu/Game-Express`. Clone
> `https://github.com/uesu/Game-Express` into a temp folder, copy in ONLY the runtime manifest
> from its `docs/PROD-REPO-SETUP.md` §1 (the `gamexpress/` package, `config/games.json`,
> `config/overrides.json`, `config/program_announcements.json`, `state/.gitkeep`,
> `state/state.json`, `requirements.txt`, `.gitignore`, `.github/workflows/monitor.yml`,
> `PRIVACY_POLICY.md`, `TERMS_OF_SERVICE.md`), write the 3-line prod README from §2, then open a
> pull request. Do not copy `tests/`, `docs/`, `ci.yml`, `ruff.toml`, `AGENTS.md`, `README.md`,
> or any `APPLY-*` scratch file.

That session can reach GitHub, so it can push and open the PR for you. **Nothing in this flow
touches the Game-Express working tree** — step 2 only reads a clone of it.

Then come back here for §3 (secrets), §4 (state), §6 (cutover order) and §9 (rollback), which are
still manual: an agent cannot set your repository secrets or your cron-job.org schedule.

---

> **The schedule fan-out DOES change this guide.** It adds up to six new secrets — see §3 — and
> they are already live on dev. Everything else that landed recently (timestamp speculation, the
> card layout pass) adds no file, no secret and no variable: the per-game rhythm lives inside
> `config/games.json`, which is already on the copy list, and the read-only
> `python -m gamexpress speculate` command works in prod as soon as the files are there.

## 1. The file manifest — exactly 34 files

### Copy to prod (runtime)

```
gamexpress/                      26 .py files — the whole package
  __init__.py  __main__.py  cards.py  codeposter.py  config.py  discord.py
  http.py  media.py  models.py  preview_html.py  runner.py  samples.py
  schedule.py  state.py  textutil.py  timeparse.py
  sources/__init__.py  bannerfeed.py  codes.py  countdown.py  gachawiki.py
          hoyolab.py  kuro.py  launcher.py  newspage.py  twitter.py
config/games.json                game definitions, X accounts, code sources
config/overrides.json            manual corrections
config/program_announcements.json  discovered tweet ids — the workflow commits to this
state/.gitkeep
state/state.json                 what has been posted (see §4 — copy it, do not start empty)
requirements.txt
.github/workflows/monitor.yml    the only workflow prod needs
.gitignore
```

### Optionally copy: the weekly Python bump

```
.github/workflows/python_version_bump.yml
.github/scripts/python_version_bump.py
```

**Why you may want this in prod.** Prod's `monitor.yml` pins `python-version: '3.14'`. Nothing
else updates it. If you sync from dev regularly the pin rides along with `monitor.yml` and you
can skip this — but if dev goes quiet for a few months, prod keeps running an ageing
interpreter with no one telling it.

**It is safe to run in a documentation-free repo.** The script writes to exactly three
filenames — `ci.yml`, `monitor.yml`, `ruff.toml` — and skips every one it cannot find, so in a
prod repo it rewrites `monitor.yml` and nothing else. It reads the current pin from whichever
workflow is present. **It never opens a Markdown file for writing**, so there is no README and
no `docs/` for it to invent or corrupt; the PR body it composes is written to the runner's temp
directory, not into the repo. The set of files staged in the PR is whatever the script reports
having rewritten, not a hard-coded list, which is why the same workflow file works in both
repos with no prod-only edit. `tests/test_smoke.py` asserts all of this against a simulated
prod repo on every CI run.

Two consequences if you do copy it:

- It needs its own **`BUMP_PAT`** secret in the prod repo (§3) — the built-in token may not
  write under `.github/workflows/`.
- Leave `AUTO_MERGE_PYTHON_BUMP` **unset** in prod. A new Python series reaching the live bot
  unreviewed is the one thing this whole split exists to prevent. The PR will sit and wait.

If you skip it, delete nothing else — just don't copy these two files, and rely on §8 syncs to
carry the pin.

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
tests/                     the suite, fixtures, golden cards (grows every release —
                           deliberately not counted here)
docs/                      the whole manual: README (index), CONFIGURATION, ACCURACY,
                           SOURCES, BANNER_DATABASE, SCHEDULER, ROLLOUT, TESTING,
                           TROUBLESHOOTING, SECURITY, TIMESTAMP-PATTERNS, DEPENDABOT,
                           PYTHON_VERSION, CREDITS, PROD-REPO-SETUP and changelog/
                           (this guide lives in docs/ too — it describes the move,
                           it is not part of what moves)
.github/workflows/ci.yml           PRs happen in dev
.github/dependabot.yml             prod receives syncs, it does not raise PRs
ruff.toml                          lint config; prod never lints
README.md                  write a 3-line prod README instead (see §2)
.env.example
APPLY-*.md  APPLY-*.sh         hand-off scratch files for a pull-request session
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
find /tmp/prod -type f | wc -l     # expect 36 (34 runtime + 2 policy files)
                                  # 38 if you also copied the two python-bump files
```

**Don't trust that number on its own — verify the package instead.** The count goes stale the
day a new module is added (`sources/gachawiki.py` was exactly that), and a missing module is not
a quiet problem: prod imports it on the first run and the monitor dies. This check keeps working
no matter how many files the package grows to:

```bash
diff <(cd /path/to/Game-Express && find gamexpress -name '*.py' -not -path '*__pycache__*' | sort) \
     <(cd /tmp/prod          && find gamexpress -name '*.py' -not -path '*__pycache__*' | sort) \
  && echo "package complete"
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
| `DISCORD_WEBHOOK_SCHEDULE_MIRROR_GI` | **set on dev** | fan-out: the schedule card is **copied** to `#gi-news` as well |
| `DISCORD_WEBHOOK_SCHEDULE_MIRROR_HSR` | **set on dev** | |
| `DISCORD_WEBHOOK_SCHEDULE_MIRROR_ZZZ` | **set on dev** | |
| `DISCORD_WEBHOOK_SCHEDULE_MIRROR_WUWA` | **set on dev** | |
| `DISCORD_WEBHOOK_SCHEDULE_MIRROR_HNA` | **set on dev** | |
| `DISCORD_WEBHOOK_SCHEDULE_MIRROR_ANANTA` | **set on dev** | |
| `NITTER_RSS_TOKEN` | optional | only unlocks `nitter.miningtcup.me`. Useful, not required: the 2026-10-06 audit had 8 mirrors answering and the fleet merges the first **two** of them, so the token adds a proven answerer rather than supplying one you cannot do without |
| `BUMP_PAT` | yes, if you keep `python_version_bump.yml` | a PAT with **Workflows: read and write**. Without it the weekly bump validates fine and then fails on the push — see below |
| `DISCORD_WEBHOOK_CODES` | optional | catch-all for games without their own channel |
| `DISCORD_WEBHOOK_URL` | optional | global catch-all |

**`BUMP_PAT` is per-repository and easy to forget.** The Python bump workflow rewrites
`python-version:` inside `.github/workflows/`, and the built-in `GITHUB_TOKEN` is never allowed
to push a file under that directory — so a brand-new repo gets a weekly red run that says
`refusing to allow a GitHub App to create or update workflow … without workflows permission`,
even though every test passed. One PAT can cover all your repositories, but **the secret itself
must be created separately in each one**. Full permission list and reasoning:
[`PYTHON_VERSION.md`](PYTHON_VERSION.md#one-time-setup-this-needs).

**The six `_MIRROR_` secrets are what makes each game's schedule card also land in that game's
own news channel**, while `#schedule` keeps receiving everything. Omit them in prod and you get
the old single-channel behaviour with no code change; copy them and prod matches dev. Read
[`ROLLOUT.md`](ROLLOUT.md) before adding them — **the first run after adding one back-fills
every live card for that game**, so add them one game at a time rather than all six at once.

Two names to avoid: `DISCORD_WEBHOOK_SCHEDULE_<GAME>` *moves* that game out of `#schedule`
instead of copying it, and `DISCORD_WEBHOOK_SCHEDULE_MIRROR` with no game suffix mirrors **every**
game into one channel.

`github_token` appears in the logs' `GE_SECRETS_JSON` blob — that is GitHub's automatic token,
not something you create.

### Variables (same page → Variables)

| Variable | Prod value | Notes |
|---|---|---|
| `PING_SCHEDULE` | `<@&…>` | dev currently pings a real role. Copy the same value to keep behaviour identical, or set `none` for a silent prod |
| `ENABLED_FEATURES` | **do not set** | default is `schedule,codes`. Setting it to `none` is the kill switch — never on prod |
| `AUTO_MERGE_DEPENDABOT` | **do not copy** | dev-only, there is no Dependabot in prod |
| `AUTO_MERGE_PYTHON_BUMP` | **do not copy** | dev-only |

⚠️ `PING_SCHEDULE` is resolved first-set-wins (`PING_<FEATURE>_<GAME>` → `PING_<FEATURE>` →
`PING_ROLE_ID`), and the literal string `none` **counts as set** — it will beat a correct
`PING_ROLE_ID` sitting next to it. Set the one variable you mean; do not stack them.

Only `#schedule` is ever pinged. The game-channel copies are deliberately silent, so a role ID
here does not multiply the notification across six more channels.

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
     misnamed **primary** secret shows up here. Never writes state.
     ⚠️ **This does not test the `_MIRROR_` secrets** — `check-webhooks` only walks the primary
     `webhook_source()` chain. To verify the fan-out, read the `Show resolved config` step of
     any run instead: each game must show `🪞 also DISCORD_WEBHOOK_SCHEDULE_MIRROR_<GAME>`. A
     misspelled name shows no `🪞` at all, a channel link instead of a webhook URL shows
     `✗ … is not a webhook URL`, and pasting the `#schedule` URL shows
     `⚠ … is the same channel as DISCORD_WEBHOOK_SCHEDULE — no copy sent`.
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
`gamexpress/http.py`:

```python
BOT_UA = "Game-Express (+https://github.com/uesu/Game-Express)"
```

(There is deliberately no version in it — a bare product token is valid and can never go stale.
The same name also appears in `sources/codes.py` (`Game-Express (code monitor)`) and
`sources/twitter.py` (`X_UA`); change all three together or none.)

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

### Check the Python pin before you push the sync

That `cp … monitor.yml` overwrites prod's workflow with dev's, **including its
`python-version:` line**. Once prod becomes the repo that posts, two things make that
dangerous:

1. **GitHub disables a scheduled workflow after 60 days of repository inactivity.** A dev repo
   that nobody has pushed to all quarter stops running its weekly bump, so dev's pin freezes
   while prod's — if you copied the bump into prod — keeps moving.
2. A blind sync then **silently downgrades production's interpreter**, and nothing fails: an
   older pin still installs, still passes, still posts. You would only notice months later.

One line, before `git add`:

```bash
diff <(grep -m1 "python-version:" /path/to/Game-Express/.github/workflows/monitor.yml) \
     <(git show HEAD:.github/workflows/monitor.yml | grep -m1 "python-version:") \
  && echo "pin unchanged — safe to sync"
```

If it prints a difference, read which way it goes. Dev **ahead** of prod is a normal upgrade:
push it. Dev **behind** prod means dev went dormant — restore prod's line before committing, or
drop `monitor.yml` from the sync entirely and copy only `gamexpress/` and the config files.

A dormant dev repo is worth fixing at the source: open Actions in the dev repo and re-enable
any workflow GitHub has greyed out, or push any commit to reset the 60-day clock.

Tag the dev commit you shipped (`git tag prod-$(date +%F)`, then push the tag) so "what is
running right now" is always answerable.

---

## 9. Rollback

Everything is reversible in two moves: pause the prod cron job, remove
`ENABLED_FEATURES=none` from dev, repoint the cron URL at `Game-Express`. Copy
`state/state.json` back from prod first, or dev will re-seed and you'll lose edit-ability on
the cards prod posted.
