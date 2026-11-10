"""A private table must authorize the human seat even when a client asks for Terra."""

import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import Mock

from cardwars.arena import matchplay
from cardwars.human.table import Table, roster


class HumanTableTest(unittest.TestCase):
    def test_roster_validation_and_rejection_before_start(self):
        items = {"hero": {"type": "Hero"}, **{str(i): {"type": "Spell"} for i in range(20)}}
        cards = [str(i) for i in range(20)]
        self.assertEqual(roster(dict(hero_id="hero", card_ids=cards), items)["card_ids"], cards)
        for invalid in [cards[1:], cards[:-1] + ["hero"], cards[:-1] + ["0"]]:
            with self.assertRaises(ValueError):
                roster(dict(hero_id="hero", card_ids=invalid), items)
        with tempfile.TemporaryDirectory() as tmp:
            t = Table(None, "terra", Path(tmp), {"items": items}, {})
            self.assertEqual(t.state(0), {"phase": "lobby"})
            with self.assertRaisesRegex(ValueError, "Start the match"):
                t.post("act", {"action_id": "1/0/end"})

    def test_observation_and_actions_are_bound_to_the_human_seat(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)
            with closing(sqlite3.connect(path / "match.sqlite")) as db, db:
                db.row_factory = sqlite3.Row
                db.execute("CREATE TABLE players(seat TEXT, catalog_seen INT, hero TEXT, deck TEXT, layout TEXT, tiles TEXT)")
                db.executemany("INSERT INTO players VALUES (?,1,NULL,NULL,NULL,NULL)", [("human",), ("terra",)])
                db.execute("CREATE TABLE match(catalog TEXT, deadline REAL)")
                db.execute("INSERT INTO match VALUES('catalog',NULL)")
                matchplay.create(db, ["human","terra"], [],100)
                def publish(revision, active):
                    matchplay.publish(db, dict(revision=revision, active=active, turn=revision+1,
                        winner=-1, hp=[100,100], hands=[["own-card"],["secret-card"]], board=[],
                        actions=[dict(id="end",label="End")]))
                publish(0,1)
                db.commit()
                t = Table(None, "terra", path, {"items": {}}, {})
                t.child = Mock(exitcode=None)
                t.errors = Mock()
                t.errors.poll.return_value = False
                state = t.state(0)
                self.assertEqual(state["hand"], ["own-card"])
                self.assertNotIn("secret-card", json.dumps(state))
                self.assertEqual(state["actions"], [])
                with self.assertRaisesRegex(ValueError,"other player"):
                    t.post("act", {"action_id":"1/0/end", "seat":"terra"})
                matchplay.accept_action(db,"terra","1/0/end")
                publish(1,0)
                db.commit()
                with self.assertRaisesRegex(ValueError,"unavailable"):
                    t.post("act", {"action_id":"1/0/end"})
                self.assertTrue(t.post("act", {"action_id":t.state(0)["actions"][0]["id"]})["accepted"])
