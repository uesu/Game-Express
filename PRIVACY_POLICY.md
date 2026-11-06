# Privacy Policy

**Effective date:** November 6, 2026
**Applies to:** *Game-Express*, the open-source game version-schedule announcer, redemption-code
poster, and optional official-news and pre-load/maintenance-started announcer ("the Service"):
- **Automation mode**: GitHub Actions + Discord webhooks.

---

## 1. Short version

**The Service does not collect Discord member data or add analytics, profiling or
sale of personal data.** Public source content can contain names or handles;
the Service processes that content, retains delivery state and produces workflow
logs/summaries. It reads **public game
announcements** (official notices, plus community and wiki pages for banner lineups and estimated dates)
and **public redemption-code lists**, and posts them to **Discord channels controlled by whoever runs
the instance**.

## 2. Who operates it

Every copy is run by the person or community that deploys it: their GitHub repository, their
GitHub Actions minutes and their Discord webhooks. There is no central server, account system,
dashboard, database or Discord bot application run by the author — since v1.7.0 the only runtime
is GitHub Actions.

## 3. Data the Service processes

| Data | Where it lives | Why | Shared? |
|---|---|---|---|
| Public announcement data (titles, text, times, image/video links of official posts) | processed **in memory** during a run | building the cards | Discord receives rendered content; source services receive the public requests. Operational logs/summaries can retain source references. |
| Dedup state: version numbers, code strings, public news/milestone IDs, Discord **message IDs** of the Service's own posts, the public post ID a card is locked to, confirmed banner names, timestamps, a short non-reversible webhook fingerprint | `state/state.json` **inside the operator's repository** | deduplication and editing its own cards | GitHub and anyone with repository access; a public repository makes committed state public. An explicitly configured peer instance can read its accessible state file. |
| Webhook URLs, optional nitter token (`NITTER_RSS_TOKEN`), optional Reddit private feed link/token (`REDDIT_FEED_TOKEN`), optional read-only Discord bot token for the Reddit intake reader (`DISCORD_BOT_TOKEN`), optional Python-bump token (`BUMP_PAT`) | operator's **encrypted GitHub secrets** | authentication | GitHub stores secrets; each credential is sent strictly to its intended service (`NITTER_RSS_TOKEN` only to the allowlisted token-gated mirrors, `REDDIT_FEED_TOKEN` only to official `reddit.com` hosts). Output redaction/masking is a safeguard, not a guarantee; review logs before sharing them. |

No analytics, telemetry, cookies, tracking pixels, advertising, or profiling. The monitor reads only
public source pages and sends cards to the operator's configured webhooks.

## 4. Third-party services contacted

The Service sends HTTPS requests for public content to the services below.
Recipients can observe request metadata such as the runner IP and requested
URL; configured credentials are sent to the intended service when required:
- HoYoLAB / HoYoverse (news API, livestream code module, HoYoPlay launcher & basic-info APIs), and the c3kay.de
  JSON Feed mirror of HoYoLAB news, used only when the HoYoLAB API cannot be reached;
- Kuro Games (official website JSON, global `G153` launcher & background indexes on `kurogame.com` / `kurogames.com` / `aki-game.net` / `aki-game.com`, structured launch media) and NetEase / ANANTA media CDNs (`easebar.com`, `anantagame.com`, `netease.com`, `163.com`);
- nitter instances (`nitter.cf` and `xitter.cf` first, for single posts and timelines; a token-gated
  instance is used only when the operator sets `NITTER_RSS_TOKEN`), `nitter.gq` / `xitter.gq` / `teapawt.org` / `teapaw.org` / `teapawt.net`,
  `nitter.mizuki.st` (trial, 2026-11-06; its feeds are served by the `nitter.meowing.monster` backend) and the
  community-operated reserve mirrors listed in `docs/SOURCES.md`,
  FxTwitter, fixupx and vxTwitter (public X posts);
- Discord's bot REST API (optional, 2026-11-02): with `DISCORD_BOT_TOKEN` + `INTAKE_CHANNEL_ID` set, the monitor reads
  **one operator-designated private channel** (`GET /channels/<id>/messages`, newest-first, at most 800 messages per
  run) to collect the public Reddit post records written there by the operator's own *Gaming Express* Devvit relay
  (Reddit Developer Platform; it stores only post ids and poll counters). Messages that are not relay records are
  skipped and never stored; nothing is written through the bot. The relay's `record.json` attachments (the same
  public post record, untrimmed) are read from `cdn.discordapp.com` without the token, at most 10 per run;
- Reddit and Redlib instances (`www.reddit.com` and `old.reddit.com` public feeds — carrying `REDDIT_FEED_TOKEN`
  query parameters only when configured — public Redlib mirrors, rich-embed proxies `vxreddit.com`, `embedez.com`,
  and `embeddit.deltandy.me`, and the public `arctic-shift.photon-reddit.com` archive as a fallback);
- hoyo-codes.seria.moe, api.ennead.cc (Open Gacha Codes and the official game calendars for banner names), wuthering.gg, the Fandom game wikis across all six games (MediaWiki
  API: code lists and banner lineups), and GitHub / jsDelivr (PromoGacha and Hum-Bao code lists, the
  optional peer-instance state file);
