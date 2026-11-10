"""Build the public match catalog from the same Blueprints that Card Wars loads."""

import json
import random
import xml.etree.ElementTree as ET
from pathlib import Path

from .catalog_source import EffectSources
from .creature_text import creature_description
from .leader_text import leader_description
from .spell_building_text import spell_building_description


def make_catalog(
    project: Path, seed: int, pool_mode: str = "sample40"
) -> tuple[str, list[str], list[str], dict[str, str]]:
    assets = project / "Assets"
    blueprints = assets / "StreamingAssets" / "Blueprints"
    sources = EffectSources(assets / "Scripts" / "Assembly-CSharp")
    translations = {}
    for file in sorted((assets / "Resources" / "languages").glob("EN_*.txt")):
        for entry in ET.parse(file).getroot().findall("entry"):
            translations[entry.attrib["name"]] = entry.text or ""

    def load(table):
        return json.loads((blueprints / f"db_{table}.json").read_text(encoding="utf-8"))

    def description(row, val1, val2):
        return (
            translations[row["Desc"]]
            .replace("<val1>", str(int(row.get(val1) or 0)))
            .replace("<val2>", str(int(row.get(val2) or 0)))
        )

    cards = []
    for table, kind in (
        ("Creatures", "Creature"),
        ("Spells", "Spell"),
        ("Buildings", "Building"),
    ):
        for row in load(table):
            cards.append((row["ID"], kind, row))
    if pool_mode in ("full", "no_obsidian"):
        ordinary = {row["Name"] for _, _, row in cards if row["Quality"] != "Gold"}
        pool = sorted(
            card for card in cards
            if card[2]["Quality"] != "Gold" or card[2]["Name"] not in ordinary
        )
        if pool_mode == "no_obsidian":
            pool = [card for card in pool if card[2]["Quality"] != "Obsidian"]
        expected_size = 258 if pool_mode == "no_obsidian" else 272
        if len(pool) != expected_size or len({row["Name"] for _, _, row in pool}) != expected_size:
            raise ValueError(f"Expected a catalog of {expected_size} distinct card names")
    elif pool_mode == "sample40":
        pool = sorted(random.Random(seed).sample(cards, 40))
    else:
        raise ValueError(f"Unknown card pool: {pool_mode}")
    lines = [
        "# Match catalog",
        "",
        "Choose one hero and 20 distinct card IDs. All cards are level 1. "
        "Universal cards can be played on any landscape. A creature's floop cost is followed "
        "by the effect of activating it. Rarity is the number of stars checked by card effects. "
        "Magic Points are mana.",
        "",
        "## Cards",
        "",
    ]
    for card_id, kind, row in pool:
        edition = "Fionna & Cake" if row["Quality"] == "FionnaCake" else row["Quality"]
        stats = (f"{kind}, {edition}, rarity {row['Rarity']}, {row['Faction']}, "
                 f"mana {row['Cost']}")
        if kind == "Creature":
            stats += f", attack {row['ATK']}, defense {row['DEF']}"
        if row.get("AbilityType") == "FLOOP":
            stats += f", floop {row.get('FloopCost') or 0} mana"
        describe = creature_description if kind == "Creature" else spell_building_description
        parameters = sources.parameters(row)
        parameters["name"] = translations[row["Name"]]
        effect = describe(row, description(row, "val1", "val2"), parameters)
        lines.append(f"- `{card_id}` {translations[row['Name']]} — {stats}. {effect}")
    lines.extend(["", "## Heroes", ""])
    heroes = sorted(load("Leaders"), key=lambda row: row["ID"])
    if pool_mode != "sample40" and len({row["ID"] for row in heroes}) != 72:
        raise ValueError("Expected all 72 heroes")
    for row in heroes:
        effect = leader_description(row, sources.parameters(row))
        lines.append(
            f"- `{row['ID']}` {translations[row['Name']]} — "
            f"{effect} Cooldown {row['Cooldown']} {'turn' if int(row['Cooldown']) == 1 else 'turns'}."
        )
    return (
        "\n".join(lines) + "\n",
        [card[0] for card in pool],
        [row["ID"] for row in heroes],
        {card_id: row["Faction"] for card_id, _, row in pool},
    )
