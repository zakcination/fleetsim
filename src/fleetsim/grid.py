"""Warehouse grid world loaded from a League of Robot Runners (LoRR) map.

LoRR 2026 map legend (see Start-Kit ``Input_Output_Format.md``):

* ``@`` / ``T`` – hard obstacle (here: shelving that cannot be driven through)
* ``.``          – free floor
* ``S``          – *service point*, traversable; the pick-up goal of a LoRR task.
                   fleetsim treats every ``S`` cell as the storage slot of one pod.
* ``E``          – *emitter point*, traversable; the delivery goal of a LoRR task.
                   fleetsim treats ``E`` cells as pick stations.

Cells are addressed by a flat integer index ``r * width + c``.
"""

from __future__ import annotations

from collections import OrderedDict, deque
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

OBSTACLE_CHARS = frozenset("@T")
UNREACHABLE = np.iinfo(np.int32).max

MAPS_DIR = Path(__file__).resolve().parent / "maps"
DEFAULT_MAP = MAPS_DIR / "warehouse_long_corridor_large.map"
# A 72 x 99 "fulfilment cell" cut from the top-left of the LoRR map: 6 shelf
# columns x 32 shelf rows, the left-wall pick stations and the top cross-aisle.
DEFAULT_CROP = (0, 72, 0, 99)


def read_map_lines(path: str | Path) -> list[str]:
    """Parse a MovingAI/LoRR ``.map`` file and return its grid rows."""
    lines = Path(path).read_text().splitlines()
    header: dict[str, str] = {}
    i = 0
    while i < len(lines) and lines[i].strip() != "map":
        parts = lines[i].split()
        if len(parts) == 2:
            header[parts[0]] = parts[1]
        i += 1
    if i == len(lines):
        raise ValueError(f"{path}: missing 'map' line")
    height, width = int(header["height"]), int(header["width"])
    rows = [ln.rstrip("\n") for ln in lines[i + 1 : i + 1 + height]]
    if len(rows) != height or any(len(r) != width for r in rows):
        raise ValueError(f"{path}: grid does not match header {height}x{width}")
    return rows


