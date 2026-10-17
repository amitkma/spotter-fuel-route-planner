"""Urls for the trip planner."""

# Django imports
from django.urls import path

# Spotter imports
from spotter.features.trip import apis, views

urlpatterns = [
    path("api/v1/trips/plan/", apis.TripPlanAPI.as_view(), name="trip-plan"),
    path("trips/map/", views.trip_map, name="trip-map"),
]
