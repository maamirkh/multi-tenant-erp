"""InstallmentContract ORM model — the Installments aggregate root.

Spec ref: specs/010-installments/data-model.md "InstallmentContract"
(ADR-INST-02); specs/010-installments/plan.md §7.1/§7.2/§9.

**Partial unique index, not a plain UNIQUE** (BR-INST-042/ADR-INST-03):
at most one *non-terminal* contract may exist per originating obligation
— ``CANCELLED``/``COMPLETED``/``WRITTEN_OFF`` contracts must NOT block a
new contract against the same invoice. Mirrors the platform's own
``uq_subscriptions_company_active`` precedent.

``active_schedule_version_id`` intentionally has no ORM-level
``ForeignKey()``/``relationship()`` — the real DB constraint already
exists (migration 065, added there once ``installment_schedule_versions``
exists) but no Python ORM class for that table is created until Phase 4;
this column is a plain UUID here, matching the "no future-phase model
pre-creation" discipline.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from core.database.models.tenant_base import TenantBaseModel

_ONE_NONTERMINAL_PER_OBLIGATION_WHERE = text(
    "status NOT IN ('CANCELLED', 'COMPLETED', 'WRITTEN_OFF')"
)


class InstallmentContract(TenantBaseModel):
    """The Installments aggregate root — an installment sale agreement."""

    __tablename__ = "installment_contracts"
    __table_args__ = (
        UniqueConstraint(
            "company_id",
            "contract_number",
            name="uq_installment_contracts_company_number",
        ),
        Index(
            "uq_installment_contracts_one_nonterminal_per_obligation",
            "company_id",
            "sales_invoice_id",
            unique=True,
            postgresql_where=_ONE_NONTERMINAL_PER_OBLIGATION_WHERE,
            sqlite_where=_ONE_NONTERMINAL_PER_OBLIGATION_WHERE,
        ),
        CheckConstraint(
            "status IN ('DRAFT', 'PENDING_APPROVAL', 'APPROVED', 'ACTIVE', "
            "'DEFAULTED', 'COMPLETED', 'CANCELLED', 'WRITTEN_OFF')",
            name="ck_installment_contracts_status",
        ),
        CheckConstraint(
            "principal_amount >= 0 AND contractual_total >= 0 "
            "AND installment_count > 0",
            name="ck_installment_contracts_positive_amounts",
        ),
        {"comment": "Installments aggregate root — an installment sale agreement"},
    )

    contract_number: Mapped[str] = mapped_column(String(30), nullable=False)
    branch_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    customer_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    sales_invoice_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), nullable=False
    )
    plan_template_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey(
            "installment_plan_templates.id",
            name="fk_installment_contracts_plan_template_id",
            ondelete="RESTRICT",
        ),
        nullable=True,
    )
    contract_date: Mapped[date] = mapped_column(Date, nullable=False)
    principal_amount: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    down_payment_amount: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    markup_amount: Mapped[Decimal] = mapped_column(
        Numeric(20, 6), nullable=False, server_default="0"
    )
    contractual_total: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    installment_count: Mapped[int] = mapped_column(Integer, nullable=False)
    frequency: Mapped[str] = mapped_column(String(20), nullable=False)
    first_due_date: Mapped[date] = mapped_column(Date, nullable=False)
    maturity_date: Mapped[date] = mapped_column(Date, nullable=False)
    currency_code: Mapped[str] = mapped_column(String(3), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="DRAFT"
    )
    terms_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    active_schedule_version_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), nullable=True
    )
    submitted_by: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), nullable=True
    )
    submitted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    approved_by: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), nullable=True
    )
    approved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    activated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    closed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    defaulted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    cancelled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    written_off_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    requires_review: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="false",
        doc=(
            "Non-terminal flag (plan.md §13): set true when the "
            "originating Sales invoice is corrected post-activation "
            "(credit note issued / invoice cancelled). Never auto-"
            "cancels or auto-adjusts the contract — an authorized human "
            "action resolves it (Scenario H, FR-INST-241)."
        ),
    )
