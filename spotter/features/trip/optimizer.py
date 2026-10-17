"""Cheapest refuelling plan along a fixed route.

Fixed-route "gas station problem", solved exactly with a DP over (station, fuel level).
Fuel is in 1-mile units by default, so each station is a ~500-long vector and a few numpy ops.
Coast to coast takes a few ms.

Minimises `fuel cost + stop_penalty * stops`. With penalty 0 you get the true cheapest plan,
which tends to stop every few miles for 1 gallon. The penalty isn't in the reported cost.

Recurrence, for station i with price per mile `p`:
    arrive[f]  = min cost to reach station i with f miles of fuel left
    stop[g]    = min over f <= g of (arrive[f] + (g - f) * p) + penalty
               = g * p + prefix_min(arrive[f] - f * p)[g] + penalty
    leave[g]   = min(arrive[g], stop[g])
    arrive'[f] = leave[f + leg]                (drive to the next station)
"""

# Standard library imports
from collections.abc import Sequence
from dataclasses import dataclass
from typing import TypeVar

# Other third-party library imports
import numpy as np

T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class Candidate[T]:
    """A station along the route that fuel can be bought at."""

    mile: float
    price: float  # USD per gallon
    ref: T  # caller data, e.g. the station itself


@dataclass(frozen=True, slots=True)
class FuelStop[T]:
    """Fuel bought at one station."""

    candidate: Candidate[T]
    gallons: float
    cost: float
    fuel_on_arrival_miles: float


@dataclass(frozen=True, slots=True)
class FuelPlan[T]:
    """The full refuelling plan."""

    stops: list[FuelStop[T]]
    total_gallons: float
    total_cost: float


class NoFeasiblePlanError(Exception):
    """Some stretch of the route is longer than the vehicle's range with no station in it."""

    def __init__(self, gap_start_mile: float, gap_end_mile: float) -> None:
        self.gap_start_mile = gap_start_mile
        self.gap_end_mile = gap_end_mile
        super().__init__(
            f"No fuel station within range between mile {gap_start_mile:.0f} "
            f"and mile {gap_end_mile:.0f}."
        )


def plan_fuel_stops[T](
    candidates: Sequence[Candidate[T]],
    total_miles: float,
    range_miles: float,
    mpg: float,
    start_fuel_miles: float = 0.0,
    stop_penalty: float = 0.0,
    resolution_miles: float = 1.0,
) -> FuelPlan[T]:
    """Return the plan minimising fuel cost + `stop_penalty` per stop.

    `candidates` can be in any order. `start_fuel_miles` is free fuel already in the tank.
    Raises NoFeasiblePlanError if there's a gap longer than the range.
    """
    unit = resolution_miles
    capacity = round(range_miles / unit)
    destination = round(total_miles / unit)
    start_fuel = min(round(start_fuel_miles / unit), capacity)
    if destination <= start_fuel:
        return FuelPlan([], 0.0, 0.0)

    stations = sorted((c for c in candidates if 0.0 <= c.mile <= total_miles), key=lambda c: c.mile)
    positions = [round(c.mile / unit) for c in stations]
    _check_gaps(positions, destination, start_fuel, capacity, unit)

    levels = np.arange(capacity + 1)
    inf = np.inf
    arrive = np.full(capacity + 1, inf)
    arrive[start_fuel - positions[0]] = 0.0

    stopped: list[np.ndarray] = []  # per station: did we stop, for each fuel level after it
    bought_from: list[np.ndarray] = []  # per station: fuel level on arrival, if we stopped
    for i, station in enumerate(stations):
        price_per_unit = station.price * unit / mpg
        shifted = arrive - levels * price_per_unit
        running_min = np.minimum.accumulate(shifted)
        # argmin of the running min, latest on ties (= buy as little as possible)
        argmin = np.maximum.accumulate(np.where(shifted <= running_min, levels, 0))
        stop = levels * price_per_unit + running_min + stop_penalty
        is_stop = stop < arrive
        leave = np.where(is_stop, stop, arrive)
        stopped.append(is_stop)
        bought_from.append(argmin)

        next_position = positions[i + 1] if i + 1 < len(stations) else destination
        leg = next_position - positions[i]
        arrive = np.full(capacity + 1, inf)
        if leg <= capacity:
            arrive[: capacity + 1 - leg] = leave[leg:]

    if not np.isfinite(arrive).any():  # pragma: no cover - _check_gaps guarantees a path
        raise NoFeasiblePlanError(0.0, total_miles)

    # backtrack from the destination
    fuel = int(np.argmin(arrive))
    stops: list[FuelStop[T]] = []
    for i in range(len(stations) - 1, -1, -1):
        next_position = positions[i + 1] if i + 1 < len(stations) else destination
        fuel += next_position - positions[i]  # fuel when leaving station i
        if stopped[i][fuel]:
            arrived_with = int(bought_from[i][fuel])
            gallons = (fuel - arrived_with) * unit / mpg
            stops.append(
                FuelStop(stations[i], gallons, gallons * stations[i].price, arrived_with * unit)
            )
            fuel = arrived_with

    stops.reverse()
    return FuelPlan(stops, sum(s.gallons for s in stops), sum(s.cost for s in stops))


def _check_gaps(
    positions: list[int], destination: int, start_fuel: int, capacity: int, unit: float
) -> None:
    """Raise a precise error for the first stretch the vehicle can't cover."""
    if not positions or positions[0] > start_fuel:
        raise NoFeasiblePlanError(0.0, (positions[0] if positions else destination) * unit)
    for here, there in zip(positions, [*positions[1:], destination], strict=True):
        if there - here > capacity:
            raise NoFeasiblePlanError(here * unit, there * unit)
