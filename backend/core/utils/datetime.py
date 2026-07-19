"""Datetime utility functions.

All timestamps in DevSphere ERP are UTC-aware.  This module provides
helpers that enforce that contract so that call sites never create naive
``datetime`` objects accidentally.
"""

from datetime import UTC, datetime


def utcnow() -> datetime:
    """Return the current UTC datetime as a timezone-aware object.

    Always use this function instead of ``datetime.utcnow()`` (which returns
    a naive datetime and is deprecated in Python 3.12).
    """
    return datetime.now(UTC)


def format_iso(dt: datetime) -> str:
    """Return *dt* formatted as an ISO 8601 string.

    Example::

        format_iso(utcnow())  # "2026-07-11T10:00:00.000000+00:00"
    """
    return dt.isoformat()


def ensure_utc(dt: datetime) -> datetime:
    """Return *dt* as a UTC-aware datetime.

    If *dt* is already timezone-aware its timezone is converted to UTC.
    If *dt* is naive it is assumed to be UTC and ``tzinfo=UTC`` is attached.

    Args:
        dt: Any ``datetime`` object, naive or aware.

    Returns:
        A timezone-aware datetime in UTC.
    """
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)
