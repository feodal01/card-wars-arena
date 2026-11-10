import unittest

from cardwars.arena.spell_building_text import spell_building_description


def effect(script, val1="", val2="", **parameters):
    row = {"ScriptName": script, "val1": val1, "val2": val2}
    return spell_building_description(row, "Native English text.", parameters)


class SpellBuildingTextTests(unittest.TestCase):
    def test_rarity_gate_applies_to_both_permanents_in_the_opposing_lane(self):
        self.assertEqual(effect("RarityGate", "3"),
                         "Your opponent can play only creatures and buildings of rarity 3 or lower "
                         "in the lane opposite this building.")

    def test_landscape_count_has_different_scope_for_spell_and_building(self):
        self.assertIn("on both sides", effect("ActionPointLandscapes"))
        building = effect("ATKBonusLandscapes", "2")
        self.assertIn("subtract 2 attack", building)
        self.assertIn("+2 attack for each distinct landscape type on your side", building)

    def test_removal_and_damage_use_distinct_mechanics(self):
        for script, qualifier in [
            ("DestroyLowerRarity", "3 or lower"),
            ("DestroyHigherRarity", "3 or higher"),
            ("KillLoneOpponent", "exactly one"),
        ]:
            with self.subTest(script=script):
                text = effect(script, "3")
                self.assertIn(qualifier, text)
                self.assertIn("remaining HP", text)
                self.assertIn("damage", text)
        self.assertIn("directly to their owners' discard piles", effect("DestroyBuildingLane"))
        self.assertIn("reduce that damage by 5", effect("DamageReduction", "5"))

    def test_random_creature_stays_in_deck_and_return_spell_can_recover_itself(self):
        self.assertIn("also stays in the deck", effect("RandomCard", card_type="creature"))
        self.assertIn("spell you just cast", effect("ReturnCard", "2", card_type="spell"))
        self.assertEqual(effect("ReturnCard", "1", card_type="building"),
                         "Choose a building card in your discard pile and return it to your hand.")

    def test_distinct_empty_slot_and_capacity_requirements(self):
        self.assertIn("another opposing lane without a building", effect("MoveBuildingOpponent"))
        self.assertIn("lane without a creature", effect("EmptyLaneCards"))
        self.assertIn("fewer than 7 cards in hand", effect("DrawCardsSpell", "2", hand_gate=7))
        self.assertIn("7 or more cards", effect("ReturnOpponentCreature", hand_gate=7))
        self.assertIn("remaining creatures to your discard", effect("ReturnCreatures", hand_gate=7))
        self.assertIn("even if your hand is full", effect("ReturnToHandSacrifice"))

    def test_cave_removal_counts_creatures_not_empty_lanes(self):
        text = effect("ATKDEFBonusEmptyLanes", "4", "6")
        self.assertIn("+4 attack and +6 defense for every friendly lane without a creature", text)
        self.assertIn("subtract 4 attack and 6 defense for each of your creatures in play", text)

    def test_target_and_damage_source_of_faction_attacks(self):
        self.assertIn("a friendly Corn creature", effect("AttackCreatureCorn", "0", Faction="Corn"))
        self.assertIn("Your creature deals", effect("AttackCreatureSwamp", "2", Faction="Swamp"))
        self.assertIn("The spell deals", effect("AttackCreatureSand", "4", Faction="Sand"))

    def test_drain_uses_first_parameter_for_both_health_changes(self):
        self.assertEqual(effect("DrainOpponentHealth", "5", "9"),
                         "Heal your hero for 5 HP and deal 5 damage to the opposing hero.")

    def test_sacrifice_selects_a_permanent_and_draws_by_second_parameter(self):
        for kind, count, reward in (("creature", "1", "1 card."), ("building", "12", "12 cards.")):
            with self.subTest(kind=kind):
                text = effect("DestroyEntityForCards", "0", count, card_type=kind)
                self.assertIn(f"one of your {kind} cards", text)
                self.assertIn(f"draw {reward}", text)
        self.assertIn("Draw 3 cards", effect("DrawCardsSpell", "3", hand_gate=7))

    def test_preserve_localized_text_of_unchanged_scripts(self):
        self.assertEqual(effect("DEFBonusBuilding", "4"), "Native English text.")
