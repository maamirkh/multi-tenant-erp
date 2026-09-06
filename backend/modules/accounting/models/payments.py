"""Payment Processing ORM models — Phase 10.

Phase 10 entities:
  Payment              — a customer receipt or supplier disbursement (unified aggregate root)
  PaymentAllocationLine — links a Payment to the AR/AP transaction(s) it settles
  PaymentRefund        — a refund of a prior Payment's unallocated balance

Design note (supersedes the Phase 6/7 placeholders): ``ARPaymentAllocation``/
``APPaymentAllocation`` (models/ar.py, models/ap.py) were built in Phase 6/7
as provisional per-domain placeholders explicitly deferred to Payment
Processing ("nothing populates this table yet"), before the unified
``Payment`` aggregate (data-model.md §2.8: "covers both AR receipts and AP
disbursements") existed. Now that Payment Processing is being implemented
with one unified aggregate root, ``PaymentAllocationLine`` supersedes them
as a single table with nullable ``ar_transaction_id``/``ap_transaction_id``
(exactly one populated per party_type) — matching tasks.md T205's explicit
field list, which also adds ``gain_loss_amount``/``gain_loss_journal_
entry_id`` that the older placeholder tables lack. The Phase 6/7 tables
remain in the schema, permanently unpopulated, exactly as their own
docstrings already anticipated pending this decision.

``PaymentAllocationLine``/refund "credit" bookkeeping: every Payment gets a
paired AR/APTransaction (transaction_type PAYMENT or ADVANCE, negative
outstanding_amount = a credit) via ``source_document_type="Payment"``/
``source_document_id=payment.id`` — found later via the existing
``find_by_source_document()`` repository method (Phase 6/7) rather than a
new back-reference field on ``Payment``. This reuses the AR/AP subsidiary
ledger's existing OPEN/PARTIALLY_PAID/PAID state machine unmodified: a
credit is simply a transaction with a negative amount, closed out via the
same ``AllocationEngine`` that closes a normal invoice.

Spec ref: specs/008-accounting-finance/spec.md §22 Payments
Data model: specs/008-accounting-finance/data-model.md §2.8 Payment
Tasks ref: specs/008-accounting-finance/tasks.md T204-T206
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
    Uuid,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from core.database.models.tenant_base import TenantBaseModel


class Payment(TenantBaseModel):
    """A customer receipt or supplier disbursement — the unified Payment aggregate root."""

    __tablename__ = "accounting_payments"
    __table_args__ = (
        CheckConstraint(
            "payment_type IN ('CUSTOMER_RECEIPT','SUPPLIER_DISBURSEMENT',"
            "'ADVANCE_RECEIPT','ADVANCE_PAYMENT')",
            name="ck_accounting_payments_type",
        ),
        CheckConstraint(
            "payment_method IN ('CASH','BANK_TRANSFER','CHEQUE','CARD','ONLINE')",
            name="ck_accounting_payments_method",
        ),
        CheckConstraint(
            "party_type IN ('CUSTOMER','SUPPLIER')",
            name="ck_accounting_payments_party_type",
        ),
        CheckConstraint(
            "status IN ('DRAFT','POSTED','ALLOCATED','CANCELLED')",
            name="ck_accounting_payments_status",
        ),
        {"comment": "Customer receipts and supplier disbursements, scoped per company"},
    )

    payment_type: Mapped[str] = mapped_column(String(30), nullable=False)
    payment_method: Mapped[str] = mapped_column(String(20), nullable=False)
    payment_date: Mapped[date] = mapped_column(Date, nullable=False)
    currency_code: Mapped[str] = mapped_column(String(3), nullable=False)
    exchange_rate: Mapped[Decimal] = mapped_column(
        Numeric(20, 10), server_default="1", nullable=False
    )
    amount_foreign: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    amount_base: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    bank_account_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("accounting_bank_accounts.id", ondelete="RESTRICT"),
        nullable=True,
    )
    cash_account_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("accounting_cash_accounts.id", ondelete="RESTRICT"),
        nullable=True,
    )
    advance_account_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("accounting_accounts.id", ondelete="RESTRICT"),
        nullable=True,
        doc="Advance/deposit GL account for ADVANCE_RECEIPT/ADVANCE_PAYMENT "
        "payment types — persisted (Phase 14, tasks.md T274) so a payment "
        "held DRAFT pending approval can reconstruct its journal lines at "
        "approve_payment() time without the caller re-supplying it.",
    )
    party_type: Mapped[str] = mapped_column(String(20), nullable=False)
    party_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        nullable=False,
        index=True,
        doc="No FK — cross-module reference to Sales' customers / Purchase's "
        "suppliers, same convention as CustomerLedger.customer_id.",
    )
    reference: Mapped[str | None] = mapped_column(String(100), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), server_default="POSTED", nullable=False
    )
    journal_entry_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("accounting_journal_entries.id", ondelete="RESTRICT"),
        nullable=True,
    )
    cheque_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("accounting_cheques.id", ondelete="RESTRICT"),
        nullable=True,
    )
    discount_amount: Mapped[Decimal] = mapped_column(
        Numeric(20, 6), server_default="0", nullable=False
    )
    wht_amount: Mapped[Decimal] = mapped_column(
        Numeric(20, 6),
        server_default="0",
        nullable=False,
        doc="Withholding tax deducted from a gross supplier payment "
        "(tasks.md T211) — 0 unless accounting.taxwithholding.enabled.",
    )
    wht_payable_account_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("accounting_accounts.id", ondelete="RESTRICT"),
        nullable=True,
        doc="WHT payable GL account — persisted (Phase 14, tasks.md T274) "
        "for the same reconstruction-at-approval reason as advance_account_id.",
    )


class PaymentAllocationLine(TenantBaseModel):
    """Links a Payment to the specific AR/AP transaction(s) it settles."""

    __tablename__ = "accounting_payment_allocation_lines"
    __table_args__ = (
        CheckConstraint(
            "allocated_amount_foreign > 0",
            name="ck_accounting_payment_allocation_lines_positive",
        ),
        {"comment": "Payment-to-invoice/bill allocation lines, scoped per company"},
    )

    payment_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("accounting_payments.id", ondelete="RESTRICT"),
        nullable=False,
    )
    ar_transaction_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("accounting_ar_transactions.id", ondelete="RESTRICT"),
        nullable=True,
    )
    ap_transaction_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("accounting_ap_transactions.id", ondelete="RESTRICT"),
        nullable=True,
    )
    allocated_amount_foreign: Mapped[Decimal] = mapped_column(
        Numeric(20, 6), nullable=False
    )
    allocated_amount_base: Mapped[Decimal] = mapped_column(
        Numeric(20, 6), nullable=False
    )
    discount_amount: Mapped[Decimal] = mapped_column(
        Numeric(20, 6), server_default="0", nullable=False
    )
    gain_loss_amount: Mapped[Decimal] = mapped_column(
        Numeric(20, 6),
        server_default="0",
        nullable=False,
        doc="Realized FX gain (positive) or loss (negative), base currency.",
    )
    gain_loss_journal_entry_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("accounting_journal_entries.id", ondelete="RESTRICT"),
        nullable=True,
    )
    allocated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


class PaymentRefund(TenantBaseModel):
    """A refund of a prior Payment's unallocated (credit) balance."""

    __tablename__ = "accounting_payment_refunds"
    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_accounting_payment_refunds_positive"),
        {
            "comment": "Refunds of a prior payment's unallocated balance, scoped per company"
        },
    )

    original_payment_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("accounting_payments.id", ondelete="RESTRICT"),
        nullable=False,
    )
    refund_date: Mapped[date] = mapped_column(Date, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    journal_entry_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("accounting_journal_entries.id", ondelete="RESTRICT"),
        nullable=True,
    )
    bank_account_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("accounting_bank_accounts.id", ondelete="RESTRICT"),
        nullable=True,
    )
    cash_account_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("accounting_cash_accounts.id", ondelete="RESTRICT"),
        nullable=True,
    )
