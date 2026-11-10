"""Construct one long-lived player process for an organizer-created seat."""

import json
import shutil
import sys
from pathlib import Path

from cardwars.config import NATIVE

TOOLS = ("get_state", "act", "submit_deck", "read_rules")
PROMPT = (
    "Play this entire five-game Card Wars match as the seat assigned by the arena MCP server. "
    "Call read_rules, then get_state. At each draft choose a hero and twenty distinct card IDs "
    "from the shared catalog. If it is truncated, get_state(catalog_page=1) returns the first "
    "page and catalog_pages. Request the remaining pages by number, including the last pages "
    "for hero IDs. Submit the current game number. Play using only the action IDs returned "
    "by get_state. Place landscapes when the arena offers placement actions. "
    "Write player messages in English. Include a short public comment in English in each "
    "submit_deck explaining your hero and deck, and in one act per turn explaining your move "
    "from the visible board. Use the optional comment argument, up to 400 characters. "
    "Continue playing immediately. "
    "If waiting for the opponent or Unity, call get_state with wait_seconds=20. "
    "Continue after each game and finish only at match_over."
)


def relay_command(directory: Path, seat: str) -> list[str]:
    # macOS limits Unix socket paths to 103 bytes. The broker's link targets a short private path.
    socket_path = (directory / seat / "arena.sock").resolve(strict=True)
    return [
        sys.executable,
        "-I",
        str(Path(__file__).with_name("proxy.py").resolve()),
        str(socket_path),
    ]


def custom_command(player, relay, seat_dir, seat, seed):
    if sys.platform != "darwin" or not Path("/usr/bin/sandbox-exec").is_file():
        raise ValueError("Custom command players require the macOS seat sandbox")
    raw = player["command"]
    if (
        not isinstance(raw, list)
        or not raw
        or not all(isinstance(arg, str) for arg in raw)
    ):
        raise ValueError("command must be a nonempty array of argv strings")
    substitutions = {
        "{seat}": seat,
        "{seed}": str(seed),
        "{seat_dir}": str(seat_dir),
        "{python}": sys.executable,
    }
    argv = []
    for arg in raw:
        if arg == "{mcp}":
            argv.extend(relay)
        else:
            argv.append(substitutions.get(arg, arg))
    executable = shutil.which(argv[0])
    if executable is None:
        raise ValueError(f"Player executable unavailable: {argv[0]}")
    # Python discovers pyvenv.cfg relative to its invocation path. Preserve a venv
    # entry point even when its executable is a symlink to the base interpreter.
    argv[0] = str(Path(executable).absolute())

    # Command seats may use a standalone, explicitly named program/script and the host Python
    # runtime. All other organizer files and arbitrary local/network sockets stay inaccessible.
    runtime = {
        Path("/System"),
        Path("/usr/bin"),
        Path("/bin"),
        Path("/opt/homebrew/Cellar"),
        Path(sys.prefix).resolve(),
        Path(sys.base_prefix).resolve(),
    }
    files = {
        Path(argv[0]),
        Path(argv[0]).resolve(),
        Path(relay[2]),
        *(seat_dir / name for name in ("rules.md", "catalog.md")),
        Path(relay[-1]),
    }
    for arg in raw[1:]:
        script = Path(arg)
        if script.is_absolute() and script.suffix == ".py" and script.is_file():
            script = script.resolve()
            if script.is_relative_to(seat_dir.parent):
                raise ValueError(
                    "Keep custom player programs outside the private match directory"
                )
            files.add(script)
    rules = [
        "(version 1)",
        "(deny default)",
        '(import "system.sb")',
        "(allow process-exec process-fork sysctl-read)",
        "(allow signal (target children))",
        "(deny network*)",
        "(allow network-outbound (literal " + json.dumps(relay[-1]) + "))",
    ]
    for directory in runtime:
        rules.append(
            f"(allow file-read* file-map-executable (subpath {json.dumps(str(directory))}))"
        )
    for file in files:
        rules.append(
            f"(allow file-read* file-map-executable (literal {json.dumps(str(file))}))"
        )
    # Python and dyld may traverse parent directories to locate a venv or an executable.
    for parent in {p for file in files | runtime for p in file.parents} | {seat_dir}:
        rules.append(f"(allow file-read-metadata (literal {json.dumps(str(parent))}))")
    # Environment is rebuilt inside the trusted launcher. No provider keys or parent MCP tokens.
    return [
        "/usr/bin/env",
        "-i",
        "PATH=/usr/bin:/bin:/opt/homebrew/bin",
        f"HOME={seat_dir}",
        "LANG=en_US.UTF-8",
        "PYTHONDONTWRITEBYTECODE=1",
        f"CARDWARS_MCP_COMMAND={json.dumps(relay)}",
        f"CARDWARS_SEAT={seat}",
        f"CARDWARS_SEED={seed}",
        "/usr/bin/sandbox-exec",
        "-p",
        "\n".join(rules),
        *argv,
    ]


