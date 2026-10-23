"""Errors raised by the festival domain and its storage."""


class FestivalError(Exception):
    """Base class for errors that can be explained to a festival organiser."""

    status_code = 422


class NotFoundError(FestivalError):
    """The requested venue, artist or performance does not exist."""

    status_code = 404


class ConflictError(FestivalError):
    """The requested change conflicts with existing festival data."""

    status_code = 409


class InvalidValueError(FestivalError):
    """A value violates a rule of the festival."""

    status_code = 422


class StorageError(Exception):
    """The festival data could not be read or written."""

    status_code = 500
