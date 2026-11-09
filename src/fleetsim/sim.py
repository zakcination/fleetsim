"""Discrete-time fleet simulation: orders -> allocation -> planning -> motion log.

With the health options off (the default) the simulator behaves exactly like
v0.1. With them on, robots run on batteries and visit chargers, parts heat up
and wear, faults stop robots where they stand, technicians walk over and repair
them, and a maintenance policy can take worn robots out for service first.

Collision-freedom is kept through every disruption: a robot that stops becomes
a permanent obstacle in the reservation table, and every robot whose booked
route crosses it replans its remaining legs immediately or, if no route exists,
stops safely where it is ("blocked") and retries every few seconds.
"""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field

import numpy as np

from . import health as H
from .allocation import make_allocator
from .grid import DEFAULT_CROP, DEFAULT_MAP, Grid
from .orders import Order, OrderStream
from .planner import ReservationTable, SearchStats, plan_errand

# Robot states (int8 codes in the tick log)
(IDLE, TO_POD, LIFT, TO_STATION, SERVICE, RETURN, DROP, TO_HOME,
 TO_CHARGER, CHARGING, FAILED, REPAIR, BLOCKED) = range(13)
STATE_NAMES = ["idle", "to_pod", "lift", "to_station", "service", "return", "drop", "to_home",
               "to_charger", "charging", "failed", "repair", "blocked"]
BUSY_STATES = (TO_POD, LIFT, TO_STATION, SERVICE, RETURN, DROP)
TRAVEL_STATES = (TO_POD, TO_STATION, RETURN)
DOWN_STATES = (FAILED, REPAIR)


@dataclass
class SimConfig:
    n_robots: int = 10
    allocator: str = "greedy"  # any registered policy: greedy | nearest | hungarian | hungarian_aging
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
    # --- health (all off by default: v0.1 behaviour) -------------------------
    battery: bool = False
    chargers: int = 4
    charge_at: float = 25.0  # % below which a free robot goes to charge
    faults: float = 0.0  # fault-rate multiplier: 0 off, 1 rare, 4 normal, 12 frequent
    techs: int = 2
    initial_wear: float = 0.15  # each part starts with wear ~ U(0, initial_wear)
    maintenance: str = "none"  # none (run to failure) | interval | condition
    service_interval: int = 5400  # interval policy: operating seconds between services
    service_wear: float = 0.5  # condition policy: service when any part's wear exceeds this

    @property
    def health_on(self) -> bool:
        return self.battery or self.faults > 0 or self.maintenance != "none"


@dataclass
class Leg:
    goal: int
    dwell: int
    travel: int  # state while driving to the goal
    dwell_state: int  # state while dwelling at the goal
    tag: str  # pod | station | drop | charge


@dataclass
class Robot:
    id: int
    home: int
    t0: int = 0
    path: list[int] = field(default_factory=list)
    states: np.ndarray = field(default_factory=lambda: np.zeros(0, dtype=np.int8))
    order: Order | None = None
    legs: list[Leg] | None = None
    arr: list[int] | None = None
    frozen: int | None = None  # state while stopped (failed / repair / blocked)
    resume: list[Leg] | None = None  # legs to finish after a stop
    failed: bool = False
    blocked: bool = False
    want_service: bool = False
    job: dict | None = None
    hp: H.Health | None = None

    def pos(self, t: int) -> int:
        k = t - self.t0
        return self.path[k] if k < len(self.path) else self.path[-1]

    def state(self, t: int) -> int:
        k = t - self.t0
        if k < len(self.states):
            return int(self.states[k])
        return self.frozen if self.frozen is not None else IDLE


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
    soc: np.ndarray | None = None  # [T, N] battery %, when batteries are on
    motor_temp: np.ndarray | None = None  # [T, N] hotter motor, °C, when health is on
    jobs: list[dict] = field(default_factory=list)  # every repair / service job
    chargers: list[int] = field(default_factory=list)

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


def choose_chargers(grid: Grid, homes: list[int], k: int) -> list[int]:
    """``k`` charger cells on open floor, away from homes and stations, spread along the grid."""
    taken = set(homes)
    for c in homes:
        taken.update(grid.neighbors[c])
    for s in grid.stations:
        taken.add(s)
        taken.update(grid.neighbors[s])
    cands = [c for c in grid.free_cells() if grid.char(c) == "." and c not in taken and len(grid.neighbors[c]) >= 3]
    if not cands or k <= 0:
        return []
    k = min(k, len(cands))
    return [cands[int(i)] for i in np.linspace(0, len(cands) - 1, k).round()]


