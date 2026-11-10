"""Generate local spectator graphics for a completed five-game match."""

import argparse
import base64
import json
import re
from pathlib import Path

from .display import display_names, display_label

HERE = Path(__file__).resolve().parent


def data_uri(path, kind):
    return f"data:{kind};base64," + base64.b64encode(path.read_bytes()).decode("ascii")


def player(seat, profile):
    model = profile.get("model") or seat
    match = re.fullmatch(r"gpt-([\d.]+)-(\w+)", model)
    claude = re.fullmatch(r"claude-(\w+)-(\d+)-(\d+)", model)
    if match:
        name = f"{match[2].title()} {match[1]}"
    elif claude:
        name = f"{claude[1].title()} {claude[2]}.{claude[3]}"
    else:
        name = profile.get("display_name", seat) if profile.get("harness") == "Card Wars" else model
    brand = "openai" if model.startswith("gpt-") else "claude" if model.startswith("claude-") else None
    harness = profile.get("harness") or ""
    return dict(seat=seat, name=name, brand=brand, effort=profile.get("effort"),
                harness={"claude": "Claude Code", "codex": "Codex"}.get(harness, harness))


def hero_graphics(assets, selected):
    leaders = json.loads((assets / "StreamingAssets/Blueprints/db_Leaders.json").read_text())
    portraits = {}
    atlases = {}
    rectangles = {}
    # The NGUI prefab uses top-left coordinates, matching an SVG viewBox.
    sprite_rect = re.compile(
        r"^  - name: (\S+)\n    outer:\n      serializedVersion: \d+\n"
        r"      x: (\d+)\n      y: (\d+)\n      width: (\d+)\n      height: (\d+)$", re.M
    )
    for leader in leaders:
        if leader["ID"] not in selected:
            continue
        atlas = leader["IconAtlas"]
        if atlas not in atlases:
            prefab = (assets / "Resources" / f"{atlas}.prefab").read_text()
            rectangles[atlas] = {name: " ".join(rect) for name, *rect in sprite_rect.findall(prefab)}
            atlases[atlas] = data_uri(assets / "Texture2D" / f"{atlas}.png", "image/png")
        portraits[leader["ID"]] = dict(atlas=atlas, rect=rectangles[atlas][leader["SpriteNameHero"]])
    return portraits, atlases


def card_graphics(unity, start, names, used):
    descriptions = dict(re.findall(r"^- `([^`]+)` .*? — (.+)$", start["catalog"], re.M))
    tables = unity / "Assets/StreamingAssets/Blueprints"
    rows = {r["ID"]: r for t in ("Creatures", "Spells", "Buildings")
            for r in json.loads((tables / f"db_{t}.json").read_text())}
    textures = unity / "Assets/Resources/textures"
    sprites = {p.stem.casefold(): p for folder in ("cardart", "cardartzoomed")
               for p in (textures / folder).rglob("*.png")}
    cards = {}
    for key in sorted(used):
        row = rows[key]
        art = sprites.get(row["SpriteName"].casefold())
        details = descriptions[key].split(". ", 1)
        cards[key] = dict(name=names[key], type=key.split("_", 1)[0], cost=row["Cost"],
                          faction=start["card_factions"][key], atk=row.get("ATK"), hp=row.get("DEF"),
                          effect=details[1] if len(details) > 1 else "",
                          floop=(re.findall(r"floop (\d+) mana", details[0]) or [None])[0],
                          art=data_uri(art, "image/png") if art else "")
    return cards


def match_graphics(trace, unity):
    events = [json.loads(line) for line in trace.read_text().splitlines() if line.strip()]
    start = next(event["data"] for event in events if event["type"] == "match_start")
    seats = start["seats"]
    players = [player(s, start.get("player_profiles", {}).get(s, {})) for s in seats]
    names = display_names(start["catalog"])
    games = {}
    used = set()
    before = [0, 0]
    states = {}
    for event in events:
        number, kind, data = event["game"], event["type"], event["data"]
        if kind == "draft_start":
            games[number] = dict(number=number, before=before.copy(), decks=[], plays=[], placements=[], hp=[])
        game = games.get(number)
        if game is None:
            continue
        if kind == "submit_deck":
            game["decks"].append(dict(player=seats.index(data["seat"]), cards=data["cards"],
                                      hero=names[data["hero"]], heroId=data["hero"], comment=data.get("comment", "")))
            used.update(data["cards"])
        elif kind == "act":
            if data["engine_id"].startswith("place:"):
                _, terrain, lane = data["engine_id"].split(":")
                game["placements"].append(dict(rev=data["revision"], player=seats.index(data["seat"]),
                                               terrain=terrain, lane=int(lane), comment=data.get("comment", "")))
            card = re.match(r"(?:Play|Cast) ((?:Creature|Building|Spell)_\w+)", data["label"])
            if card:
                card_id = card[1]
                used.add(card_id)
                state = states[number]
                game["plays"].append(dict(hands=state["hands"], board=state["board"], rev=data["revision"], turn=data["turn"], card=card_id,
                                          player=seats.index(data["seat"]), comment=data.get("comment", ""),
                                          label=display_label(data["label"], names)))
        elif kind == "unity_state":
            states[number] = data
            point = [data["turn"], *data["hp"]]
            if game["hp"] and game["hp"][-1][0] == point[0]:
                game["hp"][-1] = point
            else:
                game["hp"].append(point)
        elif kind == "game_end":
            winner = seats.index(data["winner"])
            before[winner] += 1
            game.update(winner=winner, after=before.copy(), turns=data.get("turns"),
                        finalHp=data.get("hp"), reason=data.get("reason"))
    if len(games) != 5 or not all("winner" in g for g in games.values()):
        raise ValueError("Broadcast replay requires five completed games")
    cards = card_graphics(unity, start, names, used)
    selected = {deck["heroId"] for g in games.values() for deck in g["decks"]}
    portraits, atlases = hero_graphics(unity / "Assets", selected)
    return dict(portraits=portraits, atlases=atlases, players=players, games=list(games.values()), cards=cards, health=start["health"],
                pool=len(start["pool"]), logos={p: data_uri(HERE / f"assets/{p}.svg", "image/svg+xml")
                                                for p in ("openai", "claude")})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("trace", type=Path)
    parser.add_argument("unity_project", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    data = match_graphics(args.trace, args.unity_project)
    args.output.parent.mkdir(exist_ok=True, parents=True)
    args.output.write_text(broadcast_html(data))


def broadcast_html(data, extra_script=""):
    template = (HERE / "broadcast.html").read_text()
    script = (HERE / "broadcast.js").read_text() + "\n" + (HERE / "broadcast_field.js").read_text() + "\n" + extra_script
    return (template.replace("/*STYLE*/", (HERE / "broadcast.css").read_text())
            .replace("/*SCRIPT*/", script)
            .replace("/*MATCH*/", json.dumps(data).replace("<", r"\u003c")))


if __name__ == "__main__":
    main()
