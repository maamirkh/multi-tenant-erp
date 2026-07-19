"""Authentication domain enumerations.

All enum values in this module are stored in the database as their
string name (``values_callable=lambda e: [m.value for m in e]`` pattern
is NOT used; SQLAlchemy stores enum names by default for ``PgEnum``).

Keeping enums centralised here avoids circular imports between model files.
"""

from __future__ import annotations

import enum


class AccountStatus(str, enum.Enum):
    """Lifecycle states for a user account.

    Transitions:
        ACTIVE    → LOCKED   (too many failed login attempts)
        LOCKED    → ACTIVE   (lockout duration expires or admin unlock)
        ACTIVE    → INACTIVE (administrative deactivation)
        INACTIVE  → ACTIVE   (administrative reactivation)
        *         → DELETED  (soft-delete; terminal state — no restore)
    """

    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    LOCKED = "LOCKED"
    DELETED = "DELETED"


class AuditEventType(str, enum.Enum):
    """Types of security-relevant events recorded in the audit log.

    Each value maps 1-to-1 with a discrete authentication or account
    lifecycle action.  The string values are stored verbatim in the
    ``audit_logs.event_type`` column.
    """

    LOGIN_SUCCESS = "LOGIN_SUCCESS"
    LOGIN_FAILURE = "LOGIN_FAILURE"
    LOGOUT = "LOGOUT"
    TOKEN_REFRESHED = "TOKEN_REFRESHED"
    ACCOUNT_LOCKED = "ACCOUNT_LOCKED"
    PASSWORD_CHANGED = "PASSWORD_CHANGED"
    PASSWORD_RESET_REQUESTED = "PASSWORD_RESET_REQUESTED"
    PASSWORD_RESET_COMPLETED = "PASSWORD_RESET_COMPLETED"
    EMAIL_VERIFIED = "EMAIL_VERIFIED"
