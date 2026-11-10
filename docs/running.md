# Run Card Wars Arena

## Explore a match after cloning

Download an archived `trace.html` and open it in a browser. Select a game, turn or card play to inspect both hands, the board before and after, and the wheel outcome. Each HTML viewer works offline. GitHub’s file page also has a download button. [Interactive human match](../results/2026-11-10-human-terra/trace.html) · [Trace guide](trace.md)

To verify the results or regenerate a viewer, use Python 3.11 or later and `uv`. Run these commands from the repository root. These operations work without Unity or model accounts.

```sh
uv sync --locked
uv run --locked python scripts/check_release.py
uv run --locked cardwars verify results/2026-11-10-human-terra/trace.jsonl
uv run --locked cardwars trace results/2026-11-10-human-terra/trace.jsonl --output build/human-match.html
```

Videos and the illustrated workshop use Git LFS. After installing Git LFS, run `git lfs install --local` and `git lfs pull` in the clone. To fetch only one recording, see the [media index](../materials/README.md). The JSON scores, raw traces, Markdown reviews and HTML trace viewers are ordinary Git files.

## Prepare the live game

The tested host is macOS with Unity Editor **2022.3.62f3**. Live play needs a compatible recovered Card Wars Unity project with the game scenes, original scripts, English localization, art and Blueprint tables. The public checkout provides the arena bridge. The input to this setup is a working Unity project ported to that editor version. APKs, phone saves and the installed Mac app are different inputs.

```sh
export CARDWARS_UNITY_PROJECT="$PWD/local/arena-unity"
uv run --locked cardwars prepare-engine /path/to/recovered-card-wars "$CARDWARS_UNITY_PROJECT"
uv run --locked cardwars catalog --project "$CARDWARS_UNITY_PROJECT" --check-sources --output build/catalog.md
```

Setup copies `Assets`, `Packages` and `ProjectSettings` to a **new directory**, gives the copy its own standalone application ID, installs the bridge and checks 222 effect sources. Allow Unity to finish its first asset import before running a timed match. You can open and close the prepared project in Unity, or use the batch command in the [engine setup guide](engine.md). The default editor path is the standard macOS Unity Hub path. Override `[engine].executable` in the TOML for another installation.

## Run a match

A standard match comprises five games, including games four and five after a player has secured the majority. Each player selects one of 72 hero entries and 20 distinct cards from 258 eligible cards. Heroes start at 100 HP. The first player is drawn separately each game. Players place four landscapes each, then the first player plays cards. The second player makes the first attack. Unity resolves the wheel using a random stop. Deck selection has a ten-minute clock and each turn has a five-minute clock. [Full rules](../cardwars/arena/rules.md) · [Card and hero catalog](catalog.md)

| Mode | Command |
|---|---|
| Run the headless random baseline, seed 42 | `uv run --locked cardwars match results/2026-11-10-random-baseline/match.toml` |
| Watch uniform random vs. play-first | `uv run --locked cardwars match configs/arena100.toml --players random random-play-first --seed 42` |
| Agent vs. agent through two harnesses | `uv run --locked cardwars match configs/arena100.toml --players terra sonnet` |
| Recreate the Terra vs. Astra medium setup | `uv run --locked cardwars match results/2026-11-08-terra-astra-medium/match.toml --seed 8895705922137395424` |
| Agent vs. random | `uv run --locked cardwars match configs/arena100.toml --players terra random` |
| Agent vs. the original campaign AI | `uv run --locked cardwars match configs/arena100.toml --players terra campaign` |

The campaign AI occupies the second seat and receives the first player’s hero and all 20 cards. The decks are shuffled independently. The native campaign decision method plays the bot’s turns. [Mirror-match evidence](../results/2026-11-09-terra-campaign-mirror/review.md)

