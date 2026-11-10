# Read a match trace

[Open a five-game replay](../results/2026-11-08-terra-sonnet-medium/trace.html). If a host displays the HTML source, download the file and open it in a browser with JavaScript enabled. The styles, event data and scripts are embedded.

The organizer trace includes both hands, complete decks and original diagnostics, which can contain paths. Keep it outside player access during a live match.

## Build the viewer

```sh
uv run cardwars trace results/2026-11-08-terra-sonnet-medium/trace.jsonl --output trace.html
```

Python callers can use `cardwars.reports.trace.render_trace(trace_path, output)`. A single JSONL file suffices, including partial and historical runs.

## Follow a decision

1. Pick a game and a turn. The turn number and player name identify who acted. The duration bar spans consecutive turn snapshots and includes decision time and engine time. For a draft, select the deck submission for the relevant player.
2. Filter the timeline by decisions, wheel, setup, technical events or results. Search matches labels, IDs, event fields and associated board events. Showing all records includes Unity snapshots and public events.
3. Select an action. The options panel highlights the choice the engine accepted. Compare health, mana, hands and lanes before and after. For wheel events, inspect the hit and critical areas and the random stop position. A forced outcome has no random stop.
4. Open JSON to inspect the original event with its `seq` and UTC time. Raw events identify lanes starting at zero. Board cards in the viewer count from one.

The viewer associates an action with its revision and the following revision in the same game. A restart breaks the association. An interrupted trace may lack an after-state or `match_end`. A damaged line is reported with its line number. Large IDs and seeds are represented as strings in HTML so JavaScript preserves them exactly. Archived raw JSON retains the language recorded during play.

The timeline and per-event inspector were inspired by the [Langfuse trace view](https://langfuse.com/changelog/2025-03-19-new-trace-view).

The viewer bundles original English names so a shared replay works offline. To verify the bundled names and historical target prompts against the Unity project, run `uv run python -m cardwars.reports.archive_labels "$CARDWARS_UNITY_PROJECT" --check`. Replace `--check` with `--output cardwars/reports/assets/english.json` to regenerate the table.
