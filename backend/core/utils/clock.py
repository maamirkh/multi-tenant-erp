"""Centralized UTC clock — testability shim.

Re-exports the canonical helpers from :mod:`core.utils.datetime` under the
``clock`` module name so callers have a single, mockable import.

Prefer ``utc_now()`` over ``datetime.utcnow()`` (deprecated in Python 3.12)
or ``datetime.now()`` (returns a naive datetime without ``tzinfo``).

Usage::

    from core.utils.clock import utc_now

    now = utc_now()

In tests, patch at the call-site::

    from unittest.mock import patch
    from datetime import UTC, datetime

    fixed = datetime(2026, 1, 1, tzinfo=UTC)
    with patch("core.utils.clock.utc_now", return_value=fixed):
        ...
"""

from core.utils.datetime import ensure_utc
from core.utils.datetime import utcnow as utc_now

__all__ = ["utc_now", "ensure_utc"]
