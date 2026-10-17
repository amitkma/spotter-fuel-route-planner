"""Models for places (offline US gazetteer)."""

# Django imports
from django.db import models

# Spotter imports
from spotter.core.models import BaseModel, sane_str


class Place(BaseModel):
    """A US city/town and its centroid (Census gazetteer). Used for offline geocoding."""

    class Kind(models.TextChoices):
        """Source of the place."""

        PLACE = "place", "Incorporated place / CDP"
        COUSUB = "cousub", "County subdivision"
        OVERRIDE = "override", "Manual / online geocoded"

    name = models.CharField(max_length=128)
    state = models.CharField(max_length=2, help_text="USPS state code, e.g. TX")
    normalized_name = models.CharField(max_length=128, help_text="See `normalize_place_name`")
    lat = models.FloatField()
    lng = models.FloatField()
    kind = models.CharField(max_length=10, choices=Kind.choices, default=Kind.PLACE)

    class Meta:
        """Metadata for Place."""

        constraints = [
            models.UniqueConstraint(
                fields=["normalized_name", "state"], name="unique_place_name_per_state"
            )
        ]

    __str__ = sane_str("name", "state")
