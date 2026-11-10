"""Prepare private game data and validate a seat's draft and observations."""

import json
import sqlite3
import tempfile
import time
from collections import Counter
from contextlib import closing
from pathlib import Path

from cardwars.commentary import decision_comment

from . import matchplay
from .catalog import make_catalog
from .landscapes import required_tiles
from .matchplay import DECK_SECONDS

SEATS = ("astra", "claude")


def prepare(project, destination, seed, seats=SEATS, pool_mode="sample40", health=25, placement="own_turn", campaign=False):
    if destination.exists():
        raise ValueError(f"Match directory already exists: {destination}")
    catalog, cards, heroes, factions = make_catalog(project, seed, pool_mode)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=destination.parent) as tmp:
        staging = Path(tmp) / "match"
        staging.mkdir(mode=0o700)
        rules = Path(__file__).with_name("rules.md").read_text(encoding="utf-8")
        if campaign:
            heading, rest = rules.split("## Before each game\n\n", 1)
            _, details = rest.split("\n\n", 1)
            rules = (heading + "## Before each game\n\nChoose one hero and 20 distinct cards "
                     "within ten minutes. The original campaign AI receives a copy of your hero and deck. "
                     "Each deck is shuffled separately. You can keep or change your picks between games.\n\n"
                     + details)
        settings = (
            f"This match has {len(cards)} available cards and {len(heroes)} heroes. "
            f"Each hero starts with {health} HP. "
        )
        if placement == "before_cards":
            settings += "The first player places four tiles, then the other player places four. Card play begins after both sides finish placement."
        else:
            settings += "Each player places four tiles at the start of their first turn."
        for seat in seats:
            player = staging / seat
            player.mkdir(mode=0o700)
            (player / "catalog.md").write_text(catalog, encoding="utf-8")
            (player / "rules.md").write_text(settings + "\n\n" + rules, encoding="utf-8")
        with closing(sqlite3.connect(staging / "match.sqlite")) as db, db:
            db.execute(
                "CREATE TABLE match(seed TEXT, catalog TEXT, cards TEXT, heroes TEXT, deadline REAL, factions TEXT)"
            )
            db.execute(
                "INSERT INTO match VALUES (?, ?, ?, ?, NULL, ?)",
                (
                    str(seed),
                    catalog,
                    json.dumps(cards),
                    json.dumps(heroes),
                    json.dumps(factions),
                ),
            )
            db.execute(
                "CREATE TABLE players(seat TEXT PRIMARY KEY, catalog_seen INTEGER DEFAULT 0,"
                " hero TEXT, deck TEXT, layout TEXT, tiles TEXT)"
            )
            db.executemany(
                "INSERT INTO players(seat) VALUES (?)", [(seat,) for seat in seats]
            )
        staging.rename(destination)


def connect(directory):
    db = sqlite3.connect(
        (directory / "match.sqlite").resolve().as_uri() + "?mode=rw", uri=True
    )
    db.row_factory = sqlite3.Row
    return db


def start(directory):
    with closing(connect(directory)) as db, db:
        cursor = db.execute(
            "UPDATE match SET deadline=? WHERE deadline IS NULL",
            (time.time() + DECK_SECONDS,),
        )
        if cursor.rowcount != 1:
            raise ValueError("The draft has already started.")


