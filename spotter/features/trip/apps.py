"""App config for the trip feature."""

# Django imports
from django.apps import AppConfig


class TripConfig(AppConfig):
    """Trip feature app config."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "spotter.features.trip"
    label = "trip"
