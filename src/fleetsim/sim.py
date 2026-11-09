"""Discrete-time fleet simulation: orders -> allocation -> planning -> motion log."""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field

import numpy as np

from .allocation import make_allocator
from .grid import DEFAULT_CROP, DEFAULT_MAP, Grid
from .orders import Order, OrderStream
from .planner import ReservationTable, SearchStats, plan_errand

# Robot states (int8 codes in the tick log)
IDLE, TO_POD, LIFT, TO_STATION, SERVICE, RETURN, DROP, TO_HOME = range(8)
STATE_NAMES = ["idle", "to_pod", "lift", "to_station", "service", "return", "drop", "to_home"]
BUSY_STATES = (TO_POD, LIFT, TO_STATION, SERVICE, RETURN, DROP)
TRAVEL_STATES = (TO_POD, TO_STATION, RETURN)


@dataclass
class SimConfig:
    n_robots: int = 10
    allocator: str = "greedy"  # "greedy" | "hungarian"
    k: int = 5  # Hungarian re-solve period (ticks)
    aging: float = 0.25  # hungarian_aging: seconds of travel traded per second of order age
    ticks: int = 3600  # measured horizon (1 tick = 1 s)
    warmup: int = 600  # extra ticks simulated before measurement starts
    load: float = 0.85  # offered load as a fraction of free-flow fleet capacity
    rate: float | None = None  # orders/tick; overrides ``load`` if given
    lift: int = 2
    service: int = 10
    drop: int = 2
    seed: int = 0
    map_path: str = str(DEFAULT_MAP)
    crop: tuple[int, int, int, int] | None = DEFAULT_CROP
    station_side: str = "left"


@dataclass
class Robot:
    id: int
    home: int
    t0: int = 0
    path: list[int] = field(default_factory=list)
    states: np.ndarray = field(default_factory=lambda: np.zeros(0, dtype=np.int8))
    order: Order | None = None

    def pos(self, t: int) -> int:
        k = t - self.t0
        return self.path[k] if k < len(self.path) else self.path[-1]

    def state(self, t: int) -> int:
        k = t - self.t0
        return int(self.states[k]) if k < len(self.states) else IDLE


@dataclass
class SimResult:
    config: SimConfig
    grid: Grid
    homes: list[int]
    traj: np.ndarray  # [T, N] cell index
    state: np.ndarray  # [T, N] int8 state code
    order_of: np.ndarray  # [T, N] order id or -1
    orders: list[Order]
    plans: list[dict]
    rate: float
    wall_s: float

    @property
    def total_ticks(self) -> int:
        return self.traj.shape[0]


def estimate_cycle_time(grid: Grid, homes: list[int], cfg: SimConfig, rng: np.random.Generator) -> float:
    """Mean uncongested errand duration (robot->pod->station->pod), in ticks."""
    total = []
    for _ in range(300):
        pod = int(rng.choice(grid.pods))
        st = int(rng.choice(grid.stations))
        start = int(rng.choice(homes))
        d_pod = grid.dist_to(pod)
        d_ps = int(grid.dist_to(st)[pod])
        total.append(int(d_pod[start]) + cfg.lift + 2 * d_ps + cfg.service + cfg.drop)
    return float(np.mean(total))


def _state_array(n: int, arrivals: list[int], cfg: SimConfig) -> np.ndarray:
    a_pod, a_st, a_ret, a_home = arrivals
    s = np.full(n, IDLE, dtype=np.int8)
    s[0:a_pod] = TO_POD
    s[a_pod : a_pod + cfg.lift] = LIFT
    s[a_pod + cfg.lift : a_st] = TO_STATION
    s[a_st : a_st + cfg.service] = SERVICE
    s[a_st + cfg.service : a_ret] = RETURN
    s[a_ret : a_ret + cfg.drop] = DROP
    s[a_ret + cfg.drop : a_home] = TO_HOME
    return s


