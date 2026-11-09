"""Task allocation: greedy nearest-idle-robot vs. Hungarian assignment.

Both policies see the same inputs: the robots that are free to take work and the
pending (unassigned) orders, oldest first. Cost = shortest-path travel time from
the robot's current cell to the order's pod slot (BFS distance on the static map).
"""

from __future__ import annotations

from typing import Protocol

import numpy as np
from scipy.optimize import linear_sum_assignment

from .grid import UNREACHABLE, Grid
from .orders import Order

BIG = 10**9


class Allocator(Protocol):
    name: str

    def assign(
        self, t: int, robots: list[tuple[int, int]], pending: list[Order], grid: Grid
    ) -> list[tuple[int, Order]]: ...


def _cost_matrix(robots: list[tuple[int, int]], orders: list[Order], grid: Grid) -> np.ndarray:
    pos = np.fromiter((p for _, p in robots), dtype=np.int64, count=len(robots))
    cost = np.empty((len(robots), len(orders)), dtype=np.int64)
    for j, o in enumerate(orders):
        d = grid.dist_to(o.pod)[pos].astype(np.int64)
        d[d == UNREACHABLE] = BIG
        cost[:, j] = d
    return cost


class GreedyAllocator:
    """Every tick, the oldest pending order takes the nearest free robot (FIFO)."""

    name = "greedy"

    def assign(self, t, robots, pending, grid):
        if not robots or not pending:
            return []
        free = list(robots)
        pos = np.array([p for _, p in free])
        alive = np.ones(len(free), dtype=bool)
        out = []
        for o in pending:
            if not alive.any():
                break
            d = grid.dist_to(o.pod)[pos].astype(np.int64)
            d[~alive] = np.iinfo(np.int64).max
            i = int(np.argmin(d))
            alive[i] = False
            out.append((free[i][0], o))
        return out


class HungarianAllocator:
    """Every ``k`` ticks, solve min-total-travel assignment with linear_sum_assignment.

    Only the oldest ``window`` pending orders are considered, so that the
    optimiser cannot starve old orders indefinitely when there is a backlog.
    """

    def __init__(self, k: int = 5, window_factor: float = 2.0, min_window: int = 20) -> None:
        self.k = k
        self.window_factor = window_factor
        self.min_window = min_window
        self.name = f"hungarian_k{k}"

    def assign(self, t, robots, pending, grid):
        if t % self.k != 0 or not robots or not pending:
            return []
        window = max(self.min_window, int(self.window_factor * len(robots)))
        orders = pending[:window]
        cost = _cost_matrix(robots, orders, grid)
        rows, cols = linear_sum_assignment(cost)
        return [(robots[r][0], orders[c]) for r, c in zip(rows, cols) if cost[r, c] < BIG]


def make_allocator(name: str, k: int = 5) -> Allocator:
    if name == "greedy":
        return GreedyAllocator()
    if name.startswith("hungarian"):
        return HungarianAllocator(k=k)
    raise ValueError(f"unknown allocator {name!r}")
