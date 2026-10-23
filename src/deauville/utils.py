"""Small value-normalisation helpers shared by the application."""

from __future__ import annotations

import re
import unicodedata
from datetime import datetime
from typing import Any

from .errors import InvalidValueError


def clean_name(value: Any, label: str) -> str:
    """Trim a required name and reject empty or non-text values."""
    if not isinstance(value, str):
        raise InvalidValueError(f"{label} must be text.")
    result = value.strip()
    if not result:
        raise InvalidValueError(f"{label} cannot be empty.")
    return result


def clean_optional_text(value: Any) -> str:
    """Trim optional text, treating None as an empty string."""
    if value is None:
        return ""
    if not isinstance(value, str):
        raise InvalidValueError("Text values must be strings.")
    return value.strip()


def slugify(value: Any, label: str = "Name") -> str:
    """Return the canonical lower-case ASCII slug for a name or identifier."""
    text = clean_name(value, label)
    ascii_text = (
        unicodedata.normalize("NFKD", text)
        .encode("ascii", "ignore")
        .decode("ascii")
        .lower()
    )
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_text).strip("-")
    if not slug:
        raise InvalidValueError(f"{label} cannot produce a valid slug.")
    return slug


def parse_local_datetime(value: Any, label: str = "Start") -> datetime:
    """Parse a local, timezone-free datetime with minute precision."""
    if isinstance(value, datetime):
        moment = value
    elif isinstance(value, str):
        try:
            moment = datetime.fromisoformat(value)
        except ValueError as error:
            raise InvalidValueError(
                f"{value!r} is not a valid local date and time."
            ) from error
    else:
        raise InvalidValueError(f"{label} must be a local date and time.")

    if moment.tzinfo is not None:
        raise InvalidValueError(f"{label} must not contain a time zone.")
    if moment.second or moment.microsecond:
        raise InvalidValueError(f"{label} must use YYYY-MM-DDTHH:MM.")
    return moment
