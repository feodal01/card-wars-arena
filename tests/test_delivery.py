import copy
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cardwars.config import load_config
from cardwars.reports.verify import verify

ROOT = Path(__file__).resolve().parents[1]


class ConfigTests(unittest.TestCase):
    def test_config_is_relative_and_detached_schedule_requires_no_engine(self):
        with patch.dict(os.environ, {"CARDWARS_UNITY_PROJECT": str(ROOT)}):
            config = load_config(ROOT / "configs/arena100.toml")
        self.assertEqual(config.project, ROOT)
        self.assertEqual(config.match_players, ("astra", "claude"))
        ids = [p["rating_id"] for p in config.players.values()]
        self.assertEqual(len(ids), len(set(ids)))
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(
                load_config(ROOT / "configs/arena100.toml", resolve_engine=False).health,
                100,
            )
            with self.assertRaisesRegex(ValueError, "CARDWARS_UNITY_PROJECT"):
                load_config(ROOT / "configs/arena100.toml")

    def test_invalid_configuration_is_reported_before_start(self):
        original = (ROOT / "configs/arena100.toml").read_text()
        for old, new in [
            ("games = 5", "games = 3"),
            ('players = ["astra", "claude"]', 'players = ["astra", "astra"]'),
            ("health = 100", "health = false"),
            ("watch = true", "watc = true"),
        ]:
            with self.subTest(new=new), tempfile.TemporaryDirectory() as folder:
                config = Path(folder) / "match.toml"
                config.write_text(original.replace(old, new))
                with self.assertRaises(ValueError):
                    load_config(config, resolve_engine=False)


class TechnicalResultTests(unittest.TestCase):
    def timeout_match(self, phase):
        old = ROOT / "results/2026-11-05-landscape-turns/trace.jsonl"
        rows = [json.loads(line) for line in old.read_text().splitlines()]
        meta = rows[0]["data"] | {"deck_seconds": 600, "turn_seconds": 300}
        seats = meta["seats"]
        score = dict.fromkeys(seats, 0)
        events = []

        def append(game, stamp, kind, data):
            events.append(
                {
                    "seq": len(events) + 1,
                    "ts": stamp,
                    "type": kind,
                    "game": game,
                    "data": data,
                }
            )

        append(1, 0, "match_start", meta)
        for game in range(1, 6):
            stamp = game * 1000
            window = [r for r in rows if r["game"] == game]
            rosters = [r["data"] for r in window if r["type"] == "submit_deck"]
            append(game, stamp, "draft_start", {"deadline": stamp + 600})
            append(game, stamp + 1, "submit_deck", rosters[0] | {"comment": "План на партию"})
            if phase == "select_deck":
                winner = rosters[0]["seat"]
                loser = next(s for s in seats if s != winner)
                deadline, turn, hp, reason = stamp + 600, 0, [], "deck_timeout"
            else:
                append(game, stamp + 2, "submit_deck", rosters[1])
                opening = next(r["data"] for r in window if r["type"] == "opening")
                append(game, stamp + 3, "opening", opening)
                state = next(r["data"] for r in window if r["type"] == "unity_state")
                deadline = stamp + 4 + 300
                append(
                    game, stamp + 4, "unity_state", state | {"turn_deadline": deadline}
                )
                if state["events"]:
                    append(game, stamp + 4, "public_events", state["events"])
                loser, winner = seats[state["active"]], seats[1 - state["active"]]
                turn, hp, reason = 1, state["hp"], "turn_timeout"
            append(
                game,
                deadline + 1,
                "timeout",
                {
                    "phase": phase,
                    "seat": loser,
                    "deadline": deadline,
                    "observed_at": deadline + 1,
                },
            )
            append(
                game,
                deadline + 1,
                "game_end",
                {"turns": turn, "hp": hp, "winner": winner, "reason": reason},
            )
            score[winner] += 1
        append(5, 6000, "match_end", score)
        return events, score

    def test_timeout_wins_need_verified_clocks(self):
        for phase in ("battle", "select_deck"):
            with self.subTest(phase=phase):
                events, score = self.timeout_match(phase)

                def audit(rows):
                    return verify(io.StringIO("\n".join(json.dumps(r) for r in rows)))

                self.assertEqual(audit(events)["score"], score)
                broken = copy.deepcopy(events)
                expiry = next(e for e in broken if e["type"] == "timeout")
                expiry["data"]["observed_at"] = expiry["data"]["deadline"] - 1
                with self.assertRaisesRegex(ValueError, "expired seat clock"):
                    audit(broken)
