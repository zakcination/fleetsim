"""Robot health: battery, motor heat and wear, lift cycles, faults and repair times.

This is a *teaching* model with made-up but plausible rates (the same numbers as
``web/academy.html``), not data from a real fleet. Its job is to make the
trade-offs of charging, repair capacity and maintenance policy measurable.

Randomness: the simulator draws exactly one uniform number per robot per tick
from its own generator, whether or not anything fails. Two policy arms with the
same seed therefore face the same random numbers (common random numbers), which
keeps paired comparisons tight.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

# --- rates (per second of simulated time) -----------------------------------
DRAIN_MOVE = 100 / (75 * 60)  # % per moving second: ~75 min of driving per charge
DRAIN_IDLE = 100 / (12 * 3600)  # % per idle second
DRAIN_LIFT = 0.12  # % per second spent lifting or lowering
CARRY_FACTOR = 1.25  # driving with a pod costs 25% more energy
CHARGE_RATE = 100 / (14 * 60)  # % per second: empty to full in ~14 min on a new pack
CHARGE_TO = 95.0
PACK_AGING = 0.00003  # pack health lost per charging second

AMBIENT = 24.0  # °C
HEAT_MOVE, HEAT_CARRY = 0.33, 0.47  # °C added per moving second (empty / carrying)
COOL = 0.02  # Newton cooling coefficient per second
OVERHEAT = 72.0  # °C above which motor faults become much more likely

MOTOR_WEAR_PER_MOVE = 1 / 40000  # wear fraction per moving second (~11 h to full wear)
LIFT_WEAR_PER_CYCLE = 1 / 1500

# base fault probabilities per exposed second, multiplied by the "faults" knob
P_MOTOR, P_LIFT, P_LIDAR, P_ENCODER, P_BATTERY = 4e-6, 1e-4, 3e-6, 2e-6, 1e-6
P_OVERHEAT = 2e-4

REPAIR_S = {"motor_l": 300, "motor_r": 300, "lift": 240, "lidar": 120, "encoder": 90,
            "battery": 360, "depleted": 180, "service": 150}
COMPONENTS = ("motor_l", "motor_r", "lidar", "encoder", "lift", "battery")


@dataclass
class Health:
    soc: float  # state of charge, %
    pack: float  # pack health, %
    temp_l: float
    temp_r: float
    wear_l: float
    wear_r: float
    lift_wear: float
    lifts: int = 0
    odometer: int = 0  # cells driven
    op_time: int = 0  # operating seconds since the last service

    @classmethod
    def new(cls, rng: np.random.Generator, initial_wear: float, interval: int = 5400) -> "Health":
        u = rng.random(6)  # always 6 draws, so every policy arm sees the same random stream
        return cls(soc=70 + 30 * u[0], pack=100 - 6 * u[1], temp_l=AMBIENT, temp_r=AMBIENT,
                   wear_l=initial_wear * u[2], wear_r=initial_wear * u[3], lift_wear=initial_wear * u[4],
                   op_time=int(u[5] * interval))  # staggered service clocks

    @property
    def max_wear(self) -> float:
        return max(self.wear_l, self.wear_r, self.lift_wear)

    def score(self) -> float:
        """0-100, the weakest component."""
        return 100 * min(1 - self.wear_l, 1 - self.wear_r, 1 - self.lift_wear, self.pack / 100)

    def repair(self, component: str) -> None:
        if component == "motor_l":
            self.wear_l, self.temp_l = 0.0, AMBIENT
        elif component == "motor_r":
            self.wear_r, self.temp_r = 0.0, AMBIENT
        elif component == "lift":
            self.lift_wear = 0.0
        elif component == "battery":
            self.pack, self.soc = 100.0, 100.0
        elif component == "depleted":
            self.soc = 60.0
        elif component == "service":
            self.wear_l = self.wear_r = self.lift_wear = 0.0
            self.temp_l = self.temp_r = AMBIENT
            self.op_time = 0


def hazards(h: Health, moving: bool, lifting: bool, battery: bool, faults: float) -> list[tuple[str, float]]:
    """Fault probability for each component during one second."""
    if faults <= 0:
        return []
    out = []
    if moving:
        out.append(("motor_l", faults * (P_MOTOR * (1 + 30 * h.wear_l ** 3) + (P_OVERHEAT if h.temp_l > OVERHEAT else 0))))
        out.append(("motor_r", faults * (P_MOTOR * (1 + 30 * h.wear_r ** 3) + (P_OVERHEAT if h.temp_r > OVERHEAT else 0))))
        out.append(("lidar", faults * P_LIDAR))
        out.append(("encoder", faults * P_ENCODER))
    if lifting:
        out.append(("lift", faults * P_LIFT * (1 + 30 * h.lift_wear ** 3)))
    if battery:
        out.append(("battery", faults * P_BATTERY * (1 + 20 * ((100 - h.pack) / 40) ** 2)))
    return out


def pick_fault(u: float, hz: list[tuple[str, float]]) -> str | None:
    """Which component fails this second, given one uniform draw ``u``."""
    acc = 0.0
    for name, p in hz:
        acc += p
        if u < acc:
            return name
    return None
