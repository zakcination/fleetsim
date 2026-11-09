"""Independent collision checker for logged fleet trajectories."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .grid import Grid


@dataclass(frozen=True)
class Conflict:
    kind: str  # "vertex" | "edge" | "teleport" | "obstacle"
    t: int
    agents: tuple[int, ...]
    cells: tuple[int, ...]


def find_conflicts(traj: np.ndarray, grid: Grid | None = None) -> list[Conflict]:
    """Check a ``[T, N]`` array of cell indices (row t = positions at tick t).

    Reports vertex conflicts (two robots on one cell), edge conflicts (two robots
    swapping cells between t and t+1), and, if ``grid`` is given, illegal moves
    (non-adjacent jumps, standing on an obstacle).
    """
    traj = np.asarray(traj)
    T, N = traj.shape
    out: list[Conflict] = []
    for t in range(T):
        row = traj[t]
        cells, counts = np.unique(row, return_counts=True)
        for c in cells[counts > 1]:
            out.append(Conflict("vertex", t, tuple(int(a) for a in np.nonzero(row == c)[0]), (int(c),)))
        if grid is not None:
            for a in range(N):
                if not grid.is_free(int(row[a])):
                    out.append(Conflict("obstacle", t, (a,), (int(row[a]),)))
        if t + 1 < T:
            nxt = traj[t + 1]
            moved = row != nxt
            pos_now = {int(row[a]): a for a in np.nonzero(moved)[0]}
            for a in np.nonzero(moved)[0]:
                b = pos_now.get(int(nxt[a]))
                if b is not None and b > a and int(nxt[b]) == int(row[a]):
                    out.append(Conflict("edge", t, (int(a), int(b)), (int(row[a]), int(nxt[a]))))
                if grid is not None and int(nxt[a]) not in grid.neighbors[int(row[a])]:
                    out.append(Conflict("teleport", t, (int(a),), (int(row[a]), int(nxt[a]))))
    return out
