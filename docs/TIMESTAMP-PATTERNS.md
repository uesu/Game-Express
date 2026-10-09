# Timestamp pattern study — feasibility report for native speculation

Status: **shipped.** The study below is what the implementation is calibrated on; the numbers in
every table are reproduced as assertions in `tests/test_smoke.py` so they cannot silently rot.

Try it: `python -m gamexpress speculate` (read-only — posts nothing, writes no state). Add
`--verbose` to see the real maintenance dates it is anchored on, `--game genshin` to narrow it,
and `--now <unix>` to check what it *would* have predicted at some past moment.

Scope: timestamps only (special program / livestream, maintenance start+end, pre-install).
Not banners, not characters.

Dataset: historical announcement posts for Genshin Impact 4.7→7.1, Honkai: Star Rail 2.3→4.6,
Zenless Zone Zero 1.5→3.2 and Wuthering Waves 1.4→3.7 (May 2024 → Sep 2026). All times below are
UTC+8, which is the publisher clock for all four titles and also the reader's local time.

---

## 1. Can a Discord timestamp be read?

Yes. `<t:EPOCH:STYLE>` is not an opaque token — `EPOCH` is plain Unix seconds and `STYLE` only
selects the rendering (`F` = full date-time, `R` = relative, `d`/`t`/`D`/`T`/`f` = other forms).
The style has no effect on the value. Worked examples from the corpus:

| tag | decodes to (UTC+8) | matches the post's own prose |
|---|---|---|
| `<t:1716552000:F>` | Fri 2024-05-24 20:00 | Genshin 4.7 Special Program |
| `<t:1717759800:F>` | Fri 2024-06-07 19:30 | HSR 2.3 Special Program |
| `<t:1718748000:F>` | Wed 2024-06-19 06:00 | HSR 2.3 maintenance start |
| `<t:1718766000:F>` | Wed 2024-06-19 11:00 | HSR 2.3 maintenance end |
| `<t:1721167200:F>` | Wed 2024-07-17 06:00 | Genshin 4.8 maintenance start |
| `<t:1728646200:F>` | Fri 2024-10-11 19:30 | HSR 2.6 Special Program |

The three struck-through HSR 2.3 drip-marketing tags each decode to exactly **+24 h** from the value
they replaced (`06-04 12:00 → 06-05 12:00 → 06-06 12:00 → 06-07 12:00`). That is the canonical
"official moved the date, re-post or edit" case the speculation layer has to survive.

The repo already parses these: `gamexpress/timeparse.py`, and `cards.py` re-emits `<t:…>` so the
reader sees their own local time.

---

## 2. Version cadence (days between consecutive maintenance starts)

| game | versions | median | exactly 42 d | min | max |
|---|---|---|---|---|---|
| Genshin | 20 | 42.0 | **100 %** (19/19) | 42 | 42 |
| Star Rail | 21 | 42.0 | 60 % | 28 | 58 |
| ZZZ | 15 | 42.0 | 35 % | 34 | 50 |
| Wuthering Waves | 18 | 42.0 | 47 % | 32 | 49 |

Genshin has not missed a 42-day beat once in 20 versions. The other three use 42 days as the
*intent* and then compress or stretch — these are the "shortened patch cycle" cases:

- Star Rail `3.8 → 4.0` = **58 d** (Chinese New Year stretch), then `4.1 → 4.2` = **28 d** and
  `4.2 → 4.3` = 40 d clawing the slip back, and `4.5 → 4.6` = **33 d**.
- ZZZ `2.4 → 2.5` = 34 d and `2.5 → 2.6` = 38 d (holiday compression), `2.1 → 2.2` = 50 d.
- WuWa `3.4 → 3.5` = 32 d, with several 35 d and 39–41 d cycles.

Conclusion: cadence must be **per game, learned, and confidence-weighted** — never a global 42.

## 3. Slot anchoring (weekday + wall-clock time)

