# Terra 6.1 vs. Opus 5.5 · 4–1

Terra (Codex, medium) won the first four games. Opus (Claude Code, medium) won the fifth with 78 HP. All five games ended in combat. Each player had 100 starting HP and chose 20 cards from the same 258-card pool. [Trace viewer](trace.html) · [Results](results.json)

| Game | Original video chapter | First player | Turns | Final HP, Terra / Opus | Decision to replay |
|---|---|---|---:|---:|---|
| 1 | 00:10 | Terra | 9 | 84 / 0 | Terra hit the hero for 28 on turn three and 36 on turn five. With Opus at 13 HP, Terra played Madame Seota and activated Hunson Abadeer before attacking. Events 54, 81 and 110–119. |
| 2 | 06:42 | Opus | 12 | 49 / 0 | Opus had 56 HP when Terra played Spectre Hector, used its Floop to return the opposing blocker, built Ghost Castle, and activated Hunson. Punk Cat rolled a critical and Hector hit in the other open lane. Events 264–277. |
| 3 | 14:10 | Terra | 9 | 100 / 0 | Two attack-wheel rolls on turn five included a critical. Opus fell from 79 to 30 HP, then to 1 on turn seven. Terra needed only to end its ninth turn and attack. Events 359, 374 and 391–392. |
| 4 | 19:48 | Terra | 7 | 100 / 0 | Opus switched to a Sand/Swamp deck. At 27 HP it blocked Spectre Hector. Terra put Ghost Castle behind Axey in a different lane, raising its attack to 29. Events 468–480. |
| 5 | 24:21 | Opus | 11 | 0 / 78 | Opus switched from BMO to Prince Gumball and replaced 16 cards. It dealt 33 hero damage on each of turns seven and nine, leaving Terra at 2 HP. Opus played Candyr and ended turn eleven to finish. Events 577, 601 and 615–620. |

Terra submitted Hunson Abadeer and the same twenty cards in all five games, with thirteen Plains and seven Universal cards. Opus replaced six, three, seven and sixteen cards in successive drafts. Its last deck included fifteen Cotton cards and five Universal cards. Its stated plan was to use Prince Gumball's cost reduction to fill the lanes early. [Recorded drafts and turn comments](trace.html)

## Why the repeated hero?

Terra's exact pick was `Leader_SuperHunson`: +8 Attack to each allied Plains creature in play, with a two-turn cooldown. Terra publicly described building around this ability. Its thirteen Plains cards produced four Plains landscapes; the seven Universal cards do not add another landscape type.

Terra picked that hero in the opening draft of three separate matches: the original Sonnet match, the English Sonnet rematch, and this Opus match. These are three fresh Codex sessions, not fifteen independent drafts. Within each match the session intentionally retained its five-game history, and Terra resubmitted that match's original twenty cards. The English Sonnet and Opus opening decks shared seventeen cards.

In all three archives, the player copies of the catalog and rules match byte for byte within each match. The initial seat state had no previous hero or deck, and the only arena tools Terra called before its first submission were `read_rules` and `get_state`. Codex receives an extra line explaining how to call MCP; it does not suggest a hero, a faction or a deck. These logs show no carryover from another match. Super Hunson was listed 61st of 72 heroes in all three catalogs. These checks do not establish why a model chose a particular strategy or rule out effects of the fixed catalog order.

Both players can pick the same hero and the same twenty cards. Terra submitted first in all five games here; the separate opening draw gave Opus the first turn in games two and five.

## Recording and result recovery

The MP4 includes the deck and hero reveals, all five native opening draws, battlefield footage, public comments, stereo game audio and game chapters. After Unity published the final state in game five, it exited with an error. Event 619 records Opus as the winner with 78 HP, Terra at zero and no further legal actions. Event 620 records the combat outcomes. The organizer preserved the interruption at event 621 and used the matching terminal state on disk to complete the two result entries. The verifier checked all 623 events. The final two broadcast slates use those verified results.

## Remastered replay

The [1080p replay](../../materials/recordings/2026-11-08-terra-opus-medium/broadcast-replay.mp4) runs 18:23; the [16-second sample](../../materials/recordings/2026-11-08-terra-opus-medium/broadcast-preview.mp4) shows live game animation. The models were not called again. The isolated Unity playback used the original rosters, actions and wheel draws. After each of 195 accepted actions, the turn, active player, board, health, hands, legal actions and winner agreed with the original trace. Deck selection and thinking pauses have been shortened; the original video chapter times above refer to the unedited timeline.

Each fight title holds for 36 frames (1.2 seconds). The native field was captured at 1600 × 850 and averaged 29.6–30.0 frames/s per game, up from 6.6–7.7 at 960 × 510. The broadcast is 1920 × 1080 with stereo sound. The five new chapters start at 00:00, 03:19, 08:07, 11:24, 14:11. The [cue sheet](broadcast-cues.json) maps every accepted action's original trace sequence to its frame in this replay.
