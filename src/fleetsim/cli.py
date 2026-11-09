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
                    load=a.load, seed=a.seed)
    res = run(cfg, log_progress=True)
    print(json.dumps(analytics.summarize(res), indent=2))
    if a.db or a.parquet:
        frames = analytics.to_frames(res)
        if a.db:
            analytics.write_sqlite(frames, a.db)
        if a.parquet:
            analytics.write_parquet(frames, a.parquet)


def _cmd_bench(a: argparse.Namespace) -> None:
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    db = out / "fleetsim.db"
    if db.exists():
        db.unlink()
    rows = []
    for load in a.loads:
        for n in a.robots:
            for alloc in a.allocators:
                cfg = SimConfig(n_robots=n, allocator=alloc, k=a.k, ticks=a.ticks, warmup=a.warmup,
                                load=load, seed=a.seed)
                res = run(cfg)
                s = analytics.summarize(res)
                rows.append(s)
                print(f"{s['run_id']:>32}  {s['throughput_per_h']:7.0f} tasks/h  util {s['utilization']:.2f}  "
                      f"wait {s['order_wait_s']:6.1f}s  plan {s['plan_ms_mean']:.1f}ms  "
                      f"collisions {s['collisions']}  ({res.wall_s:.1f}s)", flush=True)
                frames = analytics.to_frames(res)
                analytics.write_sqlite(frames, db)
                if not a.no_parquet:
                    analytics.write_parquet(frames, out / "parquet")
    summary = pd.DataFrame(rows)
    summary.to_csv(out / "summary.csv", index=False)
    viz.benchmark_chart(summary, out / "benchmark.png")
    print(f"wrote {out/'summary.csv'}, {out/'benchmark.png'}, {db}")


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
    b.add_argument("--seed", type=int, default=0)
    b.add_argument("--out", default="results")
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
