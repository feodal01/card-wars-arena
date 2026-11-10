"""State shared by the trusted match host and the player-facing MCP tools."""

import json
import time

from cardwars.commentary import decision_comment

DECK_SECONDS = 600
GAME_COUNT = 5
TURN_SECONDS = 300


def create(db, seats, landscapes, health):
    db.execute(
        "CREATE TABLE series(game INTEGER, phase TEXT, seats TEXT, landscapes TEXT, "
        "health INTEGER, observation TEXT, turn_deadline REAL, pending TEXT, placement TEXT NOT NULL DEFAULT 'own_turn')"
    )
    db.execute(
        "CREATE TABLE trace(seq INTEGER PRIMARY KEY, ts REAL, game INTEGER, type TEXT, data TEXT)"
    )
    db.execute(
        "CREATE TABLE results(game INTEGER PRIMARY KEY, winner TEXT, reason TEXT, turns INTEGER, hp TEXT)"
    )
    db.execute(
        "INSERT INTO series(game,phase,seats,landscapes,health) VALUES(1,'select_deck',?,?,?)",
        (json.dumps(seats), json.dumps(landscapes), health),
    )


def current(db):
    # Previously prepared standalone drafts have no series and remain usable.
    if db.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='series'"
    ).fetchone():
        return db.execute("SELECT * FROM series").fetchone()
    return None


def places_on_turn(series):
    # Series created before interactive placement use their saved pre-battle layouts.
    return (
        series is not None
        and "placement" in series.keys()  # noqa: SIM118 -- sqlite3.Row membership checks values.
        and series["placement"] == "own_turn"
    )


def record(db, game, kind, payload):
    db.execute(
        "INSERT INTO trace(ts,game,type,data) VALUES(?,?,?,?)",
        (time.time(), game, kind, json.dumps(payload, ensure_ascii=False)),
    )


def score(db, seats):
    wins = dict.fromkeys(seats, 0)
    for row in db.execute("SELECT winner, COUNT(*) FROM results GROUP BY winner"):
        wins[row[0]] = row[1]
    return wins


def action_key(game, revision, local):
    return f"{game}/{revision}/{local}"


def public_view(db, series, seat, original, after_event):
    seats = json.loads(series["seats"])
    idx = seats.index(seat)
    original.update(
        game=series["game"],
        phase=series["phase"],
        score=score(db, seats),
        seat=seat,
        seat_index=idx,
        landscape_types=json.loads(series["landscapes"]),
        actions=[],
    )
    last = db.execute("SELECT * FROM results ORDER BY game DESC LIMIT 1").fetchone()
    if last:
        original["last_result"] = {
            "game": last["game"],
            "winner": last["winner"],
            "reason": last["reason"],
        }
    if series["observation"]:
        obs = json.loads(series["observation"])
        original.update(
            turn=obs["turn"],
            stage="landscapes" if obs["turn"] == 0 else "cards",
            hp=obs["hp"],
            board=obs["board"],
            hand=obs["hands"][idx],
            active_player=seats[obs["active"]] if obs["active"] in (0, 1) else None,
        )
        for key in ("mana", "heroes", "cooldowns", "hand_sizes", "deck_sizes"):
            if key in obs:
                original[key] = obs[key]
        if series["phase"] == "battle":
            original["seconds_remaining"] = max(
                0, series["turn_deadline"] - time.time()
            )
            if obs["active"] == idx and series["pending"] is None:
                original["actions"] = [
                    {
                        "id": action_key(series["game"], obs["revision"], a["id"]),
                        "label": a["label"],
                    }
                    for a in obs["actions"]
                ]
    if after_event is not None:
        rows = db.execute(
            "SELECT seq,game,data FROM trace WHERE seq>? AND type='public_events' "
            "ORDER BY seq LIMIT 100",
            (after_event,),
        ).fetchall()
        original["events"] = [
            {"seq": r["seq"], "game": r["game"], "events": json.loads(r["data"])}
            for r in rows
        ]
    elif series["observation"]:
        original["events"] = obs.get("events", [])
    return original


