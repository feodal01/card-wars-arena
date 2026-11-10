"""Schedule and score five-game matches."""

import argparse
import contextlib
import fcntl
import json
import os
import subprocess
import sys
import tempfile
import tomllib
from pathlib import Path

from cardwars.config import load_config

from .evidence import read_match
from .schedule import load_plan, player_fingerprint


def write_atomic(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=path.parent, delete=False
    ) as file:
        temporary = Path(file.name)
        try:
            file.write(content)
            file.flush()
            os.fsync(file.fileno())
            file.close()
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)


@contextlib.contextmanager
def run_lock(directory):
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / ".tournament.lock").open("a") as lock:
        try:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise ValueError(f"Another tournament process holds {directory}") from exc
        try:
            yield
        finally:
            fcntl.flock(lock.fileno(), fcntl.LOCK_UN)


def freeze(directory, plan):
    path = directory / "schedule.json"
    if path.exists():
        if json.loads(path.read_text(encoding="utf-8")) != plan:
            raise ValueError(
                "Schedule or entrant configuration has changed. Choose a new output directory."
            )
    elif (directory / "matches").exists():
        raise ValueError(
            "Cannot adopt an existing matches directory without its schedule"
        )
    else:
        write_atomic(path, json.dumps(plan, indent=2, ensure_ascii=False) + "\n")


def fixture_path(directory, fixture):
    return directory / "matches" / fixture["id"]


def completed(path):
    summary = path / "results.json"
    return (
        summary.exists()
        and json.loads(summary.read_text(encoding="utf-8")).get("complete") is True
    )


def verified_fixtures(directory, plan):
    records = {}
    for fixture in plan["fixtures"]:
        path = fixture_path(directory, fixture)
        if completed(path):
            records[fixture["id"]] = read_match(path, fixture, plan)
    return records


def publish(directory, plan, checked, html=None, include=(), method="elo"):
    from cardwars.players.identity import public_profile

    from .board import render

    records = [checked[f["id"]] for f in plan["fixtures"] if f["id"] in checked]
    for path in include:
        records.append(read_match(path))
    target = html or directory / "leaderboard.html"
    write_atomic(
        target,
        render(records, target, len(plan["fixtures"]), plan["ruleset"], len(checked),
               {p["rating_id"]: p["kind"] for p in plan["participants"].values()}
               if method == "bradley-terry" else None,
               profiles={p["rating_id"]: public_profile(p)
                       for p in plan["participants"].values()}),
    )
    return records


def run(directory, plan, match_config, limit=None, launch=subprocess.run, method="elo"):
    with run_lock(directory):
        freeze(directory, plan)
        checked = verified_fixtures(directory, plan)
        remaining = limit
        for fixture in plan["fixtures"]:
            path = fixture_path(directory, fixture)
            if fixture["id"] in checked:
                continue
            if remaining == 0:
                break
            # A long tournament reads the config again in each child. Detect
            # edits between matches before spending another match's budget.
            live = load_config(match_config, resolve_engine=False)
            if live.ruleset != plan["ruleset"] or any(
                player_fingerprint(live.players[seat])
                != plan["participants"][seat]["definition"]
                for seat in fixture["players"]
            ):
                raise ValueError(
                    "Match rules or player definition changed during tournament"
                )
            command = [
                sys.executable,
                "-m",
                "cardwars",
                "match",
                str(match_config),
                "--output",
                str(path),
                "--players",
                *fixture["players"],
                "--seed",
                str(fixture["seed"]),
            ]
            path.parent.mkdir(exist_ok=True)
            if path.exists():
                if not (path / "match.sqlite").is_file():
                    raise ValueError(
                        f"Incomplete directory {path}; inspect it before retrying"
                    )
                command.append("--resume")
            print(
                f"{fixture['id']}: {' vs '.join(fixture['players'])} (seed {fixture['seed']})",
                flush=True,
            )
            launch(command, check=True)
            checked[fixture["id"]] = read_match(path, fixture, plan)
            publish(directory, plan, checked, method=method)
            if remaining is not None:
                remaining -= 1
        return publish(directory, plan, checked, method=method)


def main(argv=None):
    parser = argparse.ArgumentParser(prog="cardwars tournament")
    sub = parser.add_subparsers(dest="action", required=True)
    for name in ("plan", "run", "board"):
        cmd = sub.add_parser(name)
        cmd.add_argument("config", type=Path)
        cmd.add_argument(
            "--output",
            type=Path,
            required=name != "plan",
            help="Tournament directory containing the schedule and match folders",
        )
        if name == "run":
            cmd.add_argument("--dry-run", action="store_true")
            cmd.add_argument(
                "--limit",
                type=int,
                help="Maximum number of new completed matches in this invocation",
            )
        if name == "board":
            cmd.add_argument(
                "--html", type=Path, help="Override the leaderboard.html destination"
            )
            cmd.add_argument(
                "--include",
                action="append",
                type=Path,
                default=[],
                help="Also include this verified match directory; repeat for more evidence",
            )
    args = parser.parse_args(argv)
    try:
        match_path, plan = load_plan(args.config)
        with args.config.open("rb") as file:
            method = tomllib.load(file).get("report", {}).get("method", "elo")
        if method not in ("elo", "bradley-terry"):
            raise ValueError(f"Unknown rating method: {method}")
        if args.action == "plan" or getattr(args, "dry_run", False):
            print(json.dumps(plan, indent=2, ensure_ascii=False))
        elif args.action == "run":
            if args.limit is not None and args.limit < 0:
                raise ValueError("--limit must be nonnegative")
            run(args.output, plan, match_path, args.limit, method=method)
        else:
            if (
                json.loads((args.output / "schedule.json").read_text(encoding="utf-8"))
                != plan
            ):
                raise ValueError("Stored schedule differs from requested configuration")
            checked = verified_fixtures(args.output, plan)
            publish(args.output, plan, checked, args.html, args.include, method)
    except (
        OSError,
        ValueError,
        KeyError,
        TypeError,
        subprocess.CalledProcessError,
    ) as exc:
        parser.exit(1, f"Tournament failed: {exc}\n")
