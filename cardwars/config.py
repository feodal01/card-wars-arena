"""Load the match manifest. Paths are relative to its TOML file."""

import hashlib
import json
import os
import re
import tomllib
from dataclasses import dataclass
from pathlib import Path

UNITY_MAC = "/Applications/Unity/Hub/Editor/2022.3.62f3/Unity.app/Contents/MacOS/Unity"
ID = re.compile(r"[a-z0-9][a-z0-9_-]{0,47}\Z")
NATIVE = {
    "codex": [
        "codex",
        "exec",
        "--json",
        "--ignore-user-config",
        "--ignore-rules",
        "--skip-git-repo-check",
        "--ephemeral",
        "{arena}",
        "{options}",
        "--",
        "{prompt}",
    ],
    "claude": [
        "claude",
        "--print",
        "--verbose",
        "--output-format",
        "stream-json",
        "--no-session-persistence",
        "{arena}",
        "{options}",
        "--",
        "{prompt}",
    ],
    "opencode": [
        "{python}",
        "-I",
        "{arena}",
        "--format",
        "json",
        "{options}",
        "--",
        "{prompt}",
    ],
    "prime": [
        "node",
        "{arena}",
        "--print",
        "--mode",
        "json",
        "--no-session",
        "{options}",
        "--",
        "{prompt}",
    ],
}
TRACE_FORMATS = {"none", "arena", *NATIVE}
SUBSTITUTIONS = {
    "{seat}",
    "{seat_dir}",
    "{seed}",
    "{mcp}",
    "{mcp_json}",
    "{mcp_config}",
    "{python}",
    "{model}",
    "{effort}",
    "{arena}",
    "{options}",
    "{prompt}",
}


@dataclass(frozen=True)
class MatchConfig:
    project: Path
    executable: Path
    health: int
    seed: int | None
    watch: bool
    record: bool
    match_players: tuple[str, str]
    players: dict[str, dict]
    ruleset: str
    pool_mode: str
    placement: str


def _table(value, allowed, where):
    if not isinstance(value, dict):
        raise ValueError(f"{where}: expected a TOML table")  # noqa: TRY004 -- invalid config value
    unknown = value.keys() - set(allowed)
    if unknown:
        raise ValueError(f"{where}: unknown fields {', '.join(sorted(unknown))}")
    return value


def _path(directory, raw, resolve_engine):
    if not isinstance(raw, str) or not raw:
        raise ValueError("Specify a path or an environment variable reference")
    if not resolve_engine:
        return directory / raw

    def env(match):
        name = match[1]
        if not os.environ.get(name):
            raise ValueError(f"Before launching, set {name}")
        return os.environ[name]

    return (
        directory
        / Path(re.sub(r"\$\{([A-Za-z_][A-Za-z_0-9]*)\}", env, raw)).expanduser()
    ).resolve()


def _text(value, where, max_length=160):
    if not isinstance(value, str) or not value.strip() or len(value) > max_length:
        raise ValueError(
            f"{where}: expected a nonempty string of at most {max_length} characters"
        )
    return value


def _argv(value, where):
    if (
        not isinstance(value, list)
        or not value
        or not all(isinstance(a, str) for a in value)
        or not value[0]
    ):
        raise ValueError(f"{where}: expected a nonempty array of argv strings")
    for arg in value:
        if re.fullmatch(r"\{[a-z_]+\}", arg) and arg not in SUBSTITUTIONS:
            raise ValueError(f"{where}: unknown argv placeholder {arg}")
    return value


