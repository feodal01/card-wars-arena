# Terra 6.1 vs. the Card Wars campaign AI

Terra won 5–0. Terra 6.1 played through Codex at medium reasoning effort. Before each of the five games, Terra selected a hero and 20 cards for both sides. Each hero had 100 HP. Unity shuffled the two decks separately.

[Full recording · 16:04](../../materials/recordings/2026-11-09-terra-campaign-mirror/broadcast.mp4) · [Interactive trace](trace.html) · [Run configuration](match.toml)

| Game | Video | First player | Winner | Turns | Final HP, Terra / AI | Hero on both sides | New cards since last game |
|---|---|---|---|---:|---:|---|---:|
| 1 | 00:00 | Terra | Terra | 7 | 53 / 0 | Hunson Abadeer | — |
| 2 | 02:33 | Campaign AI | Terra | 10 | 26 / 0 | Hunson Abadeer | 0 |
| 3 | 05:59 | Terra | Terra | 7 | 87 / 0 | Hunson Abadeer | 0 |
| 4 | 08:29 | Terra | Terra | 9 | 74 / 0 | Hunson Abadeer | 0 |
| 5 | 11:49 | Campaign AI | Terra | 12 | 50 / 0 | Hunson Abadeer | 0 |

## The opponent

The original campaign sequencer calls `AIManager.MakeDecision()` again after each completed action. It evaluates candidate cards, lanes, creature abilities and the hero ability against the current board. When the method returns null, the opponent ends its turn. Its card scripts choose targets. Landscape placement follows the opponent deck’s native shuffled slots.

The recovered original and the Unity arena copy of `AIManager.cs` had identical SHA-256 digests (`14507afd4ac222d1ee9b23e8f79adead7abccfeee0b8c160d8eb276d59c9add1`). The verifier checked all ten rosters and all 57 campaign decisions after placement. It also checked 20 native landscape placements. The recording includes all 171 accepted actions with shortened thinking pauses.

## Plays to revisit

1. The bot cast Lonely Hearts on its first turn, then used Super Hunson to boost its Plains creatures. On turns four and six it took Terra from 100 to 53 HP. Terra ended the game on turn seven. Events 41–90.
2. The bot hit Terra for 43 on turn five and left Terra at 26 HP after turn seven. Terra's turn-ten Ultimate Magic Hands returned Struzann Jinn to hand before the finishing attack. Events 153–160, 174–175 and 198–208.
3. Terra played Psionic Architect and Poultrygeist, then activated Super Hunson. The attack on turn five took the bot from 95 HP to 47. On turn seven, Lonely Hearts removed its only creature and Terra finished through open lanes. Events 271–293.
4. Terra flooped its wounded Struzann Jinn to return the opposing Psionic Architect, then flooped Poultrygeist. After that turn the campaign hero had 8 HP. Events 380–390.
5. The campaign AI went first. Both players deployed Madame Seota on consecutive turns. Terra opened turn twelve facing a hero with 6 HP, played Punk Cat and activated Super Hunson before the final attack. Events 525–547.

[Frame numbers for each trace event](broadcast-cues.json) · [Machine-readable results](results.json)
