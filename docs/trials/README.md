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
| [T2](T2-repair-capacity.md) | How many technicians does a fleet need? | Pre-registered; running | — |
| [T3](T3-maintenance.md) | Run to failure, fixed intervals, or condition-based maintenance? | Pre-registered; running | — |

## Run your own

Copy [`TEMPLATE.md`](TEMPLATE.md), fill it in, commit it, then run. Open a pull request with the protocol commit first and the results second.
