"""InstallmentAllocationReference ORM model — append-only.

Explains which Accounting payment/allocation satisfied which schedule
line (spec.md §13.2, BR-INST-007). Plain ``Base`` (not
``TenantBaseModel``) with an explicit ``company_id`` column, matching
migration 066's exact field list — no soft-delete, no ``updated_at``, no
``update()`` method anywhere on its repository (T119): a reversal always
inserts a **new** row, never mutates an existing one (BR-INST-017,
FR-INST-242).

No FK on ``accounting_payment_id``/``accounting_payment_allocation_line_id``
— cross-module references follow the established ``source_document_id``
convention (plan.md §7.2); Installments never imports
``modules.accounting.models``.

Spec ref: specs/010-installments/data-model.md
"InstallmentAllocationReference"; specs/010-installments/plan.md §7.2.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from core.database.base import Base


class InstallmentAllocationReference(Base):
    """Append-only explanation of which Accounting payment/allocation
    satisfied which schedule line — never updated or deleted."""

    __tablename__ = "installment_allocation_references"
    __table_args__ = (
        {
            "comment": (
                "Append-only explanation of which Accounting payment/"
                "allocation satisfied which schedule line — never updated "
                "or deleted"
            )
        },
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    company_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    contract_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey(
            "installment_contracts.id",
            name="fk_installment_allocation_references_contract_id",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    schedule_line_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey(
            "installment_schedule_lines.id",
            name="fk_installment_allocation_references_schedule_line_id",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    accounting_payment_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), nullable=False
    )
    accounting_payment_allocation_line_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), nullable=False
    )
    allocated_amount: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    allocation_order: Mapped[int] = mapped_column(Integer, nullable=False)
    is_reversal: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
    reverses_allocation_reference_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey(
            "installment_allocation_references.id",
            name="fk_installment_allocation_references_reverses_id",
            ondelete="RESTRICT",
        ),
        nullable=True,
    )
    allocated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
