"""Analyse trials T2 / T2b (repair capacity) and T3 / T3b (maintenance policy).

Run the bench commands in docs/trials/T2-repair-capacity.md and T3-maintenance.md first.
Prints the tables used in the write-ups and saves results/T2/t2.png and results/T3/t3.png.
"""

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from fleetsim.stats import t_half_width  # noqa: E402


def mean_ci(x) -> tuple[float, float]:
    x = np.asarray(x, dtype=float)
    return float(np.nanmean(x)), t_half_width(x)


def fmt(x, digits=3) -> str:
    m, h = mean_ci(x)
    return f"{m:.{digits}f} ± {h:.{digits}f}"


def t2(name: str = "T2") -> None:
    runs = pd.read_csv(f"results/{name}/runs.csv")
    base = pd.read_csv(f"results/{name}-baseline/runs.csv").set_index("seed")["throughput_per_h"]
    runs["loss"] = 1 - runs["throughput_per_h"] / runs["seed"].map(base)
    runs["wait_share"] = runs["repair_wait_s"] / runs["mttr_s"]
    print(f"== {name}: baseline (no faults) tasks/h:", fmt(base, 1), "| collisions:", int(runs.collisions.sum()))
    rows = []
    for (f, c), g in runs.groupby(["faults", "techs"]):
        rows.append(dict(faults=f, techs=c, tasks_h=fmt(g.throughput_per_h, 1), loss=fmt(g.loss), availability=fmt(g.availability),
                         failures=fmt(g.failures, 1), mttr_s=fmt(g.mttr_s, 0), tech_wait_s=fmt(g.repair_wait_s, 0),
                         wait_share=fmt(g.wait_share), blocked=fmt(g.blocked_share)))
    print(pd.DataFrame(rows).to_string(index=False))
    print("-- recovered share of lost throughput per added technician (paired by seed)")
    for f, g in runs.groupby("faults"):
        wide = g.pivot(index="seed", columns="techs", values="loss")
        for c in (1, 2, 3):
            rec = (wide[c] - wide[c + 1]) / wide[c]
            gain = (wide[c] - wide[c + 1]) * runs["seed"].map(base).groupby(runs["seed"]).first()
            m, h = mean_ci(wide[c])
            note = "" if m - h > 0 else "   [loss at this level not distinguishable from 0: share not evaluable]"
            print(f"   faults x{f:g}: {c} -> {c + 1} technicians: recovered share {fmt(rec)}, gain {fmt(gain, 1)} tasks/h{note}")
        thr = g.pivot(index="seed", columns="techs", values="throughput_per_h")
        for c in (1, 2, 3, 4):
            r = thr[c] / base
            m, h = mean_ci(r)
            print(f"   faults x{f:g}, {c} technician(s): tasks/h vs baseline {m:.3f} [{m - h:.3f}, {m + h:.3f}]")

    fig, (a, b) = plt.subplots(1, 2, figsize=(11.5, 4))
    for f, color in ((4.0, "#4C72B0"), (12.0, "#C44E52")):
        g = runs[runs.faults == f].groupby("techs")
        a.errorbar(g.loss.mean().index, 100 * g.loss.mean(), yerr=100 * g.loss.apply(t_half_width), fmt="-o", capsize=4,
                   color=color, label=f"faults ×{f:g}")
        b.errorbar(g.mttr_s.mean().index, g.mttr_s.mean() / 60, yerr=g.mttr_s.apply(t_half_width) / 60, fmt="-o", capsize=4,
                   color=color, label=f"MTTR, faults ×{f:g}")
        b.plot(g.repair_wait_s.mean().index, g.repair_wait_s.mean() / 60, "--s", color=color, alpha=0.7,
               label=f"of which waiting for a technician, ×{f:g}")
    a.axhline(0, color="black", lw=1)
    a.set_xlabel("technicians"); a.set_ylabel("throughput lost vs fault-free baseline (%)"); a.set_xticks([1, 2, 3, 4])
    a.set_title("Each added technician buys back less (below 0 = beats the baseline)", fontsize=10); a.legend(frameon=False, fontsize=8); a.grid(alpha=0.3)
    b.set_xlabel("technicians"); b.set_ylabel("minutes per repair"); b.set_xticks([1, 2, 3, 4])
    b.set_title("With few technicians, downtime is mostly waiting", fontsize=10); b.legend(frameon=False, fontsize=8); b.grid(alpha=0.3)
    fig.suptitle(f"Trial {name} · 50 robots, load 1.0, aged fleet · 10 seeds per cell, 95% intervals", fontsize=11)
    fig.tight_layout(); fig.savefig(f"results/{name}/{name.lower()}.png", dpi=150); plt.close(fig)
    print(f"wrote results/{name}/{name.lower()}.png")


