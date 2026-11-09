# Changelog

All notable changes to fleetsim. Versions follow [semantic versioning](https://semver.org/).

## 0.2.0 - 2026-11-09

The open-lab release: a fleet-health layer, replicated trials, and a browser Academy.

**Findings (every trial pre-registered, 10 seeds per cell, 95% intervals)**

- **T1:** the Hungarian method's 12–15% gain over first-come-first-served dispatch is queue discipline, not optimal matching. A nearest-pair rule reaches 100.5–101% of its throughput. One of three predictions failed.
- **T2 / T2b:** with one technician, 73–86% of repair time is waiting for the technician. T2's design was confounded by a battery-charging wave; the rerun without batteries shows the crew must match the repair work on offer (failures per hour × time per job), and the diminishing-returns prediction failed.
- **T3 / T3b:** condition-based maintenance cuts failures by 34–48% and always beats a fixed interval, which was worse than doing nothing. Its throughput gain depends on the regime: +5.5% when charging limits the fleet, +0.7% with longer order waits when it does not.
- **T4 / T4b / T4c:** protected technician corridors kept robots and technicians apart in all 60 corridor runs. T4's cost (9% at frequent faults) came from a walled-in technician base. With bases fixed (T4b) and a deadlock removed (T4c), on / off throughput is 1.003 [1.000, 1.006] at normal faults and 1.027 [0.978, 1.077] at frequent faults. Four of fourteen predictions across the three trials failed. Still open: technicians block each other for whole duties, and the repair queue starves reachable jobs.

**Simulator**

- Fleet health (off by default): batteries and chargers, motor heat and wear, lift cycles, faults that grow with wear, technicians, and maintenance policies `none`, `interval`, `condition`.
- Failures keep the fleet collision-free: a stopped robot becomes an obstacle and affected robots replan their remaining legs or stop safely and retry.
- Technician corridors (`tech_corridors=True`): technicians are priority agents in the reservation table. They walk out on a booked corridor, repair from the next cell, and walk back to a base robots may never enter. A technician whose way home is closed still takes the job.
- Idle top-up (`idle_topup=True`): when no orders are waiting, idle robots below 90% charge go to a free charger and charge to full. An order or a low-battery robot cuts a top-up short. No trial yet: the numbers in the docs are single runs.
- `fleetsim bench --replications N` with common random numbers, paired comparisons and confidence intervals.
- New dispatch policies `nearest` and `hungarian_aging`, plus `@register_allocator` for your own.
- New KPIs: availability, MTBF, MTTR, repair queue and walk times, tail order waits, corridor reroutes.

**Web**

- fleetsim Academy: eight missions from one robot to 100+, a close-up inspector for any robot (parts, battery, telemetry, repair job, history), and technicians on priority corridors.
- Live 3D simulator, field guide and landing page on GitHub Pages.

**Design notes**

- [docs/INCIDENTS.md](docs/INCIDENTS.md): how power cuts, control outages, bad telemetry, delays and collisions will be modelled as scenarios with a response policy and a trial each. Not built yet.

**Project**

- Learning path with worked exercises, a trials board and a trial template, contributor docs, CI on Python 3.11 and 3.12, a `ros:jazzy` devcontainer.

**Fixed**

- A robot failing on a cell booked as another robot's future parking spot no longer aborts the run (found by trial T2's first launch).

## 0.1.0 - 2026-11-09

- LoRR warehouse grid world, Poisson orders, space-time A* with prioritized planning, greedy and Hungarian dispatch, tick-level logs in SQLite and Parquet, an SQL analytics notebook.
