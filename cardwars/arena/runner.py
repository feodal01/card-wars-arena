"""Drive Unity and two configured player processes through one five-game match."""

import fcntl
import json
import os
import random
import secrets
import signal
import subprocess
import sys
import time
import uuid
from contextlib import ExitStack, closing, contextmanager
from pathlib import Path

from cardwars.players.identity import public_profile
from cardwars.players.launch import launch_command
from cardwars.tools.broker import seat_socket

from . import draft as arena
from . import matchplay
from .landscapes import TYPES

INSTALLER = Path(__file__).resolve().parents[1] / "engine" / "unity" / "install.py"


def atomic_json(path, value):
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
    temporary.replace(path)


@contextmanager
def process(command, log, *, events_path=None, **kwargs):
    with ExitStack() as files:
        log_stream = files.enter_context(log.open("a", encoding="utf-8"))
        stdout = (
            files.enter_context(events_path.open("a", encoding="utf-8"))
            if events_path else log_stream
        )
        child = subprocess.Popen(
            command,
            stdin=subprocess.DEVNULL,
            stdout=stdout,
            stderr=log_stream,
            start_new_session=True,
            **kwargs,
        )
        try:
            yield child
        finally:
            if child.poll() is None:
                os.killpg(child.pid, signal.SIGTERM)
                try:
                    child.wait(timeout=8)
                except subprocess.TimeoutExpired:
                    os.killpg(child.pid, signal.SIGKILL)
                    child.wait()


def check_clients(players):
    for seat, client in players.items():
        if client is not None and client.poll() is not None:
            raise RuntimeError(
                f"{seat} exited before match completion ({client.returncode})"
            )


def draft(db, players, campaign=None):
    while True:
        check_clients(players)
        with db:
            db.execute("BEGIN IMMEDIATE")
            rosters = []
            on_turn = matchplay.places_on_turn(matchplay.current(db))
            if campaign:
                source = db.execute("SELECT hero,deck,tiles FROM players WHERE seat!=?", (campaign,)).fetchone()
                if source["deck"]:
                    copied = db.execute("UPDATE players SET hero=?,deck=?,tiles=? WHERE seat=? AND deck IS NULL",
                                        (*source, campaign))
                    if copied.rowcount:
                        matchplay.record(db, matchplay.current(db)["game"], "submit_deck", {
                            "seat": campaign, "hero": source["hero"], "cards": json.loads(source["deck"]),
                            "required_landscapes": json.loads(source["tiles"])})
            for seat in players:
                player = db.execute(
                    "SELECT * FROM players WHERE seat=?", (seat,)
                ).fetchone()
                if player["deck"]:
                    rosters.append(
                        {
                            "seat": seat,
                            "hero": player["hero"],
                            "cards": json.loads(player["deck"]),
                            (
                                "required_landscapes" if on_turn else "landscapes"
                            ): json.loads(
                                player["tiles"] if on_turn else player["layout"]
                            ),
                        }
                    )
            if len(rosters) == 2:
                db.execute("UPDATE series SET phase='loading'")
                return rosters
            deadline = db.execute("SELECT deadline FROM match").fetchone()[0]
            now = time.time()
            if now >= deadline:
                if not rosters:
                    raise RuntimeError(
                        "Both players missed the deck deadline; no sporting winner can be assigned"
                    )
                loser = next(s for s in players if s != rosters[0]["seat"])
                matchplay.record(
                    db,
                    matchplay.current(db)["game"],
                    "timeout",
                    {
                        "seat": loser,
                        "deadline": deadline,
                        "observed_at": now,
                        "phase": "select_deck",
                    },
                )
                matchplay.finish(db, rosters[0]["seat"], "deck_timeout", 0, [])
                return None
        time.sleep(0.06)


