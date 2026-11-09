"""Replication statistics: confidence intervals and paired comparisons.

Runs that share a seed share the order stream and robot homes (common random
numbers), so policies are compared *paired by seed*, which removes most of the
seed-to-seed noise from the difference.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats as st

DESIGN = ["n_robots", "load", "allocator"]
METRICS = [
    "throughput_per_h", "utilization", "travel_wait_share", "congestion_delay_s",
    "order_wait_s", "order_wait_p95_s", "order_wait_p99_s", "order_wait_max_s",
    "backlog_end", "plan_ms_mean", "plan_fail_rate", "collisions",
]


def t_half_width(x: np.ndarray, level: float = 0.95) -> float:
    x = np.asarray(x, dtype=float)
    x = x[~np.isnan(x)]
    if len(x) < 2:
        return float("nan")
    return float(st.t.ppf(0.5 + level / 2, len(x) - 1) * x.std(ddof=1) / np.sqrt(len(x)))


def aggregate(runs: pd.DataFrame, by: list[str] = DESIGN, metrics: list[str] = METRICS) -> pd.DataFrame:
    """Mean and 95% half-width (``<metric>_ci``) per design cell."""
    metrics = [m for m in metrics if m in runs]
    rows = []
    for key, g in runs.groupby(by, dropna=False, sort=True):
        row = dict(zip(by, key if isinstance(key, tuple) else (key,)))
        row["replications"] = len(g)
        for m in metrics:
            row[m] = float(g[m].mean())
            row[f"{m}_ci"] = t_half_width(g[m].to_numpy())
        rows.append(row)
    return pd.DataFrame(rows)


def paired(runs: pd.DataFrame, baseline: str, metric: str = "throughput_per_h",
           cell: list[str] = ["n_robots", "load"]) -> pd.DataFrame:
    """Per design cell: ratio policy/baseline paired by seed, mean and 95% interval."""
    rows = []
    for key, g in runs.groupby(cell, sort=True):
        wide = g.pivot_table(index="seed", columns="allocator", values=metric)
        if baseline not in wide:
            continue
        for alloc in wide.columns:
            if alloc == baseline:
                continue
            r = (wide[alloc] / wide[baseline]).dropna().to_numpy()
            hw = t_half_width(r)
            row = dict(zip(cell, key))
            row.update(policy=alloc, baseline=baseline, metric=metric, pairs=len(r),
                       ratio=float(r.mean()), ratio_lo=float(r.mean() - hw), ratio_hi=float(r.mean() + hw))
            rows.append(row)
    return pd.DataFrame(rows)
