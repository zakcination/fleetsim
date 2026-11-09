"""fleetsim: simulated multi-robot fulfillment (task allocation + MAPF + analytics)."""

from .grid import Grid
from .sim import SimConfig, SimResult, run

__all__ = ["Grid", "SimConfig", "SimResult", "run"]
__version__ = "0.2.0"
