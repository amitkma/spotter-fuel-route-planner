"""App config for the places feature."""

# Django imports
from django.apps import AppConfig


class PlacesConfig(AppConfig):
    """Places feature app config."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "spotter.features.places"
    label = "places"
