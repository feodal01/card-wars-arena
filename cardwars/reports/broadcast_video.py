"""Export the five-game spectator broadcast directly from recorded Unity frames."""

import argparse
import bisect
import json
import os
import re
import shutil
import subprocess
import tempfile
from contextlib import ExitStack
from dataclasses import dataclass
from pathlib import Path

import imageio_ffmpeg

from .broadcast import HERE, broadcast_html, match_graphics
from .display import display_label, display_names
from .video import concat_path, encode

FPS = 30


@dataclass
class Shot:
    key: str
    frames: int
    start: float | None = None
    event: int | None = None


def timeline(number, events, seats, names, photos):
    scenes, shots = [], []

    def slide(kind, seconds, index=0):
        key = f"{number}-{kind}-{index}"
        scenes.append(dict(key=key, program=dict(g=number, kind=kind, index=index)))
        shots.append(Shot(key, round(FPS * seconds)))

    if number == 1:
        slide("intro", 3)
    slide("game", 1.8)
    slide("draft", 1.4)
    decks = [e for e in events if e["type"] == "submit_deck"]
    for index in range(1, len(decks) + 1):
        slide("draft", 5 if index == 1 else 7, index)

    states = {e["data"]["revision"]: e for e in events if e["type"] == "unity_state"}
    actions = [e for e in events if e["type"] == "act"]
    if states:
        if len(photos) < 2:
            raise ValueError(f"Missing recorded battlefield for game {number}")
        slide("fight", 1.2)
        start, last = photos[0] / 1000, photos[-1] / 1000
        end = min(states[0]["ts"] + 0.85, actions[0]["ts"] if actions else last, last)
        key = f"{number}-draw"
        shots.append(Shot(key, max(1, round((end - start) * FPS)), start))
        scenes.append(dict(key=key, game=number))
        focus = quote = None
        for i, e in enumerate(actions):
            d = e["data"]
            key = f"{number}-act-{e['seq']}"
            card = re.match(r"(?:Play|Cast) ((?:Creature|Spell|Building)_\w+)", d["label"])
            action = dict(player=seats.index(d["seat"]), turn=d["turn"],
                          label=display_label(d["label"], names), comment=d.get("comment", ""))
            if card:
                focus = dict(card=card[1])
            if action["comment"]:
                quote = action
            scenes.append(dict(key=key, game=number, action=action, focus=focus, quote=quote))
            next_state = states.get(d["revision"] + 1)
            next_action = actions[i + 1]["ts"] if i + 1 < len(actions) else last
            end = min(next_state["ts"] + 0.85 if next_state else last, next_action, last)
            shots.append(Shot(key, max(1, round((end - e["ts"]) * FPS)), e["ts"], e["seq"]))
    slide("result", 5)
    if number == 5:
        slide("final", 6)
    return scenes, shots


def write_mix(folder, shots, output):
    with ExitStack() as stack:
        mix = None
        rate, channels = 48000, 2
        if (folder / "mix.f32").is_file():
            base, rate, channels = map(int, (folder / "mix.txt").read_text().split())
            mix = stack.enter_context((folder / "mix.f32").open("rb"))
        dest = stack.enter_context(output.open("wb"))
        count = 0
        for shot in shots:
            samples = round((count + shot.frames) * rate / FPS) - round(count * rate / FPS)
            count += shot.frames
            remaining = samples * channels * 4
            if mix and shot.start is not None:
                offset = round((shot.start - base / 1000) * rate)
                leading = min(samples, max(0, -offset)) * channels * 4
                dest.write(bytes(leading))
                remaining -= leading
                mix.seek(max(0, offset) * channels * 4)
                chunk = mix.read(remaining)
                dest.write(chunk)
                remaining -= len(chunk)
            dest.write(bytes(remaining))
    return rate, channels