def _profile(name, values):
    if not ID.fullmatch(name):
        raise ValueError(f"Invalid harness id: {name}")
    row = _table(values, {"adapter", "command", "trace_format"}, f"harnesses.{name}")
    adapter = row.get("adapter", "stdio")
    if not isinstance(adapter, str) or adapter not in {"stdio", *NATIVE}:
        raise ValueError(f"{name}: unknown MCP adapter {adapter!r}")
    command = _argv(row.get("command", NATIVE.get(adapter)), f"{name}.command")
    if "{prompt}" not in command:
        raise ValueError(
            f"{name}.command: include {{prompt}} for the seat's instructions"
        )
    if adapter == "stdio" and ("{options}" in command or "{arena}" in command):
        raise ValueError(
            f"{name}: a stdio profile accepts {{mcp}}, {{model}} and {{effort}}"
        )
    if adapter in NATIVE and ("{arena}" not in command or "{options}" not in command):
        raise ValueError(
            f"{name}.command: native adapters require {{arena}} and {{options}}"
        )
    trace = row.get("trace_format", "arena" if adapter == "stdio" else adapter)
    if not isinstance(trace, str) or trace not in TRACE_FORMATS:
        raise ValueError(f"{name}.trace_format: choose from {sorted(TRACE_FORMATS)}")
    return {"adapter": adapter, "command": list(command), "trace_format": trace}


def _player(name, values, profiles):
    if not ID.fullmatch(name):
        raise ValueError(f"Invalid player ID: {name!r}")
    if name in {"match", "results", "record-frames"} or re.fullmatch(
        r"game-[0-9]+(?:-.*)?", name
    ):
        raise ValueError(f"Reserved player ID: {name}")
    row = dict(
        _table(
            values,
            {
                "kind",
                "harness",
                "rating_id",
                "display_name",
                "model",
                "effort",
                "command",
                "policy",
            },
            f"players.{name}",
        ),
        id=name,
    )
    for field in ("harness", "rating_id", "display_name", "model", "effort"):
        if field in row:
            _text(row[field], f"{name}.{field}")
    kind = row.get("kind", "harness" if "harness" in row else None)
    if not isinstance(kind, str) or kind not in {
        "random",
        "campaign",
        "human",
        "command",
        "harness",
        *NATIVE,
    }:
        raise ValueError(f"{name}: unknown kind {kind!r}")
    if "harness" in row and kind != "harness":
        raise ValueError(f"{name}: use either kind or harness")
    if "command" in row and kind != "command" or "policy" in row and kind != "random":
        raise ValueError(
            f"{name}: command and policy apply only to their respective player kind"
        )
    row["kind"] = kind
    if kind == "human":
        if "model" in row or "effort" in row:
            raise ValueError(f"{name}: human players use the browser table")
        row.update(harness="browser", trace_format="none")
        row.setdefault("rating_id", name)
        row.setdefault("display_name", "You")
        return row
    if kind == "campaign":
        if "model" in row or "effort" in row:
            raise ValueError(f"{name}: the campaign opponent runs in Unity")
        row.update(harness="Card Wars", trace_format="none")
        row.setdefault("rating_id", "cardwars-campaign-mirror-v1")
        row.setdefault("display_name", "Campaign AI")
        return row
    if kind in {"random", "command"}:
        if "model" in row or "effort" in row:
            raise ValueError(
                f"{name}: use a harness profile to select model and effort"
            )
        row.update(harness=kind, trace_format="none")
        if kind == "command":
            args = _argv(row.get("command"), f"{name}.command")
            default_id = (
                "command-" + hashlib.sha256(json.dumps(args).encode()).hexdigest()[:12]
            )
        else:
            policy = row.setdefault("policy", "uniform")
            if policy not in ("uniform", "play-first"):
                raise ValueError(f"{name}.policy: unknown random strategy")
            default_id = f"random-{policy}-v1"
        row.setdefault("rating_id", default_id)
        return row
    harness = row.get("harness", kind)
    if harness not in profiles:
        raise ValueError(f"{name}: unknown harness {harness!r}")
    profile = profiles[harness]
    for key in ("model", "effort"):
        token = "{" + key + "}"
        if token in profile["command"] and key not in row:
            raise ValueError(f"{name}: {token} requires {key}")
        if (
            profile["adapter"] == "stdio"
            and key in row
            and token not in profile["command"]
        ):
            raise ValueError(
                f"{name}: include {token} in the harness command to apply {key}"
            )
    if profile["adapter"] == "opencode" and "effort" in row and "model" not in row:
        raise ValueError(f"{name}: OpenCode requires model to select a variant")
    row.update(profile, harness=harness, kind="harness")
    # Keep labels readable but hash the full tuple to avoid collisions across separators,
    # templates, and different model/settings under the same human-provided alias.
    identity = [harness, profile, row.get("model"), row.get("effort")]
    digest = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()[
        :16
    ]
    label = row.get("rating_id") or "-".join(
        str(item)
        for item in (harness, row.get("model", "default"), row.get("effort", "default"))
    )
    row["rating_id"] = f"{label[:140]}-{digest}"
    return row


