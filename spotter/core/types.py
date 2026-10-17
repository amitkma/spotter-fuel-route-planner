"""Common types."""

# Standard library imports
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class LatLng:
    """A WGS84 coordinate."""

    lat: float
    lng: float

    def rounded(self, ndigits: int = 5) -> "LatLng":
        """Return the coordinate rounded to `ndigits` (5 digits is ~1 m)."""
        return LatLng(round(self.lat, ndigits), round(self.lng, ndigits))
