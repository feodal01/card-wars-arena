"""Organizer-only live match page, generated from committed trace events and public CLI messages."""

import base64
import hashlib
import json
import sqlite3
import sys
import threading
import webbrowser
from contextlib import closing, contextmanager
from dataclasses import dataclass, field
from html import escape
from pathlib import Path

from cardwars.arena.matchplay import GAME_COUNT
from cardwars.commentary import PRIVATE_TEXT
from cardwars.reports.display import display_label, display_names

TRACE_TYPES = (
    "match_start",
    "draft_start",
    "submit_deck",
    "opening",
    "act",
    "game_end",
    "match_end",
    "public_events",
    "run_interrupted",
    "run_resumed",
)
FORMATS = {"codex", "claude", "opencode", "prime", "arena"}
MAX_LINE = 512 * 1024
REFRESH = "setInterval(() => { if (!location.hash) location.reload(); }, 2000);"
SCRIPT_HASH = base64.b64encode(hashlib.sha256(REFRESH.encode()).digest()).decode()


def public_messages(fmt, event, *, codex_summaries=False):
    """Accept only completed assistant text from the configured stdout format."""
    if not isinstance(event, dict):
        return []
    kind = event.get("type")
    texts = []
    if fmt == "arena" and kind == "arena.message":
        texts = [event.get("text")]
    elif fmt == "codex" and kind == "item.completed":
        item = event.get("item")
        if isinstance(item, dict) and item.get("type") == "agent_message":
            texts = [item.get("text")]
        elif codex_summaries and isinstance(item, dict) and item.get("type") == "reasoning":
            # Codex exec's JSON mapper populates this item from Reasoning.summary only.
            summary = item.get("text")
            if isinstance(summary, str) and summary.strip():
                texts = ["Codex summary · " + summary.strip()]
    elif fmt == "opencode" and kind == "text":
        part = event.get("part")
        if (
            isinstance(part, dict)
            and part.get("type") == "text"
            and not part.get("synthetic")
            and not part.get("ignored")
        ):
            texts = [part.get("text")]
    elif (fmt, kind) in (("claude", "assistant"), ("prime", "message_end")):
        msg = event.get("message")
        if (
            isinstance(msg, dict)
            and msg.get("role") == "assistant"
            and isinstance(msg.get("content"), list)
            and not event.get("parent_tool_use_id")
        ):
            texts = [
                p.get("text")
                for p in msg["content"]
                if isinstance(p, dict) and p.get("type") == "text"
            ]
    return [
        t.strip()
        for t in texts
        if isinstance(t, str) and t.strip() and not PRIVATE_TEXT.search(t)
    ]


@dataclass
class SeatStream:
    path: Path
    fmt: str
    offset: int = 0
    skipping: bool = False
    codex_summaries: bool = False

    def read(self):
        if not self.path.exists():
            return
        with self.path.open("rb") as stream:
            stream.seek(self.offset)
            # Never buffer a whole tool response, or consume a partial JSON line as a new event.
            while line := stream.readline(MAX_LINE):
                complete = line.endswith(b"\n")
                if not complete and len(line) < MAX_LINE:
                    break
                self.offset = stream.tell()
                if self.skipping or not complete:
                    self.skipping = not complete
                    continue
                try:
                    event = json.loads(line)
                except (ValueError, RecursionError):
                    continue
                yield from public_messages(self.fmt, event, codex_summaries=self.codex_summaries)


@dataclass
class Game:
    phase: str = "Deck selection"
    decks: dict = field(default_factory=dict)
    actions: list = field(default_factory=list)
    winner: str | None = None


