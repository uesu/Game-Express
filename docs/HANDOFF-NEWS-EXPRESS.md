# Hand-off for News-Express — the Twitter card splits into more than one container

Written 2026-11-18 for the `testing area/twitter_v3.py` Twitter → Discord card (the runner
`twitter_monitor.yml` launches). This is the same class of bug the Game-Express news card had and
that was just fixed there; the two repositories are independent, so the Twitter card needs its own
change.

## 1. What the Game-Express side showed

`A Traveler's Guide to Iia | Your Dream RV` (HoYoLAB 47482558) arrived as **one message with two
containers**:

| | containers | children | components | text chars |
|---|---|---|---|---|
| hand-built "it fits" payload | 1 | 13 | 17 | 1,095 |
| what Game-Express posted | 2 | 11 + 6 | 22 | 1,117 |

`news_payloads()` started a new container once a card reached **eight units** and labelled them
`-# Part 1/2` / `-# Part 2/2`. That threshold was never a capacity limit: Discord's
**4,000-character / 40-component budget is per message** and every container inside the message
counts against the same budget. The split itself also *adds* a label plus a divider per container,
so the chunked payload always carried more components and more text than the single container it
replaced — it could only ever cut cards that already fit, and could never rescue one that did not.
It had also been splitting two real ZZZ notices (3,541 and 3,726 characters).

The fix was not a bigger threshold: the renderer now builds the complete card as one container and
returns it when `validate_payload()` accepts it, and the unreachable multi-container branch is gone.
Over-budget articles page (`-# Page n`) instead. In Game-Express a fitting card now packs to the cap
(a 3,650-character article → one 3,955-character message; 30 inline galleries → exactly 40
components) and a second message appears only when the request genuinely exceeds one message's cap.

## 2. The equivalent in `testing area/twitter_v3.py`

`_pack_twitter_components()` (~line 1828) has the same shape as the rule that was removed:

```python
def _pack_twitter_components(components: list, accent: int) -> list:
    """Pack card children into Discord containers (at most ten children each)."""
    return [{"type": 17, "accent_color": accent,
             "components": components[i:i + 10]}
            for i in range(0, len(components), 10)]
```

It is called once per tweet card (~line 2154) after the card's inner components are complete, and
the 40-component guard afterwards (`_twitter_component_count`, `_group_selected_galleries`) only
decides whether the galleries need compacting — it never revisits the 10-per-container packing. So a
tweet whose card has 11+ inner components is delivered as **two or three stacked cards in one
message**, even when the whole card is far inside the per-message budget. Each extra container also
draws its own accent bar, which is what makes it read as "the card separated".

Nothing is illegal about a container holding more than ten children: the limit that matters is the
message-wide 40 components, which the same function already computes one line later.

## 3. Suggested change (mirror of the Game-Express fix)

1. Build `single = {"type": 17, "accent_color": accent, "components": inner_components}` and check it
   with the existing counters: `_twitter_component_count(single) <= 40` and the card's text within
   4,000 characters (the `notes_budget` code at ~line 2147 already measures that).
2. If it fits, return `{"flags": IS_COMPONENTS_V2, "components": [single]}` — one container, no
   regrouping.
3. Only when it does not fit, fall back to today's 10-per-container packing (and keep the gallery
   compacting order: quote gallery first, then main media). That path is then genuinely a fallback
   rather than the default shape.
4. Do not change: `MAX_TEXT_COMPONENTS` chunking, `LEGACY_TWEET_MEDIA_LIMIT` grouping of 5–20 media,
   `MAX_TWEET_MEDIA = 20`, the nested button row, `SUPPORT_FOOTER`, the media heal and dedup caches.

## 4. Tests that would have caught it (Game-Express pattern, portable as-is)

- Render one real card that currently splits (11–20 media, or text + quote + galleries) and assert
  `len(payload["components"]) == 1`, every child present in source order, and
  `_twitter_component_count(...) <= 40`.
- Table-drive the boundary: the largest card that still fits stays one container; one gallery more
  must page or compact — never silently drop a media item, and every emitted payload stays valid.
- Assert the negative: a payload is split into more than one container **only** when the card's own
  component count or text length exceeds the per-message caps. That is the invariant the eight-unit
  rule (and the ten-children rule) violated.
- Keep a golden payload of one known-good card; a container count in it is the regression alarm.

## 5. How to tell which case the reported tweet was

Pull the tweet's rendered payload from the run log (or rebuild it with the `test_tweet` workflow
input for that status id) and look at:

- `len(payload["components"])` — more than one container with a total component count under 40 means
  the 10-child packing split a card that fits: cosmetic, fix with §3.
- a component count over 40 or text over 4,000 — genuine overflow; the card needs compaction or a
  second message, and the split is correct (the exact numbers are then worth recording).
- 5–20 media where the legacy 4-media presentation regrouped the images — that grouping is by design
  (`LEGACY_TWEET_MEDIA_LIMIT`), not the packing rule.

## 6. Not in scope

Game-Express deliberately does **not** post Twitter/X cards and takes no Twitter reveal ping: the
Game-Express reveal ping (`NEWS_REVEAL_PING` + `PING_NEWS_REVEAL`) is now off for Wuthering Waves
only, because this Twitter card is the one that already announces those reveals. Nothing here asks
News-Express to change its pinging.
