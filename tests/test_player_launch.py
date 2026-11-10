"""The OS boundary must hold even when a participant knows the other socket's address."""

import os
import shutil
import socket
import subprocess
import sys
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

from cardwars.arena.draft import prepare, start
from cardwars.players.launch import launch_command, protect_harness
from cardwars.tools.broker import seat_socket


@unittest.skipUnless(sys.platform == "darwin", "macOS Seatbelt")
class PlayerIsolationTest(unittest.TestCase):
    def test_custom_python_reads_real_seat_with_venv_mcp(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            directory = root / "match"
            catalog = "Synthetic public marker"
            with patch(
                "cardwars.arena.draft.make_catalog", return_value=(catalog, [], [], {})
            ):
                prepare(root, directory, 7, seats=("one", "two"))
            start(directory)
            script = root / "client.py"
            script.write_text("""
import asyncio, json, os, sys
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def main():
    command = json.loads(os.environ["CARDWARS_MCP_COMMAND"])
    assert sys.prefix == sys.argv[1]
    params = StdioServerParameters(command=command[0], args=command[1:])
    async with stdio_client(params) as streams, ClientSession(*streams) as session:
        await session.initialize()
        reply = await session.call_tool("get_state", {})
        assert not reply.isError
        print(json.loads(reply.content[0].text)["catalog"])
asyncio.run(main())
""")
            player = {
                "kind": "command",
                "command": ["{python}", str(script), sys.prefix],
            }
            with seat_socket(directory, "one"):
                cmd = launch_command(player, directory, "one", seed=7)
                result = subprocess.run(
                    cmd,
                    check=False,
                    cwd=directory / "one",
                    capture_output=True,
                    text=True,
                    timeout=15,
                )
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertEqual(catalog, result.stdout.strip())

    def test_match_files_and_sockets(self):
        with ExitStack() as stack:
            root = Path(stack.enter_context(tempfile.TemporaryDirectory()))
            match = root / "match"
            seat = match / "one"
            other = match / "two"
            seat.mkdir(parents=True)
            other.mkdir()
            (match / "match.sqlite").write_text("private")
            (other / "rules.md").write_text("private")
            (seat / "rules.md").write_text("mine")
            sockets = []
            for _ in range(2):
                address = Path(
                    stack.enter_context(
                        tempfile.TemporaryDirectory(prefix="cw-", dir="/tmp")
                    )
                )
                path = (address / "arena.sock").resolve()
                listener = stack.enter_context(
                    socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                )
                listener.bind(str(path))
                listener.listen(2)
                sockets.append(str(path))
            (seat / "arena.sock").symlink_to(sockets[0])
            script = root / "probe.py"
            script.write_text("""
import os, socket, sys
from pathlib import Path
assert Path("rules.md").read_text() == "mine"
for path in ("../match.sqlite", "../two/rules.md"):
    try:
        Path(path).read_bytes()
    except PermissionError:
        pass
    else:
        raise AssertionError(path)
for index, path in enumerate(sys.argv[1:3]):
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as conn:
        try:
            conn.connect(path)
        except PermissionError:
            assert index == 1
        else:
            assert index == 0
if sys.argv[3] == "command":
    assert "ARENA_TEST_SECRET" not in os.environ
    try:
        Path("rules.md").write_text("tampered")
    except PermissionError:
        pass
    else:
        raise AssertionError("writable rules")
""")
            for kind in ("command", "harness"):
                with self.subTest(kind=kind):
                    argv = [sys.executable, str(script), *sockets, kind]
                    if kind == "command":
                        argv = launch_command(
                            {"kind": kind, "command": argv}, match, "one", seed=1
                        )
                    else:
                        argv = protect_harness(argv, match, "one", sockets[0])
                    subprocess.run(
                        argv,
                        check=True,
                        cwd=seat,
                        env={**os.environ, "ARENA_TEST_SECRET": "sentinel"},
                        timeout=10,
                    )


class HarnessProfilesTest(unittest.TestCase):
    def load(self, text):
        from cardwars.config import load_config

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "match.toml"
            path.write_text(
                '[engine]\nproject="."\n[match]\nplayers=["a","b"]\n[players.b]\nkind="random"\n'
                + text
            )
            return load_config(path, resolve_engine=False).players["a"]

    def test_rating_tracks_applied_options_and_command_not_alias(self):
        profile = (
            '[harnesses.mine]\nadapter="stdio"\n'
            'command=["my-cli","{model}","{effort}","{mcp_json}","{prompt}"]\n'
            '[players.a]\nharness="mine"\nmodel="M"\neffort="high"\nrating_id="alias"'
        )
        base = self.load(profile)
        for changed in (
            profile.replace('model="M"', 'model="M2"'),
            profile.replace('effort="high"', 'effort="medium"'),
            profile.replace('"my-cli"', '"my-cli","--versioned"'),
        ):
            self.assertNotEqual(base["rating_id"], self.load(changed)["rating_id"])
        self.assertEqual(
            base["rating_id"], self.load(profile + '\ndisplay_name="Me"')["rating_id"]
        )
        self.assertEqual(
            {"kind": "harness", "trace_format": "arena", "harness": "mine"},
            {k: base[k] for k in ("kind", "trace_format", "harness")},
        )
        with self.assertRaisesRegex(ValueError, "include.*effort"):
            self.load(profile.replace(',"{effort}"', ""))
        with self.assertRaisesRegex(ValueError, "prompt"):
            self.load(profile.replace(',"{prompt}"', ""))

    def test_legacy_native_spelling_is_equivalent(self):
        self.assertEqual(
            self.load('[players.a]\nkind="codex"'),
            self.load('[players.a]\nharness="codex"'),
        )

    def test_templates_reach_real_command_and_current_rules(self):
        from cardwars.config import load_config

        path = Path(__file__).resolve().parents[1] / "configs/arena100.toml"
        config = load_config(path, resolve_engine=False)
        with (
            tempfile.TemporaryDirectory() as tmp,
            patch(
                "cardwars.players.launch.protect_harness",
                side_effect=lambda argv, *args, **kwargs: argv,
            ),
        ):
            directory = Path(tmp)
            seat = directory / "one"
            seat.mkdir()
            (seat / "rules.md").write_text("Rules specific to game settings")
            (seat / "arena.sock").touch()
            actual_which = shutil.which
            for name, player in config.players.items():
                if player["kind"] != "harness":
                    continue
                with self.subTest(name=name):
                    if name == "prime" and not shutil.which("prime-agent"):
                        continue
                    with patch(
                        "cardwars.players.launch.shutil.which",
                        side_effect=lambda name: actual_which(name) or "/bin/echo",
                    ):
                        argv = launch_command(player, directory, "one", seed=8)
                    self.assertIn("Rules specific to game settings", argv[-1])
                    self.assertIn("five-game", argv[-1])
                    self.assertIn("comment in English", argv[-1])
                    args = argv[:-1]
                    self.assertNotIn("{arena}", args)
                    self.assertNotIn("{options}", args)
                    self.assertTrue(any(player["effort"] in value for value in args))
                    self.assertTrue(
                        any(player["model"].split("/")[-1] in value for value in args)
                    )

    @unittest.skipUnless(sys.platform == "darwin", "macOS Seatbelt")
    def test_custom_authenticated_harness_receives_rules_and_real_mcp(self):
        import json

        config = self.load(
            '[harnesses.demo]\ncommand=["{python}", "-I", "{seat_dir}", "{model}", '
            '"{effort}", "{prompt}"]\n[players.a]\nharness="demo"\nmodel="mock"\neffort="low"'
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            directory = root / "match"
            with patch(
                "cardwars.arena.draft.make_catalog",
                return_value=("catalog", [], [], {}),
            ):
                prepare(root, directory, seed=93, seats=("a", "b"))
            # Python treats a directory with __main__.py as a runnable program.
            (directory / "a" / "__main__.py").write_text("""
import asyncio, json, os, sys
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
async def run():
    command, *args = json.loads(os.environ["CARDWARS_MCP_COMMAND"])
    params = StdioServerParameters(command=command, args=args)
    async with stdio_client(params) as streams, ClientSession(*streams) as session:
        await session.initialize()
        rules = await session.call_tool("read_rules", {})
        assert rules.content[0].text in sys.argv[3]
        assert sys.argv[1:3] == ["mock", "low"] and os.environ["CARDWARS_TEST_PROVIDER"] == "test"
        print(json.dumps({"type": "arena.message", "text": "Ready"}))
asyncio.run(run())
""")
            with seat_socket(directory, "a"):
                argv = launch_command(config, directory, "a", seed=2)
                completed = subprocess.run(
                    argv,
                    cwd=directory / "a",
                    check=True,
                    capture_output=True,
                    text=True,
                    timeout=15,
                    env={**os.environ, "CARDWARS_TEST_PROVIDER": "test"},
                )
            self.assertEqual(
                json.loads(completed.stdout), {"type": "arena.message", "text": "Ready"}
            )
