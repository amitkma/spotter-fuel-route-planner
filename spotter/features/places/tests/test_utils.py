"""Tests for place name and location parsing helpers."""

# Standard library imports
from unittest import TestCase

# Spotter imports
from spotter.core.types import LatLng
from spotter.features.places.utils import normalize_place_name, parse_location


class NormalizePlaceNameTest(TestCase):
    def test_equivalent_spellings_match(self):
        for name in ("St. Louis", "Saint Louis", "ST LOUIS ", "St Louis"):
            self.assertEqual(normalize_place_name(name), "stlouis")

    def test_punctuation_accents_and_abbreviations(self):
        self.assertEqual(normalize_place_name("Bois D'Arc"), normalize_place_name("Bois D Arc"))
        self.assertEqual(normalize_place_name("Cañon City"), "canoncity")
        self.assertEqual(normalize_place_name("S Coffeyville"), "southcoffeyville")
        self.assertEqual(normalize_place_name("Ft. Worth"), "fortworth")


class ParseLocationTest(TestCase):
    def test_coordinates(self):
        self.assertEqual(parse_location("34.05, -118.24").coordinates, LatLng(34.05, -118.24))
        self.assertEqual(parse_location("40 -74").coordinates, LatLng(40, -74))

    def test_city_state_formats(self):
        cases = {
            "Austin, TX": ("Austin", "TX"),
            "Austin, Texas": ("Austin", "TX"),
            "Austin TX": ("Austin", "TX"),
            "Austin, TX 78701": ("Austin", "TX"),
            "Austin, TX, USA": ("Austin", "TX"),
            "Salt Lake City Utah": ("Salt Lake City", "UT"),
            "kansas city, new mexico": ("kansas city", "NM"),
        }
        for text, (city, state) in cases.items():
            with self.subTest(text=text):
                parsed = parse_location(text)
                self.assertEqual((parsed.city, parsed.state), (city, state))

    def test_foreign_regions(self):
        for text in ("Toronto, ON", "Vancouver, British Columbia", "Monterrey, Mexico"):
            with self.subTest(text=text):
                self.assertTrue(parse_location(text).foreign)
        self.assertFalse(parse_location("Portland, OR").foreign)

    def test_free_text(self):
        parsed = parse_location("1600 Pennsylvania Avenue")
        self.assertIsNone(parsed.coordinates)
        self.assertIsNone(parsed.state)
