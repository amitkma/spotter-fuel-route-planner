"""APIs for trip planning."""

# Standard library imports
from urllib.parse import urlencode

# Django imports
from django.urls import reverse

# Other third-party library imports
from drf_spectacular.utils import OpenApiExample, OpenApiParameter, extend_schema
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

# Spotter imports
from spotter.features.trip.serializers import TripPlanRequestSerializer, TripPlanSerializer
from spotter.features.trip.services import plan_trip

DESCRIPTION = (
    "Plans the driving route between two locations in the USA and picks the cheapest fuel "
    "stops along it (500 mile range, 10 mpg). The response includes the total fuel cost, "
    "each stop, a GeoJSON map of the route and stops, and a link to an interactive map. "
    "It makes at most one routing API call per new route, and repeated routes are cached."
)


@extend_schema(tags=["Trips"])
class TripPlanAPI(APIView):
    """Plan a trip with optimal fuel stops."""

    def _respond(self, request: Request, data: dict) -> Response:
        serializer = TripPlanRequestSerializer(data=data)
        serializer.is_valid(raise_exception=True)
        params = serializer.validated_data
        plan = plan_trip(params["start"], params["finish"], params.get("stop_penalty"))
        map_url = request.build_absolute_uri(f"{reverse('trip-map')}?{urlencode(params)}")
        return Response(TripPlanSerializer(plan, context={"map_url": map_url}).data)

    @extend_schema(
        summary="Plan a trip (query parameters)",
        description=DESCRIPTION,
        parameters=[
            OpenApiParameter(
                "start",
                str,
                required=True,
                examples=[
                    OpenApiExample("City", value="New York, NY"),
                    OpenApiExample("Coordinates", value="40.7128,-74.0060"),
                ],
            ),
            OpenApiParameter(
                "finish",
                str,
                required=True,
                examples=[
                    OpenApiExample("City", value="Los Angeles, CA"),
                ],
            ),
            OpenApiParameter(
                "stop_penalty",
                float,
                description=(
                    "USD charged per stop while optimising (default 5). 0 = absolute cheapest."
                ),
            ),
        ],
        responses=TripPlanSerializer,
    )
    def get(self, request: Request) -> Response:
        """Plan a trip from `?start=...&finish=...`."""
        return self._respond(request, request.query_params.dict())

    @extend_schema(
        summary="Plan a trip (JSON body)",
        description=DESCRIPTION,
        request=TripPlanRequestSerializer,
        responses=TripPlanSerializer,
        examples=[
            OpenApiExample(
                "Chicago to Houston",
                value={"start": "Chicago, IL", "finish": "Houston, TX"},
                request_only=True,
            )
        ],
    )
    def post(self, request: Request) -> Response:
        """Plan a trip from a JSON body."""
        return self._respond(request, request.data if isinstance(request.data, dict) else {})