def order_legs(o: Order, cfg: SimConfig) -> list[Leg]:
    return [Leg(o.pod, cfg.lift, TO_POD, LIFT, "pod"),
            Leg(o.station, cfg.service, TO_STATION, SERVICE, "station"),
            Leg(o.pod, cfg.drop, RETURN, DROP, "drop")]


def states_for(n: int, legs: list[Leg], arr: list[int]) -> np.ndarray:
    s = np.full(n, IDLE, dtype=np.int8)
    prev = 0
    for leg, a in zip(legs, arr):
        s[prev:a] = leg.travel
        s[a:a + leg.dwell] = leg.dwell_state
        prev = a + leg.dwell
    s[prev:arr[len(legs)]] = TO_HOME
    return s


class Fleet:
    """One simulation run. ``run()`` below is the convenient entry point."""

    def __init__(self, cfg: SimConfig, grid: Grid | None = None):
        self.cfg = cfg
        self.grid = grid or Grid.from_file(cfg.map_path, crop=cfg.crop, station_side=cfg.station_side)
        g = self.grid
        rng = np.random.default_rng(cfg.seed)
        self.homes = g.choose_parking(cfg.n_robots)
        self.rate = cfg.rate if cfg.rate is not None else cfg.load * cfg.n_robots / estimate_cycle_time(g, self.homes, cfg, rng)
        self.stream = OrderStream(g.pods, g.stations, self.rate, seed=cfg.seed + 1)
        self.allocator = make_allocator(cfg.allocator, k=cfg.k, aging=cfg.aging)
        self.hrng = np.random.default_rng(cfg.seed + 2)  # health stream, independent of orders
        self.chargers = choose_chargers(g, self.homes, cfg.chargers) if cfg.battery else []
        self.tech_base = min(g.free_cells())
        self.rt = ReservationTable()
        self.robots: list[Robot] = []
        for i, h in enumerate(self.homes):
            r = Robot(id=i, home=h, path=[h], states=np.array([IDLE], dtype=np.int8))
            if cfg.health_on:
                r.hp = H.Health.new(self.hrng, cfg.initial_wear, cfg.service_interval)
            self.rt.reserve(i, 0, r.path)
            self.robots.append(r)
        self.techs = [{"id": i, "cell": self.tech_base, "job": None} for i in range(cfg.techs)]
        self.pending: list[Order] = []
        self.orders: list[Order] = []
        self.plans: list[dict] = []
        self.jobs: list[dict] = []
        self.retry_at: dict[int, int] = {}

    # ------------------------------------------------------------ planning
    def _commit(self, r: Robot, t: int, path: list[int], arr: list[int], legs: list[Leg]) -> None:
        r.t0, r.path, r.arr, r.legs, r.frozen = t, path, arr, legs, None
        r.states = states_for(len(path), legs, arr)
        o = r.order
        if o is None:
            return
        for leg, a in zip(legs, arr):
            if leg.tag == "pod":
                o.picked = t + a + leg.dwell
            elif leg.tag == "station":
                o.at_station, o.serviced = t + a, t + a + leg.dwell
            elif leg.tag == "drop":
                o.completed = t + a + leg.dwell

    def _try_plan(self, r: Robot, t: int, legs: list[Leg], order_id: int = -1, n_free: int = 0) -> bool:
        start = r.pos(t)
        old = self.rt.release(r.id)
        stats = SearchStats()
        c0 = time.perf_counter()
        res = plan_errand(self.grid, self.rt, r.id, start, t, [(lg.goal, lg.dwell) for lg in legs], r.home, stats=stats)
        self.plans.append(dict(tick=t, robot=r.id, order_id=order_id, ms=(time.perf_counter() - c0) * 1e3,
                               ok=res is not None, expansions=stats.expansions, n_free=n_free, n_pending=len(self.pending)))
        if res is None:
            if old is not None:
                self.rt.reserve(r.id, *old)  # keep the previous (still conflict-free) plan
            return False
        path, arrivals = res
        self.rt.reserve(r.id, t, path)
        self._commit(r, t, path, arrivals, legs)
        return True

    def _remaining(self, r: Robot, t: int) -> list[Leg]:
        if not r.legs:
            return []
        k, out = t - r.t0, []
        for leg, a in zip(r.legs, r.arr):
            end = a + leg.dwell
            if k >= end:
                continue
            out.append(Leg(leg.goal, end - k if k >= a else leg.dwell, leg.travel, leg.dwell_state, leg.tag))
        return out

    def _freeze(self, r: Robot, t: int, state: int) -> None:
        p = r.pos(t)
        self.rt.release(r.id)
        self.rt.reserve(r.id, t, [p])
        r.t0, r.path, r.legs, r.arr, r.frozen = t, [p], None, None, state
        r.states = np.array([state], dtype=np.int8)
        if r.order is not None and r.order.completed > t:
            r.order.completed = -1  # not done until the robot moves again

    def _resolve(self, t: int, stopped: list[int]) -> None:
        """Replan every robot whose booked route runs into a robot that just stopped."""
        queue = list(stopped)
        while queue:
            f = self.robots[queue.pop()]
            c = f.pos(t)
            for j in self.robots:
                if j is f or j.frozen is not None:
                    continue
                k0 = max(0, t + 1 - j.t0)
                if j.path[-1] != c and c not in j.path[k0:]:
                    continue
                legs = self._remaining(j, t)
                if not self._try_plan(j, t, legs):
                    j.resume, j.blocked = legs, True
                    self._freeze(j, t, BLOCKED)
                    queue.append(j.id)

    def _stop(self, r: Robot, t: int, component: str) -> None:
        """A fault (or a scheduled service) stops the robot where it stands."""
        r.resume = r.resume if r.blocked else self._remaining(r, t)
        r.failed, r.blocked = True, False
        self._freeze(r, t, FAILED)
        job = {"id": len(self.jobs), "robot": r.id, "component": component, "kind": "service" if component == "service" else "failure",
               "created": t, "tech": None, "arrive": None, "start": None, "end": None, "status": "waiting"}
        self.jobs.append(job)
        r.job = job
        self._resolve(t, [r.id])

    # ------------------------------------------------------------ health
    def _techs(self, t: int) -> None:
        waiting = [j for j in self.jobs if j["status"] == "waiting"]
        for tech in self.techs:
            if tech["job"] is None and waiting:
                job = waiting.pop(0)
                cell = self.robots[job["robot"]].pos(t)
                job["tech"], job["status"] = tech["id"], "en route"
                job["arrive"] = t + int(self.grid.distance(tech["cell"], cell))
                tech["job"] = job
            job = tech["job"]
            if job is None:
                continue
            r = self.robots[job["robot"]]
            if job["status"] == "en route" and t >= job["arrive"]:
                job["status"], job["start"] = "repairing", t
                job["end"] = t + H.REPAIR_S[job["component"]]
                tech["cell"] = r.pos(t)
                r.frozen = REPAIR
                r.states = np.array([REPAIR], dtype=np.int8)
            if job["status"] == "repairing" and t >= job["end"]:
                job["status"] = "done"
                tech["job"] = None
                r.hp.repair(job["component"])
                r.failed, r.job, r.frozen = False, None, None
                legs, r.resume = r.resume or [], None
                if not self._try_plan(r, t, legs):
                    r.resume, r.blocked = legs, True
                    self._freeze(r, t, BLOCKED)

    def _health_tick(self, t: int, u: np.ndarray) -> None:
        cfg = self.cfg
        for r in self.robots:
            hp, s = r.hp, r.state(t)
            if s in DOWN_STATES:
                continue
            moving = r.pos(t) != r.pos(t + 1)
            carrying = s in (TO_STATION, RETURN)
            if cfg.battery:
                if s == CHARGING:
                    hp.soc = min(100.0, hp.soc + H.CHARGE_RATE * hp.pack / 100)
                    hp.pack = max(60.0, hp.pack - H.PACK_AGING)
                elif moving:
                    hp.soc -= H.DRAIN_MOVE * (H.CARRY_FACTOR if carrying else 1)
                elif s in (LIFT, DROP):
                    hp.soc -= H.DRAIN_LIFT
                else:
                    hp.soc -= H.DRAIN_IDLE
                if hp.soc <= 0:
                    hp.soc = 0.0
                    self._stop(r, t, "depleted")
                    continue
            heat = (H.HEAT_CARRY if carrying else H.HEAT_MOVE) if moving else 0.0
            hp.temp_l += heat * (1 + hp.wear_l) - (hp.temp_l - H.AMBIENT) * H.COOL
            hp.temp_r += heat * (1 + hp.wear_r) - (hp.temp_r - H.AMBIENT) * H.COOL
            if moving:
                hp.wear_l += H.MOTOR_WEAR_PER_MOVE
                hp.wear_r += H.MOTOR_WEAR_PER_MOVE * 1.05
                hp.odometer += 1
            if s == LIFT and r.arr and t == r.t0 + r.arr[0]:
                hp.lifts += 1
                hp.lift_wear += H.LIFT_WEAR_PER_CYCLE
            if s not in (IDLE, BLOCKED):
                hp.op_time += 1
            comp = H.pick_fault(float(u[r.id]), H.hazards(hp, moving, s == LIFT, cfg.battery, cfg.faults))
            if comp is not None:
                self._stop(r, t, comp)
                continue
            if not r.want_service and ((cfg.maintenance == "interval" and hp.op_time >= cfg.service_interval)
                                       or (cfg.maintenance == "condition" and hp.max_wear >= cfg.service_wear)):
                r.want_service = True

    # ------------------------------------------------------------ main loop
    def step(self, t: int) -> None:
        cfg = self.cfg
        new = self.stream.arrivals(t)
        self.pending.extend(new)
        self.orders.extend(new)
        if cfg.health_on:
            self._techs(t)
            if t % 3 == 0:
                for r in self.robots:
                    if r.blocked and not r.failed and self._try_plan(r, t, r.resume or []):
                        r.blocked, r.resume = False, None

        free = []
        for r in self.robots:
            if r.failed or r.blocked or r.state(t) not in (IDLE, TO_HOME):
                continue
            p = r.pos(t)
            if r.want_service:
                if r.state(t) == IDLE and p == r.home:
                    r.want_service = False
                    self._stop(r, t, "service")
                continue
            if cfg.battery and r.hp.soc < cfg.charge_at and self.chargers:
                if t >= self.retry_at.get(r.id, 0):
                    ch = min(self.chargers, key=lambda c: (self.grid.distance(p, c), c))
                    need = (H.CHARGE_TO - r.hp.soc + self.grid.distance(p, ch) * H.DRAIN_MOVE) / (H.CHARGE_RATE * r.hp.pack / 100)
                    if not self._try_plan(r, t, [Leg(ch, max(10, int(np.ceil(need))), TO_CHARGER, CHARGING, "charge")]):
                        self.retry_at[r.id] = t + 10  # charger busy for a long time: try again in 10 s
                continue
            free.append((r.id, p))

        pairs = self.allocator.assign(t, free, self.pending, self.grid)
        assigned = set()
        for rid, order in pairs:
            r = self.robots[rid]
            start = r.pos(t)
            r.order = order
            if not self._try_plan(r, t, order_legs(order, cfg), order_id=order.id, n_free=len(free)):
                r.order = None
                continue
            order.assigned, order.robot = t, rid
            order.free_flow = (self.grid.distance(start, order.pod) + cfg.lift
                               + 2 * self.grid.distance(order.pod, order.station) + cfg.service + cfg.drop)
            assigned.add(order.id)
        if assigned:
            self.pending = [o for o in self.pending if o.id not in assigned]

        if cfg.health_on:
            self._health_tick(t, self.hrng.random(len(self.robots)))
        for r in self.robots:
            if r.order is not None and r.order.completed == t:
                r.order = None

    def run(self, log_progress: bool = False) -> SimResult:
        wall0 = time.perf_counter()
        cfg = self.cfg
        T, N = cfg.warmup + cfg.ticks, cfg.n_robots
        traj = np.empty((T, N), dtype=np.int32)
        state = np.empty((T, N), dtype=np.int8)
        order_of = np.full((T, N), -1, dtype=np.int32)
        soc = np.empty((T, N), dtype=np.float32) if cfg.battery else None
        temp = np.empty((T, N), dtype=np.float32) if cfg.health_on else None
        for t in range(T):
            self.step(t)
            for r in self.robots:
                traj[t, r.id] = r.pos(t)
                s = r.state(t)
                state[t, r.id] = s
                if s in BUSY_STATES and r.order is not None:
                    order_of[t, r.id] = r.order.id
                if soc is not None:
                    soc[t, r.id] = r.hp.soc
                if temp is not None:
                    temp[t, r.id] = max(r.hp.temp_l, r.hp.temp_r)
            if t % 250 == 0:
                self.rt.prune_before(t)
            if log_progress and t % 500 == 0:
                print(f"  t={t} pending={len(self.pending)} jobs open={sum(j['status'] != 'done' for j in self.jobs)}", flush=True)
        return SimResult(cfg, self.grid, self.homes, traj, state, order_of, self.orders, self.plans, self.rate,
                         time.perf_counter() - wall0, soc=soc, motor_temp=temp, jobs=self.jobs, chargers=self.chargers)


def run(cfg: SimConfig, grid: Grid | None = None, log_progress: bool = False) -> SimResult:
    return Fleet(cfg, grid).run(log_progress)


def config_dict(cfg: SimConfig) -> dict:
    d = asdict(cfg)
    d["crop"] = None if cfg.crop is None else ",".join(map(str, cfg.crop))
    return d
