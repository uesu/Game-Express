# ZZZ glossary research: Ju Fufu leak (2026-11-02)

Sources: public fan wikis only (Fandom ZZZ / WuWa wikis, Prydwen, Icy Veins, Honey Hunter, Baidu Baike, Grokipedia). No leaked data.

## Added to `gamexpress/data/glossary/zzz.json` (verified EN usage)
| CN | EN | Source |
|---|---|---|
| 虎啸 | Tiger's Roar | Fandom Ju Fufu page, Prydwen, Baidu |
| 恶虎七式 | Tiger Seven Forms | Fandom: Dash Attack CN 恶虎七式・山君鼎戏 |
| 山君鼎戏 | Mountain King's Game | Fandom Dash Attack name |
| 虎威 | Hu Wei | Companion name; Icy Veins, Honey Hunter |

## Corrections to the reply (not added)
- 猛虎下山 is NOT "Fierce Tiger Descends the Mountain". The EN name for the Dash Attack is Mountain King's Game. 猛虎下山 as a standalone title is unconfirmed.
- 山君鼎戏 is NOT "Mountain Lord's Play". Fandom gives Mountain King's Game.
- 恶虎七式 is NOT "Seven Styles of the Fierce Tiger". Fandom gives Tiger Seven Forms.
- 虎威 is NOT "Tiger's Might" as an item name. Hu Wei is the companion's name.
- 侠肝义胆: Baidu gives the Third Scroll title as "The Chivalrous and Righteous Young Hero". "Chivalrous Heart" is not confirmed. Not added.
- The Lily terms (Slumberland, Dreambind, Cradle Lullaby, Dreambell Chime, Dream Perfume, Wish of Praying Dream, Sillage, Silvered Dream, Floral Blessing, Deep Dream Fragrance, Blooming Dream, Eternal/First Bloom, Dream Aroma, Dream Shelter, Dreamland of Flowers, Into the Dream Cradle, Mend and Cleanse) belong to **Lily (WuWa)**, not ZZZ. They belong in `wuwa.json`, and only after source confirmation.
- Terms not searched or not confirmed: 异放, 星月诗篇, 落羽生花, 憧憬的轮廓, 绮梦绽香, 熏香绽放, 织梦的芬芳, 献花予你, 梦之庇佑, 花束的祝福, 潜能觉醒 (the Potential title itself), 梦愈净瑕, 幻梦调和, 花满梦土, 斑白眠梦, 香尘, 初绽/永绽. None were added.

## Specialty and Daze (correction to the reply)
- Ju Fufu's specialty is **"Stun"** in the EN wiki (Fandom "Stun Specialty Agents"; Ju Fufu infobox "Stun"). Do NOT force Stun → Daze globally. The reply's regex would also break "Stun Specialty".
- The 失衡 mechanic meter is **Daze** in EN ("Daze Multiplier" on Fandom and Icy Veins). Keep Daze for mechanic terms.

## Test filter risk (correction to the reply)
- The reply's `\[.*?[Tt]est.*?\]` pattern would drop titles like `[Testament]`. Use a word boundary (`\btest\b`), which the repo's current `_real_effect_title` already does.

## Still open
- Ju Fufu Potential names and the Potential Awakening text are not in the glossary, so CN still leaks for those lines until the terms are verified.
