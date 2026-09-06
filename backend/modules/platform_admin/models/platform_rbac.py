"""Platform RBAC ORM models — genuinely enforced, permission-code-based
(ADR-2, deliberately not mirroring the tenant `require_rank()` pattern,
which plan.md §3.2 confirms is decorative — production authorization there
never consults `Permission`/`RolePermission` at all).

Persistence for `platform_permissions`, `platform_roles`,
`platform_role_permissions`, `platform_admin_role_assignments` (migration
057, data-model.md "Identity & Session"). `PlatformPermission.code` is the
primary key, mirroring the tenant `Permission` model's code-as-PK
convention — the only one of the four RBAC tables that does not inherit
`BaseModel`, since migration 057 gives it no separate `id` column.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from core.database.base import Base
from core.database.models.base_model import BaseModel


class PlatformPermission(Base):
    """Platform permission catalogue entry — code-as-PK, e.g.
    `"platform.tenants.suspend"`. Configuration data, not an enum
    (FR-9A-140) — seeded by `PlatformRbacSeedService` (T062), never a
    migration.
    """

    __tablename__ = "platform_permissions"

    code: Mapped[str] = mapped_column(
        String(100),
        primary_key=True,
        doc="Dot-notation permission code; also the primary key.",
    )

    label: Mapped[str] = mapped_column(
        String(200), nullable=False, doc="Human-readable permission name."
    )

    area: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        doc="Permission area grouping, per spec.md §15.1's table.",
    )

    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class PlatformRole(BaseModel):
    """Platform RBAC role — `code` is configuration data, not an enum
    (FR-9A-140, Constitution §46); new roles need no migration.
    """

    __tablename__ = "platform_roles"

    code: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        unique=True,
        doc="e.g. 'platform_owner', 'platform_operations_admin'.",
    )

    name: Mapped[str] = mapped_column(String(150), nullable=False, doc="Display name.")

    description: Mapped[str | None] = mapped_column(Text, nullable=True)


class PlatformRolePermission(BaseModel):
    """Bundle of permissions granted by a Platform Role."""

    __tablename__ = "platform_role_permissions"

    role_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("platform_roles.id", ondelete="CASCADE"),
        nullable=False,
    )

    permission_id: Mapped[str] = mapped_column(
        String(100),
        ForeignKey("platform_permissions.code", ondelete="RESTRICT"),
        nullable=False,
    )


class PlatformAdminRoleAssignment(BaseModel):
    """A Platform Role assigned to a Platform Administrator. Effective
    permissions = union across all of an administrator's assigned roles'
    permissions (FR-9A-142).
    """

    __tablename__ = "platform_admin_role_assignments"

    platform_administrator_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("platform_administrators.id", ondelete="CASCADE"),
        nullable=False,
    )

    role_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("platform_roles.id", ondelete="RESTRICT"),
        nullable=False,
    )

    assigned_by: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("platform_administrators.id"),
        nullable=True,
        doc="Null only for the bootstrap-created first assignment.",
    )

    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
