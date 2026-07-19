"""Role ORM model — named role with numeric rank for hierarchy.

Roles are company-scoped.  Each company gets a copy of the 8 system roles
seeded on creation, plus the ability to create custom roles.

Multi-tenancy: Inherits ``company_id`` from ``TenantBaseModel``.

Spec reference: data-model.md Section 2.2, spec FR-040.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    false,
    true,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.database.models.tenant_base import TenantBaseModel

if TYPE_CHECKING:
    from modules.users_roles.models.role_permission import RolePermission


class Role(TenantBaseModel):
    """Role definition within a company.

    Inherits ``id``, ``created_at``, ``updated_at``, ``company_id``,
    ``created_by``, ``is_deleted``, ``deleted_at`` from ``TenantBaseModel``.
    """

    __tablename__ = "roles"
    __table_args__ = (
        UniqueConstraint("company_id", "slug", name="uq_roles_company_slug"),
        Index("ix_roles_company_is_active", "company_id", "is_active"),
        Index("ix_roles_company_rank", "company_id", "rank"),
        CheckConstraint(
            "rank > 0 AND rank <= 100",
            name="ck_roles_rank_range",
        ),
    )

    name: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        doc="Human-readable role name.",
    )

    slug: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        doc="URL-safe identifier; unique per company.",
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        doc="Purpose description for the role.",
    )

    rank: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        doc="Numeric hierarchy value. Higher rank = more authority.",
    )

    is_system: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=false(),
        doc="True for system-seeded roles; cannot be deleted or renamed.",
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=true(),
        doc="Soft disable without deletion.",
    )

    # ── Relationships ───────────────────────────────────────────────────────

    role_permissions: Mapped[list[RolePermission]] = relationship(
        "RolePermission",
        back_populates="role",
        cascade="all, delete-orphan",
        lazy="select",
    )
