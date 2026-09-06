"""Fiscal Calendar ORM models — Phase 3.

Phase 3 entities:
  FiscalYear      — the company's accounting year (SETUP/OPEN/CLOSED)
  FiscalPeriod    — a subdivision (1-13) of a fiscal year (OPEN/LOCKED/CLOSED)
  OpeningBalance  — starting balance per account for a fiscal year setup

Spec ref: specs/008-accounting-finance/spec.md §16 Fiscal Calendar
Data model: specs/008-accounting-finance/data-model.md §2.2 FiscalCalendar
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    false,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from core.database.models.tenant_base import TenantBaseModel


class FiscalYear(TenantBaseModel):
    """The company's accounting year — the aggregate root for the fiscal calendar.

    Invariants (data-model.md §2.2, enforced by ``FiscalCalendarService``):
      - ``fiscal_year_name`` unique per company
      - Year-end close cannot proceed until all periods are LOCKED
      - Only one active fiscal year setup process at a time
    """

    __tablename__ = "accounting_fiscal_years"
    __table_args__ = (
        UniqueConstraint(
            "company_id",
            "fiscal_year_name",
            name="uq_accounting_fiscal_years_company_name",
        ),
        CheckConstraint(
            "status IN ('SETUP', 'OPEN', 'CLOSED')",
            name="ck_accounting_fiscal_years_status",
        ),
        CheckConstraint(
            "end_date > start_date", name="ck_accounting_fiscal_years_date_range"
        ),
        {"comment": "Fiscal year definitions, scoped per company"},
    )

    fiscal_year_name: Mapped[str] = mapped_column(String(50), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), server_default="SETUP", nullable=False
    )
    base_currency_code: Mapped[str] = mapped_column(String(3), nullable=False)
    is_current: Mapped[bool] = mapped_column(
        Boolean, server_default=false(), nullable=False
    )


class FiscalPeriod(TenantBaseModel):
    """A subdivision (typically monthly) of a ``FiscalYear``.

    Invariants (data-model.md §2.2, enforced by ``FiscalPeriodStateMachine``):
      - Periods within a year are non-overlapping and contiguous
      - OPEN -> LOCKED -> CLOSED only; no reversal of CLOSED
      - LOCKED can revert to OPEN (Controller authority + audit record)
      - CLOSED is only reachable via the year-end close workflow, never a
        direct "close this period" action (see ``fiscal_service.py``)
    """

    __tablename__ = "accounting_fiscal_periods"
    __table_args__ = (
        UniqueConstraint(
            "fiscal_year_id",
            "period_number",
            name="uq_accounting_fiscal_periods_year_number",
        ),
        CheckConstraint(
            "period_number >= 1 AND period_number <= 13",
            name="ck_accounting_fiscal_periods_number",
        ),
        CheckConstraint(
            "status IN ('OPEN', 'LOCKED', 'CLOSED')",
            name="ck_accounting_fiscal_periods_status",
        ),
        CheckConstraint(
            "end_date > start_date", name="ck_accounting_fiscal_periods_date_range"
        ),
        {"comment": "Accounting periods within a fiscal year, scoped per company"},
    )

    fiscal_year_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("accounting_fiscal_years.id", ondelete="RESTRICT"),
        nullable=False,
    )
    period_number: Mapped[int] = mapped_column(Integer, nullable=False)
    period_name: Mapped[str] = mapped_column(String(50), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), server_default="OPEN", nullable=False
    )
    locked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    locked_by_user_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), nullable=True
    )
    lock_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    closed_by_user_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), nullable=True
    )


class OpeningBalance(TenantBaseModel):
    """Starting balance for one account as part of a fiscal year setup.

    One row per (fiscal_year_id, account_id) — spec.md §16.3: opening
    balances must sum debit == credit before commit (validated by
    ``FiscalCalendarService.setup_opening_balances``).
    """

    __tablename__ = "accounting_opening_balances"
    __table_args__ = (
        UniqueConstraint(
            "fiscal_year_id",
            "account_id",
            name="uq_accounting_opening_balances_year_account",
        ),
        CheckConstraint(
            "debit_amount >= 0 AND credit_amount >= 0",
            name="ck_accounting_opening_balances_non_negative",
        ),
        CheckConstraint(
            "debit_amount = 0 OR credit_amount = 0",
            name="ck_accounting_opening_balances_one_sided",
        ),
        {
            "comment": "Opening balances per account for a fiscal year, scoped per company"
        },
    )

    fiscal_year_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("accounting_fiscal_years.id", ondelete="RESTRICT"),
        nullable=False,
    )
    account_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("accounting_accounts.id", ondelete="RESTRICT"),
        nullable=False,
    )
    debit_amount: Mapped[Decimal] = mapped_column(
        Numeric(20, 6), server_default="0", nullable=False
    )
    credit_amount: Mapped[Decimal] = mapped_column(
        Numeric(20, 6), server_default="0", nullable=False
    )
    currency_code: Mapped[str | None] = mapped_column(String(3), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
