"""Category ORM model — hierarchical product category tree.

A Category can be a root (parent_id=NULL) or a sub-category (parent_id set).
Unlimited depth is supported via the self-referencing FK; the application
layer enforces a maximum depth and circular-reference prevention.

Multi-tenancy: Inherits ``company_id`` from ``TenantBaseModel``.

Spec ref: specs/005-inventory-management/spec.md §14
Data model: specs/005-inventory-management/data-model.md §1.2 / §2
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from core.database.models.tenant_base import TenantBaseModel

if TYPE_CHECKING:
    pass


class Category(TenantBaseModel):
    """Product category node.

    Inherits ``id``, ``created_at``, ``updated_at``, ``company_id``,
    ``created_by``, ``is_deleted``, ``deleted_at`` from ``TenantBaseModel``.

    ``status`` uses VARCHAR with CHECK constraint (not ENUM) for forward
    compatibility — same pattern as existing modules.
    """

    __tablename__ = "inventory_categories"
    __table_args__ = (
        UniqueConstraint(
            "company_id",
            "code",
            name="uq_inv_categories_company_code",
        ),
        Index("ix_inv_categories_company_id", "company_id"),
        Index("ix_inv_categories_parent_id", "parent_id"),
        Index("ix_inv_categories_company_status", "company_id", "status"),
        CheckConstraint(
            "status IN ('active', 'inactive')",
            name="ck_inv_categories_status",
        ),
        CheckConstraint(
            "sort_order >= 0",
            name="ck_inv_categories_sort_order",
        ),
        {"comment": "Hierarchical product category tree, scoped per company"},
    )

    code: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        doc="Unique category code per company (e.g. 'ELEC-001')",
    )

    name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        doc="Human-readable category name",
    )

    description: Mapped[str | None] = mapped_column(
        String(1000),
        nullable=True,
        doc="Optional description",
    )

    parent_id: Mapped[str | None] = mapped_column(
        PG_UUID(as_uuid=False),
        ForeignKey("inventory_categories.id", ondelete="RESTRICT"),
        nullable=True,
        doc="FK to parent Category — NULL for root categories",
    )

    sort_order: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
        doc="Display sort order within a parent (ascending)",
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default="active",
        doc="'active' or 'inactive'",
    )
