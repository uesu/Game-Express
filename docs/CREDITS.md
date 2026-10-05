# Credits & community resources

Game-Express is a thin layer over other people's work. Everything it reads is someone's
volunteer project, and every card it posts exists because these are kept running — if one of
them asks for support, they have earned it.

**Not affiliated** with HoYoverse, Kuro Games, NetEase or Discord. Game names, artwork and
assets belong to their owners. See [PRIVACY_POLICY.md](../PRIVACY_POLICY.md) and
[TERMS_OF_SERVICE.md](../TERMS_OF_SERVICE.md).

What each endpoint actually serves, and why it was chosen or rejected, is in
[SOURCES.md](SOURCES.md).

---

## Data sources

- [seriaati/hoyo-codes](https://github.com/seriaati/hoyo-codes) and [hoyo-update-notifier](https://github.com/seriaati/hoyo-update-notifier) (the verified code API and the Sophon/launcher endpoints)
- [Ertezy/Kitsudock-data](https://github.com/Ertezy/Kitsudock-data) — the hourly `hub.json` behind the 5★ banner lineups (formerly *Gacha-hub-info*; collector MIT, banner data assembled from the fandom wikis under CC BY-SA 3.0 — Endfield from endfield.wiki.gg, CC BY-SA 4.0), and the [Kitsudock](https://github.com/Ertezy/Kitsudock) launcher it is built for
- [c3kay/hoyolab-rss-feeds](https://github.com/c3kay/hoyolab-rss-feeds) — the HoYoLAB mirror that covers for the API when it bot-checks a CI runner
- [api.ennead.cc](https://api.ennead.cc/) and [Open Gacha Codes](https://github.com/torikushiii/OpenGachaCodes)
- [Hum-Bao/hoyoverse-codes](https://github.com/Hum-Bao/hoyoverse-codes) (redeem-validated code lists)
- [gripcrip-blip/codehub · PromoGacha](https://github.com/gripcrip-blip/codehub)
- [DuolaD/HoYo_Versioncatcher](https://github.com/DuolaD/HoYo_Versioncatcher)
- [RSSHub](https://github.com/DIYgod/RSSHub) (Kuro endpoints)
- [wuthering.gg](https://wuthering.gg/codes)
- The **Fandom wikis** read directly for redemption codes — [Genshin Impact](https://genshin-impact.fandom.com/), [Honkai: Star Rail](https://honkai-star-rail.fandom.com/), [Zenless Zone Zero](https://zenless-zone-zero.fandom.com/) and [Wuthering Waves](https://wutheringwaves.fandom.com/) — and their editors. Wiki text is CC BY-SA 3.0.
- [nitter](https://github.com/zedeus/nitter) (and forks / instances: [git.kareem.one/shaquille/nitter](https://git.kareem.one/shaquille/nitter), [tw.eir-nya.gay](https://tw.eir-nya.gay/), [Cynosphere/nitter](https://gitlab.com/Cynosphere/nitter)), [xcancel](https://xcancel.com/) and **every operator who keeps a public instance online** — they are the reason an announcement is seen minutes after it is tweeted
- [FxTwitter / FixTweet](https://github.com/FixTweet/FxTwitter) (the fallback that resolves a tweet when no mirror answers)

---

## Built with

- [aiohttp](https://github.com/aio-libs/aiohttp), [feedparser](https://github.com/kurtmckee/feedparser), [python-dotenv](https://github.com/theskumar/python-dotenv) — the entire runtime dependency list
- [astral-sh/uv](https://github.com/astral-sh/uv) and [ruff](https://github.com/astral-sh/ruff) (installs and linting), [zizmor](https://github.com/zizmorcore/zizmor) and [rhysd/actionlint](https://github.com/rhysd/actionlint) (workflow auditing), [pypa/gh-action-pip-audit](https://github.com/pypa/gh-action-pip-audit) (CVE checks), [peter-evans/create-pull-request](https://github.com/peter-evans/create-pull-request)
- Discord's [Components V2](https://discord.com/developers/docs/components/reference) and [cron-job.org](https://cron-job.org/) (the external scheduler)

---

## Sibling project

- [News-Express](https://github.com/uesu/News-Express) — same design, different beat

---

## Community databases & resources

Not used by the monitor — these are the sites the community actually reads, collected here so
they are easy to find.

### Solaris — Wuthering Waves

- **Discover Wuthering Waves Lore**: https://wutheringwaves.notion.site/
- **The Shorekeeper (Team Management)**: https://cyzed.com/
- **Wuthering Waves Database**: https://encore.moe/
- **Guides or Builds, Tier Lists, Detailed Information**: https://www.prydwen.gg/wuthering-waves/ · [game8.co/games/Wuthering-Waves](https://game8.co/games/Wuthering-Waves/archives/457465)
- **Character Builds, Tier List, Echoes, Guides, Weapons and their Background Information**: https://wutheringlab.com/
- **Provides Detailed Data to Help Players Navigate the Game World more Efficiently**: https://wuthering.gg/map
- **Built by Wuthering Waves' experienced theorycrafting & speedrunning community**: https://tethys.gg/
- **Official Wiki**: https://wutheringwaves.fandom.com/
- **More**: https://wuthering.gg/ · https://arabwuwa.com/ · https://wuwa.akademiya.app/en · https://wuwatracker.com/characters · https://wuwacompanion.com/en/database · https://www.prydwen.gg/wuthering-waves/characters

### New Eridu — Zenless Zone Zero

- **Database for everything in Zenless Zone Zero**: https://zzz.gachabase.net/?lang=en&branch=beta
- **Guides or Builds, Tier Lists, Detailed Information**: https://www.prydwen.gg/zenless/ · https://www.icy-veins.com/zenless-zone-zero/ · https://www.icy-veins.com/zenless-zone-zero/tier-list · [game8.co/games/Zenless-Zone-Zero](https://game8.co/games/Zenless-Zone-Zero/archives/522597)
- **Information Related to Zenless Zone Zero**: https://zzz.honeyhunterworld.com/?lang=EN · https://zzz-run-archive.onrender.com/
- **Official Wiki**: https://zenless-zone-zero.fandom.com/

### Genshin Impact

https://ambr.top/en · https://lunaris.moe/ · https://e-teyvat.vxnus.xyz/ · https://gensh.honeyhunterworld.com/?lang=EN · https://www.icy-veins.com/genshin-impact/ · https://www.icy-veins.com/genshin-impact/tier-list · https://www.prydwen.gg/genshin-impact/characters

### Honkai: Star Rail

https://hsr.gachabase.net/ · https://www.huroka.com/ · https://hsr.yatta.top/en · https://starrail.honeyhunterworld.com/?lang=EN · https://www.icy-veins.com/honkai-star-rail/ · https://www.prydwen.gg/star-rail/characters/ · https://sk.theherta.com/ · [game8.co/games/Honkai-Star-Rail](https://game8.co/games/Honkai-Star-Rail/archives/404256)

### All HoYoverse + Wuthering Waves · more databases

- **The definitive database for all HoYoverse and Wuthering Waves (Release, Beta & CBT)**: https://gachabase.net/ · https://nanoka.cc/
- **More Database**: https://endfield.teamstardust.org/ · https://silver.teamstardust.org/ · https://www.ntegame.com/ · https://irminsul.gg/ · https://perlica.moe/ · https://endfieldtools.dev/ · https://anantacodex.com/
