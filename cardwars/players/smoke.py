"""Check an installed CLI's actual arena MCP connection without requesting model inference."""

import argparse
import asyncio
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from cardwars.arena.draft import prepare
from cardwars.players.launch import (
    TOOLS,
    claude_flags,
    codex_flags,
    harness_settings,
    protect_harness,
    relay_command,
)
from cardwars.tools.broker import seat_socket


async def check(kind: str, directory: Path, home: Path) -> None:
    relay = relay_command(directory, kind)
    seat = directory / kind
    env = os.environ.copy()
    writable = None
    if kind in {"prime", "opencode"}:
        extra_env, flags, writable = harness_settings(kind, relay, seat)
        env.update(extra_env)
        if kind == "opencode":
            args = [sys.executable, "-I", *flags, "--check"]
            argv = protect_harness(args, directory, kind, relay[-1], writable=writable)
            await asyncio.to_thread(
                subprocess.run, argv, cwd=seat, env=env, check=True, timeout=50
            )
            return
        env["CARDWARS_CHECK_MCP"] = "1"
        argv = ["node", *flags, "--mode", "rpc", "--no-session"]
    elif kind == "codex":
        # No model turn or user configuration is needed to exercise the native control protocol.
        env["CODEX_HOME"] = str(home)
        argv = ["codex", "app-server", *codex_flags(relay)]
    else:
        argv = [
            "claude",
            "--print",
            "--no-session-persistence",
            *claude_flags(relay),
            "--input-format",
            "stream-json",
            "--output-format",
            "stream-json",
            "--verbose",
        ]
    argv = protect_harness(argv, directory, kind, relay[-1], writable=writable)
    cli = await asyncio.create_subprocess_exec(
        *argv,
        cwd=seat,
        env=env,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=None,
        limit=4 * 1024 * 1024,
    )

    async def send(message):
        cli.stdin.write(json.dumps(message).encode() + b"\n")
        await cli.stdin.drain()

    async def request(number, method, params):
        if kind == "codex":
            await send({"id": number, "method": method, "params": params})
        else:
            await send(
                {
                    "type": "control_request",
                    "request_id": str(number),
                    "request": {"subtype": method, **params},
                }
            )
        while line := await cli.stdout.readline():
            message = json.loads(line)
            if kind == "codex" and message.get("id") == number:
                if "error" in message:
                    raise RuntimeError(f"{method}: {message['error']}")
                return message["result"]
            reply = message.get("response", {})
            if reply.get("request_id") == str(number):
                if reply.get("subtype") != "success":
                    raise RuntimeError(f"Claude rejected {method}")
                return reply["response"]
        raise RuntimeError(f"{kind} exited before answering {method}")

    try:
        async with asyncio.timeout(30):
            if kind == "prime":
                while line := await cli.stdout.readline():
                    event = json.loads(line)
                    if event.get("type") == "arena.ready":
                        inventory = set(event["tools"])
                        break
                else:
                    raise RuntimeError(
                        "Prime exited before verifying the MCP inventory"
                    )
            elif kind == "codex":
                await request(
                    1,
                    "initialize",
                    {
                        "clientInfo": {"name": "arena-check", "version": "1"},
                        "capabilities": {"experimentalApi": True},
                    },
                )
                await send({"method": "initialized", "params": {}})
                thread = await request(
                    2, "thread/start", {"ephemeral": True, "cwd": str(seat)}
                )
                thread_id = thread["thread"]["id"]
                servers = (
                    await request(3, "mcpServerStatus/list", {"threadId": thread_id})
                )["data"]
                if [s["name"] for s in servers] != ["arena"]:
                    raise RuntimeError("Unexpected Codex MCP inventory")
                inventory = set(servers[0]["tools"])
                state = await request(
                    4,
                    "mcpServer/tool/call",
                    {
                        "threadId": thread_id,
                        "server": "arena",
                        "tool": "get_state",
                        "arguments": {},
                    },
                )
                if (
                    state["isError"]
                    or json.loads(state["content"][0]["text"])["phase"]
                    != "waiting_to_start"
                ):
                    raise RuntimeError("Codex failed to read the synthetic draft")
            else:
                await request(1, "initialize", {})
                number = 2
                while True:
                    servers = (await request(number, "mcp_status", {}))["mcpServers"]
                    if [s["name"] for s in servers] != ["arena"]:
                        raise RuntimeError("Unexpected Claude MCP inventory")
                    server = servers[0]
                    if server["status"] != "pending":
                        break
                    number += 1
                    await asyncio.sleep(0.15)
                if server["status"] != "connected":
                    raise RuntimeError(f"Claude MCP status: {server['status']}")
                inventory = {tool["name"] for tool in server["tools"]}
            if inventory != set(TOOLS):
                raise RuntimeError(
                    f"{kind} listed unexpected tools: {sorted(inventory)}"
                )
        print(f"{kind}: connected, {', '.join(sorted(inventory))}")
    finally:
        if cli.returncode is None:
            cli.kill()
        await cli.wait()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("kind", choices=("codex", "claude", "opencode", "prime"))
    parser.add_argument(
        "--project",
        type=Path,
        required=True,
        help="Unity project with public card blueprints",
    )
    args = parser.parse_args()
    check_player(args.kind, args.project)


def check_player(kind, project):
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        directory = root / "match"
        home = root / "codex"
        home.mkdir()
        prepare(project, directory, seed=0, seats=(kind, "opponent"))
        with seat_socket(directory, kind):
            asyncio.run(check(kind, directory, home))


if __name__ == "__main__":
    main()
