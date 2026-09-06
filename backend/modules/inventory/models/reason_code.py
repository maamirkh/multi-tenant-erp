"""ReasonCode ORM model — approved reason codes for stock operations.

Reason codes categorise why a stock adjustment, damage record, or return
occurred. They are referenced in Phases 5 and 6 (stock adjustments).

Multi-tenancy: Inherits ``company_id`` from ``TenantBaseModel``.

Spec ref: specs/005-inventory-management/spec.md §15 / §23
Data model: specs/005-inventory-management/data-model.md §2
"""

from __future__ import annotations

from sqlalchemy import Boolean, CheckConstraint, Index, String, UniqueConstraint, true
from sqlalchemy.orm import Mapped, mapped_column

from core.database.models.tenant_base import TenantBaseModel


class ReasonCode(TenantBaseModel):
    """Approved reason code for stock adjustments, damage, and returns.

    Invariants:
    - code unique per company
    - applies_to must be one of ADJUSTMENT / DAMAGE / RETURN
    """

    __tablename__ = "inventory_reason_codes"
    __table_args__ = (
        UniqueConstraint(
            "company_id",
            "code",
            name="uq_inv_reason_codes_company_code",
        ),
        Index("ix_inv_reason_codes_company_id", "company_id"),
        Index("ix_inv_reason_codes_company_applies_to", "company_id", "applies_to"),
        CheckConstraint(
            "applies_to IN ('ADJUSTMENT', 'DAMAGE', 'RETURN')",
            name="ck_inv_reason_codes_applies_to",
        ),
        {"comment": "Approved reason codes for stock operations, scoped per company"},
    )

    code: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        doc="Unique reason code per company (e.g. 'DMGD-001', 'THEFT')",
    )

    label: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        doc="Human-readable label (e.g. 'Damaged in transit')",
    )

    applies_to: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        doc="Operation type: ADJUSTMENT / DAMAGE / RETURN",
    )

    description: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        doc="Optional detailed description",
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=true(),
        doc="False when the reason code is retired (soft-disable, not deleted)",
    )
