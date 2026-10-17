"""URLs for Spotter app."""

# Django imports
from django.urls import include, path, re_path
from django.views.generic import RedirectView

# Other third-party library imports
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

# Spotter imports
from spotter.apis import api_not_found, api_status

urlpatterns = [
    path("", RedirectView.as_view(pattern_name="trip-map"), name="home"),
    # API schema URLs
    re_path(r"^api/schema/?$", SpectacularAPIView.as_view(), name="schema"),
    re_path(r"^api/docs/?$", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    # Feature views and API URLs
    path("", include("spotter.features.trip.urls")),
    re_path(r"^api/status/?$", api_status, name="api-status"),
    # Don't add any API endpoint after this route.
    re_path(r"^api.+", api_not_found),
]
