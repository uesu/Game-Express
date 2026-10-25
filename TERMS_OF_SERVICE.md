# Terms of Service

**Effective date:** October 24, 2026
**Applies to:** *Game-Express*, the open-source game version-schedule announcer, redemption-code
poster, and optional official-news and pre-load/maintenance-started announcer ("the Service"),
running as a GitHub Actions workflow that posts through Discord webhooks.

---

## 1. Acceptance
By deploying, running or modifying an instance of the Service, you agree to these Terms. If you do not agree, do not use it.

## 2. What the Service is
A set of open-source Python scripts that read **public official announcements** (HoYoLAB,
official X accounts, official Reddit accounts and flaired moderator posts, Kuro Games' website,
official launcher APIs), **community and wiki pages** used for banner lineups, backup media/post
resolution, code witnesses and estimated dates (official banner notices found by title, a community
banner feed, game wikis, public nitter/Redlib mirrors, rich-embed proxies, public archives, and
countdown sites), and **public redemption-code lists**, then post formatted cards to Discord
channels that **you** control. There is no hosted service operated by the author on your behalf.
Each operator runs their own instance.

Operational logs and completion summaries are best-effort diagnostics, not
proof of healthy sources, successful delivery or committed/pushed state. Follow
the workflow result and existing per-item logs, review output before sharing it,
and apply the repository/Discord access and retention settings appropriate to
your instance. See [Privacy Policy](PRIVACY_POLICY.md). No separate analytics
service is introduced by completion reporting.

## 3. No affiliation
The Service is **not affiliated with, endorsed by, or sponsored by** HoYoverse / miHoYo, Kuro
Games, NetEase, Discord, X Corp., Reddit, Inc., or any database, mirror or API it reads. All game
names, logos, images, videos and trademarks belong to their respective owners and are shown for
informational purposes.

## 4. Accuracy — STC / TBA
Schedules, banners, maintenance times and codes come from official and community sources and
**can change** without notice:
- **STC = Subject to Change**, and **TBA = To be Announced**.
- Official notices win over estimates. When no official time has been published yet, the card may
  show a community or cadence **estimate** (countdown sites, the community banner feed, learned
  release cadence, or first-observed launcher availability) — always labelled as such on the card
  itself, and replaced automatically when an authoritative official notice arrives.
- **Locks.** Once a card is posted, its title link and key art stay on the announcement it was built
  from. A banner name locks when an official notice confirms it, or when any two reputable sources agree
  (the community feed, the official game calendar, the game wiki), for 5★ and 4★ alike. A locked name is not changed by the feed or the wiki, and an official name is not changed by a
  later official notice either (a conflict is recorded, not applied). Until a name locks, it may change as
  sources update, and an official notice corrects a feed or wiki value. A lock can keep an error in place
  when the sources agreed on it; an operator can correct it through `config/overrides.json`. Maintenance
  details keep updating as official times arrive.
- The Service provides **no guarantee** that any date, banner, reward or code is correct, valid
  in your region, or still active.
- Always confirm in-game or through official channels.

## 5. Operator responsibilities
If you run an instance, you are responsible for:
- **Using webhooks and tokens you own**, and keeping them secret.
- **Following the rules of every service involved**: the [Discord Terms of Service](https://discord.com/terms), the [Discord Developer Policy](https://discord.com/developers/docs/policies-and-agreements/developer-policy), the X/Twitter terms, the Reddit User Agreement and API Terms, and the terms of the APIs and mirrors the Service reads.
- **Respecting sources**: keep the default low request rate (a run every ~5 minutes, with only a few requests per source; a wiki banner lookup and a title search are each repeated at most every three hours while a banner is still TBA, and at most every six hours while it is unconfirmed) and do not use the Service to overload, scrape at high frequency, or resell data.
- **Your server's content**: ping roles, channels, and who can see the posts.

## 6. Acceptable use
Do not use the Service to spam, to impersonate official accounts, to post misleading or altered
announcements, or to redeem codes on other people's accounts. Codes are shown for players to
redeem **on their own accounts**.

## 7. Open source & warranty disclaimer
The Service is provided **"AS IS", without warranty of any kind**, express or implied, including
fitness for a particular purpose and non-infringement. Upstream services may change or disappear
at any time. The Service is built to degrade gracefully, but uninterrupted operation is not
guaranteed.

## 8. Limitation of liability
To the maximum extent permitted by law, the authors and contributors are not liable for any
damages or losses arising from the use of, or inability to use, the Service. This includes
missed announcements, incorrect data, expired codes, Discord or GitHub account actions, or
third-party service outages.

## 9. Termination
Operators can stop the Service at any time by disabling the workflow or revoking webhooks.
Server admins can remove the webhook from their server at any time.

## 10. Changes
These Terms may be updated. Changes are published in this file with a new effective date and
noted in the [changelog](docs/changelog/CHANGELOG.md). Continued use after a change means you accept the updated Terms.

## 11. Contact
Open an issue in the repository that hosts the instance you are using.


## Optional official news, milestone alerts and beta cards

Official news (`NEWS_ENABLED=1`) and pre-load/maintenance-started alerts
(`MAINTENANCE_ENABLED=1` with `MAINTENANCE_GAMES`) are off by default and require explicit
operator opt-in and dedicated per-game webhooks. Operators remain responsible for permission to
redistribute public article text/media, attribution and all upstream source/platform terms. By
default (`NEWS_EXPAND_FULL=0`), fitting articles deliver in at most two validated pages within
7,000 normalized characters or fall back to a labelled one-container excerpt with at most one lead
image and original-source access; setting `NEWS_EXPAND_FULL=1` lifts that ceiling up to an explicit
12-page / 120,000-character / 120-media cap before excerpt fallback. Optional render-time timestamp
conversion (`NEWS_TIMESTAMPS=1`) converts unambiguous source timestamps into Discord `<t:…>` tags.
Failed direct-media preflight or ambiguous webhook responses hold delivery for review rather than
blindly replaying duplicates; checks do not guarantee Discord playback. Wuthering Waves news
discovery uses a bounded current English index (`startTime`, fallback `createTime`), not a complete
archive. Silent baselines, bounded catch-up and retention deliberately avoid historical floods;
partial-delivery or milestone state must not be reset to force tests. These limitations do not
remove the existing warranty, operator responsibility or no-affiliation provisions.

Beta kit and revision-diff cards (`BETA_ENABLED=1` with `BETA_GAMES`) are likewise off by default
and require explicit operator opt-in plus a dedicated channel. They republish character, weapon and
equipment data that the community databases **nanoka.cc** and **gachabase.net** already publish
publicly, and link back to those databases. The Service does not verify that data against the games
themselves: **beta content is provisional by nature and may be incomplete, untranslated, mis-named
or changed without notice before release.** Nothing in a beta card is gameplay advice, a release
date or a guarantee that any value will ship unchanged. Where two retained public snapshots make a
simple value direction unambiguous, the Service may label that line `[BUFF]` or `[NERF]`; all
ambiguous mechanics remain `[CHANGED]`, and a first-seen kit is never assigned a guessed direction.
Operators remain responsible for attribution, for each upstream database's terms, and for any
channel rules that apply to unreleased content. Honkai:
Nexus Anima and ANANTA are excluded until they ship. Off by default, the feature makes no requests
to those databases at all.
