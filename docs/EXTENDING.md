# Extending fleetsim

Three extension points cover most experiments: dispatch policies, maps and the logs.

## 1. A new dispatch policy

Register a class and it becomes available everywhere: `SimConfig(allocator=...)`, `fleetsim run --allocator ...` and `fleetsim bench --allocators ...`.

```python
# my_policies.py
import numpy as np
from fleetsim.allocation import register_allocator

@register_allocator("oldest_first_any_robot")
class OldestFirstAnyRobot:
    """Toy policy: oldest orders go to free robots in id order (ignores distance)."""

    name = "oldest_first_any_robot"

    def __init__(self, **_):          # receives k=<SimConfig.k>; ignore what you don't need
        pass

    def assign(self, t, robots, pending, grid):
        # robots:  list of (robot_id, current_cell) that are free right now
        # pending: unassigned orders, oldest first (order.pod, order.station, order.created)
        # grid:    fleetsim.grid.Grid; grid.dist_to(cell) is a cached BFS distance field
        # return:  list of (robot_id, order); each robot and order at most once
        return list(zip([rid for rid, _ in robots], pending))
```

```python
import my_policies  # noqa: F401  (registers the policy)
from fleetsim import SimConfig, run
from fleetsim.analytics import summarize

res = run(SimConfig(n_robots=50, allocator="oldest_first_any_robot", load=1.2))
print(summarize(res))
```

Rules your policy gets for free: the planner books collision-free routes for whatever you assign, and if a plan fails the order goes back to `pending`. The built-ins are good templates: `GreedyAllocator`, `NearestPairAllocator` and `HungarianAllocator` in [`src/fleetsim/allocation.py`](../src/fleetsim/allocation.py). The test `tests/test_sim.py::test_custom_allocator_plugs_in` shows the minimal contract.

## 2. A different map

Any MovingAI/LoRR `.map` file works if it has `S` (pod slots) and `E` (stations) cells:

```python
from fleetsim import Grid, SimConfig, run

grid = Grid.from_file("path/to/warehouse.map", crop=None, station_side="all")
res = run(SimConfig(n_robots=80), grid=grid)
```

`crop=(r0, r1, c0, c1)` cuts a sub-region. `station_side="left"` keeps only the left-most column of `E` cells. Parking cells are chosen so that parked robots never disconnect the floor (`Grid.choose_parking`).

## 3. The logs

```bash
fleetsim run --n 50 --allocator nearest --db results/my.db --parquet results/my_parquet
```

| Table | Grain | Columns |
|---|---|---|
| `runs` | simulation | config, offered rate, wall time |
| `ticks` | robot × second | `tick, robot, row, col, state, moved, waiting, order_id` |
| `orders` | order | `created, assigned, picked, at_station, serviced, completed, free_flow` |
| `plans` | planner call | `tick, robot, ms, ok, expansions, n_pending` |

Example with DuckDB on the Parquet files (`pip install duckdb`):

```python
import duckdb
duckdb.sql("""
  SELECT run_id, AVG(waiting::INT) AS wait_share
  FROM 'results/my_parquet/ticks/*.parquet'
  WHERE state IN ('to_pod', 'to_station', 'return')
  GROUP BY run_id
""").show()
```

## 4. Health, faults and maintenance

Everything is off by default, and then results are bit-identical to v0.1. Switch parts on through `SimConfig`:

```python
from fleetsim import SimConfig, run
from fleetsim.analytics import summarize

cfg = SimConfig(n_robots=50, allocator="nearest", load=1.0,
                battery=True, chargers=4, charge_at=25,        # batteries and chargers
                faults=4, techs=2, initial_wear=0.6,           # fault rate x4 (normal), aged fleet
                maintenance="condition", service_wear=0.5)     # or "none" / "interval"
k = summarize(run(cfg))
print(k["availability"], k["failures"], k["mttr_s"], k["repair_wait_s"])
```

The rates live in [`src/fleetsim/health.py`](../src/fleetsim/health.py). A new maintenance policy is a few lines in `Fleet._health_tick`: set `r.want_service = True`, and the robot finishes its job, drives home and is serviced there. The fault model draws one uniform number per robot per tick from its own stream, so policy arms with the same seed see the same faults.

## 5. The web demo

[`web/live.html`](../web/live.html) is a single self-contained file: the map, the planner, the policies and the three.js renderer are all inline. Open it in a browser, edit, reload. Dispatch policies live in `Sim.allocate`, KPIs in `Sim.kpis`, and the advice panel in `insights()`.
