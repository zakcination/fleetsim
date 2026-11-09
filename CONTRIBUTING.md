# Contributing to fleetsim

fleetsim is a small, readable simulator for robotic fulfillment fleets. It covers task allocation, multi-agent path finding (MAPF) and fleet analytics. Contributions of every size are welcome: a new dispatch policy, a faster planner, a better chart, a typo fix.

## Five-minute setup

```bash
git clone https://github.com/zakcination/fleetsim.git
cd fleetsim
pip install -e ".[dev]"
pytest
```

Prefer containers? Open the repo in VS Code and choose **Reopen in Container**. The devcontainer is based on `ros:jazzy` and runs the tests on first start.

## Where to start

| You like… | Start here |
|---|---|
| Algorithms / OR | Add a dispatch policy in 30 lines: [`docs/EXTENDING.md`](docs/EXTENDING.md#1-a-new-dispatch-policy) |
| MAPF research | Replace prioritized planning with PBS, RHCR windows, PIBT or LaCAM. See [`docs/ROADMAP.md`](docs/ROADMAP.md) |
| Data / SQL | New KPIs or notebook sections on the tick log ([`notebooks/analytics.ipynb`](notebooks/analytics.ipynb)) |
| Web / 3D | The browser simulator in [`web/live.html`](web/live.html): new views, heatmaps, replay of Python logs |
| ROS 2 / robotics | The ROS 2 bridge track in [`docs/ROADMAP.md`](docs/ROADMAP.md#track-c--ros-2--digital-twin) |

Issues labelled **good first issue** are scoped to an afternoon.

## Ground rules for changes

1. **Zero collisions stays zero.** Any change that touches planning must keep `tests/test_sim.py::test_simulation_is_collision_free` green. Never weaken the checker to make it pass.
2. **Numbers come from code.** Results in the README and docs are produced by `fleetsim bench`, never typed in by hand. If your change moves them, re-run the bench and commit `results/summary.csv`, `results/benchmark.png` and the regenerated notebook.
3. **Compare fairly.** A new policy or planner gets the same seeds, warm-up and window as the baselines. Report tail latency (p95 wait) next to throughput.
4. **Small PRs.** One idea per pull request, with a test.

## Pull request checklist

- [ ] `pytest` passes locally
- [ ] New behaviour has a test
- [ ] Docs updated (README, `docs/`, or docstrings)
- [ ] If results changed: bench re-run and outputs committed

## Code style

Plain, typed Python 3.11+. Prefer clear loops over clever one-liners in the planner, because people read this code to learn. Keep dependencies to the scientific Python stack unless there's a strong reason.

## AI-assisted contributions

AI coding agents are welcome; most of v0.1 was written with one (see the README log). You are responsible for every line you submit. Run it, read it, and say in the PR description which parts were agent-assisted.

## Conduct

By participating you agree to the [Code of Conduct](CODE_OF_CONDUCT.md).
