# Recordings and offline deck workshop

The [illustrated deck workshop](deck-workshop.html) runs offline. Download the HTML file, open it in a browser, and export a hero and 20 cards as JSON. Import the JSON at the human player’s table before starting a match.

| Match | Video | Match evidence |
|---|---|---|
| Human vs. Terra | [Five games · 22:39](recordings/2026-11-10-human-terra/broadcast.mp4) | [Game-by-game results](../results/2026-11-10-human-terra/README.md) |
| Terra vs. campaign AI | [Five games · 16:04](recordings/2026-11-09-terra-campaign-mirror/broadcast.mp4) | [Analysis](../results/2026-11-09-terra-campaign-mirror/review.md) |
| Terra vs. Astra | [Five games · 17:35](recordings/2026-11-08-terra-astra-medium/broadcast.mp4) | [Analysis](../results/2026-11-08-terra-astra-medium/review.md) |
| Terra vs. Opus | [Remastered replay · 18:23](recordings/2026-11-08-terra-opus-medium/broadcast-replay.mp4) · [Original broadcast](recordings/2026-11-08-terra-opus-medium/broadcast.mp4) · [16-second sample](recordings/2026-11-08-terra-opus-medium/broadcast-preview.mp4) | [Analysis and remaster provenance](../results/2026-11-08-terra-opus-medium/review.md) |

Git LFS stores these files at their original quality. After cloning, run `git lfs pull` to fetch all media, or fetch only the files for the human match:

```sh
git lfs pull --include="materials/recordings/2026-11-10-human-terra/*"
```

The [media manifest](manifest.json) lists each file’s size in bytes and SHA-256 digest. From the repository root, `uv run --locked python scripts/check_release.py --media` verifies the downloads against the archived matches.

The illustrations, character names and original game audio are from Adventure Time Card Wars. The arena uses them in the workshop and recordings. The game’s Unity project and native asset archives are supplied separately by the operator.

The README features the Adventure Time Card Wars sword emblem. [Artwork source · Wallpapers.com](https://wallpapers.com/png/adventure-time-card-wars-logo-7d1rdgz9ujzywiyr.html)
