# T2b · Repair capacity without the charging confound

**Status:** pre-registered on 2026-11-09, before any T2b run. Results are appended below the line; the protocol is not edited afterwards.

**Disclosure.** This follow-up was designed after seeing [T2](T2-repair-capacity.md)'s results. T2 showed a waiting share of 0.86 of repair time (faults ×12, 1 technician) and a recovered share of 0.62 for the second technician, so H1 and H2 below are informed predictions, not blind ones. T2 also showed that its fault-free baseline was throttled by a synchronized battery-charging wave (29% of robot time idle with a low battery), which made faults look almost free. T2b removes batteries to isolate repair capacity.

## Hypotheses

- **H1.** At frequent faults (×12) with 1 technician, more than half of mean time to repair is spent waiting for the technician.
- **H2.** At frequent faults, going from 1 to 2 technicians recovers at least 50% of the throughput lost to faults; going from 3 to 4 recovers less than 10% of the loss that remains at 3.
- **H3.** With batteries off, every fault arm completes fewer tasks per hour than the fault-free baseline (paired by seed, upper 95% bound of the ratio below 1). In T2 this failed: the 4-technician arm beat the baseline.
- **H4 (safety).** Every run is collision-free.

## Protocol

Identical to T2 except **batteries off**: 50 robots, load 1.0, nearest-pair dispatch, aged fleet (initial wear U(0, 0.6)), run-to-failure maintenance, fault rate {4, 12} × technicians {1, 2, 3, 4}, plus a fault-free baseline; 10 seeds (0–9) with common random numbers; 600 s warm-up and 3,600 s measured. Metrics and the definition of "recovered share" are as in T2. If the loss at 3 technicians is not distinguishable from zero (95% interval includes 0), the second half of H2 is reported as "not evaluable" and the absolute gain in tasks/h is reported instead.

Reproduce:

```bash
fleetsim bench --robots 50 --loads 1.0 --allocators nearest --replications 10 --no-db --no-parquet --out results/T2b-baseline
```

```bash
fleetsim bench --robots 50 --loads 1.0 --allocators nearest --initial-wear 0.6 --faults 4 12 --techs 1 2 3 4 --replications 10 --no-db --no-parquet --out results/T2b
```

**Protocol correction, made before any T2b run.** The first version of this file ran the baseline with `--maintenance interval`, which would have sent robots for scheduled services and lowered the baseline. The baseline is now a plain run with the health layer off. With the same seed it has the same orders and robot homes, and without batteries or faults the health layer does not change how robots move.

---

## Results

*Not yet run.*
