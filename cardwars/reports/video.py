"""Make an MP4 of Unity's game-only frames, with one chapter per completed game."""

# /// script
# requires-python = ">=3.11"
# dependencies = ["imageio-ffmpeg==0.6.0"]
# ///
import argparse
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

import imageio_ffmpeg


def encode(ffmpeg, args):
    subprocess.run(
        [ffmpeg, "-hide_banner", "-loglevel", "error", "-y", *args], check=True
    )


def concat_path(path):
    return "file '" + str(path.resolve()).replace("'", "'\\''") + "'"


def video_seconds(ffmpeg, path):
    result = subprocess.run(
        [
            ffmpeg,
            "-hide_banner",
            "-i",
            str(path),
            "-map",
            "0:v:0",
            "-f",
            "null",
            "-",
            "-progress",
            "pipe:1",
            "-nostats",
            "-loglevel",
            "error",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    return (
        int(
            [s for s in result.stdout.splitlines() if s.startswith("out_time_us=")][
                -1
            ].split("=")[1]
        )
        / 1e6
    )


def render(match, output):
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    results = json.loads((match / "results.json").read_text())
    games = results["games"]
    if len(games) != 5:
        raise ValueError("Expected a completed five-game match")
    seats = results.get("players", list(results["score"]))
    scores = dict.fromkeys(seats, 0)
    with tempfile.TemporaryDirectory(dir=match) as temporary:
        work = Path(temporary)
        segments = []
        chapters = [";FFMETADATA1"]
        elapsed = 0
        for game in games:
            number = game["game"]
            frames = sorted((match / f"game-{number}" / "frames").glob("frame-*.jpg"))
            if len(frames) < 2:
                raise ValueError(f"Missing Game view recording for game {number}")
            timestamps = [int(f.stem.split("-")[1]) for f in frames]
            length = (timestamps[-1] - timestamps[0]) / 1000
            lines = ["ffconcat version 1.0"]
            for idx, frame in enumerate(frames):
                duration = (
                    (timestamps[idx + 1] - timestamps[idx]) / 1000
                    if idx + 1 < len(frames)
                    else 2.8
                )
                lines.extend([concat_path(frame), "option framerate 1000", f"duration {duration:.3f}"])
            lines.extend([concat_path(frames[-1]), "option framerate 1000"])
            timeline = work / f"frames-{number}.txt"
            timeline.write_text("\n".join(lines) + "\n", encoding="utf-8")
            winner = game["winner"]
            scores[winner] += 1
            caption = work / f"score-{number}.txt"
            hp = game["hp"]
            health = f"Health {hp[0]} — {hp[1]}" if len(hp) == 2 else "Technical win"
            caption.write_text(
                f"Game {number} of 5   ·   Winner: {winner}\n"
                f"{health}    Match score {scores[seats[0]]} — {scores[seats[1]]}",
                encoding="utf-8",
            )
            # Use relative safe filenames in drawtext, so user directory punctuation never enters the filter.
            vf = (
                f"fps=30,drawbox=x=0:y=ih/2-44:w=iw:h=88:color=black@0.86:t=fill:enable='gte(t,{length:.3f})',"
                f"drawtext=fontfile='/System/Library/Fonts/Supplemental/Arial.ttf':textfile={caption.name}:"
                f"fontsize=25:fontcolor=white:line_spacing=9:x=(w-text_w)/2:y=(h-text_h)/2:enable='gte(t,{length:.3f})'"
            )
            segment = work / f"game-{number}.mp4"
            folder = match / f"game-{number}"
            if (folder / "mix.f32").is_file():
                start, rate, channels = map(int, (folder / "mix.txt").read_text().split())
                offset = start - timestamps[0]
                sound = ["-f", "f32le", "-ar", str(rate), "-ac", str(channels),
                         "-i", str(folder / "mix.f32")]
                sync = (f"adelay={offset}:all=1" if offset >= 0
                        else f"atrim=start={-offset / 1000:.3f},asetpts=PTS-STARTPTS")
            else:
                sound = ["-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo"]
                sync = "anull"
            command = [
                ffmpeg,
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(timeline),
                *sound,
                "-vf",
                vf,
                "-af", sync + ",apad",
                "-t", f"{length + 2.8:.3f}",
                "-c:a", "aac", "-ar", "48000", "-ac", "2", "-b:a", "160k",
                "-c:v",
                "libx264",
                "-preset",
                "veryfast",
                "-crf",
                "16",
                "-pix_fmt",
                "yuv420p",
                str(segment),
            ]
            subprocess.run(command, cwd=work, check=True)
            end = elapsed + round(video_seconds(ffmpeg, segment) * 1000)
            chapters.extend(
                [
                    "[CHAPTER]",
                    "TIMEBASE=1/1000",
                    f"START={elapsed}",
                    f"END={end}",
                    f"title=Game {number}",
                ]
            )
            elapsed = end
            segments.append(segment)
        playlist = work / "games.txt"
        playlist.write_text("\n".join(map(concat_path, segments)) + "\n")
        metadata = work / "chapters.txt"
        metadata.write_text("\n".join(chapters) + "\n", encoding="utf-8")
        result = work / "match.mp4"
        encode(
            ffmpeg,
            [
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(playlist),
                "-f",
                "ffmetadata",
                "-i",
                str(metadata),
                "-map",
                "0:v",
                "-map",
                "0:a",
                "-map_metadata",
                "1",
                "-map_chapters",
                "1",
                "-c",
                "copy",
                "-movflags",
                "+faststart",
                str(result),
            ],
        )
        shutil.copyfile(result, output)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("match", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    render(args.match.resolve(), args.output.resolve())
