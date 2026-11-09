# T4c · Technician corridors after the deadlock fix

**Status:** pre-registered on 2026-11-09, before any T4c run. Results are appended below the line; the protocol is not edited afterwards.

**Disclosure.** This follow-up was designed after seeing [T4b](T4b-technician-corridors-fixed-bases.md), where one run deadlocked: a failed robot closed the only approach to a technician's base, and the technician, who had to book a way home with every job, stopped taking jobs. Two changes were made in the commit before this file:

1. A technician with no way home still takes the job and looks for the way home after the repair.
2. The cheap reachability check that runs before a route search now counts technician bases as closed to robots. This changes computing time only; with change 1 switched off, three T4b corridor runs were reproduced exactly.

Seen before registering, with both changes: the unit tests, and a replay of the deadlocked run (faults ×12, seed 2) up to second 3,000, in which the longest time a technician stood idle with a job waiting was 1 s and computing took 5 s instead of 88 s. No throughput figure from any run with change 1 has been looked at.

## Hypotheses

- **H1 (safety).** In every corridor run: zero robot–robot conflicts, zero robot–technician conflicts, no technician jumps cells, no robot stands on a technician base.
- **H2.** At normal faults (×4), corridors cost less than 2% of throughput: paired ratio on / off with a lower 95% bound above 0.98.
- **H3.** At frequent faults (×12), corridors cost less than 5%: lower 95% bound above 0.95.
- **H4 (the deadlock is gone).** In every corridor run, no technician is idle for 120 consecutive seconds or more while a repair job is waiting (`tech_idle_with_work_max_s` below 120).
- **H5 (the fix does no harm).** Corridor arms against T4b's corridor arms with the same seeds: paired ratio T4c / T4b with a lower 95% bound above 0.98 at both fault rates.

Also reported, without a bar: how many corridor runs differ from T4b at all, and computing time per run.

My honest expectation: H1, H2 and H4 hold. H3 held in T4b with a wide interval and could go either way. H5 should hold at ×4, where the no-way-home case is rare; at ×12 I do not know, because a technician who keeps working far from base changes which robot is repaired next.

## Protocol

Identical to T4 and T4b: 50 robots, load 1.0, nearest-pair dispatch, 2 technicians, batteries off, aged fleet, run-to-failure; corridors off / on × faults ×4 / ×12; 10 seeds with common random numbers; 600 s warm-up and 3,600 s measured.

Reproduce:

```bash
fleetsim bench --robots 50 --loads 1.0 --allocators nearest --initial-wear 0.6 --faults 4 12 --techs 2 --corridors off on --replications 10 --no-db --no-parquet --out results/T4c
```

---

## Results

*Not yet run.*
