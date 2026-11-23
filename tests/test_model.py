import random
from itertools import permutations

import pytest

from boarding import mip, scenarios
from boarding.aircraft import AISLE, LEFT, MIDDLE, RIGHT, WINDOW, Seat, all_seats, ordinary_boarding_order, steffen_order
from boarding.simulate import simulate
from boarding.timing import Timing

T = Timing()


# --- cabin and boarding order -------------------------------------------------

def test_steffen_order_matches_dissertation_example():
    order = steffen_order(20)
    assert len(order) == len(set(order)) == 120
    # "passenger 34 sits in row 13 on the left; the next free seat is row 11, left"
    assert order[33] == Seat(13, LEFT, WINDOW)
    assert order[34] == Seat(11, LEFT, WINDOW)
    # all window seats first, then middle, then aisle
    assert [s.m for s in order] == [WINDOW] * 40 + [MIDDLE] * 40 + [AISLE] * 40


def test_ordinary_order_skips_family_seats():
    family = {Seat(20, RIGHT, WINDOW), Seat(5, LEFT, AISLE)}
    order = ordinary_boarding_order(20, family)
    assert len(order) == 118 and not family & set(order)


# --- timing equations ---------------------------------------------------------

@pytest.mark.parametrize(
    "bin_before, bags, expected",
    [(0, 1, 1.2), (0, 2, 4.8), (1, 2, 7.2), (2, 1, 3.6), (1, 1, 2.4), (2, 2, 9.6), (0, 0, 0.0)],
)
def test_store_time_reproduces_table_2(bin_before, bags, expected):
    assert T.store(bin_before, bags) == pytest.approx(expected)


def test_seat_conflict_time():
    assert T.sit(0) == 8.0 and T.sit(1) == 24.0 and T.sit(2) == 40.0


# --- simulation ---------------------------------------------------------------

def test_single_passenger():
    seat = Seat(10, LEFT, WINDOW)
    res = simulate([(seat, 2)])
    assert res.total_time == pytest.approx(10 * T.t_row + T.t_sit + T.store(0, 2))


def test_family_in_aisle_seat_causes_seat_interference_and_fills_bin():
    seat = Seat(3, LEFT, WINDOW)
    family = {Seat(3, LEFT, AISLE): 2}
    res = simulate([(seat, 1)], family)
    assert res.sit_time[0] == T.sit(1)
    assert res.store_time[0] == T.store(2, 1)


def test_passenger_behind_waits_for_passenger_stowing_ahead():
    front, back = Seat(2, LEFT, WINDOW), Seat(5, LEFT, WINDOW)
    alone = simulate([(back, 0)]).total_time
    blocked = simulate([(front, 2), (back, 0)]).seated_time[1]
    assert blocked > alone


# --- MIP ----------------------------------------------------------------------

def small_instance(seed=0, n_rows=2):
    rng = random.Random(seed)
    seats = all_seats(n_rows)
    family = {s: rng.choice((0, 1, 2)) for s in rng.sample(seats, 4)}
    counts = {0: 2, 1: 3, 2: len(seats) - 4 - 5}
    return n_rows, family, counts


@pytest.mark.parametrize("seed", [0, 1, 2])
def test_mip_matches_brute_force_optimum(seed):
    n_rows, family, counts = small_instance(seed)
    order = ordinary_boarding_order(n_rows, set(family))
    bags = [b for b in (0, 1, 2) for _ in range(counts[b])]
    best = min(simulate(list(zip(order, perm)), family).total_time for perm in set(permutations(bags)))
    sol = mip.solve(n_rows, family, counts)
    assert sol.status == "Optimal"
    assert sol.total_time == pytest.approx(best)


def test_mip_objective_equals_simulation_and_respects_bag_counts():
    rng = random.Random(3)
    family, counts = scenarios.random_families(0.2, 0.4, rng)
    sol = mip.solve(20, family, counts)
    order = ordinary_boarding_order(20, set(family))
    sim = simulate([(s, sol.bags_by_seat[s]) for s in order], family)
    assert sim.total_time == pytest.approx(sol.total_time)
    allocated = list(sol.bags_by_seat.values())
    assert {b: allocated.count(b) for b in (0, 1, 2)} == counts


# --- experiment set-up ----------------------------------------------------------

def test_bag_counts_match_dissertation_table_3():
    assert [scenarios.ordinary_bag_counts(96, f)[2] for f in (0.2, 0.4, 0.6, 0.8, 1.0)] == [20, 39, 58, 77, 96]
    assert [scenarios.ordinary_bag_counts(72, f)[2] for f in (0.2, 0.4, 0.6, 0.8, 1.0)] == [15, 29, 44, 58, 72]
    assert [scenarios.ordinary_bag_counts(48, f)[2] for f in (0.2, 0.4, 0.6, 0.8, 1.0)] == [10, 20, 29, 39, 48]


def test_family_groups_sit_together():
    family, _ = scenarios.family_groups(0.2, 0.2, 0.6, random.Random(0))
    assert len(family) == 24
    by_row_side = {}
    for s in family:
        by_row_side.setdefault((s.row, s.side), set()).add(s.m)
    assert all(ms in ({WINDOW, MIDDLE}, {WINDOW, MIDDLE, AISLE}) for ms in by_row_side.values())
