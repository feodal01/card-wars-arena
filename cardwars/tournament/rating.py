"""Match-level Elo with one update per completed five-game match."""

from dataclasses import dataclass, field
from math import log, sqrt

INITIAL = 1500.0
K = 32.0


@dataclass
class Standing:
    rating: float = INITIAL
    matches: int = 0
    wins: int = 0
    games_won: int = 0
    kind: str = ""
    opponents: set = field(default_factory=set)


def unique_matches(records):
    seen = {}
    conditions = {}
    for m in records:
        if m.match_id in seen:
            if seen[m.match_id] != m.trace_hash:
                raise ValueError(f"Conflicting traces for match {m.match_id}")
            continue
        condition = (m.ruleset, m.seed, tuple(sorted(m.rating_ids)))
        if condition in conditions:
            raise ValueError(
                "Repeated fixture with another match ID; use a fresh pair seed"
            )
        seen[m.match_id] = m.trace_hash
        conditions[condition] = m.match_id
        yield m


def chance(rating_a, rating_b):
    return 1 / (1 + 10 ** ((rating_b - rating_a) / 400))


def standings(records):
    boards = {}
    for m in unique_matches(records):
        table = boards.setdefault(m.ruleset, {})
        a, b = m.rating_ids
        if a == b:
            continue
        for identifier, kind in zip(m.rating_ids, m.kinds):
            row = table.setdefault(identifier, Standing(kind=kind))
            if row.kind != kind:
                raise ValueError(f"Conflicting player types for {identifier}")
        a_won = m.wins[0] > m.wins[1]
        delta = K * (int(a_won) - chance(table[a].rating, table[b].rating))
        table[a].rating += delta
        table[b].rating -= delta
        for i, identifier in enumerate(m.rating_ids):
            row = table[identifier]
            row.matches += 1
            row.wins += int(m.wins[i] > m.wins[1 - i])
            row.games_won += m.wins[i]
            row.opponents.add(m.rating_ids[1 - i])
    return boards


def win_rate_interval(wins, matches):
    """Conservative 95% interval for match win rate on independent seeds."""
    if not matches:
        return None
    mean = wins / matches
    radius = sqrt(log(40) / (2 * matches))
    return max(0, mean - radius), min(1, mean + radius)
