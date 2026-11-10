# Terra 6.1 vs. Sonnet 5.5 · English-catalog rematch · 4–1

GPT-6.1 Terra (Codex, medium) won the first four games. Claude Sonnet 5.5 (Claude Code, medium) won the fifth with 81 HP. All five games ended on hero health. Both seats received the same corrected English catalog, with 258 cards, 72 heroes and 100 starting HP. The verified trace spans 36 minutes 55 seconds from match start to match end, including the drafts and loading. [Replay](trace.html) · [Result](results.json) · [Original trace](trace.jsonl)

## Five decisions to replay

The HP columns below always list Terra first. Event numbers are the `seq` field in the viewer. Select the indicated game and turn to inspect the choices, the before and after states, and the wheel.

| Game | First player | Turns | Final HP | What decided the game |
|---|---|---:|---|---|
| 1 | Sonnet | 14 | 25 / 0 | On turn six, Terra used Spectre Hector's Floop to return the blocker in front of it to Sonnet's hand. Its 23 Attack went through the open lane (77–84). On turn twelve, Axey and Poultrygeist joined the board, Hunson boosted the attackers, and combat left Sonnet at 2 HP (137–147). Sonnet reduced Terra to 25 before Terra finished on turn fourteen. |
| 2 | Terra | 9 | 100 / 0 | Ethan Allfire was Sonnet's only creature after turn eight. Terra spent one mana on Lonely Hearts to remove it, added Silo of Truth and activated Hunson. All four lanes were open, and Sonnet went from 77 HP to zero in that combat (271–283). |
| 3 | Sonnet | 12 | 54 / 0 | Sonnet spent BMO's extra mana on three plays on turn five (346–358) and led 100–77 after turn seven. Terra's 25-Attack Temporal Wisp rolled a critical on turn eight, taking Sonnet from 100 to 50 (379–383). Bog Frog Bomb's Floop later removed Axey (409–410), but Terra rebuilt, activated Hunson and dealt the remaining 50 on turn twelve (421–425). |
| 4 | Terra | 13 | 24 / 0 | Sonnet used BMO, played Dr. Death, activated its Floop and added Evil Eye. Combat took Terra from 81 to 31 (527–540). At 24 HP, Terra survived another turn. Sonnet's last Bog BanShe Angel attacked Madame Seota and rolled a defensive Crit for Terra: the counterattack removed the Angel (575–582). Terra then boosted three attackers facing empty lanes and finished (584–588). |
| 5 | Sonnet | 11 | 0 / 81 | Sonnet used BMO to play and Floop Chest Burster. The Floop dealt 4 hero damage, then attackers in three open lanes dealt 39, leaving Terra at 15 (696–706). Terra returned Bog BanShe Angel to hand with Ultimate Magic Hands and played Axey. Sonnet replayed the Angel opposite an empty lane, gave it Ghost Castle for 32 Attack and finished (708–727). |

## Decks and adaptation

**Terra kept Hunson Abadeer and the same twenty card IDs through all five drafts.** Thirteen Plains and seven Universal cards gave it thirteen creatures, four buildings and three spells. The hero's +8 Attack affected friendly Plains creatures already on the board. Terra activated it thirteen times. Lonely Hearts removed a lone defender in game two, and Temporal Wisp's critical in game three shows how a buffed creature can convert an open lane into 50 hero damage.

**Sonnet made two roster changes.** It began with Cinnamon Bun and a Corn deck. After game one, it replaced two cards with Wall of Ears and Ethan Allfire to put cheaper bodies on the board. Both additions saw play in game two. Cinnamon Bun activated three times in game one and once in game two.

After falling behind 0–2, Sonnet changed eighteen cards and switched to BMO. Its new deck contained twelve Swamp and eight Universal cards, with sixteen creatures and four buildings. Its draft comment identified mana for creature Floops as the reason. It kept that exact roster for games four and five. It used BMO twice in each of the three games, including for Dr. Death in game four and Chest Burster in game five.

**A missed defensive outcome is visible in game four.** On turn twelve, Sonnet planned for Bog BanShe Angel to kill the wounded Madame Seota. The defense wheel instead rolled a counterattack, which removed the Angel. With Terra at 24 HP and Sonnet still at 48, that single exchange left three lanes exposed for Terra's next turn. The roll and the before/after boards are visible at events 581–585.

## Comparison with the earlier match

The [earlier match](../2026-11-08-terra-sonnet-medium/review.md) ended 5–0. Sonnet picked the Super Princess Cookie variant five times under the old description, drafted no Cotton cards and never had access to its power. In the rematch it selected Cinnamon Bun and BMO and activated its heroes ten times. Terra's first deck retained eighteen of the twenty cards from its earlier first deck. The rematch used a fresh seed and fresh sessions. The difference in score alone cannot establish the effect of fixing the catalog.

## Trace coverage

One match trace contains ten accepted decks, 231 accepted actions (116 Terra, 115 Sonnet), 113 wheel events and five game results. Both players attached English explanations to every deck submission and at least one decision in each of the 59 card-play turns. There are 77 decision comments, including comments on landscape placement and additional actions. The public comments describe the players' stated plans. The actual outcomes above come from the engine snapshots.

Match seed: `5532167097018958320`. Ruleset: `cardwars-v3-en-noobs258-20-bo5-landfirst-hp100`.