For an agent, install and sign in to its CLI and select a model your account can use. The TOML defines the harness command, model and reasoning effort. The historical Terra runs used the Codex executable supplied with the desktop app. If installed at the same location, select it with `export PATH="/Applications/ChatGPT.app/Contents/Resources/codex-cli/bin:$PATH"`. Check the connection with `uv run --locked cardwars tools check codex --project "$CARDWARS_UNITY_PROJECT"`. Substitute `claude`, `opencode` or `prime` for the other adapters. Each agent keeps its own session for the match and receives four seat-bound MCP tools. [Harness configuration and custom commands](players.md) · [Tool contract](tools.md)

The match command prints a new run directory. Supply `--output runs/my-match` for a named run. Set `watch = false` for silent headless play or `record = true` for native gameplay capture. For broadcast graphics and MP4 export, install Node.js 22+, Google Chrome and the Python video extra with `uv sync --locked --extra video`. [Spectator and export guide](spectator.md)

## Play against an agent

```sh
uv run --locked --extra video cardwars duel configs/arena100.toml --opponent terra
```

1. Open the private browser table printed by the launcher. Choose a hero and 20 cards there, or import a JSON deck from the [offline workshop](../materials/deck-workshop.html). The workshop displays the land color, cost and full ability on each card. It also distinguishes hero variants and cooldowns.
2. Leave **Record match video** checked for a recording with game audio. Click **Start match** when ready. Offline preparation has no clock.
3. Place your four landscapes when prompted. Select a card in your hand to see legal lanes and costs. The board aligns opposing lanes vertically. The Actions panel offers available floops, hero powers, spell targets and ending the turn with unspent mana. The opponent’s hand stays private.
4. After each game, keep or change your hero and deck and click **Lock deck for game N**. After game five the table links the trace and, when encoding finishes, the MP4. Keep the launcher running through export. Refreshing the private URL reconnects to your current seat.

Use `--opponent random-play-first` to practice without a model account. The video exporter uses the field and audio captured during play plus event timestamps from the trace to shorten thinking pauses. A trace by itself supports the interactive turn viewer.

## Run a league

```sh
uv run --locked cardwars tournament plan configs/league100.toml
uv run --locked cardwars tournament run configs/league100.toml --output runs/my-league --limit 1
uv run --locked cardwars tournament board configs/league100.toml --output runs/my-league
```

The plan can be inspected without installing the engine. The supplied league schedules 20 five-game matches per pair among three entrants. Running the same league directory continues its schedule. Each verified match supplies one majority result to the Bradley–Terry rating on the Elo scale. The results index also links the earlier sequential Elo demonstration. [Scheduling and ratings](rating.md)

## Repository layout

| Path | Contents |
|---|---|
| `cardwars/arena/`, `cardwars/engine/` | Match host, verified catalog, clocks, Unity preparation and native bridge |
| `cardwars/tools/`, `cardwars/players/` | Private seat MCP server and relay, CLI harness adapters and random player |
| `cardwars/human/` | Browser player table and offline deck workshop generator |
| `cardwars/reports/`, `cardwars/tournament/` | Trace inspector, broadcast, recording, schedules and ratings |
| `configs/`, `docs/` | Maintained arena and league configurations, rule and interface guides |
| `results/` | Published evidence, configurations where available, reviews and offline viewers |
| `materials/` | Recordings, deck workshop and media checksums |
| `tests/`, `scripts/` | Regression tests and release verification |
| `runs/`, `build/`, `local/` | Ignored local match workspaces, generated files and the operator’s engine |

Run `uv run --locked python -m unittest discover -s tests` and `node --test tests/on_air.test.cjs` for the Python and browser-timing suites. Set `CARDWARS_UNITY_PROJECT` to include tests using the original card data. A seed fixes the host’s draw and player seeds. Repeating the seed-42 configuration produced the same starting seats but different native battles and a different series winner. A new agent session can also make different decisions. For an article or an exact decision, link to the archived match at a specific Git commit and include the trace event number.
