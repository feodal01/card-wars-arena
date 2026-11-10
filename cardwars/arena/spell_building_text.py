"""Level-one spell and building effects where the Unity implementation adds detail."""

_EFFECTS = {
    "BlockTargetFloop": "Choose an opposing creature whose floop is not already blocked. It cannot floop on its owner's next turn.",
    "ReduceDEF": "Multiply every creature's defense by {defense_factor}, rounding down. Existing wounds remain.",
    "DrainOpponentHealth": "Heal your hero for {val1} HP and deal {val1} damage to the opposing hero.",
    "ReduceCost": "Your remaining cards cost {discount} less mana this turn. Requires at least {minimum_hand} cards in hand, including this spell.",
    "ReduceActionPoints": "Reduce the opposing hero's mana for their next turn by {penalty}.",
    "DoubleDamage": "Choose a wounded opposing creature. Deal damage to it equal to its missing HP.",
    "ShuffleAndDraw": "Shuffle your remaining hand into your deck and draw up to {draw_count} cards.",
    "MoveBuildingOpponent": "Move an opposing building to another opposing lane without a building. The destination may contain a creature.",
    "MoveBuildingSelf": "Move one of your buildings to another friendly lane without a building. The destination may contain a creature.",
    "HealCreature": "Choose one of your wounded creatures and fully heal it.",
    "RandomCard": "Add a random {card_type} card from your deck to your hand. The card also stays in the deck and can be drawn later.",
    "DestroyHigherRarity": "Deal damage equal to remaining HP to each opposing creature of rarity {val1} or higher.",
    "DestroyLowerRarity": "Deal damage equal to remaining HP to each opposing creature of rarity {val1} or lower.",
    "KillLoneOpponent": "If your opponent has exactly one creature, deal damage equal to its remaining HP to it.",
    "HealCreatures": "Requires one of your creatures to be wounded. Fully heal every creature on both sides.",
    "ReturnCreatures": "Return all your creatures to your hand. Once your hand contains {hand_gate} cards, send the remaining creatures to your discard pile.",
    "ReturnOpponentCreature": "Choose an opposing creature and return it to its owner's hand. If the opponent already holds {hand_gate} or more cards, send it to their discard pile.",
    "EmptyLaneCards": "Draw one card per friendly lane without a creature, even if the lane contains a building. Requires at least one such lane, a card in your deck and room in your hand.",
    "DestroyBuildingLane": "Choose an opposing lane with a creature or building. Send all creatures and buildings in that lane and the friendly lane opposite it directly to their owners' discard piles. Skip on-death abilities.",
    "ActionPointLandscapes": "Gain one mana for each distinct landscape type on both sides of the field, counting each type once.",
    "DamageToATK": "Choose a wounded friendly creature. Replace its attack modifier so that its attack before multipliers equals its missing HP.",
    "FlatFloopCost": "Set the base floop cost of your creatures to {val1} mana for the rest of the turn. Clear your global floop cost modifier and keep any lane-specific modifier.",
    "ATKDEFBonusEmptyLanes": "The friendly creature here gains +{val1} attack and +{val2} defense for every friendly lane without a creature. When the building leaves, subtract {val1} attack and {val2} defense for each of your creatures in play.",
    "ATKBonusLandscapes": "When this building or your creature enters this lane, the creature gains +{val1} attack for each distinct landscape type on your side. When the building leaves, subtract {val1} attack for each such type.",
    "StartTurnHealCreatures": "At the start of your turn, heal your creature in this lane for {val1} HP per friendly creature in play, including itself.",
    "DEFOnFloop": "Each time your creature in this lane floops, it gains +{val1} defense.",
    "DamageReduction": "Each time your creature in this lane takes damage, reduce that damage by {val1}, to a minimum of zero.",
    "RarityGate": "Your opponent can play only creatures and buildings of rarity {val1} or lower in the lane opposite this building.",
    "SwapATKDEFBuilding": "When this building or your creature enters this lane, swap the creature's attack and defense. When the building leaves, add the creature's defense just before removal to its base attack and its attack just before removal to its base defense. Stat multipliers and existing wounds remain.",
    "SwapATKDEFSelf": "{original} Stat multipliers apply to the new values. Existing wounds remain.",
    "SwapATKDEFOpponent": "{original} Stat multipliers apply to the new values. Existing wounds remain.",
    "HealHeroOnDeath": "When your creature in this lane dies from losing all HP, heal your hero for {val1} HP.",
    "ReturnToHandSacrifice": "When your creature in this lane dies from losing all HP, return it to your hand even if your hand is full. Discard this building.",
    "DamageHeroOnDeath": "When your creature in this lane dies from losing all HP, deal {val1} damage to the opposing hero.",
    "FloopCostMod": "Your creature's floop in this lane costs {val1} less mana, to a minimum of zero.",
    "ActionOnFloop": "Gain {val1} mana when your creature in this lane floops.",
    "BlockCardCreature": "Your opponent cannot play {card_type} cards on their next turn.",
    "BlockCardSpell": "Your opponent cannot play {card_type} cards on their next turn.",
    "BlockCardBuilding": "Your opponent cannot play {card_type} cards on their next turn.",
}

_ATTACKS = {
    "AttackCreatureCorn", "AttackCreaturePlains", "AttackCreatureSwamp",
    "AttackCreatureCotton", "AttackCreatureSand",
}


def _cards(count: str) -> str:
    return f"{count} card" if int(count) == 1 else f"{count} cards"


def spell_building_description(row: dict, original: str, parameters: dict) -> str:
    script = row["ScriptName"]
    if script in _ATTACKS:
        source = "The spell" if script == "AttackCreatureSand" else "Your creature"
        return (
            f"Choose a friendly {parameters['Faction']} creature facing an opposing creature. "
            f"{source} deals damage to that enemy equal to your creature's attack."
        )
    if script == "DrawCardsSpell":
        return (
            f"Draw {_cards(row['val1'])}, while your deck has cards and your hand has room. "
            f"Requires fewer than {parameters['hand_gate']} cards in hand to cast."
        )
    if script in ("DestroyEntityForCards", "DestroyEntityForAction"):
        sacrifice = f"Send one of your {parameters['card_type']} cards from play directly to your discard pile"
        if script == "DestroyEntityForCards":
            return f"{sacrifice} and draw {_cards(row['val2'])}. Requires a card in your deck."
        return f"{sacrifice} and gain {parameters['reward']} mana."
    if script == "ReturnCard":
        kind = parameters["card_type"]
        text = f"Choose a {kind} card in your discard pile and return it to your hand."
        if kind == "spell":
            text += " Requires a spell already in your discard pile to cast. You can choose the spell you just cast."
        return text
    template = _EFFECTS.get(script)
    if template is None:
        return original
    return template.format(original=original, **row, **parameters)
