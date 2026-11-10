"""Tile distribution in CWDeckController.SetLandscapes for a proposed level-one deck."""

from collections import Counter

# Native Faction enum order also supplies the initial order for ties.
TYPES = ("Corn", "Plains", "Swamp", "Cotton", "Sand")


def required_tiles(cards, factions):
    counts = Counter(factions[card] for card in cards)
    ranked = sorted(TYPES, key=lambda tile: -counts[tile])
    colored = [tile for tile in ranked if counts[tile]]
    if len(colored) >= 4:
        return colored[:4]
    if len(colored) == 3:
        return [colored[0], *colored]
    if len(colored) == 2:
        first, second = colored
        first_count = counts[first]
        total = first_count + counts[second]
        copies = 3 if first_count * 100 >= 65 * total else 2
        return [first] * copies + [second] * (4 - copies)
    return [ranked[0]] * 4