def play_battle(directory, unity, project, db, opening, players, watch):
    seats = tuple(players)
    config = directory / "opening.json"
    atomic_json(config, opening)
    env = dict(
        os.environ,
        CARD_WARS_OPENING=str(config),
        CARD_WARS_BATTLE="1",
        CARD_WARS_VIEW_SEAT=str(opening.get("view_seat", -1)),
        CARD_WARS_WATCH="1" if watch else "0",
    )
    mode = [] if watch else ["-batchmode"]
    with process(
        [
            str(unity),
            *mode,
            "-projectPath",
            str(project),
            "-buildTarget",
            "StandaloneOSX",
            "-logFile",
            str(directory / "unity.log"),
            "-executeMethod",
            "ArenaOpening.Run",
        ],
        directory / "engine.log",
        env=env,
    ) as engine:
        path = directory / "state.json"
        revision = None
        sent = None
        engine_deadline = time.monotonic() + 210
        while True:
            check_clients(players)
            if path.exists():
                obs = json.loads(path.read_text(encoding="utf-8"))
                if obs["revision"] != revision:
                    with db:
                        db.execute("BEGIN IMMEDIATE")
                        matchplay.publish(db, obs)
                    if obs["winner"] == -1 and obs["active"] == 1 and opening.get("campaign_opponent"):
                        key = matchplay.action_key(opening["game"], obs["revision"], obs["campaign_action"])
                        with db:
                            matchplay.accept_action(db, seats[1], key)
                    revision = obs["revision"]
                    if obs["winner"] != -1:
                        code = engine.wait(timeout=45)
                        if code != 0:
                            winner = obs["winner"]
                            if (winner not in (0, 1) or len(obs["hp"]) != 2 or
                                    obs["hp"][winner] <= 0 or obs["hp"][1 - winner] > 0 or obs["actions"]):
                                raise RuntimeError("Unity exited with an invalid terminal snapshot")
                            print(f"Unity exited with code {code} after publishing the terminal snapshot",
                                  file=sys.stderr, flush=True)
                        return seats[obs["winner"]], "health", obs["turn"], obs["hp"]
                    engine_deadline = None
            if engine.poll() is not None:
                raise RuntimeError(
                    f"Unity exited without a terminal snapshot (code {engine.returncode}): {directory}"
                )
            if engine_deadline and time.monotonic() > engine_deadline:
                raise TimeoutError(
                    f"Unity failed to produce the next decision: {directory}"
                )
            with db:
                db.execute("BEGIN IMMEDIATE")
                series = matchplay.current(db)
                if revision is not None and series["pending"] is not None:
                    if sent != revision:
                        atomic_json(
                            directory / f"action-{revision}.json",
                            {"id": series["pending"]},
                        )
                        sent = revision
                        engine_deadline = time.monotonic() + 90
                elif revision is not None and time.time() >= series["turn_deadline"]:
                    matchplay.record(
                        db,
                        series["game"],
                        "timeout",
                        {
                            "seat": seats[obs["active"]],
                            "deadline": series["turn_deadline"],
                            "observed_at": time.time(),
                            "phase": "battle",
                        },
                    )
                    return (
                        seats[1 - obs["active"]],
                        "turn_timeout",
                        obs["turn"],
                        obs["hp"],
                    )
            time.sleep(0.035)


def write_results(db, directory):
    meta = json.loads(
        db.execute("SELECT data FROM trace WHERE type='match_start'").fetchone()[0]
    )
    seats = meta["seats"]
    path = directory / "trace.jsonl"
    temporary = directory / "trace.jsonl.tmp"
    with temporary.open("w", encoding="utf-8") as trace:
        for row in db.execute("SELECT * FROM trace ORDER BY seq"):
            event = {**dict(row), "data": json.loads(row["data"])}
            trace.write(
                json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n"
            )
    temporary.replace(path)
    games = []
    for row in db.execute("SELECT * FROM results ORDER BY game"):
        game = row["game"]
        count = db.execute(
            "SELECT COUNT(*) FROM trace WHERE game=? AND type='act'", (game,)
        ).fetchone()[0]
        opening = db.execute(
            "SELECT data FROM trace WHERE game=? AND type='opening'", (game,)
        ).fetchone()
        games.append(
            {
                "game": game,
                "winner": row["winner"],
                "reason": row["reason"],
                "turns": row["turns"],
                "hp": json.loads(row["hp"]),
                "actions": count,
                "first": seats[json.loads(opening["data"])["first"]]
                if opening
                else None,
            }
        )
    atomic_json(
        directory / "results.json",
        {
            "score": matchplay.score(db, seats),
            "games": games,
            "players": seats,
            "complete": len(games) == matchplay.GAME_COUNT,
            "seed": meta["seed"],
            **{
                key: meta[key]
                for key in ("match_id", "ruleset", "identities", "display_names", "player_profiles")
                if key in meta
            },
        },
    )


