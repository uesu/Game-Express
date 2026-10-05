# Rolling out the schedule-card fan-out

How to switch on the per-game copies (`#zzz-news`, `#gi-news`, …) **safely**, one step at a
time, so that every step is verifiable before the next one.

The code ships **dormant**: with no `DISCORD_WEBHOOK_SCHEDULE_*_MIRROR_*` secret set,
`_sync_mirror()` returns on its first branch and behaviour is byte-for-byte what it was before.
Merging changes nothing. *You* decide when the fan-out starts, per game.

> **Status on `uesu/Game-Express`: complete as of 2026-10-05.** All six mirror secrets are set
> and `PING_SCHEDULE` carries a real role ID, so every game now shows
> `🪞 also DISCORD_WEBHOOK_SCHEDULE_MIRROR_<GAME>` in `Show resolved config` and the schedule
> channel pings again. Steps 1–7 below are kept as the reference procedure — run them in this
> order when standing up the **production** repo (see
> [`PROD-REPO-SETUP.md`](PROD-REPO-SETUP.md) §3), or when adding a seventh game.

See [`CONFIGURATION.md`](CONFIGURATION.md#fan-out--the-same-card-in-two-channels) for what the
setting does; this page is the operational order.

---

## Your inspection point: the `Show resolved config` step

`monitor.yml` runs `python -m gamexpress validate` on **every** run — live or test, before the
mode branch, before anything is posted. That step prints the routing table, and it is where the
fan-out shows up:

| Line in the log | Meaning |
|---|---|
| `schedule[✓ DISCORD_WEBHOOK_SCHEDULE \| no ping]` | no copy for this game — unchanged behaviour |
| `… \| 🪞 also DISCORD_WEBHOOK_SCHEDULE_MIRROR_ZZZ` | ✅ wired correctly |
| `… \| ⚠ …_MIRROR_ZZZ is the same channel as DISCORD_WEBHOOK_SCHEDULE — no copy sent` | you pasted the `#schedule` URL. No copy is sent; nothing is broken |
| `… \| ✗ …_MIRROR_ZZZ is not a webhook URL` | you pasted a channel link, not a webhook URL |
| no `🪞` at all | the secret name is misspelled |

> `mode=test` → `test=webhooks` does **not** check mirror secrets — `check-webhooks` only walks
> the primary `webhook_source()` chain. Use the step above instead.

---

## Step 1 — Settle the new card layout first (no secrets yet)

Do this **before** touching any secret, so that if something looks wrong you know it is the card
layout and not the fan-out.

> **Actions → `monitor` → Run workflow**
> ① mode `live` · ② only `schedule` · ③ game *(blank)* · ④ repost *(blank)* · ⑥ ping **off**

Expect:

1. `Show resolved config` → every game reads `schedule[✓ DISCORD_WEBHOOK_SCHEDULE | no ping]`,
   **no 🪞**.
2. Summary → a burst of `✏️` edit lines, one per live version.
3. In `#schedule` → no line above the card any more, title ends `… 📜`, Discord shows `(edited)`.
4. **Nobody is notified.** Edits never ping.

🛑 If anything looks wrong, stop here. No fan-out is involved yet.

## Step 2 — Create the game-channel webhook

> Discord → `#zzz-news` → ⚙ **Edit Channel** → **Integrations** → **Webhooks** →
> **New Webhook** → name it → **Copy Webhook URL**

## Step 3 — Add the secret

> GitHub → **Settings → Secrets and variables → Actions → New repository secret**
>
> | | |
> |---|---|
> | Name | `DISCORD_WEBHOOK_SCHEDULE_MIRROR_ZZZ` |
> | Secret | the webhook URL you just copied |

Two names to **avoid**:

- `DISCORD_WEBHOOK_SCHEDULE_ZZZ` — that *moves* ZZZ out of `#schedule` instead of copying it.
- `DISCORD_WEBHOOK_SCHEDULE_MIRROR` — no game suffix, so it mirrors **every** game into that one
  channel.

## Step 4 — Run that one game and read the log top-down

> **Run workflow** → ① `live` · ② `schedule` · ③ **`zzz`**

1. `Show resolved config` → `🪞 also DISCORD_WEBHOOK_SCHEDULE_MIRROR_ZZZ` (table above).
2. Summary → `🪞 ZZZ 3.3: also posted to DISCORD_WEBHOOK_SCHEDULE_MIRROR_ZZZ (no ping)`.
3. `#zzz-news` → the card is identical to the one in `#schedule`, with **no** `@role` pill.

> ⚠️ **The first run backfills.** Every ZZZ version whose card is still live — posted, not
> retired, maintenance under 45 days old — is copied across at once, not just the newest one.
> This is why you add one game first rather than all six.

**If you pointed it at a valid webhook for the *wrong* channel:** fix the secret and re-run. It
self-heals — the stored fingerprint no longer matches, so a fresh copy is posted to the right
channel. Delete the stray message by hand.

## Step 5 — Add the remaining games

| Channel | Secret name |
|---|---|
| `#gi-news` | `DISCORD_WEBHOOK_SCHEDULE_MIRROR_GI` |
| `#hsr-news` | `DISCORD_WEBHOOK_SCHEDULE_MIRROR_HSR` |
| `#wuwa-news` | `DISCORD_WEBHOOK_SCHEDULE_MIRROR_WUWA` |
| `#hna-news` | `DISCORD_WEBHOOK_SCHEDULE_MIRROR_HNA` |
| `#ananta-news` | `DISCORD_WEBHOOK_SCHEDULE_MIRROR_ANANTA` |

Either the key or the short name works (`_GI` or `_GENSHIN`, `_WUWA` or `_WW`, `_HNA` or
`_NEXUSANIMA`). Then one run: ① `live` · ② `schedule` · ③ *(blank)*. Each game backfills on that
run.

`DISCORD_WEBHOOK_SCHEDULE` itself never changes. Games without a mirror secret keep taking the
exact code path they always did — the two lookups are independent chains, and
`test_without_the_mirror_secret_exactly_one_card_is_sent` guards it.

## Step 6 — Resume the scheduler

Re-enable the **cron-job.org** job (see [`SCHEDULER.md`](SCHEDULER.md)).

## Step 7 — *Last, optional* — turn pings on

Only after several clean cron runs.

> **Settings → Secrets and variables → Actions → Variables** → `PING_SCHEDULE` → replace `none`
> with the role ID, in the `<@&123…>` form.

> ⚠️ **`none` counts as "set".** `Settings.ping()` walks `PING_<FEATURE>_<GAME>` →
> `PING_<FEATURE>` → `PING_ROLE_ID` and the **first one that exists wins**, so a leftover
> `PING_SCHEDULE=none` silently beats a correct `PING_ROLE_ID`. Edit `PING_SCHEDULE` itself;
> do not add a second variable next to it.

- Every live card is edited once to add the role to its legend line. Those edits **notify
  nobody**, so older cards gain a mention that never pinged.
- From then on a new card pings **once**, in `#schedule` only. The game-channel copies stay
  silent — that is the `test_the_game_channel_copy_never_pings` guarantee.

---

## Rolling back

Delete the mirror secret. The next run drops the stored copy ids and stops copying;
`#schedule` is untouched throughout. No code change, no redeploy. Re-adding the secret later
posts a fresh copy rather than editing a message in a channel the run can no longer prove it
owns.

## Cost

One extra request per card actually delivered, and **zero on idle runs** — the mirror is only
touched when a card is posted or edited. Measured at about +1.2 s on a posting run. A broken
game-channel webhook is reported (`⚠️ … copy failed`) and retried next run; it never reaches
`ctx.errors` and never fails the run, because the copy is a convenience and the schedule channel
is the product.
