import numpy as np
import pandas as pd
import pytest

from fleetsim import analytics, health as H
from fleetsim.checker import find_conflicts
from fleetsim.grid import Grid
from fleetsim.sim import BLOCKED, CHARGING, FAILED, REPAIR, Fleet, SimConfig, run


@pytest.fixture(scope="module")
def grid():
    return Grid.from_file()


def test_health_off_reproduces_t1_exactly(grid):
    """The health layer must not change v0.1 behaviour when it is switched off."""
    runs = pd.read_csv("results/T1/runs.csv")
    s = analytics.summarize(run(SimConfig(n_robots=10, allocator="greedy", load=1.3, seed=0), grid=grid),
                            check_collisions=False)
    row = runs[runs.run_id == s["run_id"]].iloc[0]
    for k in ("throughput_per_h", "utilization", "order_wait_p95_s", "backlog_end"):
        assert s[k] == pytest.approx(row[k], abs=1e-9)


def test_faults_and_repairs_stay_collision_free(grid):
    cfg = SimConfig(n_robots=40, load=1.0, allocator="nearest", battery=True, chargers=3, faults=12, techs=1,
                    initial_wear=0.7, ticks=1800, warmup=0, seed=4)
    res = run(cfg, grid=grid)
    assert find_conflicts(res.traj, grid) == []
    kinds = {j["kind"] for j in res.jobs}
    assert "failure" in kinds
    assert any(j["end"] is not None for j in res.jobs)  # at least one repair finished
    states = set(np.unique(res.state))
    assert FAILED in states or REPAIR in states
    # a robot that is down never moves
    down = np.isin(res.state[:-1], (FAILED, REPAIR))
    assert (res.traj[1:][down] == res.traj[:-1][down]).all()


def test_failed_robot_blocks_and_others_route_around(grid):
    f = Fleet(SimConfig(n_robots=20, load=1.2, faults=0, maintenance="condition", service_wear=2.0, seed=1), grid=grid)
    for t in range(200):
        f.step(t)
    busy = next(r for r in f.robots if r.order is not None and r.legs)
    f._stop(busy, 200, "motor_l")
    cell = busy.pos(200)
    for r in f.robots:
        if r is not busy and r.frozen is None:
            assert cell not in r.path[max(0, 201 - r.t0):] and r.path[-1] != cell
    assert busy.order.completed == -1  # the order is on hold, not done
    for t in range(201, 900):
        f.step(t)
    assert not busy.failed  # a technician repaired it and it resumed


def test_charging_keeps_batteries_up(grid):
    res = run(SimConfig(n_robots=12, load=0.8, battery=True, chargers=3, charge_at=30, ticks=5400, warmup=0, seed=2), grid=grid)
    assert (res.state == CHARGING).any()
    assert res.soc.min() > 5
    assert not any(j["component"] == "depleted" for j in res.jobs)


def test_condition_maintenance_services_worn_robots_at_home(grid):
    res = run(SimConfig(n_robots=15, load=0.8, maintenance="condition", service_wear=0.3, initial_wear=0.6,
                        ticks=1800, warmup=0, seed=3), grid=grid)
    services = [j for j in res.jobs if j["kind"] == "service"]
    assert services
    homes = set(res.homes)
    assert all(res.traj[j["created"], j["robot"]] in homes for j in services)


def test_same_seed_same_health_draws_across_policies(grid):
    a = Fleet(SimConfig(n_robots=10, faults=4, maintenance="none", seed=5), grid=grid)
    b = Fleet(SimConfig(n_robots=10, faults=4, maintenance="condition", seed=5), grid=grid)
    assert [r.hp.wear_l for r in a.robots] == [r.hp.wear_l for r in b.robots]
    assert np.array_equal(a.hrng.random(10), b.hrng.random(10))


def test_hazard_grows_with_wear():
    young = H.Health(soc=90, pack=100, temp_l=24, temp_r=24, wear_l=0.0, wear_r=0.0, lift_wear=0.0)
    old = H.Health(soc=90, pack=100, temp_l=24, temp_r=24, wear_l=0.9, wear_r=0.9, lift_wear=0.9)
    p = lambda h: sum(v for _, v in H.hazards(h, moving=True, lifting=True, battery=True, faults=1))
    assert p(old) > 5 * p(young)
    assert H.pick_fault(0.0, H.hazards(old, True, True, True, 1)) == "motor_l"
    assert H.pick_fault(0.999, H.hazards(old, True, True, True, 1)) is None


