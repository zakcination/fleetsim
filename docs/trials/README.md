# Trials

Every quantitative claim in this project comes from a trial in this folder. The rules:

1. **Write it down first.** Hypotheses, protocol and pass bars are committed before any run. The commit history is the proof.
2. **Compare fairly.** Every arm gets the same seeds: the same orders, robot homes, and fault draws.
3. **Replicate.** At least 10 seeds per cell, with 95% intervals, paired by seed.
4. **Report everything.** Failed hypotheses stay in the write-up.

## Findings so far

| Trial | Question | Status | Finding |
|---|---|---|---|
| [T1](T1-allocation.md) | Is the Hungarian method's gain optimal matching or queue discipline? | Done: 300 runs, 0 collisions | Queue discipline. Nearest-pair greedy reaches 100.5–101% of Hungarian's throughput; first-come-first-served is 12–15% behind. A small aging term halves the worst wait for about 1% throughput. One of three hypotheses failed and is reported. |
| [T2](T2-repair-capacity.md) | How many technicians does a fleet need? | Done: 90 runs, 0 collisions | With one technician, 73–86% of repair time is waiting for the technician, but the throughput figures are not trustworthy: the baseline was throttled by a battery-charging wave, and a faulty fleet with 4 technicians "beat" it by 3.3%. Reported as a confound, with a follow-up. |
| [T2b](T2b-repair-capacity-no-battery.md) | The same, with batteries off to isolate repair capacity | Done: 90 runs, 0 collisions | Waiting still dominates (86% with one technician). The diminishing-returns prediction **failed**: at frequent faults each of 4 technicians keeps paying off (+93, +56, +69 tasks/h), because the repair work on offer (3.4–4.5 technician-hours per hour) exceeds the crew. At normal faults two technicians are enough. Size the crew from failures/h × time per job. |
| [T3](T3-maintenance.md) | Run to failure, fixed intervals, or condition-based maintenance? | Done: 30 four-hour runs, 0 collisions | Condition-based wins: +5.5% tasks/h over run-to-failure and +9.6% over a fixed interval, with 34% fewer failures. The fixed interval is worse than doing nothing (it over-services). All three hypotheses hold. Caveat: the fleet was limited by charging, so T3b repeats it without batteries. |
| [T3b](T3b-maintenance-no-battery.md) | The same, with batteries off (registered before T3's results were seen) | Done: 30 four-hour runs, 0 collisions | All three hypotheses hold by their bars, but the throughput gain over run-to-failure shrinks to 0.7%, and condition-based maintenance has **longer** order waits (118 s vs 19 s) because services share the technicians. What survives: 48% fewer failures, and a fixed interval is clearly worst. |
| [T4](T4-technician-corridors.md) | What do protected technician corridors cost? | Done: 40 runs, 0 collisions, 0 robot–technician conflicts | Safety holds. Both cost predictions **failed** (1.1% at normal faults with the interval reaching 2.4%; 9.0% at frequent faults), traced to a technician base walled in by parked robots: a defect in the feature, not a cost of corridors. |
| [T4b](T4b-technician-corridors-fixed-bases.md) | The same, after fixing base placement | Done: 40 runs, 0 collisions, 0 robot–technician conflicts | With correct bases the cost is within both bars: on / off throughput 1.003 [1.000, 1.006] at normal faults and 1.021 [0.967, 1.076] at frequent faults. The "better than T4 at both fault rates" prediction **failed** narrowly at normal faults. One run deadlocked: a technician cut off from base stopped taking jobs. |

## Run your own

Copy [`TEMPLATE.md`](TEMPLATE.md), fill it in, commit it, then run. Open a pull request with the protocol commit first and the results second.
