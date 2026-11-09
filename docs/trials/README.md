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
| [T2](T2-repair-capacity.md) | How many technicians does a fleet need? | Done: 90 runs, 0 collisions | With one technician, 73–86% of repair time is waiting for the technician, and each added technician buys back less (+67, +43, +17 tasks/h). The size of the throughput loss is not trustworthy: the baseline was throttled by a battery-charging wave, and a faulty fleet with 4 technicians "beat" it by 3.3%. Reported as a confound, with a follow-up. |
| [T2b](T2b-repair-capacity-no-battery.md) | The same, with batteries off to isolate repair capacity | Pre-registered; running | — |
| [T3](T3-maintenance.md) | Run to failure, fixed intervals, or condition-based maintenance? | Done: 30 four-hour runs, 0 collisions | Condition-based wins: +5.5% tasks/h over run-to-failure and +9.6% over a fixed interval, with 34% fewer failures. The fixed interval is worse than doing nothing (it over-services). All three hypotheses hold. Caveat: the fleet was limited by charging, so T3b repeats it without batteries. |
| [T3b](T3b-maintenance-no-battery.md) | The same, with batteries off (registered before T3's results were seen) | Pre-registered; running | — |

## Run your own

Copy [`TEMPLATE.md`](TEMPLATE.md), fill it in, commit it, then run. Open a pull request with the protocol commit first and the results second.
