"""Compare the MIP allocation with random baselines on one instance."""

from __future__ import annotations

import random

import numpy as np

from . import mip
from .aircraft import Seat, ordinary_boarding_order
from .simulate import simulate
from .timing import DEFAULT_TIMING, Timing

N_ROWS = 20


def bag_list(bag_counts: dict[int, int]) -> list[int]:
    return [b for b in (0, 1, 2) for _ in range(bag_counts.get(b, 0))]


def random_allocation(order: list[Seat], bag_counts, rng: random.Random) -> list[tuple[Seat, int]]:
    """Same Steffen boarding order, but bags are assigned to seats at random."""
    bags = bag_list(bag_counts)
    rng.shuffle(bags)
    return list(zip(order, bags))


def random_boarding(order: list[Seat], bag_counts, rng: random.Random) -> list[tuple[Seat, int]]:
    """Classic 'random boarding': random seats *and* a random boarding order."""
    seats = list(order)
    rng.shuffle(seats)
    bags = bag_list(bag_counts)
    rng.shuffle(bags)
    return list(zip(seats, bags))


def evaluate_instance(
    family: dict[Seat, int],
    bag_counts: dict[int, int],
    rng: random.Random,
    n_random: int = 200,
    timing: Timing = DEFAULT_TIMING,
) -> dict:
    order = ordinary_boarding_order(N_ROWS, set(family))
    sol = mip.solve(N_ROWS, family, bag_counts, timing=timing)
    mip_boarding = [(seat, sol.bags_by_seat[seat]) for seat in order]
    t_mip = simulate(mip_boarding, family, timing).total_time
    if abs(t_mip - sol.total_time) > 1e-6:
        raise RuntimeError(f"MIP objective {sol.total_time} != simulated {t_mip}")

    t_alloc = np.array([simulate(random_allocation(order, bag_counts, rng), family, timing).total_time for _ in range(n_random)])
    t_order = np.array([simulate(random_boarding(order, bag_counts, rng), family, timing).total_time for _ in range(n_random)])
    return {
        "n_family": len(family),
        "family_bags": sum(family.values()),
        "ordinary_one_bag": bag_counts.get(1, 0),
        "ordinary_two_bags": bag_counts.get(2, 0),
        "total_bags": sum(family.values()) + bag_counts.get(1, 0) + 2 * bag_counts.get(2, 0),
        "mip_status": sol.status,
        "mip_seconds": sol.solve_seconds,
        "t_mip": t_mip,
        "t_random_allocation_mean": t_alloc.mean(),
        "t_random_allocation_best": t_alloc.min(),
        "t_random_boarding_mean": t_order.mean(),
        "mip_beats_all_random_allocations": bool(t_mip <= t_alloc.min() + 1e-9),
        "mip_allocation": mip_boarding,
    }
