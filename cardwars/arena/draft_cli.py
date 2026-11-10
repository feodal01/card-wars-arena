"""Operator commands for standalone deck-selection checks."""

import argparse
import json
import secrets
from contextlib import closing
from pathlib import Path

from cardwars.tools.mcp_server import serve

from .draft import SEATS, connect, prepare, start


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    prep = commands.add_parser("prepare")
    prep.add_argument("directory", type=Path)
    prep.add_argument(
        "--project", type=Path, required=True, help="Root of the Card Wars Unity project"
    )
    prep.add_argument("--seed", type=int)
    opening = commands.add_parser(
        "opening", help="Print the private opening configuration for Unity"
    )
    opening.add_argument("directory", type=Path)
    opening.add_argument("--health", required=True, type=int)
    opening.add_argument(
        "--landscapes",
        required=True,
        nargs=4,
        choices=("Corn", "Plains", "Swamp", "Cotton", "Sand"),
    )
    for name in ("start", "serve"):
        sub = commands.add_parser(name)
        sub.add_argument("directory", type=Path)
        if name == "serve":
            sub.add_argument("seat")
    args = parser.parse_args()
    if args.command == "prepare":
        seed = secrets.randbits(63) if args.seed is None else args.seed
        prepare(args.project, args.directory, seed)
    elif args.command == "opening":
        if args.health <= 0:
            parser.error("--health must be positive")
        with closing(connect(args.directory)) as db:
            rosters = []
            for seat in SEATS:
                row = db.execute(
                    "SELECT hero, deck FROM players WHERE seat=?", (seat,)
                ).fetchone()
                if row["deck"] is None:
                    parser.error(f"Player {seat} has not submitted a deck.")
                rosters.append({"hero": row["hero"], "cards": json.loads(row["deck"])})
        print(
            json.dumps(
                {
                    "players": rosters,
                    "health": args.health,
                    "landscapes": args.landscapes,
                }
            )
        )
    elif args.command == "start":
        start(args.directory)
    else:
        serve(args.directory, args.seat)


if __name__ == "__main__":
    main()
