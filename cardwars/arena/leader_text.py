"""Describe leader Cast and CanPlay using the active leader's Blueprint fields."""

_EFFECTS = {
    "ATKBonusAllCreaturesLeader": "Give all your creatures +{v1} attack.",
    "DEFBonusAllCreaturesLeader": "Give all your creatures +{v1} defense.",
    "ATKBonusFactionCreaturesLeader": "Give all your {faction} creatures +{v1} attack.",
    "DEFBonusFactionCreaturesLeader": "Give all your {faction} creatures +{v1} defense.",
    "ATKDEFBonusFactionCreaturesLeader": "Give all your {faction} creatures +{v1} attack and +{v2} defense.",
    "DrawCardsLeader": "Draw up to {v1} {cards} from your deck. Requires a card in your deck and fewer than {hand_gate} cards in hand.",
    "GainActionPointsLeader": "Gain {v1} mana this turn.",
    "HealAllCreaturesLeader": "Fully heal all your wounded creatures.",
    "HealAllFactionCreaturesLeader": "Fully heal all your wounded {faction} creatures.",
    "HealCreatureLeader": "Choose one of your wounded creatures and fully heal it.",
    "ReduceCostLeader": "Your cards cost {discount} less mana this turn. Requires at least {minimum_hand} cards in hand.",
    "ReduceTypeCostLeader": "Your {card_type} cards cost {v1} less mana this turn. Requires a {card_type} card in hand.",
    "ReduceFactionCreatureCostLeader": "This turn your {faction} {card_type} cards cost {v1} less mana and your other {card_type} cards cost {v2} less. Requires a {card_type} card in hand.",
    "ReturnCardLeader": "Choose a card in your discard pile and return it to your hand. Requires room in hand.",
    "ReturnCardTypeLeader": "Choose a {card_type} card in your discard pile and return it to your hand. Requires room in hand.",
    "ReturnBuildingsLeader": "Return all opposing buildings to their owner's hand. Once the hand is full, discard the remaining buildings.",
    "BlockCardTypeDestroyBuildingsLeader": "Discard every opposing building. Your opponent cannot play {card_type} cards on their next turn. Requires an opposing building in play or a {card_type} card in the opponent's hand.",
}


def leader_description(row: dict, parameters: dict) -> str:
    script = row["ScriptName"]
    effect = _EFFECTS[script].format(
        v1=row["Val1"], v2=row["Val2"], faction=row["forFaction"],
        card_type=row["forCardType"].lower(), cards="card" if row["Val1"] == "1" else "cards",
        **parameters,
    )
    if script.startswith(("ATK", "DEF", "Heal")):
        effect += " Requires at least one matching creature in play."
    return effect
