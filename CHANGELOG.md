# Changelog

All notable changes to fleetsim. Versions follow [semantic versioning](https://semver.org/).

## 0.2.0 - 2026-11-09

The open-lab release: a fleet-health layer, replicated trials, and a browser Academy.

**Findings (every trial pre-registered, 10 seeds per cell, 95% intervals)**

- **T1:** the Hungarian method's 12–15% gain over first-come-first-served dispatch is queue discipline, not optimal matching. A nearest-pair rule reaches 100.5–101% of its throughput. One of three predictions failed.
- **T2 / T2b:** with one technician, 73–86% of repair time is waiting for the technician. T2's design was confounded by a battery-charging wave; the rerun without batteries shows the crew must match the repair work on offer (failures per hour × time per job), and the diminishing-returns prediction failed.
- **T3 / T3b:** condition-based maintenance cuts failures by 34–48% and always beats a fixed interval, which was worse than doing nothing. Its throughput gain depends on the regime: +5.5% when charging limits the fleet, +0.7% with longer order waits when it does not.

**Simulator**

- Fleet health (off by default): batteries and chargers, motor heat and wear, lift cycles, faults that grow with wear, technicians, and maintenance policies `none`, `interval`, `condition`.
- Failures keep the fleet collision-free: a stopped robot becomes an obstacle and affected robots replan their remaining legs or stop safely and retry.
- Technician corridors (`tech_corridors=True`): technicians are priority agents in the reservation table. They walk out on a booked corridor, repair from the next cell, and walk back to a base robots may never enter.
- `fleetsim bench --replications N` with common random numbers, paired comparisons and confidence intervals.
- New dispatch policies `nearest` and `hungarian_aging`, plus `@register_allocator` for your own.
- New KPIs: availability, MTBF, MTTR, repair queue and walk times, tail order waits, corridor reroutes.

**Web**

- fleetsim Academy: eight missions from one robot to 100+, a close-up inspector for any robot (parts, battery, telemetry, repair job, history), and technicians on priority corridors.
- Live 3D simulator, field guide and landing page on GitHub Pages.

**Project**

- Learning path with worked exercises, a trials board and a trial template, contributor docs, CI on Python 3.11 and 3.12, a `ros:jazzy` devcontainer.

**Fixed**

- A robot failing on a cell booked as another robot's future parking spot no longer aborts the run (found by trial T2's first launch).

## 0.1.0 - 2026-11-09

- LoRR warehouse grid world, Poisson orders, space-time A* with prioritized planning, greedy and Hungarian dispatch, tick-level logs in SQLite and Parquet, an SQL analytics notebook.
