"""Render a Card Wars operator trace as one self-contained offline HTML file."""

import argparse
import json
import math
from importlib.resources import files
from pathlib import Path

from .display import trace_display


def _integer(value):
    number = int(value)
    return number if abs(number) <= 2**53 - 1 else value


def _float(value):
    result = float(value)
    if not math.isfinite(result):
        raise ValueError("number is outside the supported range")
    return result


def _invalid_number(value):
    raise ValueError(f"invalid JSON number {value}")


def _load_trace(path):
    events = []
    diagnostics = []
    with path.open(encoding="utf-8-sig", errors="replace") as stream:
        for line_number, line in enumerate(stream, 1):
            if not line.strip():
                continue
            try:
                event = json.loads(
                    line,
                    parse_int=_integer,
                    parse_float=_float,
                    parse_constant=_invalid_number,
                )
                if not isinstance(event, dict) or not isinstance(
                    event.get("type"), str
                ):
                    raise TypeError("expected an event object with a type")
            except (TypeError, ValueError) as exc:
                diagnostics.append(f"Line {line_number}: {exc}")
                continue
            events.append(event)
    return {"source": path.name, "events": events, "diagnostics": diagnostics, "display": trace_display(events)}


def render_trace(trace_path: Path, output: Path) -> Path:
    """Read JSONL in recorded order. Embed event data without executable markup."""
    trace_path, output = Path(trace_path), Path(output)
    if trace_path.resolve() == output.resolve():
        raise ValueError("Output must differ from the source trace")
    payload = json.dumps(
        _load_trace(trace_path), ensure_ascii=True, separators=(",", ":")
    )
    payload = (
        payload.replace("&", r"\u0026").replace("<", r"\u003c").replace(">", r"\u003e")
    )
    resources = files("cardwars.reports")
    page = resources.joinpath("trace.html").read_text(encoding="utf-8")
    for marker, name in (
        ("/* TRACE_STYLE */", "trace.css"),
        ("/* TRACE_SCRIPT */", "trace.js"),
    ):
        asset = resources.joinpath(name).read_text(encoding="utf-8")
        if name == "trace.js":
            asset = (
                resources.joinpath("trace_detail.js").read_text(encoding="utf-8")
                + "\n"
                + asset
            )
        page = page.replace(marker, asset)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(page.replace("TRACE_PAYLOAD", payload), encoding="utf-8")
    return output


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("trace", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    render_trace(args.trace, args.output)


if __name__ == "__main__":
    main()