def render_game(ffmpeg, folder, work, number, stamps, shots):
    plate_list = work / f"plates-{number}.txt"
    entries = []
    for shot in shots:
        entries.extend([concat_path(work / (shot.key + ".png")), "option framerate 1000",
                        f"duration {shot.frames / FPS:.9f}"])
    entries.extend([concat_path(work / (shots[-1].key + ".png")), "option framerate 1000"])
    plate_list.write_text("ffconcat version 1.0\n" + "\n".join(entries) + "\n")
    mix = work / f"mix-{number}.f32"
    rate, channels = write_mix(folder, shots, mix)
    frames = sum(shot.frames for shot in shots)
    out = work / f"game-{number}.mp4"
    inputs = ["-f", "concat", "-safe", "0", "-i", str(plate_list),
              "-f", "f32le", "-ar", str(rate), "-ac", str(channels), "-i", str(mix)]
    opts = ["-t", f"{frames / FPS:.9f}", "-map", "1:a", "-ar", "48000", "-ac", "2",
            "-c:a", "aac", "-b:a", "160k", "-c:v", "libx264", "-threads", "4",
            "-preset", "veryfast", "-crf", "16", "-pix_fmt", "yuv420p", str(out)]
    battlefield = [shot for shot in shots if shot.start is not None]
    if battlefield:
        first = shots.index(battlefield[0])
        before = sum(shot.frames for shot in shots[:first])
        battle = sum(shot.frames for shot in battlefield)
        vf = (f"[0:v]fps={FPS},tpad=stop_mode=clone:stop_duration=1[bg];"
              f"[2:v]scale=1434:762:flags=lanczos,setsar=1[field];"
              f"[bg][field]overlay=36:140:enable='between(n,{before},{before+battle-1})'[v]")
        cmd = [ffmpeg, "-nostdin", "-loglevel", "error", "-y", *inputs, "-f", "image2pipe",
               "-framerate", str(FPS), "-vcodec", "mjpeg", "-i", "pipe:0",
               "-filter_complex", vf, "-map", "[v]", *opts]
        with subprocess.Popen(cmd, stdin=subprocess.PIPE) as proc:
            previous = None
            try:
                for shot in shots:
                    for i in range(shot.frames):
                        stamp = stamps[0]
                        if shot.start is not None:
                            when = 1000 * (shot.start + i / FPS)
                            stamp = stamps[max(0, bisect.bisect_right(stamps, when) - 1)]
                        if stamp != previous:
                            jpeg = (folder / "frames" / f"frame-{stamp}.jpg").read_bytes()
                            previous = stamp
                        proc.stdin.write(jpeg)
            finally:
                proc.stdin.close()
            if proc.wait():
                raise RuntimeError(f"Could not encode game {number}")
    else:
        encode(ffmpeg, [*inputs, "-vf", f"fps={FPS}", "-map", "0:v", *opts])
    mix.unlink()
    return out


def render(match, project, output):
    events = [json.loads(s) for s in (match / "trace.jsonl").read_text().splitlines()]
    data = match_graphics(match / "trace.jsonl", project)
    meta = events[0]["data"]
    names = display_names(meta["catalog"])
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    chrome = os.getenv("CARDWARS_CHROME") or shutil.which("google-chrome") or "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    with tempfile.TemporaryDirectory(dir=output.parent) as tmp:
        work = Path(tmp)
        (work / "broadcast.html").write_text(broadcast_html(data))
        plans, scenes = [], []
        for number in range(1, 6):
            folder = match / f"game-{number}"
            stamps = sorted(int(p.stem[6:]) for p in (folder / "frames").glob("frame-*.jpg"))
            slides, shots = timeline(number, [e for e in events if e["game"] == number], meta["seats"], names, stamps)
            plans.append((number, folder, stamps, shots))
            scenes.extend(slides)
        (work / "scenes.json").write_text(json.dumps(scenes))
        subprocess.run(["node", str(HERE / "capture_plates.js"), str(work), chrome], check=True)
        parts, chapters = [], [";FFMETADATA1"]
        cursor = 0
        cues = []
        for number, folder, stamps, shots in plans:
            print(f"Encoding game {number}", flush=True)
            clip = render_game(ffmpeg, folder, work, number, stamps, shots)
            start = cursor
            actions = []
            for shot in shots:
                if shot.event is not None:
                    actions.append(dict(trace_seq=shot.event, frame=cursor))
                cursor += shot.frames
            cues.append(dict(game=number, start_frame=start, end_frame=cursor, actions=actions))
            chapters.extend(["[CHAPTER]", f"TIMEBASE=1/{FPS}", f"START={start}", f"END={cursor}", f"title=Game {number}"])
            parts.extend([concat_path(clip), f"duration {(cursor-start)/FPS:.9f}"])
        (work / "chapters.txt").write_text("\n".join(chapters) + "\n")
        (work / "parts.txt").write_text("ffconcat version 1.0\n" + "\n".join(parts) + "\n")
        final = work / "match.mp4"
        encode(ffmpeg, ["-f", "concat", "-safe", "0", "-i", str(work / "parts.txt"), "-f", "ffmetadata",
                        "-i", str(work / "chapters.txt"), "-map", "0:v", "-map", "0:a", "-map_chapters", "1",
                        "-c", "copy", "-movflags", "+faststart", str(final)])
        final.replace(output)
        output.with_suffix(".cues.json").write_text(json.dumps(dict(video=output.name, fps=FPS, frames=cursor,
                                                                  chapters=cues), indent=2) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("match", type=Path)
    parser.add_argument("project", type=Path)
    parser.add_argument("output", type=Path)
    a = parser.parse_args()
    render(a.match.resolve(), a.project.resolve(), a.output.resolve())
