"""Space-time A* with prioritized planning over a shared reservation table.

Design (lifelong prioritized planning, "commit the whole errand"):

* Every robot always owns an *infinite* plan: a finite space-time path followed
  by parking forever on the last cell. The reservation table stores all of them.
* A new plan for robot ``i`` is searched against the plans of everybody else
  (vertex conflicts, edge/swap conflicts, and parked robots). If the search fails
  the robot keeps its old plan, which is still conflict-free, so the fleet is
  collision-free by construction. ``checker.find_conflicts`` verifies it on the
  logged trajectories.
* Robots only park permanently on their home cell; intermediate goals (pod
  slot, station) are *dwell* goals that must be free for the whole dwell window.
"""

from __future__ import annotations

import heapq
from dataclasses import dataclass

from .grid import UNREACHABLE, Grid

INF = 1 << 60


class ReservationTable:
    """Vertex, edge and parking reservations keyed by absolute time step."""

    def __init__(self) -> None:
        self.vertex: dict[tuple[int, int], int] = {}
        self.edge: dict[tuple[int, int, int], int] = {}  # (from, to, t): move during t -> t+1
        self.park: dict[int, tuple[int, int]] = {}  # cell -> (agent, from_t)
        self.cell_last: dict[int, dict[int, int]] = {}  # cell -> {agent: last t on cell}
        self.owned: dict[int, tuple[int, list[int]]] = {}  # agent -> (t0, path)

    # -------------------------------------------------------------- mutation
    def reserve(self, agent: int, t0: int, path: list[int]) -> None:
        if agent in self.owned:
            raise RuntimeError(f"agent {agent} already holds a reservation")
        prev = None
        for k, cell in enumerate(path):
            t = t0 + k
            other = self.vertex.get((cell, t))
            if other is not None and other != agent:
                raise RuntimeError(f"vertex conflict reserving agent {agent} at {(cell, t)} (held by {other})")
            self.vertex[(cell, t)] = agent
            if prev is not None and prev != cell:
                self.edge[(prev, cell, t - 1)] = agent
            self.cell_last.setdefault(cell, {})[agent] = t
            prev = cell
        end = path[-1]
        holder = self.park.get(end)
        if holder is not None and holder[0] != agent:
            raise RuntimeError(f"agent {agent} parks on {end}, already parked by {holder[0]}")
        self.park[end] = (agent, t0 + len(path) - 1)
        self.owned[agent] = (t0, list(path))

    def release(self, agent: int) -> tuple[int, list[int]] | None:
        held = self.owned.pop(agent, None)
        if held is None:
            return None
        t0, path = held
        prev = None
        for k, cell in enumerate(path):
            t = t0 + k
            if self.vertex.get((cell, t)) == agent:
                del self.vertex[(cell, t)]
            if prev is not None and prev != cell and self.edge.get((prev, cell, t - 1)) == agent:
                del self.edge[(prev, cell, t - 1)]
            last = self.cell_last.get(cell)
            if last is not None:
                last.pop(agent, None)
                if not last:
                    del self.cell_last[cell]
            prev = cell
        end = path[-1]
        if self.park.get(end, (None,))[0] == agent:
            del self.park[end]
        return held

    def prune_before(self, t_now: int) -> None:
        """Drop vertex/edge entries in the past (they can never conflict again)."""
        self.vertex = {k: v for k, v in self.vertex.items() if k[1] >= t_now}
        self.edge = {k: v for k, v in self.edge.items() if k[2] >= t_now}

    # -------------------------------------------------------------- queries
    def cell_free(self, cell: int, t: int, agent: int) -> bool:
        other = self.vertex.get((cell, t))
        if other is not None and other != agent:
            return False
        p = self.park.get(cell)
        return p is None or p[0] == agent or t < p[1]

    def move_free(self, a: int, b: int, t: int, agent: int) -> bool:
        """Can ``agent`` move a -> b during t -> t+1 without a swap conflict?"""
        other = self.edge.get((b, a, t))
        return other is None or other == agent

    def last_use_by_others(self, cell: int, agent: int) -> int:
        """Last time step any *other* agent occupies ``cell`` (INF if parked there)."""
        p = self.park.get(cell)
        if p is not None and p[0] != agent:
            return INF
        last = self.cell_last.get(cell)
        if not last:
            return -1
        return max((t for a, t in last.items() if a != agent), default=-1)


@dataclass
class SearchStats:
    expansions: int = 0
    segments: int = 0