def accept_action(db, seat, action_id, comment=None):
    db.execute("BEGIN IMMEDIATE")
    series = current(db)
    if series is None or series["phase"] != "battle":
        raise ValueError("No battle action is pending.")
    obs = json.loads(series["observation"])
    if json.loads(series["seats"])[obs["active"]] != seat:
        raise ValueError("The other player is choosing an action.")
    if time.time() >= series["turn_deadline"]:
        raise ValueError("The turn deadline has expired.")
    for action in obs["actions"]:
        if action_key(series["game"], obs["revision"], action["id"]) == action_id:
            if series["pending"] == action["id"]:
                return {"accepted": True}
            if series["pending"] is not None:
                raise ValueError("Another action was already accepted for this state.")
            db.execute("UPDATE series SET pending=?", (action["id"],))
            record(
                db,
                series["game"],
                "act",
                {
                    "seat": seat,
                    "turn": obs["turn"],
                    "revision": obs["revision"],
                    "action_id": action_id,
                    "engine_id": action["id"],
                    "label": action["label"],
                    **decision_comment(comment),
                },
            )
            return {"accepted": True}
    raise ValueError("That action is unavailable. Call get_state() for the current actions.")


def validate_snapshot(obs):
    if obs["winner"] not in (-1, 0, 1) or len(obs["hp"]) != 2 or len(obs["hands"]) != 2:
        raise ValueError("Invalid Unity snapshot")
    if obs["winner"] == -1 and (obs["active"] not in (0, 1) or not obs["actions"]):
        raise ValueError("Unity yielded without a decision or winner")
    ids = [a["id"] for a in obs["actions"]]
    if len(ids) != len(set(ids)) or any(not isinstance(x, str) for x in ids):
        raise ValueError("Unity action IDs must be unique strings")
    if any(not isinstance(h, list) for h in obs["hands"]):
        raise ValueError("Invalid Unity hand format")


def publish(db, obs):
    validate_snapshot(obs)
    series = current(db)
    old = json.loads(series["observation"]) if series["observation"] else None
    if old and (obs["revision"] != old["revision"] + 1 or series["pending"] is None):
        raise ValueError("Unexpected Unity revision")
    deadline = series["turn_deadline"]
    if old is None or old["turn"] != obs["turn"] or old["active"] != obs["active"]:
        deadline = time.time() + TURN_SECONDS
    db.execute(
        "UPDATE series SET phase='battle', observation=?, pending=NULL, turn_deadline=?",
        (json.dumps(obs, ensure_ascii=False), deadline),
    )
    record(db, series["game"], "unity_state", {**obs, "turn_deadline": deadline})
    if obs.get("events"):
        record(db, series["game"], "public_events", obs["events"])


def finish(db, winner, reason, turns, hp):
    series = current(db)
    game = series["game"]
    db.execute(
        "INSERT INTO results VALUES(?,?,?,?,?)",
        (game, winner, reason, turns, json.dumps(hp)),
    )
    record(
        db,
        game,
        "game_end",
        {"winner": winner, "reason": reason, "turns": turns, "hp": hp},
    )
    if game == GAME_COUNT:
        db.execute("UPDATE series SET phase='match_over', pending=NULL")
        record(db, game, "match_end", score(db, json.loads(series["seats"])))
    else:
        if places_on_turn(series):
            db.execute("UPDATE players SET hero=NULL,deck=NULL,tiles=NULL")
        else:
            db.execute("UPDATE players SET hero=NULL,deck=NULL,layout=NULL")
        db.execute(
            "UPDATE series SET game=game+1,phase='select_deck',observation=NULL,"
            "pending=NULL,turn_deadline=NULL"
        )
        deadline = time.time() + DECK_SECONDS
        db.execute("UPDATE match SET deadline=?", (deadline,))
        record(db, game + 1, "draft_start", {"deadline": deadline})
