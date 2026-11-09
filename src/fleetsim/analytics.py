"""Tick-level logging (SQLite + Parquet) and fleet KPIs."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd

from .checker import find_conflicts, find_tech_conflicts
from .sim import BLOCKED, BUSY_STATES, CHARGING, DOWN_STATES, STATE_NAMES, TRAVEL_STATES, SimResult, config_dict


def run_id_of(res: SimResult) -> str:
    c = res.config
    alloc = f"{c.allocator}{c.aging:g}" if c.allocator == "hungarian_aging" else c.allocator
    health = ""
    if c.health_on:  # keep health arms apart; runs without health keep their v0.1 ids
        health = (f"_f{c.faults:g}_t{c.techs}_{c.maintenance}" + ("_bat" if c.battery else "")
                  + ("_cor" if c.tech_corridors else ""))
    return f"n{c.n_robots}_{alloc}_load{c.load:g}{health}_s{c.seed}"


def to_frames(res: SimResult, run_id: str | None = None) -> dict[str, pd.DataFrame]:
    run_id = run_id or run_id_of(res)
    T, N = res.traj.shape
    W = res.grid.width
    ticks = pd.DataFrame(
        {
            "run_id": run_id,
            "tick": np.repeat(np.arange(T, dtype=np.int32), N),
            "robot": np.tile(np.arange(N, dtype=np.int16), T),
            "row": (res.traj // W).ravel().astype(np.int16),
            "col": (res.traj % W).ravel().astype(np.int16),
            "state": pd.Categorical.from_codes(res.state.ravel(), STATE_NAMES).astype(str),
            "order_id": res.order_of.ravel(),
        }
    )
    # did the robot move between t-1 and t?  (False at t=0)
    moved = np.zeros_like(res.traj, dtype=bool)
    moved[1:] = res.traj[1:] != res.traj[:-1]
    ticks["moved"] = moved.ravel()
    # travelling (to_pod / to_station / return) but will not move on the next tick
    waiting = np.zeros_like(res.traj, dtype=bool)
    waiting[:-1] = np.isin(res.state[:-1], TRAVEL_STATES) & (res.traj[1:] == res.traj[:-1])
    ticks["waiting"] = waiting.ravel()

    orders = pd.DataFrame([o.__dict__ for o in res.orders])
    if orders.empty:
        orders = pd.DataFrame(columns=["id", "pod", "station", "created", "assigned", "robot", "picked",
                                       "at_station", "serviced", "completed", "free_flow"])
    orders = orders.rename(columns={"id": "order_id"})
    # planned times beyond the horizon have not happened yet
    for col in ("picked", "at_station", "serviced", "completed"):
        orders.loc[orders[col] >= T, col] = -1
    orders.insert(0, "run_id", run_id)

    plans = pd.DataFrame(res.plans)
    plans.insert(0, "run_id", run_id)

    cfg = config_dict(res.config)
    runs = pd.DataFrame([{**cfg, "run_id": run_id, "rate_per_tick": res.rate, "wall_s": res.wall_s,
                          "n_free_cells": res.grid.n_free, "n_pods": len(res.grid.pods),
                          "n_stations": len(res.grid.stations)}])
    frames = {"runs": runs, "ticks": ticks, "orders": orders, "plans": plans}
    if res.soc is not None:
        ticks["soc"] = res.soc.ravel()
    if res.motor_temp is not None:
        ticks["motor_temp"] = res.motor_temp.ravel()
    if res.jobs:
        jobs = pd.DataFrame(res.jobs).drop(columns=["status"])
        jobs.insert(0, "run_id", run_id)
        frames["jobs"] = jobs
    return frames


def write_sqlite(frames: dict[str, pd.DataFrame], db_path: str | Path) -> None:
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as con:
        run_id = frames["runs"]["run_id"].iloc[0]
        for name, df in frames.items():
            try:
                con.execute(f"DELETE FROM {name} WHERE run_id = ?", (run_id,))
            except sqlite3.OperationalError:
                pass  # table does not exist yet
            df.to_sql(name, con, if_exists="append", index=False, chunksize=50_000)
        con.execute("CREATE INDEX IF NOT EXISTS ix_ticks_run ON ticks(run_id, tick)")
        con.execute("CREATE INDEX IF NOT EXISTS ix_orders_run ON orders(run_id)")


def write_parquet(frames: dict[str, pd.DataFrame], out_dir: str | Path) -> None:
    out_dir = Path(out_dir)
    run_id = frames["runs"]["run_id"].iloc[0]
    for name, df in frames.items():
        d = out_dir / name
        d.mkdir(parents=True, exist_ok=True)
        df.to_parquet(d / f"{run_id}.parquet", index=False)


def allocator_label(cfg) -> str:
    if cfg.allocator == "hungarian":
        return f"hungarian(k={cfg.k})"
    if cfg.allocator == "hungarian_aging":
        return f"hungarian_aging(k={cfg.k},a={cfg.aging:g})"
    return cfg.allocator


def summarize(res: SimResult, check_collisions: bool = True) -> dict:
    """KPIs over the measured window [warmup, warmup + ticks)."""
    cfg = res.config
    T = res.total_ticks
    w0 = cfg.warmup
    S = res.state[w0:]
    hours = (T - w0) / 3600.0

    completed = [o for o in res.orders if w0 <= o.completed < T]
    created = [o for o in res.orders if o.created >= w0]
    # censored wait: orders still unassigned at the end count with their wait so far
    waits = np.array([(o.assigned if 0 <= o.assigned < T else T) - o.created for o in created], dtype=float)
    lead = np.array([o.completed - o.created for o in completed], dtype=float)
    delay = np.array([o.completed - o.assigned - o.free_flow for o in completed], dtype=float)

    travel = np.isin(res.state[w0:-1], TRAVEL_STATES)
    stood_still = res.traj[w0 + 1 :] == res.traj[w0:-1]
    plans = [p for p in res.plans if p["tick"] >= w0]
    ms = np.array([p["ms"] for p in plans]) if plans else np.zeros(1)

    out = {
        "run_id": run_id_of(res),
        "n_robots": cfg.n_robots,
        "allocator": allocator_label(cfg),
        "aging": cfg.aging if cfg.allocator == "hungarian_aging" else float("nan"),
        "seed": cfg.seed,
        "faults": cfg.faults,
        "techs": cfg.techs if cfg.health_on else float("nan"),
        "maintenance": cfg.maintenance,
        "battery": cfg.battery,
        "corridors": cfg.tech_corridors,
        "load": cfg.load,
        "orders_per_h": res.rate * 3600,
        "throughput_per_h": len(completed) / hours,
        "per_robot_per_h": len(completed) / hours / cfg.n_robots,
        "utilization": float(np.isin(S, BUSY_STATES).mean()),
        "travel_wait_share": float((travel & stood_still).sum() / max(travel.sum(), 1)),
        "congestion_delay_s": float(delay.mean()) if len(delay) else float("nan"),
        "order_wait_s": float(waits.mean()) if len(waits) else float("nan"),
        "order_wait_p95_s": float(np.percentile(waits, 95)) if len(waits) else float("nan"),
        "order_wait_p99_s": float(np.percentile(waits, 99)) if len(waits) else float("nan"),
        "order_wait_max_s": float(waits.max()) if len(waits) else float("nan"),
        "lead_time_p50_s": float(np.median(lead)) if len(lead) else float("nan"),
        "backlog_end": sum(1 for o in res.orders if o.assigned < 0),
        "plan_ms_mean": float(ms.mean()),
        "plan_ms_p95": float(np.percentile(ms, 95)),
        "planner_ms_per_tick": float(ms.sum() / (T - w0)),
        "plan_fail_rate": float(np.mean([not p["ok"] for p in plans])) if plans else 0.0,
        "wall_s": res.wall_s,
    }
    if cfg.health_on:
        out.update(health_kpis(res))
    if check_collisions:
        out["collisions"] = len(find_conflicts(res.traj, res.grid))
    return out


def health_kpis(res: SimResult) -> dict:
    """Availability, MTBF, MTTR and battery KPIs over the measured window."""
    cfg = res.config
    T, w0 = res.total_ticks, cfg.warmup
    S = res.state[w0:]
    up = ~np.isin(S, DOWN_STATES)
    fails = [j for j in res.jobs if j["kind"] == "failure" and w0 <= j["created"] < T]
    services = [j for j in res.jobs if j["kind"] == "service" and w0 <= j["created"] < T]
    repaired = [j for j in res.jobs if j["kind"] == "failure" and j["end"] is not None and w0 <= j["end"] < T]
    up_hours = float(up.sum()) / 3600
    out = {
        "availability": float(up.mean()),
        "failures": len(fails),
        "services": len(services),
        "mtbf_h": up_hours / len(fails) if fails else float("nan"),
        "mttr_s": float(np.mean([j["end"] - j["created"] for j in repaired])) if repaired else float("nan"),
        "repair_wait_s": float(np.mean([j["arrive"] - j["created"] for j in repaired])) if repaired else float("nan"),
        "repair_queue_s": float(np.mean([j["assigned"] - j["created"] for j in repaired])) if repaired else float("nan"),
        "tech_walk_s": float(np.mean([j["arrive"] - j["assigned"] for j in repaired])) if repaired else float("nan"),
        "corridor_reroutes": res.reroutes,
        "blocked_share": float((S == BLOCKED).mean()),
        "charging_share": float((S == CHARGING).mean()),
    }
    if res.tech_traj is not None:
        out["tech_conflicts"] = len(find_tech_conflicts(res.traj, res.tech_traj, res.grid))
        out["robots_on_tech_bases"] = int(np.isin(res.traj, res.tech_bases).sum())
        out["tech_at_base_share"] = float((res.tech_traj[w0:] == np.array(res.tech_bases)[None, :]).mean())
    if res.soc is not None:
        out["soc_min"] = float(res.soc[w0:].min())
        out["soc_mean"] = float(res.soc[w0:].mean())
    return out
