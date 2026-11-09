# T1 · Is Hungarian's gain optimal matching or queue discipline?

**Status:** pre-registered on 2026-11-09, before any T1 run. Results are appended below the line and the protocol is not edited afterwards.

## Background

The v0.1 benchmark (one seed) showed Hungarian assignment completing 16–20% more tasks per hour than first-come-first-served greedy at offered load 1.3. Hungarian differs from FIFO greedy in two ways at once:

1. it solves the assignment optimally (minimum total travel), and
2. it chooses *which* orders to serve from a window of the oldest `2 × free robots`, favouring orders whose pods are near free robots.

Nearest-pair greedy keeps (2) and drops (1): same order window, no batching delay, but a greedy rather than optimal matching. Aging Hungarian keeps (1) and weakens (2) by subtracting `λ × age` from each order's cost.

## Hypotheses

- **H1.** At load 1.3, nearest-pair greedy reaches at least 95% of Hungarian's throughput at every fleet size. If true, most of the gain comes from queue discipline, not optimal matching.
- **H2.** Increasing the aging weight λ lowers the p95 order wait and lowers throughput monotonically, forming a fairness–throughput frontier.
- **H3 (control).** At load 0.85, all policies are within 2% of each other on throughput.

## Protocol

| Factor | Levels |
|---|---|
| Policy | `greedy` (FIFO), `nearest`, `hungarian` (k = 5), `hungarian_aging` (k = 5) |
| Fleet size N | 10, 50, 100 |
| Offered load | 0.85, 1.3 |
| Aging weight λ (`hungarian_aging` only) | 0.25 in the main grid; frontier at N = 50, load 1.3: 0, 0.05, 0.1, 0.25, 0.5, 1.0 |
| Replications | 10 seeds (0–9), common random numbers: the same seed gives every policy the same order stream and robot homes |

Each run: 600 s warm-up, then 3,600 s measured. Metrics: tasks/h, mean / p95 / max order wait (censored), utilization, collisions. Policies are compared with **paired** differences by seed; intervals are 95% t-intervals over the 10 seeds.

**Pass bars.** H1 holds if the lower 95% bound of `nearest / hungarian` throughput is ≥ 0.95 at load 1.3 for all N. H2 holds if p95 wait and throughput both decrease from λ = 0 to λ = 1.0 with non-overlapping intervals at the ends. H3 holds if every pairwise throughput difference at load 0.85 has a 95% interval inside ±2%.

Reproduce:

```bash
fleetsim bench --allocators greedy nearest hungarian hungarian_aging --robots 10 50 100 --loads 0.85 1.3 --replications 10 --no-db --no-parquet --out results/T1
```

```bash
fleetsim bench --allocators hungarian_aging --aging 0 0.05 0.1 0.25 0.5 1.0 --robots 50 --loads 1.3 --replications 10 --no-db --no-parquet --out results/T1-frontier
```

---

## Results

*Not yet run.*
