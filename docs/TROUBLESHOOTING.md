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
| A maintenance / pre-install / banner notice appeared, but no card | Correct: only a *Special Program* / *Special Broadcast* opens a card. The notice's data is recorded and lands on the card the moment the announcement is seen; the version shows as `tracked` in the summary |
| An announcement was found but no card appeared | the programme has already aired (over 36 h ago, or its maintenance began over 12 h ago), so it is history, not news — the summary says `🗂 … already out`. This is why versions that shipped before the bot existed stay out of the channel. `repost = <game>:<version>` posts one deliberately |
| A card that used to update stopped updating | the version is **frozen**: edits end `CARD_FREEZE_D` (45) days past maintenance, and the summary says `🧊 … card frozen` once. `repost = <game>:<version>` publishes a fresh card |
| A card can never get its air time or link | the record was built from a notice and there is **no cached tweet id** to replay, so nothing can repair it. The summary says `🩹 …` and names the fix (see below) |
| `🗂 … its card is not re-created` | the stored card id no longer resolves (Discord `10008`); the summary names the saved id even though the record drops it in the same retirement pass. The response does not prove who removed it or why. Because the programme has already aired, no new card is posted; the record stays tracked and silent. `repost = <game>:<version>` publishes one deliberately |
| `🗂 … copy not created — copy <id> was deleted (10008)` | a mirror id was recorded, but the edit returned Discord `10008` (`Unknown Message`). The summary names the id and uses “was deleted” as its report wording; `10008` only proves that the id no longer resolves, not who removed it or why. A settled version is not re-posted. If no copy id was recorded, the shorter `— already out` line means no copy was ever made |
| Runs are skipped (grey) | the variable `ENABLED_FEATURES=none` is set. That's only for a development copy; remove it on the repo that posts |
| Workflow stopped after 60 days | GitHub pauses idle repos. The daily heartbeat commit prevents this; re-enable it in the Actions tab if it happened |

The 🩹 case is the one the bot cannot fix by itself: the record has no air time, no announcement
link, and no cached tweet id to replay. Add the announcement's tweet id for that version to
`config/program_announcements.json` (see
[ACCURACY.md](ACCURACY.md#the-announcements-own-link-and-key-art)) and the next run edits the card
in place — air time, link and key art all come back together.

---

## The card looks wrong

| Symptom | Fix |
|---|---|
| `400 … components` in the log | a card broke a Discord limit. `python -m gamexpress validate` pinpoints it (CI also catches this) |
| No ping | `PING_ROLE_ID` unset or `none`; the role must be mentionable, or the webhook needs *Mention @everyone, @here and All Roles* |
| Emojis show as `:name:` | the webhook's channel needs *Use External Emojis* for `@everyone`, or change `EMOJI_*` |
| Card not edited after an override | the card must have been posted by a webhook with the same URL (the fingerprint is stored) |
| Title link or key art changed to a different post after posting | a posted Special Program card is locked to the post that opened it ([ACCURACY.md](ACCURACY.md#once-posted-the-card-keeps-its-announcement)). It can only switch if its record has neither `announcement_locked` nor `program_seen`, so check that in `state/state.json`. Pin the right post with `title_url` and `image` in `config/overrides.json`; the next run edits the card back, and the log names the change (`schedule card updated — key art, link`) |
| No livestream date line | the record never got the announcement, so there is no air time to show (a misleading `TBA` would be worse). If the tweet id is cached, the next run replays it once and date, key art and title link come back together; if not, see the `🩹` line above |
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
