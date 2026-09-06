"""Tag ORM model — flexible product tagging.

Tags are shared across all products in a company. Each tag has a unique
name per company and an optional display color for UI differentiation.

Multi-tenancy: Inherits ``company_id`` from ``TenantBaseModel``.

Spec ref: specs/005-inventory-management/spec.md §14
Data model: specs/005-inventory-management/data-model.md §2
"""

from __future__ import annotations

from sqlalchemy import Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from core.database.models.tenant_base import TenantBaseModel


class Tag(TenantBaseModel):
    """Product tag for flexible grouping and filtering.

    Invariants:
    - name unique per company (case-insensitive enforced in service)
    """

    __tablename__ = "inventory_tags"
    __table_args__ = (
        UniqueConstraint(
            "company_id",
            "name",
            name="uq_inv_tags_company_name",
        ),
        Index("ix_inv_tags_company_id", "company_id"),
        {"comment": "Product tags for flexible grouping, scoped per company"},
    )

    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        doc="Tag name, unique per company",
    )

    color: Mapped[str | None] = mapped_column(
        String(7),
        nullable=True,
        doc="Optional hex color code (e.g. '#FF5733') for UI display",
    )

    usage_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
        doc="Denormalised count of products using this tag (updated by service)",
    )
