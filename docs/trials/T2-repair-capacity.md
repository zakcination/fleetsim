# T2 · How many technicians does a fleet need?

**Status:** pre-registered on 2026-11-09, before any T2 run. Results are appended below the line; the protocol is not edited afterwards.

**Disclosure.** Before writing this, one smoke run (50 robots, aged fleet, normal faults, 2 technicians, run-to-failure) showed a mean time to repair of 1,957 s, of which 1,695 s was waiting for a technician. That run shaped H1 and is not part of the trial data.

## Background

A failed robot stops where it stands, blocks the aisle, and waits for a technician. Repair capacity therefore behaves like the classic *machine-repair queue*: with too few technicians, most downtime is spent waiting, not repairing. This trial measures how much throughput each extra technician buys back. The plan's original T2 ("health-aware dispatch") overlapped with T3's maintenance policies, so T2 was redefined before any run.

The health model is a teaching model (rates in `src/fleetsim/health.py`), so the numbers are about this model, not a real fleet. What should transfer is the shape: queueing-dominated downtime and diminishing returns.

## Hypotheses

- **H1.** At frequent faults (×12) with 1 technician, more than half of mean time to repair is spent waiting for the technician.
- **H2.** At frequent faults, going from 1 to 2 technicians recovers at least 50% of the throughput lost to faults; going from 3 to 4 recovers less than 10%.
- **H3 (safety).** Every run is collision-free, including all fault and replanning events.

## Protocol

| Factor | Levels |
|---|---|
| Fault rate | 0 (baseline), 4 (normal), 12 (frequent) |
| Technicians | 1, 2, 3, 4 (baseline runs: 2; technicians are idle without faults) |
| Fixed | 50 robots, load 1.0, nearest-pair dispatch, batteries on with 4 chargers, aged fleet (initial wear U(0, 0.6)), run-to-failure maintenance |
| Replications | 10 seeds (0–9), common random numbers: same orders, homes, initial wear and per-tick fault draws across arms |

Each run: 600 s warm-up, then 3,600 s measured. **Throughput lost to faults** = 1 − tasks/h ÷ tasks/h of the fault-free run with the same seed. **Recovered share** going from c to c + 1 technicians = (loss(c) − loss(c + 1)) / loss(c), computed per seed and averaged, with a 95% t-interval.

**Pass bars.** H1: the lower 95% bound of waiting ÷ MTTR is above 0.5. H2: the mean recovered share 1→2 is ≥ 0.5 and the mean recovered share 3→4 is < 0.1. H3: zero collisions across all runs.

Reproduce:

```bash
fleetsim bench --robots 50 --loads 1.0 --allocators nearest --battery --initial-wear 0.6 --faults 4 12 --techs 1 2 3 4 --replications 10 --no-db --no-parquet --out results/T2
```

```bash
fleetsim bench --robots 50 --loads 1.0 --allocators nearest --battery --initial-wear 0.6 --faults 0 --techs 2 --replications 10 --no-db --no-parquet --out results/T2-baseline
```

---

## Results

*Not yet run.*
