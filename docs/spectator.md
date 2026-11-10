# Watch a match

With `match.watch = true`, the organizer opens a browser before starting either player. If it does not open, use the path printed in the terminal. The local page lives at `.operator/live.html` inside the run directory.

Watch both draft slots from the start. Once a player locks in a roster, their hero and all twenty cards appear under their name. During play, the page shows accepted actions with their player and turn, public messages and the series score. Use the current-game link to follow the match or a game number to inspect an earlier draft. The final page stays on disk after completion or an orderly interruption.

With `match.record = true`, the browser opens the broadcast instead. Use the local URL printed by the organizer. The broadcast keeps the submitted decks visible while Unity loads, then shows **Fight!** for 1.2 seconds and cuts to the native Game view. Unity captures at 1600 × 850 with a target of 30 frames per second; the browser receives those frames directly. Game audio plays from Unity on the host. The JPEGs and the timestamped listener mix are saved inside each `game-N/` folder for video export. Only the spectator sees the draft reveals; the players' tools remain private to each seat.

An English decision comment goes with the accepted deck submission or action. It appears in the live feed and in the offline trace inspector. Bots can also play without commentary. In Unity, player names from the opening appear at the starting draw, above the hands, in announcements and in the deck view opened with **Tab**. Older opening files use seat labels.

## Event sources

The organizer reads committed game events from SQLite in read-only mode. The selected harness format determines which complete stdout messages can also be displayed.

| Format | Visible event |
|---|---|
| `codex` | Completed `agent_message`. Standard `codex exec --json` may also supply a public reasoning summary. |
| `claude` | Text blocks from an assistant message |
| `opencode` | Visible text parts |
| `prime` | Text blocks from `message_end` |
| `arena` | Explicit custom event, e.g. `{"type":"arena.message","text":"I am defending the open lane."}` |
| `none` | Game events, including comments submitted through MCP |

Some harnesses emit text only after completing a message. Accepted game actions can appear sooner. The organizer excludes private reasoning, tool responses and diagnostic logs from the feed. The local file requires no HTTP server. Codex is asked for a concise public summary. CLI 0.146.0 builds this event from the summary array and skips empty summaries. [Codex implementation](https://github.com/openai/codex/blob/rust-v0.146.0/codex-rs/exec/src/event_processor_with_jsonl_output.rs#L151-L159)

## Broadcast replay

Build the English broadcast graphics from an archived five-game trace and its Unity art library. The HTML embeds the card art and runs offline.

```sh
python -m cardwars.reports.broadcast PATH/TO/trace.jsonl PATH/TO/UNITY_PROJECT broadcast.html
```

Use the scene selector or the left and right arrow keys to review the matchup, each deck reveal, landscape placement, featured card plays and results. Add `?clean` to the local URL to hide the controls for capture. The scoreboard counts completed games. A draft reveals a player's full submission at lock-in. The footer attributes quotes to players and labels broadcast narration separately. These graphics are for the spectator. The HTML contains both hands and all five results.

The replay uses the OpenAI mark from [ChatGPT](https://chatgpt.com/cdn/assets/favicon.6a33781f61.svg) and the Claude mark from [Claude](https://claude.com/icon.svg). The marks belong to their respective owners.

To export a completed recorded match with the broadcast layout, native video, stereo sound and five chapters, run the following on the organizer's Mac with Chrome and Node 22 installed.

```sh
uv run --extra video python -m cardwars.reports.broadcast_video runs/my-match "$CARDWARS_UNITY_PROJECT" runs/my-match/broadcast.mp4
```

The export keeps every accepted action, shortens thinking pauses and writes the corresponding video frames to `broadcast.cues.json`.
