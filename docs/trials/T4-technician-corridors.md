# T4 · What do protected technician corridors cost?

**Status:** pre-registered on 2026-11-09, before any T4 run. Results are appended below the line; the protocol is not edited afterwards.

**Disclosure.** Three smoke runs with corridors on were seen while building the feature: 50 robots, faults ×12, 2 technicians, seed 0 → 607 tasks/h; 50 robots, faults ×4, 2 technicians, seed 1 → 843 tasks/h, with a mean technician walk of 67 s against 51 s without corridors for the same seed; 80 robots, faults ×12, 3 technicians, seed 2 → 722 tasks/h. All three had zero conflicts. The no-corridor arm of this trial repeats two cells of [T2b](T2b-repair-capacity-no-battery.md) (790.7 and 636.4 tasks/h on average), so the hypotheses below are informed predictions.

## Background

Until now a technician was a timer: the walk to a broken robot took its shortest-path time and nobody was physically on the floor. With `tech_corridors=True` a technician is a priority agent in the reservation table. The whole duty is booked at once (walk out, stand next to the robot, repair, walk back to a base robots may not enter). Robots whose routes cross the corridor replan or stop. No robot may ever share a cell with a technician.

That safety has a price: robots detour or wait, technicians walk around obstacles instead of through them, and a technician with no job walks home, so the next walk can start from further away. This trial measures the price.

## Hypotheses

- **H1 (safety).** In every corridor run: zero robot–robot conflicts, zero robot–technician conflicts (same cell, or swapping cells), no technician ever jumps to a non-adjacent cell, and no robot ever stands on a technician base.
- **H2.** At normal faults (×4), corridors cost less than 2% of throughput: the paired ratio corridors-on / corridors-off has a lower 95% bound above 0.98.
- **H3.** At frequent faults (×12), corridors cost less than 5%: lower 95% bound above 0.95.
- **H4.** Technicians walk longer per job with corridors on (mean paired difference in walk time above 0, lower 95% bound above 0).

## Protocol

| Factor | Levels |
|---|---|
| Technician model | timer (corridors off), priority corridors (on) |
| Fault rate | 4 (normal), 12 (frequent) |
| Fixed | 50 robots, load 1.0, nearest-pair dispatch, 2 technicians, batteries off, aged fleet (initial wear U(0, 0.6)), run-to-failure maintenance |
| Replications | 10 seeds (0–9), common random numbers: the same orders, robot homes, initial wear and per-tick fault draws in both arms |

Each run: 600 s warm-up, then 3,600 s measured. Metrics: tasks/h, order wait, MTTR split into queue, walk and repair, corridor reroutes, blocked share, and the four safety counts of H1. Arms are compared by seed with 95% t-intervals. The off arm should reproduce T2b's two cells exactly; if it does not, that is reported as a defect.

Two differences between the arms are part of the treatment and not controlled away: the technician repairs from a neighbouring cell instead of the robot's own cell, and technician base cells are closed to robots.

Reproduce:

```bash
fleetsim bench --robots 50 --loads 1.0 --allocators nearest --initial-wear 0.6 --faults 4 12 --techs 2 --corridors off on --replications 10 --no-db --no-parquet --out results/T4
```

---

## Results

*Not yet run.*
