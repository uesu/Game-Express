# Troubleshooting

Symptom → fix. Start with the **job summary** of the run in question
(*Actions → Game-Express Monitor → the run*): it lists what was posted, what was skipped and
why, and the health of every source.

- [Nothing is posted](#nothing-is-posted)
- [The card looks wrong](#the-card-looks-wrong)
- [Sources and codes](#sources-and-codes)
- [cron-job.org](#cron-joborg)
- [Still stuck](#still-stuck)

---

## Nothing is posted

| Symptom | Fix |
|---|---|
| Nothing posted for days | Normal. It posts only on official announcements and new codes. Check the job summary: *"nothing new"* plus source health. |
| First Monitor runs posted nothing | Correct: the first run per game is a **silent seed** (`🌱 … seeded silently`). Use `repost = starrail:4.6` to post a current card now |
| `repost` posted nothing | the version isn't tracked yet (not announced, or never seen). The summary says `version … isn't tracked` and lists the ones that are |
| Runs are skipped (grey) | the variable `ENABLED_FEATURES=none` is set. That's only for a development copy; remove it on the repo that posts |
| Workflow stopped after 60 days | GitHub pauses idle repos. The daily heartbeat commit prevents this; re-enable it in the Actions tab if it happened |

---

## The card looks wrong

| Symptom | Fix |
|---|---|
| `400 … components` in the log | a card broke a Discord limit. `python -m gamexpress validate` pinpoints it (CI also catches this) |
| No ping | `PING_ROLE_ID` unset or `none`; the role must be mentionable, or the webhook needs *Mention @everyone, @here and All Roles* |
| Emojis show as `:name:` | the webhook's channel needs *Use External Emojis* for `@everyone`, or change `EMOJI_*` |
| Card not edited after an override | the card must have been posted by a webhook with the same URL (the fingerprint is stored) |
| `webhooks` test shows ✗ / `not a webhook URL` | the secret holds something else (a channel link, extra spaces). Copy the webhook URL again |

---

## Sources and codes

| Symptom | Fix |
|---|---|
| `every code source was unreachable` | a transient outage. The next run catches up because codes are compared against the state, not the time |
| X silent | nitter fleet down. The HoYoLAB / Kuro sources still work; add `NITTER_RSS_TOKEN` or a fresh `NITTER_INSTANCES` |
| A code isn't posted | it's *pending*: only one source has it, or a source lists it as expired. The job summary shows the reason. Official / redeem-validated codes post immediately |
| `4 Star Characters: TBA` although the names are known | the official text didn't list exactly the expected number, or two posts disagreed. Put the names in `config/overrides.json`; the card is edited on the next run |

---

## cron-job.org

| Symptom | Fix |
|---|---|
| cron-job.org shows **401** | the token expired or is wrong: make a new classic token (`repo` scope) and paste it into the job's header ([SCHEDULER.md](SCHEDULER.md)) |
| cron-job.org shows **404** | wrong owner / repo / file name in the URL, or the token can't see the repo |
| cron-job.org shows **422** | the branch in the body doesn't exist (`{"ref":"main"}`) or the workflow has no `workflow_dispatch` |

Full scheduler setup, the classic token and the response codes: **[SCHEDULER.md](SCHEDULER.md)**.

---

## Still stuck

Reproduce it offline before changing anything — none of these posts to Discord or writes state:

```bash
python -m gamexpress validate                               # routing, pings, emojis, card limits
python tests/test_smoke.py                                  # the full offline suite
python -m gamexpress preview --out /tmp/previews            # render every card locally
DRY_RUN=1 STATE_PATH=/tmp/s.json python -m gamexpress run   # a real pass that posts nothing
```

Then check **[TESTING.md](TESTING.md)** for the end-to-end checklist, and
**[ACCURACY.md](ACCURACY.md)** for why a specific value came out the way it did.