def test_health_kpis(grid):
    res = run(SimConfig(n_robots=20, load=1.0, battery=True, faults=12, techs=1, initial_wear=0.7, ticks=1200, warmup=200, seed=6), grid=grid)
    k = analytics.summarize(res, check_collisions=False)
    assert 0 < k["availability"] <= 1
    assert k["failures"] >= 0 and k["blocked_share"] >= 0
    frames = analytics.to_frames(res)
    assert "soc" in frames["ticks"] and "jobs" in frames


def test_failure_on_another_robots_future_parking_cell(grid):
    """Regression: a robot that fails on a cell booked as someone else's future home must
    take the cell; the other robot replans or waits. (Crashed trial T2's first launch.)"""
    f = Fleet(SimConfig(n_robots=40, load=1.1, allocator="nearest", maintenance="condition", service_wear=2.0, seed=3), grid=grid)
    traj, hit = [], None
    for t in range(1500):
        f.step(t)
        if hit is None and t > 50:
            for r in f.robots:
                holder = f.rt.park.get(r.pos(t))
                if not r.failed and r.frozen is None and holder is not None and holder[0] != r.id:
                    hit = (r.id, holder[0], t)
                    f._stop(r, t, "motor_l")  # must not raise
                    break
        traj.append([r.pos(t) for r in f.robots])
    assert hit is not None, "scenario did not occur; pick another seed"
    assert find_conflicts(np.array(traj), grid) == []
    assert not f.robots[hit[0]].failed  # repaired and moving again


# ----------------------------------------------------------------- technician corridors
def test_state_codes_match_technicians_module():
    from fleetsim import sim, technicians

    assert technicians.BLOCKED_STATE == sim.BLOCKED and technicians.REPAIR_STATE == sim.REPAIR


def test_timer_crew_reproduces_t2b_exactly(grid):
    """The technician refactor must not change the default (timer) model."""
    row = pd.read_csv("results/T2b/runs.csv").query("faults == 12 and techs == 2 and seed == 3").iloc[0]
    s = analytics.summarize(run(SimConfig(n_robots=50, load=1.0, allocator="nearest", faults=12, techs=2, initial_wear=0.6, seed=3),
                                grid=grid), check_collisions=False)
    for k in ("throughput_per_h", "availability", "mttr_s", "failures"):
        assert s[k] == pytest.approx(row[k], abs=1e-9)


def test_corridors_keep_technicians_and_robots_apart(grid):
    from fleetsim.checker import find_tech_conflicts

    cfg = SimConfig(n_robots=45, load=1.0, allocator="nearest", faults=12, techs=2, initial_wear=0.7,
                    ticks=2400, warmup=0, seed=5, tech_corridors=True)
    res = run(cfg, grid=grid)
    assert find_conflicts(res.traj, grid) == []
    assert find_tech_conflicts(res.traj, res.tech_traj, grid) == []  # incl. technicians never jumping cells
    assert not np.isin(res.traj, res.tech_bases).any()  # robots never enter a technician base
    assert any(j["end"] is not None for j in res.jobs)
    assert res.reroutes > 0  # robots did yield to corridors
    # the same seed has the same robot homes and orders with corridors off
    off = Fleet(SimConfig(n_robots=45, load=1.0, allocator="nearest", faults=12, techs=2, initial_wear=0.7, seed=5), grid=grid)
    assert off.homes == res.homes


def test_technician_walks_out_repairs_from_next_cell_and_returns(grid):
    f = Fleet(SimConfig(n_robots=20, load=1.0, allocator="nearest", maintenance="condition", service_wear=2.0,
                        techs=1, seed=2, tech_corridors=True), grid=grid)
    for t in range(300):
        f.step(t)
    victim = next(r for r in f.robots if r.order is not None and r.legs and r.pos(300) // grid.width > 25)
    f._stop(victim, 300, "motor_l")
    tech, job = f.crew.techs[0], victim.job
    stand = left = home = None
    for t in range(301, 1500):
        f.step(t)
        p = tech.pos(t)
        assert all(r.pos(t) != p for r in f.robots)
        if left is None and p != tech.base:
            left = t
        if stand is None and job["status"] == "repairing":
            stand = p
        if job["status"] == "done" and home is None and p == tech.base:
            home = t
    assert left is not None and stand is not None and home is not None
    assert stand in grid.neighbors[f._repair_cells[job["id"]]]  # repaired from the next cell, not on top of the robot
    assert job["end"] - job["start"] == 300 and not victim.failed

