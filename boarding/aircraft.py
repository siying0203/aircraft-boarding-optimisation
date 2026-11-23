"""Cabin layout and the Steffen boarding sequence.

The cabin is a single-aisle aircraft with ``n_rows`` rows. Each row has two
sides (1 = left, 2 = right) with three seats per side:

    m = 1  window      m = 2  middle      m = 3  aisle

A seat is the tuple ``(row, side, m)``. Row 1 is at the front, next to the
(only) door, so a passenger seated in row r walks past rows 1 .. r-1.
"""

from __future__ import annotations

from typing import NamedTuple

WINDOW, MIDDLE, AISLE = 1, 2, 3
LEFT, RIGHT = 1, 2
SEAT_TYPES = (WINDOW, MIDDLE, AISLE)
SIDES = (LEFT, RIGHT)


class Seat(NamedTuple):
    row: int
    side: int
    m: int  # 1 window, 2 middle, 3 aisle


def all_seats(n_rows: int) -> list[Seat]:
    return [Seat(r, s, m) for r in range(1, n_rows + 1) for s in SIDES for m in SEAT_TYPES]


def steffen_order(n_rows: int) -> list[Seat]:
    """Steffen (2008) boarding sequence for the whole cabin.

    Window seats first, then middle seats, then aisle seats. Within each seat
    type, passengers board every second row from the back, one side at a
    time, so that neighbours in the queue are two rows apart and can stow
    their luggage in parallel:

        right side, rows n, n-2, ... ; left side, rows n, n-2, ... ;
        right side, rows n-1, n-3, ...; left side, rows n-1, n-3, ...

    With 20 rows this gives position 34 -> row 13 left and position 35 ->
    row 11 left, matching the example in the dissertation.
    """
    order: list[Seat] = []
    for m in SEAT_TYPES:
        for start in (n_rows, n_rows - 1):
            for side in (RIGHT, LEFT):
                order.extend(Seat(r, side, m) for r in range(start, 0, -2))
    return order


def ordinary_boarding_order(n_rows: int, family_seats: set[Seat]) -> list[Seat]:
    """Steffen order for ordinary passengers, skipping seats already taken by
    families (who board first). A passenger whose Steffen seat is taken simply
    gets the next free seat in the sequence."""
    return [seat for seat in steffen_order(n_rows) if seat not in family_seats]
