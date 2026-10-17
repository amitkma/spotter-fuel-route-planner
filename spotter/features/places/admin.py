"""Admin for places."""

# Django imports
from django.contrib import admin

# Spotter imports
from spotter.features.places.models import Place


@admin.register(Place)
class PlaceAdmin(admin.ModelAdmin):
    """Admin for Place."""

    list_display = ("name", "state", "lat", "lng", "kind")
    list_filter = ("kind", "state")
    search_fields = ("name", "normalized_name")
