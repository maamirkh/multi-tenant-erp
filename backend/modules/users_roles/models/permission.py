"""Permission ORM model — global capability catalogue.

Permissions are platform-wide (not company-scoped).  They represent
discrete capabilities that can be assigned to roles via the
``role_permissions`` join table.

Spec reference: data-model.md Section 2.3, spec Section 6.1.
"""

from __future__ import annotations

from sqlalchemy import DateTime, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from core.database.base import Base


class Permission(Base):
    """Global permission record.

    Does NOT inherit from ``BaseModel`` or ``TenantBaseModel`` because
    permissions are global.  Uses explicit ``id`` and ``created_at``.
    """

    __tablename__ = "permissions"
    __table_args__ = (Index("ix_permissions_module", "module"),)

    id: Mapped[str] = mapped_column(
        String(100),
        primary_key=True,
        doc="Permission code in dot-notation (e.g. 'members.create'). Also serves as PK.",
    )

    code: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        unique=True,
        doc="Dot-notation permission code. Same as id for this entity.",
    )

    label: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        doc="Human-readable permission name.",
    )

    module: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        doc="Module group (e.g. 'members', 'roles', 'companies').",
    )

    action: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        doc="Action type (create, read, update, delete, manage).",
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        doc="Detailed description of the permission.",
    )

    created_at: Mapped[str] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        doc="UTC timestamp of record creation.",
    )
