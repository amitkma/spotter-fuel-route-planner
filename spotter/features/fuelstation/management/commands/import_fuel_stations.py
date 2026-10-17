"""Import the OPIS fuel price list into the FuelStation table."""

# Standard library imports
from dataclasses import asdict
from pathlib import Path

# Django imports
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

# Spotter imports
from spotter.features.fuelstation.services import import_fuel_stations
from spotter.features.places.models import Place


class Command(BaseCommand):
    """Load and geocode fuel stations. Re-running replaces all stations."""

    help = "Import fuel stations and prices from the OPIS CSV."

    def add_arguments(self, parser):
        """Add command arguments."""
        parser.add_argument(
            "--file",
            type=Path,
            default=settings.DATA_DIR / "fuel-prices-for-be-assessment.csv",
            help="OPIS price list CSV.",
        )
        parser.add_argument(
            "--geocode-cache",
            type=Path,
            default=settings.DATA_DIR / "geocoded_cities.json",
            help="JSON cache of cities geocoded online (committed to the repo).",
        )
        parser.add_argument(
            "--offline",
            action="store_true",
            help="Never call the online geocoder; use the gazetteer and cache only.",
        )

    def handle(self, *args, **options):
        """Run the import."""
        if not Place.objects.exists():
            raise CommandError("No places found. Run `python manage.py import_places` first.")
        report = import_fuel_stations(
            path=options["file"],
            geocode_cache_file=options["geocode_cache"],
            online_geocoding=not options["offline"],
            log=self.stdout.write,
        )
        for key, value in asdict(report).items():
            self.stdout.write(f"  {key:<16} {value}")
        self.stdout.write(self.style.SUCCESS(f"Imported {report.stations} fuel stations."))
