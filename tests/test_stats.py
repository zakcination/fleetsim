import numpy as np
import pandas as pd
import pytest

from fleetsim import stats
from fleetsim.allocation import AgingHungarianAllocator, HungarianAllocator
from fleetsim.grid import Grid
from fleetsim.orders import Order
from fleetsim.sim import SimConfig, run


def test_t_half_width_matches_textbook():
    x = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
    # t(0.975, 4) = 2.776, sd = 1.5811, n = 5
    assert stats.t_half_width(x) == pytest.approx(2.776 * 1.5811 / np.sqrt(5), rel=1e-3)
    assert np.isnan(stats.t_half_width([1.0]))


def test_paired_ratio_removes_seed_noise():
    rows = []
    for seed in range(6):
        base = 100 + 30 * seed  # large seed-to-seed variation
        rows += [dict(n_robots=10, load=1.3, allocator="a", seed=seed, throughput_per_h=base),
                 dict(n_robots=10, load=1.3, allocator="b", seed=seed, throughput_per_h=1.1 * base)]
    p = stats.paired(pd.DataFrame(rows), baseline="a")
    assert p.loc[0, "ratio"] == pytest.approx(1.1)
    assert p.loc[0, "ratio_hi"] - p.loc[0, "ratio_lo"] < 1e-9


def test_same_seed_gives_every_policy_the_same_orders():
    g = Grid.from_file()
    a = run(SimConfig(n_robots=10, allocator="greedy", ticks=300, warmup=0, seed=3), grid=g)
    b = run(SimConfig(n_robots=10, allocator="nearest", ticks=300, warmup=0, seed=3), grid=g)
    assert [(o.created, o.pod, o.station) for o in a.orders] == [(o.created, o.pod, o.station) for o in b.orders]
    assert a.homes == b.homes


def test_aging_zero_equals_hungarian_and_aging_prefers_old_orders():
    g = Grid.from_file()
    homes = g.choose_parking(2)
    robots = list(enumerate(homes))
    near = min(g.pods, key=lambda p: g.distance(homes[0], p))
    far = max(g.pods, key=lambda p: g.distance(homes[0], p))
    pending = [Order(0, far, g.stations[0], created=0), Order(1, near, g.stations[0], created=990)]
    one = [(0, homes[0])]
    plain = HungarianAllocator(k=1).assign(1000, one, pending, g)
    assert AgingHungarianAllocator(k=1, aging=0).assign(1000, one, pending, g) == plain
    assert plain[0][1].id == 1  # travel only: take the near, young order
    assert AgingHungarianAllocator(k=1, aging=1.0).assign(1000, one, pending, g)[0][1].id == 0  # old order wins
