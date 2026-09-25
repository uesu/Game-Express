# Privacy Policy

**Effective date:** September 25, 2026
**Applies to:** *Game-Express*, the open-source game version-schedule announcer and redemption-code
poster ("the Service"), in both of its modes:
- **Automation mode**: GitHub Actions + Discord webhooks.
- **Bot mode**: an optional self-hosted Discord bot with slash commands.

---

## 1. Short version

**The Service collects, stores, sells and shares no personal data.** It reads **public, official
game announcements** and **public redemption-code lists**, and posts them to **Discord channels
controlled by whoever runs the instance**.

## 2. Who operates it

Every copy is **self-hosted** by the person or community that deploys it: their GitHub
repository, their Discord webhooks, and their optional bot. There is no central server, account
system, dashboard or database run by the author.

## 3. Data the Service processes

| Data | Where it lives | Why | Shared? |
|---|---|---|---|
| Public announcement data (titles, text, times, image links of official posts) | processed **in memory** during a run | building the cards | only sent to the operator's Discord webhooks |
| Dedup state: version numbers, code strings, Discord **message IDs** of the Service's own posts, timestamps, a short non-reversible webhook fingerprint | `state/state.json` **inside the operator's repository** or host | never posting twice; editing its own cards | no |
| Webhook URLs, bot token, optional nitter token | operator's **encrypted GitHub secrets** or host environment variables | authentication | no. They are never logged; GitHub masks secrets in logs |
| **Bot mode**: slash-command interactions (command name, chosen game, interaction ID/token) | processed **in memory** to send the reply | answering `/codes`, `/schedule`, `/status` | no. User IDs, usernames and message content are **not stored** |

No analytics, telemetry, cookies, tracking pixels, advertising, or profiling. The bot requests
**no privileged intents** and cannot read server messages or member lists.

## 4. Third-party services contacted

The Service sends ordinary HTTPS requests (no personal data) to:
- HoYoLAB / HoYoverse (news API, livestream code module, HoYoPlay launcher API);
- Kuro Games (official website JSON, launcher index);
- nitter instances, FxTwitter and vxTwitter (public X posts);
- hoyo-codes.seria.moe, api.ennead.cc (Open Gacha Codes), wuthering.gg, Fandom (MediaWiki API),
  and GitHub / jsDelivr (PromoGacha and Hum-Bao code lists, the optional peer-instance state
  file);
- Discord (to post and edit the operator's cards and answer slash commands).

The operator's scheduler (cron-job.org) only calls GitHub's API to start the workflow. It
receives no data about Discord users.

Each service has its own privacy policy. Links in cards (YouTube, Twitch, HoYoLAB, X, redeem
pages, and the Discord invite button configured through `COMMUNITY_BUTTONS`) open third-party
sites, and their policies apply.

## 5. Retention

- Dedup state keeps roughly the last 6 versions per game and codes seen within about 120 days.
  After that, entries are pruned automatically.
- Operators can delete `state/state.json` at any time; the next run silently re-seeds.
- Slash-command data is not retained.

## 6. Children

The Service is a developer tool and is not directed at children. It does not knowingly process
data from anyone. Discord's own age requirements apply to its users.

## 7. Your choices

- **Operators** can disable any feature (`ENABLED_FEATURES=none`), remove the bot, revoke
  webhooks, or delete the repository at any time.
- **Discord users** can mute the channel or leave the server. Nothing about them is stored by
  the Service.

## 8. Changes

Updates are published in this file with a new effective date and noted in the README changelog.

## 9. Contact

Open an issue in the repository that hosts the instance you are using.
