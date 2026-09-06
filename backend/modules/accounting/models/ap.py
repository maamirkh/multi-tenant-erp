"""Accounts Payable ORM models — Phase 7.

Phase 7 entities:
  SupplierLedger                      — subsidiary ledger root, one per supplier per company
  APTransaction                       — bill/credit-note/debit-note/adjustment records
  APPaymentAllocation                 — links a payment to the bill(s) it settles
  SupplierStatementReconciliation     — a reconciliation session against a supplier statement
  SupplierStatementReconciliationItem — one matched/unmatched line within a session

Mirrors ``models/ar.py``'s design exactly (data-model.md §2.5: "Key
Attributes: Mirror of CustomerLedger / ARTransaction with supplier
context") — same materialized-cache-not-running-balance pattern
(research.md Decision 3), same deferred ``payment_id`` FK convention
(Phase 9 populates ``APPaymentAllocation``).

``SupplierLedger.supplier_id`` has NO FK — cross-module reference to
Purchase (Epic 6), same convention as ``CustomerLedger.customer_id``'s
reference to Sales.

Spec ref: specs/008-accounting-finance/spec.md §19 Accounts Payable
Data model: specs/008-accounting-finance/data-model.md §2.5 SupplierLedger
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


class SupplierLedger(TenantBaseModel):
    """Subsidiary ledger root — one per (company_id, supplier_id).

    ``supplier_id`` references Epic 6's ``suppliers`` table — no FK
    constraint (cross-module reference, same convention as ``CustomerLedger.
    customer_id``).
    """

    __tablename__ = "accounting_supplier_ledgers"
    __table_args__ = (
        UniqueConstraint(
            "company_id",
            "supplier_id",
            name="uq_accounting_supplier_ledgers_company_supplier",
        ),
        {"comment": "AP subsidiary ledger root, one per supplier per company"},
    )

    supplier_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), nullable=False, index=True
    )
    total_outstanding_base: Mapped[Decimal] = mapped_column(
        Numeric(20, 6),
        server_default="0",
        nullable=False,
        doc="Materialized cache — authoritative value is always SUM(ap_transactions.outstanding_amount).",
    )
    last_payment_date: Mapped[date | None] = mapped_column(Date, nullable=True)


class APTransaction(TenantBaseModel):
    """A single AP event: bill, credit note, debit note, or adjustment.

    ``outstanding_amount`` is denormalized for aging-query performance —
    updated by ``AccountsPayableService`` whenever an allocation is
    recorded (Phase 9) or an adjustment is posted (this phase).
    """

    __tablename__ = "accounting_ap_transactions"
    __table_args__ = (
        CheckConstraint(
            "transaction_type IN ('BILL','CREDIT_NOTE','DEBIT_NOTE','PAYMENT',"
            "'ADVANCE','ADJUSTMENT')",
            name="ck_accounting_ap_transactions_type",
        ),
        CheckConstraint(
            "status IN ('OPEN','PARTIALLY_PAID','PAID','OVERDUE','DISPUTED')",
            name="ck_accounting_ap_transactions_status",
        ),
        {"comment": "AP subsidiary ledger transactions, scoped per company"},
    )

    supplier_ledger_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("accounting_supplier_ledgers.id", ondelete="RESTRICT"),
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
    bill_number: Mapped[str | None] = mapped_column(String(50), nullable=True)


class APPaymentAllocation(TenantBaseModel):
    """Links a payment to the AP transaction(s) it settles.

    ``payment_id`` has no FK — Payment Processing ships in Phase 9; this
    table exists now per T158 but nothing populates it until then, mirroring
    ``ARPaymentAllocation``'s identical deferral.
    """

    __tablename__ = "accounting_ap_allocations"
    __table_args__ = (
        CheckConstraint(
            "allocated_amount_foreign > 0", name="ck_accounting_ap_allocations_positive"
        ),
        {
            "comment": "AP payment allocations, scoped per company (Phase 9 populates this)"
        },
    )

    ap_transaction_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("accounting_ap_transactions.id", ondelete="RESTRICT"),
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


class SupplierStatementReconciliation(TenantBaseModel):
    """A reconciliation session matching a supplier's statement against the
    AP ledger (research.md Decision 6's statement-first pattern, applied to
    AP — the same pattern Phase 8's BankReconciliation uses for bank
    statements).
    """

    __tablename__ = "accounting_supplier_reconciliations"
    __table_args__ = (
        CheckConstraint(
            "status IN ('DRAFT','IN_PROGRESS','COMPLETED')",
            name="ck_accounting_supplier_reconciliations_status",
        ),
        {"comment": "Supplier statement reconciliation sessions, scoped per company"},
    )

    supplier_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), nullable=False, index=True
    )
    statement_date: Mapped[date] = mapped_column(Date, nullable=False)
    statement_total: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), server_default="DRAFT", nullable=False
    )


class SupplierStatementReconciliationItem(TenantBaseModel):
    """One line within a reconciliation session: a supplier statement line
    matched (or not) against an ``APTransaction``.
    """

    __tablename__ = "accounting_supplier_reconciliation_items"
    __table_args__ = (
        CheckConstraint(
            "match_status IN ('MATCHED','UNMATCHED_GL','UNMATCHED_STATEMENT','DISPUTED')",
            name="ck_accounting_supplier_reconciliation_items_match_status",
        ),
        {
            "comment": "Individual matched/unmatched lines within a supplier reconciliation session"
        },
    )

    reconciliation_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("accounting_supplier_reconciliations.id", ondelete="CASCADE"),
        nullable=False,
    )
    ap_transaction_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("accounting_ap_transactions.id", ondelete="RESTRICT"),
        nullable=True,
    )
    statement_line_reference: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )
    statement_amount: Mapped[Decimal | None] = mapped_column(
        Numeric(20, 6), nullable=True
    )
    gl_amount: Mapped[Decimal | None] = mapped_column(Numeric(20, 6), nullable=True)
    match_status: Mapped[str] = mapped_column(
        String(20), server_default="UNMATCHED_STATEMENT", nullable=False
    )
    difference: Mapped[Decimal] = mapped_column(
        Numeric(20, 6), server_default="0", nullable=False
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
