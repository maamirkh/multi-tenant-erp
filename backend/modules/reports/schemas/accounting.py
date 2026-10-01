"""Accounting report filter schemas (spec §17, plan.md Phase 2 §2.1).

No ``branch_id`` anywhere — Accounting carries no ``branch_id`` column on
any model (FR-RPT-084). Response *row*/*aggregate* types are the
Accounting module's own already-tested Pydantic schemas
(``TrialBalanceReport``, ``PLReport``, ``BalanceSheetReport``,
``CashFlowReport``, ``GLReportRow``, ``ARAgingRow``, ``APAgingRow``,
``FinancialKPIResponse``) reused verbatim — Reports defines no competing
response shape for any of these (FR-RPT-081, no re-derived calculation).
The one exception is ``BankCashBookRow`` below: Bank Book and Cash Book
are two distinct existing response shapes (``BankBookRow``/``CashBookRow``)
merged under a single Epic 11 report key (``accounting.bank_cash_book``,
spec §9) — a thin, non-computational union type, not a new calculation.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class TrialBalanceFilter(BaseModel):
    model_config = ConfigDict(extra="forbid")

    period_id: UUID
    comparative_period_id: UUID | None = None


class GlFilter(BaseModel):
    model_config = ConfigDict(extra="forbid")

    account_id: UUID | None = None
    cost_center_id: UUID | None = None
    fiscal_period_id: UUID | None = None
    start_date: date | None = None
    end_date: date | None = None
    cursor: str | None = None
    """Opaque continuation token (base64 of ``posting_date|journal_entry_id|
    line_number``) — the one cursor-paginated report key; carried on the
    filter itself since ``ReportAdapter.run()``'s uniform signature has no
    dedicated cursor parameter."""


class ProfitLossFilter(BaseModel):
    model_config = ConfigDict(extra="forbid")

    period_from: date
    period_to: date
    comparative_from: date | None = None
    comparative_to: date | None = None
    cost_center_id: UUID | None = None
    report_currency: str | None = None


class BalanceSheetFilter(BaseModel):
    model_config = ConfigDict(extra="forbid")

    as_of_date: date
    comparative_date: date | None = None
    report_currency: str | None = None


class CashFlowFilter(BaseModel):
    model_config = ConfigDict(extra="forbid")

    period_from: date
    period_to: date


class ArAgingFilter(BaseModel):
    model_config = ConfigDict(extra="forbid")

    as_of_date: date


class ApAgingFilter(BaseModel):
    model_config = ConfigDict(extra="forbid")

    as_of_date: date


class BankCashBookFilter(BaseModel):
    model_config = ConfigDict(extra="forbid")

    account_type: Literal["bank", "cash"]
    account_id: UUID
    from_date: date
    to_date: date


class AccountingKpiFilter(BaseModel):
    model_config = ConfigDict(extra="forbid")

    as_of_date: date


class BankCashBookRow(BaseModel):
    """Union row shape for the combined Bank/Cash Book report key — see
    module docstring."""

    transaction_id: UUID
    transaction_date: date
    transaction_type: str
    amount: Decimal
    reference: str | None = None
    description: str | None = None
    is_reconciled: bool | None = None
