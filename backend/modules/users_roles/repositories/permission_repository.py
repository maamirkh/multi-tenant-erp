"""PermissionRepository — data access layer for the Permission model.

Permissions are global (not company-scoped) and read-only.
They are seeded via the RoleSeedService, not via direct API calls.

Spec reference: data-model.md Section 2.3, tasks T023.
"""

from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from modules.users_roles.models.permission import Permission

logger = logging.getLogger(__name__)


class PermissionRepository:
    """Read-only data access for the ``permissions`` table.

    Args:
        db: SQLAlchemy ``Session`` injected by the FastAPI ``get_db`` dependency.
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, permission_id: str) -> Permission | None:
        """Return the permission with the given ID, or ``None``."""
        stmt = select(Permission).where(Permission.id == permission_id)
        return self.db.execute(stmt).scalars().one_or_none()

    def get_by_code(self, code: str) -> Permission | None:
        """Return the permission with the given code, or ``None``."""
        stmt = select(Permission).where(Permission.code == code)
        return self.db.execute(stmt).scalars().one_or_none()

    def list_all(self) -> list[Permission]:
        """Return all permissions ordered by module then code."""
        stmt = select(Permission).order_by(Permission.module, Permission.code)
        return list(self.db.execute(stmt).scalars().all())

    def list_by_module(self, module: str) -> list[Permission]:
        """Return all permissions for a specific module."""
        stmt = (
            select(Permission)
            .where(Permission.module == module)
            .order_by(Permission.code)
        )
        return list(self.db.execute(stmt).scalars().all())

    def get_by_codes(self, codes: set[str]) -> list[Permission]:
        """Return all permissions matching the given codes."""
        if not codes:
            return []
        stmt = (
            select(Permission)
            .where(Permission.code.in_(codes))
            .order_by(Permission.code)
        )
        return list(self.db.execute(stmt).scalars().all())
