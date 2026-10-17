"""Tests for geo helpers."""

# Standard library imports
from unittest import TestCase

# Other third-party library imports
import numpy as np

# Spotter imports
from spotter.core.geo import (
    chord_to_miles,
    cumulative_miles,
    haversine_miles,
    miles_to_chord,
    resample_polyline,
    simplify_polyline,
)


class GeoTest(TestCase):
    def test_haversine_known_distance(self):
        # New York -> Los Angeles is ~2445 miles as the crow flies.
        d = haversine_miles(40.7128, -74.0060, 34.0522, -118.2437)
        self.assertAlmostEqual(float(d), 2445, delta=5)

    def test_chord_round_trip(self):
        for miles in (0.1, 10, 500):
            self.assertAlmostEqual(float(chord_to_miles(np.array(miles_to_chord(miles)))), miles, 6)

    def test_resample_keeps_endpoints_and_spacing(self):
        points = np.array([[30.0, -97.0], [31.0, -97.0]])  # ~69 miles straight north
        miles = cumulative_miles(points)
        dense, dense_miles = resample_polyline(points, miles, 1.0)
        self.assertGreaterEqual(len(dense), 70)
        np.testing.assert_allclose(dense[0], points[0])
        np.testing.assert_allclose(dense[-1], points[-1])
        self.assertLessEqual(np.diff(dense_miles).max(), 1.0 + 1e-9)

    def test_simplify_drops_collinear_points(self):
        line = np.column_stack((np.linspace(30, 31, 100), np.linspace(-97, -96, 100)))
        simplified = simplify_polyline(line, 1e-6)
        self.assertEqual(len(simplified), 2)

    def test_simplify_keeps_corners(self):
        line = np.array([[0, 0], [0.5, 0], [1, 0], [1, 0.5], [1, 1]], dtype=float)
        simplified = simplify_polyline(line, 1e-6)
        self.assertEqual(simplified.tolist(), [[0, 0], [1, 0], [1, 1]])
