"""Event-time simulation of single-file aisle boarding.

Passengers enter through the front door one after another and walk down a
single aisle. The simulation tracks, for every passenger p and every row r
they reach, the time ``E[p, r]`` at which p *leaves* the aisle cell of row r
(for their own row: the time they have stowed their bags and sat down). The
rules are the dissertation's constraints (7)-(11):

* (7)  walking:     E[p, r] >= E[p, r-1] + T_row
* (8)  spacing:     E[p, r] >= E[q, r] + 2 T_row          q = previous passenger through row r
* (9)  queueing:    E[p, r] >= E[q', r+1] + T_row         q' = previous passenger through row r+1
                    (p cannot step forward while the cell ahead is occupied)
* (10) own row:     E[p, r_p] >= E[p, r_p - 1] + T_row + T_sit(1 + 2D) + T_store
* (11) own row:     E[p, r_p] >= E[q, r_p] + T_row + T_sit(1 + 2D) + T_store

Every constraint is a "max" of earlier events, so the earliest feasible times
can be computed directly, passenger by passenger, in boarding order. The MIP
in ``mip.py`` uses exactly the same constraints, so for any fixed seat
allocation the MIP's boarding time equals this simulation's result (this is
checked in the tests).

Time zero is the moment the first ordinary passenger enters the cabin;
family passengers are already seated, as in the dissertation.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

import numpy as np

from .aircraft import Seat
from .timing import DEFAULT_TIMING, Timing


@dataclass
class Result:
    total_time: float  # time at which the last passenger is seated
    seated_time: np.ndarray  # per passenger, in boarding order
    store_time: np.ndarray
    sit_time: np.ndarray


def simulate(
    boarding: list[tuple[Seat, int]],
    family: dict[Seat, int] | None = None,
    timing: Timing = DEFAULT_TIMING,
    walk_factor: np.ndarray | None = None,
    sit_factor: np.ndarray | None = None,
    store_factor: np.ndarray | None = None,
) -> Result:
    """Simulate boarding.

    Parameters
    ----------
    boarding:  ``[(seat, bags), ...]`` for ordinary passengers in boarding order.
    family:    ``{seat: bags}`` for family passengers already seated.
    *_factor:  optional per-passenger multipliers on walking, sitting and
               stowing times (used for the stochastic robustness check).
    """
    family = family or {}
    n = len(boarding)
    ones = np.ones(n)
    walk_factor = ones if walk_factor is None else walk_factor
    sit_factor = ones if sit_factor is None else sit_factor
    store_factor = ones if store_factor is None else store_factor

    # state of each row/side: overhead-bin contents and occupied seat types
    bin_bags: dict[tuple[int, int], int] = defaultdict(int)
    occupied: dict[tuple[int, int], set[int]] = defaultdict(set)
    for seat, bags in family.items():
        bin_bags[(seat.row, seat.side)] += bags
        occupied[(seat.row, seat.side)].add(seat.m)

    last_exit: dict[int, float] = {}  # row -> exit time of the latest passenger through it
    seated = np.zeros(n)
    stores = np.zeros(n)
    sits = np.zeros(n)

    for p, (seat, bags) in enumerate(boarding):
        t_row = timing.t_row * walk_factor[p]
        key = (seat.row, seat.side)
        blockers = sum(1 for m in occupied[key] if m > seat.m)
        sit = timing.sit(blockers) * sit_factor[p]
        store = timing.store(bin_bags[key], bags) * store_factor[p]

        exits = {}
        prev = 0.0
        for r in range(1, seat.row):
            e = prev + t_row  # (7)
            if r in last_exit:
                e = max(e, last_exit[r] + 2 * t_row)  # (8)
            if r + 1 in last_exit:
                e = max(e, last_exit[r + 1] + t_row)  # (9)
            exits[r] = prev = e
        service = sit + store
        e = prev + t_row + service  # (10)
        if seat.row in last_exit:
            e = max(e, last_exit[seat.row] + t_row + service)  # (11)
        exits[seat.row] = e

        last_exit.update(exits)
        bin_bags[key] += bags
        occupied[key].add(seat.m)
        seated[p], stores[p], sits[p] = e, store, sit

    return Result(float(seated.max()) if n else 0.0, seated, stores, sits)