def load_config(path: Path, *, resolve_engine=True) -> MatchConfig:
    path = Path(path).resolve()
    with path.open("rb") as file:
        data = tomllib.load(file)
    _table(data, {"engine", "match", "players", "harnesses"}, str(path))
    engine = _table(data.get("engine"), {"project", "executable"}, "engine")
    match = _table(
        data.get("match"),
        {
            "players",
            "health",
            "seed",
            "watch",
            "record",
            "games",
            "rules_version",
            "pool",
            "placement",
        },
        "match",
    )
    roster = data.get("players")
    if not isinstance(roster, dict):
        raise ValueError("Expected [players.<id>] tables")  # noqa: TRY004 -- invalid config value
    profiles = {name: _profile(name, {"adapter": name}) for name in NATIVE}
    custom = data.get("harnesses", {})
    if not isinstance(custom, dict):
        raise ValueError("harnesses must be a table")  # noqa: TRY004 -- invalid TOML value
    profiles.update({name: _profile(name, row) for name, row in custom.items()})
    players = {name: _player(name, row, profiles) for name, row in roster.items()}
    pair = match.get("players")
    if (
        not isinstance(pair, list)
        or len(pair) != 2
        or any(not isinstance(n, str) or n not in players for n in pair)
        or pair[0] == pair[1]
    ):
        raise ValueError("match.players requires two distinct IDs from [players]")
    if type(match.get("games", 5)) is not int or match.get("games", 5) != 5:
        raise ValueError("A match must contain exactly five games")
    health = match.get("health", 100)
    seed = match.get("seed")
    if type(health) is not int or not 1 <= health <= 2**31 - 1:
        raise ValueError("match.health: expected a positive Int32")
    if seed is not None and type(seed) is not int:
        raise ValueError("match.seed: expected an integer")
    for key in ("watch", "record"):
        if key in match and type(match[key]) is not bool:
            raise ValueError(f"match.{key}: expected true or false")
    pool_mode = match.get("pool", "no_obsidian")
    if pool_mode not in ("sample40", "full", "no_obsidian"):
        raise ValueError("match.pool: expected sample40, full or no_obsidian")
    rules = match.get("rules_version", "cardwars-v1-on-turn-40-20-bo5")
    if not isinstance(rules, str) or not ID.fullmatch(rules):
        raise ValueError(
            "match.rules_version: expected a short ruleset identifier"
        )
    if pool_mode != "sample40":
        pool_tag = "full272" if pool_mode == "full" else "noobs258"
        rules = match.get("rules_version", "cardwars-v2") + f"-{pool_tag}-20-bo5"
    placement = match.get("placement", "before_cards")
    if placement not in ("own_turn", "before_cards"):
        raise ValueError("match.placement: expected own_turn or before_cards")
    if placement == "before_cards":
        rules += "-landfirst"
    return MatchConfig(
        _path(path.parent, engine.get("project"), resolve_engine),
        _path(path.parent, engine.get("executable", UNITY_MAC), resolve_engine),
        health,
        seed,
        match.get("watch", False),
        match.get("record", False),
        tuple(pair),
        players,
        f"{rules}-hp{health}",
        pool_mode,
        placement,
    )
