import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from cardwars.arena import matchplay
from cardwars.reports.live import (
    MAX_LINE,
    LivePage,
    SeatStream,
    live_view,
    public_messages,
)


class LiveSpectatorTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.directory = Path(tmp.name)
        self.db = sqlite3.connect(self.directory / "match.sqlite")
        self.addCleanup(self.db.close)
        with self.db:
            matchplay.create(self.db, ["alpha", "beta"], [], 100)
            matchplay.record(
                self.db,
                1,
                "match_start",
                {
                    "seats": ["alpha", "beta"],
                    "display_names": {"alpha": "Luna 6 max", "beta": "Luna 6.1 low"},
                    "catalog": "- `leader` Finn — Hero.\n- `card` Steel Fist — Creature.\n",
                    "player_profiles": {
                        "alpha": {"trace_format": "codex"},
                        "beta": {"trace_format": "arena"},
                    },
                },
            )
            matchplay.record(self.db, 1, "draft_start", {})
        self.page = LivePage(self.directory)

    def record(self, game, kind, value):
        with self.db:
            matchplay.record(self.db, game, kind, value)
        self.page.update()
        return self.page.file.read_text()

    def test_draft_five_games_and_final_score(self):
        self.page.update()
        html = self.page.file.read_text()
        self.assertEqual(html.count("Waiting for a hero"), 2)
        for game in range(1, 6):
            self.record(game, "draft_start", {})
            for seat in ("alpha", "beta"):
                html = self.record(
                    game,
                    "submit_deck",
                    {
                        "seat": seat,
                        "hero": "leader",
                        "cards": ["card", f"unique-{game}-{seat}"],
                    },
                )
                self.assertIn("Finn", html)
                self.assertIn("Steel Fist", html)
                self.assertIn(f"unique-{game}-{seat}", html)
                self.assertEqual(html.count("Waiting for a hero"), int(seat == "alpha"))
            self.record(
                game, "act", {"seat": "beta", "turn": 2, "label": f"Summon G{game}"}
            )
            self.record(game, "game_end", {"winner": "beta"})
        self.record(5, "match_end", {"beta": 5, "alpha": 0})
        self.page.update(final=True)
        html = self.page.file.read_text()
        for game in range(1, 6):
            self.assertIn(f'id="game-{game}"', html)
            self.assertIn(f"Summon G{game}", html)
        self.assertIn("Match complete", html)
        self.assertIn("Luna 6.1 low</span><strong>5", html)
        self.assertNotIn("location.reload()", html)

    def test_context_keeps_interrupted_page_and_only_selected_public_text(self):
        with (
            patch("webbrowser.open_new") as opener,
            self.assertRaises(KeyboardInterrupt),
            live_view(self.directory, interval=100) as page,
        ):
            opener.assert_called_once_with(page.resolve().as_uri())
            self.assertEqual(page.parent.name, ".operator")
            self.assertIn("Deck selection", page.read_text())
            (self.directory / "alpha.log").write_text("stderr-sentinel")
            (self.directory / "alpha.events.jsonl").write_text(
                json.dumps(
                    {
                        "type": "item.completed",
                        "item": {"type": "reasoning", "text": "private-sentinel"},
                    }
                )
                + "\n"
                + json.dumps(
                    {
                        "type": "item.completed",
                        "item": {
                            "type": "agent_message",
                            "text": "<script>public</script>",
                        },
                    }
                )
                + "\n"
            )
            (self.directory / "beta.events.jsonl").write_text(
                '{"type":"arena.message","text":"Hello from beta"}\n'
            )
            with self.db:
                matchplay.record(self.db, 1, "run_interrupted", "secret error detail")
            raise KeyboardInterrupt
        html = page.read_text()
        self.assertIn("Match interrupted", html)
        self.assertIn("&lt;script&gt;public&lt;/script&gt;", html)
        self.assertIn("Hello from beta", html)
        for private in ("stderr-sentinel", "private-sentinel", "secret error detail"):
            self.assertNotIn(private, html)
        self.assertNotIn("location.reload()", html)
        with closing(sqlite3.connect(self.directory / "match.sqlite")) as db:
            self.assertEqual(db.execute("SELECT count(*) FROM trace").fetchone()[0], 3)

    def test_codex_summary_requires_trusted_exec_format_and_completed_event(self):
        event = {"type": "item.completed", "item": {"type": "reasoning", "text": "Brief summary."}}
        self.assertEqual(public_messages("codex", event), [])
        self.assertEqual(public_messages("codex", event, codex_summaries=True), ["Codex summary · Brief summary."])
        for kind in ("item.started", "item.updated"):
            self.assertEqual(public_messages("codex", event | {"type": kind}, codex_summaries=True), [])
        event["item"] = {"type": "reasoning", "text": "<think>private"}
        self.assertEqual(public_messages("codex", event, codex_summaries=True), [])

    def test_filters_schemas_and_reassembles_complete_jsonl(self):
        payload = {
            "role": "assistant",
            "content": [
                {"type": "thinking", "thinking": "secret"},
                {"type": "tool_use", "text": "not public"},
                {"type": "text", "text": "public"},
                {"type": "text", "text": "<think>secret"},
            ],
        }
        for fmt, kind in (("claude", "assistant"), ("prime", "message_end")):
            self.assertEqual(
                public_messages(fmt, {"type": kind, "message": payload}), ["public"]
            )
            self.assertEqual(
                public_messages(fmt, {"type": "tool_result", "message": payload}), []
            )
        self.assertEqual(
            public_messages(
                "opencode", {"type": "text", "part": {"type": "text", "text": "move"}}
            ),
            ["move"],
        )
        self.assertEqual(
            public_messages(
                "opencode",
                {"type": "reasoning", "part": {"type": "text", "text": "hidden"}},
            ),
            [],
        )
        self.assertEqual(
            public_messages(
                "arena", {"type": "arena.message", "text": "Bearer " + "x" * 24}
            ),
            [],
        )
        path = self.directory / "split"
        stream = SeatStream(path, "arena")
        path.write_bytes(
            b"x" * MAX_LINE + b"\n" + b'{"type":"arena.message","text":"pu'
        )
        self.assertEqual(list(stream.read()), [])
        with path.open("ab") as writer:
            writer.write(b'blic"}\n')
        self.assertEqual(list(stream.read()), ["public"])
        self.assertEqual(list(stream.read()), [])


if __name__ == "__main__":
    unittest.main()