def recover_opening(directory, seats, identities, ruleset):
    """Only replay a locked opening if no battle decision has ever been published."""
    with closing(arena.connect(directory)) as db, db:
        db.execute("BEGIN IMMEDIATE")
        series = matchplay.current(db)
        tail = db.execute("SELECT type FROM trace ORDER BY seq DESC LIMIT 1").fetchone()
        if (
            not series
            or series["phase"] != "loading"
            or series["observation"]
            or not tail
            or tail[0] != "run_interrupted"
        ):
            raise ValueError("Only an interrupted loading phase can be resumed.")
        game = series["game"]
        meta = json.loads(
            db.execute("SELECT data FROM trace WHERE type='match_start'").fetchone()[0]
        )
        if (
            list(seats) != meta["seats"]
            or meta.get("identities") != identities
            or meta.get("ruleset") != ruleset
        ):
            raise ValueError(
                "The players or rules differ from the saved match."
            )
        start_rng = random.Random(meta["seed"])
        for _ in meta["seats"]:
            start_rng.getrandbits(63)
        openings = db.execute(
            "SELECT data FROM trace WHERE type='opening' ORDER BY seq"
        ).fetchall()
        for (data,) in openings:
            opening = json.loads(data)
            if [start_rng.randrange(2), start_rng.randrange(2**31)] != [
                opening["first"],
                opening["seed"],
            ]:
                raise ValueError("Stored opening differs from its seeded draw")
        if opening["game"] != game:
            raise ValueError("Missing locked opening")
        last = directory / f"game-{game}"
        if (last / "state.json").exists() or list(last.glob("action-*.json")):
            raise ValueError(
                "Native state already published. Recovery requires replay verification."
            )
        attempt = (
            db.execute(
                "SELECT COUNT(*) FROM trace WHERE type='run_resumed' AND game=?",
                (game,),
            ).fetchone()[0]
            + 1
        )
        last.rename(directory / f"game-{game}-startup-{attempt}")
        retry_rng = random.Random(f"{meta['seed']}:resume:{game}:{attempt}")
        client_seeds = [retry_rng.getrandbits(63) for _ in seats]
        matchplay.record(
            db,
            game,
            "run_resumed",
            {
                "game": game,
                "reason": "retry_same_opening",
                "player_seeds": client_seeds,
            },
        )
    return start_rng, meta["health"], client_seeds, opening


def run(config, directory, seats=None, seed=None, resume=False, *, human_deck=None):
    """A Unity project can be patched/opened by only one match host at a time."""
    settings = config.project / "ProjectSettings/ProjectSettings.asset"
    if "companyName: CardWarsArena" not in settings.read_text():
        raise ValueError(
            "Use the isolated CardWarsArena Unity project, not the original game"
        )
    lockfile = config.project / "CardWarsArena.host.lock"
    with lockfile.open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise ValueError(
                f"The project is already in use by another match: {config.project}"
            ) from error
        return _run_locked(config, directory, seats, seed, resume, human_deck)


