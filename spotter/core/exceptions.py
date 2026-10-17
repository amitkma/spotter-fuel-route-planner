"""Core Exceptions."""

# Django imports
from django.utils.translation import gettext_lazy as _

# Other third-party library imports
from rest_framework import status
from rest_framework.exceptions import APIException


class ExternalAPIException(Exception):
    """Exception raised when any external API raise an exception."""

    is_retryable: bool

    def __init__(self, is_retryable: bool, *args: object) -> None:
        self.is_retryable = is_retryable
        super().__init__(*args)


class UpstreamServiceError(APIException):
    """A third-party service (routing/geocoding) failed or is unavailable."""

    status_code = status.HTTP_502_BAD_GATEWAY
    default_detail = _("An upstream service is unavailable. Please try again.")
    default_code = "upstream_unavailable"


class UnprocessableError(APIException):
    """The request is valid but cannot be fulfilled (e.g. no route, no fuel in range)."""

    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    default_detail = _("The request could not be processed.")
    default_code = "unprocessable"
