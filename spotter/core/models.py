"""All common models."""

# Standard library imports
from collections.abc import Callable

# Django imports
from django.db import models


def sane_str(*attrs: str, include_id=True) -> Callable[[object], str]:
    """Sane representation of instances."""
    if "id" not in attrs and "pk" not in attrs and include_id:
        attrs = ("id", *attrs)

    def _str(self: object) -> str:
        pairs = (f"{attr}={getattr(self, attr)!s}" for attr in attrs)
        return f"<{type(self).__name__} at {hex(id(self))}: {', '.join(pairs)}>"

    return _str


class BaseModel(models.Model):
    """Base model that should be subclassed by all other models created in app.

    It contains meta fields that are common in all models.
    """

    created_at = models.DateTimeField(db_index=True, auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        """Metadata for BaseModel."""

        abstract = True
