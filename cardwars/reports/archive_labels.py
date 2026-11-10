"""Regenerate the offline report's English labels from a Card Wars Unity project."""

import argparse
import json
import xml.etree.ElementTree as ET
from importlib.resources import files
from pathlib import Path


def _entries(path):
    return {item.attrib["name"]: item.text for item in ET.parse(path).getroot().findall("entry")}


def generate(project: Path) -> str:
    languages = project / "Assets/Resources/languages"
    blueprints = project / "Assets/StreamingAssets/Blueprints"
    english = {}
    for path in sorted(languages.glob("EN_*.txt")):
        english.update(_entries(path))

    names = {}
    for table in ("Creatures", "Spells", "Buildings", "Leaders"):
        for row in json.loads((blueprints / f"db_{table}.json").read_text("utf-8")):
            card_id = row["ID"]
            name = english[row["Name"]]
            if card_id in names or not name:
                raise ValueError(f"Duplicate ID or missing English name for {card_id}")
            names[card_id] = name

    en_menu = _entries(languages / "EN_Menu.txt")
    prompts = {}
    for key, original in _entries(languages / "RU_Menu.txt").items():
        if key.startswith(("!!PICK_", "!!TAP_CREATURE_")):
            translation = en_menu[key]
            if not original or not translation or prompts.setdefault(original, translation) != translation:
                raise ValueError(f"Missing or conflicting target prompt for {key}")

    return json.dumps({"names": names, "target_prompts": prompts},
                      indent=2, ensure_ascii=False, sort_keys=True) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project", type=Path, help="Path to the restored Unity project")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true", help="Compare the packaged snapshot with Unity")
    mode.add_argument("--output", type=Path, help="Write the snapshot as UTF-8 JSON")
    args = parser.parse_args(argv)
    result = generate(args.project)
    if args.check:
        saved = files("cardwars.reports").joinpath("assets/english.json").read_text("utf-8")
        if result != saved:
            parser.exit(1, "Packaged English labels differ from the Unity source.\n")
        print("Packaged English labels match the Unity source.")
    else:
        args.output.write_text(result, encoding="utf-8")


if __name__ == "__main__":
    main()
