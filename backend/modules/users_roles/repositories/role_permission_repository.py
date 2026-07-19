"""RolePermissionRepository — data access layer for the RolePermission join table.

Manages the many-to-many relationship between roles and permissions.

Spec reference: data-model.md Section 2.4, tasks T024.
"""

from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from modules.users_roles.models.role_permission import RolePermission

logger = logging.getLogger(__name__)


class RolePermissionRepository:
    """Data access for the ``role_permissions`` table.

    Args:
        db: SQLAlchemy ``Session`` injected by the FastAPI ``get_db`` dependency.
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, role_permission: RolePermission) -> RolePermission:
        """Persist a new role-permission mapping."""
        self.db.add(role_permission)
        self.db.flush()
        return role_permission

    def delete_by_role_id(self, role_id: UUID) -> int:
        """Delete all permission mappings for a role. Returns count deleted."""
        stmt = delete(RolePermission).where(RolePermission.role_id == role_id)
        result = self.db.execute(stmt)
        return result.rowcount  # type: ignore[return-value]

    def get_permissions_for_role(self, role_id: UUID) -> list[RolePermission]:
        """Return all permission mappings for a role."""
        stmt = (
            select(RolePermission)
            .where(RolePermission.role_id == role_id)
            .order_by(RolePermission.permission_id)
        )
        return list(self.db.execute(stmt).scalars().all())

    def get_permission_codes_for_role(self, role_id: UUID) -> set[str]:
        """Return a set of permission codes granted to a role."""
        stmt = select(RolePermission.permission_id).where(
            RolePermission.role_id == role_id
        )
        return set(self.db.execute(stmt).scalars().all())

    def bulk_set_permissions_for_role(
        self, role_id: UUID, permission_codes: set[str]
    ) -> None:
        """Replace all permission mappings for a role with the given set.

        Deletes existing mappings and inserts the new set in a single
        flush cycle.
        """
        self.delete_by_role_id(role_id)
        for code in sorted(permission_codes):
            rp = RolePermission(role_id=role_id, permission_id=code)
            self.db.add(rp)
        self.db.flush()
        logger.debug(
            "Permissions set for role",
            extra={"role_id": str(role_id), "count": len(permission_codes)},
        )
