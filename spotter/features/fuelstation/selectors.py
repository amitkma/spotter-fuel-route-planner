"""Fuel station selectors.

Only ~6.6k stations, so they all live in memory as numpy arrays + a KD-tree. No DB hit per
request.
"""

# Standard library imports
import threading
from dataclasses import dataclass
from typing import cast

# Other third-party library imports
import numpy as np
from scipy.spatial import cKDTree

# Spotter imports
from spotter.core.geo import FloatArray, chord_to_miles, miles_to_chord, to_unit_vectors
from spotter.features.fuelstation.models import FuelStation


@dataclass(frozen=True, slots=True)
class StationInfo:
    """In-memory copy of a station."""

    id: int
    opis_id: int
    name: str
    address: str
    city: str
    state: str
    price: float
    lat: float
    lng: float


@dataclass(frozen=True, slots=True)
class RouteStation:
    """A station that lies along a route."""

    station: StationInfo
    mile: float  # miles from the start
    off_route_miles: float  # straight-line miles off the route


class StationIndex:
    """All geocoded stations, with a fast "which ones are near this route" query."""

    def __init__(self, stations: list[StationInfo]) -> None:
        self.stations = stations
        lats = np.array([s.lat for s in stations], dtype=float)
        lngs = np.array([s.lng for s in stations], dtype=float)
        self.xyz = to_unit_vectors(lats, lngs)

    @classmethod
    def from_db(cls) -> "StationIndex":
        """Build the index from the DB."""
        rows = FuelStation.objects.filter(lat__isnull=False, lng__isnull=False).values_list(
            "id", "opis_id", "name", "address", "city", "state", "retail_price", "lat", "lng"
        )
        stations = [
            StationInfo(i, o, n, a, c, s, float(p), cast(float, lat), cast(float, lng))
            for i, o, n, a, c, s, p, lat, lng in rows
        ]
        return cls(stations)

    def __len__(self) -> int:
        """Return the number of stations in the index."""
        return len(self.stations)

    def along_route(
        self, route_points: FloatArray, route_miles: FloatArray, corridor_miles: float
    ) -> list[RouteStation]:
        """Return stations within `corridor_miles` of the route, sorted by route mile.

        `route_points` should be densely sampled (see `resample_polyline`), `route_miles` is the
        cumulative distance of each point.
        """
        if not self.stations or len(route_points) == 0:
            return []
        tree = cKDTree(to_unit_vectors(route_points[:, 0], route_points[:, 1]))
        chord, vertex = tree.query(self.xyz, distance_upper_bound=miles_to_chord(corridor_miles))
        hits = np.flatnonzero(np.isfinite(chord))
        off_route = chord_to_miles(chord[hits])
        miles = route_miles[vertex[hits]]
        order = np.argsort(miles, kind="stable")
        return [
            RouteStation(self.stations[hits[i]], float(miles[i]), float(off_route[i]))
            for i in order
        ]


_index: StationIndex | None = None
_lock = threading.Lock()


def get_station_index() -> StationIndex:
    """Return the process-wide station index, building it on first use."""
    global _index  # noqa: PLW0603
    if _index is None:
        with _lock:
            if _index is None:
                _index = StationIndex.from_db()
    return _index


def reset_station_index() -> None:
    """Drop the cached index. Needed after re-importing stations, and in tests."""
    global _index  # noqa: PLW0603
    _index = None
