"""Verify archived match evidence, local documentation links and optional media."""

import argparse
import hashlib
import json
import re
from pathlib import Path
from urllib.parse import unquote, urlsplit

from cardwars.tournament.evidence import read_match

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def check_links():
    pages = [ROOT / "README.md", *(ROOT / "docs").rglob("*.md"),
             *(ROOT / "materials").rglob("*.md"), *(ROOT / "results").rglob("*.md")]
    for page in pages:
        for link in re.findall(r"\]\(([^)\s]+)\)", page.read_text()):
            parsed = urlsplit(link)
            if not parsed.scheme and parsed.path:
                target = (page.parent / unquote(parsed.path)).resolve()
                if not target.is_relative_to(ROOT) or not target.exists():
                    raise ValueError(f"Broken link in {page.relative_to(ROOT)}: {link}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--media", action="store_true", help="Hash the downloaded Git LFS files")
    args = parser.parse_args()
    check_links()
    materials = ROOT / "materials"
    media = json.loads((materials / "manifest.json").read_text())
    count = 0
    archive = ROOT / "results"
    traces = {p.parent for p in archive.rglob("trace.jsonl")}
    summaries = {p.parent for p in archive.rglob("results.json")}
    if not traces or traces != summaries:
        raise ValueError("Each archived match requires both a trace and a score.")
    for directory in sorted(traces):
        match = read_match(directory)
        if not (directory / "trace.html").is_file():
            raise ValueError(f"Missing offline replay for {directory.name}")
        cues = directory / "broadcast-cues.json"
        if cues.exists():
            cue = json.loads(cues.read_text())
            video = f"recordings/{directory.name}/{cue['video']}"
            if cue["trace_sha256"] != match.trace_hash or cue["sha256"] != media[video]["sha256"]:
                raise ValueError(f"Video, cue sheet and trace disagree for {directory.name}")
        print(f"{directory.relative_to(ROOT)}  {match.wins[0]}–{match.wins[1]}")
        count += 1
    for name, info in media.items():
        path = materials / name
        if not path.is_file():
            raise ValueError(f"Missing material: {name}")
        if args.media and (path.stat().st_size != info["bytes"] or digest(path) != info["sha256"]):
            raise ValueError(f"Media checksum mismatch: {name}. Run git lfs pull first.")
    print(f"Verified {count} five-game matches and local links.")
    if args.media:
        print(f"Verified {len(media)} media files against their SHA-256 checksums.")


if __name__ == "__main__":
    main()
