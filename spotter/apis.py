"""Generic APIs."""

# Django imports
from django.http import JsonResponse

# Other third-party library imports
from rest_framework.decorators import api_view
from rest_framework.request import Request
from rest_framework.response import Response

# Spotter imports
from spotter.features.fuelstation.selectors import get_station_index


@api_view(["GET"])
def api_status(request: Request) -> Response:
    """Health check with the number of stations loaded."""
    return Response({"status": "ok", "fuel_stations": len(get_station_index())})


def api_not_found(request, *args, **kwargs) -> JsonResponse:
    """JSON 404 for any unknown API route."""
    return JsonResponse(
        {
            "type": "client_error",
            "errors": [{"code": "not_found", "detail": "Not found.", "attr": None}],
        },
        status=404,
    )
