"""UOM and UOMConversion ORM models — Unit of Measure master data.

Multi-tenancy: Both models inherit ``company_id`` from ``TenantBaseModel``.

Spec ref: specs/005-inventory-management/spec.md §14
Data model: specs/005-inventory-management/data-model.md §1.4 / §2
"""

from __future__ import annotations

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from core.database.models.tenant_base import TenantBaseModel


class UOM(TenantBaseModel):
    """Unit of Measure definition.

    ``uom_type`` categorises what the unit measures:
      UNIT, WEIGHT, VOLUME, LENGTH, AREA

    Invariants:
    - ``code`` unique per company
    - ``uom_type`` must be one of the defined enum values
    - Cannot be deleted if any product references it as base_uom (enforced in service)
    """

    __tablename__ = "inventory_uoms"
    __table_args__ = (
        UniqueConstraint(
            "company_id",
            "code",
            name="uq_inv_uoms_company_code",
        ),
        Index("ix_inv_uoms_company_id", "company_id"),
        Index("ix_inv_uoms_company_status", "company_id", "status"),
        CheckConstraint(
            "uom_type IN ('UNIT', 'WEIGHT', 'VOLUME', 'LENGTH', 'AREA')",
            name="ck_inv_uoms_type",
        ),
        CheckConstraint(
            "status IN ('active', 'inactive')",
            name="ck_inv_uoms_status",
        ),
        {"comment": "Unit of Measure definitions, scoped per company"},
    )

    code: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        doc="Unique UOM code per company (e.g. 'KG', 'PCS', 'LTR')",
    )

    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        doc="Human-readable UOM name (e.g. 'Kilogram', 'Pieces')",
    )

    uom_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        doc="Measurement category: UNIT / WEIGHT / VOLUME / LENGTH / AREA",
    )

    symbol: Mapped[str | None] = mapped_column(
        String(10),
        nullable=True,
        doc="Optional display symbol (e.g. 'kg', 'pcs')",
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default="active",
        doc="'active' or 'inactive'",
    )


class UOMConversion(TenantBaseModel):
    """Conversion factor between two UOM within the same company.

    Invariant:
    - ``conversion_factor`` must be > 0
    - source_uom_id ≠ target_uom_id (enforced in service)
    - Unique per (company_id, source_uom_id, target_uom_id) pair
    """

    __tablename__ = "inventory_uom_conversions"
    __table_args__ = (
        UniqueConstraint(
            "company_id",
            "source_uom_id",
            "target_uom_id",
            name="uq_inv_uom_conv_company_pair",
        ),
        Index("ix_inv_uom_conversions_company_id", "company_id"),
        Index("ix_inv_uom_conversions_source", "company_id", "source_uom_id"),
        CheckConstraint(
            "conversion_factor > 0",
            name="ck_inv_uom_conv_factor_positive",
        ),
        {"comment": "Unit of Measure conversion factors, scoped per company"},
    )

    source_uom_id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        ForeignKey("inventory_uoms.id", ondelete="RESTRICT"),
        nullable=False,
        doc="FK to source UOM",
    )

    target_uom_id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        ForeignKey("inventory_uoms.id", ondelete="RESTRICT"),
        nullable=False,
        doc="FK to target UOM",
    )

    conversion_factor: Mapped[float] = mapped_column(
        Numeric(18, 6),
        nullable=False,
        doc="Multiply source qty by this factor to get target qty. Must be > 0.",
    )

    notes: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        doc="Optional notes about this conversion",
    )
