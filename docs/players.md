# Connect a player

Choose two entries from `[players.<id>]` in `[match].players`. Each external player gets one process and one MCP session for the five-game match. The opening prompt contains the rules and the match parameters. The seat can call `read_rules`, `get_state`, `submit_deck` and `act`. Players are asked to write public explanations in English.

## Installed harnesses

The match manifest supplies launch commands for Codex CLI, Claude Code, OpenCode V2 and Prime Agent. Pick a model available to your account. Codex and Claude can use their normal CLI credentials. OpenCode and Prime have separate settings and state directories per seat. Supply provider credentials via their standard environment and keep secrets out of TOML and command arguments. Set the Unity project path as described in the [README](../README.md).

```sh
for cli in codex claude opencode prime; do
  uv run cardwars tools check "$cli" --project "$CARDWARS_UNITY_PROJECT"
done
```

These connectivity checks do not call a model. Codex opens a temporary session, lists the tools and calls `get_state`. Claude checks the four tools through `mcp_status`. OpenCode waits for its single arena server. Prime checks its four active tool schemas and calls `read_rules`. To run a match using model quota:

```sh
uv run cardwars match configs/arena100.toml --players terra sonnet
uv run cardwars match configs/arena100.toml --players opencode prime
```

| Harness | Model settings | Session |
|---|---|---|
| Codex CLI | `--model`, `model_reasoning_effort` | `exec --json`, dedicated MCP via `-c`, shell and external tools disabled |
| Claude Code | `--model`, `--effort` | `--restricted --strict-mcp-config`, empty built-in tool set, verbose streaming JSON |
| OpenCode V2 | `--model provider/model#variant` | Private password-protected loopback server, MCP ready before `run --format json`, four arena tools allowed |
| Prime Agent 0.9.4 | `--provider`, `--model`, `--thinking` | Node loads the installed SDK. An extension registers the four MCP tools in a single session and disables the Python REPL. |

Set `model` and `effort` for each rated entrant. The harness, command template, model and effort identify a configuration. `rating_id` can supply a readable prefix. Override the spectator label with `display_name`. Effort values depend on the provider and client. OpenCode uses the variant name. Prime accepts either a model ID or `provider/model`.

The organizer writes harness stdout to `<seat>.events.jsonl` for supported streams and diagnostics to `<seat>.log`. On this Mac, the ChatGPT.app Codex binary successfully queried Terra at medium effort. Homebrew Codex 0.146.0 returned `model_not_found` under the same account. To select the bundled executable, use the PATH in the README or put its full path in `harnesses.codex.command`.

## A custom harness

A trusted local CLI that accepts a prompt and a stdio MCP configuration can be configured directly. A different interface needs a wrapper that attaches the tools to its session. The default `stdio` adapter inherits the environment and can reach the provider. Disable unrelated tools, plugins and prior-session history in the CLI. The macOS seat sandbox protects the organizer directory, archived matches and the opposing seat's socket throughout the process tree.

```toml
[harnesses.my-cli]
adapter = "stdio"
trace_format = "arena"
command = ["/absolute/path/my-cli", "--model", "{model}", "--effort", "{effort}",
           "--mcp-json", "{mcp_config}", "--verbose", "--prompt", "{prompt}"]

[players.alice]
harness = "my-cli"
model = "my-model"
effort = "high"
```

Each placeholder replaces one whole argument. Use flags supported by your CLI.

| Placeholder | Value |
|---|---|
| `{prompt}` | Initial prompt and complete game rules |
| `{mcp}`, `{mcp_json}` | Stdio relay command as separate arguments or one JSON array. The array is also in `CARDWARS_MCP_COMMAND`. |
| `{mcp_config}` | JSON object of the form `{"mcpServers":{"arena":{"type":"stdio","command":"…","args":[…]}}}` |
| `{model}`, `{effort}` | Player settings for custom CLI flags |
| `{arena}`, `{options}` | Native adapter connection and per-player flags |
| `{seat}`, `{seat_dir}`, `{seed}`, `{python}` | Seat name, working directory, seed and arena interpreter |

For `trace_format = "arena"`, write one event per stdout line such as `{"type":"arena.message","text":"I am holding mana for my next play."}`. Select `none` for an unsupported output format. Built-in formats are `codex`, `claude`, `opencode` and `prime`. Include the corresponding output flags in your command.

## Random and isolated players

```sh
uv run cardwars match configs/arena100.toml --players random random-play-first --seed 42
```

Both bots draw a random hero and twenty random cards. The uniform bot samples legal actions uniformly. The play-first bot prefers any available choice that continues play over ending a turn.

```toml
[players.my-bot]
kind = "command"
command = ["{python}", "/absolute/path/my_bot.py", "--seed", "{seed}", "--", "{mcp}"]
```

The script can launch the remaining argv as its stdio MCP server, or read the `CARDWARS_MCP_COMMAND` JSON array. On macOS the organizer clears the environment and permits reading the named script, runtime dependencies, rules and catalog. The bot's only network connection is its seat's socket. External command players and authenticated harnesses require macOS with `sandbox-exec`.

[Codex MCP](https://developers.openai.com/codex/mcp) · [Claude Code CLI](https://code.claude.com/docs/en/cli-reference) · [OpenCode V2](https://github.com/anomalyco/opencode/blob/v2.2.2/services/www/src/docs/content/mcp-servers.mdx) · [Prime Agent](https://github.com/PrimeIntellect-ai/prime-agent)

## Campaign AI mirror

Run `uv run cardwars match configs/arena100.toml --players terra campaign` to play five games against the original Card Wars opponent. The first seat drafts before each game. The organizer copies its hero and all 20 cards to the campaign seat. Unity shuffles each deck separately and the usual first-player draw applies.

The second seat runs inside Unity. The arena calls the recovered `AIManager.MakeDecision()` after each resolved action. A null decision ends the turn. The opponent's card scripts select their own targets, and its landscape slots come from the game's shuffled opponent deck. The trace records the Unity decision and the accepted action.
