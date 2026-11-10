"""Audit a complete five-game match, including clock-verified technical wins from its operator JSONL trace alone."""
import argparse
import json
import math
from collections import Counter
from pathlib import Path


def check(condition, message):
    if not condition:
        raise ValueError(message)


class Trace:
    def __init__(self, source):
        self.source = map(json.loads, source)
        self.next_row = next(self.source, None)
        self.seq = 0
        self.counts = Counter()

    def take(self, game, kind):
        self.seq += 1
        row = self.next_row
        check(row is not None, f"Trace ended before event {self.seq}: game {game} {kind}")
        self.next_row = next(self.source, None)
        actual = row["seq"], row["game"], row["type"]
        check(actual == (self.seq, game, kind),
              f"Expected event {(self.seq, game, kind)}, got {actual}")
        self.last_ts = row["ts"]
        self.counts[kind] += 1
        return row["data"]


FACTIONS = ("Corn", "Plains", "Swamp", "Cotton", "Sand")


def native_tiles(factions):
    # CWDeckController.SetLandscapes ignores Universal and ranks ties in faction enum order.
    counts = Counter(factions)
    ranked = sorted(FACTIONS, key=lambda f: -counts[f])
    represented = sum(counts[f] > 0 for f in ranked)
    if represented >= 4:
        return ranked[:4]
    if represented == 3:
        return [ranked[0], *ranked[:3]]
    if represented == 2:
        total = counts[ranked[0]] + counts[ranked[1]]
        majority_tiles = 3 if 100 * counts[ranked[0]] >= 65 * total else 2
        return [ranked[0]] * majority_tiles + [ranked[1]] * (4 - majority_tiles)
    return [ranked[0]] * 4


class PlacementAudit:
    """Track only placement choices. Ordinary card effects can change an already completed board."""
    def __init__(self, opening):
        self.first = opening["first"]
        self.before_cards = opening.get("landscape_placement") == "before_cards"
        self.remaining = [Counter(r["required_landscapes"]) for r in opening["players"]]
        self.placed = [["None"] * 4, ["None"] * 4]
        self.expected_after_action = None
        self.current_board = None

    def observe(self, state, seq):
        sides = state["board"]
        check(len(sides) == 2, f"Missing seat in board at {seq}")
        board = []
        for seat, side in enumerate(sides):
            lanes = sorted(side["lanes"], key=lambda lane: lane["lane"])
            check(side["seat"] == seat and [lane["lane"] for lane in lanes] == list(range(4)),
                  f"Invalid lane indices at {seq}")
            check(not {"required_landscapes", "landscapes", "layout"} & side.keys(),
                  f"Hidden roster layout was exposed on the public board at {seq}")
            tiles = [lane["landscape"] for lane in lanes]
            if self.remaining[seat]:
                check(tiles == self.placed[seat], f"Unplaced landscape appeared at {seq}")
            board.append(tiles)
        if self.expected_after_action is not None:
            check(board == self.expected_after_action, f"Placement changed the wrong lanes at {seq}")
        self.expected_after_action = None
        self.current_board = board
        active = state["active"]
        if state["winner"] != -1:
            check(not any(self.remaining), f"Game ended before all eight placements at {seq}")
            return
        check(active in (0, 1), f"Invalid active seat at {seq}")
        offered = {a["id"] for a in state["actions"]}
        if self.before_cards and any(self.remaining):
            expected = self.first if self.remaining[self.first] else 1 - self.first
            check(state["turn"] == 0 and active == expected, f"Wrong terrain handoff at {seq}")
            check(not any(lane.get("creature") or lane.get("building")
                          for side in sides for lane in side["lanes"]), f"Card appeared during terrain setup at {seq}")
        elif self.before_cards:
            check(state["turn"] >= 1 and (state["turn"] != 1 or active == self.first),
                  f"First card turn did not go to the drawn seat at {seq}")
        remaining = self.remaining[active]
        if remaining:
            turn = 0 if self.before_cards else (1 if active == self.first else 2)
            check(state["turn"] == turn, f"Landscape offered outside seat's first turn at {seq}")
            legal = {f"place:{tile}:{lane}" for tile in remaining
                     for lane, current in enumerate(board[active]) if current == "None"}
            check(offered == legal, f"Wrong placement choices for the active seat at {seq}")
        else:
            check(not any(a.startswith("place:") for a in offered), f"Extra placement at {seq}")

    def apply(self, engine_id, active):
        if engine_id.startswith("place:"):
            _, tile, index = engine_id.split(":")
            lane = int(index)
            self.placed[active][lane] = tile
            self.remaining[active][tile] -= 1
            if not self.remaining[active][tile]:
                del self.remaining[active][tile]
            self.expected_after_action = [side.copy() for side in self.current_board]
            self.expected_after_action[active][lane] = tile


