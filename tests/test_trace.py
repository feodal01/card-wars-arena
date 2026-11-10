import json
import os
import tempfile
import unittest
from pathlib import Path

from cardwars.reports.archive_labels import generate
from cardwars.reports.trace import main, render_trace


def embedded(page):
    section = page.split('id="trace-data" type="application/json">', 1)[1]
    return json.loads(section.split("</script>", 1)[0])


class TraceReportTests(unittest.TestCase):
    def test_partial_trace_preserves_order_and_safe_payload(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            source = folder / "trace.jsonl"
            output = folder / "nested" / "trace.html"
            unsafe = "</ScRiPt><img src=x onerror=alert(1)> & необычное имя"
            first = {
                "type": "match_start",
                "game": 1,
                "seq": 1,
                "data": {"seed": 2**63, "seats": [unsafe, "B"]},
            }
            timeout = {
                "type": "timeout",
                "game": 1,
                "data": {"seat": unsafe, "observed_at": 30},
            }
            source.write_text(
                json.dumps(first) + "\n" + json.dumps(timeout) + '\n{"type":',
                encoding="utf-8",
            )
            main([str(source), "--output", str(output)])
            page = output.read_text(encoding="utf-8")
            data = embedded(page)
            self.assertEqual(
                data["events"][0]["data"], {"seed": str(2**63), "seats": [unsafe, "B"]}
            )
            self.assertEqual(data["events"][1], timeout)
            self.assertIn("Line 3", data["diagnostics"][0])
            self.assertNotIn("<img src=x", page)
            self.assertNotIn("<script src=", page)
            self.assertNotIn("TRACE_PAYLOAD", page)

    @unittest.skipUnless(os.environ.get("CARDWARS_UNITY_PROJECT"), "requires Unity localization")
    def test_packaged_archive_labels_match_unity(self):
        project = Path(os.environ["CARDWARS_UNITY_PROJECT"])
        root = Path(__file__).resolve().parents[1]
        saved = (root / "cardwars/reports/assets/english.json").read_text("utf-8")
        self.assertEqual(generate(project), saved)

    def test_archived_names_and_action_labels_are_display_only(self):
        root = Path(__file__).resolve().parents[1]
        source = root / "results/2026-11-08-terra-sonnet-medium/trace.jsonl"
        with tempfile.TemporaryDirectory() as temp:
            data = embedded(render_trace(source, Path(temp) / "trace.html").read_text())
        original = "Коснись существа, чтобы атаковать! (seat 0, lane 0)"
        self.assertEqual(data["display"]["names"]["Building_BlueCastle"], "Astral Fortress")
        self.assertEqual(data["display"]["labels"][original], "Tap a creature to attack! (seat 0, lane 1)")
        event = next(e for e in data["events"] if e["seq"] == 50)
        self.assertEqual(event["data"]["label"], original)
        self.assertEqual(event["data"]["engine_id"], "target:0")

    def test_unknown_event_and_unsupported_numeric_value(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "trace.jsonl"
            path.write_text(
                '{"type":"future","data":42}\n{"type":"bad","ts":1e9999}\n[]\n',
                encoding="utf-8",
            )
            out = render_trace(path, path.with_suffix(".html"))
            data = embedded(out.read_text(encoding="utf-8"))
            self.assertEqual(data["events"], [{"type": "future", "data": 42}])
            self.assertEqual(len(data["diagnostics"]), 2)
            with self.assertRaises(ValueError):
                render_trace(path, path)

    def test_historical_traces_can_open_without_results_or_unity(self):
        root = Path(__file__).resolve().parents[1]
        for name in ("2026-11-05-random-match", "2026-11-05-landscape-turns"):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temp:
                source = root / "results" / name / "trace.jsonl"
                out = render_trace(source, Path(temp) / "trace.html")
                data = embedded(out.read_text(encoding="utf-8"))
                self.assertFalse(data["diagnostics"])
                self.assertEqual(data["events"][-1]["type"], "match_end")
                self.assertEqual(
                    len(data["events"]),
                    len(source.read_text(encoding="utf-8").splitlines()),
                )