def codex_flags(relay):
    disabled = (
        "shell_tool",
        "unified_exec",
        "shell_snapshot",
        "apps",
        "plugins",
        "hooks",
        "memories",
        "multi_agent",
        "computer_use",
        "browser_use",
        "in_app_browser",
        "image_generation",
        "artifact",
        "skill_search",
        "goals",
    )
    config = {
        "model_reasoning_summary": '"concise"',
        "show_raw_agent_reasoning": "false",
        "approval_policy": '"never"',
        "web_search": '"disabled"',
        "project_doc_max_bytes": "0",
        "default_permissions": '"arena"',
        "permissions.arena.filesystem": '{":root" = "deny", ":minimal" = "read"}',
        "permissions.arena.network.enabled": "false",
        "features": "{"
        + ", ".join(f"{f} = false" for f in disabled)
        + ", code_mode_host = true}",
        "mcp_servers.arena.command": json.dumps(relay[0]),
        "mcp_servers.arena.args": json.dumps(relay[1:]),
        "mcp_servers.arena.enabled_tools": json.dumps(TOOLS),
        "mcp_servers.arena.required": "true",
        "mcp_servers.arena.default_tools_approval_mode": '"approve"',
    }
    return [arg for key, value in config.items() for arg in ("-c", f"{key}={value}")]


def mcp_config(relay):
    return json.dumps(
        {
            "mcpServers": {
                "arena": {"type": "stdio", "command": relay[0], "args": relay[1:]}
            }
        }
    )


def claude_flags(relay):
    return [
        "--restricted",
        "--strict-mcp-config",
        "--mcp-config",
        mcp_config(relay),
        "--disable-slash-commands",
        "--setting-sources",
        "",
        "--permission-mode",
        "dontAsk",
        "--tools",
        "",
        "--allowedTools",
        ",".join(f"mcp__arena__{name}" for name in TOOLS),
    ]


def protect_harness(argv, directory: Path, seat: str, socket: str, *, writable=None):
    """The authenticated CLI needs its provider and credential store. Hide match files from
    the whole process tree, including harness-native utilities that bypass shell permissions."""
    if sys.platform != "darwin" or not Path("/usr/bin/sandbox-exec").is_file():
        raise ValueError("Authenticated CLI players require the macOS seat sandbox")
    directory = directory.resolve()
    filters = [f"(subpath {json.dumps(str(directory))})"]
    # Other runs and archived operator traces may contain private decks as well.
    for name in ("runs", "results", "materials", ".git"):
        filters.append(
            f"(subpath {json.dumps(str(Path(__file__).resolve().parents[2] / name))})"
        )
    rules = [
        "(version 1)",
        "(allow default)",
        "(deny file-read-data file-write* " + " ".join(filters) + ")",
        f"(allow file-read-data (subpath {json.dumps(str(directory / seat))}))",
        (
            f"(allow file-read-metadata (literal {json.dumps(str(directory / seat))}) "
            f"(literal {json.dumps(str(directory))}))"
        ),
        '(deny network-outbound (remote unix-socket (path-regex #"/cw-[^/]+/arena[.]sock$")))',
        f"(allow network-outbound (literal {json.dumps(socket)}))",
    ]
    if writable:
        rules.append(f"(allow file-write* (subpath {json.dumps(str(writable))}))")
    return ["/usr/bin/sandbox-exec", "-p", "\n".join(rules), *argv]


