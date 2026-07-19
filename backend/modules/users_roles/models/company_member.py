"""CompanyMember ORM model — binds a User to a Company with role and status.

The ``company_members`` table is the core join entity of Epic 4.  Every
membership carries a role assignment, lifecycle status, and optional
employee metadata.

Multi-tenancy: Inherits ``company_id`` from ``TenantBaseModel``.
All queries MUST filter by ``company_id``.

Spec reference: data-model.md Section 2.1.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.database.models.tenant_base import TenantBaseModel

if TYPE_CHECKING:
    from modules.auth.models.user import User
    from modules.users_roles.models.role import Role


class CompanyMember(TenantBaseModel):
    """Company membership record linking a user to a company with a role.

    Inherits ``id``, ``created_at``, ``updated_at``, ``company_id``,
    ``created_by``, ``is_deleted``, ``deleted_at`` from ``TenantBaseModel``.
    """

    __tablename__ = "company_members"
    __table_args__ = (
        UniqueConstraint(
            "company_id", "user_id", name="uq_company_members_company_user"
        ),
        Index(
            "uq_company_members_company_employee_id",
            "company_id",
            "employee_id",
            unique=True,
            postgresql_where=sa.text("employee_id IS NOT NULL"),
        ),
        Index("ix_company_members_company_status", "company_id", "status"),
        Index("ix_company_members_user_id", "user_id"),
        Index("ix_company_members_role_id", "role_id"),
        Index("ix_company_members_company_department", "company_id", "department"),
        CheckConstraint(
            "status IN ('pending_invitation','active','inactive','suspended','locked','archived')",
            name="ck_company_members_status",
        ),
    )

    # ── Core fields ─────────────────────────────────────────────────────────

    user_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "users.id", name="fk_company_members_user_id_users", ondelete="RESTRICT"
        ),
        nullable=False,
        doc="The user account that holds this membership.",
    )

    role_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "roles.id", name="fk_company_members_role_id_roles", ondelete="RESTRICT"
        ),
        nullable=False,
        doc="The role assigned to this member within the company.",
    )

    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        server_default="'pending_invitation'",
        doc="Membership lifecycle state (spec BR-020).",
    )

    # ── Employee information ────────────────────────────────────────────────

    employee_id: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        doc="Company-assigned employee identifier. Unique per company.",
    )

    job_title: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        doc="Position title within the company.",
    )

    department: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        doc="Department name (free-text, ADR-E4-004).",
    )

    work_phone: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
        doc="Work contact phone number.",
    )

    hire_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
        doc="Employment start date.",
    )

    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        doc="Internal notes about the member (visible to Admin+ only).",
    )

    # ── Invitation tracking ─────────────────────────────────────────────────

    invited_by: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "users.id", name="fk_company_members_invited_by_users", ondelete="RESTRICT"
        ),
        nullable=True,
        doc="User who created this membership.",
    )

    invitation_accepted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        doc="When the invitation was accepted by the user.",
    )

    # ── Status metadata ─────────────────────────────────────────────────────

    suspended_reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        doc="Required when status is 'suspended'.",
    )

    deletion_reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        doc="Required when status is 'archived'.",
    )

    # ── Relationships ───────────────────────────────────────────────────────

    user: Mapped[User] = relationship(
        "User",
        foreign_keys=[user_id],
        lazy="select",
    )

    role: Mapped[Role] = relationship(
        "Role",
        foreign_keys=[role_id],
        lazy="select",
    )

    inviter: Mapped[User | None] = relationship(
        "User",
        foreign_keys=[invited_by],
        lazy="select",
    )