| game | maintenance start | modal weekday | duration |
|---|---|---|---|
| Genshin | 06:00 | Wed ×20 (100 %) | 5 h → 11:00 |
| Star Rail | 06:00 | Wed ×17 of 21 | 5 h → 11:00 |
| ZZZ | 06:00 | Wed ×10 of 15 | 5 h → 11:00 |
| Wuthering Waves | 04:00 | Thu ×14 of 18 | 7 h → 11:00 |

The **time of day is effectively constant**; only the date moves. This is the single most important
modelling decision: predict a *local wall-clock slot*, not a raw duration offset. Adding
`median_gap` as a `timedelta` to the previous start and then **snapping to the game's modal
weekday** is strictly better than arithmetic alone (section 5).

## 4. Derived offsets

**Pre-install lead before maintenance start:**

| game | n | median | min | max | shipped `PREINSTALL_LEAD_H` |
|---|---|---|---|---|---|
| Genshin | 10 | **43.0 h** (10/10 identical) | 43 | 43 | 43 ✅ |
| Star Rail | 11 | 40.0 h (8/11 identical) | 12 | 88 | **88 ⚠️** |
| ZZZ | 10 | **42.0 h** (9/10) | 42 | 66 | 42 ✅ |
| WuWa | 18 | **42.0 h** (17/18) | 42 | 42.5 | 42 ✅ |

⚠️ `PREINSTALL_LEAD_H["starrail"] = 88` in `schedule.py:200` is calibrated on version 4.6, which is
the single largest outlier in the series. The modal and median lead is **40 h** (Mon 14:00 → Wed
06:00). This only affects cold start — `observed_lead_h()` replaces it with the learned median once
this installation has seen one real pre-install/maintenance pair — but on a fresh state file the
first Star Rail card would be ~2 days early. Recommended correction: **40**.

**Special program lead before maintenance start:** median 11.4 d for Genshin / HSR / ZZZ, 11.9 d for
WuWa — i.e. *the Friday ~12 days before launch*, at a fixed per-game air time:

| game | air time | consistency | exceptions |
|---|---|---|---|
| Genshin | 20:00 | 16/20 | 4.8 at 20:05, 5.0 at 12:00, 6.0 pre-show 19:51, 6.3 at 13:00 |
| Star Rail | 19:30 | 21/21 | none |
| ZZZ | 19:30 | 14/15 | 2.0 at 19:00 |
| WuWa | 19:00 | 14/14 | none |

Program lead is the **noisiest** of the three offsets (Genshin range 10.4–18.4 d, WuWa 5.4–13.4 d),
so the special program should carry the widest uncertainty window and the lowest confidence.

## 5. Backtest — which prediction rule to ship

Each version from the 5th onward was predicted using only prior versions, then compared to truth.
"exact" = to the minute.

| strategy | Genshin | Star Rail | ZZZ | WuWa |
|---|---|---|---|---|
| previous + 42 d | 100 % exact | 64 % | 36 % | 42 % |
| previous + median(all gaps) | 100 % | 64 % | 27 % | 42 % |
| previous + median(last 3 gaps) | 100 % | 64 % | 9 % | 42 % |
| **previous + median(all) + weekday snap** | **100 %** | **76 %** | **54 %** | **57 %** |

Weekday snapping wins everywhere and never loses. Note that a short window (last 3 gaps) is *worse*
than the full history — a holiday compression poisons a short window, while the full-history median
stays locked on the 42-day intent.

The table above starts at the 5th version (the rule needs four earlier dates). The test that pins the
shipped rule (`test_predict_cycle_backtests_the_published_history`) starts earlier, at
`SPECULATE_MIN_HISTORY` = 2, so it counts more versions and reports lower numbers. Re-measured on
2026-10-09 with the same rule, both windows:

