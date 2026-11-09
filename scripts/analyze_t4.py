"""Analyse trials T4 and T4b (technician corridors): ``python scripts/analyze_t4.py [T4|T4b]``.

Run the bench command in the trial's write-up under docs/trials/ first.
"""

import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from fleetsim.stats import t_half_width  # noqa: E402


def ci(x) -> tuple[float, float, float]:
    x = np.asarray(x, dtype=float)
    m, h = float(np.nanmean(x)), t_half_width(x)
    return m, m - h, m + h


NAME = sys.argv[1] if len(sys.argv) > 1 else "T4"
runs = pd.read_csv(f"results/{NAME}/runs.csv")
print("runs", len(runs), "| robot collisions", int(runs.collisions.sum()))
on = runs[runs.corridors]
print("corridor arms: technician conflicts", int(on.tech_conflicts.sum()), "| robots on technician bases", int(on.robots_on_tech_bases.sum()))

cols = ["throughput_per_h", "order_wait_s", "order_wait_p95_s", "availability", "failures", "mttr_s", "repair_queue_s",
        "tech_walk_s", "blocked_share", "corridor_reroutes", "tech_at_base_share"]
print(runs.groupby(["faults", "corridors"])[cols].mean().round(3).T.to_string())

t2b = pd.read_csv("results/T2b/runs.csv").query("techs == 2")
for f in (4.0, 12.0):
    a = runs[(runs.faults == f) & ~runs.corridors].set_index("seed").throughput_per_h
    b = t2b[t2b.faults == f].set_index("seed").throughput_per_h
    print(f"faults x{f:g}: off arm reproduces T2b exactly: {bool((a - b).abs().max() < 1e-9)}")

fig, axes = plt.subplots(1, 3, figsize=(12.5, 3.9))
for f, color in ((4.0, "#4C72B0"), (12.0, "#C44E52")):
    g = runs[runs.faults == f]
    w = {c: g.pivot(index="seed", columns="corridors", values=c) for c in ("throughput_per_h", "tech_walk_s", "mttr_s", "order_wait_s")}
    ratio = w["throughput_per_h"][True] / w["throughput_per_h"][False]
    m, lo, hi = ci(ratio)
    print(f"faults x{f:g}: tasks/h on/off = {m:.3f} [{lo:.3f}, {hi:.3f}]")
    for name in ("tech_walk_s", "mttr_s", "order_wait_s"):
        d = w[name][True] - w[name][False]
        dm, dlo, dhi = ci(d)
        print(f"   {name}: off {w[name][False].mean():.0f}, on {w[name][True].mean():.0f}, paired diff {dm:+.0f} [{dlo:+.0f}, {dhi:+.0f}]")
    x = 0 if f == 4.0 else 1
    axes[0].errorbar([x], [100 * (m - 1)], yerr=[[100 * (m - lo)], [100 * (hi - m)]], fmt="o", ms=8, capsize=6, color=color)
    for k, (name, ax) in enumerate((("tech_walk_s", axes[1]), ("mttr_s", axes[2]))):
        for j, arm in enumerate((False, True)):
            mm, l2, h2 = ci(w[name][arm])
            ax.errorbar([x + (j - 0.5) * 0.25], [mm], yerr=[[mm - l2], [h2 - mm]], fmt="o" if arm else "s", ms=7, capsize=5,
                        color=color, mfc=color if arm else "white", label=("corridors on" if arm else "timer (off)") if f == 4.0 else None)
axes[0].axhline(0, color="black", lw=1)
axes[0].axhline(-2, color="#4C72B0", lw=1, ls=":"); axes[0].axhline(-5, color="#C44E52", lw=1, ls=":")
axes[0].set_title("Throughput change with corridors (%)\n(dotted: pre-registered limits)", fontsize=10)
axes[1].set_title("Technician walk per job (s)", fontsize=10)
axes[2].set_title("Mean time to repair (s)", fontsize=10)
for ax in axes:
    ax.set_xticks([0, 1], ["faults ×4", "faults ×12"]); ax.set_xlim(-0.6, 1.6); ax.grid(alpha=0.3)
axes[1].legend(frameon=False, fontsize=8)
fig.suptitle(f"Trial {NAME} · 50 robots, 2 technicians, batteries off · 10 seeds per cell, paired, 95% intervals", fontsize=11)
fig.tight_layout(); fig.savefig(f"results/{NAME}/{NAME.lower()}.png", dpi=150)
print(f"wrote results/{NAME}/{NAME.lower()}.png")

if NAME != "T4":  # did the base fix help? Same seeds, corridor arms, against T4
    old = pd.read_csv("results/T4/runs.csv")
    for f in (4.0, 12.0):
        a = runs[(runs.faults == f) & runs.corridors].set_index("seed")
        b = old[(old.faults == f) & old.corridors].set_index("seed")
        m, lo, hi = ci(a.throughput_per_h / b.throughput_per_h)
        print(f"faults x{f:g}: corridor arm tasks/h {NAME} / T4 = {m:.3f} [{lo:.3f}, {hi:.3f}]"
              f" | mean {b.throughput_per_h.mean():.1f} -> {a.throughput_per_h.mean():.1f}")
    on = runs[runs.corridors].sort_values("throughput_per_h")
    print("slowest corridor runs:")
    print(on[["run_id", "throughput_per_h", "failures", "availability", "mttr_s", "repair_queue_s", "blocked_share", "wall_s"]].head(4).to_string(index=False))
