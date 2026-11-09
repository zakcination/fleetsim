# Incidents: force majeure, bugs and accidents

Status: **design, not built yet.** This page says how fleetsim will model things that go wrong
beyond a single worn part: power cuts, a control-system outage, bad telemetry, software faults and
robot collisions. Nothing here is in the simulator yet; the build order is at the end.

## Why not just add five features

The strongest argument against modelling these at all:

* Nobody outside an operator knows how often they happen or how big they are. A throughput number
  that depends on an invented outage rate is an invented number.
* An event with no response to compare is only a dip in a chart of a size we chose ourselves.
* Collisions contradict the one guarantee the simulator has. Today a collision cannot happen: every
  route is booked in the reservation table and the independent checker has found zero conflicts in
  580 trial runs. Letting robots crash needs a new layer (robots that do not follow their booked
  timing), which is the largest change since v0.1.

So the rule for this track: an incident is a **scenario, not a rate**. We do not claim "outages cost
4% a year". We ask "given a 10-minute outage at this point, which response recovers faster, and by
how much", with the same seeds and the same order stream as a twin run that has no incident. Every
incident type ships with at least one response policy and one trial, or it does not ship.

## One mechanism

`SimConfig.incidents` holds a list of events; the default is empty, so every earlier trial stays
reproducible. Each event has a kind, a start second, a duration and parameters. Events are applied
at the start of each simulated second, drawn (when random) from their own random stream so that
orders and part faults stay identical across arms. The result logs every event window, and the
charts shade it.

| Kind | Real-world example | What it does in the model | Responses to compare | Needs first |
|---|---|---|---|---|
| `power` | Charger circuit trips, site brown-out | Some or all chargers deliver nothing for the window; robots on them stop charging | Idle top-up on/off (do full batteries buy ride-through time?); shed load below a reserve charge | Nothing new |
| `stop` | Fleet-manager crash, Wi-Fi loss, emergency stop | Every robot holds its cell for the window; orders keep arriving | Restart everyone at once vs. in waves; oldest-order-first vs. nearest after restart | Nothing new |
| `zone` | Spill, dropped tote, fire door, a person on the floor | A rectangle of cells closes; robots inside leave or hold; routes go around | Hold vs. evacuate; reroute vs. wait | Nothing new (same machinery as a stopped robot) |
| `telemetry` | Stuck sensor, drift, dropped packets, wrong calibration | The wear and temperature that maintenance *reads* differ from the true values (bias, noise, frozen value, gaps) | Raw threshold vs. filtered reading vs. fall back to a fixed interval when data is stale | Split "true" from "observed" health |
| `delay` | Wheel slip, slow lift, software hiccup | A robot executes its booked route late by some seconds | Replan on delay vs. padded bookings (k-robust plans) vs. an action dependency graph | An execution layer |
| `collision` | Two drive units touch | Only possible once `delay` exists: two robots end up on one cell, both stop with damage, the cell may need clearing | The same three responses as `delay`, judged on crashes per 1,000 tasks | `delay` |
| `surge` | Promotion, late truck, station closed | Order rate multiplies, or stations close, for the window | Dispatch policies under overload | Nothing new |

"Software bugs" is not one row on purpose. A bug shows up as one of the effects above: the fleet
stops (`stop`), a robot is late or off its plan (`delay`), or the system acts on wrong data
(`telemetry`). Modelling the effect keeps the model small and still covers the cause.

## How resilience is measured

Each incident run is paired with a twin run: same seed, same orders, no incident.

* **Depth**: lowest rolling tasks per hour during the incident, and the peak backlog.
* **Time to recover**: seconds after the incident ends until the backlog is back within 5% of the twin.
* **Lost tasks**: tasks the twin completed that the incident run did not, by the end of the run.
* **Safety**: conflicts found by the independent checker. Must stay zero for every kind except `collision`.

## Build order

1. Incident list, twin-run analysis, `power` and `stop`. First trial: does keeping idle robots
   fully charged ([idle top-up](EXTENDING.md)) lengthen the time the fleet rides through a charger
   outage, and what does it cost in normal operation?
2. `telemetry`. Trial: how wrong does the reading have to be before condition-based maintenance
   (the winner of [T3b](trials/T3b-maintenance-no-battery.md)) loses to a fixed interval?
3. `zone` and `surge`.
4. `delay`, then `collision`. Research-grade. Reading: Atzmon et al., *Robust Multi-Agent Path
   Finding* (SoCS 2018); Hönig et al., *Persistent and Robust Execution of MAPF Schedules in
   Warehouses* (RA-L 2019); the League of Robot Runners 2026 delay model.

## What this will not tell you

How often any of this happens at a real site, or what it costs in money. The value is the
comparison between responses under a stated scenario.