| game | from the 5th version: exact / within 3 d | from the 3rd version (the test): exact / within 3 d | median abs error | mean signed error | worst miss |
|---|---|---|---|---|---|
| Genshin | 16/16 · 16/16 | 18/18 · 18/18 | 0 h | 0 h | none |
| Star Rail | 13/17 · 14/17 | 14/19 · 16/19 | 0 h | +12.6 h | −16 d (2026-02-13), +14 d (2026-04-22), +9 d (2026-09-28) |
| ZZZ | 6/11 · 6/11 | 6/13 · 7/13 | 48 h | +20.3 h | −8 d (2025-09-04), +8 d (2025-12-30) |
| WuWa | 8/14 · 10/14 | 9/16 · 11/16 | 0 h | +70.5 h | +13 d (2026-07-10), +9 d (2025-04-29) |

(Signed error: positive = the prediction is later than the published date. Genshin and Star Rail were
measured to the minute; WuWa publishes at 04:00 and ZZZ at 06:00 and the test uses those times.)

Reading the table: Genshin is the only game that never misses. Star Rail lands within a day in 15 of 19
versions and WuWa in 10 of 16, and their misses are whole-cycle shifts, not drift. ZZZ is the least reliable
(within a day in 6 of 13), and its card says so with the cadence label. The most recent published dates were
Genshin 7.1 (exact), ZZZ 3.2 (exact), WuWa 3.7 (+1 d) and Star Rail 4.6 (+9 d). Star Rail's worst miss is 16 d,
so its 4.7 forecast (2026-11-11) is an estimate with a week or more of uncertainty, not a date.

**Maintenance length and pre-install, as observed (not backtested beyond these):** the maintenance
end came 5 h after the start for Genshin 7.1 and Star Rail 4.6, and 7 h for WuWa 3.7. ZZZ has no official
end in the state yet, so its 5 h is still the estimate. The official pre-install for Star Rail 4.6 came
88 h before the start, not the 40 h the rule uses, so the Star Rail pre-install estimate is the least
certain of the four.

**Forecast produced by the winning rule from the latest data in the corpus:**

| game | last known | predicted next maintenance | pre-install | special program |
|---|---|---|---|---|
| Genshin (7.2) | 7.1 Wed 2026-09-23 06:00 | Wed 2026-11-04 06:00 | Mon 2026-11-02 11:00 | Fri 2026-10-23 20:00 |
| Star Rail (4.7) | 4.6 Mon 2026-09-28 06:00 | Wed 2026-11-11 06:00 | Mon 2026-11-09 14:00 | Fri 2026-10-30 19:30 |
| ZZZ (3.3) | 3.2 Wed 2026-09-09 06:00 | Wed 2026-10-21 06:00 | Mon 2026-10-19 12:00 | Fri 2026-10-09 19:30 |
| WuWa (3.8) | 3.7 Wed 2026-09-30 04:00 | Thu 2026-11-12 04:00 | Tue 2026-11-10 10:00 | Fri 2026-10-30 19:00 |

(Star Rail and WuWa rows are shown after the weekday snap; the raw arithmetic lands on Mon and Wed
respectively, which is exactly the error the snap removes.)

---

## 6. How it is implemented

The feature needed no new subsystem — just one more producer feeding machinery that already
existed. What was already there:

| requirement | where it already lives |
|---|---|
| a trust tier below every real source | `PRIORITY["pattern"] = 9` vs `countdown` 10, `launcher` 20, `x` 40, `news` 45, `hoyolab`/`kuro` 50, `override` 100 — `schedule.py:189` |
| per-field provenance so a guess never overwrites a fact | `prov[key] = [priority, ts]`, merged in the record loop at `schedule.py:789–880` |
| a working pattern-derived prediction, as precedent | `derive_preinstall()` `schedule.py:568`, writes at `PRIORITY["pattern"]` and refuses to touch a value it did not itself derive (`:582`) |
| learning the offset from observed history instead of a constant | `observed_lead_h()` + median, `schedule.py:~555` |
| auto-edit when the real date lands | `edit_on_update` → `schedule.py:1017` |
| **no edit when the prediction was already right** | `schedule.py:1020-1021`: `h = stable_hash(payload["components"])`; `if h == record.get("payload_hash")` → skip. Identical render ⇒ zero Discord calls |
| visible "this is a guess" labelling | `cards.py:326-329` — "🕒 … estimated from … — the official notice replaces it automatically" |
| un-marking a field once the real value arrives | `_unmark_estimated()` `schedule.py:508` |

