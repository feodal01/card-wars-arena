import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from cardwars.tournament import run, run_lock
from cardwars.tournament.board import render
from cardwars.tournament.evidence import Match, read_match
from cardwars.tournament.rating import standings, win_rate_interval
from cardwars.tournament.schedule import fixtures, load_plan

ROOT = Path(__file__).resolve().parents[1]
HISTORY = ROOT / "results/2026-11-05-landscape-turns"


def demo_config(directory, second_policy="play-first"):
    """Match the two-seat, 25 HP native replay used by recorded_demo."""
    (directory / "match.toml").write_text(
        '[engine]\nproject = "."\n'
        '[match]\nplayers = ["random-a", "random-b"]\nhealth = 25\n'
        'pool = "sample40"\nplacement = "own_turn"\n'
        '[players.random-a]\nkind = "random"\npolicy = "uniform"\n'
        f'[players.random-b]\nkind = "random"\npolicy = "{second_policy}"\nrating_id = "second-policy"\n'
    )
    league = directory / "league.toml"
    league.write_text(
        '[tournament]\nmatch_config = "match.toml"\nentrants = ["random-a", "random-b"]\nseed = 2601106\n'
    )
    return league


def example(seed=1):
    return Match(
        "m1",
        "rules",
        ("A", "B"),
        ("a", "b"),
        ("random", "command"),
        (5, 0),
        seed,
        "hash",
        "pool",
        Path("fixtures/one"),
    )


def recorded_demo(directory, fixture, plan):
    """A native historical trace with test entrant IDs; no engine launch in unit tests."""
    directory.mkdir(parents=True, exist_ok=True)
    seats = fixture["players"]
    translated = (HISTORY / "trace.jsonl").read_text().replace("random-a", "__seat1__")
    translated = translated.replace("random-b", seats[1]).replace("__seat1__", seats[0])
    events = [json.loads(line) for line in translated.splitlines()]
    meta = events[0]["data"]
    ids = {s: plan["participants"][s]["rating_id"] for s in seats}
    meta.update(
        seed=fixture["seed"],
        ruleset=plan["ruleset"],
        match_id=fixture["id"],
        identities=ids,
        player_kinds={s: "random" for s in seats},
    )
    (directory / "trace.jsonl").write_text(
        "".join(json.dumps(e) + "\n" for e in events)
    )
    source = (HISTORY / "results.json").read_text().replace("random-a", "__seat1__")
    result = json.loads(
        source.replace("random-b", seats[1]).replace("__seat1__", seats[0])
    )
    result.update(
        players=seats,
        seed=fixture["seed"],
        ruleset=plan["ruleset"],
        identities=ids,
        match_id=fixture["id"],
        complete=True,
    )
    (directory / "results.json").write_text(json.dumps(result))


class TournamentTests(unittest.TestCase):
    def test_round_robin(self):
        schedule = fixtures(["c", "a", "b"], 3, 123456)
        self.assertEqual(fixtures(["b", "c", "a"], 3, 123456), schedule)
        self.assertEqual(9, len(schedule))
        self.assertEqual(9, len({f["seed"] for f in schedule}))
        for repeat in range(1, 4):
            self.assertEqual(
                3, len({tuple(sorted(f["players"])) for f in schedule if f["repeat"] == repeat})
            )

    def test_rating_updates_after_each_match(self):
        one = example()
        two = replace(
            one,
            match_id="m2",
            seed=2,
            trace_hash="other",
            rating_ids=one.rating_ids[::-1],
            kinds=one.kinds[::-1],
            players=one.players[::-1],
            wins=(3, 2),
        )
        partial = standings([one])["rules"]
        self.assertEqual(1516, partial["a"].rating)
        table = standings([one, two, one])["rules"]
        self.assertAlmostEqual(1498.53, table["a"].rating, places=2)
        self.assertEqual(2, table["a"].matches)
        self.assertEqual(1, table["a"].wins)
        self.assertEqual((0, 1), win_rate_interval(1, 2))
        sweep = standings([one, replace(two, wins=(0, 5))])["rules"]
        self.assertAlmostEqual(1530.53, sweep["a"].rating, places=2)
        with self.assertRaisesRegex(ValueError, "Repeated fixture"):
            standings([one, replace(two, seed=one.seed)])
        with self.assertRaisesRegex(ValueError, "Conflicting traces"):
            standings([one, replace(one, trace_hash="tampered")])
        with self.assertRaisesRegex(ValueError, "Repeated fixture"):
            standings([one, replace(one, match_id="duplicate")])

    def test_historical_self_play_and_rulesets(self):
        historic = [
            read_match(path.parent)
            for path in sorted((ROOT / "results").glob("2026-11-05-*/trace.jsonl"))
        ]
        self.assertEqual(2, len(historic))
        tables = standings(historic)
        self.assertEqual(2, len(tables))
        self.assertTrue(all(not rows for rows in tables.values()))
        html = render(historic, ROOT / "results/leaderboard.html", 0, "demo", 0)
        self.assertIn("2026-11-05-landscape-turns/trace.jsonl", html)
        self.assertIn("2026-11-05-random-match/trace.jsonl", html)

    def test_aliases_cannot_manufacture_new_policies(self):
        with tempfile.TemporaryDirectory() as tmp:
            league = demo_config(Path(tmp), second_policy="uniform")
            with self.assertRaisesRegex(ValueError, "Duplicate built-in random policy"):
                load_plan(league)

    def test_resume_and_validate_each_trial(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            match_path, plan = load_plan(demo_config(directory))
            launched = []

            def fake(command, check):
                self.assertTrue(check)
                destination = Path(command[command.index("--output") + 1])
                players = command.index("--players") + 1
                job = next(f for f in plan["fixtures"] if f["id"] == destination.name)
                self.assertEqual(job["players"], command[players : players + 2])
                self.assertEqual(str(job["seed"]), command[command.index("--seed") + 1])
                launched.append(job["id"])
                recorded_demo(destination, job, plan)

            run(directory, plan, match_path, limit=1, launch=fake)
            self.assertEqual(["match-0001"], launched)
            run(directory, plan, match_path, launch=fake)
            before = (directory / "leaderboard.html").read_bytes()
            run(directory, plan, match_path, launch=fake)
            self.assertEqual(before, (directory / "leaderboard.html").read_bytes())
            self.assertEqual(["match-0001"], launched)
            path = directory / "matches/match-0001/results.json"
            summary = json.loads(path.read_text())
            summary["games"][0]["hp"] = [1, 1]
            path.write_text(json.dumps(summary))
            with self.assertRaisesRegex(ValueError, "reported game differs"):
                run(directory, plan, match_path, launch=fake)
            with self.assertRaisesRegex(ValueError, "configuration has changed"):
                run(directory, dict(plan, seed=2027), match_path, launch=fake)
            with (
                run_lock(directory),
                self.assertRaisesRegex(ValueError, "Another tournament"),
            ):
                run(directory, plan, match_path, launch=fake)
