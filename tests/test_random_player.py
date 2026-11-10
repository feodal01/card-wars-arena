"""Exercise the random seat against a separate stdio MCP process across five games."""
import asyncio
import io
import random
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from mcp import StdioServerParameters
from mcp.server.fastmcp import FastMCP

from cardwars.players.random import choose_action, run


def serve_fixture(legacy=False) -> None:
    server = FastMCP("Random seat test", log_level="ERROR")
    game = 1
    accepted_decks = []
    accepted_layouts = []
    tiles = ["Swamp", "Plains", "Swamp", "Corn"]
    layout = {}
    previewed = {}
    submitted = None
    actions = []
    stale = True
    end_game = False
    cards = [f"card-{n}" for n in range(40)]
    heroes = ["hero-1", "hero-2"]
    card_heading, hero_heading = ("## Карты", "## Герои") if legacy else ("## Cards", "## Heroes")
    catalog = "\n".join([
        card_heading, *(f"- `{c}` card" for c in cards),
        hero_heading, *(f"- `{h}` hero" for h in heroes),
    ])

    @server.tool()
    def get_state(include_catalog: bool = False) -> dict:
        nonlocal game, end_game, submitted
        if end_game:
            end_game = False
            game += 1
            submitted = None
            layout.clear()
            return {"game": game - 1, "phase": "game_over"}
        if game == 6:
            assert len(set(accepted_decks)) > 1
            assert len(set(accepted_layouts)) > 1
            assert len(set(actions)) > 1
            return {"game": 5, "phase": "match_over"}
        if submitted is None:
            state = {"game": game, "phase": "select_deck", "own_deck": None}
            if include_catalog:
                state["catalog"] = catalog
            return state
        prefix = "stale" if stale else str(game)
        if len(layout) < 4:
            remaining = list(tiles)
            for tile in layout.values():
                remaining.remove(tile)
            placements = [f"place:{tile}:{lane}" for tile in sorted(set(remaining))
                          for lane in range(4) if lane not in layout]
            return {"game": game, "phase": "battle", "actions": [
                {"id": f"{prefix}/{p}", "label": p} for p in placements]}
        return {"game": game, "phase": "battle", "actions": [
            {"id": f"{prefix}/{i}", "label": f"option-{i}"} for i in range(4)]}

    @server.tool()
    def submit_deck(hero_id: str, card_ids: list[str], game: int,
                    landscapes: list[str] | None = None) -> dict:
        nonlocal submitted
        assert game == len(accepted_decks) + 1
        assert submitted is None and hero_id in heroes
        assert len(card_ids) == len(set(card_ids)) == 20 and set(card_ids) <= set(cards)
        if legacy:
            if landscapes is None:
                previewed[game] = (hero_id, card_ids)
                return {"accepted": False, "required_landscapes": tiles}
            assert (hero_id, card_ids) == previewed[game] and sorted(landscapes) == sorted(tiles)
            layout.update(enumerate(landscapes))
            accepted_layouts.append(tuple(landscapes))
        else:
            assert landscapes is None
        submitted = card_ids
        accepted_decks.append(tuple(card_ids))
        return {"accepted": True} if legacy else {"accepted": True, "required_landscapes": tiles}

    @server.tool()
    def act(action_id: str) -> dict:
        nonlocal stale, end_game
        if stale:
            stale = False
            raise ValueError("Decision expired")
        prefix, index = action_id.split("/")
        assert prefix == str(game)
        if len(layout) < 4:
            kind, tile, lane = index.split(":")
            assert kind == "place" and int(lane) not in layout and 0 <= int(lane) < 4
            assert list(layout.values()).count(tile) < tiles.count(tile)
            layout[int(lane)] = tile
            if len(layout) == 4:
                accepted_layouts.append(tuple(layout[i] for i in range(4)))
            return {"accepted": True}
        assert index in {"0", "1", "2", "3"}
        actions.append(index)
        end_game = True
        return {"accepted": True}

    server.run(transport="stdio")


class RandomPlayerTest(unittest.TestCase):
    def test_play_first(self):
        end = {"id": "1/3/end"}
        play = {"id": "1/3/play:1:2"}
        rng = random.Random(5)
        self.assertEqual(play, choose_action([play, end], rng, "play-first"))
        self.assertEqual(end, choose_action([end], rng, "play-first"))
        self.assertEqual(end, choose_action([play, end], random.Random(0), "uniform"))

    def test_five_games_over_stdio(self):
        self.check_series("--serve-fixture", 20)

    def test_resumed_pre_placement_series(self):
        self.check_series("--serve-legacy", 0)

    def check_series(self, fixture, expected_placements):
        server = StdioServerParameters(command=sys.executable, args=[str(Path(__file__).resolve()), fixture])
        output = io.StringIO()
        with redirect_stdout(output):
            asyncio.run(asyncio.wait_for(run(server, seed=123), timeout=30))
        self.assertEqual(expected_placements, output.getvalue().count("place:"))
        self.assertEqual(5, output.getvalue().count("game_over"))
        self.assertIn("Game 5: match_over", output.getvalue())


if __name__ == "__main__":
    if sys.argv[1:] in (["--serve-fixture"], ["--serve-legacy"]):
        serve_fixture(legacy=sys.argv[1] == "--serve-legacy")
    else:
        unittest.main()
