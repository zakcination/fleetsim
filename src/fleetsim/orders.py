"""Poisson order stream: each order is "fetch pod p -> station s -> return p"."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class Order:
    id: int
    pod: int
    station: int
    created: int
    assigned: int = -1
    robot: int = -1
    picked: int = -1  # pod lifted
    at_station: int = -1
    serviced: int = -1
    completed: int = -1  # pod returned to its slot
    free_flow: int = -1  # uncongested errand duration from assignment


class OrderStream:
    """Poisson arrivals at ``rate`` orders/tick; pod and station drawn uniformly."""

    def __init__(self, pods: list[int], stations: list[int], rate: float, seed: int = 0) -> None:
        self.pods = np.asarray(pods)
        self.stations = np.asarray(stations)
        self.rate = rate
        self.rng = np.random.default_rng(seed)
        self.next_id = 0

    def arrivals(self, t: int) -> list[Order]:
        k = int(self.rng.poisson(self.rate))
        out = []
        for _ in range(k):
            out.append(
                Order(
                    id=self.next_id,
                    pod=int(self.rng.choice(self.pods)),
                    station=int(self.rng.choice(self.stations)),
                    created=t,
                )
            )
            self.next_id += 1
        return out
