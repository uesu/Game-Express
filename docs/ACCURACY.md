# How it decides to post

The accuracy rules. Game-Express never posts on a timer: a card exists because an **official**
post matched a pattern, and every value on it can be traced back to a source.

- [The schedule pipeline](#the-schedule-pipeline)
- [Verified against real posts](#verified-against-real-posts)
- [Filling the gaps before the official notice](#filling-the-gaps-before-the-official-notice)
- [The code gate](#the-code-gate)

Related: [SOURCES.md](SOURCES.md) (what each upstream serves) ·
[SECURITY.md](SECURITY.md) (how untrusted source data is handled) ·
[TIMESTAMP-PATTERNS.md](TIMESTAMP-PATTERNS.md) (the release-rhythm study behind the estimates).

---

## The schedule pipeline

1. **Detect**: official posts are read from HoYoLAB, official X accounts and the Kuro site, then
   filtered by per-game patterns (`special program`, `special broadcast`, maintenance /
   pre-install notices, banner notices, explicit "redemption code" posts). Posts that aren't
   announcements are ignored: recaps, replays, "has ended", merch.
2. **Extract, from official text only**:
   - **Program time** comes from the post's datetime with an explicit offset: `UTC+8`,
     `UTC-4`, `GMT+8`. `(server time)` is never trusted, because it differs per region.
     Missing years are inferred from the post date (`December 19 at 19:30 (UTC+8)`).
   - **Version**: `Version 4.6` / `Ver.4.6` / `V4.6`. Genshin tweets that only say "the new
     version" get the number from the matching HoYoLAB post, or from the official launcher's
     live version + 0.1.
   - **Maintenance**: pre-install, start, and end (end comes from an explicit end time, a range
     like `04:00 - 11:00 (UTC+8)`, or "estimated to take 5 hours"). Compensation deadlines and
     event end dates are never mistaken for maintenance.
   - **Banners**: only names that directly follow "5-star character" / "S-Rank Agent" /
     "5-star Resonator" (and the 4★ equivalents) in official banner notices. Genshin titles the
     banner and *then* names the character (the 5-star character `"Tasteful Excellence"
     Escoffier`), so the bare name after a closing quote is the character and the quote is the
     banner it is featured on. Weapons and banner titles never match.
   - **4★ characters are TBA unless certain.** The names are shown only when the official
     notice lists exactly the expected number of rate-up 4★ (GI 3 · HSR 3 · ZZZ 2 · WW 3), every
     name looks like a real name, and no official source disagrees. Otherwise the card shows
     `4 Star Characters: TBA` and the job summary says why. Once two official posts disagree,
     that phase stays TBA until you confirm the names in `config/overrides.json`.
3. **Merge with provenance.** Priority is *overrides > official notice > official tweet >
   launcher signal > countdown estimate > learned pre-install fallback > banner feed*.
4. **Unknown values are TBA, and banners always carry (STC).** Countdown and learned pre-install
   values are explicitly labelled estimated; neither can overwrite an official value.
5. **Only an announcement opens a card.** A *Special Program* / *Special Broadcast* / livestream
   post creates the card; maintenance, pre-install and banner notices may only fill in a card
   that already exists. This is what the channel is for — a maintenance notice is not an
   announcement, and on its own it never earns a post.
6. **A programme that already aired is history.** Once it is over (more than 36 h past, or the
   version's maintenance began more than 12 h ago) the version is still tracked and its data
   still saved, but no card is ever opened for it — including after a failed edit. That covers
   every version released before this bot was deployed. `repost` is the deliberate override.
7. **Post once** per game + version (`state/state.json`), then **edit silently** when data
   changes. A `404 Unknown Message` means the stored id no longer resolves — the message may have
   been removed, or it may never have belonged to this webhook at all. For a version that is
   still current the card is re-created once and the new id adopted; for one that has already
   aired, rule 6 wins and nothing is posted; if the stored id no longer resolves, the
   retirement summary still names it even though state drops it in the same pass. The optional
   game-channel copy follows the same no-new-message rule for settled versions; a previously
   recorded copy that returns 10008 is named in its one-time settled-retirement summary.
   Every other edit failure remains an error and never reposts.

---

## Verified against real posts

The parsers reproduce the exact timestamps of the four reference cards from the official posts
(pinned by the golden tests in `tests/fixtures/golden/`):
- GI 7.1 program: `1789214400`
- GI 7.1 pre-install / maintenance start: `1789959600` / `1790114400` (43 h)
- HSR 4.6 pre-install / maintenance: `1790229600` / `1790546400` → `1790564400` (88 h)
- ZZZ 3.2 pre-install: `1788753600` (42 h before maintenance)
- WW 3.7 pre-install / broadcast: `1790560800` / `1789815600` (42 h before maintenance)

---

## Filling the gaps before the official notice

A Special Program is announced days before the maintenance notice, so a fresh card would
otherwise be mostly `TBA`. Three fallbacks fill those holes — all of them **labelled on the
card**, all of them replaced automatically the moment an official value arrives, and each
with its own off switch.

### Maintenance times — countdown sites

The maintenance notice usually
arrives days after the Special Program, so until then the card can only show `TBA`. Since
**1.2.0** the monitor fills those gaps from community countdown sites
(`{game}-countdown.gengamer.in`, `gachacountdown.online`):

- an estimate is used **only** for a time that no official source has given yet, and it is
  replaced automatically the moment the official notice is seen (the same silent edit);
- the card says so: `🕒 maintenance start, maintenance end estimated from Gacha Countdown — the
  official notice replaces it automatically`, and the run summary carries the same line;
- `COUNTDOWN_ESTIMATES=0` switches it off, and a countdown site is only asked for a game that
  is actually missing a time (no request is wasted on a version that is already out).

### Pre-install time — a learned lead

If maintenance start is known
but no official source has published pre-install yet, the monitor derives one labelled
**estimated**. The fallback is not a fixed weekday rule: each real notice records its lead in
hours (`maintenance start - pre-install`), and later versions use that game's median. The median
handles shortened/extended patches and holiday moves without one bad parse dragging future
cards. On a fresh installation the verified 2026 leads are used once (GI 43 h · HSR 88 h · ZZZ
42 h · WW 42 h). A derived value never teaches the model, so a guess cannot confirm itself; an
official HoYoLAB, X/Nitter, Kuro, launcher or override value replaces it automatically.

### The announcement's own link and key art

A run only sees posts inside its
lookback window, so a version that is already a week old can end up with a card that links to the
*Update and Maintenance Notice* — and shows that notice's cover — simply because the Special
Program announcement had scrolled out. Since **1.3.0** the monitor looks the announcement up:

- the **official news pages** (`genshin.hoyoverse.com/en/news`, `hsr.hoyoverse.com/en-us/news`,
  `zenless.hoyoverse.com/en-us/news`, `wutheringwaves.kurogames.com/en/main/news`) archive every
  announcement with its cover, and an article page carries the embedded stream — whose YouTube
  thumbnail is the program's own 1280×720 artwork;
- failing that, the **HoYoLAB news list is paged back** past the lookback window;
- the headline links the announcement **wherever it was published** — an official **X post** is preferred (ZZZ 3.3:
  `x.com/ZZZ_EN/status/2106957553435312559`; Genshin 7.1: `x.com/GenshinImpact/status/2096810691021689205`).
  An official **HoYoLAB / official-site article** is equally correct, and is the fallback when X cannot be
  read (ZZZ 3.3's card had been built from `hoyolab.com/article/46972907` before it was pinned to X). The card says which one it used (`🛰️ … key art and link from HoYoLAB`). What the link must never be
  is the *Update and Maintenance Notice* — a different post that happens to carry the maintenance
  times, and the reason the first 7.1 card had no air time and the notice's cover;
- images are always upgraded to the biggest rendition the source serves (tweet photo → `?name=orig`,
  YouTube → `maxresdefault`), and the card says where the key art came from
  (`🖼️ key art: HoYoLAB — the official announcement`);
- one lookup per version that still needs it. That normally ends 12 h after maintenance — the
  card is history by then — with one exception: a version whose record never got an announcement
  at all is looked up **once more** when its tweet id is already cached in
  `config/program_announcements.json`, which is what makes the lookup a single call that succeeds
  instead of an open-ended retry. `CARD_FREEZE_D` ends it for good, and `PROGRAM_MEDIA=0` switches
  the whole thing off.

---

### Once posted, the card keeps its announcement

The lookup above decides the card's link and key art **once**. The first post that gives an air
time sets `announcement_locked`, and from then on:

| Field | After the lock |
|---|---|
| title link, source button(s), key art | fixed to the post that opened the card |
| air time, programme name, version name, YouTube link | fixed. Only an *estimated* air time can still be replaced by an official one |
| banners (5★ and 4★ names, re-runs) | a name stays open, and keeps updating, until two sources confirm it. Then it locks: no later notice or wiki reading changes it. An override confirms alone |
| maintenance: pre-install, start, end, compensation | keep updating. An official value replaces the `🕒 estimated from version cadence` line and its countdown |

Why: until this rule, every run rebuilt the link and key art from whatever program posts were still
inside the 72 h lookback. When the real announcement aged out, a same-day giveaway that repeated the
air time took the card over (ZZZ 3.3, 2026-10-09). Nothing remembered which post had opened it.

- A teaser with no air time does not lock, so the real announcement can still take the card and its
  air time.
- Records written before the flag are locked when they carry `program_seen` or `media_from`, and keep
  their link. An explicit `announcement_locked` value always takes precedence over those keys.
- The human fix is `title_url` in `config/overrides.json`. It pins the link and the source button
  together, names the button after its host (`X Post` or `HoYoLAB`), and drops the post it replaces.
  `image` pins the key art. An override always wins, so a locked card can still be corrected by hand.
- **Which post opens the lock.** `schedule.LOCK_RANK` ranks the candidates: X post 3, HoYoLAB and Kuro
  official 2, official news page 1. The highest rank wins, then the earliest post. So the X post wins over
  a HoYoLAB copy of the same announcement. This ranking is separate from `PRIORITY`, which still decides
  which *value* wins (HoYoLAB 50 over X 40). The lock decides where the link points.
- **One upgrade, never a giveaway.** A card locked to a lower rank (HoYoLAB taken while X could not be
  read) moves **once** to a higher-rank post, and only when that post has the same air time and was
  published no later than the lock's own announcement (`announcement_ts`). A later giveaway can never
  upgrade a lock. Records without `announcement_source` / `announcement_ts` get no upgrade.
- **Countdown estimates are unchanged, in all six games.** Before an official notice, maintenance
  start and end still come from the countdown and version-cadence model, labelled as estimates. An
  official value from X, HoYoLAB, Kuro or the launcher replaces it and removes the
  `🕒 estimated from version cadence` line. `test_a_countdown_estimate_is_replaced_by_the_official_notice_in_every_game`
  pins this.
- **Known limit: the first program post seen locks the card.** If a program-titled post with an air time
  (for example a same-window giveaway) is seen before the real announcement, it takes the lock. The
  cross-game check covers the announcement-first order for all six games. The giveaway-first order fails
  for all six: it is a documented limit, not a fixed one. Correct it with `title_url` and `image` in
  `config/overrides.json`.
- **Banners settle once confirmed.** Each banner name has a witness list, one entry per group (`official`,
  `feed`, `wiki`). Two different groups that name the same value confirm it, and a confirmed name is locked
  in `banners_settled`. Two copies of one notice (HoYoLAB and X) are one group, not two. An override
  confirms alone. Re-runs and the 4★ summary come only from the wiki, so they lock only once the wiki names
  them and their phase lists are already locked. A name that only one source gives stays open, and it keeps
  updating as it always did. The full rule is in [BANNER_DATABASE.md](BANNER_DATABASE.md#confirmation-and-the-lock).
- **Not decided:** HoYoverse moving a programme does not move the air time of a locked card. Until
  that is decided, pin `program_ts` in `config/overrides.json`.

## The code gate

A code is posted when **any one** of these is true:
1. it comes from an **official** source: the HoYoLAB livestream module, or an official X /
   HoYoLAB post that explicitly lists redemption codes;
2. a **redeem-validator** (hoyo-codes.seria.moe or Hum-Bao, which both try every code on a real
   account) reports it working, and no validator reports it expired;
3. at least `CODES_MIN_SOURCES` (default **2**) *independent* community sources list it as
   active **and no source lists it as expired**.
   - Open Gacha Codes and ennead count as one source, because they share a backend.
   - PromoGacha copies seria and the wikis, so it counts as whichever of those it copied.
   - The other independent sources are fandom and wuthering.gg.

### Expiry dates come first

If a source gives an explicit *valid until* date and that date has passed, the code is expired,
no matter who else still lists it. This matters because:
- wiki editors often leave 24-hour livestream codes under *Active* for days;
- aggregators never delete anything.

A posted code whose date passes is struck through on the card silently.

Anything else waits as *pending* for up to 14 days and is posted the moment a second source
confirms it. The job summary lists those codes with the reason (`only fandom`). It counts the
already-expired ones in one line (`🧊 HSR: 12 code(s) ignored — already expired`) instead of
listing each. Glued-together codes, placeholders and unmapped reward icons are filtered out
before the gate.
