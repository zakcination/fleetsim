"""Task allocation: greedy nearest-idle-robot vs. Hungarian assignment.

Both policies see the same inputs: the robots that are free to take work and the
pending (unassigned) orders, oldest first. Cost = shortest-path travel time from
the robot's current cell to the order's pod slot (BFS distance on the static map).
"""

from __future__ import annotations

from typing import Callable, Protocol

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


ALLOCATORS: dict[str, Callable[..., "Allocator"]] = {}


def register_allocator(name: str):
    """Class decorator: make a dispatch policy available as ``SimConfig(allocator=name)``.

    The class is constructed with keyword arguments from the simulation config
    (currently ``k``); accept ``**kwargs`` if you don't need them.
    """

    def deco(cls):
        ALLOCATORS[name] = cls
        return cls

    return deco


@register_allocator("greedy")
class GreedyAllocator:
    """Every tick, the oldest pending order takes the nearest free robot (FIFO)."""

    name = "greedy"

    def __init__(self, **_):
        pass

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


@register_allocator("nearest")
class NearestPairAllocator:
    """Every tick, repeatedly match the globally closest (free robot, order) pair.

    Same order window as Hungarian, no batching delay, but ignores order age.
    This is the baseline that separates "optimal matching" from "serving
    nearby orders first" when comparing against Hungarian.
    """

    name = "nearest"

    def __init__(self, window_factor: float = 2.0, min_window: int = 20, **_):
        self.window_factor = window_factor
        self.min_window = min_window

    def assign(self, t, robots, pending, grid):
        if not robots or not pending:
            return []
        window = max(self.min_window, int(self.window_factor * len(robots)))
        orders = pending[:window]
        cost = _cost_matrix(robots, orders, grid)
        flat = np.argsort(cost, axis=None, kind="stable")
        used_r, used_o, out = set(), set(), []
        for f in flat:
            r, c = divmod(int(f), cost.shape[1])
            if r in used_r or c in used_o or cost[r, c] >= BIG:
                continue
            used_r.add(r)
            used_o.add(c)
            out.append((robots[r][0], orders[c]))
            if len(out) == min(len(robots), len(orders)):
                break
        return out


@register_allocator("hungarian")
class HungarianAllocator:
    """Every ``k`` ticks, solve min-total-travel assignment with linear_sum_assignment.

    Only the oldest ``window`` pending orders are considered, so that the
    optimiser cannot starve old orders indefinitely when there is a backlog.
    """

    def __init__(self, k: int = 5, window_factor: float = 2.0, min_window: int = 20, **_) -> None:
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


@register_allocator("hungarian_aging")
class AgingHungarianAllocator(HungarianAllocator):
    """Hungarian with an age bonus: cost = travel_s - aging * wait_s.

    ``aging`` is the number of seconds of extra travel the policy accepts to serve
    an order that has waited one second longer. 0 reproduces plain Hungarian;
    larger values trade throughput for fairness (lower tail waits).
    """

    def __init__(self, k: int = 5, aging: float = 0.25, **kw) -> None:
        super().__init__(k=k, **kw)
        self.aging = aging
        self.name = f"hungarian_aging_k{k}_a{aging:g}"

    def assign(self, t, robots, pending, grid):
        if t % self.k != 0 or not robots or not pending:
            return []
        window = max(self.min_window, int(self.window_factor * len(robots)))
        orders = pending[:window]
        travel = _cost_matrix(robots, orders, grid)
        age = np.array([t - o.created for o in orders], dtype=float)
        rows, cols = linear_sum_assignment(travel - self.aging * age[None, :])
        return [(robots[r][0], orders[c]) for r, c in zip(rows, cols) if travel[r, c] < BIG]


def make_allocator(name: str, k: int = 5, **params) -> Allocator:
    try:
        return ALLOCATORS[name](k=k, **params)
    except KeyError:
        raise ValueError(f"unknown allocator {name!r}; registered: {sorted(ALLOCATORS)}") from None
