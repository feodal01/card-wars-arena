"""Deterministic round-robin fixtures and a frozen tournament manifest."""

import hashlib
import itertools
import json
import random
import tomllib
from pathlib import Path


def fingerprint(value):
    packed = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
    return hashlib.sha256(packed.encode("utf-8")).hexdigest()


def player_fingerprint(player):
    # Keep frozen schedules for pre-profile random/command entrants reproducible.
    if player["kind"] in {"random", "command"}:
        player = {k: v for k, v in player.items() if k not in {"harness", "trace_format"}}
    return fingerprint(player)


def fixtures(entrants, repeats, seed):
    """One five-game match per unordered pair in each round."""
    names = sorted(entrants)
    if len(names) < 2 or len(names) != len(set(names)):
        raise ValueError("Expected at least two distinct entrants")
    if type(repeats) is not int or repeats < 1:
        raise ValueError("repeats must be a positive integer")
    if type(seed) is not int:
        raise ValueError("A tournament integer seed is required")

    rng = random.Random(seed)
    seen_seeds = set()
    schedule = []
    for repeat in range(1, repeats + 1):
        pairs = list(itertools.combinations(names, 2))
        rng.shuffle(pairs)
        for a, b in pairs:
            if rng.randrange(2):
                a, b = b, a
            pair_seed = rng.getrandbits(63)
            while pair_seed in seen_seeds:
                pair_seed = rng.getrandbits(63)
            seen_seeds.add(pair_seed)
            schedule.append(
                {
                    "id": f"match-{len(schedule) + 1:04d}",
                    "repeat": repeat,
                    "players": [a, b],
                    "seed": pair_seed,
                }
            )
    return schedule


def load_plan(path):
    from cardwars.config import load_config

    path = Path(path).resolve()
    with path.open("rb") as file:
        spec = tomllib.load(file)["tournament"]
    extra = set(spec) - {"match_config", "entrants", "repeats", "seed"}
    if extra:
        raise ValueError(f"Unexpected tournament settings: {sorted(extra)}")
    match_path = (path.parent / spec["match_config"]).resolve()
    match = load_config(match_path, resolve_engine=False)
    names = spec["entrants"]
    if not isinstance(names, list) or not all(isinstance(x, str) for x in names):
        raise ValueError("entrants must be a list of player IDs in the match config")
    scheduled = fixtures(names, spec.get("repeats", 1), spec["seed"])
    people = {}
    random_policies = set()
    for name in sorted(names):
        if name not in match.players:
            raise ValueError(f"Unknown entrant: {name}")
        p = match.players[name]
        if p["kind"] == "random":
            if p["policy"] in random_policies:
                raise ValueError(f"Duplicate built-in random policy: {p['policy']}")
            random_policies.add(p["policy"])
        if p["kind"] not in {"random", "command"} and not p.get("model"):
            raise ValueError(f"Set an explicit model for rated agent {name}")
        people[name] = {
            "kind": p["kind"],
            "rating_id": p["rating_id"],
            "model": p.get("model"),
            "definition": player_fingerprint(p),
            **{key: p[key] for key in ("display_name", "effort") if key in p},
            **({"harness": p["harness"]} if p["kind"] not in {"random", "command"} else {}),
        }
    # A seat alias can run diagnostics, but cannot be a second rated opponent.
    ids = [p["rating_id"] for p in people.values()]
    if len(ids) != len(set(ids)):
        raise ValueError(
            "Duplicate rating identity: select distinct, versioned opponents"
        )
    plan = {
        "format": 2,
        "seed": spec["seed"],
        "repeats": spec.get("repeats", 1),
        "ruleset": match.ruleset,
        "participants": people,
        "fixtures": scheduled,
    }
    return match_path, plan
