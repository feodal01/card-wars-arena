"""Command-line entry point for a local Card Wars arena installation."""

import argparse
import json
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path

from cardwars.config import load_config


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv[:1] == ["tournament"]:
        from cardwars.tournament import main as tournament_main

        return tournament_main(argv[1:])
    parser = argparse.ArgumentParser(
        prog="cardwars", description="Local Card Wars arena"
    )
    subs = parser.add_subparsers(required=True, dest="command")
    setup = subs.add_parser("prepare-engine", help="Copy a recovered Unity project and install the arena bridge")
    setup.add_argument("source", type=Path)
    setup.add_argument("destination", type=Path)
    m = subs.add_parser(
        "match", help="Play one five-game match from a TOML configuration"
    )
    m.add_argument("config", type=Path)
    m.add_argument(
        "--output", type=Path, help="New run directory (default: runs/matches/...)"
    )
    m.add_argument("--players", nargs=2, metavar=("A", "B"))
    m.add_argument("--seed", type=int)
    m.add_argument("--resume", action="store_true")
    subs.add_parser("tournament", help="Match schedule and static ratings board")
    tools = subs.add_parser("tools", help="Connect and check seat MCP tools")
    modes = tools.add_subparsers(required=True, dest="tools_command")
    serve = modes.add_parser(
        "serve", help="Trusted single-seat MCP server over stdio"
    )
    serve.add_argument("directory", type=Path)
    serve.add_argument("seat")
    check = modes.add_parser(
        "check", help="Check CLI connectivity without calling a model"
    )
    check.add_argument("kind", choices=("codex", "claude", "opencode", "prime"))
    check.add_argument("--project", required=True, type=Path)
    catalog = subs.add_parser("catalog", help="Build the English catalog that players receive")
    catalog.add_argument("--project", required=True, type=Path, help="Recovered arena Unity project")
    catalog.add_argument("--output", type=Path, help="Markdown destination (default: stdout)")
    catalog.add_argument("--pool", choices=("sample40", "full", "no_obsidian"), default="no_obsidian")
    catalog.add_argument("--seed", type=int, default=0, help="Seed for sample40")
    catalog.add_argument("--check-sources", action="store_true", help="Check reviewed Unity effect sources for changes")
    duel = subs.add_parser("duel", help="Open the private human table and offline deck workshop")
    duel.add_argument("config", type=Path)
    duel.add_argument("--opponent", default="terra")
    duel.add_argument("--output", type=Path)
    duel.add_argument("--workshop", type=Path, default=Path("build/deck-workshop.html"))
    t = subs.add_parser("trace", help="Build an offline HTML trace viewer")
    t.add_argument("trace", type=Path)
    t.add_argument("--output", required=True, type=Path)
    a = subs.add_parser("verify", help="Verify match events and score")
    a.add_argument("trace", type=Path)
    v = subs.add_parser("video", help="Create an MP4 from recorded game frames")
    v.add_argument("directory", type=Path)
    v.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "prepare-engine":
            from cardwars.engine.prepare import prepare_project

            checked = prepare_project(args.source, args.destination)
            print(f"Prepared {args.destination.resolve()} and verified {checked} effect sources.")
        elif args.command == "match":
            from cardwars.arena.runner import run

            if args.resume and args.output is None:
                raise ValueError("Specify the existing --output directory to resume")
            output = args.output or Path("runs/matches") / (
                datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
                + "-"
                + uuid.uuid4().hex[:8]
            )
            print(f"Match: {output.resolve()}", flush=True)
            run(load_config(args.config), output, args.players, args.seed, args.resume)
        elif args.command == "duel":
            from cardwars.human.table import serve_table

            output = args.output or Path("runs/matches") / ("human-" + uuid.uuid4().hex[:12])
            serve_table(load_config(args.config), args.opponent, output, args.workshop)
        elif args.command == "catalog":
            from cardwars.arena.catalog import make_catalog
            from cardwars.arena.catalog_audit import check_sources

            if args.check_sources:
                count = check_sources(args.project)
                print(f"Verified {count} Unity source files.", file=sys.stderr)
            markdown, *_ = make_catalog(args.project, args.seed, args.pool)
            if args.output:
                args.output.parent.mkdir(parents=True, exist_ok=True)
                args.output.write_text(markdown, encoding="utf-8")
            else:
                sys.stdout.write(markdown)
        elif args.command == "tools":
            if args.tools_command == "serve":
                from cardwars.tools.mcp_server import serve

                serve(args.directory.resolve(), args.seat)
            else:
                from cardwars.players.smoke import check_player

                check_player(args.kind, args.project)
        elif args.command == "trace":
            from cardwars.reports.trace import render_trace

            render_trace(args.trace, args.output)
        elif args.command == "verify":
            from cardwars.reports.verify import verify

            with args.trace.open(encoding="utf-8") as file:
                print(json.dumps(verify(file), ensure_ascii=False, indent=2))
        elif args.command == "video":
            from cardwars.reports.video import render

            render(args.directory.resolve(), args.output.resolve())
    except (ValueError, OSError, RuntimeError) as exc:
        parser.exit(1, f"cardwars: {exc}\n")


if __name__ == "__main__":
    sys.exit(main())
