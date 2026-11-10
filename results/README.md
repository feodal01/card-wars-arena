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

| Format | Player 1 | Player 2 | Score | Replay |
|---|---|---|:---:|---|
| 100 HP baseline, seed 42 | Uniform random | Play-first random | 2–3 | [Five games](2026-11-10-random-baseline/trace.html) |
| 125 HP pilot, 40-card pool | Uniform random | Play-first random | 4–1 | [Five games](2026-11-06-hp-pilot/125/trace.html) |
| 260 HP pilot, same seed and pool | Uniform random | Play-first random | 3–2 | [Five games](2026-11-06-hp-pilot/260/trace.html) |
| Rated demo | Uniform random | Play-first random | 2–3 | [Five games](2026-11-06-demo/matches/match-0001/trace.html) |
| Experimental demo | Play-first random | Uniform random | 4–1 | [Five games](2026-11-06-demo/matches/match-0002/trace.html) |
| Unity exhibition | Uniform random | Play-first random | 2–3 | [Five games](2026-11-06-exhibition/trace.html) |
| Landscape-placement trial | Random A | Random B | 4–1 | [Five games](2026-11-05-landscape-turns/trace.html) |
| Early setup trial | Random A | Random B | 2–3 | [Five games](2026-11-05-random-match/trace.html) |

The [100 HP baseline configuration](2026-11-10-random-baseline/match.toml) ran on a freshly prepared engine. The historical [Elo board](leaderboard.html) includes the rated demo. In the early setup trace, one diagnostic uses a relative path in the public copy.

From the repository root, run `uv run --locked python scripts/check_release.py` to verify every archived score against its trace. For an article, link to a match’s Markdown page or result file at a specific commit. Event sequence numbers in the JSONL identify individual decisions.
