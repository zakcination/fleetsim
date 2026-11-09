import numpy as np

from fleetsim.checker import find_conflicts
from fleetsim.grid import Grid


def test_detects_vertex_conflict():
    traj = np.array([[0, 2], [1, 1]])
    kinds = [c.kind for c in find_conflicts(traj)]
    assert kinds == ["vertex"]


def test_detects_edge_swap():
    traj = np.array([[0, 1], [1, 0]])
    kinds = [c.kind for c in find_conflicts(traj)]
    assert kinds == ["edge"]


def test_following_is_not_a_conflict():
    traj = np.array([[0, 1], [1, 2], [2, 3]])
    assert find_conflicts(traj) == []


def test_detects_teleport_and_obstacle():
    g = Grid.from_ascii("S..E\n.@..")
    traj = np.array([[g.idx(0, 0)], [g.idx(1, 1)], [g.idx(1, 2)]])
    kinds = sorted(c.kind for c in find_conflicts(traj, g))
    assert kinds == ["obstacle", "teleport", "teleport"]
