"""drf-spectacular (OpenAPI) settings."""

SPECTACULAR_SETTINGS = {
    "TITLE": "Spotter Fuel Route Planner API",
    "DESCRIPTION": (
        "Plans a driving route between two US locations and picks the most cost effective "
        "fuel stops along it, for a vehicle with a 500 mile range that does 10 miles/gallon."
    ),
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "ENUM_NAME_OVERRIDES": {
        name: f"drf_standardized_errors.openapi_serializers.{name}.choices"
        for name in ("ValidationErrorEnum", "ClientErrorEnum", "ServerErrorEnum")
    },
    "POSTPROCESSING_HOOKS": [
        "drf_spectacular.hooks.postprocess_schema_enums",
        "drf_standardized_errors.openapi_hooks.postprocess_schema_enums",
    ],
}
