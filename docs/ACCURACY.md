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
   - **Banners**: only quoted names that directly follow "5-star character" / "S-Rank Agent" /
     "5-star Resonator" (and the 4★ equivalents) in official banner notices. Weapons never
     match.
   - **4★ characters are TBA unless certain.** The names are shown only when the official
     notice lists exactly the expected number of rate-up 4★ (GI 3 · HSR 3 · ZZZ 2 · WW 3), every
     name looks like a real name, and no official source disagrees. Otherwise the card shows
     `4 Star Characters: TBA` and the job summary says why. Once two official posts disagree,
     that phase stays TBA until you confirm the names in `config/overrides.json`.
3. **Merge with provenance.** Priority is *overrides > official notice > official tweet >
   launcher signal > countdown estimate > learned pre-install fallback > banner feed*.
4. **Unknown values are TBA, and banners always carry (STC).** Countdown and learned pre-install
   values are explicitly labelled estimated; neither can overwrite an official value.
5. **Post once** per game + version (`state/state.json`), then **edit silently** when data
   changes. If a moderator deleted the original Discord message, a `404 Unknown Message` causes
   one fresh post whose new message id is adopted; every other edit failure remains an error and
   never reposts. Announcements that are already stale (the program aired more than 36 h ago with
   no pending maintenance) are recorded, not posted.

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
- images are always upgraded to the biggest rendition the source serves (tweet photo → `?name=orig`,
  YouTube → `maxresdefault`), and the card says where the key art came from
  (`🖼️ key art: HoYoLAB — the official announcement`);
- one lookup per version that still needs it, never for a version that is already live, and
  `PROGRAM_MEDIA=0` switches it off.

---

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