- the official banner notices, found by title through HoYoLAB's search endpoint and Kuro's article menu (for
  Wuthering Waves, a GitHub mirror as a fallback), the community banner feed (`ertezy.github.io`, Kitsudock data), and countdown sites
  (`gachacountdown.online`, `*-countdown.gengamer.in`) for estimated dates;
- Discord (to post and edit the operator's cards through the operator's webhooks);
- when the operator enables the optional beta feature (`BETA_ENABLED=1`), the public community
  databases nanoka.cc (revision manifest and structured per-revision JSON exports) and
  gachabase.net (beta changelog pages). Both are read-only public endpoints; no account, token
  or credential is ever sent to them.

The operator's scheduler (cron-job.org) only calls GitHub's API to start the workflow. It
receives no data about Discord users.

Each service has its own privacy policy. Links in cards (YouTube, Twitch, HoYoLAB, X, Reddit, redeem
pages, and the Discord invite button configured through `COMMUNITY_BUTTONS`) open third-party
sites, and their policies apply.

## 5. Retention

- Dedup state keeps roughly the last 6 versions per game and codes seen within about 120 days.
  After that, entries are pruned automatically.
- State deletion discards deduplication and message-edit history and can cause
  repeated posts or loss of continuity. Preserve a backup; disable the workflow
  instead of resetting state merely to stop the Service.
- Discord retains rendered cards according to the server/platform settings.
- GitHub retains workflow logs and step summaries according to its applicable
  access and retention settings. They can include public source references,
  operational outcomes, source errors and elapsed time. The existing summary output
  adds no separate database, JSON report or analytics endpoint. Redaction is
  best effort; operators should review output before publishing it.

## 6. Children

The Service is a developer tool and is not directed at children. It does not knowingly process
Discord member data. Public source content can nevertheless contain information
about people. Discord's own age requirements apply to its users.

## 7. Your choices

- **Operators** can disable any feature (`ENABLED_FEATURES=none`, `REDDIT_ENABLED=0`,
  `NEWS_ENABLED=0`, `MAINTENANCE_ENABLED=0`), revoke webhooks, or delete the repository at any time.
- **Discord users** can mute the channel or leave the server. Nothing about them is stored by
  the Service.

## 8. Changes

Updates are published in this file with a new effective date and noted in the
[changelog](docs/changelog/CHANGELOG.md).

## 9. Contact

Open an issue in the repository that hosts the instance you are using.


## Optional official-news and milestone processing and retention

When explicitly enabled (`NEWS_ENABLED=1`), news reads full public official article text,
publisher names, publication timestamps and image/GIF/video links from the already listed
HoYoLAB/Kuro services and sends rendered Components V2 messages to dedicated Discord channels:
by default (`NEWS_EXPAND_FULL=0`), full fitting content in one message, longer fitting content
across at most two pages within the 7,000-character policy, or a labelled excerpt with a source
link; when `NEWS_EXPAND_FULL=1` is set, longer articles may span up to an explicit `12`-page /
`120,000`-character / `120`-media cap before falling back to an excerpt. Optional render-only
timestamp conversion (`NEWS_TIMESTAMPS=1`) rewrites exact timezone-qualified date-times into
Discord `<t:…>` tags without altering stored source payloads. The monitor performs bounded media
GET/signature/dimension checks using short in-memory prefixes; it does not store article media as
a dataset. Failed checks refresh the official article once, then hold delivery for retry. Discord
fetches linked media according to its own behavior. Unsupported media remains an original-source
link or notice. No Discord member data or new analytics is added.

When explicitly enabled (`MAINTENANCE_ENABLED=1` with `MAINTENANCE_GAMES`), milestone alerts retain
per-game `preload` and `maintenance` state entries, non-reversible webhook fingerprints, message
IDs, timestamps, version-lock metadata, and bounded post-delivery refresh counters in the existing
`state/state.json`. Signed URL query strings (`auth_key=`) are redacted in summaries and logs.

When explicitly enabled (`BETA_ENABLED=1` with `BETA_GAMES`), beta cards render public
character, weapon and equipment data published by those community databases and post it to
dedicated Discord channels. State retains, per game, the last processed source build,
per-revision/batch delivery status and message IDs, and a bounded readable public-kit snapshot
(skill text, values and item metadata) for source-backed later-revision diffs; it also retains the
splash-art URLs already resolved for a card (so a published card never re-fetches them). It stores
no account, Discord member or analytics data, and writes no beta state when the feature is off.

The existing repository state retains public news IDs, publication times, publication floors,
route/content fingerprints, delivery status and the monitor's own per-part message IDs; partial
entries include minimal discovery metadata for retry. Completed news entries retain up to 30 days,
with a 500-entry/game admission bound shared with partial progress. Safe capacity cleanup can
remove completed entries older than 48 hours sooner, advancing a floor to prevent reposts. Partial
progress remains until completion/review rather than being silently evicted; full capacity defers
new admission. Disabling writes a pause marker once, without new source requests. Repository/Git
history and Discord/log retention are independent of pruning this current JSON. Operators control
visibility and must preserve attribution, state and credentials.
