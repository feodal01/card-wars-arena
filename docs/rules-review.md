# Card Wars rules and catalog audit

The November 8 review compared the recovered mobile scripts, the isolated arena project, the instructions delivered over MCP and recorded match events. The active pool contains 183 creatures, 48 spells, 27 buildings and 72 heroes. These 330 entries use 189 distinct effect classes. The independent review traced activation and target requirements, side, timing, numeric fields and the method that applies each effect.

## Build and inspect the player catalog

```sh
uv run cardwars catalog --project "$CARDWARS_UNITY_PROJECT" --check-sources --output catalog.md
```

The player-facing catalog is also built when the host prepares a run. The original English strings are stored in Unity's `Assets/Resources/languages/EN_*.txt`. The four `db_*.json` Blueprint tables identify the name, effect script, faction, edition, stats, prices and per-entry parameters. Engine-only constants can come from the executing C# statement. For example, the mana awarded by a sacrifice comes from `DestroyEntityForAction.DoResult`, and the reshuffle draw comes from the draw loop. Faction and card-type enum values are resolved against the same project. Script-specific English templates express the reviewed targeting and timing. Unmodified effects use the English game text and parameter substitution. The dataset includes cards whose original English description disagrees with the implementation.

The optional source check compares hashes of the local effect classes and shared engine code to the recorded build and names any changed files. A successful comparison establishes source identity with this baseline. It cannot prove equivalence for every board state or automatically explain a new effect implementation. Review changes to an effect before updating its baseline. [Catalog builder](../cardwars/arena/catalog.py) · [Source check](../cardwars/arena/catalog_audit.py)

| Draft decision | Source evidence |
|---|---|
| Princess Cookie gives friendly Swamp creatures +4 Attack. The Super version gives friendly Cotton creatures +8. At least one matching creature must be in play. | `ATKBonusFactionCreaturesLeader.CanPlay/Cast` reads that hero's `forFaction`. The original English text for the Super version says Swamp. |
| White Ninja deals 3 damage to the opposing creature and heals itself for 2. | `DamageOpponentHealSelf` uses different fields for damage and healing. |
| Sand Sphinx reduces each packet of damage to the creature in its lane by 5. | `DamageReduction` works through `CreatureScript.TakeDamage`. It can save a creature from a spell that deals its remaining HP as damage. |
| Corn Parthenon counts distinct landscape types on its owner's side. The bonus is removed when the building leaves. | `ATKBonusLandscapes.OnCardEnterPlay/OnCardLeftPlay` counts the owner's landscape types. |
| Pick an occupied friendly lane for Fairy Shepard's Floop. | `HealTargetAdjacent.SelectionFilter` may also accept an empty lane beside a wounded creature, but `DoHealing/DoResult` expects the selected lane to contain a creature. |

The Terra–Sonnet match predates these corrections. Sonnet drafted Super Princess Cookie five times and took zero Cotton cards. Across all five games the engine never offered the hero action to Sonnet. [Match analysis](../results/2026-11-08-terra-sonnet-medium/review.md)

## Engine checks

The reference export is the recovered mobile project under `recovered-fixed-export/ExportedProject/Assets/Scripts/Assembly-CSharp`. The arena uses the Blueprint tables under `Assets/StreamingAssets/Blueprints` in its isolated project.