@dataclass
class Grid:
    """Static warehouse layout plus cached shortest-path distance fields."""

    rows: list[str]
    station_side: str = "left"  # "left": only E cells on the left wall; "all": every E
    height: int = field(init=False)
    width: int = field(init=False)

    def __post_init__(self) -> None:
        self.height, self.width = len(self.rows), len(self.rows[0])
        self.free = np.array([[ch not in OBSTACLE_CHARS for ch in row] for row in self.rows])
        self._restrict_to_largest_component()
        self.neighbors: list[tuple[int, ...]] = [() for _ in range(self.height * self.width)]
        for idx in self.free_cells():
            r, c = divmod(idx, self.width)
            nbrs = []
            for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                rr, cc = r + dr, c + dc
                if 0 <= rr < self.height and 0 <= cc < self.width and self.free[rr, cc]:
                    nbrs.append(rr * self.width + cc)
            self.neighbors[idx] = tuple(nbrs)
        self.pods = [i for i in self.free_cells() if self.char(i) == "S"]
        emitters = [i for i in self.free_cells() if self.char(i) == "E"]
        if self.station_side == "left":
            min_col = min(e % self.width for e in emitters)
            emitters = [e for e in emitters if e % self.width == min_col]
        self.stations = emitters
        if not self.pods or not self.stations:
            raise ValueError("map has no pods (S) or no stations (E)")
        self._dist_cache: OrderedDict[int, np.ndarray] = OrderedDict()
        self.dist_cache_size = 2048

    # ------------------------------------------------------------------ factory
    @classmethod
    def from_file(
        cls,
        path: str | Path = DEFAULT_MAP,
        crop: tuple[int, int, int, int] | None = DEFAULT_CROP,
        station_side: str = "left",
    ) -> "Grid":
        rows = read_map_lines(path)
        if crop is not None:
            r0, r1, c0, c1 = crop
            rows = [row[c0:c1] for row in rows[r0:r1]]
        return cls(rows, station_side=station_side)

    @classmethod
    def from_ascii(cls, text: str, station_side: str = "all") -> "Grid":
        rows = [ln for ln in text.strip("\n").splitlines()]
        return cls(rows, station_side=station_side)

    # ------------------------------------------------------------------ helpers
    def _restrict_to_largest_component(self) -> None:
        seen = np.zeros_like(self.free)
        best: list[tuple[int, int]] = []
        for r0 in range(self.height):
            for c0 in range(self.width):
                if not self.free[r0, c0] or seen[r0, c0]:
                    continue
                comp, q = [], deque([(r0, c0)])
                seen[r0, c0] = True
                while q:
                    r, c = q.popleft()
                    comp.append((r, c))
                    for rr, cc in ((r - 1, c), (r + 1, c), (r, c - 1), (r, c + 1)):
                        if 0 <= rr < self.height and 0 <= cc < self.width and self.free[rr, cc] and not seen[rr, cc]:
                            seen[rr, cc] = True
                            q.append((rr, cc))
                if len(comp) > len(best):
                    best = comp
        keep = np.zeros_like(self.free)
        for r, c in best:
            keep[r, c] = True
        self.free = keep

    def free_cells(self) -> list[int]:
        rs, cs = np.nonzero(self.free)
        return [int(r) * self.width + int(c) for r, c in zip(rs, cs)]

    def char(self, idx: int) -> str:
        r, c = divmod(idx, self.width)
        return self.rows[r][c]

    def rc(self, idx: int) -> tuple[int, int]:
        return divmod(idx, self.width)

    def idx(self, r: int, c: int) -> int:
        return r * self.width + c

    def is_free(self, idx: int) -> bool:
        r, c = divmod(idx, self.width)
        return bool(self.free[r, c])

    @property
    def n_free(self) -> int:
        return int(self.free.sum())

    # ------------------------------------------------------------- distances
    def bfs(self, source: int, blocked: set[int] | frozenset[int] = frozenset()) -> np.ndarray:
        """Unit-cost BFS distances from ``source`` (int32, UNREACHABLE if none)."""
        dist = np.full(self.height * self.width, UNREACHABLE, dtype=np.int32)
        dist[source] = 0
        q = deque([source])
        nb = self.neighbors
        d = dist  # local alias
        while q:
            u = q.popleft()
            du = d[u] + 1
            for v in nb[u]:
                if d[v] == UNREACHABLE and v not in blocked:
                    d[v] = du
                    q.append(v)
        return dist

    def dist_to(self, goal: int) -> np.ndarray:
        """Distance field to ``goal`` (grid is undirected, so also *from* goal). LRU cached."""
        cache = self._dist_cache
        field_ = cache.get(goal)
        if field_ is not None:
            cache.move_to_end(goal)
            return field_
        field_ = self.bfs(goal)
        cache[goal] = field_
        if len(cache) > self.dist_cache_size:
            cache.popitem(last=False)
        return field_

    def distance(self, a: int, b: int) -> int:
        return int(self.dist_to(b)[a])

    # ------------------------------------------------------------- parking
    def choose_parking(self, n: int, rng: np.random.Generator | None = None) -> list[int]:
        """Pick ``n`` parking (home) cells for idle robots.

        A parked robot is a permanent obstacle in the planner, so parking cells are
        plain floor (``.``), never a pod slot or station, never adjacent to a
        station, and chosen greedily such that blocking all of them keeps every
        other free cell connected. That guarantees every task stays feasible.
        """
        stations = set(self.stations)
        near_station = {v for s in self.stations for v in self.neighbors[s]}
        cands = [
            i
            for i in self.free_cells()
            if self.char(i) == "." and i not in near_station and i not in stations and len(self.neighbors[i]) >= 3
        ]
        if rng is not None:
            cands = list(rng.permutation(cands))
        else:  # deterministic: spread by stepping through a strided order
            cands = cands[::2] + cands[1::2]
        chosen: list[int] = []
        blocked: set[int] = set()
        n_free = self.n_free
        probe = self.stations[0]
        for c in cands:
            if len(chosen) == n:
                break
            if c == probe or any(nb in blocked for nb in self.neighbors[c]):
                continue  # keep parked robots non-adjacent: cheap way to avoid walls
            blocked.add(c)
            reach = int((self.bfs(probe, blocked) != UNREACHABLE).sum())
            if reach == n_free - len(blocked):
                chosen.append(c)
            else:
                blocked.discard(c)
        if len(chosen) < n:
            raise ValueError(f"could only find {len(chosen)} safe parking cells for {n} robots")
        return chosen
