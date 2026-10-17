# Privacy Policy

**Effective date:** October 17, 2026
**Applies to:** *Game-Express*, the open-source game version-schedule announcer and redemption-code
poster ("the Service"):
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
| Public announcement data (titles, text, times, image links of official posts) | processed **in memory** during a run | building the cards | Discord receives rendered content; source services receive the public requests. Operational logs/summaries can retain source references. |
| Dedup state: version numbers, code strings, Discord **message IDs** of the Service's own posts, the public post ID a card is locked to, confirmed banner names, timestamps, a short non-reversible webhook fingerprint | `state/state.json` **inside the operator's repository** | deduplication and editing its own cards | GitHub and anyone with repository access; a public repository makes committed state public. An explicitly configured peer instance can read its accessible state file. |
| Webhook URLs, optional nitter token | operator's **encrypted GitHub secrets** | authentication | GitHub stores secrets; credentials are sent to their intended service when required. Output redaction/masking is a safeguard, not a guarantee; review logs before sharing them. |

No analytics, telemetry, cookies, tracking pixels, advertising, or profiling. The monitor reads only
public source pages and sends cards to the operator's configured webhooks.

## 4. Third-party services contacted

The Service sends HTTPS requests for public content to the services below.
Recipients can observe request metadata such as the runner IP and requested
URL; configured credentials are sent to the intended service when required:
- HoYoLAB / HoYoverse (news API, livestream code module, HoYoPlay launcher API), and the c3kay.de
  JSON Feed mirror of HoYoLAB news, used only when the HoYoLAB API cannot be reached;
- Kuro Games (official website JSON, launcher index);
- nitter instances (`nitter.cf` and `xitter.cf` first, for single posts and timelines; a token-gated
  instance is used only when the operator sets a token, and the token is sent only to that instance),
  FxTwitter, fixupx and vxTwitter (public X posts);
- hoyo-codes.seria.moe, api.ennead.cc (Open Gacha Codes and the official game calendars for banner names), wuthering.gg, the Fandom game wikis (MediaWiki
  API: code lists and banner lineups), and GitHub / jsDelivr (PromoGacha and Hum-Bao code lists, the
  optional peer-instance state file);
- the official banner notices, found by title through HoYoLAB's search endpoint and Kuro's article menu (for
  Wuthering Waves, a GitHub mirror as a fallback), the community banner feed (`ertezy.github.io`, Kitsudock data), and countdown sites
  (`gachacountdown.online`, `*-countdown.gengamer.in`) for estimated dates;
- Discord (to post and edit the operator's cards through the operator's webhooks).

The operator's scheduler (cron-job.org) only calls GitHub's API to start the workflow. It
receives no data about Discord users.

Each service has its own privacy policy. Links in cards (YouTube, Twitch, HoYoLAB, X, redeem
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
  operational outcomes, source errors and elapsed time. The completion helper
  adds no separate database, JSON report or analytics endpoint. Redaction is
  best effort; operators should review output before publishing it.

## 6. Children

The Service is a developer tool and is not directed at children. It does not knowingly process
Discord member data. Public source content can nevertheless contain information
about people. Discord's own age requirements apply to its users.

## 7. Your choices

- **Operators** can disable any feature (`ENABLED_FEATURES=none`), revoke
  webhooks, or delete the repository at any time.
- **Discord users** can mute the channel or leave the server. Nothing about them is stored by
  the Service.

## 8. Changes

Updates are published in this file with a new effective date and noted in the
[changelog](docs/changelog/CHANGELOG.md).

## 9. Contact

Open an issue in the repository that hosts the instance you are using.
