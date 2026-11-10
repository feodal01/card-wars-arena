"""Local broadcast with a persistent multipart stream of Unity's native frames."""

import json
import re
import secrets
import sqlite3
import threading
import time
import webbrowser
from contextlib import closing, contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit, parse_qs

from .broadcast import HERE, broadcast_html, card_graphics, data_uri, hero_graphics, player
from .display import display_label, display_names


class Program:
    def __init__(self, directory, project):
        self.directory = Path(directory)
        self.database = (self.directory / "match.sqlite").resolve().as_uri() + "?mode=ro"
        with closing(sqlite3.connect(self.database, uri=True)) as db:
            start = json.loads(db.execute("SELECT data FROM trace WHERE type='match_start'").fetchone()[0])
        self.seats = start["seats"]
        self.names = display_names(start["catalog"])
        portraits, atlases = hero_graphics(project / "Assets", set(start["heroes"]))
        data = dict(
            cards=card_graphics(project, start, self.names, start["pool"]),
            players=[player(s, start["player_profiles"][s]) for s in self.seats],
            games=[dict(number=n, before=[0, 0], decks=[], plays=[], placements=[], hp=[]) for n in range(1, 6)],
            portraits=portraits, atlases=atlases, health=start["health"], pool=len(start["pool"]),
            logos={p: data_uri(HERE / f"assets/{p}.svg", "image/svg+xml") for p in ("openai", "claude")},
        )
        self.html = broadcast_html(data, (HERE / "on_air.js").read_text()).encode()

    def events(self, after):
        projected = []
        with closing(sqlite3.connect(self.database, uri=True)) as db:
            rows = db.execute(
                "SELECT seq, ts, game, type, data FROM trace WHERE seq>? AND type IN "
                "('draft_start','submit_deck','act','game_end','match_end','unity_state','run_interrupted') "
                "ORDER BY seq", (after,)
            )
            for seq, ts, game, kind, raw in rows:
                d = json.loads(raw)
                if kind == "submit_deck":
                    d = dict(player=self.seats.index(d["seat"]), heroId=d["hero"], hero=self.names[d["hero"]],
                             cards=d["cards"], comment=d.get("comment", ""))
                elif kind == "act":
                    focus = re.search(r"^(?:Play|Cast) ((?:Creature|Building|Spell)_\w+)", d["label"])
                    d = dict(player=self.seats.index(d["seat"]), turn=d["turn"], label=display_label(d["label"], self.names),
                             card=focus[1] if focus else None, comment=d.get("comment", ""))
                elif kind == "unity_state":
                    d = dict(hp=d["hp"], turn=d["turn"])
                elif kind == "game_end":
                    d["winner"] = self.seats.index(d["winner"])
                projected.append([seq, ts, game, kind, d])
            n = db.execute("SELECT game FROM series").fetchone()[0]
        marker = self.directory / f"game-{n}" / "frame.latest"
        return {"rows": projected, "feed": n if marker.is_file() else None}


@contextmanager
def broadcast_view(directory, project, open_browser=True):
    program = Program(directory, project)
    prefix = "/" + secrets.token_urlsafe(24) + "/"
    stop = threading.Event()
    terminal_delivered = threading.Event()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            url = urlsplit(self.path)
            if not url.path.startswith(prefix):
                self.send_error(404)
                return
            route = url.path[len(prefix):]
            try:
                if route == "":
                    self.send_bytes(program.html, "text/html; charset=utf-8")
                elif route == "events":
                    cursor = int(parse_qs(url.query).get("after", ["0"])[0])
                    payload = program.events(cursor)
                    self.send_bytes(json.dumps(payload).encode(), "application/json")
                    if any(row[3] in {"match_end", "run_interrupted"} for row in payload["rows"]):
                        terminal_delivered.set()
                elif m := re.fullmatch(r"game-([1-5])[.]mjpg", route):
                    self.stream_game(program.directory / f"game-{m[1]}")
                else:
                    self.send_error(404)
            except (BrokenPipeError, ConnectionResetError, TimeoutError):
                pass
            except ValueError:
                self.send_error(400)

        def send_bytes(self, data, mime):
            self.send_response(200)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)

        def stream_game(self, folder):
            self.connection.settimeout(4)
            self.send_response(200)
            self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=cwframe")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            last = ""
            unchanged = time.monotonic()
            while not stop.is_set():
                try:
                    stamp = (folder / "frame.latest").read_text().strip()
                    if stamp.isdigit() and stamp != last:
                        frame = (folder / "frames" / f"frame-{stamp}.jpg").read_bytes()
                        self.wfile.write(f"--cwframe\r\nContent-Type: image/jpeg\r\nContent-Length: {len(frame)}\r\n\r\n".encode())
                        self.wfile.write(frame)
                        self.wfile.write(b"\r\n")
                        last = stamp
                        unchanged = time.monotonic()
                except FileNotFoundError:
                    pass
                if time.monotonic() - unchanged > 12:
                    # A suspended editor may resume on the same game after a long
                    # pause. Keep its connection; retire feeds from finished games.
                    with closing(sqlite3.connect(program.database, uri=True)) as db:
                        game, phase = db.execute("SELECT game, phase FROM series").fetchone()
                    if folder.name != f"game-{game}" or phase == "match_over":
                        break
                    unchanged = time.monotonic()
                stop.wait(.008)

        def log_message(self, *args):
            pass

    with ThreadingHTTPServer(("127.0.0.1", 0), Handler) as server:
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        url = f"http://127.0.0.1:{server.server_port}{prefix}?clean"
        try:
            print(f"Broadcast: {url}", flush=True)
            if open_browser:
                webbrowser.open_new(url)
            yield url
        finally:
            # Let an open viewer receive the last committed result before shutdown.
            terminal_delivered.wait(timeout=.75)
            stop.set()
            server.shutdown()
            thread.join()
