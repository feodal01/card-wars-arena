"""Spectator explanations survive accepted retries and remain outside seat observations."""

import asyncio
import json
import sys
import unittest
from contextlib import closing
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from cardwars.arena import draft, matchplay, runner
from cardwars.commentary import decision_comment
from cardwars.reports.live import LivePage
from cardwars.reports.trace import render_trace
from tests.test_trace import embedded


async def call_twice(path, tool, args, caption):
    server = StdioServerParameters(command=sys.executable,
        args=["-m", "cardwars.tools.mcp_server", str(path), "alpha"])
    async with stdio_client(server) as (reader, writer), ClientSession(reader, writer) as client:
        await client.initialize()
        for attempt in range(2):
            response = await client.call_tool(tool, args | {"comment": caption.format(attempt)})
            assert not response.isError, response.content


class DecisionCommentsTest(unittest.TestCase):
    def test_accepted_draft_and_move_are_captioned_once_for_spectators(self):
        seats = ["alpha", "beta"]
        cards = [f"card-{i}" for i in range(20)]
        catalog = ("catalog", cards, ["hero"], dict.fromkeys(cards, "Corn"))
        with TemporaryDirectory() as tmp, patch.object(draft, "make_catalog", return_value=catalog):
            path = Path(tmp) / "match"
            draft.prepare(Path(tmp), path, 1, seats)
            with closing(draft.connect(path)) as db:
                with db:
                    matchplay.create(db, seats, [], 100)
                    matchplay.record(db, 1, "match_start", {"seats": seats, "seed": 1})
                draft.start(path)
                asyncio.run(call_twice(path, "submit_deck", {"hero_id": "hero", "card_ids": cards, "game": 1}, "Plan {}."))
                with db:
                    matchplay.publish(db, {
                        "active": 0, "turn": 1, "revision": 0, "winner": -1,
                        "hp": [100, 100], "board": [], "hands": [[], []],
                        "actions": [{"id": "end", "label": "End turn"}],
                    })
                asyncio.run(call_twice(path, "act", {"action_id": "1/0/end"}, "Move <{}>."))
                runner.write_results(db, path)
                self.assertEqual(
                    [json.loads(r[0])["comment"] for r in db.execute(
                        "SELECT data FROM trace WHERE type IN ('submit_deck','act') ORDER BY seq"
                    )], ["Plan 0.", "Move <0>."],
                )
            other = json.dumps(draft.state(path, "beta", after_event=0), ensure_ascii=False)
            self.assertNotIn("Plan 0", other)
            self.assertNotIn("Move <0>", other)
            report = render_trace(path / "trace.jsonl", path / "trace.html")
            events = embedded(report.read_text())["events"]
            self.assertEqual([e["data"]["comment"] for e in events if e["type"] in ("act", "submit_deck")], ["Plan 0.", "Move <0>."])
            page = LivePage(path)
            page.update()
            html = page.file.read_text()
            self.assertIn("Game 1 · deck selection — Plan 0.", html)
            self.assertIn("Game 1 · turn 1 — Move &lt;0&gt;.", html)

    def test_only_short_public_text_is_stored(self):
        self.assertEqual(decision_comment("<think>private</think>"), {})
        self.assertEqual(decision_comment(None), {})
        self.assertEqual(decision_comment("   "), {})
        self.assertEqual(decision_comment("x" * 401), {"comment": "x" * 400})