So the three behaviours asked for are already guaranteed by the existing design:

1. **Predict when nothing is live** → write at `PRIORITY["pattern"]`.
2. **Auto-edit when real data disagrees** → the real source outranks `pattern`, the field is
   replaced, `_unmark_estimated()` clears the label, the payload hash changes, `EDIT_ON_UPDATE`
   edits the stored message id in place.
3. **Stay silent when the prediction was already correct** → the re-render is byte-identical, the
   hash matches, and the edit is skipped. This is not new work; it is current behaviour.

What was added:

| piece | where |
|---|---|
| per-game rhythm as **config, not code** | a `cadence` block per game in `config/games.json`, parsed into `config.Cadence` by `config._cadence()` — every malformed field falls back to a default instead of raising |
| real maintenance dates, estimates excluded | `schedule.observed_starts()` |
| learned median gap, outliers discarded | `schedule.observed_cadence_days()` |
| nearest-weekday snap | `schedule._snap_weekday()` |
| the predictor | `schedule.predict_cycle()` |
| the producer that writes into a dark version | `schedule.derive_cycle()`, called from `merge()` immediately before `derive_preinstall()` |
| the read-only inspection command | `gamexpress/__main__.py:cmd_speculate` |

```
derive_cycle(game, version, data, prov, now, records)
  └─ maint_start = snap(last_real_start + median_gap, modal_weekday) at the game's fixed local time
     maint_end   = maint_start + per-game duration (5 h HoYoverse, 7 h Kuro)
     program_ts  = snap(maint_start - 12 d, program weekday) at the game's fixed air time
     then the existing derive_preinstall() fills pre-install from that start
  └─ every field written at PRIORITY["pattern"], added to data["estimated"],
     estimate_sources = ["version cadence"], never written over a higher tier
```

Four guards keep it honest:

1. **Forward only.** A prediction is "one cadence after the newest real maintenance", so it is
   refused for any version at or below that anchor — otherwise a livestream post for the current
   version would be stamped with its successor's dates.
2. **Horizon.** The result must be in the future and within 120 days, the same window
   `apply_estimates()` already allows countdown sites.
3. **No self-teaching.** `observed_starts()` skips anything listed in `data["estimated"]`, so a
   guess can never become its own evidence.
4. **No state churn.** An unchanged prediction rewrites nothing, so the committed `state.json`
   does not change and no Discord edit is produced.

### One bug fixed along the way

`PREINSTALL_LEAD_H["starrail"]` was `88`, calibrated on version 4.6 — the single largest outlier
of 11 observations, the one version whose maintenance slipped to a Monday. The modal and median
lead is **40 h**, used by 8 of 11 versions. On a fresh state file the old value put HSR's
pre-install card two days early. Now `40`, with the cold-start test checking a *typical* version
(4.5) rather than the latest one.

Risks and how they are already contained:

- *A wrong guess is posted publicly.* Contained by the footer label at `cards.py:329` and by the
  fact that any real source immediately outranks and replaces it.
- *Edit storms.* Contained by the payload-hash comparison — a stable prediction produces no traffic.
- *Compressed/holiday cycles.* Partly contained by the full-history median (which beats a short
  window) plus the weekday snap; the residual is real, which is why ZZZ/WuWa should post a window
  ("expected around …") rather than a hard `<t:…:F>`, and Genshin can post an exact slot.
- *The model teaching itself.* Already solved for pre-install — `derive_preinstall()` never records
  a derived value as an observation. The cadence history must follow the same rule: observe only
  timestamps from real sources.

No change was required to the posting path, the editing path, or the Discord layer.

### What a confirmed prediction costs

If the official notice matches the guess exactly, **no timestamp on the card moves**. The card is
still edited once — it has to stop telling readers the times are estimated — but that edit is
silent, carries no ping, and is the only difference. A further run with the same notice produces
zero Discord calls. Both are asserted in
`test_a_correct_speculation_moves_nothing_but_the_estimated_caveat`.
