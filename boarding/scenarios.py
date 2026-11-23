"""Random instances for the three experiments in the dissertation.

Each function returns ``(family, bag_counts)``:
    family      {seat: bags} for family passengers (seated before boarding)
    bag_counts  {0: n0, 1: n1, 2: n2} for ordinary passengers
"""

from __future__ import annotations

import math
import random

from .aircraft import AISLE, MIDDLE, SIDES, WINDOW, Seat, all_seats

N_ROWS = 20
N_SEATS = N_ROWS * 6


def ordinary_bag_counts(n_ordinary: int, share_two_bags: float) -> dict[int, int]:
    """No ordinary passenger travels without a bag (as in the dissertation);
    a share carries two. Rounded up, which reproduces the dissertation's
    counts exactly (e.g. 96 passengers, 20% -> 20 with two bags)."""
    two = min(n_ordinary, math.ceil(round(share_two_bags * n_ordinary, 9)))
    return {0: 0, 1: n_ordinary - two, 2: two}


def _family_bags(seats, rng: random.Random) -> dict[Seat, int]:
    return {seat: rng.choice((0, 1, 2)) for seat in seats}


def random_families(family_share: float, share_two_bags: float, rng: random.Random):
    """Experiment 1: family passengers in random seats."""
    n_family = math.floor(family_share * N_SEATS)
    seats = rng.sample(all_seats(N_ROWS), n_family)
    return _family_bags(seats, rng), ordinary_bag_counts(N_SEATS - n_family, share_two_bags)


def families_in_window_seats(n_window: int, family_share: float, share_two_bags: float, rng: random.Random):
    """Experiment 2: ``n_window`` family passengers in window seats, the rest
    in random middle or aisle seats."""
    n_family = math.floor(family_share * N_SEATS)
    seats = all_seats(N_ROWS)
    window = [s for s in seats if s.m == WINDOW]
    other = [s for s in seats if s.m != WINDOW]
    chosen = rng.sample(window, n_window) + rng.sample(other, n_family - n_window)
    return _family_bags(chosen, rng), ordinary_bag_counts(N_SEATS - n_family, share_two_bags)


def group_sizes(n_family: int, share_in_pairs: float) -> tuple[int, int]:
    """Numbers of 2-person and 3-person groups with 2*g2 + 3*g3 = n_family,
    choosing the split whose share of people in pairs is closest to the target."""
    options = [(g2, (n_family - 2 * g2) // 3) for g2 in range(n_family // 2 + 1) if (n_family - 2 * g2) % 3 == 0]
    return min(options, key=lambda o: abs(2 * o[0] / n_family - share_in_pairs))


def family_groups(family_share: float, share_in_pairs: float, share_two_bags: float, rng: random.Random):
    """Experiment 3: families sit together. Pairs take the window and middle
    seat of one row/side; groups of three take a whole row/side."""
    n_family = math.floor(family_share * N_SEATS)
    g2, g3 = group_sizes(n_family, share_in_pairs)
    row_sides = rng.sample([(r, s) for r in range(1, N_ROWS + 1) for s in SIDES], g2 + g3)
    seats = []
    for k, (r, s) in enumerate(row_sides):
        ms = (WINDOW, MIDDLE) if k < g2 else (WINDOW, MIDDLE, AISLE)
        seats.extend(Seat(r, s, m) for m in ms)
    return _family_bags(seats, rng), ordinary_bag_counts(N_SEATS - n_family, share_two_bags)
