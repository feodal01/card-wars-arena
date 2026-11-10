"""Detect Unity source changes since the card text was reviewed."""

import hashlib
import json
from pathlib import Path

BASELINE = Path(__file__).with_name("catalog_sources.json")
TABLES = ("Creatures", "Spells", "Buildings", "Leaders")
# Shared implementations also affect what the scripts do when they call the engine.
SHARED = {
    "CardScript", "CreatureScript", "SpellScript", "BuildingScript", "LeaderScript",
    "GameState", "Lane", "CardForm", "CardItem", "LeaderForm", "LeaderItem",
    "CWBattleSequenceController", "BattleManagerScript", "ArenaChoices",
    "CardDataManager", "Faction", "CardType", "LandscapeType", "BlockCardType",
}


def source_hashes(project):
    assets = project / "Assets"
    classes = set(SHARED)
    for table in TABLES:
        path = assets / "StreamingAssets/Blueprints" / f"db_{table}.json"
        for row in json.loads(path.read_text(encoding="utf-8")):
            classes.add(row["ScriptName"])
    scripts = assets / "Scripts/Assembly-CSharp"
    return {
        name: hashlib.sha256((scripts / (name + ".cs")).read_bytes()).hexdigest()
        for name in sorted(classes)
    }


def check_sources(project):
    reviewed = json.loads(BASELINE.read_text(encoding="utf-8"))
    current = source_hashes(project)
    changes = sorted(key for key in reviewed.keys() | current.keys()
                     if reviewed.get(key) != current.get(key))
    if changes:
        raise ValueError("Review changed Unity effect sources before publishing: " + ", ".join(changes))
    return len(current)
