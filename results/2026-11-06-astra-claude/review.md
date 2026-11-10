# Astra 3–2 Claude

GPT-6 Astra (Codex CLI 0.166.0-alpha.6) and Claude Opus 5.5 (Claude Code 2.1.318) played five games in Unity. Claude used the config alias `opus` and its session reported `claude-opus-5-5`. Both seats took 45 actions. All five games ended when a hero ran out of HP. [Replay](trace.html)

| Game | First | Heroes, Astra / Claude | Final HP, Astra / Claude | Turns |
|---|---|---|---|---:|
| 1 | Claude | BMO / Ash | 19 / 0 | 4 |
| 2 | Claude | BMO / Ash | 21 / 0 | 4 |
| 3 | Astra | BMO / Ash | 25 / 0 | 3 |
| 4 | Astra | BMO / Earl Of Lemongrab | 0 / 19 | 4 |
| 5 | Astra | Earl Of Lemongrab / Earl Of Lemongrab | 0 / 25 | 2 |

**Astra won the first three games with the same deck.** In game one, Astra dealt 13 hero damage on turn two. On turn four it activated BMO and played Sandwitch and another creature. Claude replaced eight cards after its first loss and two more before game three. In game three Astra played a Gold Psionic Architect with 25 Attack. The combat phase took Claude from 25 HP to zero.

**Claude changed heroes in game four.** It replaced three cards and selected Earl Of Lemongrab, whose power discounted summons by one mana that turn. On turn two Claude played Husker Knight for zero, Orange Slimey for zero and Big Foot for two. The attack left Astra at 5 HP. Claude won two turns later and kept its hero and deck for game five.

**Game five ended with the first attack.** Astra switched to Earl Of Lemongrab and added two one-cost creatures, Nice Ice Baby and Ms. Mummy. Inspect game five, turn one, event 279. Astra's power was unavailable. On turn two Claude could use its own power (294) and played a discounted Gold Psionic Architect for two opposite an open lane (297). The attack ended the game (303). The heroes matched but opening hands and cooldowns differed.

Two earlier launch attempts stopped during Codex tool connection before either played a battle. One completed match was counted.
