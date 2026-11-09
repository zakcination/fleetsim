# T3b · Maintenance policy without the charging confound

**Status:** pre-registered on 2026-11-09, before any T3b run **and before T3's results were looked at** (T3 was still running). Results are appended below the line; the protocol is not edited afterwards.

**Disclosure.** [T2](T2-repair-capacity.md) showed that with batteries on and 4 chargers the fleet's throughput is limited by charging, which can hide the effect of faults and repairs. T3 uses the same battery setup, so T3b repeats it with batteries off. No T3 result had been seen when this was written.

## Hypotheses

Same as [T3](T3-maintenance.md):

- **H1.** Condition-based maintenance completes more tasks per hour than run-to-failure (paired ratio, lower 95% bound > 1).
- **H2.** Condition-based maintenance completes more tasks per hour than fixed-interval maintenance (paired ratio, lower 95% bound > 1).
- **H3.** Condition-based maintenance has at least 30% fewer failures than run-to-failure (mean paired reduction ≥ 0.3).

## Protocol

Identical to T3 except **batteries off**: 50 robots, load 1.0, nearest-pair dispatch, faults ×4, 2 technicians, aged fleet (initial wear U(0, 0.6)); policies none / interval (5,400 s) / condition (wear ≥ 0.5); 600 s warm-up then 4 h measured; 10 seeds with common random numbers.

Reproduce:

```bash
fleetsim bench --robots 50 --loads 1.0 --allocators nearest --initial-wear 0.6 --faults 4 --techs 2 --maintenance none interval condition --ticks 14400 --replications 10 --no-db --no-parquet --out results/T3b
```

---

## Results

*Not yet run.*
