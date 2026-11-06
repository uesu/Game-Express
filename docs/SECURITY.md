# Security & resilience

What this repository is defending, from what, and which code does the defending. Nothing here
is theoretical hardening for its own sake — each guard exists because a specific thing can
actually go wrong with *this* monitor, and each one is pinned by a test so a later refactor
cannot quietly remove it.

Personal repository, no user accounts, no inbound traffic: there is no web service to attack.
The entire attack surface is **(a) what the monitor reads** and **(b) what GitHub Actions is
allowed to do**.

---

## 1. Threat model

| # | What could go wrong | Realistic? | Handled by |
|---|---|---|---|
| T1 | A community source (nitter mirror, Redlib mirror, Reddit proxy, wiki, code API) is taken over and feeds the bot a hostile payload | Yes — 27 nitter mirrors, 27 Reddit/Redlib entries and 3 proxies include community-operated hosts | §2 |
| T2 | A source floods the bot with hundreds of fake "codes" | Yes — a parser change upstream is enough | §3 |
| T3 | A webhook URL, `NITTER_RSS_TOKEN`, or `REDDIT_FEED_TOKEN` leaks into a public log or summary | Yes, logs are public on a public repo | §4 |
| T4 | A compromised GitHub Action steals the Discord webhooks or pushes to the repo | Rare but real (supply chain) | §5 |
| T5 | A run dies mid-way and corrupts state → duplicate or lost posts | Yes, runners get killed | §6 |
| T6 | A dependency ships a known CVE | Yes | §5 |

Out of scope: someone who already controls the repository or its secrets, and Discord itself.

---

## 2. Untrusted content (T1)

Everything on a card except the game's own `config/games.json` entry is scraped from somebody
else's server. Two sinks matter:

**Links.** `cards.safe_url()` is the single gate. A URL reaches a card only if it is plain
`http(s)`, free of whitespace and control characters, and no longer than `SAFE_URL_MAX` (1 KiB);
parentheses are percent-encoded. Discord's stricter `BUTTON_URL_MAX = 512` cap is additionally
enforced in `cards.link_button()` and `cards.validate_payload()` alongside non-empty `1..5`
Action Row validation, and direct media preflight/dimension checks allowlist only verified
official publisher CDNs (`hoyoverse.com`, `hoyolab.com`, `mihoyo.com`, `kurogame.com`,
`kurogames.com`, `aki-game.net`, `aki-game.com`, `easebar.com`, `anantagame.com`, `netease.com`,
`163.com`) plus X/Reddit media hosts where applicable, and the two beta-database hosts
(`nanoka.cc`, `gachabase.net`) that feature 5 (`BETA_ENABLED`) reads from. That blocks the
concrete attacks:

* `javascript:` / `data:` or an oversized (`>512`-char) URL in a link button would make Discord
  reject the **whole message** (`HTTP 400 Invalid Form Body`), so one poisoned or bloated link
  would silently kill a real announcement. Now only that single button is dropped
  (`link_button()` returns `None`, empty Action Rows are omitted) and the card still posts.
* `)` inside a markdown link closes it early:
  `[title](https://ok/x) [FREE CODES](https://evil)` renders as an extra clickable link that
  nobody here wrote — a phishing line inside a card readers trust *because* it came from this
  bot. Encoded parens (or a dropped link) make that impossible.

**Invisible characters.** `textutil.strip_invisible()` removes C0/C1 controls, zero-width
spaces and joiners, the BOM, and the bidi overrides `U+202A–202E` / `U+2066–2069` — the ones
that make a line *display* differently from what it says (a right-to-left override can render
`NEWS` as `SWEN`, or hide where a line really ends). It runs inside `clean_text()`, which every
scraped source already passes through, and again inside `cards.text()` as a last chokepoint, so
a field arriving by any other route is cleaned too. Test:
`test_invisible_and_bidi_characters_are_stripped_from_scraped_text`.

**Text.** Mentions can never be injected: `Ping.allowed_mentions` sends `{"parse": []}` unless a
role/@everyone was explicitly configured, and an edit re-sends exactly that same object —
`parse` filtered to `roles`/`users`/`everyone` and only the ids the card already declared, so a
scraped `@everyone`, `@here` or `@username` in a title can never become a live mention through
an edit. Scraped titles are bracket-escaped by `_md_link_text()`. Code strings must match
`^[A-Z0-9]{5,20}$`.

**Volume.** `http.MAX_BYTES` (8 MiB) caps one response body. Without it a hostile or broken host
could stream forever and `resp.text()` would buffer until the runner died; now it is one
ordinary source failure. Largest real body in production: ~1.3 MB.

Tests: `test_a_hostile_source_cannot_inject_links_or_kill_a_card`,
`test_an_endless_response_body_is_cut_off_instead_of_eating_the_runner`.

## 3. Corroboration and the flood brake (T2)

A code is posted only if it is **official**, **redeem-validated**, or listed by
**`CODES_MIN_SOURCES` (default 2) independent source families** — one compromised community
site or unverified subreddit post cannot invent a code on its own (`codeposter.gate()`, with
`Item.official` on subreddit fallbacks restricted to verified publisher/moderator accounts so
public user-selectable `"Official News"` / `"Official Media"` flairs never grant single-source trust).

