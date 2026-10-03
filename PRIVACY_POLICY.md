# Privacy Policy

**Effective date:** October 2, 2026
**Applies to:** *Game-Express*, the open-source game version-schedule announcer and redemption-code
poster ("the Service"):
- **Automation mode**: GitHub Actions + Discord webhooks.

---

## 1. Short version

**The Service collects, stores, sells and shares no personal data.** It reads **public, official
game announcements** and **public redemption-code lists**, and posts them to **Discord channels
controlled by whoever runs the instance**.

## 2. Who operates it

Every copy is run by the person or community that deploys it: their GitHub repository, their
GitHub Actions minutes and their Discord webhooks. There is no central server, account system,
dashboard, database or Discord bot application run by the author — since v1.7.0 the only runtime
is GitHub Actions.

## 3. Data the Service processes

| Data | Where it lives | Why | Shared? |
|---|---|---|---|
| Public announcement data (titles, text, times, image links of official posts) | processed **in memory** during a run | building the cards | only sent to the operator's Discord webhooks |
| Dedup state: version numbers, code strings, Discord **message IDs** of the Service's own posts, timestamps, a short non-reversible webhook fingerprint | `state/state.json` **inside the operator's repository** | never posting twice; editing its own cards | no |
| Webhook URLs, optional nitter token | operator's **encrypted GitHub secrets** | authentication | no. They are never logged; GitHub masks secrets in logs |

No analytics, telemetry, cookies, tracking pixels, advertising, or profiling. The monitor reads only
public source pages and sends cards to the operator's configured webhooks.

## 4. Third-party services contacted

The Service sends ordinary HTTPS requests (no personal data) to:
- HoYoLAB / HoYoverse (news API, livestream code module, HoYoPlay launcher API);
- Kuro Games (official website JSON, launcher index);
- nitter instances, FxTwitter and vxTwitter (public X posts);
- hoyo-codes.seria.moe, api.ennead.cc (Open Gacha Codes), wuthering.gg, Fandom (MediaWiki API),
  and GitHub / jsDelivr (PromoGacha and Hum-Bao code lists, the optional peer-instance state
  file);
- Discord (to post and edit the operator's cards through the operator's webhooks).

The operator's scheduler (cron-job.org) only calls GitHub's API to start the workflow. It
receives no data about Discord users.

Each service has its own privacy policy. Links in cards (YouTube, Twitch, HoYoLAB, X, redeem
pages, and the Discord invite button configured through `COMMUNITY_BUTTONS`) open third-party
sites, and their policies apply.

## 5. Retention

- Dedup state keeps roughly the last 6 versions per game and codes seen within about 120 days.
  After that, entries are pruned automatically.
- Operators can delete `state/state.json` at any time; the next run silently re-seeds.
- Nothing else is retained: a run holds the announcement data it fetched in memory and exits.

## 6. Children

The Service is a developer tool and is not directed at children. It does not knowingly process
data from anyone. Discord's own age requirements apply to its users.

## 7. Your choices

- **Operators** can disable any feature (`ENABLED_FEATURES=none`), revoke
  webhooks, or delete the repository at any time.
- **Discord users** can mute the channel or leave the server. Nothing about them is stored by
  the Service.

## 8. Changes

Updates are published in this file with a new effective date and noted in the README changelog.

## 9. Contact

Open an issue in the repository that hosts the instance you are using.
