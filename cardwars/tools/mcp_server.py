"""Trusted, seat-bound MCP over stdio. Keep the organizer directory outside player access."""

import argparse
import os
import stat
import time
from contextlib import closing
from pathlib import Path

from cardwars.arena import matchplay
from cardwars.arena.draft import connect, state, submit


def serve(directory: Path, seat: str):
    with closing(connect(directory)) as db:
        if db.execute("SELECT 1 FROM players WHERE seat=?", (seat,)).fetchone() is None:
            raise ValueError("Unknown player seat.")
    from mcp.server.fastmcp import FastMCP

    server = FastMCP(
        "Card Wars",
        instructions="Call get_state. From the shared catalog, choose "
        "one hero and exactly 20 distinct cards, then call submit_deck. Use act to place tiles when place actions appear.",
    )

    seat_dir = directory / seat

    @server.tool()
    def read_rules() -> str:
        """Read the game rules and settings for this match."""
        fd = os.open(seat_dir / "rules.md", os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(fd, encoding="utf-8") as file:
            info = os.fstat(file.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                raise ValueError("Expected a regular rules file for this seat")
            return file.read()

    @server.tool()
    def get_state(
        include_catalog: bool = False,
        after_event: int | None = None,
        wait_seconds: int = 0,
        catalog_page: int | None = None,
    ) -> dict:
        """Read your current phase and time remaining. Your first call after the draft opens includes the catalog."""
        if not 0 <= wait_seconds <= 30:
            raise ValueError("wait_seconds must be between 0 and 30")
        if catalog_page is not None and catalog_page < 1:
            raise ValueError("catalog_page starts at 1")
        deadline = time.monotonic() + wait_seconds
        while True:
            observation = state(directory, seat, include_catalog or catalog_page is not None, after_event)
            if catalog_page is not None and observation.get("catalog"):
                lines = observation["catalog"].splitlines()
                pages = (len(lines) + 24) // 25
                if catalog_page > pages:
                    raise ValueError(f"catalog_page must be between 1 and {pages}")
                observation["catalog"] = "\n".join(lines[(catalog_page - 1) * 25:catalog_page * 25])
                observation["catalog_pages"] = pages
            if (
                observation.get("catalog")
                or observation.get("actions")
                or (
                    observation["phase"] == "select_deck"
                    and not observation["own_deck"]
                )
                or observation["phase"] in {"match_over", "selection_expired"}
                or (after_event is not None and observation.get("events"))
            ):
                return observation
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return observation
            time.sleep(min(remaining, 0.25))

    @server.tool()
    def submit_deck(
        hero_id: str,
        card_ids: list[str],
        game: int | None = None,
        landscapes: list[str] | None = None,
        comment: str | None = None,
    ) -> dict:
        """Lock in one hero and 20 cards for this game.

        After the draw, place the returned tiles using act. Give spectators a short
        plan in English in comment. Only legacy matches use landscapes.
        """
        return submit(directory, seat, hero_id, card_ids, game, landscapes, comment)

    @server.tool()
    def act(action_id: str, comment: str | None = None) -> dict:
        """Play an available action using its ID from get_state. Use comment for a short explanation in English for spectators."""
        with closing(connect(directory)) as db, db:
            return matchplay.accept_action(db, seat, action_id, comment)

    server.run(transport="stdio")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("seat")
    args = parser.parse_args()
    serve(args.directory, args.seat)


if __name__ == "__main__":
    main()
