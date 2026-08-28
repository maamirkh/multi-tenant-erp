"""InstallmentLateCharge ORM model.

One occurrence of a policy-driven late charge (spec.md §14.2,
data-model.md "InstallmentLateCharge"). Unlike ``InstallmentAllocationReference``
(append-only), waiver is a controlled, distinct-permission mutation of an
otherwise stable row — hence ``TenantBaseModel`` (soft-delete/audit
columns), not the plain ``Base`` idiom.

``accounting_journal_entry_id``/``accounting_ar_transaction_id`` are set
together, or neither is (atomic, plan.md §12.1/§12.2) — no FK on either,
matching the established ``source_document_id`` cross-module reference
convention (plan.md §7.2). Field shapes mirror migration 066 exactly.

Spec ref: specs/010-installments/data-model.md "InstallmentLateCharge";
specs/010-installments/plan.md §12.1, §12.2.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from core.database.models.tenant_base import TenantBaseModel


class InstallmentLateCharge(TenantBaseModel):
    """One occurrence of a policy-driven late charge — never charged
    twice for the same ``(schedule_line_id, overdue_occurrence_date)``."""

    __tablename__ = "installment_late_charges"
    __table_args__ = (
        UniqueConstraint(
            "schedule_line_id",
            "overdue_occurrence_date",
            name="uq_installment_late_charges_line_occurrence",
        ),
        {
            "comment": (
                "One occurrence of a policy-driven late charge — never "
                "charged twice for the same (schedule_line_id, "
                "overdue_occurrence_date)"
            )
        },
    )

    contract_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey(
            "installment_contracts.id",
            name="fk_installment_late_charges_contract_id",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    schedule_line_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey(
            "installment_schedule_lines.id",
            name="fk_installment_late_charges_schedule_line_id",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    charge_amount: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    charged_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    overdue_occurrence_date: Mapped[date] = mapped_column(Date, nullable=False)
    accounting_journal_entry_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), nullable=True
    )
    accounting_ar_transaction_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), nullable=True
    )
    waived_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    waived_by: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    waived_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
