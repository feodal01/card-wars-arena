"""Participant metadata safe to include in match evidence and spectator views."""

from pathlib import Path


def public_profile(player):
    harness = player.get("harness", player["kind"])
    label = player.get("display_name")
    if not label and player.get("model"):
        label = " · ".join(
            filter(None, (player["model"], player.get("effort"), harness))
        )
    profile = {
        "display_name": label or player["rating_id"],
        "harness": harness,
        "model": player.get("model"),
        "effort": player.get("effort"),
        "trace_format": player.get("trace_format", "none"),
    }
    command = player.get("command", [])
    if (
        player.get("adapter") == "codex"
        and len(command) >= 2
        and Path(command[0]).name == "codex"
        and command[1] == "exec"
        and "--json" in command
        and profile["trace_format"] == "codex"
    ):
        profile["reasoning_summary_format"] = "codex_exec"
    return profile
