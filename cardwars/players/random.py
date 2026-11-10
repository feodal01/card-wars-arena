"""Play one seat for an entire match using only its public MCP tools."""
# /// script
# requires-python = ">=3.11"
# dependencies = ["mcp==1.30.0"]
# ///
import argparse
import asyncio
import json
import random
import re
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


def parse_catalog(catalog: str) -> tuple[list[str], list[str]]:
    cards_text, heroes_text = re.split(r"^## (?:Heroes|Герои)$", catalog, flags=re.MULTILINE)
    pattern = r"^- `([^`]+)`"
    cards = re.findall(pattern, cards_text, re.MULTILINE)
    heroes = re.findall(pattern, heroes_text, re.MULTILINE)
    if len(cards) not in (40, 258, 272) or len(set(cards)) != len(cards) or not heroes:
        raise ValueError("Expected 40, 258 or 272 distinct cards and at least one hero in the MCP catalog")
    return cards, heroes


def choose_action(actions, rng: random.Random, policy: str):
    if policy == "play-first":
        plays = [action for action in actions if action["id"].rsplit("/", 1)[-1] != "end"]
        if plays:
            return rng.choice(plays)
    return rng.choice(actions)


async def play(session: ClientSession, rng: random.Random, policy: str) -> None:
    catalog = None
    roster_game = None
    roster = None
    previous_phase = None
    rejections = 0
    while True:
        response = await session.call_tool("get_state", {"include_catalog": catalog is None})
        if response.isError:
            raise RuntimeError(response.content[0].text)
        state = json.loads(response.content[0].text)
        game, phase = state["game"], state["phase"]
        if (game, phase) != previous_phase:
            print(f"Game {game}: {phase}", flush=True)
            previous_phase = (game, phase)
        if phase == "match_over":
            return
        if "catalog" in state:
            catalog = parse_catalog(state["catalog"])
        if phase == "select_deck" and state["own_deck"] is None:
            if catalog is None:
                raise ValueError("The seat was asked to select a deck without a catalog")
            if roster_game != game:
                cards, heroes = catalog
                roster = {"game": game, "hero_id": rng.choice(heroes),
                          "card_ids": rng.sample(cards, 20)}
                roster_game = game
            result = await session.call_tool("submit_deck", roster)
            if not result.isError:
                draft = json.loads(result.content[0].text)
                if not draft["accepted"]:
                    # Pre-on-turn series request a lane order when resuming an earlier match.
                    tiles = draft["required_landscapes"]
                    if len(tiles) != 4 or "landscapes" in roster:
                        raise ValueError("Invalid request for an earlier match's landscape order")
                    roster["landscapes"] = rng.sample(tiles, 4)
                elif "landscapes" not in roster and len(draft["required_landscapes"]) != 4:
                    raise ValueError("Expected four tiles for battle")
        elif state.get("actions"):
            action = choose_action(state["actions"], rng, policy)
            result = await session.call_tool("act", {"action_id": action["id"]})
            if not result.isError:
                print(f"Game {game}: {action['label']}", flush=True)
        else:
            await asyncio.sleep(0.12)
            continue
        if result.isError:
            # Re-read the seat's state: the decision may already have expired.
            rejections += 1
            reason = result.content[0].text
            print(f"Game {game}: decision rejected: {reason}", file=sys.stderr, flush=True)
            if rejections >= 10:
                raise RuntimeError(f"Ten consecutive decisions rejected: {reason}")
            await asyncio.sleep(0.12)
        else:
            rejections = 0


async def run(server: StdioServerParameters, seed: int | None, policy: str = "uniform") -> None:
    async with stdio_client(server) as (reader, writer), ClientSession(reader, writer) as session:
        await session.initialize()
        await play(session, random.Random(seed), policy)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, help="Seed for this seat's decisions")
    parser.add_argument("--policy", choices=("uniform", "play-first"), default="uniform")
    parser.add_argument("server", help="Seat-bound MCP server executable")
    parser.add_argument("server_args", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    asyncio.run(run(StdioServerParameters(command=args.server, args=args.server_args), args.seed, args.policy))


if __name__ == "__main__":
    main()
