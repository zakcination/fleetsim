"""Command line: ``fleetsim run`` (one simulation), ``fleetsim bench`` (README table), ``fleetsim gif``."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from . import analytics, viz
from .allocation import ALLOCATORS
from .sim import SimConfig, run


def _cmd_run(a: argparse.Namespace) -> None:
    cfg = SimConfig(n_robots=a.n, allocator=a.allocator, k=a.k, ticks=a.ticks, warmup=a.warmup,
                    load=a.load, seed=a.seed, battery=a.battery, faults=a.faults, techs=a.techs,
                    maintenance=a.maintenance, tech_corridors=a.corridors, idle_topup=a.idle_topup)
    res = run(cfg, log_progress=True)
    print(json.dumps(analytics.summarize(res), indent=2))
    if a.db or a.parquet:
        frames = analytics.to_frames(res)
        if a.db:
            analytics.write_sqlite(frames, a.db)
        if a.parquet:
            analytics.write_parquet(frames, a.parquet)


def _bench_one(cfg: SimConfig) -> dict:
    return analytics.summarize(run(cfg))


def _cmd_bench(a: argparse.Namespace) -> None:
    from multiprocessing import Pool

    from . import stats

    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    cfgs = []
    import itertools

    for load, n, alloc, faults, techs, maint, cor, top in itertools.product(a.loads, a.robots, a.allocators, a.faults, a.techs,
                                                                            a.maintenance, a.corridors, a.idle_topup):
        for aging in (a.aging if alloc == "hungarian_aging" else [a.aging[0]]):
            for rep in range(a.replications):
                cfgs.append(SimConfig(n_robots=n, allocator=alloc, k=a.k, aging=aging, ticks=a.ticks, warmup=a.warmup,
                                      load=load, seed=a.seed + rep, battery=a.battery, chargers=a.chargers,
                                      faults=faults, techs=techs, maintenance=maint, initial_wear=a.initial_wear,
                                      tech_corridors=cor == "on", idle_topup=top == "on"))
    logs = not (a.no_db and a.no_parquet)
    rows = []
    if logs or a.workers <= 1:
        db = out / "fleetsim.db"
        if not a.no_db and db.exists():
            db.unlink()
        for cfg in cfgs:
            res = run(cfg)
            s = analytics.summarize(res)
            rows.append(s)
            print(f"{s['run_id']:>36}  {s['throughput_per_h']:7.0f} tasks/h  util {s['utilization']:.2f}  "
                  f"wait {s['order_wait_s']:6.1f}s  plan {s['plan_ms_mean']:.1f}ms  "
                  f"collisions {s['collisions']}  ({res.wall_s:.1f}s)", flush=True)
            if logs:
                frames = analytics.to_frames(res)
                if not a.no_db:
                    analytics.write_sqlite(frames, db)
                if not a.no_parquet:
                    analytics.write_parquet(frames, out / "parquet")
    else:
        with Pool(a.workers) as pool:
            for i, s in enumerate(pool.imap(_bench_one, cfgs, chunksize=1), 1):
                rows.append(s)
                print(f"[{i}/{len(cfgs)}] {s['run_id']:>36}  {s['throughput_per_h']:7.0f} tasks/h  "
                      f"p95 wait {s['order_wait_p95_s']:6.0f}s  collisions {s['collisions']}", flush=True)
    runs = pd.DataFrame(rows)
    runs.to_csv(out / "runs.csv", index=False)
    if a.replications > 1:
        summary = stats.aggregate(runs)
        base = a.baseline or a.allocators[0]
        base_label = analytics.allocator_label(SimConfig(allocator=base, k=a.k, aging=a.aging[0]))
        stats.paired(runs, base_label).to_csv(out / "paired.csv", index=False)
    else:
        summary = runs
    summary.to_csv(out / "summary.csv", index=False)
    viz.benchmark_chart(summary, out / "benchmark.png")
    print(f"wrote {out}/runs.csv, summary.csv, benchmark.png" + (", paired.csv" if a.replications > 1 else ""))


def _cmd_gif(a: argparse.Namespace) -> None:
    cfg = SimConfig(n_robots=a.n, allocator=a.allocator, ticks=a.t_start + a.frames * a.step, warmup=0,
                    load=a.load, seed=a.seed)
    res = run(cfg)
    viz.animate(res, a.out, t_start=a.t_start, n_frames=a.frames, step=a.step)
    print(f"wrote {a.out}")


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(prog="fleetsim")
    sub = p.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("run", help="simulate one configuration")
    r.add_argument("--n", type=int, default=50)
    r.add_argument("--allocator", choices=sorted(ALLOCATORS), default="greedy")
    r.add_argument("--k", type=int, default=5)
    r.add_argument("--ticks", type=int, default=3600)
    r.add_argument("--warmup", type=int, default=600)
    r.add_argument("--load", type=float, default=0.85)
    r.add_argument("--seed", type=int, default=0)
    r.add_argument("--battery", action="store_true")
    r.add_argument("--faults", type=float, default=0.0)
    r.add_argument("--techs", type=int, default=2)
    r.add_argument("--maintenance", default="none", choices=["none", "interval", "condition"])
    r.add_argument("--corridors", action="store_true", help="technicians walk on priority corridors")
    r.add_argument("--idle-topup", action="store_true", help="idle robots top up their battery")
    r.add_argument("--db", help="append tick/order/plan logs to this SQLite file")
    r.add_argument("--parquet", help="write Parquet logs under this directory")
    r.set_defaults(func=_cmd_run)

    b = sub.add_parser("bench", help="N x allocator x load sweep -> results/")
    b.add_argument("--robots", type=int, nargs="+", default=[10, 50, 100])
    b.add_argument("--loads", type=float, nargs="+", default=[0.85, 1.3])
    b.add_argument("--allocators", nargs="+", choices=sorted(ALLOCATORS), default=["greedy", "hungarian"])
    b.add_argument("--k", type=int, default=5)
    b.add_argument("--ticks", type=int, default=3600)
    b.add_argument("--warmup", type=int, default=600)
    b.add_argument("--aging", type=float, nargs="+", default=[0.25], help="aging weights for hungarian_aging")
    b.add_argument("--replications", type=int, default=1, help="seeds per design cell (common random numbers)")
    b.add_argument("--baseline", help="allocator that paired.csv compares against (default: first)")
    b.add_argument("--workers", type=int, default=4, help="parallel processes when no logs are written")
    b.add_argument("--seed", type=int, default=0)
    b.add_argument("--battery", action="store_true", help="robots run on batteries and visit chargers")
    b.add_argument("--chargers", type=int, default=4)
    b.add_argument("--faults", type=float, nargs="+", default=[0.0], help="fault-rate multipliers (0 off, 4 normal, 12 frequent)")
    b.add_argument("--techs", type=int, nargs="+", default=[2], help="technician counts")
    b.add_argument("--maintenance", nargs="+", default=["none"], choices=["none", "interval", "condition"])
    b.add_argument("--initial-wear", type=float, default=0.15, help="parts start with wear ~ U(0, this)")
    b.add_argument("--idle-topup", nargs="+", default=["off"], choices=["off", "on"],
                   help="idle robots top up their battery when no orders are waiting")
    b.add_argument("--corridors", nargs="+", default=["off"], choices=["off", "on"],
                   help="technicians as timers (off) or walking on priority corridors (on)")
    b.add_argument("--out", default="results")
    b.add_argument("--no-db", action="store_true")
    b.add_argument("--no-parquet", action="store_true")
    b.set_defaults(func=_cmd_bench)

    gf = sub.add_parser("gif", help="render an animation")
    gf.add_argument("--n", type=int, default=50)
    gf.add_argument("--allocator", choices=sorted(ALLOCATORS), default="hungarian")
    gf.add_argument("--load", type=float, default=1.0)
    gf.add_argument("--t-start", type=int, default=300)
    gf.add_argument("--frames", type=int, default=150)
    gf.add_argument("--step", type=int, default=1)
    gf.add_argument("--seed", type=int, default=0)
    gf.add_argument("--out", default="docs/fleet.gif")
    gf.set_defaults(func=_cmd_gif)

    a = p.parse_args(argv)
    a.func(a)


if __name__ == "__main__":
    main()
