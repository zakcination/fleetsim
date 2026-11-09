import numpy as np
import pytest

from fleetsim.checker import find_conflicts
from fleetsim.grid import Grid
from fleetsim.planner import ReservationTable, plan_errand, space_time_astar

CORRIDOR = """
E.....E
@@@.@@@
S.....S
"""


@pytest.fixture
def corridor():
    return Grid.from_ascii(CORRIDOR)


def test_astar_free_path_is_shortest(corridor):
    rt = ReservationTable()
    a, b = corridor.idx(0, 0), corridor.idx(0, 6)
    path = space_time_astar(corridor, rt, 0, a, 0, b, final=True)
    assert path[0] == a and path[-1] == b
    assert len(path) - 1 == corridor.distance(a, b) == 6


def test_astar_avoids_vertex_reservation(corridor):
    rt = ReservationTable()
    mid = corridor.idx(0, 3)
    # agent 1 sits on the middle cell during t=0..5, then leaves through the gap
    rt.reserve(1, 0, [mid] * 6 + [corridor.idx(1, 3), corridor.idx(2, 3)])
    a, b = corridor.idx(0, 0), corridor.idx(0, 6)
    path = space_time_astar(corridor, rt, 0, a, 0, b, final=True)
    assert path is not None
    for t, cell in enumerate(path):
        assert rt.cell_free(cell, t, 0)
    assert len(path) - 1 > 6  # had to wait


def test_astar_avoids_swap_conflict():
    g = Grid.from_ascii("S..E")
    rt = ReservationTable()
    # agent 1 moves right->left along the single row and parks at the far left
    rt.reserve(1, 0, [g.idx(0, 3), g.idx(0, 2), g.idx(0, 1), g.idx(0, 0)])
    # agent 0 wants to go left->right: impossible without passing through agent 1
    assert space_time_astar(g, rt, 0, g.idx(0, 0), 0, g.idx(0, 3), final=True, max_expansions=5000) is None


def test_final_goal_waits_until_cell_is_no_longer_used(corridor):
    rt = ReservationTable()
    goal = corridor.idx(0, 3)
    # agent 1 passes through the goal at t=20
    p1 = [corridor.idx(2, 3)] * 18 + [corridor.idx(1, 3), goal, corridor.idx(0, 2), corridor.idx(0, 1)]
    rt.reserve(1, 0, p1)
    path = space_time_astar(corridor, rt, 0, corridor.idx(0, 6), 0, goal, final=True)
    assert path is not None and len(path) - 1 > 19


def test_reservation_release_roundtrip(corridor):
    rt = ReservationTable()
    path = [corridor.idx(0, 0), corridor.idx(0, 1), corridor.idx(0, 2)]
    rt.reserve(3, 5, path)
    assert not rt.cell_free(corridor.idx(0, 1), 6, 0)
    assert not rt.cell_free(corridor.idx(0, 2), 100, 0)  # parked
    rt.release(3)
    assert rt.vertex == {} and rt.edge == {} and rt.park == {} and rt.cell_last == {}


def test_prioritized_errands_are_collision_free():
    """Many robots planned one after another on a small warehouse never collide."""
    text = """
E.........E
.SSSS.SSSS.
.@@@@.@@@@.
.SSSS.SSSS.
...........
.SSSS.SSSS.
.@@@@.@@@@.
.SSSS.SSSS.
E.........E
"""
    g = Grid.from_ascii(text)
    rng = np.random.default_rng(0)
    homes = g.choose_parking(8)
    rt = ReservationTable()
    for i, h in enumerate(homes):
        rt.reserve(i, 0, [h])
    plans = {}
    for i, h in enumerate(homes):
        rt.release(i)
        pod = int(rng.choice(g.pods))
        st = int(rng.choice(g.stations))
        res = plan_errand(g, rt, i, h, 0, [(pod, 1), (st, 3), (pod, 1)], h)
        assert res is not None
        rt.reserve(i, 0, res[0])
        plans[i] = res[0]
    T = max(len(p) for p in plans.values()) + 5
    traj = np.array([[plans[i][min(t, len(plans[i]) - 1)] for i in range(len(homes))] for t in range(T)])
    assert find_conflicts(traj, g) == []
