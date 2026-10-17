"""Numpy geo helpers for matching stations to a route. Coordinates are (lat, lng) degrees."""

# Standard library imports
import math

# Other third-party library imports
import numpy as np
from numpy.typing import NDArray

EARTH_RADIUS_MILES = 3958.7613
METERS_PER_MILE = 1609.344

FloatArray = NDArray[np.float64]


def haversine_miles(lat1, lng1, lat2, lng2):
    """Great-circle distance in miles. Accepts scalars or numpy arrays (broadcasting)."""
    lat1, lng1, lat2, lng2 = (np.radians(v) for v in (lat1, lng1, lat2, lng2))
    a = (
        np.sin((lat2 - lat1) / 2) ** 2
        + np.cos(lat1) * np.cos(lat2) * np.sin((lng2 - lng1) / 2) ** 2
    )
    return 2 * EARTH_RADIUS_MILES * np.arcsin(np.sqrt(np.clip(a, 0.0, 1.0)))


def to_unit_vectors(lats: FloatArray, lngs: FloatArray) -> FloatArray:
    """Convert lat/lng to 3D unit vectors (so a plain euclidean KD-tree works)."""
    lat_r, lng_r = np.radians(lats), np.radians(lngs)
    cos_lat = np.cos(lat_r)
    return np.column_stack((cos_lat * np.cos(lng_r), cos_lat * np.sin(lng_r), np.sin(lat_r)))


def miles_to_chord(miles: float) -> float:
    """Great-circle miles -> chord length on the unit sphere."""
    return 2 * math.sin(miles / (2 * EARTH_RADIUS_MILES))


def chord_to_miles(chord: FloatArray) -> FloatArray:
    """Inverse of `miles_to_chord` (vectorised)."""
    return 2 * EARTH_RADIUS_MILES * np.arcsin(np.clip(chord / 2, 0.0, 1.0))


def cumulative_miles(points: FloatArray) -> FloatArray:
    """Cumulative distance (miles) along a `(n, 2)` lat/lng polyline, starting at 0."""
    if len(points) < 2:
        return np.zeros(len(points))
    steps = haversine_miles(points[:-1, 0], points[:-1, 1], points[1:, 0], points[1:, 1])
    return np.concatenate(([0.0], np.cumsum(steps)))


def resample_polyline(
    points: FloatArray, cumulative: FloatArray, step_miles: float
) -> tuple[FloatArray, FloatArray]:
    """Resample a polyline so consecutive points are at most `step_miles` apart.

    Long straight highways have very few vertices, so a station right next to the road can
    still be far from every vertex. Returns the new points and their cumulative miles.
    """
    total = float(cumulative[-1]) if len(cumulative) else 0.0
    if total == 0.0:
        return points, cumulative
    samples = np.linspace(0.0, total, max(2, math.ceil(total / step_miles) + 1))
    # keep the original vertices so we don't cut corners
    distances = np.union1d(samples, cumulative)
    lats = np.interp(distances, cumulative, points[:, 0])
    lngs = np.interp(distances, cumulative, points[:, 1])
    return np.column_stack((lats, lngs)), distances


def simplify_polyline(points: FloatArray, tolerance_deg: float) -> FloatArray:
    """Ramer-Douglas-Peucker. Only for the geometry we send back, matching uses the full one."""
    n = len(points)
    if n < 3:
        return points
    keep = np.zeros(n, dtype=bool)
    keep[0] = keep[-1] = True
    stack = [(0, n - 1)]
    while stack:
        start, end = stack.pop()
        if end - start < 2:
            continue
        a, b = points[start], points[end]
        segment = points[start + 1 : end]
        ab = b - a
        norm = float(np.hypot(*ab))
        if norm == 0.0:
            dists = np.hypot(*(segment - a).T)
        else:
            dists = np.abs(ab[0] * (segment[:, 1] - a[1]) - ab[1] * (segment[:, 0] - a[0])) / norm
        idx = int(np.argmax(dists))
        if dists[idx] > tolerance_deg:
            split = start + 1 + idx
            keep[split] = True
            stack.extend(((start, split), (split, end)))
    return points[keep]
