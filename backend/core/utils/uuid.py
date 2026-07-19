"""UUID utility functions.

Thin wrappers around the standard library ``uuid`` module so that call
sites are decoupled from the underlying implementation and can be easily
stubbed in tests.
"""

import uuid
from uuid import UUID


def generate_uuid() -> UUID:
    """Return a new random UUID (version 4)."""
    return uuid.uuid4()


def is_valid_uuid(value: str) -> bool:
    """Return ``True`` if *value* is a well-formed UUID string.

    Accepts any UUID version and any case (upper/lower).

    Examples::

        is_valid_uuid("550e8400-e29b-41d4-a716-446655440000")  # True
        is_valid_uuid("not-a-uuid")                             # False
    """
    try:
        uuid.UUID(value)
        return True
    except ValueError:
        return False
