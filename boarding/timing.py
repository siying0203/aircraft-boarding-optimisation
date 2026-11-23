"""Passenger timing assumptions (Section IV-B of the dissertation).

All times are in seconds.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Timing:
    t_row: float = 2.4  # walk from one row to the next (Milne & Kelly, 2014)
    t_sit: float = 8.0  # sit down once the way is clear

    def store(self, bags_in_bin: int, bags: int) -> float:
        """Eq. (2): time to stow ``bags`` pieces when the overhead bin of this
        row and side already holds ``bags_in_bin`` pieces.

            T_store = (N_bin + N_passenger) * N_passenger / 2 * T_row
        """
        return (bags_in_bin + bags) * bags / 2 * self.t_row

    def sit(self, blockers: int) -> float:
        """Eq. (1): time to reach the seat when ``blockers`` seated passengers
        (between the aisle and this seat) must stand up and sit down again.

            T_conflict = (1 + 2 D) * T_sit
        """
        return (1 + 2 * blockers) * self.t_sit


DEFAULT_TIMING = Timing()
