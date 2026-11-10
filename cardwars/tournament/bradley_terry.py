"""Joint match-level Bradley–Terry fit and pair-stratified bootstrap on the Elo scale."""

import math
import random
from collections import defaultdict


def _reaches_all(edges):
    visited = {0}
    pending = [0]
    while pending:
        for other in edges[pending.pop()]:
            if other not in visited:
                visited.add(other)
                pending.append(other)
    return len(visited) == len(edges)


def _fit(n, pairs):
    # A finite unpenalized MLE exists when the directed wins graph is strongly connected.
    forward = [set() for _ in range(n)]
    reverse = [set() for _ in range(n)]
    wins = [0] * n
    for (a, b), (wa, wb) in pairs.items():
        for u, v, count in ((a, b, wa), (b, a, wb)):
            if count:
                forward[u].add(v)
                reverse[v].add(u)
                wins[u] += count
    if n < 2 or not _reaches_all(forward) or not _reaches_all(reverse):
        return None

    strengths = [1.0] * n
    for _ in range(10000):
        denominator = [0.0] * n
        for (a, b), outcomes in pairs.items():
            term = sum(outcomes) / (strengths[a] + strengths[b])
            denominator[a] += term
            denominator[b] += term
        updated = [win / total for win, total in zip(wins, denominator)]
        scale = sum(updated) / n
        updated = [s / scale for s in updated]
        error = max(abs(math.log(x / y)) for x, y in zip(updated, strengths))
        strengths = updated
        if error < 1e-8:
            logs = [400 * math.log10(s) for s in strengths]
            center = sum(logs) / n
            return [1500 + value - center for value in logs]
    return None


def estimate(matches, entrants, samples=1000):
    names = sorted(entrants)
    index = {name: i for i, name in enumerate(names)}
    counts = defaultdict(lambda: [0, 0])
    for match in matches:
        if match.rating_ids[0] == match.rating_ids[1]:
            continue
        a, b = (index[name] for name in match.rating_ids)
        winner = a if match.wins[0] > match.wins[1] else b
        pair = tuple(sorted((a, b)))
        counts[pair][pair.index(winner)] += 1
    counts = dict(sorted(counts.items()))
    fitted = _fit(len(names), counts)
    if fitted is None:
        return {}, {}
    ratings = dict(zip(names, fitted))
    if min(map(sum, counts.values())) < 5:
        return ratings, {}
    rng = random.Random(0)
    draws = []
    for _ in range(samples):
        sampled = {}
        for pair, tally in counts.items():
            total = sum(tally)
            p = tally[0] / total
            wins = sum(rng.random() < p for _ in range(total))
            sampled[pair] = (wins, total - wins)
        fit = _fit(len(names), sampled)
        if fit is not None:
            draws.append(fit)
    # Count undefined fits conservatively in either tail rather than dropping them.
    tail = int(samples * 0.025)
    k = tail - (samples - len(draws))
    if k < 0:
        return ratings, {}
    intervals = {}
    for i, name in enumerate(names):
        values = sorted(draw[i] for draw in draws)
        intervals[name] = (values[k], values[-1 - k])
    return ratings, intervals