class LivePage:
    def __init__(self, directory):
        self.directory = Path(directory)
        self.file = self.directory / ".operator" / "live.html"
        self.file.parent.mkdir(mode=0o700, exist_ok=True)
        self.sequence = 0
        self.names = {}
        self.health = None
        self.catalog = {}
        self.streams = {}
        self.games = {}
        self.messages = []
        self.ended = False
        self.interrupted = False
        self.style = Path(__file__).with_name("live.css").read_text(encoding="utf-8")

    def event(self, number, kind, data):
        game = self.games.setdefault(number, Game())
        if kind in ("submit_deck", "act") and data.get("comment"):
            stage = "deck selection" if kind == "submit_deck" else (
                f"turn {data['turn']}" if data["turn"] else "landscape placement"
            )
            self.messages.append((data["seat"], f"Game {number} · {stage} — {data['comment']}"))
        if kind == "match_start":
            seats = data["seats"]
            names = data.get("display_names", {})
            self.health = data.get("health")
            identities = data.get("identities", {})
            self.names = {s: names.get(s) or identities.get(s) or s for s in seats}
            self.catalog = display_names(data.get("catalog", ""))
            for seat in seats:
                profile = data.get("player_profiles", {}).get(seat, {})
                fmt = profile.get("trace_format")
                if fmt in FORMATS:
                    self.streams[seat] = SeatStream(
                        self.directory / f"{seat}.events.jsonl", fmt,
                        codex_summaries=profile.get("reasoning_summary_format") == "codex_exec",
                    )
        elif kind == "submit_deck":
            game.decks[data["seat"]] = (data["hero"], data["cards"])
            if len(game.decks) == 2:
                game.phase = "Loading Unity"
        elif kind in ("opening", "run_resumed"):
            game.phase = "Loading Unity"
            self.interrupted = False
        elif kind == "public_events":
            game.phase = "In play"
        elif kind == "act":
            game.phase = "In play"
            game.actions.append((data["seat"], data["turn"], display_label(data["label"], self.catalog)))
        elif kind == "game_end":
            game.winner = data["winner"]
            game.phase = "Game complete"
        elif kind == "match_end":
            self.ended = True
        elif kind == "run_interrupted":
            self.interrupted = True
            if game.winner is None:
                game.phase = "Game interrupted"

    def update(self, final=False):
        uri = (self.directory / "match.sqlite").resolve().as_uri() + "?mode=ro"
        marks = ",".join("?" for _ in TRACE_TYPES)
        with closing(sqlite3.connect(uri, uri=True)) as db:
            rows = db.execute(
                f"SELECT seq,game,type,data FROM trace WHERE seq>? AND type IN ({marks}) ORDER BY seq",
                (self.sequence, *TRACE_TYPES),
            ).fetchall()
        for sequence, number, kind, raw in rows:
            self.event(number, kind, json.loads(raw))
            self.sequence = sequence
        count = len(self.messages)
        for seat, stream in self.streams.items():
            self.messages.extend((seat, msg) for msg in stream.read())
        if rows or count != len(self.messages) or final:
            tmp = self.file.with_suffix(".tmp")
            tmp.write_text(self.render(final), encoding="utf-8", errors="replace")
            tmp.replace(self.file)

    def roster(self, seat, game):
        name = escape(self.names[seat])
        roster = game.decks.get(seat)
        if roster is None:
            contents = '<p class="muted">Waiting for a hero and 20 cards.</p>'
        else:
            hero, cards = roster
            hero_name = escape(self.catalog.get(hero, hero))
            items = "".join(f"<li>{escape(self.catalog.get(c, c))}</li>" for c in cards)
            contents = f'<h4>{hero_name}</h4><p class="muted">Hero · Cards in deck: {len(cards)}</p><ol>{items}</ol>'
        return f'<article class="roster"><h3>{name}</h3>{contents}</article>'

    def game_view(self, number, game):
        phase = game.phase
        if game.winner is not None:
            phase = "Winner · " + self.names.get(game.winner, game.winner)
        feed = "".join(
            f"<li><small>{escape(self.names[seat])} · "
            f"{'Landscape placement' if turn == 0 else f'Turn {int(turn)}'}</small>{escape(label)}</li>"
            for seat, turn, label in reversed(game.actions)
        )
        rosters = "".join(self.roster(seat, game) for seat in self.names)
        actions = (
            f'<div class="actions"><h3>Player actions</h3><ul class="feed">{feed}</ul></div>'
            if feed
            else ""
        )
        return (
            f'<section class="game" id="game-{number}"><header><h2>Game {number}</h2>'
            f'<b>{escape(phase)}</b></header>{actions}<div class="decks">{rosters}</div></section>'
        )

    def render(self, final):
        current = max(self.games)
        state = self.games[current].phase
        if self.ended:
            state = "Match complete"
        elif self.interrupted or final:
            state = "Match interrupted"
        reload = "" if final else f"<script>{REFRESH}</script>"
        score = "".join(
            f"<div><span>{escape(name)}</span><strong>{sum(g.winner == seat for g in self.games.values())}</strong></div>"
            for seat, name in self.names.items()
        )
        nav = "".join(f'<a href="#game-{n}">{n}</a>' for n in self.games)
        games = "".join(self.game_view(n, g) for n, g in self.games.items())
        messages = "".join(
            f"<li><small>{escape(self.names[s])}</small>{escape(text)}</li>"
            for s, text in reversed(self.messages)
        )
        empty = (
            "No public messages were recorded."
            if final
            else "No public messages yet."
        )
        match_format = (
            f" · Starting HP: {self.health}" if type(self.health) is int else ""
        )
        follow = "#" if final else "./live.html"
        feed = (
            f'<ul class="feed">{messages}</ul>'
            if messages
            else f'<p class="muted">{empty}</p>'
        )
        return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; script-src 'sha256-{SCRIPT_HASH}'; base-uri 'none'; form-action 'none'">
<meta name="viewport" content="width=device-width,initial-scale=1">{reload}
<title>Card Wars · Match</title><style>{self.style}</style></head><body>
<main><div class="mast"><h1>Card Wars</h1><div>{escape(state)}<br><small>Game {current} of {GAME_COUNT}{match_format}</small></div></div>
<div class="score">{score}</div><nav aria-label="Select game"><span>Games</span>{nav}<a href="{follow}">Current game</a></nav>
<div class="columns"><div class="games">{games}</div><aside><h2>Public messages</h2>{feed}</aside></div></main></body></html>"""


@contextmanager
def live_view(directory, *, open_browser=True, interval=0.75):
    """Enter after match_start commits and before spawning players. Yield the local page path."""
    page = LivePage(directory)
    page.update()
    stop = threading.Event()

    def poll():
        while not stop.wait(interval):
            try:
                page.update()
            except sqlite3.OperationalError as error:
                if getattr(error, "sqlite_errorcode", None) not in (
                    sqlite3.SQLITE_BUSY,
                    sqlite3.SQLITE_LOCKED,
                ):
                    raise

    thread = threading.Thread(target=poll, name="cardwars-spectator", daemon=True)
    thread.start()
    try:
        print(f"Spectator page: {page.file}", flush=True)
        if open_browser:
            try:
                webbrowser.open_new(page.file.resolve().as_uri())
            except webbrowser.Error as error:
                print(f"Open the spectator page manually: {error}", file=sys.stderr)
        yield page.file
    finally:
        stop.set()
        thread.join()
        page.update(final=True)
