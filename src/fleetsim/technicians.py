"""Technicians: who repairs a stopped robot, and how they get to it.

Two crews share one interface (``step``, ``on_freeze``, ``fix``):

* :class:`TimerCrew` (default). A technician is a timer: the walk to the robot
  takes its shortest-path time, and the technician is not present on the floor.
  This is the model trials T2, T2b, T3 and T3b were run with.
* :class:`CorridorCrew` (``SimConfig.tech_corridors=True``). A technician is an
  agent in the reservation table with **priority over robots**. The whole duty
  is booked at once: walk out, stand on a cell next to the robot, repair, walk
  back to a base cell that robots may never enter. Robots whose booked routes
  cross that corridor replan or stop; a robot that stops on a corridor makes the
  technician walk around it. No robot ever shares a cell with a technician.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import numpy as np

from . import health as H
from .grid import UNREACHABLE, Grid

if TYPE_CHECKING:  # pragma: no cover
    from .sim import Fleet

BLOCKED_STATE = 12  # sim.BLOCKED (kept in sync by a test; avoids a circular import)
REPAIR_STATE = 11  # sim.REPAIR


def bfs_path(grid: Grid, src: int, dst: int, blocked: set[int]) -> list[int] | None:
    """Shortest walking route from ``src`` to ``dst`` around ``blocked`` cells."""
    if src == dst:
        return [src]
    prev = {src: -1}
    q = deque([src])
    while q:
        u = q.popleft()
        for v in grid.neighbors[u]:
            if v in prev or v in blocked:
                continue
            prev[v] = u
            if v == dst:
                path = [v]
                while u != -1:
                    path.append(u)
                    u = prev[u]
                return path[::-1]
            q.append(v)
    return None


def choose_tech_bases(grid: Grid, homes: list[int], chargers: list[int], k: int) -> list[int]:
    """``k`` base cells near the map's first free cell, off-limits to robots.

    Chosen after the robot homes (so switching corridors on does not move any
    home) and such that parked robots plus bases never cut the floor in two and
    every base keeps a way out.
    """
    taken = set(homes) | set(chargers) | set(grid.stations)
    for c in list(chargers) + list(grid.stations):
        taken.update(grid.neighbors[c])
    origin = min(grid.free_cells())
    dist = grid.bfs(origin)
    cands = sorted((c for c in grid.free_cells() if grid.char(c) == "." and c not in taken), key=lambda c: (int(dist[c]), c))
    chosen: list[int] = []
    blocked = set(homes)
    probe = grid.stations[0]
    for c in cands:
        if len(chosen) == k:
            break
        blocked.add(c)
        connected = int((grid.bfs(probe, blocked) != UNREACHABLE).sum()) == grid.n_free - len(blocked)
        exits = all(any(n not in blocked for n in grid.neighbors[b]) for b in chosen + [c])
        if connected and exits:
            chosen.append(c)
        else:
            blocked.discard(c)
    if len(chosen) < k:
        raise ValueError(f"could only place {len(chosen)} technician bases for {k} technicians")
    return chosen


class TimerCrew:
    """Technicians as timers (v0.2 trials). Not present on the floor."""

    tracks = False

    def __init__(self, fleet: "Fleet") -> None:
        self.f = fleet
        base = min(fleet.grid.free_cells())
        self.techs = [{"id": i, "cell": base, "job": None} for i in range(fleet.cfg.techs)]

    def step(self, t: int) -> None:
        f = self.f
        waiting = [j for j in f.jobs if j["status"] == "waiting"]
        for tech in self.techs:
            if tech["job"] is None and waiting:
                job = waiting.pop(0)
                cell = f.robots[job["robot"]].pos(t)
                job["tech"], job["status"], job["assigned"] = tech["id"], "en route", t
                job["arrive"] = t + int(f.grid.distance(tech["cell"], cell))
                tech["job"] = job
            job = tech["job"]
            if job is None:
                continue
            r = f.robots[job["robot"]]
            if job["status"] == "en route" and t >= job["arrive"]:
                job["status"], job["start"] = "repairing", t
                job["end"] = t + H.REPAIR_S[job["component"]]
                tech["cell"] = r.pos(t)
                r.frozen = REPAIR_STATE
                r.states = np.array([REPAIR_STATE], dtype=np.int8)
            if job["status"] == "repairing" and t >= job["end"]:
                job["status"] = "done"
                tech["job"] = None
                f._finish_repair(r, t, job)

    def on_freeze(self, cell: int, t: int) -> None:
        pass

    def fix(self, t: int) -> None:
        pass


@dataclass
class Tech:
    id: int
    agent: int  # id in the reservation table (>= number of robots)
    base: int
    t0: int = 0
    path: list[int] = field(default_factory=list)
    job: dict | None = None
    dirty: bool = False  # the booked route is no longer walkable: replan

    def pos(self, t: int) -> int:
        return self.path[max(0, min(len(self.path) - 1, t - self.t0))]


class CorridorCrew:
    """Technicians as priority agents walking on booked corridors."""

    tracks = True

    def __init__(self, fleet: "Fleet") -> None:
        self.f = fleet
        n = fleet.cfg.n_robots
        self.bases = choose_tech_bases(fleet.grid, fleet.homes, fleet.chargers, fleet.cfg.techs)
        fleet.rt.forbid = frozenset(self.bases)
        fleet.rt.robot_limit = n
        self.techs = [Tech(id=i, agent=n + i, base=b, path=[b]) for i, b in enumerate(self.bases)]
        for tech in self.techs:
            fleet.rt.reserve(tech.agent, 0, tech.path)
        self.retry_at: dict[int, int] = {}  # job id -> earliest tick to try again
        self._depth = 0

    # -------------------------------------------------------------- routing
    def _obstacles(self, tech: Tech, t: int) -> set[int]:
        f = self.f
        obs = {cell for cell, (agent, since) in f.rt.park.items() if agent != tech.agent and since <= t}
        for r in f.robots:  # stopped or dwelling robots (lifting, picking, charging)
            p = r.pos(t)
            if r.frozen is not None or p == r.pos(t + 6):
                obs.add(p)
        for other in self.techs:
            if other is not tech:
                obs.update(other.path[max(0, t - other.t0):])
        obs.discard(tech.pos(t))
        return obs

    def plan(self, tech: Tech, t: int) -> None:
        """Book the technician's current duty: go + repair + return, or just return."""
        f, grid = self.f, self.f.grid
        cur, obs = tech.pos(t), self._obstacles(tech, t)
        job, full, stuck = tech.job, None, False
        if job is not None and job["status"] == "en route":
            robot_cell = f.robots[job["robot"]].pos(t)
            best = None
            for stand in grid.neighbors[robot_cell]:
                if stand in obs:
                    continue
                p = bfs_path(grid, cur, stand, obs)
                if p is not None and (best is None or len(p) < len(best)):
                    best = p
            back = bfs_path(grid, best[-1], tech.base, obs) if best is not None else None
            if back is not None:
                job["arrive"] = t + len(best) - 1
                full = best + [best[-1]] * H.REPAIR_S[job["component"]] + back[1:]
            else:  # cannot reach the robot (or get home again) right now: try again shortly
                job["status"], job["tech"] = "waiting", None
                self.retry_at[job["id"]] = t + 5
                tech.job = job = None
        if full is None:
            back = bfs_path(grid, cur, tech.base, obs)
            stay = max(0, job["end"] - t) if job is not None and job["status"] == "repairing" else 0
            full = [cur] * stay + (back if back is not None else [cur])
            stuck = back is None
        self._claim(tech, t, full)
        tech.dirty = stuck  # no way home yet: stay put and retry

    def _claim(self, tech: Tech, t: int, full: list[int]) -> None:
        """Reserve the corridor; every robot whose booked route crosses it replans or stops."""
        f, rt = self.f, self.f.rt
        tech.t0, tech.path, tech.dirty = t, full, False
        rt.release(tech.agent)
        end = len(full) - 1
        hit = []
        for j in f.robots:
            if j.frozen is not None:
                continue
            last, bad = len(j.path) - 1, False
            for kk in range(max(0, t - j.t0), last + 1):
                dt = j.t0 + kk - t
                if full[min(dt, end)] == j.path[kk]:  # same cell, same second
                    bad = True
                    break
                if kk > 0 and 1 <= dt <= end and full[dt] == j.path[kk - 1] and full[dt - 1] == j.path[kk]:  # swap
                    bad = True
                    break
            if not bad and j.path[last] in full[max(0, j.t0 + last - t):]:  # parks where the technician will walk
                bad = True
            if bad:
                hit.append((j, f._remaining(j, t)))
        for j, _ in hit:
            rt.release(j.id)
        rt.reserve(tech.agent, t, full)
        for j, legs in hit:
            f.reroutes += 1
            if not f._try_plan(j, t, legs, restore=False):
                j.resume, j.blocked = legs, True
                f._freeze(j, t, BLOCKED_STATE)
        f._resolve(t)

    # -------------------------------------------------------------- hooks
    def on_freeze(self, cell: int, t: int) -> None:
        """A robot stopped on ``cell``: any technician booked to walk through it must replan."""
        for tech in self.techs:
            if cell in tech.path[max(0, t + 1 - tech.t0):]:
                tech.dirty = True

    def fix(self, t: int) -> None:
        if self._depth > 5:
            return
        self._depth += 1
        for tech in self.techs:
            if tech.dirty:
                self.plan(tech, t)
        self._depth -= 1

    # -------------------------------------------------------------- tick
    def step(self, t: int) -> None:
        f = self.f
        for tech in self.techs:
            job = tech.job
            if job is None:
                continue
            r = f.robots[job["robot"]]
            if job["status"] == "en route" and t >= job["arrive"]:
                job["status"], job["start"] = "repairing", t
                job["end"] = t + H.REPAIR_S[job["component"]]
                r.frozen = REPAIR_STATE
                r.states = np.array([REPAIR_STATE], dtype=np.int8)
                f.stopped_cells.add(tech.pos(t))  # the technician at work blocks the cell like a stopped robot
                f.stop_version += 1
            if job["status"] == "repairing" and t >= job["end"]:
                f.stopped_cells.discard(tech.pos(t))
                f.stop_version += 1
                job["status"] = "done"
                tech.job = None
                f._finish_repair(r, t, job)
        waiting = [j for j in f.jobs if j["status"] == "waiting" and self.retry_at.get(j["id"], 0) <= t]
        for tech in self.techs:
            if tech.job is None and waiting:  # next job straight from where the technician stands
                job = waiting.pop(0)
                tech.job = job
                job["tech"], job["status"], job["assigned"] = tech.id, "en route", t
                self.plan(tech, t)
            elif tech.dirty and t % 4 == 0:
                self.plan(tech, t)
