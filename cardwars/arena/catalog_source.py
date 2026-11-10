"""Read catalog parameters encoded in the active Unity project's C# rather than Blueprints."""

import re
from pathlib import Path

# Match the executing statement. AI evaluation methods can use different numbers.
_DRAW_LOOP = r"for\s*\(int i = 0; i < (\d+); i\+\+\)\s*\{\s*base\.GameInstance\.DrawCard\(base\.Owner\);"
_DISCOUNT = r"SetDiscount\(base\.Owner, CardType\.None, (\d+)\);"
_MORE_THAN = r"if\s*\(GameState\.Instance\.GetCardsInHand\(player\) > (\d+)\)"
_HAND_GATE = r"GameState\.Instance\.GetCardsInHand\(player\) < (\d+)"
_LITERALS = {
    "ReduceDEF": {"defense_factor": r"DEFFactor \*= (\d+(?:\.\d+)?)f;"},
    "DrainOpponentATKLowerSelfDEF": {
        "divisor": r"creatureScript\.(?:ATKMod|DEFMod) [+-]= base\.Enemy\.ATK / (\d+);",
        "special_attack": r"if \(base\.Enemy\.ATK == (\d+)\)",
    },
    "ATKBonusFloopCount": {"first_bonus": r"private int floopCount = (\d+);"},
    "ShuffleHand": {"draw_count": _DRAW_LOOP},
    "ShuffleAndDraw": {"draw_count": _DRAW_LOOP},
    "DestroyEntityForAction": {"reward": r"AddMagicPoints\(base\.Owner, (\d+)\);"},
    "ReduceCost": {"discount": _DISCOUNT, "hand_threshold": _MORE_THAN},
    "ReduceCostLeader": {"discount": _DISCOUNT, "hand_threshold": _MORE_THAN},
    "ReduceActionPoints": {"penalty": r"AddMagicPoints\(!base\.Owner, -(\d+), false\);"},
    "DrawCardsLeader": {"hand_gate": _HAND_GATE},
    "DrawCardsSpell": {"hand_gate": _HAND_GATE},
    "ReturnCreatures": {"hand_gate": r"GetCardsInHand\(base\.Owner\) < (\d+)"},
    "ReturnOpponentCreature": {"hand_gate": r"GetCardsInHand\(!base\.Owner\) < (\d+)"},
}
# Values cast by each class to a C# enum in its legality checks and/or resolution.
_ENUM_FIELDS = {
    **{f"AttackCreature{name}": ("Faction", "val1")
       for name in ("Corn", "Plains", "Swamp", "Cotton", "Sand")},
    "ATKPenaltyFaction": ("Faction", "val1"),
    "DamageTargetFaction": ("Faction", "val2"),
    "LandscapeATKBonus": ("LandscapeType", "val2"),
    **{script: ("CardType", "val1") for script in (
        "ReturnCard", "ReturnDiscardCard", "ReturnOppnentToHand", "ReturnTargetToHand",
        "RandomCard", "DestroyEntityForAction", "DestroyEntityForCards", "BlockCardCreature",
        "BlockCardSpell", "BlockCardBuilding",
    )},
}


class EffectSources:
    """Load once per catalog so edits to the project are visible on the next build."""

    def __init__(self, scripts: Path):
        self.literals = {}
        for script, fields in _LITERALS.items():
            source = (scripts / f"{script}.cs").read_text(encoding="utf-8")
            self.literals[script] = {}
            for key, expression in fields.items():
                values = set(re.findall(expression, source))
                if len(values) != 1:
                    raise ValueError(f"Review {script}.cs: expected one native value for {key}")
                self.literals[script][key] = values.pop()
        self.enums = {}
        for enum in ("Faction", "LandscapeType", "CardType"):
            source = (scripts / f"{enum}.cs").read_text(encoding="utf-8")
            self.enums[enum] = {
                int(number): name
                for name, number in re.findall(r"^\s*(\w+)\s*=\s*(\d+)\s*,?\s*$", source, re.M)
            }

    def parameters(self, row: dict) -> dict:
        script = row["ScriptName"]
        values = self.literals.get(script, {}).copy()
        if "hand_threshold" in values:
            values["minimum_hand"] = int(values.pop("hand_threshold")) + 1
        if script in _ENUM_FIELDS:
            enum, field = _ENUM_FIELDS[script]
            try:
                # CardDataManager loads blank val1/val2 as zero.
                name = self.enums[enum][int(row[field] or 0)]
                if enum == "CardType":
                    values["card_type"] = name.lower()
                else:
                    values[enum] = name
            except (ValueError, KeyError) as exc:
                raise ValueError(f"Review {script}: unknown {enum} in {field}={row.get(field)!r}") from exc
        return values
