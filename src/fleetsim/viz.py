"""Matplotlib outputs: benchmark chart and fleet animation (GIF)."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib import animation  # noqa: E402
from matplotlib.colors import ListedColormap  # noqa: E402

from .sim import BUSY_STATES, SimResult  # noqa: E402

ALLOC_COLORS = {"greedy": "#4C72B0", "hungarian(k=5)": "#DD8452"}


def benchmark_chart(summary: pd.DataFrame, path: str | Path) -> None:
    """Throughput, order wait and planner time vs fleet size, per allocator and load."""
    fig, axes = plt.subplots(1, 3, figsize=(13, 3.8))
    loads = sorted(summary["load"].unique())
    styles = {ld: ls for ld, ls in zip(loads, ["--", "-", ":"])}
    panels = [
        ("throughput_per_h", "Throughput (tasks / h)"),
        ("order_wait_s", "Mean order wait to assignment (s)"),
        ("plan_ms_mean", "Planner time per errand (ms)"),
    ]
    for ax, (col, title) in zip(axes, panels):
        for (alloc, load), g in summary.groupby(["allocator", "load"]):
            g = g.sort_values("n_robots")
            ax.plot(g["n_robots"], g[col], styles[load], marker="o",
                    color=ALLOC_COLORS.get(alloc, None), label=f"{alloc}, load {load:g}")
        ax.set_title(title, fontsize=10)
        ax.set_xlabel("robots")
        ax.set_xticks(sorted(summary["n_robots"].unique()))
        ax.grid(alpha=0.3)
    axes[0].legend(fontsize=8, frameon=False)
    fig.suptitle("fleetsim v0.1 - LoRR warehouse crop, space-time A* + prioritized planning", fontsize=11)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def animate(res: SimResult, path: str | Path, t_start: int = 0, n_frames: int = 150, step: int = 2,
            fps: int = 12, dpi: int = 70) -> None:
    """Animated GIF of robots moving; orange = carrying out an order, grey = idle/going home."""
    g = res.grid
    base = np.zeros((g.height, g.width), dtype=np.int8)  # 0 obstacle, 1 floor, 2 pod slot, 3 station
    for idx in g.free_cells():
        base[divmod(idx, g.width)] = 1
    for idx in g.pods:
        base[divmod(idx, g.width)] = 2
    for idx in g.stations:
        base[divmod(idx, g.width)] = 3
    cmap = ListedColormap(["#3a3a3a", "#f4f4f4", "#d8e6f3", "#5cb85c"])

    fig, ax = plt.subplots(figsize=(g.width / 9, g.height / 9 + 0.5))
    ax.imshow(base, cmap=cmap, vmin=0, vmax=3, interpolation="nearest")
    ax.set_xticks([])
    ax.set_yticks([])
    scat = ax.scatter([], [], s=14, edgecolors="black", linewidths=0.3)
    title = ax.set_title("", fontsize=9)
    W = g.width
    ticks = range(t_start, min(res.total_ticks, t_start + n_frames * step), step)

    def frame(t):
        cells = res.traj[t]
        busy = np.isin(res.state[t], BUSY_STATES)
        scat.set_offsets(np.c_[cells % W, cells // W])
        scat.set_facecolors(np.where(busy[:, None], [[1.0, 0.55, 0.1, 1]], [[0.6, 0.6, 0.6, 1]]))
        title.set_text(f"{res.config.n_robots} robots, {res.config.allocator}   t = {t} s   "
                       f"busy {busy.sum()}/{len(busy)}")
        return scat, title

    anim = animation.FuncAnimation(fig, frame, frames=list(ticks), blit=False)
    anim.save(str(path), writer=animation.PillowWriter(fps=fps), dpi=dpi)
    plt.close(fig)
