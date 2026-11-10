"""Level-one creature floops whose native English localization omits an engine rule."""

# ScriptName identifies behavior. Values come from the specific edition's Blueprint
# or from the implementation when the script reads a literal or casts an enum.
_EFFECTS = {
    "DEFBonusRandom": "Give a random creature on either side +{v1} defense.",
    "ATKHealBonus": "Give this creature +{v1} attack and heal it for {v2} HP.",
    "ATKBonusAdjacentEmpty": "Gain +{v1} attack for each adjacent friendly lane without a creature. Buildings do not count. Requires at least one such lane.",
    "ATKBonusDamageSelf": "If this creature has more than {v1} HP, deal {v1} damage to it and give it +{v2} attack.",
    "ATKBonusFloopCount": "The first floop gives this creature +{first_bonus} attack. Each successive floop grants one more attack than the last while it stays in play.",
    "ATKBonusForBuilding": "Choose one of your creatures. Give it +{v1} attack for each of your buildings. Requires a friendly building.",
    "ATKPenaltyFaction": "Reduce the attack of all opposing {Faction} creatures by {v2}.",
    "ATKPenaltySacrifice": "Reduce the opposing creature's attack by {v1}. Send the creature that flooped to your discard pile.",
    "BonusATKTarget": "Choose one of your creatures and give it +{v1} attack.",
    "ConvertOpponentAttToHP": "Heal this creature for HP equal to the opposing creature's attack.",
    "DEFPenaltyATKBonusAdjacent": "Give each adjacent friendly creature −{v1} defense and +{v2} attack. At least one of them must have more than {v1} HP.",
    "DEFPenaltyDamageSelf": "Deal {v1} damage to this creature and reduce the opposing creature's defense by {v2}.",
    "DamageAndDiscard": "Deal {v1} damage to the opposing creature. Send the creature that flooped to your discard pile.",
    "DamageAndTakeCard": (
        "Requires room in your hand and an opposing creature in this lane. Deal {v1} damage to it. "
        "If its HP before the hit was at most {v1}, take its card from the opponent's discard pile "
        "into your hand when it dies while facing this creature."
    ),
    "DamageOneHealAll": "Heal each of your other creatures for {v1} HP. Deal {v2} damage to this creature.",
    "DamageOpponentAdjacents": "Deal {v1} damage each to the creature opposite this one and its neighbors. The opposing lane must contain a creature.",
    "DamageOpponentAndHero": "Deal {v1} damage to the opposing hero. If there is a creature opposite this one, also deal {v1} damage to it.",
    "DamageOpponentDEF": "Deal damage to the opposing creature equal to this creature's current defense.",
    "DamageOpponentDamage": "Deal damage to the opposing creature equal to this creature's missing HP.",
    "DamageOpponentDiscardedCreatures": "Deal {v1} damage to the opposing creature for each creature card in the opponent's discard pile. Requires at least one such card.",
    "DamageOpponentDiscardPile": "Deal {v1} damage to the creature opposite this one for each complete group of {group} in your discard pile. Requires at least one complete group.",
    "DamageOpponentHealSelf": "Deal {v1} damage to the opposing creature if present. Heal this creature for {v2} HP. Requires an opposing creature in this lane or a wound on this creature.",
    "DamageOpponentIfDamagedLastTurn": "Deal damage to the opposing creature equal to {v1}% of the last single hit this creature took, rounded down. This amount resets at the start of your battle phase. Requires a recorded hit greater than zero.",
    "DamageOpponentLowerATK": "Deal {v1} damage to the opposing creature and reduce its attack by {v2}.",
    "DamageOpponentRarity": "Deal {v1} damage to the opposing creature for each of its rarity stars.",
    "DamageRandom": "Deal {v1} damage to a random creature on either side. Requires at least one opposing creature in play.",
    "DamageTargetFaction": "Choose an opposing {Faction} creature and deal {v1} damage to it.",
    "DamageTargetHealSelf": "If your opponent has creatures, choose one and deal {v1} damage to it. Heal this creature for {v2} HP. A wounded creature can use this floop even when the opposing field is empty.",
    "DrawCards": "Draw up to {draw}. Requires a card in your deck and room in your hand.",
    "DrawCardsSacrifice": "Draw up to {draw} and send this creature to your discard pile. Requires a card in your deck and room in your hand.",
    "DrawCardsTake": "Requires room in your hand and a card in your deck. Return this creature to your hand, then draw up to {draw} while you have room.",
    "DrainOpponentATKLowerSelfDEF": "Divide the opposing creature's attack by {divisor}, rounding down. Take that much attack from it, or take one if its attack is exactly {special_attack}. Increase this creature's attack and reduce its defense by that amount. Requires a target with positive attack.",
    "EqualizeATK": "Replace the opposing creature's attack modifier so that its attack before multipliers equals this creature's current attack.",
    "FloopAdjacent": "Choose an adjacent friendly creature whose floop effect can resolve, except another creature with this ability. It uses its effect for free, even if it already flooped or its floop is blocked. Its flooped status stays the same.",
    "HealAdjacentDamage": "Heal each adjacent friendly creature for HP equal to this creature's missing HP. Requires a wound on this creature or one of its neighbors.",
    "HealAdjacentHPAndDiscard": "Heal each adjacent friendly creature for HP equal to this creature's current defense. Then send this creature to your discard pile. Requires a wounded neighbor.",
    "HealAllSacrifice": "Fully heal all your other creatures and send this creature to your discard pile. At least one of the other creatures must be wounded.",
    "HealRandom": "Heal a random wounded creature on your side for {v1} HP.",
    "HealTarget": "Choose one of your wounded creatures and heal it for {v1} HP.",
    "HealTargetAdjacent": "Choose one of your creatures. It or one of its neighbors must be wounded. Heal the chosen creature and its neighbors for {v1} HP each.",
    "HealTargetAll": "Choose one of your wounded creatures and fully heal it.",
    "HealTargetBuildings": "Choose one of your wounded creatures and heal it for {v1} HP per friendly building. Requires a friendly building.",
    "HealTargetCards": "Choose one of your wounded creatures and heal it for {v1} HP per card in your hand. Requires at least one card in hand.",
    "HealTargetLandscapes": "Choose one of your wounded creatures and heal it for {v1} HP per distinct landscape type on your side.",
    "HelplessOpponent": "The opposing creature becomes helpless until the start of its owner's next turn. An attack in this lane can hit the opposing hero directly.",
    "IncreaseCritArea": "Increase the size of seat A's critical-hit zone by {v1}% for A's next attack phase. If A goes first and uses this on turn one, the bonus expires when combat is skipped.",
    "IncreaseDefenseArea": "Increase the size of seat A's block zone by {v1}% for B's next attack phase. If B goes first and uses this on turn one, the bonus expires when combat is skipped.",
    "IncreaseDefenseCritArea": "Increase the size of seat A's counterattack zone by {v1}% for B's next attack phase. If B goes first and uses this on turn one, the bonus expires when combat is skipped.",
    "IncreaseFloopCost": "Your floops cost {v1} more mana until the end of this turn.",
    "LandscapeATKBonus": "Gain +{v1} attack for each of your {LandscapeType} landscapes. Requires at least one such landscape.",
    "LowerATKBonusATK": "Reduce the opposing creature's attack by {v1} and give this creature +{v2} attack.",
    "LowerATKByATK": "Reduce the opposing creature's attack by this creature's current attack.",
    "LowerATKOpponentCards": "Reduce the opposing creature's attack by {v1} per card in the opponent's hand.",
    "LowerDEFByATK": "Reduce the opposing creature's defense by this creature's current attack.",
    "Protection": "The opposing creature skips its next attack on its owner's turn. Requires an opposing creature that is still allowed to attack.",
    "ResetSelf": "Fully heal this creature and clear its additive attack and defense modifiers. Stat multipliers remain in effect.",
    "ResetTarget": "Choose a friendly creature with wounds or an additive attack or defense modifier. Fully heal it and clear those modifiers. Stat multipliers remain in effect.",
    "RandomDiscardCard": "Return a random card from your discard pile to your hand. Requires room in hand.",
    "LowerAllATKSacrifice": "Reduce every opposing creature's attack by {v1} and send this creature directly to your discard pile. Requires an opposing creature.",
    "SacrificeForMP": "Send this creature directly to your discard pile and gain {v1} mana this turn.",
    "ReturnDiscardCard": "Choose a {card_type} card in your discard pile and return it to your hand. Requires room in hand.",
    "ReturnOppnentToHand": "Return the {card_type} opposite this creature to its owner's hand. If the hand is full, send the card to the opponent's discard pile.",
    "ReturnTargetToHand": "Choose an opposing {card_type} and return it to its owner's hand. If the hand is full, send the card to the opponent's discard pile.",
    "ReturnHandsDrawCardsAddMP": "Shuffle your hand into your deck and draw up to {v1} cards. The next player to start their turn with their own copy of {name} in play gains {v2} mana. Neither player can use this floop while the bonus is pending.",
    "ShuffleHand": "Shuffle your hand into your deck and draw up to {draw_count} cards.",
}

