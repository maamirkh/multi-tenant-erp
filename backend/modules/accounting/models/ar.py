"""Accounts Receivable ORM models — Phase 6.

Phase 6 entities:
  CustomerLedger          — subsidiary ledger root, one per customer per company
  ARTransaction           — invoice/credit-note/adjustment/write-off records
  ARPaymentAllocation     — links a payment to the invoice(s) it settles
  CustomerCreditHistory   — audit trail of credit limit/status changes

Research ref: research.md Decision 3 — AR does NOT maintain a running
balance column computed by incrementing/decrementing on every write;
``CustomerLedger.total_outstanding_base`` is a materialized cache updated
by ``AccountsReceivableService`` on each posting, but the authoritative
value is always ``SUM(ar_transactions.outstanding_amount)`` — matches the
"allocation table, not running balance" pattern research.md prescribes.

``ARPaymentAllocation.payment_id`` has NO FK constraint — Payment
Processing is Phase 9; this table exists now (T134) but nothing populates
it until then, consistent with the deferred-FK convention used throughout
this codebase (e.g. Phase 1's Account FK deferred until Phase 2 existed).

Spec ref: specs/008-accounting-finance/spec.md §18 Accounts Receivable
Data model: specs/008-accounting-finance/data-model.md §2.4 CustomerLedger
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from core.database.models.tenant_base import TenantBaseModel


class CustomerLedger(TenantBaseModel):
    """Subsidiary ledger root — one per (company_id, customer_id).

    ``customer_id`` references Epic 7's ``customers`` table — no FK
    constraint (cross-module reference, same convention as ``company_id``
    itself before the Company Management Epic added its FK).
    """

    __tablename__ = "accounting_customer_ledgers"
    __table_args__ = (
        UniqueConstraint(
            "company_id",
            "customer_id",
            name="uq_accounting_customer_ledgers_company_customer",
        ),
        CheckConstraint(
            "credit_status IN ('GOOD', 'WARNING', 'EXCEEDED', 'HOLD')",
            name="ck_accounting_customer_ledgers_credit_status",
        ),
        CheckConstraint(
            "credit_limit >= 0", name="ck_accounting_customer_ledgers_credit_limit"
        ),
        {"comment": "AR subsidiary ledger root, one per customer per company"},
    )

    customer_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), nullable=False, index=True
    )
    credit_limit: Mapped[Decimal] = mapped_column(
        Numeric(20, 6), server_default="0", nullable=False
    )
    credit_status: Mapped[str] = mapped_column(
        String(20), server_default="GOOD", nullable=False
    )
    credit_hold_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    credit_hold_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    credit_hold_by: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), nullable=True
    )
    total_outstanding_base: Mapped[Decimal] = mapped_column(
        Numeric(20, 6),
        server_default="0",
        nullable=False,
        doc="Materialized cache — authoritative value is always SUM(ar_transactions.outstanding_amount).",
    )
    last_payment_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    average_payment_days: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 2), nullable=True
    )


class ARTransaction(TenantBaseModel):
    """A single AR event: invoice, credit note, debit note, adjustment, or write-off.

    ``outstanding_amount`` is denormalized for aging-query performance —
    updated by ``AccountsReceivableService`` whenever an allocation is
    recorded (Phase 9) or an adjustment/write-off is posted (this phase).
    """

    __tablename__ = "accounting_ar_transactions"
    __table_args__ = (
        CheckConstraint(
            "transaction_type IN ('INVOICE','CREDIT_NOTE','DEBIT_NOTE','PAYMENT',"
            "'ADVANCE','ADJUSTMENT','WRITE_OFF')",
            name="ck_accounting_ar_transactions_type",
        ),
        CheckConstraint(
            "status IN ('OPEN','PARTIALLY_PAID','PAID','OVERDUE','DISPUTED','WRITTEN_OFF')",
            name="ck_accounting_ar_transactions_status",
        ),
        {"comment": "AR subsidiary ledger transactions, scoped per company"},
    )

    customer_ledger_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("accounting_customer_ledgers.id", ondelete="RESTRICT"),
        nullable=False,
    )
    transaction_type: Mapped[str] = mapped_column(String(20), nullable=False)
    transaction_date: Mapped[date] = mapped_column(Date, nullable=False)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    currency_code: Mapped[str] = mapped_column(String(3), nullable=False)
    exchange_rate: Mapped[Decimal] = mapped_column(
        Numeric(20, 10), server_default="1", nullable=False
    )
    amount_foreign: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    amount_base: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    outstanding_amount: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), server_default="OPEN", nullable=False
    )
    source_document_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    source_document_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), nullable=True
    )
    journal_entry_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("accounting_journal_entries.id", ondelete="RESTRICT"),
        nullable=True,
    )
    invoice_number: Mapped[str | None] = mapped_column(String(50), nullable=True)


class ARPaymentAllocation(TenantBaseModel):
    """Links a payment to the AR transaction(s) it settles.

    ``payment_id`` has no FK — Payment Processing ships in Phase 9; this
    table exists now per T134 but nothing populates it until then.
    """

    __tablename__ = "accounting_ar_allocations"
    __table_args__ = (
        CheckConstraint(
            "allocated_amount_foreign > 0", name="ck_accounting_ar_allocations_positive"
        ),
        {
            "comment": "AR payment allocations, scoped per company (Phase 9 populates this)"
        },
    )

    ar_transaction_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("accounting_ar_transactions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    payment_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), nullable=False, index=True
    )
    allocated_amount_foreign: Mapped[Decimal] = mapped_column(
        Numeric(20, 6), nullable=False
    )
    allocated_amount_base: Mapped[Decimal] = mapped_column(
        Numeric(20, 6), nullable=False
    )
    allocated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    discount_amount: Mapped[Decimal] = mapped_column(
        Numeric(20, 6), server_default="0", nullable=False
    )


class CustomerCreditHistory(TenantBaseModel):
    """Audit trail of credit limit/status changes for a customer ledger."""

    __tablename__ = "accounting_customer_credit_history"
    __table_args__ = (
        CheckConstraint(
            "event_type IN ('LIMIT_CHANGED','HOLD_PLACED','HOLD_RELEASED','STATUS_CHANGED')",
            name="ck_accounting_credit_history_event_type",
        ),
        {"comment": "Customer credit limit/status change history, scoped per company"},
    )

    customer_ledger_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("accounting_customer_ledgers.id", ondelete="RESTRICT"),
        nullable=False,
    )
    event_type: Mapped[str] = mapped_column(String(30), nullable=False)
    old_value: Mapped[str | None] = mapped_column(String(100), nullable=True)
    new_value: Mapped[str | None] = mapped_column(String(100), nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    actor_user_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), nullable=True
    )
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
