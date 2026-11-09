"""Plot trial T1 from results/T1 and results/T1-frontier (run the commands in docs/trials/T1-allocation.md first)."""

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

from fleetsim.stats import t_half_width  # noqa: E402

paired = pd.read_csv("results/T1/paired.csv")
front = pd.read_csv("results/T1-frontier/runs.csv")

fig, (a, b) = plt.subplots(1, 2, figsize=(12, 4.2))
colors = {"greedy": "#4C72B0", "nearest": "#55A868", "hungarian_aging(k=5,a=0.25)": "#C44E52"}
labels = {"greedy": "FIFO greedy", "nearest": "nearest-pair greedy", "hungarian_aging(k=5,a=0.25)": "aging Hungarian (a = 0.25)"}
hi = paired[paired.load == 1.3]
for i, (pol, g) in enumerate(hi.groupby("policy")):
    g = g.sort_values("n_robots")
    x = [str(n) for n in g.n_robots]
    a.errorbar([j + (i - 1) * 0.12 for j in range(len(x))], g.ratio, yerr=[g.ratio - g.ratio_lo, g.ratio_hi - g.ratio],
               fmt="o", capsize=4, color=colors[pol], label=labels[pol])
a.axhline(1.0, color="#DD8452", lw=1.5, label="Hungarian (k = 5) = 1.0")
a.axhline(0.95, color="grey", lw=1, ls=":", label="H1 pass bar (0.95)")
a.set_xticks(range(3), ["10", "50", "100"])
a.set_xlabel("robots")
a.set_ylabel("throughput / Hungarian (paired by seed)")
a.set_title("Load 1.3: nearest-pair matches Hungarian; FIFO is 12–15% behind", fontsize=10)
a.legend(fontsize=8, frameon=False, loc="lower right")
a.grid(alpha=0.3)

g = front.groupby("aging")
thr, mx, p95 = g.throughput_per_h.mean(), g.order_wait_max_s.mean(), g.order_wait_p95_s.mean()
thr_ci, mx_ci = g.throughput_per_h.apply(t_half_width), g.order_wait_max_s.apply(t_half_width)
b.errorbar(mx, thr, xerr=mx_ci, yerr=thr_ci, fmt="-o", color="#C44E52", capsize=3, label="max order wait")
b.plot(p95, thr, "--s", color="#8172B2", label="p95 order wait")
for lam in thr.index:
    b.annotate(f"a = {lam:g}", (mx[lam], thr[lam]), textcoords="offset points", xytext=(6, 4), fontsize=8)
b.set_xlabel("order wait (s)")
b.set_ylabel("tasks / h")
b.set_title("Aging frontier, 50 robots, load 1.3: small aging halves the max wait", fontsize=10)
b.legend(fontsize=8, frameon=False)
b.grid(alpha=0.3)
fig.suptitle("Trial T1 · 10 seeds per cell, common random numbers, 95% intervals", fontsize=11)
fig.tight_layout()
fig.savefig("results/T1/t1.png", dpi=150)
print("wrote results/T1/t1.png")
