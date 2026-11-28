# Credits & community resources

Game-Express is a thin layer over other people's work. Its official publishers, community
data maintainers, open-source authors and public instance operators make the cards possible.

**Not affiliated** with HoYoverse, Kuro Games, NetEase or Discord. Game names, artwork and
assets belong to their owners. See [PRIVACY_POLICY.md](../PRIVACY_POLICY.md) and
[TERMS_OF_SERVICE.md](../TERMS_OF_SERVICE.md).

What each endpoint actually serves, and why it was chosen or rejected, is in
[SOURCES.md](SOURCES.md).

**Browse:** [Monitor sources](#sources-used-by-the-monitor) · [Tools](#tools-and-contributors) ·
[Sibling project](#sibling-project) · [Community research](#community-databases-and-research)

---

## Sources used by the monitor

### Beta revisions — feature 5

| Publisher | Contribution | Activation |
|---|---|---|
| [nanoka.cc](https://nanoka.cc/) | Ordered build manifest, structured kits and equipment, asset URLs | `BETA_ENABLED=1` |
| [gachabase.net](https://gachabase.net/) | Beta changelog and source comparison links | `BETA_ENABLED=1` |
| [Encore / alt3ri](https://encore.moe/) | Matching current WuWa beta character/weapon fallback via `?v=Beta`, primary and official legacy API endpoints | Missing/unreadable nanoka detail; same request budget |

Feature 5 reads these community databases only when an operator opts in:

- **[nanoka.cc](https://nanoka.cc/)** (`gi.`, `hsr.`, `zzz.`, `ww.` sub-domains) — the revision
  manifest (`static.nanoka.cc/manifest.json`) and the structured per-revision JSON exports this
  feature renders kits from. Thanks to the nanoka maintainers for publishing clean, structured
  data at `static.nanoka.cc/<game>/<revision>/en/<kind>/<id>.json`.
- **[gachabase.net](https://gachabase.net/)** (`gi.`, `hsr.`, `zzz.` sub-domains) — the beta
  changelog (`/<game>.gachabase.net/changelog/beta?lang=en`) that names revisions and usually the
  entries they touch, plus the per-entry before/after diff pages the cards link to
  (`/diff/<kind>/<id>/<slug>?prev=…&cur=…`). When a hotfix heading is blank, Game-Express compares
  its bounded prior nanoka snapshot for only already-tracked/new IDs rather than scraping the UI.

None of these beta hosts is contacted while `BETA_ENABLED` is off. The monitor reads nanoka's structured
JSON and gachabase's Markdown or server-rendered HTML changelog; it does not execute either site's UI
scripts or re-host their images — cards link to the URLs those databases publish.

### News, schedules, codes and fallback sources

Research candidates, not new monitor integrations: [Crimson Witch](https://www.crimsonwitch.com/codes)
(code tracker; also a published upstream of the Ennead HoYo collector),
[heartlog/Hoyocodes](https://github.com/heartlog/Hoyocodes) (Ennead-powered frontend), and the
[Endfield](https://endfield.gryphline.com/en-us/news), [NTE](https://nte.perfectworld.com/en/article/news/index.html)
and [Silver Palace](https://silverpalace.elementagames.com/en-us/news) official news sites.
See [source research](SOURCES.md#research-crimson-witch-hoyocodes-and-prospective-games-2026-11-27)
for evidence and unresolved integration questions. Thanks to [jino9492/subculture-calendar](https://github.com/jino9492/subculture-calendar)
for documenting the Endfield CMS host and app code, and [logreus-cloud/genshinflex](https://github.com/logreus-cloud/genshinflex/issues/53)
for documenting Silver Palace news endpoints.

- [seriaati/hoyo-codes](https://github.com/seriaati/hoyo-codes) and [hoyo-update-notifier](https://github.com/seriaati/hoyo-update-notifier) ([hun.seria.moe](https://hun.seria.moe/)) — the verified code API, the Sophon/launcher endpoints, and the `getGlobalApplicationMaintenance` maintenance gate with its headers and `game_biz` values behind feature 4's *Servers Live* card
- [yeci226/ZZZ](https://github.com/yeci226/ZZZ) — an independent production reader of the same maintenance gate (`src/utilities/news/sources.ts`), used to cross-check the response shape (`application_maintenance: object | null`) and the Star Rail gateway host
- [TheLovinator1/wutheringwaves](https://github.com/TheLovinator1/wutheringwaves) — a GitHub Atom mirror of the Wuthering Waves news list, read only as a fallback for WuWa banner notices. The repository declares no license (checked 2026-10-09).
- [Ertezy/Kitsudock-data](https://github.com/Ertezy/Kitsudock-data) — the hourly `hub.json` behind the 5★ banner lineups (formerly *Gacha-hub-info*; collector MIT, banner data assembled from the fandom wikis under CC BY-SA 3.0 — Endfield from endfield.wiki.gg, CC BY-SA 4.0), and the [Kitsudock](https://github.com/Ertezy/Kitsudock) launcher it is built for
- [c3kay/hoyolab-rss-feeds](https://github.com/c3kay/hoyolab-rss-feeds) — the HoYoLAB mirror that covers for the API when it bot-checks a CI runner
- [api.ennead.cc](https://api.ennead.cc/) ([torikushiii/hoyoverse-api](https://github.com/torikushiii/hoyoverse-api) — both `/codes/…` redemption lists and `/mihoyo/…` event calendar banner lineups) and [Open Gacha Codes](https://github.com/torikushiii/OpenGachaCodes)
- [Hum-Bao/hoyoverse-codes](https://github.com/Hum-Bao/hoyoverse-codes) (redeem-validated code lists)
- [gripcrip-blip/codehub · PromoGacha](https://github.com/gripcrip-blip/codehub)
- [DuolaD/HoYo_Versioncatcher](https://github.com/DuolaD/HoYo_Versioncatcher) (HoYoPlay launcher endpoint references)
- **[DynamiByte](https://github.com/DynamiByte)** — the [HoyoPlay launcher API endpoint notes](https://gist.github.com/DynamiByte/0ad250bbe1930e2736a6d4e6e842bcb2) and the [Wuthering Waves launcher API endpoint notes](https://gist.github.com/DynamiByte/d839bf9f671c975b6666d0f6e6634641) that document the `hyp/hyp-connect/api` base with `launcher_id`, Kuro's `<appId>_<appKey>/<gameId>` CDN path (`50004_…` + `G153`), the stable `launcher-config` endpoint and the rotating `functionCode.background` hash that `sources/launcher.py` and `sources/kuro.py` follow. The WuWa notes credit [Cheu3172/Wuwa-Web-Request](https://github.com/Cheu3172/Wuwa-Web-Request) for most of the original endpoint discovery.
- [TwintailTeam/TwintailLauncher](https://github.com/TwintailTeam/TwintailLauncher) / [TwintailTeam/game-manifests](https://github.com/TwintailTeam/game-manifests) and [TomyJan/GenshinImpact-Client-Version](https://github.com/TomyJan/GenshinImpact-Client-Version) — open-source launcher/manifest references documenting the Kuro `G153` global launcher index and `background/{hash}/en.json` schemas (`sources/kuro.py`)
- [RSSHub](https://github.com/DIYgod/RSSHub) (Kuro news endpoints)
- [wuthering.gg](https://wuthering.gg/codes)
- [gengamer.in](https://genshin-countdown.gengamer.in/) (`{genshin,hsr,zenless,wuthering}-countdown.gengamer.in`) and [gachacountdown.online](https://gachacountdown.online/) — community version countdown sites read only as provisional estimated fallbacks when no official date has been published yet (`sources/countdown.py`)
- The **Fandom wikis** read directly for both redemption codes (`sources/codes.py`) and structured version banner lineups (`sources/gachawiki.py`) — [Genshin Impact](https://genshin-impact.fandom.com/), [Honkai: Star Rail](https://honkai-star-rail.fandom.com/), [Zenless Zone Zero](https://zenless-zone-zero.fandom.com/), [Wuthering Waves](https://wutheringwaves.fandom.com/), [Honkai: Nexus Anima](https://honkai-nexus-anima.fandom.com/) and [ANANTA](https://ananta.fandom.com/) — and their editors. Wiki text is CC BY-SA 3.0.
- [nitter](https://github.com/zedeus/nitter) (and active forks / instances including [4cuck/teapawt](https://github.com/4cuck/teapawt), [shitter](https://codeberg.org/shitter/shitter), [git.kareem.one/shaquille/nitter](https://git.kareem.one/shaquille/nitter), [tw.eir-nya.gay](https://tw.eir-nya.gay/), [Cynosphere/nitter](https://gitlab.com/Cynosphere/nitter)), [status.d420.net](https://status.d420.net/) (public mirror health tracking), xcancel (*service suspended — kept last in `DEFAULT_NITTER` as a dead historical entry, never deleted*) and **every operator who keeps a public instance online** — they are the reason an announcement is seen minutes after it is tweeted
- [FxEmbed / FxTwitter](https://github.com/FxEmbed/FxEmbed) (*formerly FixTweet/FxTwitter*, MIT — the fallback that resolves a tweet when no nitter mirror answers; fixupx and [BetterTwitFix / vxTwitter](https://github.com/dylanpdx/BetterTwitFix) follow it)
- [redlib](https://github.com/redlib-org/redlib) (plus [redlib-instances](https://github.com/redlib-org/redlib-instances) and active fork [mitchross/redlib](https://github.com/mitchross/redlib)), [eddrit](https://github.com/corenting/eddrit), and **every public Redlib / eddrit operator**, plus [vxReddit](https://www.vxreddit.com), [EmbedEZ](https://embedez.com) and [Arctic Shift](https://arctic-shift.photon-reddit.com) — the Reddit backup and community-witness chain across all six games

---

## Tools and contributors

- [aiohttp](https://github.com/aio-libs/aiohttp), [feedparser](https://github.com/kurtmckee/feedparser), [python-dotenv](https://github.com/theskumar/python-dotenv) — the entire runtime dependency list
- [astral-sh/uv](https://github.com/astral-sh/uv), [ruff](https://github.com/astral-sh/ruff), [pytest](https://github.com/pytest-dev/pytest) and [PyYAML](https://github.com/yaml/pyyaml) (installs, linting and offline/workflow verification), [zizmor](https://github.com/zizmorcore/zizmor), [rhysd/actionlint](https://github.com/rhysd/actionlint) and [reviewdog/action-actionlint](https://github.com/reviewdog/action-actionlint) (workflow auditing), [pypa/gh-action-pip-audit](https://github.com/pypa/gh-action-pip-audit) (CVE checks), [peter-evans/create-pull-request](https://github.com/peter-evans/create-pull-request)
- Discord's [Components V2](https://discord.com/developers/docs/components/reference), [Discohook](https://discohook.app) (payload inspection), and [cron-job.org](https://cron-job.org/) (the external scheduler)

---

## Sibling project

- [News-Express](https://github.com/uesu/News-Express) — same design, different beat

---

## Community databases and research

Additional reading and research references. Listing a project here does not enable polling;
active integrations are identified above and in [SOURCES.md](SOURCES.md).

### Solaris — Wuthering Waves

- **Discover Wuthering Waves Lore**: https://wutheringwaves.notion.site/
- **The Shorekeeper (Team Management)**: https://cyzed.com/
- **Wuthering Waves Database**: https://encore.moe/
- **Guides or Builds, Tier Lists, Detailed Information**: https://www.prydwen.gg/wuthering-waves/ · [game8.co/games/Wuthering-Waves](https://game8.co/games/Wuthering-Waves/archives/457465)
- **Character Builds, Tier List, Echoes, Guides, Weapons and their Background Information**: https://wutheringlab.com/
- **Provides Detailed Data to Help Players Navigate the Game World more Efficiently**: https://wuthering.gg/map
- **Built by Wuthering Waves' experienced theorycrafting & speedrunning community**: https://tethys.gg/
- **Community wiki**: https://wutheringwaves.fandom.com/
- **More**: https://wuthering.gg/ · https://arabwuwa.com/ · https://wuwa.akademiya.app/en · https://wuwatracker.com/characters · https://wuwacompanion.com/en/database · https://www.prydwen.gg/wuthering-waves/characters

### New Eridu — Zenless Zone Zero

- **Database for everything in Zenless Zone Zero**: https://zzz.gachabase.net/?lang=en&branch=beta
- **Guides or Builds, Tier Lists, Detailed Information**: https://www.prydwen.gg/zenless/ · https://www.icy-veins.com/zenless-zone-zero/ · https://www.icy-veins.com/zenless-zone-zero/tier-list · [game8.co/games/Zenless-Zone-Zero](https://game8.co/games/Zenless-Zone-Zero/archives/522597)
- **Information Related to Zenless Zone Zero**: https://zzz.honeyhunterworld.com/?lang=EN · https://zzz-run-archive.onrender.com/
- **Community wiki**: https://zenless-zone-zero.fandom.com/

### Genshin Impact

https://ambr.top/en · https://lunaris.moe/ · https://e-teyvat.vxnus.xyz/ · https://gensh.honeyhunterworld.com/?lang=EN · https://www.icy-veins.com/genshin-impact/ · https://www.icy-veins.com/genshin-impact/tier-list · https://www.prydwen.gg/genshin-impact/characters

### Honkai: Star Rail

https://hsr.gachabase.net/ · https://www.huroka.com/ · https://hsr.yatta.top/en · https://starrail.honeyhunterworld.com/?lang=EN · https://www.icy-veins.com/honkai-star-rail/ · https://www.prydwen.gg/star-rail/characters/ · https://sk.theherta.com/ · [game8.co/games/Honkai-Star-Rail](https://game8.co/games/Honkai-Star-Rail/archives/404256)

### All HoYoverse + Wuthering Waves · more databases

- **The definitive database for all HoYoverse and Wuthering Waves (Release, Beta & CBT)**: https://gachabase.net/ · https://nanoka.cc/
- **More Database**: https://endfield.teamstardust.org/ · https://silver.teamstardust.org/ · https://www.ntegame.com/ · https://irminsul.gg/ · https://perlica.moe/ · https://endfieldtools.dev/ · https://anantacodex.com/

### Launcher API research

- **[DynamiByte](https://github.com/DynamiByte) (Leandro Baldassarre)** — [HoyoPlay endpoints](https://gist.github.com/DynamiByte/0ad250bbe1930e2736a6d4e6e842bcb2) and [Wuthering Waves launcher endpoints](https://gist.github.com/DynamiByte/d839bf9f671c975b6666d0f6e6634641). These describe the URL shapes and constants the two launcher adapters call; every response is still fetched and validated live by Game-Express, and a gist describing an endpoint is not proof that its payload is stable.
- **[Cheu3172/Wuwa-Web-Request](https://github.com/Cheu3172/Wuwa-Web-Request)** — the original WuWa launcher/web request research credited by the WuWa notes above.

### Additional source research supplied for feature 5

- **[Encore](https://encore.moe/)** / **[alt3ri](https://github.com/alt3ri)** — [about and upstream acknowledgements](https://encore.moe/about), [API v2 reference](https://api-v2.encore.moe/_docs/scalar), [new content](https://encore.moe/new), [game notices](https://encore.moe/gamenotice), [characters](https://encore.moe/character), [weapons](https://encore.moe/weapon), [echoes](https://encore.moe/echo) and the [version comparison](https://encore.moe/diff?lang=en). The live frontend and API expose beta resources with `?v=Beta`, omitted from the supplied OpenAPI export. Encore now supplies a bounded current-build character/weapon fallback; [the source contract and limitations](SOURCES.md#encore-beta-api-fallback-for-wuwa) explain version checks, attribution and historical limits.
- **[Arikatsu/WutheringWaves_Data](https://github.com/Arikatsu/WutheringWaves_Data)** (formerly `WW_Data`), **[alt3ri/WW_Asset](https://github.com/alt3ri/WW_Asset)** and **[WW_Asset_Webp](https://github.com/alt3ri/WW_Asset_Webp)** — data and asset references acknowledged by Encore. The inspected data README describes release 3.7; release assets alone do not establish beta revisions.
- Encore additionally acknowledges **[Arikatsu](https://github.com/Arikatsu)**, **[Adam](https://github.com/NotFakeAdam)**, **[Hiro420](https://github.com/Hiro420)**, **[Hakush.in](https://hakush.in/)**, **[KuroBBS](https://wiki.kurobbs.com/mc/home)** and its community. These are Encore's acknowledgements, not claims that Game-Express uses every project.
- **[Wuthery/kuro.py](https://github.com/Wuthery/kuro.py)** ([PyPI](https://pypi.org/project/kuro.py/)) — KuroBBS/game-account API wrapper, not an ordered beta feed.
- **[seriaati/ZenlessAssetScrape](https://github.com/seriaati/ZenlessAssetScrape)** — asset research; its README recommends Hakushin's API. Official [Genshin character pages](https://genshin.hoyoverse.com/en/character/mondstadt) provide published character context, not a beta history contract.
- **[Discohook documentation](https://docs.discohook.app/)** ([text index](https://docs.discohook.app/llms.txt)) — reference for inspecting and editing Discord payloads; a manual edit succeeding does not establish the cause of an earlier unresolved media response.

### Feature 3 follow-up research

Thanks to the official NTE, GRYPHLINE Endfield and Silver Palace publishers and their CDN/API
operators for the article text and native media used in the inactive candidate research. Thanks
also to HoYoLAB and YouTube for the official post and verified thumbnail reference. The
[SKPORT API documentation community project](https://github.com/AixLnyt/skport-api-docs) helped
scope research; its account/game APIs are **not** used as an official community-news feed.
Read-only GitHub Actions probes, aiohttp, pytest and Ruff supported the fidelity checks; see
[the evidence and limits](SOURCES.md#feature-3-follow-up-bounded-fidelity-audit-and-skport-2026-11-27).
