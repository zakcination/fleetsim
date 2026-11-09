# Learning path: from another field into fleet management

fleetsim is an **open lab**. You learn each idea by going round the same loop:

**Play** it in the [Academy](https://zakcination.github.io/fleetsim/academy.html) → **calculate** it by hand → **build** or change it in code → **measure** it with a pre-registered trial → **write** what you found.

It's meant for people who come from analytics, finance, operations research or general software and want to work on robot fleets. You don't need robotics experience. You need Python, basic statistics and curiosity.

## The six levels

| Level | Idea | Play (Academy) | Calculate | Build | Measure |
|---|---|---|---|---|---|
| 1 | The errand cycle, ticks, the grid as a graph | Mission 1 | [Exercise 1](#exercise-1-how-much-can-ten-robots-do) | Read `grid.py`; load another map ([EXTENDING](EXTENDING.md#2-a-different-map)) | — |
| 2 | Collisions, space-time A*, the reservation table | Mission 2 | [Field guide](https://zakcination.github.io/fleetsim/guide.html), chapter 5 demo | Read `planner.py`; add a planner test | Plan-failure rate vs fleet size |
| 3 | Dispatch: who takes which order | Mission 3 | [Exercise 2](#exercise-2-greedy-vs-optimal-on-paper) | Write a policy with `@register_allocator` | [T1](trials/T1-allocation.md) |
| 4 | Load, queues and capacity | Mission 4 | [Exercise 3](#exercise-3-littles-law-as-an-audit) | Add a KPI to `analytics.py`; query the tick log in SQL | Your own load sweep |
| 5 | Batteries, faults, repairs, availability | Missions 5–6 | Exercise on MTBF and MTTR in [T2](trials/T2-repair-capacity.md) | Change a rate in `health.py`; add a maintenance policy | [T2](trials/T2-repair-capacity.md), [T3](trials/T3-maintenance.md) |
| 6 | Experiments you can defend | Pin and compare runs | [Exercise 4](#exercise-4-why-the-same-seed-matters) | `fleetsim bench --replications 10` | [Write your own trial](trials/TEMPLATE.md) |

Each level ends with something you can show: a pinned comparison, a calculation, a merged pull request or a trial write-up.

## Worked exercises

All numbers come from this repo's committed results, so you can check every step.

### Exercise 1: how much can ten robots do?

One errand (drive to the pod, lift, drive to a station, 10 s pick, drive back, lower) takes about **229.5 s** on this map when the robot starts from its home cell and meets no traffic.

1. What is the capacity of 10 robots in tasks per hour?
2. Trial T1 measured 166.6 tasks/h for first-come-first-served and 190.7 for nearest-pair dispatch when orders arrive faster than that. How can a fleet beat its own capacity?

<details><summary>Answer</summary>

1. 10 × 3,600 / 229.5 = **156.9 tasks/h**.
2. The 229.5 s assumes every errand starts from home. A busy robot starts its next errand from where it dropped the last pod, which is usually closer, so real errands are shorter. Nearest-pair dispatch shortens them further by picking nearby orders. "Offered load 1.0" in fleetsim is therefore a conservative yardstick, not a hard ceiling. Check: `results/T1/runs.csv`, rows with `n_robots = 10`.
</details>

### Exercise 2: greedy vs optimal on paper

Two free robots, two waiting orders. Travel times in seconds:

| | Order A (oldest) | Order B |
|---|---:|---:|
| Robot 1 | 5 | 1 |
| Robot 2 | 6 | 20 |

Find the total travel for (a) first-come-first-served greedy, (b) nearest-pair greedy, (c) the optimal assignment.

<details><summary>Answer</summary>

(a) A takes its nearest robot, Robot 1 (5 s); B is left with Robot 2 (20 s). Total **25 s**.
(b) The closest pair is Robot 1–B (1 s); then Robot 2–A (6 s). Total **7 s**.
(c) Optimal is also Robot 2–A and Robot 1–B: **7 s**.

Nearest-pair found the optimum here. Trial T1 shows this is typical on this warehouse: nearest-pair reaches 100.5–101% of the Hungarian method's throughput, so the gain comes from *which* orders are served first, not from optimal matching.
</details>

### Exercise 3: Little's law as an audit

For any stable queue, **L = λ × W**: the average number of items in the system equals the arrival rate times the time each item spends inside.

In T1 (100 robots, load 0.85, first-come-first-served, mean of 10 seeds) the fleet completed 1,347.3 tasks/h and a typical order took 193.4 s from creation to completion (the median; Little's law strictly needs the mean, which is close to it here). The simulator separately reports utilization: the share of robot time spent on an order. What utilization does Little's law predict?

<details><summary>Answer</summary>

λ = 1,347.3 / 3,600 = 0.3743 orders/s. L = 0.3743 × 193.4 = **72.4 orders in progress**. Each busy robot carries one order, so about 72.4 of 100 robots should be busy. The simulator's own utilization figure is **72.5%**. Two independent calculations agree, which is evidence that the bookkeeping is right. Auditors and model validators use the same trick: recompute a number by a second route.
</details>

### Exercise 4: why the same seed matters

T1 compares nearest-pair with Hungarian at 50 robots, load 1.3, over 10 seeds. Tasks per hour: nearest-pair 982.0 (standard deviation across seeds 18.4), Hungarian 976.9 (13.6). The two policies saw the same orders in each seed, and their results correlate at 0.957.

1. Treating the two samples as independent, the 95% interval on the difference is ±15.2. Is the 5.1 difference detectable?
2. Pairing by seed, the standard deviation of the per-seed difference is 6.64. What is the 95% interval now (t = 2.262 for 9 degrees of freedom)?

<details><summary>Answer</summary>

1. No: 5.1 ± 15.2 includes zero by a wide margin.
2. 2.262 × 6.64 / √10 = **±4.75**, so the difference is 5.1 ± 4.75: small but detectable. Pairing made the interval 3.2 times tighter, which would otherwise take about 10 times as many runs. This is "common random numbers", and it is why `fleetsim bench --replications` gives every policy the same seed.
</details>

## If you come from another field

| You already know | It maps to | Where in fleetsim |
|---|---|---|
| Model validation: challenge every claim, recompute independently | An independent collision checker; Little's-law audits; pre-registered trials | `checker.py`, `docs/trials/` |
| Survival and hazard models (probability of default, churn) | Component failure hazards that grow with wear; maintenance timing | `health.py`, trial T3 |
| Censored data (loans that haven't defaulted yet) | Orders still waiting when the run ends count with their wait so far | `analytics.summarize` |
| Stress testing and scenarios | Load sweeps, fault-rate sweeps, technician sweeps | `fleetsim bench` |
| Backtesting with out-of-sample periods | Replications with fresh seeds; hypotheses written before the run | `--replications`, `docs/trials/TEMPLATE.md` |
| Linear and integer programming | The assignment problem and the Hungarian method | `allocation.py` |
| Queueing in call centres or branches | Order backlog, technicians as servers, the machine-repair queue | trials T1, T2 |
| SQL on transaction tables | One row per robot per second, queried the same way | `notebooks/analytics.ipynb` |
| Backend services | A fleet-health service and floor tools (planned) | [ROADMAP](ROADMAP.md) |

## Make it yours

1. Fork the repo and finish Academy missions 1–7.
2. Do the four exercises without opening the answers.
3. Add one dispatch policy or maintenance policy ([EXTENDING](EXTENDING.md)).
4. Copy [`docs/trials/TEMPLATE.md`](trials/TEMPLATE.md), write your hypothesis and pass bar, commit it, **then** run the trial.
5. Open a pull request with the result, including the hypotheses that failed. Failed predictions are welcome here; unreported ones are not.