def launch_command(player: dict, directory: Path, seat: str, seed: int) -> list[str]:
    relay = relay_command(directory, seat)
    kind = player["kind"]
    seat_dir = (directory / seat).resolve()
    if kind == "random":
        policy = player.get("policy", "uniform")
        if policy not in ("uniform", "play-first"):
            raise ValueError(f"Unknown random policy: {policy}")
        return [
            sys.executable,
            "-m",
            "cardwars.players.random",
            "--seed",
            str(seed),
            "--policy",
            policy,
            "--",
            *relay,
        ]
    if kind == "command":
        return custom_command(player, relay, seat_dir, seat, seed)
    adapter = player.get("adapter", kind)
    command = player.get("command", NATIVE.get(adapter))
    if not command:
        raise ValueError(f"Missing command for harness {adapter}")
    prompt = PROMPT + "\n\n" + (seat_dir / "rules.md").read_text(encoding="utf-8")
    if adapter == "codex":
        prompt += (
            "\nDiscover arena tools with ALL_TOOLS. Example: "
            "text(await tools[ALL_TOOLS.find(t => t.name.endsWith('__get_state')).name]({}));"
        )
    env, flags, writable = harness_settings(adapter, relay, seat_dir)
    replacements = {
        "{arena}": flags,
        "{options}": model_options(adapter, player),
        "{mcp}": relay,
        "{mcp_config}": [mcp_config(relay)],
        "{mcp_json}": [json.dumps(relay)],
        "{python}": [sys.executable],
        "{prompt}": [prompt],
        "{seed}": [str(seed)],
        "{seat}": [seat],
        "{seat_dir}": [str(seat_dir)],
    }
    for key in ("model", "effort"):
        if key in player:
            replacements["{" + key + "}"] = [player[key]]
    argv = [value for token in command for value in replacements.get(token, [token])]
    executable = shutil.which(argv[0])
    if executable is None:
        raise ValueError(f"Player CLI unavailable: {argv[0]}")
    argv[0] = str(Path(executable).absolute())
    argv = ["/usr/bin/env", *[f"{k}={v}" for k, v in env.items()], *argv]
    return protect_harness(argv, directory, seat, relay[-1], writable=writable)


def model_options(adapter, player):
    model = player.get("model")
    effort = player.get("effort")
    if adapter == "stdio":
        return []
    if adapter == "opencode" and model and effort:
        model += "#" + effort
    args = ["--model", model] if model else []
    if adapter == "prime" and model and "/" in model:
        provider, model_id = model.split("/", 1)
        args = ["--provider", provider, "--model", model_id]
    if effort and adapter == "codex":
        args += ["-c", f"model_reasoning_effort={json.dumps(effort)}"]
    if effort and adapter in ("claude", "prime"):
        args += ["--effort" if adapter == "claude" else "--thinking", effort]
    return args


def harness_settings(adapter, relay, seat_dir):
    env = {"CARDWARS_MCP_COMMAND": json.dumps(relay)}
    if adapter == "codex":
        return env, codex_flags(relay), None
    if adapter == "claude":
        return env, claude_flags(relay), None
    if adapter == "stdio":
        return env, [], None
    state = seat_dir.resolve() / ".harness"
    state.mkdir(mode=0o700, exist_ok=True)
    if adapter == "prime":
        # Use provider environment credentials and isolate Prime settings, including its daemon.
        env["PRIME_AGENT_CODING_AGENT_DIR"] = str(state)
        env["CARDWARS_PRIME_BRIDGE"] = json.dumps(
            [sys.executable, str(Path(__file__).with_name("prime_bridge.py"))]
        )
        cli = shutil.which("prime-agent")
        if not cli:
            raise ValueError("Install the Prime Agent npm package for its SDK")
        for folder in Path(cli).resolve().parents:
            manifest = folder / "package.json"
            if manifest.is_file():
                package = json.loads(manifest.read_text(encoding="utf-8"))
                if package.get("name") == "prime-agent":
                    break
        else:
            raise ValueError(
                "The prime-agent executable must belong to its installed npm package"
            )
        sdk = (folder / package["main"]).resolve(strict=True)
        flags = [
            str(Path(__file__).with_name("prime.mjs")),
            str(sdk),
            "--offline",
            "--no-builtin-tools",
            "--no-extensions",
            "--no-skills",
            "--no-prompt-templates",
            "--no-themes",
            "--no-context-files",
            "--tools",
            ",".join(TOOLS),
        ]
        return env, flags, state
    if adapter != "opencode":
        raise ValueError(f"Unknown MCP adapter {adapter}")
    # V2's standalone server inherits these private XDG directories; provider keys can
    # be supplied in the normal environment. Never register in the user's MCP inventory.
    for key, name in (
        ("XDG_CONFIG_HOME", "config"),
        ("XDG_DATA_HOME", "data"),
        ("XDG_CACHE_HOME", "cache"),
        ("XDG_STATE_HOME", "state"),
    ):
        env[key] = str(state / name)
    folder = state / "config" / "opencode"
    folder.mkdir(mode=0o700, parents=True, exist_ok=True)
    permissions = [{"action": "*", "resource": "*", "effect": "deny"}]
    permissions.extend(
        {"action": f"arena_{name}", "resource": "*", "effect": "allow"}
        for name in TOOLS
    )
    config = {
        "mcp": {
            "servers": {"arena": {"type": "local", "command": relay, "codemode": False}}
        },
        "permissions": permissions,
    }
    (folder / "opencode.json").write_text(json.dumps(config), encoding="utf-8")
    return env, [str(Path(__file__).with_name("opencode.py"))], state