| Mechanic | Verified behavior | Methods or evidence |
|---|---|---|
| Landscapes | Deck composition supplies four tiles. The starting player places all four, then the opponent places four, then card play begins. The original single-player game lets the human confirm placement before the client places the computer's side. | `CWDeckController.SetLandscapes`, `CWLandscapeCardDragOld.PlaceLandscape`, `LandscapeReadyButtonScript.OnClick`, `ArenaOpening.CreateDeck`, `ArenaMatch.BuildChoices` |
| Hand and mana | Both start with five cards and two base mana. A player draws on their own turn when below the seven-card hand limit. Base mana increases each round up to ten and replaces leftover ordinary mana. | `GameState.Setup/StartTurn/DrawCard/EndTurn`, `CWStartTurnTrigger.StartTurn`, `db_Parameters.json` |
| Play and cost | Each lane holds one creature and one building. Replacing a card of the same type sends it to discard. Faction, landscape, mana, discounts and script-specific targets determine legal choices. Spell mana is spent before ordinary mana on spells. | `CardForm.CanPlay/DetermineCost`, `CardScript.CanPlay/DetermineCost`, `GameState.CastSpell/DoResultSummon` |
| Floop | A creature on the field can activate its Floop for the current cost when its conditions are met. The flag usually resets at the start of its owner's next turn. A flooped creature can attack. | `GameState.CanFloopCard/FloopCard/UnfloopCard`, `CardScript.DetermineFloopCost`, `CWBattleSequenceController.BattleAction` |
| Hero power | Availability depends on cooldown and any script requirements. A player can save an available power. Using it restarts the cooldown. Ending the owner's turn reduces a positive counter by one. | `LeaderItem.CanPlay`, `LeaderScript.CanPlay`, `GameState.Setup/UseLeaderAbility/EndTurn` |
| Attacks | Players can end their turn with mana left. Turn one ends without attacking. The second player attacks first. A attacks in lane order 0–3 and B in reverse. An attack restriction or protected opposing creature stops the lane's attack. A helpless defender can allow damage through to the hero. The faction-pair damage modifiers in `db_RPS.json` are all zero. | `CWBattleSequenceController.BattleSequencePlay/BattleAction`, `CreatureBattleScript.DealDamage`, `ArenaCombat.Resolve` |
| Wheel | Sectors use the engine's current modifiers. For an eligible spin the arena draws a uniformly random stop position. Seat A's perspective stays fixed. The attack and defense rings have different outcomes. | `CWBattleSequenceController.RingStart/SetUpRing/StopRing/GetTweenTarget`, trace `wheel` events |
| Empty deck | If the active player's deck is empty at the beginning of their turn, they lose HP equal to their hero rank. Arena heroes are rank one. The mobile client also offers a reshuffle choice. | `GameState.StartTurn/DoResultBleed`, `CWOutOfCardsApplyBleed`, `CWOutOfGemBranch`, `ArenaCombat.Resolve` |
| Visibility | Seats see their own hand and deck, the open board, hand/deck sizes and public events. The organizer stores private observations separately. Public confirmations for a private discard selection are generalized. | `draft.state`, `matchplay.public_view/accept_action`, `ArenaMatch.Publish/Tick` |

The engine decrements the second player's hero cooldown while setting up the opening turn. In a saved game, identical heroes showed cooldowns of 2 and 2 during placement, then 2 and 1 as play began. A second player with initial cooldown one can activate their hero on their first turn if its other conditions are met.

The host starts the 300-second deadline at the first decision of a turn and resets it when the turn or active seat changes. Tile placements by the same seat, targeting prompts and state polling share that deadline. After an accepted end-of-turn action the engine handles combat before the next decision window. A double draft timeout with no submissions interrupts the match without assigning a win. Engine faults and harness termination are organizer errors.

## Limits and recorded checks

The tournament specifies equal hero HP, a shared legal pool, twenty distinct cards, redrafting, five games per session and timeouts. The mobile game uses progression-dependent HP and deck limits and allows duplicates. The bridge adapts manual targeting to both seats and sometimes applies an effect directly through `DoResult`. The reviewed Blueprint tables for cards, heroes, parameters and faction advantages matched the recovered Mac client byte for byte. Fifty of the 189 effect classes had source differences in the arena copy, including manual target selection for the second seat.

A saved trace offered only placement at revisions 0–7. At revision 8 both sides had placed four tiles and A had two mana on turn one. Revision 10 gave B turn two without an intervening wheel spin. Action 77 later showed a flooped Sand Knight attacking. Two stdio MCP clients received the same rules and paginated catalog through their own seats, and their state views isolated private hands and legal actions. The evidence covers these decisions and static source paths. It does not exercise all possible card interactions in Unity. [Player rules](arena-rules.md) · [Engine bridge](../cardwars/engine/unity/) · [MCP](../cardwars/tools/mcp_server.py)
