"""Public MCP contract: two real stdio clients over independently bound sockets."""

import asyncio
import json
import tempfile
import unittest
from contextlib import AsyncExitStack, ExitStack, closing
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from cardwars.arena import draft
from cardwars.players.launch import relay_command
from cardwars.tools.broker import seat_socket


class SeatToolsTest(unittest.TestCase):
    def test_rules_and_quiet_wait_are_seat_bound(self):
        asyncio.run(self.exercise())

    async def exercise(self):
        # This test needs only storage. The native end-to-end run exercises the real blueprints.
        with tempfile.TemporaryDirectory() as temp, ExitStack() as stack:
            base = Path(temp)
            for seat in ("alpha", "bravo"):
                work = base / seat
                work.mkdir()
                (work / "rules.md").write_text("test rules")
            import sqlite3

            with closing(sqlite3.connect(base / "match.sqlite")) as db, db:
                db.execute(
                    "CREATE TABLE players(seat TEXT PRIMARY KEY, catalog_seen INT, hero TEXT,deck TEXT,layout TEXT,tiles TEXT)"
                )
                db.executemany(
                    "INSERT INTO players VALUES (?,0,NULL,NULL,NULL,NULL)",
                    [("alpha",), ("bravo",)],
                )
                db.execute("CREATE TABLE match(catalog TEXT,deadline REAL)")
                db.execute("INSERT INTO match VALUES('synthetic cards',NULL)")
            async with AsyncExitStack() as sessions:
                clients = []
                for seat in ("alpha", "bravo"):
                    stack.enter_context(seat_socket(base, seat))
                    command = relay_command(base, seat)
                    args = StdioServerParameters(command=command[0], args=command[1:])
                    r, w = await sessions.enter_async_context(stdio_client(args))
                    c = await sessions.enter_async_context(ClientSession(r, w))
                    welcome = await c.initialize()
                    self.assertIn("one hero and exactly 20 distinct cards", welcome.instructions)
                    clients.append(c)
                a, b = clients
                tools = (await a.list_tools()).tools
                for tool in tools:
                    self.assertNotRegex(tool.description, r"[А-Яа-яЁё]")
                self.assertEqual(
                    {t.name for t in tools},
                    {
                        "get_state",
                        "submit_deck",
                        "act",
                        "read_rules",
                    },
                )
                self.assertEqual(
                    (await a.call_tool("read_rules", {})).content[0].text, "test rules"
                )
                (base / "bravo/rules.md").unlink()
                (base / "bravo/rules.md").symlink_to(base / "alpha/rules.md")
                self.assertTrue((await b.call_tool("read_rules", {})).isError)
                waiting = asyncio.create_task(
                    a.call_tool("get_state", {"wait_seconds": 4})
                )
                await asyncio.sleep(0.25)
                self.assertFalse(waiting.done())
                draft.start(base)
                view = json.loads((await waiting).content[0].text)
                self.assertEqual(view["catalog"], "synthetic cards")
                self.assertEqual(view["phase"], "select_deck")
                self.assertTrue(
                    (await a.call_tool("get_state", {"wait_seconds": 31})).isError
                )