_DETAILS = {
    "BlockFloop": "The opposing creature's floop must still be available to block.",
    "BlockFloopTarget": "Choose a creature whose floop has not already been blocked.",
    "BlockSummon": "The lane must currently be open for summons.",
    "CardsATKBonus": "Requires a card in hand.",
    "DEFBonusBuildings": "Requires a friendly building.",
    "DamageAllDamageOne": "Requires an opposing creature.",
    "DamageOpponentMyBuildings": "Requires a friendly building.",
    "DamageOpponentTheirBuildings": "Requires an opposing building.",
    "DrainAdjacentDEFAddATKBonus": "Requires a friendly neighbor. Apply the attack bonus once.",
    "HealAdjacent": "Requires a wounded neighbor.",
    "HealAdjacentDEFAndDiscard": "Requires a wounded neighbor.",
    "HealAll": "Requires a wounded friendly creature.",
    "HealHero": "Your hero must be wounded.",
    "HealHeroATK": "Your hero must be wounded.",
    "HealHeroCreatures": "Your hero must be wounded.",
    "HealSelf": "This creature must be wounded.",
    "HealSelfAndAdjacent": "This creature or at least one of its neighbors must be wounded.",
}

# GameState.FloopCard increments the counter before resolution. Each of these
# scripts subtracts one to count the player's earlier paid activations.
_PREVIOUS_FLOOPS = {
    "ATKBonusFloopTurn": "Give this creature +{v1} attack",
    "DamageHeroFloop": "Deal {v1} damage to the opposing hero",
    "DamageOpponentFloop": "Deal {v1} damage to the opposing creature",
    "HealHeroFloop": "Heal your wounded hero for {v1} HP",
    "HealTargetFloop": "Choose a friendly wounded creature and heal it for {v1} HP",
    "LowerDEFFloop": "Choose an opposing creature and reduce its defense by {v1}",
    "RaiseDEFFloop": "Choose a friendly creature and give it +{v1} defense",
}


def creature_description(row: dict, original: str, parameters: dict) -> str:
    script = row["ScriptName"]
    values = {"v1": int(row.get("val1") or 0), "v2": int(row.get("val2") or 0), **parameters}
    if script == "DamageOpponentDiscardPile":
        count = values["v2"]
        values["group"] = f"{count} card" if count == 1 else f"{count} cards"
    if script in ("DrawCards", "DrawCardsSacrifice", "DrawCardsTake"):
        count = values["v1"]
        values["draw"] = f"{count} card" if count == 1 else f"{count} cards"
    if script in _PREVIOUS_FLOOPS:
        effect = _PREVIOUS_FLOOPS[script].format(**values)
        return effect + " for each of your earlier paid floops this turn. Requires at least one earlier floop."
    if script in _EFFECTS:
        return _EFFECTS[script].format(**values)
    if script in _DETAILS:
        return original + " " + _DETAILS[script]
    return original
