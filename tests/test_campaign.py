"""The mirror and the recorded Unity policy are both part of the match contract."""

import json
import unittest
from pathlib import Path

from cardwars.reports.verify import verify


class CampaignEvidenceTest(unittest.TestCase):
    def setUp(self):
        archive = Path(__file__).resolve().parents[1] / "results/2026-11-09-terra-campaign-mirror/trace.jsonl"
        self.rows = [json.loads(line) for line in archive.read_text().splitlines()]

    def test_different_legal_hero_is_not_a_mirror(self):
        roster = next(row["data"] for row in self.rows
                      if row["type"] == "submit_deck" and row["data"]["seat"] == "campaign")
        hero = next(hero for hero in self.rows[0]["data"]["heroes"] if hero != roster["hero"])
        roster["hero"] = hero
        next(row["data"] for row in self.rows if row["type"] == "opening")["players"][1]["hero"] = hero
        with self.assertRaisesRegex(ValueError, "mirror differs"):
            verify(map(json.dumps, self.rows))

    def test_valid_action_must_match_campaign_decision(self):
        state = next(row["data"] for row in self.rows if row["type"] == "unity_state"
                     and row["data"]["turn"] > 0 and "campaign_action" in row["data"]
                     and len(row["data"]["actions"]) > 1)
        state["campaign_action"] = next(a["id"] for a in state["actions"] if a["id"] != state["campaign_action"])
        with self.assertRaisesRegex(ValueError, "differs from Unity's campaign decision"):
            verify(map(json.dumps, self.rows))
