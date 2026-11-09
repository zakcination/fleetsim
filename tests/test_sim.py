import numpy as np
import pytest

from fleetsim import analytics
from fleetsim.allocation import ALLOCATORS, GreedyAllocator, HungarianAllocator, NearestPairAllocator, register_allocator
from fleetsim.checker import find_conflicts
from fleetsim.grid import Grid, read_map_lines, DEFAULT_MAP
from fleetsim.orders import Order, OrderStream
from fleetsim.sim import BUSY_STATES, SimConfig, run


@pytest.fixture(scope="module")
def grid():
    return Grid.from_file()


def test_lorr_map_loads(grid):
    rows = read_map_lines(DEFAULT_MAP)
    assert (len(rows), len(rows[0])) == (140, 500)
    assert (grid.height, grid.width) == (72, 99)
    assert len(grid.pods) > 1000 and len(grid.stations) >= 10
    assert all(grid.char(s) == "E" for s in grid.stations)
    assert all(grid.char(p) == "S" for p in grid.pods)


def test_parking_keeps_map_connected(grid):
    homes = grid.choose_parking(100)
    assert len(set(homes)) == 100
    reach = grid.bfs(grid.stations[0], blocked=set(homes))
    for cell in grid.free_cells():
        if cell not in homes:
            assert reach[cell] < np.iinfo(np.int32).max


def test_poisson_rate():
    s = OrderStream([1, 2, 3], [9], rate=0.5, seed=1)
    n = sum(len(s.arrivals(t)) for t in range(20_000))
    assert abs(n / 20_000 - 0.5) < 0.02


def test_hungarian_beats_or_ties_greedy_on_total_cost(grid):
    rng = np.random.default_rng(3)
    homes = grid.choose_parking(30)
    robots = [(i, h) for i, h in enumerate(homes)]
    pending = [Order(i, int(rng.choice(grid.pods)), grid.stations[0], 0) for i in range(30)]

    def total(pairs):
        pos = dict(robots)
        return sum(grid.distance(pos[r], o.pod) for r, o in pairs)

    g = GreedyAllocator().assign(0, robots, pending, grid)
    h = HungarianAllocator(k=1).assign(0, robots, pending, grid)
    assert len(g) == len(h) == 30
    assert total(h) <= total(g)


def test_nearest_pair_is_a_valid_matching(grid):
    rng = np.random.default_rng(5)
    homes = grid.choose_parking(10)
    robots = list(enumerate(homes))
    pending = [Order(i, int(rng.choice(grid.pods)), grid.stations[0], 0) for i in range(25)]
    pairs = NearestPairAllocator().assign(0, robots, pending, grid)
    assert len(pairs) == 10
    assert len({r for r, _ in pairs}) == 10 and len({o.id for _, o in pairs}) == 10


def test_custom_allocator_plugs_in(grid):
    @register_allocator("test_round_robin")
    class RoundRobin:
        name = "test_round_robin"

        def __init__(self, **_):
            pass

        def assign(self, t, robots, pending, grid):
            return list(zip([r for r, _ in robots], pending))

    try:
        res = run(SimConfig(n_robots=8, allocator="test_round_robin", ticks=300, warmup=0, seed=2), grid=grid)
        assert find_conflicts(res.traj, grid) == []
        assert any(o.assigned >= 0 for o in res.orders)
    finally:
        ALLOCATORS.pop("test_round_robin", None)


@pytest.mark.parametrize("allocator", ["greedy", "nearest", "hungarian"])
def test_simulation_is_collision_free(grid, allocator):
    cfg = SimConfig(n_robots=40, allocator=allocator, ticks=600, warmup=100, load=1.2, seed=7)
    res = run(cfg, grid=grid)
    assert find_conflicts(res.traj, grid) == []
    s = analytics.summarize(res)
    assert s["collisions"] == 0
    assert s["throughput_per_h"] > 0
    assert 0 < s["utilization"] <= 1
    # every completed order went pod -> station -> pod in order
    for o in res.orders:
        if 0 <= o.completed < res.total_ticks:
            assert o.assigned <= o.picked <= o.at_station <= o.serviced <= o.completed
            assert res.traj[o.at_station, o.robot] == o.station
            assert res.traj[o.completed, o.robot] == o.pod


def test_logs_roundtrip(tmp_path, grid):
    cfg = SimConfig(n_robots=5, ticks=200, warmup=0, seed=1)
    res = run(cfg, grid=grid)
    frames = analytics.to_frames(res)
    assert len(frames["ticks"]) == 200 * 5
    analytics.write_sqlite(frames, tmp_path / "f.db")
    analytics.write_sqlite(frames, tmp_path / "f.db")  # idempotent per run_id
    analytics.write_parquet(frames, tmp_path / "pq")
    import sqlite3

    import pandas as pd

    with sqlite3.connect(tmp_path / "f.db") as con:
        n = con.execute("SELECT COUNT(*) FROM ticks").fetchone()[0]
    assert n == 1000
    assert len(pd.read_parquet(tmp_path / "pq" / "ticks")) == 1000
    busy = frames["ticks"]["state"].isin(["to_pod", "lift", "to_station", "service", "return", "drop"]).mean()
    assert busy == pytest.approx(np.isin(res.state, BUSY_STATES).mean())
