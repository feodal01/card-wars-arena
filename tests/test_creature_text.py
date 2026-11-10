import unittest

from cardwars.arena.creature_text import creature_description


def effect(script, val1="", val2="", original="Native English text.", **parameters):
    row = {"ScriptName": script, "val1": val1, "val2": val2}
    return creature_description(row, original, parameters)


class CreatureTextTests(unittest.TestCase):
    def test_white_ninja_heals_itself_using_second_value(self):
        for damage, healing in (("3", "2"), ("20", "28")):
            with self.subTest(damage=damage):
                text = effect("DamageOpponentHealSelf", damage, healing)
                self.assertIn(f"{damage} damage to the opposing creature", text)
                self.assertIn(f"Heal this creature for {healing} HP", text)

    def test_sacrifice_and_heal_targets(self):
        for script in ("ATKPenaltySacrifice", "DamageAndDiscard"):
            with self.subTest(script=script):
                text = effect(script, "3")
                self.assertIn("opposing creature", text)
                self.assertIn("Send the creature that flooped to your discard pile", text)
        wall = effect("DamageOneHealAll", "5", "2")
        self.assertIn("your other creatures for 5 HP", wall)
        self.assertIn("Deal 2 damage to this creature", wall)
        nice_bird = effect("HealAdjacentHPAndDiscard", "20")
        self.assertIn("this creature's current defense", nice_bird)
        self.assertNotIn("20", nice_bird)
        self.assertIn("random wounded creature on your side", effect("HealRandom", "12"))

    def test_pig_and_pirate_targets(self):
        pig = effect("ATKPenaltyFaction", "0", "1", Faction="Corn")
        self.assertIn("all opposing Corn creatures by 1", pig)
        pirate = effect("DamageOpponentAndHero", "5")
        self.assertIn("5 damage to the opposing hero", pirate)
        self.assertIn("If there is a creature opposite", pirate)

    def test_wheel_and_delayed_mana_are_independent_of_caster(self):
        for script, stat in (("IncreaseCritArea", "critical-hit"),
                             ("IncreaseDefenseArea", "block"),
                             ("IncreaseDefenseCritArea", "counterattack")):
            with self.subTest(script=script):
                self.assertIn(f"seat A's {stat} zone", effect(script, "150"))
        rose = effect("ReturnHandsDrawCardsAddMP", "5", "2", name="Bad Rose")
        self.assertIn("your hand into your deck and draw up to 5 cards", rose)
        self.assertIn("their own copy of Bad Rose in play gains 2 mana", rose)
        self.assertIn("Neither player", rose)

    def test_opponent_full_hand_and_obsidian_cost(self):
        self.assertIn("opponent's discard pile", effect("ReturnTargetToHand", "1", card_type="building"))
        self.assertEqual(effect("IncreaseFloopCost", "1"), "Your floops cost 1 more mana until the end of this turn.")
        self.assertIn("each of your earlier paid floops", effect("DamageOpponentFloop", "5"))

    def test_discard_damage_requires_a_full_group(self):
        for group in ("1", "2"):
            self.assertIn(f"each complete group of {group}", effect("DamageOpponentDiscardPile", "4", group))

    def test_preserves_accurate_localization(self):
        self.assertEqual(effect("ATKDEFBonus", "2", "3", "Gain +2 attack and +3 defense."),
                         "Gain +2 attack and +3 defense.")
