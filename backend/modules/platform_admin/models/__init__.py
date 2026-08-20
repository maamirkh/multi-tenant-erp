"""Platform Administration module ORM models.

All models are imported here to ensure the test suite's
``Base.metadata.create_all()`` can resolve every Platform table.

Import order follows dependency order (parent before child tables) —
``PlatformAuditEvent``/``PlatformSession`` reference ``PlatformAdministrator``
via FK, ``PlatformRefreshToken`` references ``PlatformSession``, and the
RBAC join tables (``PlatformRolePermission``, ``PlatformAdminRoleAssignment``)
reference ``PlatformPermission``/``PlatformRole``/``PlatformAdministrator``.
"""

from modules.platform_admin.models.platform_administrator import PlatformAdministrator
from modules.platform_admin.models.platform_audit_event import PlatformAuditEvent
from modules.platform_admin.models.platform_rbac import (
    PlatformAdminRoleAssignment,
    PlatformPermission,
    PlatformRole,
    PlatformRolePermission,
)
from modules.platform_admin.models.platform_refresh_token import PlatformRefreshToken
from modules.platform_admin.models.platform_session import PlatformSession

__all__ = [
    "PlatformAdminRoleAssignment",
    "PlatformAdministrator",
    "PlatformAuditEvent",
    "PlatformPermission",
    "PlatformRefreshToken",
    "PlatformRole",
    "PlatformRolePermission",
    "PlatformSession",
]
