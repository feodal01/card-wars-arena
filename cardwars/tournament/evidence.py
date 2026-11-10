"""Read completed match artifacts. Join each score to a verified native trace."""

import hashlib
import json
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

from cardwars.reports.verify import verify

# These two pre-identity recordings have known uniform-random policies on both
# seats. Identify a recording by its bytes, not by a renamed folder or seat label.
LEGACY = {
    # Public copy with the organizer directory removed from one startup error.
    "435443a54955c2c59ca6ffcb3582068f625ba443d1c3c1bfa5377e28b910ae1b": "legacy/from_deck/hp25",
    "7b23883e29ea2c9f34a202548ad40fab9a9b62af73da124ceff7a1a9ed3b7b5d": "legacy/from_deck/hp25",
    "361b9ebdd2bb5a9e15710c537b3f9996daabfddd9e06de419e6ede0fc450db55": "legacy/on_turn/hp25",
}


@dataclass(frozen=True)
class Match:
    match_id: str
    ruleset: str
    players: tuple
    rating_ids: tuple
    kinds: tuple
    wins: tuple
    seed: int
    trace_hash: str
    pool_hash: str
    directory: Path
    player_profiles: tuple = ()


def read_match(directory, fixture=None, plan=None):
    directory = Path(directory)
    trace_path = directory / "trace.jsonl"
    raw = trace_path.read_bytes()
    trace_hash = hashlib.sha256(raw).hexdigest()
    trace = BytesIO(raw)
    meta = json.loads(trace.readline())["data"]
    trace.seek(0)
    audit = verify(trace)
    summary = json.loads((directory / "results.json").read_text(encoding="utf-8"))
    seats = tuple(meta["seats"])
    if audit["score"] != summary["score"] or len(summary["games"]) != 5:
        raise ValueError(f"{directory}: score differs from verified five-game trace")
    for claimed, verified in zip(summary["games"], audit["games"]):
        keys = ("game", "winner", "reason", "turns", "actions", "first")
        if (
            any(claimed[k] != verified[k] for k in keys)
            or claimed["hp"] != verified["final_hp"]
        ):
            raise ValueError(
                f"{directory}: reported game differs from the verified trace"
            )
    if trace_hash in LEGACY:
        ruleset = LEGACY[trace_hash]
        rating_ids = ("random-uniform-v1", "random-uniform-v1")
        kinds = ("random", "random")
        match_id = trace_hash
    else:
        ruleset = meta["ruleset"]
        match_id = meta["match_id"]
        rating_ids = tuple(meta["identities"][s] for s in seats)
        if (
            not isinstance(match_id, str)
            or not match_id
            or not all(isinstance(x, str) and x for x in (*rating_ids, ruleset))
        ):
            raise ValueError(f"{directory}: missing match or policy identity")
        if ruleset.startswith("cardwars-v1-") and (
            meta.get("landscape_selection") not in ("on_turn", "before_cards")
            or ruleset != ("cardwars-v1-on-turn-40-20-bo5"
                           + ("-landfirst" if meta["landscape_selection"] == "before_cards" else "")
                           + f"-hp{meta['health']}")
        ):
            raise ValueError(
                f"{directory}: declared ruleset contradicts audited match settings"
            )
        if (
            summary.get("complete") is not True
            or summary.get("match_id") != match_id
            or summary.get("ruleset") != ruleset
            or tuple(summary.get("players", ())) != seats
            or summary.get("seed") != meta["seed"]
            or summary.get("identities") != meta["identities"]
            or any(summary.get(key) != meta.get(key) for key in ("display_names", "player_profiles"))
        ):
            raise ValueError(f"{directory}: match metadata differs from trace")
        kinds = tuple(meta["player_kinds"][s] for s in seats)
        if any(k not in {"random", "claude", "codex", "prime", "opencode", "harness", "command", "campaign", "human"} for k in kinds):
            raise ValueError(f"{directory}: unknown player kind")
        if plan and kinds != tuple(plan["participants"][s]["kind"] for s in seats):
            raise ValueError(
                f"{directory}: player kinds differ from the frozen schedule"
            )
    if plan and any("harness" in plan["participants"][seat] for seat in seats) and "player_profiles" not in meta:
        raise ValueError(f"{directory}: missing scheduled player profiles")
    if "player_profiles" in meta:
        names = meta.get("display_names", {})
        for seat in seats:
            profile = meta["player_profiles"].get(seat)
            if not isinstance(profile, dict) or not names.get(seat) or profile.get("display_name") != names[seat]:
                raise ValueError(f"{directory}: inconsistent participant display name")
    if plan and "player_profiles" in meta:
        for seat in seats:
            entrant = plan["participants"][seat]
            profile = meta["player_profiles"][seat]
            if any(entrant.get(key) != profile.get(key) for key in ("model", "effort")) or (
                "harness" in entrant and profile.get("harness") != entrant["harness"]
            ):
                raise ValueError(f"{directory}: player profile differs from the frozen schedule")
    if fixture is not None and (
        meta["seed"] != fixture["seed"]
        or list(seats) != fixture["players"]
        or ruleset != plan["ruleset"]
        or rating_ids != tuple(plan["participants"][s]["rating_id"] for s in seats)
    ):
        raise ValueError(
            f"{directory}: recorded match does not match its scheduled fixture"
        )
    wins = tuple(audit["score"][s] for s in seats)
    if sum(wins) != 5 or max(wins) < 3:
        raise ValueError(f"{directory}: incomplete match score")
    pool_hash = hashlib.sha256(
        json.dumps(meta["pool"], separators=(",", ":")).encode()
    ).hexdigest()
    return Match(
        match_id,
        ruleset,
        seats,
        rating_ids,
        kinds,
        wins,
        meta["seed"],
        trace_hash,
        pool_hash,
        directory,
        tuple(meta["player_profiles"][s] for s in seats) if "player_profiles" in meta else (),
    )