On top of that, `codeposter.MAX_CARDS_PER_RUN = 5` caps one game at 5 cards (50 codes) per run.
A real drop is 1–6 codes; dozens at once means a broken or tampered source, and the leftovers
simply go out on the next run minutes later — nothing is lost, the flood is spread out and the
run reports it as an error. Test: `test_a_source_dumping_hundreds_of_codes_cannot_flood_the_channel`.

## 4. Secrets (T3)

* Webhook URLs never reach the log or run summary: both dry-run output and live error/hold
  diagnostics (`discord._redact_webhook`, `runner._summary_text`) rewrite `/webhooks/<id>/<token>`
  across all Discord webhook hosts (`discord.com`, `discordapp.com`, `canary.discord.com`,
  `ptb.discord.com`) to `/webhooks/…`, and state stores only `webhook_fingerprint()` — a short,
  non-reversible id, never the URL.
* Source logging prints `url.split("?")[0]` and scrubs sensitive query keys (`token=`, `feed=`,
  `user=`, `auth_key=`, `key=`, `api_key=`, `access_token=`, `Bearer`), so neither
  `NITTER_RSS_TOKEN`, `REDDIT_FEED_TOKEN` (including the account username parameter), nor signed
  Kuro media `auth_key=` parameters can leak into logs, job summaries, or workflow annotations.
* Official-news and maintenance-alert `POST` calls pass `stop_on_ambiguous=True` so HTTP `200`/`204`
  responses without a parseable `message_id` or indeterminate post-dispatch timeouts/disconnects stop
  after 1 attempt with `SendResult.ambiguous = True`, holding news (ordinary and expanded) and
  milestone state for review instead of blindly re-posting duplicates while preserving pre-PR
  retry behavior (`stop_on_ambiguous=False`) for `schedule`, `codes`, and CLI callers.
* Discord error bodies are truncated to 500 characters and never include the URL.
* Actions masks every secret value in logs as a second line of defence.

**Residual risk, accepted:** `monitor.yml` passes `toJSON(secrets)` as `GE_SECRETS_JSON` so the
run can discover `DISCORD_WEBHOOK_CODES_<GAME>` without the workflow listing each one. Any step
in that job can therefore read every secret. It is accepted because the job runs only this
repository's own code plus pinned first-party actions (checkout, setup-uv) — but it is the one
thing to revisit if a third-party step is ever added to that job. zizmor's
`overprovisioned-secrets` finding is suppressed on that exact line with this reasoning.

## 5. Supply chain and permissions (T4, T6)

* Default `permissions: contents: read`; `contents: write` only where a job must commit state or
  open a PR; `pull-requests: write` only on the auto-merge jobs. No `pull_request_target`
  anywhere, so a fork PR never runs with a writable token.
* Auto-merge jobs do **not** check out the PR's code — untrusted code never executes with the
  elevated token.
* Dependabot watches both `pip` and `github-actions` weekly; `pip-audit` runs in CI; `zizmor`
  audits the workflows; `actionlint` validates them.
* **Every action is pinned to a full commit SHA**, with the human-readable version in a
  trailing comment (`uses: actions/checkout@3d3c42e…  # v7`). This is the direct lesson of
  March 2025: an attacker with a stolen bot token repointed *every* tag of
  `tj-actions/changed-files` (v1 … v45.0.7) at one malicious commit that dumped runner memory —
  secrets included — into the logs of roughly 23 000 repositories (CVE-2025-30066). Days
  earlier `reviewdog/action-setup` was compromised the same way (CVE-2025-30154), and this
  repository uses a reviewdog action. A tag can be moved; a SHA cannot. Repos pinned by SHA
  were unaffected.
* Pinning by SHA does **not** freeze the actions: Dependabot's `github-actions` ecosystem
  updates SHA pins weekly and rewrites the version comment with them, so patches still arrive
  as a reviewable PR — and because a floating major tag hides patch/minor movement, SHA pins
  actually give Dependabot *more* to report, not less.
  `test_every_action_is_pinned_to_a_commit_sha_with_a_readable_version_comment` fails CI if any
  `uses:` ever goes back to a tag.

## 6. Integrity of state (T5)

`state.py` writes through a temp file + `os.replace()` (atomic), so a killed run can never
leave a half-written file; a file that no longer parses is moved aside as `state.corrupt.json`
instead of being overwritten, so nothing is lost silently. `State.load()` and every accessor also
normalize non-dict or non-numeric sub-slots in memory so a hand-edited or partially corrupted
sub-record never crashes a live run. Every posted card records its message id and webhook
fingerprint, which is what makes "edit the existing card" and "never post the same thing twice"
reliable across runs. In `runner.run_once()`, every top-level stage (`schedule`, `codes`,
`maintenance`, `news`, `program_announcements.json`) and per-game worker runs inside a guarded
boundary with `state.prune()`, `state.save()`, and `write_summary()` guaranteed in `finally` —
persisting completed work from earlier stages and writing `$GITHUB_STEP_SUMMARY` while withholding
`state.heartbeat()` whenever `ctx.errors` is non-empty so standby failover (`peer_state_url` +
`failover_after_min`) remains faithful.

---

## Reporting

Personal repository — open an issue, or just fix it on a branch. There is no bounty and no SLA.
