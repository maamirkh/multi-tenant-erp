"""Cash Management ORM models — Phase 9.

Phase 9 entities:
  CashAccount        — a till / petty cash box, linked to a GL account
  CashTransaction    — receipts/payments/transfers/adjustments against a cash account
  PettyCashVoucher   — an individual petty cash disbursement record
  CashReconciliation — a physical-count-vs-GL reconciliation record

Spec ref: specs/008-accounting-finance/spec.md §21 Cash Management
Data model: specs/008-accounting-finance/data-model.md §2.7 CashAccount
Tasks ref: specs/008-accounting-finance/tasks.md T192-T195
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
    false,
    true,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from core.database.models.tenant_base import TenantBaseModel


class CashAccount(TenantBaseModel):
    """A physical cash account (till or petty cash box), linked to one GL account."""

    __tablename__ = "accounting_cash_accounts"
    __table_args__ = (
        UniqueConstraint(
            "company_id",
            "gl_account_id",
            name="uq_accounting_cash_accounts_company_gl_account",
        ),
        {
            "comment": "Cash accounts (tills / petty cash boxes), one GL account each, scoped per company"
        },
    )

    account_name: Mapped[str] = mapped_column(String(200), nullable=False)
    currency_code: Mapped[str] = mapped_column(String(3), nullable=False)
    gl_account_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("accounting_accounts.id", ondelete="RESTRICT"),
        nullable=False,
    )
    current_balance: Mapped[Decimal] = mapped_column(
        Numeric(20, 6),
        server_default="0",
        nullable=False,
        doc="Materialized cache — authoritative value is always the GL account balance query.",
    )
    is_petty_cash: Mapped[bool] = mapped_column(nullable=False, server_default=false())
    float_amount: Mapped[Decimal] = mapped_column(
        Numeric(20, 6),
        server_default="0",
        nullable=False,
        doc="Target petty cash float — the balance replenishment restores this account to.",
    )
    is_active: Mapped[bool] = mapped_column(nullable=False, server_default=true())


class CashTransaction(TenantBaseModel):
    """A single cash movement: receipt, payment, transfer, or adjustment."""

    __tablename__ = "accounting_cash_transactions"
    __table_args__ = (
        CheckConstraint(
            "transaction_type IN ('RECEIPT','PAYMENT','TRANSFER','ADJUSTMENT')",
            name="ck_accounting_cash_transactions_type",
        ),
        {"comment": "Cash account transactions, scoped per company"},
    )

    cash_account_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("accounting_cash_accounts.id", ondelete="RESTRICT"),
        nullable=False,
    )
    transaction_date: Mapped[date] = mapped_column(Date, nullable=False)
    transaction_type: Mapped[str] = mapped_column(String(20), nullable=False)
    amount: Mapped[Decimal] = mapped_column(
        Numeric(20, 6),
        nullable=False,
        doc="Signed: positive increases the cash balance (receipt/transfer-in), "
        "negative decreases it (payment/transfer-out).",
    )
    reference: Mapped[str | None] = mapped_column(String(100), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    journal_entry_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("accounting_journal_entries.id", ondelete="RESTRICT"),
        nullable=True,
    )
    counterparty_type: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
        doc="Informational only (e.g. CUSTOMER/SUPPLIER/EMPLOYEE/OTHER) — no FK, "
        "since Payment Processing's full party linkage is Phase 10.",
    )
    counterparty_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=True,
        doc="No FK — same deferred-linkage reason as counterparty_type.",
    )


class PettyCashVoucher(TenantBaseModel):
    """An individual petty cash disbursement, pending replenishment."""

    __tablename__ = "accounting_petty_cash_vouchers"
    __table_args__ = (
        UniqueConstraint(
            "company_id",
            "cash_account_id",
            "voucher_number",
            name="uq_accounting_petty_cash_vouchers_account_number",
        ),
        {"comment": "Petty cash disbursement vouchers, scoped per company"},
    )

    cash_account_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("accounting_cash_accounts.id", ondelete="RESTRICT"),
        nullable=False,
    )
    voucher_date: Mapped[date] = mapped_column(Date, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    expense_account_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("accounting_accounts.id", ondelete="RESTRICT"),
        nullable=False,
    )
    recipient_name: Mapped[str] = mapped_column(String(200), nullable=False)
    purpose: Mapped[str] = mapped_column(Text, nullable=False)
    approved_by_user_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), nullable=True
    )
    voucher_number: Mapped[str] = mapped_column(String(30), nullable=False)
    journal_entry_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("accounting_journal_entries.id", ondelete="RESTRICT"),
        nullable=True,
        doc="Set when this voucher is folded into a replenishment journal — "
        "NULL means not yet replenished (mirrors Cheque.bank_transaction_id).",
    )


class CashReconciliation(TenantBaseModel):
    """A physical-cash-count-vs-GL-balance reconciliation record."""

    __tablename__ = "accounting_cash_reconciliations"
    __table_args__ = (
        CheckConstraint(
            "status IN ('DRAFT','COMPLETED')",
            name="ck_accounting_cash_reconciliations_status",
        ),
        {
            "comment": "Cash reconciliation records (physical count vs GL), scoped per company"
        },
    )

    cash_account_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("accounting_cash_accounts.id", ondelete="RESTRICT"),
        nullable=False,
    )
    reconciliation_date: Mapped[date] = mapped_column(Date, nullable=False)
    physical_count_amount: Mapped[Decimal] = mapped_column(
        Numeric(20, 6), nullable=False
    )
    gl_balance_amount: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    difference: Mapped[Decimal] = mapped_column(
        Numeric(20, 6), server_default="0", nullable=False
    )
    difference_account_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("accounting_accounts.id", ondelete="RESTRICT"),
        nullable=True,
        doc="Cash Short/Over account — required only when difference != 0.",
    )
    journal_entry_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("accounting_journal_entries.id", ondelete="RESTRICT"),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(
        String(20), server_default="DRAFT", nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
