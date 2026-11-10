"""Exercise the draft protocol against a recovered Unity card catalog."""

import asyncio
import json
import os
import re
import sys
import unittest
from contextlib import AsyncExitStack, closing
from pathlib import Path
from tempfile import TemporaryDirectory

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from cardwars.arena import draft as arena


async def call(client, tool, **arguments):
    result = await client.call_tool(tool, arguments)
    assert not result.isError, result.content
    return json.loads(result.content[0].text)


async def check(match):
    async with AsyncExitStack() as stack:
        clients = []
        for seat in arena.SEATS:
            server = StdioServerParameters(
                command=sys.executable,
                args=["-m", "cardwars.tools.mcp_server", str(match), seat],
            )
            reader, writer = await stack.enter_async_context(stdio_client(server))
            client = await stack.enter_async_context(ClientSession(reader, writer))
            await client.initialize()
            clients.append(client)
        pending = await call(clients[0], "get_state", include_catalog=True)
        assert pending["phase"] == "waiting_to_start" and "catalog" not in pending
        arena.start(match)
        first, second = clients
        initial = await asyncio.gather(*(call(c, "get_state") for c in clients))
        catalog = initial[0]["catalog"]
        assert initial[1]["catalog"] == catalog
        assert not re.search(r"[А-Яа-яЁё]", catalog)
        for seat in arena.SEATS:
            assert (match / seat / "catalog.md").read_text(encoding="utf-8") == catalog
        cards_section, heroes_section = catalog.split("## Heroes")
        item = r"^- `([^`]+)`"
        cards = re.findall(item, cards_section, re.MULTILINE)
        heroes = re.findall(item, heroes_section, re.MULTILINE)
        assert len(cards) == len(set(cards)) == 40
        assert heroes and "<val" not in catalog and "!!" not in catalog
        for card_id, faction, bonus in (("Leader_PrincessCookie", "Swamp", 4),
                                        ("Leader_SuperPrincessCookie", "Cotton", 8)):
            entry = next(line for line in heroes_section.splitlines() if f"`{card_id}`" in line)
            assert faction in entry and f"+{bonus} attack" in entry.lower()

        castle = next(
            line
            for line in cards_section.splitlines()
            if "`Building_GhostCastle`" in line
        )
        assert castle.endswith(
            "Creature in this lane gets +8 Attack and +8 Defense."
        )

        for hero, deck, error in (
            ("outside", cards[:20], "Hero outside the catalog"),
            (heroes[0], cards[:19], "exactly 20"),
            (heroes[0], cards[:19] + [cards[0]], "Duplicate cards"),
            (heroes[0], cards[:19] + ["outside"], "Cards outside the pool"),
        ):
            response = await first.call_tool(
                "submit_deck", {"hero_id": hero, "card_ids": deck}
            )
            assert response.isError and error in response.content[0].text
        assert (await call(first, "get_state"))["own_deck"] is None
        roster = {"hero_id": heroes[0], "card_ids": cards[:20]}
        assert (await call(first, "submit_deck", **roster))["accepted"]
        assert (await call(first, "submit_deck", **roster))["accepted"]
        other = await call(second, "get_state")
        assert other["own_deck"] is None and cards[0] not in json.dumps(other)
        assert (await call(second, "submit_deck", **roster))["accepted"]
        other = await call(second, "get_state")
        assert other["phase"] == "decks_ready" and other["own_deck"] == roster["card_ids"]
        assert (await call(second, "get_state", include_catalog=True))[
            "catalog"
        ] == catalog


def check_expiration(project, match):
    arena.prepare(project, match, 42)
    arena.start(match)
    with closing(arena.connect(match)) as db:
        row = db.execute("SELECT heroes, cards FROM match").fetchone()
    hero = json.loads(row["heroes"])[0]
    deck = json.loads(row["cards"])[:20]
    arena.submit(match, "astra", hero, deck)
    with closing(arena.connect(match)) as db, db:
        db.execute("UPDATE match SET deadline=1")
    assert arena.state(match, "astra")["result"] == "technical_win"
    assert arena.state(match, "claude")["result"] == "technical_loss"
    try:
        arena.submit(match, "claude", hero, deck)
    except ValueError as exc:
        assert "deadline has expired" in str(exc)
    else:
        raise AssertionError("Late roster was accepted")


def check_draft(project):
    with TemporaryDirectory() as tmp:
        match = Path(tmp) / "draft"
        arena.prepare(project, match, 42)
        asyncio.run(check(match))
        check_expiration(project, Path(tmp) / "expired")


class NativeCatalogTest(unittest.TestCase):
    @unittest.skipUnless(os.environ.get("CARDWARS_UNITY_PROJECT"), "requires real Blueprints")
    def test_league_catalog_pages_on_both_mcp_seats(self):
        async def read_pages(match, seat):
            server = StdioServerParameters(command=sys.executable,
                args=["-m", "cardwars.tools.mcp_server", str(match), seat])
            async with stdio_client(server) as (reader, writer), ClientSession(reader, writer) as client:
                await client.initialize()
                first = await call(client, "get_state", catalog_page=1)
                pages = [first["catalog"]]
                for n in range(2, first["catalog_pages"] + 1):
                    pages.append((await call(client, "get_state", catalog_page=n))["catalog"])
                return "\n".join(pages) + "\n"

        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "draft"
            arena.prepare(Path(os.environ["CARDWARS_UNITY_PROJECT"]), path, 10, pool_mode="no_obsidian")
            arena.start(path)
            for seat in arena.SEATS:
                with self.subTest(seat=seat):
                    catalog = asyncio.run(read_pages(path, seat))
                    self.assertEqual(catalog, (path / seat / "catalog.md").read_text())
                    self.assertEqual(len(re.findall(r"^- `", catalog, re.MULTILINE)), 330)
                    cookie = next(line for line in catalog.splitlines() if "`Leader_SuperPrincessCookie`" in line)
                    self.assertIn("Cotton", cookie)
                    self.assertNotIn("Swamp", cookie)

    @unittest.skipUnless(
        os.environ.get("CARDWARS_UNITY_PROJECT"),
        "set CARDWARS_UNITY_PROJECT to run with real blueprints",
    )
    def test_draft_with_native_catalog(self):
        check_draft(Path(os.environ["CARDWARS_UNITY_PROJECT"]))


if __name__ == "__main__":
    check_draft(Path(sys.argv[1]))
    print(
        "OK: public catalog, deck validation, private submissions, retries and time limit"
    )
