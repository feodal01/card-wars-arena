"""A loopback player seat and a standalone illustrated deck workshop."""

import json
import multiprocessing
import os
import re
import secrets
import shutil
import signal
import threading
import traceback
import webbrowser
from contextlib import closing
from dataclasses import replace
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from cardwars.arena import draft, matchplay
from cardwars.arena.catalog import make_catalog
from cardwars.arena.runner import run
from cardwars.reports.broadcast import card_graphics, hero_graphics, player
from cardwars.reports.display import display_label, display_names
from cardwars.reports.trace import render_trace
from cardwars.players.identity import public_profile

HERE = Path(__file__).parent


def catalog_data(project, seed, pool):
    catalog, cards, heroes, factions = make_catalog(project, seed, pool)
    names = display_names(catalog)
    descriptions = dict(re.findall(r"^- `([^`]+)` .*? — (.+)$", catalog, re.M))
    items = card_graphics(project, {"catalog": catalog, "card_factions": factions}, names, cards)
    portraits, atlases = hero_graphics(project / "Assets", heroes)
    for key in cards:
        items[key]["description"] = descriptions[key]
    for key in heroes:
        items[key] = dict(name=names[key], type="Hero", description=descriptions[key], **portraits[key])
    factions_path = project / "Assets/StreamingAssets/Blueprints/db_Faction.json"
    colors = {row["FactionID"]: f"rgb({row['CardFrameColor'] or row['FactionColor']})"
              for row in json.loads(factions_path.read_text())}
    return {"items": items, "atlases": atlases, "colors": colors}, names


def page(data, table=False):
    def source(name):
        return (HERE / name).read_text(encoding="utf-8")

    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("<", r"\u003c")
    return (source("table.html").replace("{{CSS}}", source("table.css"))
            .replace("{{MODE}}", "table" if table else "workshop")
            .replace("{{TITLE}}", "Your table" if table else "Deck workshop")
            .replace("{{JS}}", source("table.js")).replace("{{DATA}}", payload)).encode()


def roster(value, items):
    hero, cards = value.get("hero_id"), value.get("card_ids")
    if not isinstance(hero, str) or items.get(hero, {}).get("type") != "Hero":
        raise ValueError("Choose one hero from this catalog.")
    if not isinstance(cards, list) or len(cards) != 20 or not all(isinstance(c, str) for c in cards):
        raise ValueError("Choose exactly 20 cards.")
    if len(set(cards)) != 20 or any(c not in items or items[c]["type"] == "Hero" for c in cards):
        raise ValueError("Choose 20 distinct cards from this catalog.")
    return {"hero_id": hero, "card_ids": cards}


def play(config, directory, seats, deck, errors):
    try:
        run(config, directory, seats, human_deck=deck)
        render_trace(directory / "trace.jsonl", directory / "trace.html")
        if config.record:
            from cardwars.reports.broadcast_video import render

            try:
                render(directory, config.project, directory / "broadcast.mp4")
            except Exception as exc:
                traceback.print_exc()
                (directory / "video-error.txt").write_text(str(exc))
    except Exception as exc:
        traceback.print_exc()
        errors.send(str(exc))
    finally:
        errors.close()


class Table:
    def __init__(self, config, opponent, directory, data, names):
        self.config = config
        self.seats = ("human", opponent)
        self.directory = directory
        self.items = data["items"]
        self.names = names
        self.child = self.errors = self.error = None
        self.lock = threading.Lock()

    def start(self, deck, record):
        with self.lock:
            if self.child is not None or self.directory.exists():
                raise ValueError("This match has already started.")
            if type(record) is not bool:
                raise ValueError("Record match video must be checked or unchecked.")
            if record:
                from importlib.util import find_spec

                if find_spec("imageio_ffmpeg") is None:
                    raise ValueError("To record, launch the table with uv run --extra video cardwars duel.")
            self.config = replace(self.config, record=record)
            ctx = multiprocessing.get_context("spawn")
            self.errors, writer = ctx.Pipe(duplex=False)
            self.child = ctx.Process(target=play, args=(self.config, self.directory, self.seats, deck, writer))
            self.child.start()
            writer.close()

    def state(self, after):
        with self.lock:
            if self.child is None:
                return {"phase": "lobby"}
            if not self.error and self.errors.poll():
                try:
                    self.error = self.errors.recv()
                except EOFError:
                    pass
            if self.error:
                return {"phase": "error", "message": self.error}
            ended = self.child.exitcode is not None
        if (self.directory / "match.sqlite").exists():
            state = draft.state(self.directory, "human", after_event=after)
            if "seat_index" in state and (not ended or state["phase"] == "match_over"):
                state.pop("catalog", None)
                for a in state["actions"]:
                    a["label"] = display_label(a["label"], self.names)
                for group in state["events"]:
                    group["events"] = [display_label(e, self.names) for e in group["events"]]
                if state["phase"] == "match_over":
                    state["replay_ready"] = (self.directory / "trace.html").is_file()
                    if self.config.record:
                        error = self.directory / "video-error.txt"
                        state["video"] = ("ready" if (self.directory / "broadcast.mp4").is_file()
                                          else "failed" if error.is_file() else "encoding")
                return state
        if ended:
            return {"phase": "error", "message": "The match host stopped. Check the run directory."}
        return {"phase": "starting"}

    def post(self, route, value):
        if route == "start":
            self.start(roster(value, self.items), value.get("record", True))
        elif not (self.directory / "match.sqlite").is_file():
            raise ValueError("Start the match from the deck workshop first.")
        elif route == "draft":
            deck = roster(value, self.items)
            draft.submit(self.directory, "human", deck["hero_id"], deck["card_ids"], game=value.get("game"))
        elif route == "act":
            with closing(draft.connect(self.directory)) as db, db:
                matchplay.accept_action(db, "human", value.get("action_id"))
        else:
            raise ValueError("Unknown request.")
        return {"accepted": True}

    def close(self):
        if self.child and self.child.is_alive():
            os.kill(self.child.pid, signal.SIGINT)
            self.child.join()


