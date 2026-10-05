# Terms of Service

**Effective date:** October 2, 2026
**Applies to:** *Game-Express*, the open-source game version-schedule announcer and redemption-code
poster ("the Service"), running as a GitHub Actions workflow that posts through Discord webhooks.

---

## 1. Acceptance
By deploying, running or modifying an instance of the Service, you agree to these Terms. If you do not agree, do not use it.

## 2. What the Service is
A set of open-source Python scripts that read **public official announcements** (HoYoLAB,
official X accounts, Kuro Games' website, official launcher APIs) and **public redemption-code
lists**, then post formatted cards to Discord channels that **you** control. There is no hosted
service operated by the author on your behalf. Each operator runs their own instance.

## 3. No affiliation
The Service is **not affiliated with, endorsed by, or sponsored by** HoYoverse / miHoYo, Kuro
Games, NetEase, Discord, X Corp., or any database or API it reads. All game names, logos, images
and trademarks belong to their respective owners and are shown for informational purposes.

## 4. Accuracy — STC / TBA
Schedules, banners, maintenance times and codes come from official and community sources and
**can change** without notice:
- **STC = Subject to Change**, and **TBA = To be Announced**.
- Official sources always win. When no official time has been published yet, the card may show a
  community **estimate** (countdown sites, the community banner feed) — always labelled as such
  on the card itself, and replaced automatically the moment the official notice appears.
- The Service provides **no guarantee** that any date, banner, reward or code is correct, valid
  in your region, or still active.
- Always confirm in-game or through official channels.

## 5. Operator responsibilities
If you run an instance, you are responsible for:
- **Using webhooks and tokens you own**, and keeping them secret.
- **Following the rules of every service involved**: the [Discord Terms of Service](https://discord.com/terms), the [Discord Developer Policy](https://discord.com/developers/docs/policies-and-agreements/developer-policy), the X/Twitter terms, and the terms of the APIs the Service reads.
- **Respecting sources**: keep the default low request rate (a run every ~5 minutes, with only a few requests per source) and do not use the Service to overload, scrape at high frequency, or resell data.
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
