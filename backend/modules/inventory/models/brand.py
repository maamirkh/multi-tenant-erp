"""Brand ORM model — product brand master data.

Multi-tenancy: Inherits ``company_id`` from ``TenantBaseModel``.

Spec ref: specs/005-inventory-management/spec.md §14
Data model: specs/005-inventory-management/data-model.md §1.3 / §2
"""

from __future__ import annotations

from sqlalchemy import CheckConstraint, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from core.database.models.tenant_base import TenantBaseModel


class Brand(TenantBaseModel):
    """Product brand within a company.

    Invariants:
    - ``code`` unique per company
    - ``status`` must be 'active' or 'inactive'
    - Deactivation blocked when assigned to Active products (enforced in service)
    """

    __tablename__ = "inventory_brands"
    __table_args__ = (
        UniqueConstraint(
            "company_id",
            "code",
            name="uq_inv_brands_company_code",
        ),
        Index("ix_inv_brands_company_id", "company_id"),
        Index("ix_inv_brands_company_status", "company_id", "status"),
        CheckConstraint(
            "status IN ('active', 'inactive')",
            name="ck_inv_brands_status",
        ),
        {"comment": "Product brand master data, scoped per company"},
    )

    code: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        doc="Unique brand code per company (e.g. 'SAMSUNG')",
    )

    name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        doc="Human-readable brand name",
    )

    country_of_origin: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        doc="Country where the brand originates (optional)",
    )

    logo_url: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        doc="S3 URL of the brand logo (optional)",
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default="active",
        doc="'active' or 'inactive'",
    )

    website: Mapped[str | None] = mapped_column(
        String(300),
        nullable=True,
        doc="Optional brand website URL",
    )