def t3(name: str = "T3") -> None:
    runs = pd.read_csv(f"results/{name}/runs.csv")
    print(f"\n== {name}: collisions:", int(runs.collisions.sum()))
    rows = []
    for m, g in runs.groupby("maintenance"):
        rows.append(dict(policy=m, tasks_h=fmt(g.throughput_per_h, 1), availability=fmt(g.availability), failures=fmt(g.failures, 1),
                         services=fmt(g.services, 1), mttr_s=fmt(g.mttr_s, 0), blocked=fmt(g.blocked_share), p95_wait_s=fmt(g.order_wait_p95_s, 0)))
    print(pd.DataFrame(rows).to_string(index=False))
    thr = runs.pivot(index="seed", columns="maintenance", values="throughput_per_h")
    fails = runs.pivot(index="seed", columns="maintenance", values="failures")
    for a_, b_ in (("condition", "none"), ("condition", "interval"), ("interval", "none")):
        r = thr[a_] / thr[b_]
        m, h = mean_ci(r)
        print(f"   tasks/h {a_} / {b_}: {m:.3f} [{m - h:.3f}, {m + h:.3f}]")
    red = 1 - fails["condition"] / fails["none"]
    m, h = mean_ci(red)
    print(f"   failure reduction, condition vs none: {m:.3f} [{m - h:.3f}, {m + h:.3f}]")
    red = 1 - fails["interval"] / fails["none"]
    m, h = mean_ci(red)
    print(f"   failure reduction, interval vs none:  {m:.3f} [{m - h:.3f}, {m + h:.3f}]")

    order, names = ["none", "interval", "condition"], ["run to failure", "fixed interval", "condition-based"]
    fig, axes = plt.subplots(1, 3, figsize=(12, 3.8))
    for ax, (col, title, scale) in zip(axes, (("throughput_per_h", "Tasks per hour", 1), ("availability", "Availability (%)", 100),
                                              ("failures", "Failures in 4 h (services hatched)", 1))):
        g = runs.groupby("maintenance")[col]
        colors = ["#8c8c8c", "#4C72B0", "#55A868"]
        if col == "failures":  # counts: bars from zero
            ax.bar(names, [g.mean()[k] for k in order], yerr=[g.apply(t_half_width)[k] for k in order], capsize=5, color=colors)
            s = runs.groupby("maintenance")["services"].mean()
            ax.bar(names, [s[k] for k in order], bottom=[g.mean()[k] for k in order], color="none", edgecolor="black", hatch="//")
        else:  # a zoomed axis, so points and intervals rather than bars
            for i, k in enumerate(order):
                ax.errorbar([names[i]], [scale * g.mean()[k]], yerr=[scale * g.apply(t_half_width)[k]], fmt="o", ms=8, capsize=6, color=colors[i])
            ax.margins(x=0.25)
        ax.set_title(title, fontsize=10); ax.grid(alpha=0.3, axis="y"); ax.tick_params(axis="x", labelsize=8)
    fig.suptitle(f"Trial {name} · 50 robots, faults ×4, 2 technicians, 4 h · 10 seeds, 95% intervals", fontsize=11)
    fig.tight_layout(); fig.savefig(f"results/{name}/{name.lower()}.png", dpi=150); plt.close(fig)
    print(f"wrote results/{name}/{name.lower()}.png")


if __name__ == "__main__":
    for name in sys.argv[1:] or ["T2", "T2b", "T3", "T3b"]:
        if not Path(f"results/{name}/runs.csv").exists():
            continue
        (t2 if name.startswith("T2") else t3)(name)
