"""Read-side queries for places."""

# Standard library imports
import threading
from dataclasses import dataclass

# Other third-party library imports
import numpy as np
from scipy.spatial import cKDTree

# Spotter imports
from spotter.core.geo import chord_to_miles, to_unit_vectors
from spotter.core.types import LatLng
from spotter.features.places.models import Place
from spotter.features.places.utils import normalize_place_name


def get_place(city: str, state: str) -> Place | None:
    """Return the place matching `city` in `state` (USPS code), if any."""
    return Place.objects.filter(normalized_name=normalize_place_name(city), state=state).first()


@dataclass(frozen=True, slots=True)
class NearestPlace:
    """The closest known US place to a coordinate."""

    name: str
    state: str
    distance_miles: float


class PlaceIndex:
    """KD-tree over all places, for offline reverse geocoding."""

    def __init__(self) -> None:
        rows = list(Place.objects.values_list("name", "state", "lat", "lng"))
        self.names = [(name, state) for name, state, _, _ in rows]
        coords = np.array([(lat, lng) for _, _, lat, lng in rows], dtype=float).reshape(-1, 2)
        self.tree = cKDTree(to_unit_vectors(coords[:, 0], coords[:, 1])) if rows else None

    def nearest(self, point: LatLng) -> NearestPlace | None:
        """Return the nearest place to `point`, or None when there is no data."""
        if self.tree is None:
            return None
        chord, idx = self.tree.query(to_unit_vectors(np.array([point.lat]), np.array([point.lng])))
        name, state = self.names[int(idx[0])]
        return NearestPlace(name, state, float(chord_to_miles(chord)[0]))


_index: PlaceIndex | None = None
_lock = threading.Lock()


def get_place_index() -> PlaceIndex:
    """Return the process-wide place index, building it on first use."""
    global _index  # noqa: PLW0603
    if _index is None:
        with _lock:
            if _index is None:
                _index = PlaceIndex()
    return _index


def reset_place_index() -> None:
    """Drop the cached index (after re-importing places, and in tests)."""
    global _index  # noqa: PLW0603
    _index = None