def verify_timeout(trace, game, seats, loser, phase, deadline, started, seconds, turn, hp,
                   first=None, actions=0, events=0, wheels=0):
    timeout = trace.take(game, "timeout")
    check(math.isfinite(deadline) and abs(deadline - started - seconds) < 1
          and timeout["phase"] == phase and timeout["seat"] == loser
          and timeout["deadline"] == deadline and deadline <= timeout["observed_at"] <= trace.last_ts + 0.01,
          "Technical result has no matching expired seat clock")
    reason = "turn_timeout" if phase == "battle" else "deck_timeout"
    winner = next(seat for seat in seats if seat != loser)
    result = trace.take(game, "game_end")
    check(result == {"winner": winner, "reason": reason, "turns": turn, "hp": hp},
          "Technical result disagrees with timeout evidence")
    return {"game":game,"first":seats[first] if first is not None else None,
            "winner":winner,"reason":reason,"turns":turn,"final_hp":hp,"actions":actions,
            "snapshots":actions+1 if first is not None else 0,"public_events":events,"wheel_events":wheels}


def verify_game(trace, game, match, action_types, seat_counts):
    seats = match["seats"]
    rule = match.get("landscape_selection")
    start = trace.take(game, "draft_start")
    draft_started = trace.last_ts
    rosters = {}
    for _ in seats:
        if trace.next_row and trace.next_row["type"] == "timeout":
            check(len(rosters) == 1, "A deck timeout needs exactly one locked deck")
            loser = next(seat for seat in seats if seat not in rosters)
            return verify_timeout(trace, game, seats, loser, "select_deck", start["deadline"],
                                  draft_started, match["deck_seconds"], 0, [])
        roster = trace.take(game, "submit_deck")
        seat = roster["seat"]
        check(seat in seats and seat not in rosters, f"Invalid or duplicate roster at {trace.seq}")
        cards = roster["cards"]
        check(roster["hero"] in match["heroes"] and len(cards) == len(set(cards)) == 20
              and set(cards) <= set(match["pool"]), f"Illegal roster at {trace.seq}")
        if rule in ("from_deck", "on_turn", "before_cards"):
            required = native_tiles(match["card_factions"][card] for card in cards)
            if rule in ("on_turn", "before_cards"):
                check("landscapes" not in roster, f"Seat chose lane order during draft at {trace.seq}")
                tiles = roster["required_landscapes"]
            else:
                tiles = roster["landscapes"]
            check(sorted(tiles) == sorted(required),
                  f"Tiles differ from native deck composition at {trace.seq}")
        elif match.get("landscape_selection") == "per_seat" or "landscapes" in roster:
            tiles = roster["landscapes"]
            check(len(tiles) == 4 and set(tiles) == set(match["landscapes"]),
                  f"Illegal landscape permutation at {trace.seq}")
        rosters[seat] = {key: value for key, value in roster.items() if key != "comment"}

    opening = trace.take(game, "opening")
    check(opening["players"] == [rosters[seat] for seat in seats], f"Wrong rosters in game {game}")
    campaign = match.get("player_kinds", {}).get(seats[1]) == "campaign"
    if campaign:
        check(opening.get("campaign_opponent") is True and all(
            rosters[seats[0]][key] == rosters[seats[1]][key] for key in ("hero", "cards", "required_landscapes")
        ), f"Campaign mirror differs from the player roster in game {game}")
    check(opening["health"] == match["health"]
          and opening["first"] in (0, 1), f"Wrong opening configuration in game {game}")

    placement = None
    if rule in ("on_turn", "before_cards"):
        check(opening.get("landscape_placement") == ("own_turn" if rule == "on_turn" else "before_cards") and "landscapes" not in opening,
              f"Opening should defer lane selection to each seat's turn at {trace.seq}")
        placement = PlacementAudit(opening)
    if rule in ("from_deck", "on_turn", "before_cards"):
        check(type(opening["draw"]) is int and opening["draw"] == opening["first"],
              f"First-player draw differs from opening at {trace.seq}")
    else:
        check(opening["landscapes"] == match["landscapes"], f"Wrong opening landscapes in game {game}")

    # Only an interrupted launch can resume: the next state must still be revision zero.
    if trace.next_row is not None and trace.next_row["type"] == "run_interrupted":
        failure = trace.take(game, "run_interrupted")
        resume = trace.take(game, "run_resumed")
        check(isinstance(failure, str) and failure and resume["game"] == game and resume["reason"],
              f"Incomplete restart record at {trace.seq}")
        seeds = resume["player_seeds"]
        check(len(seeds) == len(seats) and all(type(seed) is int for seed in seeds),
              f"Missing restart player seeds at {trace.seq}")

    revision = 0
    opening_handoff = False
    await_handoff = False
    public_events = wheels = 0
    expected_native_event = None
    last_turn = None
    while True:
        state = trace.take(game, "unity_state")
        if last_turn != (state["turn"], state["active"]):
            turn_started = trace.last_ts
            last_turn = (state["turn"], state["active"])
        check(state["revision"] == revision, f"Unity revision gap at {trace.seq}")
        hp = state["hp"]
        check(len(hp) == 2, f"Expected both health totals at {trace.seq}")
        if revision == 0:
            check(state["active"] == opening["first"] and state["turn"] == (0 if rule == "before_cards" else 1)
                  and hp == [opening["health"]] * 2, f"Opening differs from Unity at {trace.seq}")
        if revision == 0 and any("landscapes" in r for r in rosters.values()):
            board = state["board"]
            check(len(board) == 2, f"Expected both sides of opening board at {trace.seq}")
            for idx, seat in enumerate(seats):
                lanes = sorted(board[idx]["lanes"], key=lambda lane: lane["lane"])
                check(board[idx]["seat"] == idx and [lane["lane"] for lane in lanes] == list(range(4))
                      and [lane["landscape"] for lane in lanes] == rosters[seat]["landscapes"],
                      f"Opening lanes disagree with {seat} submission at {trace.seq}")
        if placement is not None:
            placement.observe(state, trace.seq)
        events = state["events"]
        if await_handoff:
            check(state["turn"] == 2 and state["active"] == 1 - opening["first"]
                  and not any(e.lower().startswith("wheel ") for e in events),
                  f"Opening turn entered combat or failed to hand off at {trace.seq}")
            opening_handoff = True
            await_handoff = False
        if expected_native_event is not None:
            check(events and events[0] == expected_native_event,
                  f"Unity did not acknowledge the selected action at {trace.seq}")
        if events:
            check(trace.take(game, "public_events") == events, f"Public event mismatch at {trace.seq}")
            public_events += len(events)
            wheels += sum(e.startswith("wheel ") for e in events)
        if state["winner"] != -1:
            break
        check(min(hp) > 0 and state["active"] in (0, 1), f"Invalid live state at {trace.seq}")
        actions = {a["id"]: a["label"] for a in state["actions"]}
        check(actions and len(actions) == len(state["actions"]), f"Invalid choices at {trace.seq}")
        if trace.next_row and trace.next_row["type"] == "timeout":
            return verify_timeout(trace, game, seats, seats[state["active"]], "battle",
                                  state["turn_deadline"], turn_started, match["turn_seconds"],
                                  state["turn"], hp, opening["first"], revision, public_events, wheels)
        act = trace.take(game, "act")
        actor = seats[state["active"]]
        engine_id = act["engine_id"]
        if campaign and state["active"] == 1:
            check(engine_id == state.get("campaign_action"), f"Action differs from Unity's campaign decision at {trace.seq}")
        check(act["seat"] == actor and act["turn"] == state["turn"] and act["revision"] == revision
              and act["action_id"] == f"{game}/{revision}/{engine_id}"
              and engine_id in actions and act["label"] == actions[engine_id],
              f"Action did not match an offered choice for the active seat at {trace.seq}")
        if placement is not None:
            placement.apply(engine_id, state["active"])
        if state["turn"] == 1 and engine_id == "end":
            await_handoff = True
        public_label = act["label"]
        if rule in ("from_deck", "on_turn", "before_cards") and engine_id.startswith("discard:"):
            public_label = "Selected a card from the discard pile"
        expected_native_event = f"Seat {state['active']}: {public_label}"
        action_types[engine_id.split(":")[0]] += 1
        seat_counts[actor] += 1
        revision += 1

    winner = state["winner"]
    if rule in ("from_deck", "on_turn", "before_cards"):
        check(opening_handoff, f"Missing first-turn handoff in game {game}")
    check(winner in (0, 1) and hp[winner] > 0 and hp[1 - winner] <= 0 and not state["actions"],
          f"Winner disagrees with terminal HP or actions in game {game}")
    if trace.next_row and trace.next_row["type"] == "run_interrupted":
        check(trace.take(game, "run_interrupted") == "Unity failed after reporting a winner",
              "Unexpected interruption after the terminal snapshot")
    result = trace.take(game, "game_end")
    check(result["reason"] == "health" and result["turns"] == state["turn"]
          and result["winner"] == seats[winner] and result["hp"] == hp,
          f"Recorded result differs from Unity in game {game}")
    return {"game": game, "first": seats[opening["first"]], "winner": seats[winner], "reason":"health", "turns": state["turn"],
                "final_hp": hp, "actions": revision, "snapshots": revision + 1, "public_events": public_events,
                "wheel_events": wheels}


