"""RolePermission ORM model — many-to-many join between roles and permissions.

Cascade behaviour: when a role is deleted, its permission mappings are
deleted via ON DELETE CASCADE.  Permissions cannot be deleted if mapped.

Spec reference: data-model.md Section 2.4.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.database.base import Base

if TYPE_CHECKING:
    from modules.users_roles.models.permission import Permission
    from modules.users_roles.models.role import Role


class RolePermission(Base):
    """Join entity linking a role to a permission.

    Uses its own ``id`` and ``created_at`` columns (not inheriting from
    ``BaseModel`` to avoid unnecessary ``updated_at`` on an append-only
    join table).
    """

    __tablename__ = "role_permissions"
    __table_args__ = (
        UniqueConstraint(
            "role_id", "permission_id", name="uq_role_permissions_role_permission"
        ),
        Index("ix_role_permissions_permission_id", "permission_id"),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
        doc="Primary key; UUID generated server-side.",
    )

    role_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "roles.id", name="fk_role_permissions_role_id_roles", ondelete="CASCADE"
        ),
        nullable=False,
        doc="The role receiving this permission.",
    )

    permission_id: Mapped[str] = mapped_column(
        String(100),
        ForeignKey(
            "permissions.id",
            name="fk_role_permissions_permission_id_permissions",
            ondelete="RESTRICT",
        ),
        nullable=False,
        doc="The permission being granted.",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        doc="When this mapping was created.",
    )

    # ── Relationships ───────────────────────────────────────────────────────

    role: Mapped[Role] = relationship(
        "Role",
        back_populates="role_permissions",
        lazy="select",
    )

    permission: Mapped[Permission] = relationship(
        "Permission",
        lazy="select",
    )
