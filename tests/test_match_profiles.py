"""Exercise the organizer boundary without starting Unity or an assistant."""

import json
import sys
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from cardwars.arena import runner
from cardwars.players.identity import public_profile
from cardwars.tournament.board import render


class MatchProfileTests(unittest.TestCase):
    def test_spectator_sees_draft_and_player_profiles_before_clients(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "match"
            seen = []
            players = {
                seat: {
                    "kind": "harness",
                    "harness": "custom",
                    "model": "same-model",
                    "rating_id": f"model-{effort}",
                    "effort": effort,
                    "trace_format": "arena",
                }
                for seat, effort in (("left", "high"), ("right", "low"))
            }
            config = SimpleNamespace(
                project=Path(tmp),
                executable=Path(sys.executable),
                health=100,
                watch=True,
                record=False,
                match_players=tuple(players),
                players=players,
                ruleset="test",
                pool_mode="no_obsidian",
                placement="before_cards",
            )

            @contextmanager
            def observer(directory, *, open_browser):
                self.assertTrue(open_browser)
                with runner.closing(runner.arena.connect(directory)) as db:
                    seen.extend(
                        r[0] for r in db.execute("SELECT type FROM trace ORDER BY seq")
                    )
                yield

            @contextmanager
            def participant(cmd, log, *, events_path, cwd):
                self.assertEqual(log.name, cwd.name + ".log")
                self.assertEqual(events_path.name, cwd.name + ".events.jsonl")
                self.assertTrue((cwd / "rules.md").is_file())
                self.assertFalse((cwd / "notes.md").exists())
                seen.append(cwd.name)
                yield None

            with (
                patch.object(runner.subprocess, "run"),
                patch.object(
                    runner.arena, "make_catalog", return_value=("catalog", [], [], {})
                ),
                patch.object(runner, "launch_command", return_value=["test"]),
                patch("cardwars.reports.live.live_view", observer),
                patch.object(runner, "process", participant),
                patch.object(
                    runner, "draft", side_effect=RuntimeError("fixture ends at draft")
                ),
                self.assertRaisesRegex(RuntimeError, "fixture ends at draft"),
            ):
                runner._run_locked(config, path, None, 123, False)

            self.assertEqual(seen, ["match_start", "draft_start", "left", "right"])
            meta = json.loads((path / "results.json").read_text())
            self.assertFalse(meta["complete"])
            self.assertEqual(
                meta["display_names"]["right"], "same-model · low · custom"
            )
            self.assertEqual(
                meta["player_profiles"]["left"], public_profile(players["left"])
            )
            self.assertNotIn("command", meta["player_profiles"]["left"])

    def test_stream_is_independent_of_diagnostics(self):
        with tempfile.TemporaryDirectory() as tmp:
            events = Path(tmp) / "events.jsonl"
            log = Path(tmp) / "diagnostics"
            command = [
                sys.executable,
                "-c",
                "import sys; print(1); print(2, file=sys.stderr)",
            ]
            with runner.process(command, log, events_path=events) as child:
                self.assertEqual(child.wait(timeout=5), 0)
            self.assertEqual((events.read_text(), log.read_text()), ("1\n", "2\n"))

    def test_leaderboard_shows_profile_even_before_first_game(self):
        html = render(
            [],
            Path("leaderboard.html"),
            1,
            "rules",
            0,
            {"r1": "harness", "r2": "harness"},
            profiles={
                "r1": {"display_name": "Один", "model": "Luna", "effort": "high"},
                "r2": {"display_name": "Два", "model": "Luna", "effort": "low"},
            },
        )
        self.assertIn("Luna · high", html)
        self.assertIn("Luna · low", html)
