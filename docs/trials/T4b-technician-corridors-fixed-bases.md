# T4b · Corridor cost with correctly placed technician bases

**Status:** pre-registered on 2026-11-09, before any T4b run. Results are appended below the line; the protocol is not edited afterwards.

**Disclosure.** This follow-up was designed after seeing [T4](T4-technician-corridors.md): corridors cost 1.1% of throughput at faults ×4 (interval down to 2.4%) and 9.0% at faults ×12, and the cause was traced to a technician base walled in by parked robots. The base-placement defect was fixed in the commit before this file. No corridor run with the new placement has been looked at for throughput; the unit tests ran such simulations and passed their safety checks.

## Hypotheses

Same bars as T4, so the two trials can be compared directly:

- **H1 (safety).** In every corridor run: zero robot–robot conflicts, zero robot–technician conflicts, no technician jumps cells, no robot stands on a technician base.
- **H2.** At normal faults (×4), corridors cost less than 2% of throughput: paired ratio on / off with a lower 95% bound above 0.98.
- **H3.** At frequent faults (×12), corridors cost less than 5%: lower 95% bound above 0.95.
- **H4.** Technicians walk longer per job with corridors on (lower 95% bound of the paired difference above 0).
- **H5 (the fix worked).** Corridor arms complete more tasks per hour than T4's corridor arms did with the same seeds (paired ratio T4b / T4, lower 95% bound above 1) at both fault rates.

My honest expectation: H2 holds; H3 is uncertain, because a crew working near its limit turns any lost technician time into long queues.

## Protocol

Identical to T4: 50 robots, load 1.0, nearest-pair dispatch, 2 technicians, batteries off, aged fleet, run-to-failure; corridors off / on × faults ×4 / ×12; 10 seeds with common random numbers; 600 s warm-up and 3,600 s measured. Only the technician base cells differ from T4, and only in the corridor arm.

Reproduce:

```bash
fleetsim bench --robots 50 --loads 1.0 --allocators nearest --initial-wear 0.6 --faults 4 12 --techs 2 --corridors off on --replications 10 --no-db --no-parquet --out results/T4b
```

---

## Results

*Not yet run.*
