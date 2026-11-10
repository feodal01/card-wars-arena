# Terra 6.1 vs. Sonnet 5.5 · 5–0

On November 8, 2026, GPT-6.1 Terra in Codex and Claude Sonnet 5.5 in Claude Code played five games at 100 HP. Both used medium reasoning effort and one continuous session. Terra brought Sonnet to zero HP in every game. The match lasted 20 minutes 56 seconds. The organizer verified ten drafts, 144 actions and five game results. [Interactive replay](trace.html) · [Recorded events](trace.jsonl) · [Results](results.json)

## Five games

The event numbers refer to `seq` in the replay. Select a game, turn and action to compare the board before and after.

| Game | First | Turns | Final HP, Terra / Sonnet | Decisions to inspect |
|---|---|---:|---:|---|
| 1 | Sonnet | 6 | 86 / 0 | Terra's Axey hit an open lane for 13 on turn two. On turn four Terra played Psionic Architect and activated Hunson Abadeer. Sonnet ended that combat at 41 HP (56–64). |
| 2 | Sonnet | 10 | 48 / 0 | Terra opened with two buildings. Sonnet occupied several lanes and led 100–48 after turn seven. On turn eight Terra played Madame Seota and activated Hunson. Combat took Sonnet from 100 to 38 (165–173). Terra ended its turn immediately on turn ten and won in combat. |
| 3 | Terra | 7 | 92 / 0 | Sonnet played its newly drafted Falling Star to reduce the opponent's mana. On turn three Terra spent one mana on Poultrygeist's Floop, gaining two for its next turn. On turn five Terra played Psionic Architect, Blue Slimey and Cave of Solitude, activated Hunson and dealt 75 hero damage (235–238, 250–264). |
| 4 | Terra | 9 | 64 / 0 | Sonnet used Cerebral Bloodstorm, added in its third draft, on turn six. A Woadic Marauder with 34 Attack and 16 HP left the field (347–351). On turn seven Terra rebuilt with Heifergeist and Axey, leaving Sonnet at 23 HP after combat (359–367). |
| 5 | Terra | 7 | 100 / 0 | On turn five Terra played Woadic Marauder, activated Hunson and took Sonnet from 91 to 44 (447–455). On turn seven Madame Seota occupied the fourth lane and combat finished the game (462–469). Terra retained all 100 HP. |

## How the decks changed

**Terra kept the same twenty cards and Hunson Abadeer in all five games.** Its deck contained thirteen creatures, four buildings and three spells. Thirteen cards belonged to Blue Plains and seven were Universal. Hunson gave friendly Blue Plains creatures +8 Attack. Terra activated the power on all seven turns when the engine offered it.

**Sonnet rebuilt twice.** Its first deck contained twenty creatures, eighteen of them Swamp. It replaced three cards before game two and played two of the additions, Evil Eye on turn three and Green Snakey on turn nine. Before game three it changed nine cards and added its first four spells. Falling Star appeared in game three and Cerebral Bloodstorm in game four. Sonnet kept the third deck for games four and five and selected the same Princess Cookie variant in every draft.

## Why Princess Cookie never activated

The original English description of `Leader_SuperPrincessCookie` and the Russian catalog shown during this match both promised +8 Attack to Swamp creatures. The actual hero record sets `forFaction = Cotton`. The activation check and effect both use this field. The current English arena catalog describes the Cotton requirement. [Catalog audit](../../docs/rules-review.md)

Every Sonnet deck consisted entirely of Swamp and Universal cards. On six of its turns the hero cooldown reached zero, but none of its offered action lists contained `hero`. In game two, for example, Sonnet had three creatures on the field and zero cooldown before ending turn seven. Its sole available action was to end the turn (snapshot before event 162).

The engine verifies the 5–0 score. Sonnet's draft matched the description the players received, and the power was unavailable on the field. The outcome under the corrected catalog would require a new match.