def run(cfg: SimConfig, grid: Grid | None = None, log_progress: bool = False) -> SimResult:
    wall0 = time.perf_counter()
    if grid is None:
        grid = Grid.from_file(cfg.map_path, crop=cfg.crop, station_side=cfg.station_side)
    rng = np.random.default_rng(cfg.seed)
    homes = grid.choose_parking(cfg.n_robots)
    rate = cfg.rate if cfg.rate is not None else cfg.load * cfg.n_robots / estimate_cycle_time(grid, homes, cfg, rng)
    stream = OrderStream(grid.pods, grid.stations, rate, seed=cfg.seed + 1)
    allocator = make_allocator(cfg.allocator, k=cfg.k, aging=cfg.aging)

    rt = ReservationTable()
    robots = []
    for i, h in enumerate(homes):
        r = Robot(id=i, home=h, t0=0, path=[h], states=np.array([IDLE], dtype=np.int8))
        rt.reserve(i, 0, r.path)
        robots.append(r)

    T = cfg.warmup + cfg.ticks
    N = cfg.n_robots
    traj = np.empty((T, N), dtype=np.int32)
    state = np.empty((T, N), dtype=np.int8)
    order_of = np.full((T, N), -1, dtype=np.int32)
    pending: list[Order] = []
    orders: list[Order] = []
    plans: list[dict] = []

    for t in range(T):
        new = stream.arrivals(t)
        pending.extend(new)
        orders.extend(new)

        free = [(r.id, r.pos(t)) for r in robots if r.state(t) in (IDLE, TO_HOME)]
        pairs = allocator.assign(t, free, pending, grid)
        assigned_ids = set()
        for rid, order in pairs:
            r = robots[rid]
            start = r.pos(t)
            old = rt.release(rid)
            stats = SearchStats()
            c0 = time.perf_counter()
            legs = [(order.pod, cfg.lift), (order.station, cfg.service), (order.pod, cfg.drop)]
            res = plan_errand(grid, rt, rid, start, t, legs, r.home, stats=stats)
            ms = (time.perf_counter() - c0) * 1e3
            plans.append(
                dict(tick=t, robot=rid, order_id=order.id, ms=ms, ok=res is not None,
                     expansions=stats.expansions, n_free=len(free), n_pending=len(pending))
            )
            if res is None:
                rt.reserve(rid, *old)  # keep the previous (still conflict-free) plan
                continue
            path, arrivals = res
            rt.reserve(rid, t, path)
            r.t0, r.path, r.order = t, path, order
            r.states = _state_array(len(path), arrivals, cfg)
            a_pod, a_st, a_ret, _ = arrivals
            order.assigned, order.robot = t, rid
            order.picked = t + a_pod + cfg.lift
            order.at_station = t + a_st
            order.serviced = t + a_st + cfg.service
            order.completed = t + a_ret + cfg.drop
            d_pod = grid.distance(start, order.pod)
            d_ps = grid.distance(order.pod, order.station)
            order.free_flow = d_pod + cfg.lift + 2 * d_ps + cfg.service + cfg.drop
            assigned_ids.add(order.id)
        if assigned_ids:
            pending = [o for o in pending if o.id not in assigned_ids]

        for r in robots:
            traj[t, r.id] = r.pos(t)
            s = r.state(t)
            state[t, r.id] = s
            if s in BUSY_STATES and r.order is not None:
                order_of[t, r.id] = r.order.id
        if t % 250 == 0:
            rt.prune_before(t)
        if log_progress and t % 500 == 0:
            print(f"  t={t} pending={len(pending)} done={sum(0 <= o.completed <= t for o in orders)}", flush=True)

    return SimResult(cfg, grid, homes, traj, state, order_of, orders, plans, rate, time.perf_counter() - wall0)


def config_dict(cfg: SimConfig) -> dict:
    d = asdict(cfg)
    d["crop"] = None if cfg.crop is None else ",".join(map(str, cfg.crop))
    return d
