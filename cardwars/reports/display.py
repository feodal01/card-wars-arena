"""English reader labels, kept separate from the evidence in recorded events."""

import json
import re
from functools import cache
from importlib.resources import files

CATALOG_NAME = re.compile(r"^- `([^`]+)` (.*?) — ", re.MULTILINE)
CYRILLIC = re.compile(r"[а-яё]", re.IGNORECASE)
CARD_ID = re.compile(r"\b(?:Creature|Spell|Building|Leader)_\w+")


@cache
def _english():
    # Original names from the game's Blueprint Name keys and EN localization.
    # Archived target prompts use the matching RU_Menu and EN_Menu keys.
    return json.loads(files("cardwars.reports").joinpath("assets/english.json").read_text("utf-8"))


def display_names(catalog):
    names = _english()["names"].copy()
    if not isinstance(catalog, str):
        return names
    for card_id, recorded in CATALOG_NAME.findall(catalog):
        # A new catalog may supply names for IDs unknown to this report version.
        if not CYRILLIC.search(recorded):
            names[card_id] = recorded
        elif card_id not in names:
            names[card_id] = card_id
    return names


def display_label(label, names):
    # Localized target prompts occur in both offered actions and "Seat N: ..." acknowledgements.
    if CYRILLIC.search(label):
        for original, english in _english()["target_prompts"].items():
            label = label.replace(original, english)
    label = re.sub(r"\blane (\d+)\b", lambda m: f"lane {int(m[1]) + 1}", label)
    return CARD_ID.sub(lambda m: names.get(m[0], m[0]), label)


def trace_display(events):
    start = next((e.get("data") for e in events if e["type"] == "match_start"), None)
    names = display_names(start.get("catalog", "") if isinstance(start, dict) else "")
    labels = []
    for event in events:
        data = event.get("data")
        if event["type"] == "act" and isinstance(data, dict):
            labels.append(data.get("label"))
        elif event["type"] == "unity_state" and isinstance(data, dict):
            if isinstance(choices := data.get("actions"), list):
                labels.extend(choice.get("label") for choice in choices if isinstance(choice, dict))
            if isinstance(messages := data.get("events"), list):
                labels.extend(messages)
        elif event["type"] == "public_events" and isinstance(data, list):
            labels.extend(data)
    rendered = {}
    for label in sorted({s for s in labels if isinstance(s, str)}):
        text = display_label(label, names)
        if text != label:
            rendered[label] = text
    return {"names": names, "labels": rendered}
