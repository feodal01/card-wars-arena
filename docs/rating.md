# Tournament schedule and ratings

A majority win in a five-game match contributes one match win. Margins of 3–2 and 5–0 count equally. HP and action counts appear in the replay. Only complete, verified traces enter the ratings. A technical win requires evidence of the missed deadline.

```sh
uv run cardwars tournament plan configs/league100.toml
uv run cardwars tournament run configs/league100.toml --output runs/league-en --dry-run
uv run cardwars tournament run configs/league100.toml --output runs/league-en
uv run cardwars tournament board configs/league100.toml --output runs/league-en
```

The first two commands print the schedule without starting players or writing files. Execution needs the configured engine. Use `--limit N` to play at most N new matches in one invocation. Open `leaderboard.html` in the league directory. Each verified match links to its result and evidence.

## Schedule and resumption

`match_config` is relative to the league TOML. Entries in `entrants` refer to player keys in that match config. Each pair plays once per round. Four entrants with one round play six matches and thirty games. Set `repeats` to run additional rounds. Each encounter gets a new seed. The scheduler assigns seats. Within each match, every game draws its own starting player.

`schedule.json` records the participants, types, identities, policy hashes, ruleset, seats and seeds. Use a new directory for a different configuration or budget. On restart, the host re-verifies existing complete results and continues from the first unplayed fixture. For an incomplete fixture with a database it tries the normal match resume mechanism. Random bots can resume an interrupted opening before the first published battle decision. For other interrupted battles or external agent sessions, inspect the evidence and move the incomplete fixture directory under `attempts/` before replaying it. The seed and seats come from the schedule. Partial attempts earn no rating. A lock prevents concurrent organizers. Regenerating the board reads the evidence again.

## The 100 HP league

The supplied league has three entrants and schedules twenty independent matches for each pair. All fixtures share the same 258-card pool. Seeds, deals and player sessions vary. With `[report].method = "bradley-terry"`, fit one observation per match winner across all verified fixtures of the same ruleset. The mean participant rating is fixed at 1500. A finite joint maximum-likelihood estimate requires a strongly connected win graph.

The 95% intervals use 1,000 bootstrap samples, resampled within each played pairing. Intervals are hidden if any played pairing has fewer than five matches. Nonfinite bootstrap fits count conservatively toward both tails. If there are more nonfinite samples than the tail size, the interval is hidden. These choices belong to the arena implementation. [Kaggle Game Arena, section 2.4](https://arxiv.org/html/2609.31473v1#S2.SS4)

## Archived sequential Elo

Each participant starts at 1500 per ruleset. For a match between A and B:

```text
p = 1 / (1 + 10^((R_B − R_A) / 400))
change = 32 × (win_A − p)
R_A ← R_A + change
R_B ← R_B − change
```

`win_A` is 1 if A wins, 0 otherwise. At equal starting ratings the winner reaches 1516 and the other player falls to 1484. The next match uses those new ratings. The archive also reports opponents, match and game W–L, and a conservative 95% interval on the match win fraction. For n independent match seeds, its radius is `sqrt(log(40)/(2n))`, clipped to [0,1] and rounded outward. One match yields 0–100%. [Early Chatbot Arena Elo](https://www.lmsys.org/blog/2023-05-03-arena/) · [Bradley–Terry update](https://www.lmsys.org/blog/2023-12-07-leaderboard/) · [Chatbot Arena paper](https://arxiv.org/abs/2403.04132) · [Hoeffding](https://doi.org/10.1080/01621459.1963.10500830)

## Identity and evidence

Keep model, prompt, harness and effort reproducible. For external programs, supply a stable `rating_id` and change it when the policy changes. Native random identities are `random-uniform-v1` and `random-play-first-v1`. The scheduler excludes aliases of the same random strategy. Different rulesets and starting HP have separate ratings. The English-input configuration uses its own `rules_version`.

Two November 5 archives predate explicit identities. Their trace hashes identify uniform-random self-play under two landscape-placement rules. The board preserves the seat labels and excludes these records from Elo. A different untagged archive requires provenance review. `board --include MATCH_DIRECTORY` adds independent verified records and can be repeated. `--html FILE` sets the destination. Duplicate evidence with the same match ID counts once. Conflicting records or reused conditions presented as a new match are rejected.

In the historical demo, play-first beat uniform 3–2. [Archived board](../results/leaderboard.html) · [Replay](../results/2026-11-06-demo/matches/match-0001/trace.html)