def serve_table(config, opponent, directory, workshop):
    if config.players.get("human", {}).get("kind") != "human" or opponent not in config.players or opponent == "human":
        raise ValueError("Configure a human seat and a registered opponent.")
    directory = directory.resolve()
    if directory.exists():
        raise ValueError(f"Choose a new run directory: {directory}")
    seed = config.seed if config.seed is not None else secrets.randbits(63)
    # Only the private player browser is opened. A spectator window reveals both hands.
    config = replace(config, seed=seed, watch=False)
    data, names = catalog_data(config.project, seed, config.pool_mode)
    profile = player(opponent, public_profile(config.players[opponent]))
    data.update(opponent=profile["name"], effort=profile["effort"], health=config.health,
                rules=(HERE.parent / "arena" / "rules.md").read_text())
    offline = page(data)
    workshop.parent.mkdir(parents=True, exist_ok=True)
    workshop.write_bytes(offline)
    html = page(data, table=True)
    table = Table(config, opponent, directory, data, names)
    prefix = "/" + secrets.token_urlsafe(24) + "/"

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def send(self, content, mime, status=200):
            self.send_response(status)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Length", str(len(content)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(content)

        def reply(self, data, status=200):
            self.send(json.dumps(data).encode(), "application/json", status)

        def do_GET(self):
            route, _, query = self.path.partition("?")
            if route == prefix:
                self.send(html, "text/html; charset=utf-8")
            elif route == prefix + "replay" and (directory / "trace.html").is_file():
                self.send((directory / "trace.html").read_bytes(), "text/html; charset=utf-8")
            elif route == prefix + "video" and (directory / "broadcast.mp4").is_file():
                with (directory / "broadcast.mp4").open("rb") as video:
                    self.send_response(200)
                    self.send_header("Content-Type", "video/mp4")
                    self.send_header("Content-Length", str(os.fstat(video.fileno()).st_size))
                    self.send_header("Content-Disposition", 'attachment; filename="broadcast.mp4"')
                    self.end_headers()
                    shutil.copyfileobj(video, self.wfile)
            elif route == prefix + "workshop.html":
                self.send(offline, "text/html; charset=utf-8")
            elif route == prefix + "state" and re.fullmatch(r"\d{0,14}", query):
                self.reply(table.state(int(query or 0)))
            else:
                self.send_error(404)

        def do_POST(self):
            route = self.path.removeprefix(prefix)
            if self.path != prefix + route or route not in ("start", "draft", "act"):
                return self.send_error(404)
            if self.headers.get("Origin") != origin or self.headers.get_content_type() != "application/json":
                return self.send_error(403)
            try:
                size = int(self.headers.get("Content-Length", "0"))
                if not 0 < size <= 8192:
                    raise ValueError("Invalid request size.")
                body = json.loads(self.rfile.read(size))
                if not isinstance(body, dict):
                    raise ValueError("Expected a JSON object.")
                self.reply(table.post(route, body))
            except (ValueError, OSError) as error:
                self.reply({"error": str(error)}, 400)

    with ThreadingHTTPServer(("127.0.0.1", 0), Handler) as server:
        origin = f"http://127.0.0.1:{server.server_port}"
        url = origin + prefix
        print(f"Player table: {url}\nOffline workshop: {workshop.resolve()}\nMatch output: {directory}", flush=True)
        webbrowser.open(url)
        try:
            server.serve_forever()
        finally:
            table.close()
