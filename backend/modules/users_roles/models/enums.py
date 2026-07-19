"""Users & Roles module enum definitions.

Enum values match spec BR-020 and Section 6.1 exactly.
All enums inherit from ``(str, enum.Enum)`` for JSON serialisation
and VARCHAR storage (not PostgreSQL ENUM types).
"""

from __future__ import annotations

import enum


class MembershipStatus(str, enum.Enum):
    """Lifecycle state of a company membership (spec BR-020).

    State machine transitions are defined in data-model.md Section 2.1.
    """

    pending_invitation = "pending_invitation"
    active = "active"
    inactive = "inactive"
    suspended = "suspended"
    locked = "locked"
    archived = "archived"


class PermissionAction(str, enum.Enum):
    """Action type for a permission entry (spec Section 6.1)."""

    create = "create"
    read = "read"
    update = "update"
    delete = "delete"
    manage = "manage"
    export = "export"