def verify(source):
    trace = Trace(source)
    match = trace.take(1, "match_start")
    seats, pool, heroes = match["seats"], match["pool"], match["heroes"]
    check(len(seats) == len(set(seats)) == 2, "Expected two distinct seats")
    pool_mode = match.get("pool_mode", "sample40")
    sizes = {"sample40": 40, "full": 272, "no_obsidian": 258}
    check(pool_mode in sizes, "Invalid pool_mode")
    expected_size = sizes[pool_mode]
    ruleset = match.get("ruleset", "")
    if pool_mode == "sample40":
        check("-full272-" not in ruleset and "-noobs258-" not in ruleset, "Invalid sampled catalog ruleset")
    else:
        tag = "full272" if pool_mode == "full" else "noobs258"
        terrain_tag = "-landfirst" if match.get("landscape_selection") == "before_cards" else ""
        check(len(heroes) == 72 and ruleset.endswith(f"-{tag}-20-bo5{terrain_tag}-hp{match['health']}"), "Invalid catalog ruleset")
        if pool_mode == "no_obsidian":
            check(not any(card.startswith("Creature_BL_") for card in pool), "Obsidian creature in pool")
    check(len(pool) == len(set(pool)) == expected_size and heroes and len(heroes) == len(set(heroes)),
          "Invalid match catalog")
    check(match["health"] > 0, "Invalid battle health")
    if match.get("landscape_selection") in ("from_deck", "on_turn", "before_cards"):
        factions = match["card_factions"]
        check(set(pool) <= factions.keys() and set(factions.values()) <= {*FACTIONS, "Universal"},
              "Invalid card-faction mapping")
    else:
        check(len(match["landscapes"]) == len(set(match["landscapes"])) == 4, "Invalid match landscapes")
    score = dict.fromkeys(seats, 0)
    action_types, seat_counts = Counter(), Counter()
    games = []
    for game in range(1, 6):
        report = verify_game(trace, game, match, action_types, seat_counts)
        games.append(report)
        score[report["winner"]] += 1
    check(trace.take(5, "match_end") == score, "Final score differs from the five winners")
    check(trace.next_row is None, "Unexpected trailing event after match_end")
    return {"games": games, "score": score, "event_counts": dict(trace.counts), "trace_rows": trace.seq,
                "actions_by_type": dict(action_types), "actions_by_seat": dict(seat_counts),
                "public_events": sum(g["public_events"] for g in games),
                "wheel_events": sum(g["wheel_events"] for g in games)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("trace", type=Path, help="Path to trace.jsonl")
    args = parser.parse_args()
    try:
        with args.trace.open(encoding="utf-8") as source:
            print(json.dumps(verify(source), indent=2, ensure_ascii=False))
    except (OSError, ValueError, KeyError, TypeError) as exc:
        parser.exit(1, f"Trace verification failed: {exc}\n")
