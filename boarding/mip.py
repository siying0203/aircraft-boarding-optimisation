"""Mixed-integer program for luggage-aware seat allocation (Section IV-C).

Families are already seated. Ordinary passengers board in Steffen order, so
the *seats* are filled in a fixed sequence; what the airline chooses is which
passenger (i.e. which number of bags) gets which seat. Following Milne &
Salari (2016) and Salari et al. (2019), the choice is made per row and side:
for every row/side we pick one luggage *scenario* -- the number of bags (0, 1
or 2) for each of its free seats. Because the scenario fixes the order in
which bags enter that overhead bin, every passenger's stowing time becomes a
constant for each scenario and the model stays linear.

Variables
    X[r, s, c] = 1 if scenario c is chosen for row r, side s      (binary)
    E[p, r]    time passenger p leaves the aisle at row r           (continuous)
    T          time the last passenger is seated                    (continuous)

    min T
    s.t. T >= E[p, r_p]                                   for all p           (4)
         sum_c X[r, s, c] = 1                              for all r, s        (5)
         sum_{r,s,c} n_b(c) X[r, s, c] = N_b               for b = 0, 1, 2     (6)
         movement and seating constraints (7)-(11), as in ``simulate.py``,
         with T_store(p) = sum_c X[r_p, s_p, c] * store_p(c).
"""

from __future__ import annotations

import itertools
import time
from dataclasses import dataclass

import pulp

from .aircraft import Seat, ordinary_boarding_order
from .timing import DEFAULT_TIMING, Timing

BAGS = (0, 1, 2)


@dataclass
class MipSolution:
    total_time: float
    bags_by_seat: dict[Seat, int]
    status: str
    solve_seconds: float


def _scenarios(n_free: int):
    return list(itertools.product(BAGS, repeat=n_free))


def solve(
    n_rows: int,
    family: dict[Seat, int],
    bag_counts: dict[int, int],
    timing: Timing = DEFAULT_TIMING,
    time_limit: float = 120.0,
    msg: bool = False,
) -> MipSolution:
    """Find the bag-to-seat allocation that minimises total boarding time.

    ``bag_counts[b]`` is the number of ordinary passengers carrying b bags;
    the counts must add up to the number of free seats.
    """
    order = ordinary_boarding_order(n_rows, set(family))
    if sum(bag_counts.get(b, 0) for b in BAGS) != len(order):
        raise ValueError("bag counts must add up to the number of ordinary passengers")

    # free seats of each row/side, in the order they are filled
    free: dict[tuple[int, int], list[Seat]] = {}
    for seat in order:
        free.setdefault((seat.row, seat.side), []).append(seat)
    scen = {key: _scenarios(len(seats)) for key, seats in free.items()}

    prob = pulp.LpProblem("aircraft_boarding", pulp.LpMinimize)
    T = pulp.LpVariable("T", 0)
    X = {
        (key, c): pulp.LpVariable(f"X_{key[0]}_{key[1]}_{''.join(map(str, c))}", cat="Binary")
        for key, cs in scen.items()
        for c in cs
    }
    prob += T

    for key, cs in scen.items():  # (5)
        prob += pulp.lpSum(X[key, c] for c in cs) == 1
    for b in BAGS:  # (6)
        prob += (
            pulp.lpSum(c.count(b) * X[key, c] for key, cs in scen.items() for c in cs)
            == bag_counts.get(b, 0)
        )

    family_bags = {}
    family_seats = {}
    for seat, bags in family.items():
        key = (seat.row, seat.side)
        family_bags[key] = family_bags.get(key, 0) + bags
        family_seats.setdefault(key, set()).add(seat.m)

    last_exit: dict[int, pulp.LpVariable] = {}
    for p, seat in enumerate(order):
        key = (seat.row, seat.side)
        k = free[key].index(seat)  # position of this passenger within its row/side
        # seated passengers between this seat and the aisle (families; under the
        # Steffen order ordinary passengers fill window -> middle -> aisle)
        earlier_ordinary = {s.m for s in free[key][:k]}
        blockers = sum(1 for m in family_seats.get(key, set()) | earlier_ordinary if m > seat.m)
        sit = timing.sit(blockers)
        store = pulp.lpSum(
            timing.store(family_bags.get(key, 0) + sum(c[:k]), c[k]) * X[key, c] for c in scen[key]
        )

        E = {r: pulp.LpVariable(f"E_{p}_{r}", 0) for r in range(1, seat.row + 1)}
        for r in range(1, seat.row):
            prob += E[r] >= (E[r - 1] if r > 1 else 0) + timing.t_row  # (7)
            if r in last_exit:
                prob += E[r] >= last_exit[r] + 2 * timing.t_row  # (8)
            if r + 1 in last_exit:
                prob += E[r] >= last_exit[r + 1] + timing.t_row  # (9)
        r = seat.row
        prob += E[r] >= (E[r - 1] if r > 1 else 0) + timing.t_row + sit + store  # (10)
        if r in last_exit:
            prob += E[r] >= last_exit[r] + timing.t_row + sit + store  # (11)
        prob += T >= E[r]  # (4)
        last_exit.update(E)

    solver = pulp.PULP_CBC_CMD(msg=msg, timeLimit=time_limit, gapRel=0)
    start = time.perf_counter()
    prob.solve(solver)
    seconds = time.perf_counter() - start

    bags_by_seat = {}
    for key, cs in scen.items():
        chosen = max(cs, key=lambda c: X[key, c].value() or 0)
        for seat, b in zip(free[key], chosen):
            bags_by_seat[seat] = b

    return MipSolution(pulp.value(T), bags_by_seat, pulp.LpStatus[prob.status], seconds)
