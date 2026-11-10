# Match archive

Each row links to a completed five-game match. Download a `trace.html` and open it locally to inspect the draft, hands, legal moves, comments and combat outcomes. The adjacent `trace.jsonl` contains the host events and `results.json` records the score. The [media collection](../materials/README.md) holds the recordings and illustrated workshop.

## Matches for the article

| Match | Score in listed order | Context |
|---|---:|---|
| [Human vs. Terra 6.1 medium](2026-11-10-human-terra/README.md) | 4–1 | Human browser table against Codex. [Replay](2026-11-10-human-terra/trace.html) |
| [Terra 6.1 vs. the original campaign AI](2026-11-09-terra-campaign-mirror/review.md) | 5–0 | The original AI received the same hero and 20 cards as Terra before every game. [Replay](2026-11-09-terra-campaign-mirror/trace.html) |
| [Terra 6.1 vs. Astra 6](2026-11-08-terra-astra-medium/review.md) | 4–1 | Both agents used Codex at medium effort. [Replay](2026-11-08-terra-astra-medium/trace.html) |
| [Terra 6.1 vs. Opus 5.5](2026-11-08-terra-opus-medium/review.md) | 4–1 | Codex vs. Claude Code, both at medium effort. The review documents recovery of the final result. [Replay](2026-11-08-terra-opus-medium/trace.html) |
| [Terra 6.1 vs. Sonnet 5.5, English rematch](2026-11-08-terra-sonnet-en-rematch/review.md) | 4–1 | Corrected English ability descriptions. [Replay](2026-11-08-terra-sonnet-en-rematch/trace.html) |
| [Terra 6.1 vs. Sonnet 5.5, first match](2026-11-08-terra-sonnet-medium/review.md) | 5–0 | The catalog misdescribed enhanced Princess Cookie. [Replay](2026-11-08-terra-sonnet-medium/trace.html) |
| [Astra vs. Opus, early rules](2026-11-06-astra-claude/review.md) | 3–2 | 25 HP and a 40-card pool. [Replay](2026-11-06-astra-claude/trace.html) |

The games in a row share one match session and an opportunity to adapt between games. Each row is one match observation for rating purposes. Compare pool size, hero health, catalog version and participant configuration before combining scores. The [rating guide](../docs/rating.md) describes the scheduled league.

## Baselines and historical fixtures

- [100 HP random baseline](2026-11-10-random-baseline/trace.html) ran on a freshly prepared engine with seed 42. Uniform random lost 2–3 to play-first. [Exact configuration](2026-11-10-random-baseline/match.toml)
- Health pilots used the same seed and 40-card pool at [125 HP](2026-11-06-hp-pilot/125/trace.html) and [260 HP](2026-11-06-hp-pilot/260/trace.html). The archived TOMLs explicitly set the historical pool and placement defaults.
- The historical [Elo board](leaderboard.html) includes the [rated demo fixture](2026-11-06-demo/matches/match-0001/trace.html). The [second fixture](2026-11-06-demo/matches/match-0002/trace.html) was experimental. Both schedule versions are preserved.
- The [Unity exhibition](2026-11-06-exhibition/trace.html), [landscape-placement run](2026-11-05-landscape-turns/trace.html) and [earlier setup run](2026-11-05-random-match/trace.html) document engine development. One diagnostic in the earlier setup trace uses a relative path in this public copy. Its gameplay events are unchanged.

From the repository root, run `uv run --locked python scripts/check_release.py` to verify every archived score against its trace. For an article, link to a match’s Markdown page or result file at a specific commit. Event sequence numbers in the JSONL identify individual decisions.