def state(directory, seat, include_catalog=False, after_event=None):
    with closing(connect(directory)) as db, db:
        db.execute("BEGIN IMMEDIATE")
        match = db.execute("SELECT catalog, deadline FROM match").fetchone()
        player = db.execute("SELECT * FROM players WHERE seat=?", (seat,)).fetchone()
        # Each seat can read only its own selections, even after both lock in.
        ready = db.execute(
            "SELECT COUNT(*) FROM players WHERE deck IS NOT NULL"
        ).fetchone()[0]
        deadline = match["deadline"]
        remaining = None if deadline is None else max(0, deadline - time.time())
        if ready == 2:
            phase = "decks_ready"
        elif deadline is None:
            phase = "waiting_to_start"
        elif remaining == 0:
            phase = "selection_expired"
        else:
            phase = "select_deck"
        result = {
            "phase": phase,
            "game": 1,
            "seconds_remaining": remaining,
            "own_hero": player["hero"],
            "own_deck": json.loads(player["deck"] or "null"),
        }
        if phase == "selection_expired":
            result["result"] = (
                "both_timed_out"
                if ready == 0
                else "technical_win"
                if player["deck"]
                else "technical_loss"
            )
        if deadline is not None and (include_catalog or not player["catalog_seen"]):
            result["catalog"] = match["catalog"]
            db.execute("UPDATE players SET catalog_seen=1 WHERE seat=?", (seat,))
        series = matchplay.current(db)
        if series is not None:
            if matchplay.places_on_turn(series):
                result["required_landscapes"] = json.loads(player["tiles"] or "null")
            elif "layout" in player.keys():  # noqa: SIM118 -- sqlite3.Row membership checks values.
                result["own_landscapes"] = json.loads(player["layout"] or "null")
            return matchplay.public_view(db, series, seat, result, after_event)
        return result


def submit(directory, seat, hero_id, card_ids, game=None, landscapes=None, comment=None):
    with closing(connect(directory)) as db, db:
        db.execute("BEGIN IMMEDIATE")
        match = db.execute("SELECT * FROM match").fetchone()
        series = matchplay.current(db)
        if series is not None and (
            series["phase"] != "select_deck" or game != series["game"]
        ):
            raise ValueError("Submit during the draft with the current game number.")
        saved = db.execute("SELECT * FROM players WHERE seat=?", (seat,)).fetchone()
        on_turn = matchplay.places_on_turn(series)
        if on_turn and landscapes is not None:
            raise ValueError(
                "Omit landscapes when submitting your deck. Place the tiles with act after the starting player is drawn."
            )
        if saved["deck"] is not None:
            same_layout = (
                on_turn or series is None or json.loads(saved["layout"]) == landscapes
            )
            if (
                saved["hero"] == hero_id
                and json.loads(saved["deck"]) == card_ids
                and same_layout
            ):
                if on_turn:
                    return {
                        "accepted": True,
                        "required_landscapes": json.loads(saved["tiles"]),
                    }
                return {"accepted": True}
            raise ValueError("Your hero and deck are already locked in.")
        if match["deadline"] is None:
            raise ValueError("The draft has not started.")
        if time.time() >= match["deadline"]:
            raise ValueError("The ten-minute draft deadline has expired.")
        if hero_id not in json.loads(match["heroes"]):
            raise ValueError(f"Hero outside the catalog: {hero_id}")
        if len(card_ids) != 20:
            raise ValueError(f"Expected exactly 20 cards, received {len(card_ids)}.")
        duplicates = [card for card, count in Counter(card_ids).items() if count > 1]
        if duplicates:
            raise ValueError("Duplicate cards: " + ", ".join(duplicates))
        unknown = sorted(set(card_ids) - set(json.loads(match["cards"])))
        if unknown:
            raise ValueError("Cards outside the pool: " + ", ".join(unknown))
        response = {"accepted": True}
        if series is not None:
            tiles = required_tiles(card_ids, json.loads(match["factions"]))
            roster = {"seat": seat, "hero": hero_id, "cards": card_ids}
            if on_turn:
                roster["required_landscapes"] = tiles
                response["required_landscapes"] = tiles
                db.execute(
                    "UPDATE players SET tiles=? WHERE seat=?", (json.dumps(tiles), seat)
                )
            else:
                if landscapes is None:
                    return {
                        "accepted": False,
                        "required_landscapes": tiles,
                        "instruction": "Order these four tiles in your lanes from left to right "
                        "and submit again using the landscapes parameter.",
                    }
                if Counter(tiles) != Counter(landscapes):
                    raise ValueError(
                        "This deck requires the following tiles: " + ", ".join(tiles)
                    )
                db.execute(
                    "UPDATE players SET layout=? WHERE seat=?",
                    (json.dumps(landscapes), seat),
                )
                roster["landscapes"] = landscapes
            matchplay.record(db, game, "submit_deck", {**roster, **decision_comment(comment)})
        db.execute(
            "UPDATE players SET hero=?, deck=? WHERE seat=?",
            (hero_id, json.dumps(card_ids), seat),
        )
    return response
