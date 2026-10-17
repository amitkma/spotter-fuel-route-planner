"""Tests for location resolution."""

# Django imports
from django.test import override_settings

# Other third-party library imports
from rest_framework.exceptions import ValidationError

# Spotter imports
from spotter.features.places.services import ApiCallCounter, resolve_location
from spotter.tests.base import BaseTest


@override_settings(GEOCODING_ONLINE_FALLBACK=False)
class ResolveLocationTest(BaseTest):
    def setUp(self):
        super().setUp()
        self.create_place("St. Louis", "MO", 38.63, -90.24)

    def test_city_state_from_gazetteer(self):
        counter = ApiCallCounter()
        location = resolve_location("saint louis, missouri", "start", counter)
        self.assertEqual(location.name, "St. Louis, MO")
        self.assertEqual(location.source, "gazetteer")
        self.assertEqual(counter.total, 0)

    def test_coordinates_near_a_us_place(self):
        location = resolve_location("38.7,-90.3", "start")
        self.assertEqual(location.name, "Near St. Louis, MO")

    def test_coordinates_far_from_any_us_place(self):
        with self.assertRaises(ValidationError):
            resolve_location("48.85,2.35", "start")  # Paris

    def test_unknown_city_without_online_fallback(self):
        with self.assertRaises(ValidationError):
            resolve_location("Gotham, NY", "finish")
