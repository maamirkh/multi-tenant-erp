"""Banking ORM models — Phase 8.

Phase 8 entities:
  BankAccount             — one per company bank account, linked to a GL account
  BankTransaction         — receipts/payments/transfers/bank charges against a bank account
  BankStatementLine       — imported (or manually entered) bank statement line
  BankReconciliation      — a reconciliation session (statement-first — research.md Decision 6)
  BankReconciliationMatch — pairs a BankTransaction with a BankStatementLine
  Cheque                  — issued-cheque lifecycle tracking

Research ref: research.md Decision 6 — statement-first reconciliation.
BankStatementLine rows are stored independently of BankTransaction rows;
the reconciliation engine matches them (recorded in
BankReconciliationMatch), leaving unmatched items visible on both sides
for manual follow-up (the same design AP's SupplierStatementReconciliation
already applies).

Spec ref: specs/008-accounting-finance/spec.md §20 Banking
Data model: specs/008-accounting-finance/data-model.md §2.6 BankAccount
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
    false,
    true,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from core.database.models.tenant_base import TenantBaseModel


class BankAccount(TenantBaseModel):
    """A company bank account, linked to exactly one GL account of type Asset/Bank."""

    __tablename__ = "accounting_bank_accounts"
    __table_args__ = (
        UniqueConstraint(
            "company_id",
            "gl_account_id",
            name="uq_accounting_bank_accounts_company_gl_account",
        ),
        {"comment": "Company bank accounts, one GL account each, scoped per company"},
    )

    bank_name: Mapped[str] = mapped_column(String(200), nullable=False)
    branch_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    account_number: Mapped[str] = mapped_column(String(50), nullable=False)
    iban: Mapped[str | None] = mapped_column(String(50), nullable=True)
    swift_bic: Mapped[str | None] = mapped_column(String(20), nullable=True)
    currency_code: Mapped[str] = mapped_column(String(3), nullable=False)
    gl_account_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("accounting_accounts.id", ondelete="RESTRICT"),
        nullable=False,
    )
    opening_balance: Mapped[Decimal] = mapped_column(
        Numeric(20, 6), server_default="0", nullable=False
    )
    opening_balance_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    current_gl_balance: Mapped[Decimal] = mapped_column(
        Numeric(20, 6),
        server_default="0",
        nullable=False,
        doc="Materialized cache — authoritative value is always the GL account balance query.",
    )
    is_active: Mapped[bool] = mapped_column(nullable=False, server_default=true())


class BankTransaction(TenantBaseModel):
    """A single bank movement: receipt, payment, transfer leg, or bank charge."""

    __tablename__ = "accounting_bank_transactions"
    __table_args__ = (
        CheckConstraint(
            "transaction_type IN ('RECEIPT','PAYMENT','TRANSFER','BANK_CHARGE')",
            name="ck_accounting_bank_transactions_type",
        ),
        {"comment": "Bank account transactions, scoped per company"},
    )

    bank_account_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("accounting_bank_accounts.id", ondelete="RESTRICT"),
        nullable=False,
    )
    transaction_date: Mapped[date] = mapped_column(Date, nullable=False)
    transaction_type: Mapped[str] = mapped_column(String(20), nullable=False)
    amount: Mapped[Decimal] = mapped_column(
        Numeric(20, 6),
        nullable=False,
        doc="Signed: positive increases the bank balance (receipt/transfer-in), "
        "negative decreases it (payment/transfer-out/bank charge).",
    )
    reference: Mapped[str | None] = mapped_column(String(100), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    journal_entry_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("accounting_journal_entries.id", ondelete="RESTRICT"),
        nullable=True,
    )
    is_reconciled: Mapped[bool] = mapped_column(nullable=False, server_default=false())
    reconciliation_match_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        nullable=True,
        doc="No FK — BankReconciliationMatch itself references this table, so "
        "adding the reverse FK would create a circular table-creation "
        "dependency; the join table is the source of truth for pairing.",
    )


class BankStatementLine(TenantBaseModel):
    """One line from an imported (or manually entered) bank statement."""

    __tablename__ = "accounting_bank_statement_lines"
    __table_args__ = (
        {
            "comment": "Imported bank statement lines, scoped per company (research.md Decision 6)"
        },
    )

    bank_account_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("accounting_bank_accounts.id", ondelete="RESTRICT"),
        nullable=False,
    )
    statement_date: Mapped[date] = mapped_column(Date, nullable=False)
    value_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    reference: Mapped[str | None] = mapped_column(String(100), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    transaction_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
    is_matched: Mapped[bool] = mapped_column(nullable=False, server_default=false())
    reconciliation_match_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        nullable=True,
        doc="No FK — same circular-dependency reason as BankTransaction's "
        "identically-named column.",
    )


class BankReconciliation(TenantBaseModel):
    """A reconciliation session for one bank account against one statement date."""

    __tablename__ = "accounting_bank_reconciliations"
    __table_args__ = (
        CheckConstraint(
            "status IN ('DRAFT','IN_PROGRESS','COMPLETED','LOCKED')",
            name="ck_accounting_bank_reconciliations_status",
        ),
        {"comment": "Bank reconciliation sessions, scoped per company"},
    )

    bank_account_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("accounting_bank_accounts.id", ondelete="RESTRICT"),
        nullable=False,
    )
    statement_date: Mapped[date] = mapped_column(Date, nullable=False)
    statement_closing_balance: Mapped[Decimal] = mapped_column(
        Numeric(20, 6), nullable=False
    )
    gl_balance_at_date: Mapped[Decimal | None] = mapped_column(
        Numeric(20, 6), nullable=True
    )
    difference: Mapped[Decimal] = mapped_column(
        Numeric(20, 6), server_default="0", nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(20), server_default="DRAFT", nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_by_user_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), nullable=True
    )


class BankReconciliationMatch(TenantBaseModel):
    """Pairs one ``BankTransaction`` with one ``BankStatementLine`` within a
    reconciliation session.
    """

    __tablename__ = "accounting_bank_reconciliation_matches"
    __table_args__ = (
        CheckConstraint(
            "match_type IN ('AUTO','MANUAL')",
            name="ck_accounting_bank_reconciliation_matches_type",
        ),
        {
            "comment": "GL-transaction-to-statement-line pairs within a reconciliation session"
        },
    )

    reconciliation_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("accounting_bank_reconciliations.id", ondelete="CASCADE"),
        nullable=False,
    )
    bank_transaction_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("accounting_bank_transactions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    statement_line_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("accounting_bank_statement_lines.id", ondelete="RESTRICT"),
        nullable=False,
    )
    match_type: Mapped[str] = mapped_column(String(10), nullable=False)
    matched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    matched_by_user_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), nullable=True
    )


class Cheque(TenantBaseModel):
    """An issued cheque and its clearing lifecycle."""

    __tablename__ = "accounting_cheques"
    __table_args__ = (
        UniqueConstraint(
            "company_id",
            "bank_account_id",
            "cheque_number",
            name="uq_accounting_cheques_account_number",
        ),
        CheckConstraint(
            "status IN ('ISSUED','PRESENTED','CLEARED','CANCELLED','STALE')",
            name="ck_accounting_cheques_status",
        ),
        {"comment": "Issued cheque register, scoped per company"},
    )

    bank_account_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("accounting_bank_accounts.id", ondelete="RESTRICT"),
        nullable=False,
    )
    cheque_number: Mapped[str] = mapped_column(String(30), nullable=False)
    payee_name: Mapped[str] = mapped_column(String(200), nullable=False)
    cheque_date: Mapped[date] = mapped_column(Date, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), server_default="ISSUED", nullable=False
    )
    bank_transaction_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("accounting_bank_transactions.id", ondelete="RESTRICT"),
        nullable=True,
    )
    bank_statement_line_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("accounting_bank_statement_lines.id", ondelete="SET NULL"),
        nullable=True,
    )
    cancelled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    cancel_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
