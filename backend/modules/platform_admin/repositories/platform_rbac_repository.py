"""PlatformRbacRepository — data access for Platform RBAC.

Deliberately does **not** inherit ``BaseRepository`` (mandates `company_id`
filtering — wrong for platform-scoped tables). Write paths `flush()` only,
never `commit()` (ADR-5) — the calling service owns the transaction
boundary, matching every other Platform repository in this module.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from modules.platform_admin.models.platform_administrator import PlatformAdministrator
from modules.platform_admin.models.platform_rbac import (
    PlatformAdminRoleAssignment,
    PlatformPermission,
    PlatformRole,
    PlatformRolePermission,
)


class PlatformRbacRepository:
    """Data access for Platform roles, permissions, and role assignments."""

    def __init__(self, db: Session) -> None:
        self.db = db

    # ------------------------------------------------------------------
    # Permissions (read-only catalogue — seeded by PlatformRbacSeedService)
    # ------------------------------------------------------------------

    def list_permissions(self) -> list[PlatformPermission]:
        stmt = select(PlatformPermission).order_by(PlatformPermission.code)
        return list(self.db.execute(stmt).scalars().all())

    def get_permission(self, code: str) -> PlatformPermission | None:
        return self.db.get(PlatformPermission, code)

    def create_permission(
        self, *, code: str, label: str, area: str, description: str | None = None
    ) -> PlatformPermission:
        """Stage a new permission catalogue entry. Caller commits."""
        permission = PlatformPermission(
            code=code, label=label, area=area, description=description
        )
        self.db.add(permission)
        self.db.flush()
        return permission

    # ------------------------------------------------------------------
    # Roles
    # ------------------------------------------------------------------

    def create_role(
        self, *, code: str, name: str, description: str | None = None
    ) -> PlatformRole:
        """Stage a new role. Caller commits."""
        role = PlatformRole(code=code, name=name, description=description)
        self.db.add(role)
        self.db.flush()
        return role

    def update_role(
        self, role: PlatformRole, *, name: str, description: str | None
    ) -> PlatformRole:
        """Stage a role's name/description update. Caller commits."""
        role.name = name
        role.description = description
        self.db.flush()
        return role

    def get_role_by_id(self, role_id: UUID) -> PlatformRole | None:
        return self.db.get(PlatformRole, role_id)

    def get_role_by_code(self, code: str) -> PlatformRole | None:
        stmt = select(PlatformRole).where(PlatformRole.code == code)
        return self.db.execute(stmt).scalars().one_or_none()

    def list_roles(
        self, *, offset: int = 0, limit: int = 50
    ) -> tuple[list[PlatformRole], int]:
        total = self.db.execute(
            select(func.count()).select_from(PlatformRole)
        ).scalar_one()
        stmt = (
            select(PlatformRole)
            .order_by(PlatformRole.created_at)
            .offset(offset)
            .limit(limit)
        )
        rows = list(self.db.execute(stmt).scalars().all())
        return rows, total

    # ------------------------------------------------------------------
    # Role <-> Permission bundle
    # ------------------------------------------------------------------

    def get_role_permission_codes(self, role_id: UUID) -> frozenset[str]:
        stmt = select(PlatformRolePermission.permission_id).where(
            PlatformRolePermission.role_id == role_id
        )
        return frozenset(self.db.execute(stmt).scalars().all())

    def set_role_permissions(self, role_id: UUID, permission_codes: set[str]) -> None:
        """Replace a role's permission bundle wholesale. Caller commits."""
        self.db.query(PlatformRolePermission).filter(
            PlatformRolePermission.role_id == role_id
        ).delete(synchronize_session=False)
        for code in permission_codes:
            self.db.add(PlatformRolePermission(role_id=role_id, permission_id=code))
        self.db.flush()

    # ------------------------------------------------------------------
    # Administrator <-> Role assignment
    # ------------------------------------------------------------------

    def assign_role(
        self,
        *,
        platform_administrator_id: UUID,
        role_id: UUID,
        assigned_by: UUID | None,
        assigned_at: datetime,
    ) -> PlatformAdminRoleAssignment:
        """Stage a new role assignment. Caller commits."""
        assignment = PlatformAdminRoleAssignment(
            platform_administrator_id=platform_administrator_id,
            role_id=role_id,
            assigned_by=assigned_by,
            assigned_at=assigned_at,
        )
        self.db.add(assignment)
        self.db.flush()
        return assignment

    def remove_assignment(
        self, *, platform_administrator_id: UUID, role_id: UUID
    ) -> None:
        """Stage removal of a role assignment. Caller commits. (Repository
        capability only — no HTTP route exposes this; the contract
        declares no DELETE role-assignment operation, T069.)"""
        self.db.query(PlatformAdminRoleAssignment).filter(
            PlatformAdminRoleAssignment.platform_administrator_id
            == platform_administrator_id,
            PlatformAdminRoleAssignment.role_id == role_id,
        ).delete(synchronize_session=False)
        self.db.flush()

    def get_administrator_role_ids(self, platform_administrator_id: UUID) -> list[UUID]:
        stmt = select(PlatformAdminRoleAssignment.role_id).where(
            PlatformAdminRoleAssignment.platform_administrator_id
            == platform_administrator_id
        )
        return list(self.db.execute(stmt).scalars().all())

    def has_role(self, platform_administrator_id: UUID, role_code: str) -> bool:
        stmt = (
            select(PlatformAdminRoleAssignment.id)
            .join(PlatformRole, PlatformRole.id == PlatformAdminRoleAssignment.role_id)
            .where(
                PlatformAdminRoleAssignment.platform_administrator_id
                == platform_administrator_id,
                PlatformRole.code == role_code,
            )
        )
        return self.db.execute(stmt).scalars().first() is not None

    def count_active_administrators_with_role(self, role_code: str) -> int:
        """Count active PlatformAdministrators holding *role_code*, used by
        the last-Platform-Owner protection (T066)."""
        stmt = (
            select(
                func.count(
                    func.distinct(PlatformAdminRoleAssignment.platform_administrator_id)
                )
            )
            .select_from(PlatformAdminRoleAssignment)
            .join(PlatformRole, PlatformRole.id == PlatformAdminRoleAssignment.role_id)
            .join(
                PlatformAdministrator,
                PlatformAdministrator.id
                == PlatformAdminRoleAssignment.platform_administrator_id,
            )
            .where(
                PlatformRole.code == role_code,
                PlatformAdministrator.is_active == True,  # noqa: E712
            )
        )
        return self.db.execute(stmt).scalar_one()

    def get_active_administrator_ids_with_role(self, role_code: str) -> list[UUID]:
        """List active `PlatformAdministrator` ids holding *role_code*
        (Epic 9A, `RolloutService`, T126 — locates the bootstrap Platform
        Owner as the audit actor for the one-time rollout data steps)."""
        stmt = (
            select(PlatformAdminRoleAssignment.platform_administrator_id)
            .join(PlatformRole, PlatformRole.id == PlatformAdminRoleAssignment.role_id)
            .join(
                PlatformAdministrator,
                PlatformAdministrator.id
                == PlatformAdminRoleAssignment.platform_administrator_id,
            )
            .where(
                PlatformRole.code == role_code,
                PlatformAdministrator.is_active == True,  # noqa: E712
            )
            .distinct()
        )
        return list(self.db.execute(stmt).scalars().all())

    # ------------------------------------------------------------------
    # Effective permissions (FR-9A-142) — resolved per request, never cached
    # ------------------------------------------------------------------

    def get_effective_permissions(
        self, platform_administrator_id: UUID
    ) -> frozenset[str]:
        stmt = (
            select(PlatformRolePermission.permission_id)
            .join(
                PlatformAdminRoleAssignment,
                PlatformAdminRoleAssignment.role_id == PlatformRolePermission.role_id,
            )
            .where(
                PlatformAdminRoleAssignment.platform_administrator_id
                == platform_administrator_id
            )
        )
        return frozenset(self.db.execute(stmt).scalars().all())