def _run_locked(config, directory, seats, seed, resume, human_deck=None):
    directory = Path(directory).resolve()
    project, unity, health = config.project, config.executable, config.health
    watch, record = config.watch or config.record, config.record
    seats = tuple(seats or config.match_players)
    if (
        len(seats) != 2
        or seats[0] == seats[1]
        or any(s not in config.players for s in seats)
    ):
        raise ValueError("A match requires two distinct registered seats.")
    humans = [s for s in seats if config.players[s]["kind"] == "human"]
    if humans and (len(humans) != 1 or human_deck is None):
        raise ValueError("Use cardwars duel to start a match from the human player’s table.")
    identities = {s: config.players[s]["rating_id"] for s in seats}
    campaign_seats = [s for s in seats if config.players[s]["kind"] == "campaign"]
    if campaign_seats and (campaign_seats != [seats[1]] or config.placement != "before_cards"):
        raise ValueError("Use the campaign AI in the second seat with before_cards placement.")
    campaign = seats[1] if campaign_seats else None
    ruleset = config.ruleset
    if campaign and "campaign-mirror" not in ruleset:
        ruleset = "campaign-mirror-" + ruleset
    profiles = {seat: public_profile(config.players[seat]) for seat in seats}
    names = {seat: p["display_name"] for seat, p in profiles.items()}
    if not unity.is_file():
        raise ValueError(f"Unity executable missing: {unity}")
    subprocess.run([sys.executable, str(INSTALLER), str(project)], check=True)
    locked = None
    if resume and any(config.players[s]["kind"] != "random" for s in seats):
        raise ValueError(
            "External harnesses require a continuous session. Keep this incomplete run and start a new match."
        )
    if resume:
        rng, health, player_seeds, locked = recover_opening(
            directory, seats, identities, config.ruleset
        )
    else:
        if seed is None:
            seed = config.seed if config.seed is not None else secrets.randbits(63)
        rng = random.Random(seed)
        arena.prepare(project, directory, seed, seats=seats, pool_mode=config.pool_mode, health=health,
                      placement=config.placement, campaign=bool(campaign))
        player_seeds = [rng.getrandbits(63) for _ in seats]
    if record:
        (directory / "record-frames").touch()
    with ExitStack() as stack:
        db = stack.enter_context(closing(arena.connect(directory)))
        for seat in seats:
            if seat != campaign and seat not in humans:
                stack.enter_context(seat_socket(directory, seat))
        commands = {
            seat: None if seat == campaign or seat in humans else launch_command(config.players[seat], directory, seat, s)
            for seat, s in zip(seats, player_seeds)
        }
        if not resume:
            with db:
                matchplay.create(db, seats, TYPES, health)
                source = db.execute(
                    "SELECT cards,heroes,catalog,factions FROM match"
                ).fetchone()
                matchplay.record(
                    db,
                    1,
                    "match_start",
                    {
                        "seed": seed,
                        "seats": seats,
                        "match_id": str(uuid.uuid4()),
                        "ruleset": ruleset,
                        "identities": identities,
                        "display_names": names,
                        "player_profiles": profiles,
                        "player_kinds": {s: config.players[s]["kind"] for s in seats},
                        "deck_seconds": arena.DECK_SECONDS,
                        "turn_seconds": matchplay.TURN_SECONDS,
                        "player_seeds": player_seeds,
                        "landscape_selection": "before_cards" if config.placement == "before_cards" else "on_turn",
                        "landscape_types": TYPES,
                        "card_factions": json.loads(source["factions"]),
                        "health": health,
                        "pool_mode": config.pool_mode,
                        "pool": json.loads(source["cards"]),
                        "heroes": json.loads(source["heroes"]),
                        "catalog": source["catalog"],
                    },
                )
                deadline = time.time() + arena.DECK_SECONDS
                db.execute("UPDATE match SET deadline=?", (deadline,))
                matchplay.record(db, 1, "draft_start", {"deadline": deadline})
        try:
            if humans:
                arena.submit(directory, humans[0], human_deck["hero_id"], human_deck["card_ids"], game=1)
            if watch and not humans:
                from cardwars.reports.live import live_view

                stack.enter_context(live_view(directory, open_browser=not record))
                if record:
                    from cardwars.reports.on_air import broadcast_view

                    stack.enter_context(broadcast_view(directory, project))
            players = {
                seat: None if cmd is None else stack.enter_context(
                    process(
                        cmd, directory / f"{seat}.log", cwd=directory / seat,
                        events_path=directory / f"{seat}.events.jsonl"
                        if profiles[seat]["trace_format"] != "none" else None,
                    )
                )
                for seat, cmd in commands.items()
            }
            begin = locked["game"] if locked else 1
            for game in range(begin, matchplay.GAME_COUNT + 1):
                opening = locked
                locked = None
                if opening is None:
                    rosters = draft(db, players, campaign) if campaign else draft(db, players)
                    if rosters:
                        first = rng.randrange(2)
                        opening = {
                            "game": game,
                            "players": rosters,
                            "display_names": [names[s] for s in seats],
                            "health": health,
                            "draw": first,
                            "first": first,
                            "seed": rng.randrange(2**31),
                            "battle": True,
                        }
                        if humans and record:
                            opening["view_seat"] = seats.index(humans[0])
                        if campaign:
                            opening["campaign_opponent"] = True
                        if "required_landscapes" in rosters[0]:
                            opening["landscape_placement"] = config.placement
                        with db:
                            matchplay.record(db, game, "opening", opening)
                if opening:
                    game_dir = directory / f"game-{game}"
                    game_dir.mkdir()
                    print(
                        f"Game {game}: Unity loading, first seat {seats[opening['first']]}",
                        flush=True,
                    )
                    outcome = play_battle(
                        game_dir, unity, project, db, opening, players, watch
                    )
                    with db:
                        matchplay.finish(db, *outcome)
                write_results(db, directory)
                print(f"Game {game} finished: {matchplay.score(db, seats)}", flush=True)
        except BaseException as error:
            series = matchplay.current(db)
            if series["phase"] != "match_over":
                with db:
                    matchplay.record(db, series["game"], "run_interrupted", str(error))
            write_results(db, directory)
            raise

        # Participants get time to read match_over. A slow final CLI response
        # cannot alter the outcome already recorded by the host.
        deadline = time.monotonic() + 15
        for seat, player in players.items():
            if player is None:
                continue
            try:
                code = player.wait(timeout=max(0, deadline - time.monotonic()))
            except subprocess.TimeoutExpired:
                print(f"{seat}: closing the session after the match", file=sys.stderr)
            else:
                if code:
                    print(
                        f"{seat}: exit code {code} after the match",
                        file=sys.stderr,
                    )
