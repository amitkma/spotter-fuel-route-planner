"""Import the bundled US gazetteer (`data/us_places.csv.gz`) into the Place table."""

# Standard library imports
import csv
import gzip
from pathlib import Path

# Django imports
from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction

# Spotter imports
from spotter.features.places.models import Place
from spotter.features.places.selectors import reset_place_index
from spotter.features.places.utils import normalize_place_name


class Command(BaseCommand):
    """Load places. Re-running replaces the gazetteer rows (overrides are kept)."""

    help = "Import US places (Census gazetteer) used for offline geocoding."

    def add_arguments(self, parser):
        """Add command arguments."""
        parser.add_argument(
            "--file",
            type=Path,
            default=settings.DATA_DIR / "us_places.csv.gz",
            help="Gzipped CSV with name,state,lat,lng,kind columns.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        """Run the import."""
        path: Path = options["file"]
        opener = gzip.open if path.suffix == ".gz" else open
        places: dict[tuple[str, str], Place] = {}
        with opener(path, "rt", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                key = (normalize_place_name(row["name"]), row["state"])
                if key[0] and key not in places:
                    places[key] = Place(
                        name=row["name"],
                        state=row["state"],
                        normalized_name=key[0],
                        lat=float(row["lat"]),
                        lng=float(row["lng"]),
                        kind=row.get("kind") or Place.Kind.PLACE,
                    )

        overrides = set(
            Place.objects.filter(kind=Place.Kind.OVERRIDE).values_list("normalized_name", "state")
        )
        Place.objects.exclude(kind=Place.Kind.OVERRIDE).delete()
        Place.objects.bulk_create(
            [p for key, p in places.items() if key not in overrides], batch_size=5000
        )
        reset_place_index()
        self.stdout.write(self.style.SUCCESS(f"Imported {len(places)} places from {path}."))
