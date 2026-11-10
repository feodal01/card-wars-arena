import math
import os
import unittest
from collections import Counter
from pathlib import Path
from types import SimpleNamespace

from cardwars.arena.catalog import make_catalog
from cardwars.players.random import parse_catalog
from cardwars.tournament.bradley_terry import estimate
from cardwars.tournament.schedule import load_plan


class LeagueTests(unittest.TestCase):
    def test_full_schedule_and_baseline(self):
        config = Path(__file__).resolve().parents[1] / "configs/league100.toml"
        _, plan = load_plan(config)
        self.assertEqual(plan["ruleset"], "cardwars-v3-en-noobs258-20-bo5-landfirst-hp100")
        counts = Counter(tuple(sorted(f["players"])) for f in plan["fixtures"])
        self.assertEqual(counts, {("astra", "claude"): 20, ("astra", "random"): 20, ("claude", "random"): 20})

    @unittest.skipUnless(os.environ.get("CARDWARS_UNITY_PROJECT"), "requires the card blueprints")
    def test_catalog_and_random_player(self):
        text, cards, heroes, _ = make_catalog(Path(os.environ["CARDWARS_UNITY_PROJECT"]), 1, "no_obsidian")
        self.assertEqual(parse_catalog(text), (cards, heroes))
        self.assertEqual((len(set(cards)), len(set(heroes))), (258, 72))
        self.assertFalse(any(c.startswith("Creature_BL_") for c in cards))
        self.assertIn("Creature_VampCorn", cards)
        self.assertIn("Creature_DrDeath", cards)
        self.assertNotIn("Creature_GL_DrDeath", cards)

    def test_joint_fit_and_separated_results(self):
        win = SimpleNamespace(rating_ids=("a", "b"), wins=(3, 2))
        lose = SimpleNamespace(rating_ids=("a", "b"), wins=(0, 5))
        self.assertEqual(estimate([win], ["a", "b"]), ({}, {}))
        self.assertEqual(estimate([win, lose], ["a", "b", "c"]), ({}, {}))
        sample = [win] * 30 + [lose] * 10
        ratings, intervals = estimate(sample, ["a", "b"])
        self.assertAlmostEqual(ratings["a"] - ratings["b"], 400 * math.log10(3))
        self.assertLess(intervals["a"][0], ratings["a"])
        self.assertGreater(intervals["a"][1], ratings["a"])
        self.assertEqual((ratings, intervals), estimate(sample[::-1], ["b", "a"]))