def space_time_astar(
    grid: Grid,
    rt: ReservationTable,
    agent: int,
    start: int,
    t0: int,
    goal: int,
    dwell: int = 0,
    final: bool = False,
    max_t: int | None = None,
    max_expansions: int = 200_000,
    stats: SearchStats | None = None,
) -> list[int] | None:
    """Shortest space-time path from (start, t0) to ``goal``.

    ``final=True``: the agent parks on ``goal`` forever, so arrival time must be
    after the last time any other agent uses that cell.
    ``final=False``: the goal must stay free for ``dwell`` extra steps after arrival.
    Returns cells for t0..t_arrival (inclusive), or None.
    """
    dist = grid.dist_to(goal)
    if dist[start] == UNREACHABLE:
        return None
    base = int(dist[start])

    # Earliest admissible arrival time T* (ignores the route, so it is a valid lower bound).
    if final:
        last = rt.last_use_by_others(goal, agent)
        if last >= INF:
            return None
        t_star = max(t0 + base, last + 1)
    else:
        holder = rt.park.get(goal)
        if holder is not None and holder[0] != agent:
            return None  # a stopped robot occupies the goal for good: no dwell window will ever open
        t_star = t0 + base
        limit = (max_t if max_t is not None else t0 + 4 * base + 400)
        while t_star <= limit:
            # jump past the first conflict in the window: every start up to it would contain it too
            bad = next((k for k in range(dwell + 1) if not rt.cell_free(goal, t_star + k, agent)), None)
            if bad is None:
                break
            t_star += bad + 1
        if t_star > limit:
            return None
    if max_t is None:
        max_t = t_star + 2 * base + 200

    def goal_ok(t: int) -> bool:
        if t < t_star:
            return False
        if final:
            return True  # t >= last use by others + 1, and parking ownership checked above
        return all(rt.cell_free(goal, t + k, agent) for k in range(1, dwell + 1))

    nbrs = grid.neighbors
    cell_free = rt.cell_free
    move_free = rt.move_free
    h0 = max(base, t_star - t0)
    open_heap: list[tuple[int, int, int, int, int]] = [(h0, h0, 0, start, t0)]
    parent: dict[tuple[int, int], tuple[int, int] | None] = {(start, t0): None}
    counter = 0
    expansions = 0
    while open_heap:
        _f, _h, _, cell, t = heapq.heappop(open_heap)
        if cell == goal and goal_ok(t):
            path = []
            node: tuple[int, int] | None = (cell, t)
            while node is not None:
                path.append(node[0])
                node = parent[node]
            path.reverse()
            if stats is not None:
                stats.expansions += expansions
                stats.segments += 1
            return path
        expansions += 1
        if expansions > max_expansions or t >= max_t:
            if expansions > max_expansions:
                break
            continue
        nt = t + 1
        for nxt in (cell, *nbrs[cell]):
            key = (nxt, nt)
            if key in parent:
                continue
            if not cell_free(nxt, nt, agent):
                continue
            if nxt != cell and not move_free(cell, nxt, t, agent):
                continue
            parent[key] = (cell, t)
            g = nt - t0
            h = max(int(dist[nxt]), t_star - nt)
            counter += 1
            heapq.heappush(open_heap, (g + h, h, counter, nxt, nt))
    if stats is not None:
        stats.expansions += expansions
    return None


def plan_errand(
    grid: Grid,
    rt: ReservationTable,
    agent: int,
    start: int,
    t0: int,
    legs: list[tuple[int, int]],
    home: int,
    stats: SearchStats | None = None,
) -> tuple[list[int], list[int]] | None:
    """Chain segments: for each (goal, dwell) leg, then park at ``home``.

    Returns (path from t0, list of arrival indices into path for each leg + home),
    or None if any segment fails. The table is *not* modified.
    """
    path = [start]
    arrivals: list[int] = []
    cur, t = start, t0
    for goal, dwell in legs:
        seg = space_time_astar(grid, rt, agent, cur, t, goal, dwell=dwell, stats=stats)
        if seg is None:
            return None
        path.extend(seg[1:])
        arrivals.append(len(path) - 1)
        path.extend([goal] * dwell)
        cur, t = goal, t0 + len(path) - 1
    seg = space_time_astar(grid, rt, agent, cur, t, home, final=True, stats=stats)
    if seg is None:
        return None
    path.extend(seg[1:])
    arrivals.append(len(path) - 1)
    return path, arrivals
