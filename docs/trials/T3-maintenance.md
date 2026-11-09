# T3 · Run to failure, fixed intervals, or condition-based maintenance?

**Status:** pre-registered on 2026-11-09, before any T3 run. Results are appended below the line; the protocol is not edited afterwards.

## Background

In fleetsim's health model, worn parts fail more often: the motor and lift fault hazards grow with wear cubed. A failed robot stops in the aisle and blocks traffic until repaired (5 min for a motor). A **service** instead takes the robot home after its current job, stops it there (no aisle blocked), and resets all wear in 2.5 min. Three policies:

- **Run to failure (`none`):** never service; repair what breaks.
- **Fixed interval (`interval`):** service each robot after 5,400 s of operation (clocks staggered at random).
- **Condition-based (`condition`):** service a robot when any part's wear reaches 0.5, using the telemetry the robot already reports.

The rates are a teaching model (`src/fleetsim/health.py`), so the result is about this model. What should transfer is whether acting on telemetry beats both extremes.

## Hypotheses

- **H1.** Condition-based maintenance completes more tasks per hour than run-to-failure (paired ratio, lower 95% bound > 1).
- **H2.** Condition-based maintenance completes more tasks per hour than fixed-interval maintenance (paired ratio, lower 95% bound > 1).
- **H3.** Condition-based maintenance has at least 30% fewer failures than run-to-failure (mean paired reduction ≥ 0.3).

## Protocol

| Factor | Levels |
|---|---|
| Maintenance policy | none, interval (5,400 s), condition (wear ≥ 0.5) |
| Fixed | 50 robots, load 1.0, nearest-pair dispatch, batteries on with 4 chargers, faults ×4 (normal), 2 technicians, aged fleet (initial wear U(0, 0.6)) |
| Horizon | 600 s warm-up, then 4 h measured (wear needs time to matter) |
| Replications | 10 seeds (0–9), common random numbers across policies |

Metrics: tasks/h, availability, failures, services, MTTR, blocked share. Policies are compared with paired ratios by seed and 95% t-intervals.

Reproduce:

```bash
fleetsim bench --robots 50 --loads 1.0 --allocators nearest --battery --initial-wear 0.6 --faults 4 --techs 2 --maintenance none interval condition --ticks 14400 --replications 10 --no-db --no-parquet --out results/T3
```

---

## Results

*Not yet run.*
