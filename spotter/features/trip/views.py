"""HTML views for trips."""

# Django imports
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render

# Other third-party library imports
from rest_framework.exceptions import APIException, ValidationError

# Spotter imports
from spotter.features.trip.serializers import TripPlanRequestSerializer, TripPlanSerializer
from spotter.features.trip.services import plan_trip


def _error_message(exc: APIException) -> str:
    detail = exc.detail
    if isinstance(detail, dict):
        return " ".join(str(m) for messages in detail.values() for m in messages)
    if isinstance(detail, list):
        return " ".join(str(m) for m in detail)
    return str(detail)


def trip_map(request: HttpRequest) -> HttpResponse:
    """Leaflet map of the route and stops. Same service as the API, so it shares the route cache."""
    context: dict = {"start": request.GET.get("start", ""), "finish": request.GET.get("finish", "")}
    serializer = TripPlanRequestSerializer(data=request.GET.dict())
    status = 200
    if context["start"] or context["finish"]:
        try:
            serializer.is_valid(raise_exception=True)
            params = serializer.validated_data
            plan = plan_trip(params["start"], params["finish"], params.get("stop_penalty"))
            context["plan"] = TripPlanSerializer(plan).data
        except ValidationError as e:
            context["error"], status = _error_message(e), 400
        except APIException as e:
            context["error"], status = _error_message(e), e.status_code
    return render(request, "trip/map.html", context, status=status)
