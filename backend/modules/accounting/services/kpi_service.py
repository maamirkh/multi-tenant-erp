"""FinancialKPIService — CFO Financial Intelligence & KPI Dashboard — Phase 15.

Computes all 15 KPIs spec.md §40 lists for the executive dashboard, each
compared against the equivalent prior-period value so the API can report a
percentage change and a direction (spec.md §40: "returns all 15 KPIs with
values and change vs prior period" — tasks.md T287).

Every KPI is derived from data already computed by earlier phases rather
than re-implemented:
  - Cash Position:            ``GLReportRepository.cash_balance_query()`` (Phase 13)
  - Total AR / Total AP:      ``AgingCalculator``/``APAgingCalculator`` totals (Phase 6/7) —
                               the aging report's grand total already equals total
                               outstanding, so there is no separate query.
  - AR/AP Overdue %:          the same aging report, minus its "current" bucket.
  - Revenue MTD, Net Margin:  ``FinancialStatementService.get_pl()`` (Phase 12/13)
  - Gross Profit Margin:      ``GLReportRepository.pl_query(group_code="COGS")``
                               (Phase 15 addition — COGS is its own account group,
                               seeded identically by every COA template)
  - Operating Cash Flow:      ``FinancialStatementService.get_cash_flow()`` (Phase 13)
  - Tax Liability Balance:    cumulative net balance (credit - debit, all-time) of
                               every configured ``TaxCode.gl_account_id`` — mirrors
                               ``TaxService.get_vat_summary_report()``'s output-minus-
                               recoverable-input pattern (spec.md §23.6), generalised
                               to a running balance rather than a period movement,
                               and to every tax type (VAT/GST/WHT), since there is no
                               single "tax liability control account" field on
                               ``AccountingConfiguration``.
  - Period Close Status:      ``FiscalYearRepository.find_current()`` +
                               ``FiscalPeriodRepository.list_periods()`` (Phase 3)

Current Ratio / Quick Ratio classification (ARCHITECTURAL NOTE): ``Account``
has no ``is_current``/``is_inventory`` flag. Every industry COA template
(``services/coa_templates.py``) seeds the SAME ``CUR-AST``/``CUR-LIA``
account-group codes for Current Assets/Current Liabilities, so
``GLReportRepository.current_position_query()`` classifies by that group
code — a platform-wide structural convention, not a per-tenant guess.
Inventory (for Quick Ratio's Current Assets − Inventory) has no such group
of its own; it is identified by ``account_name`` containing "inventory"
(case-insensitive) within the Current Assets group — the only signal
available without adding a new Account flag, which is out of this phase's
scope (tasks.md T286-T293 lists no migration task). This heuristic is
documented here and in the unit tests that pin its expected behaviour.

DSO/DPO use the current month-to-date window as "the period": DSO =
(Total AR / Revenue MTD) * days elapsed this month; DPO = (Total AP / COGS
MTD) * days elapsed this month — the standard turnover-ratio formula
(spec.md §40), just anchored to MTD rather than a trailing-12-months window
since this system has no budget/annualised revenue figure to draw on yet.

Spec ref: specs/008-accounting-finance/spec.md §40 KPI Requirements
Tasks ref: specs/008-accounting-finance/tasks.md T286
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from sqlalchemy.orm import Session

from modules.accounting.exceptions import PostingValidationError
from modules.accounting.repositories.ap import SupplierLedgerRepository
from modules.accounting.repositories.ar import CustomerLedgerRepository
from modules.accounting.repositories.fiscal import (
    FiscalPeriodRepository,
    FiscalYearRepository,
)
from modules.accounting.repositories.foundation import AccountingConfigurationRepository
from modules.accounting.repositories.gl import GLReportRepository
from modules.accounting.repositories.tax import TaxCodeRepository
from modules.accounting.services.aging_calculator import (
    AgingCalculator,
    APAgingCalculator,
)
from modules.accounting.services.financial_statements import FinancialStatementService

Trend = Literal["up", "down", "flat"]

_KPI_LABELS: dict[str, str] = {
    "cash_position": "Cash Position",
    "accounts_receivable_total": "Accounts Receivable Total",
    "accounts_payable_total": "Accounts Payable Total",
    "ar_overdue_pct": "AR Aging — Overdue %",
    "ap_overdue_pct": "AP Aging — Overdue %",
    "revenue_mtd": "Revenue (MTD)",
    "gross_profit_margin": "Gross Profit Margin",
    "net_profit_margin": "Net Profit Margin",
    "current_ratio": "Current Ratio",
    "quick_ratio": "Quick Ratio",
    "days_sales_outstanding": "Days Sales Outstanding (DSO)",
    "days_payable_outstanding": "Days Payable Outstanding (DPO)",
    "operating_cash_flow": "Operating Cash Flow",
    "tax_liability_balance": "Tax Liability Balance",
}


@dataclass
class _RawKPISet:
    """One as-of-date snapshot of every numeric KPI's raw value."""

    cash_position: Decimal
    accounts_receivable_total: Decimal
    accounts_payable_total: Decimal
    ar_overdue_pct: Decimal
    ap_overdue_pct: Decimal
    revenue_mtd: Decimal
    gross_profit_margin: Decimal
    net_profit_margin: Decimal
    current_ratio: Decimal
    quick_ratio: Decimal
    days_sales_outstanding: Decimal
    days_payable_outstanding: Decimal
    operating_cash_flow: Decimal
    tax_liability_balance: Decimal


def _safe_div(numerator: Decimal, denominator: Decimal) -> Decimal:
    """Division that returns 0 instead of raising on a zero denominator.

    Safe here because every caller is read-only reporting math (a ratio
    with no denominator has no meaningful value) — never used on the
    posting path where a silent zero could hide a real error.
    """
    if denominator == 0:
        return Decimal("0")
    return numerator / denominator


def _month_start(d: date) -> date:
    return d.replace(day=1)


def _prior_period_end(d: date) -> date:
    """Same day-of-month, one calendar month back, clipped to that month's
    last day — gives an apples-to-apples "prior MTD" comparison point
    (e.g. Aug 13 -> Jul 13; Mar 31 -> Feb 28/29).
    """
    last_day_prev_month = _month_start(d) - timedelta(days=1)
    day_count = (d - _month_start(d)).days
    candidate = last_day_prev_month.replace(day=1) + timedelta(days=day_count)
    return min(candidate, last_day_prev_month)


class FinancialKPIService:
    """Real-time financial KPI calculator for the CFO dashboard (spec.md §40)."""

    def __init__(
        self,
        db: Session,
        gl_report_repo: GLReportRepository,
        config_repo: AccountingConfigurationRepository,
        customer_ledger_repo: CustomerLedgerRepository,
        supplier_ledger_repo: SupplierLedgerRepository,
        tax_code_repo: TaxCodeRepository,
        fiscal_year_repo: FiscalYearRepository,
        fiscal_period_repo: FiscalPeriodRepository,
        financial_statements: FinancialStatementService,
    ) -> None:
        self.db = db
        self._gl_reports = gl_report_repo
        self._config_repo = config_repo
        self._ar_aging = AgingCalculator(customer_ledger_repo)
        self._ap_aging = APAgingCalculator(supplier_ledger_repo)
        self._tax_codes = tax_code_repo
        self._fiscal_years = fiscal_year_repo
        self._fiscal_periods = fiscal_period_repo
        self._financial_statements = financial_statements

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_dashboard_kpis(self, company_id: UUID, as_of_date: date) -> dict[str, Any]:
        """All 15 KPIs: 14 numeric values (each with prior-period comparison)
        plus Period Close Status (categorical, not a ratio).
        """
        self._require_configuration(company_id)
        current = self._compute_raw(company_id, as_of_date)
        prior = self._compute_raw(company_id, _prior_period_end(as_of_date))

        kpis = {
            field: self._kpi_value(
                _KPI_LABELS[field], getattr(current, field), getattr(prior, field)
            )
            for field in _KPI_LABELS
        }

        return {
            "company_id": company_id,
            "as_of_date": as_of_date,
            "kpis": kpis,
            "period_close_status": self._period_close_status(company_id),
        }

    def get_cash_position(
        self, company_id: UUID, as_of_date: date, trend_days: int = 7
    ) -> dict[str, Any]:
        """Bank + cash account balances as of ``as_of_date``, with a daily
        trend series over the trailing ``trend_days`` days (tasks.md T288).
        """
        self._require_configuration(company_id)
        accounts = self._gl_reports.cash_and_bank_account_balances_query(
            company_id, as_of_date
        )
        total = sum((a["balance"] for a in accounts), Decimal("0"))
        trend = [
            {
                "date": as_of_date - timedelta(days=offset),
                "balance": self._gl_reports.cash_balance_query(
                    company_id, as_of_date - timedelta(days=offset)
                ),
            }
            for offset in range(trend_days - 1, -1, -1)
        ]
        return {
            "company_id": company_id,
            "as_of_date": as_of_date,
            "total_cash_position": total,
            "accounts": accounts,
            "trend": trend,
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _require_configuration(self, company_id: UUID) -> None:
        if self._config_repo.get_for_company(company_id=company_id) is None:
            raise PostingValidationError(
                "Cannot compute financial KPIs: accounting configuration "
                "is not set up for this company."
            )

    def _compute_raw(self, company_id: UUID, as_of_date: date) -> _RawKPISet:
        cash_position = self._gl_reports.cash_balance_query(company_id, as_of_date)

        ar_aging = self._ar_aging.calculate_ar_aging(company_id, as_of_date)
        ar_total = ar_aging.totals.total
        ar_overdue = ar_total - ar_aging.totals.current
        ar_overdue_pct = _safe_div(ar_overdue, ar_total) * 100

        ap_aging = self._ap_aging.calculate_ap_aging(company_id, as_of_date)
        ap_total = ap_aging.totals.total
        ap_overdue = ap_total - ap_aging.totals.current
        ap_overdue_pct = _safe_div(ap_overdue, ap_total) * 100

        month_start = _month_start(as_of_date)
        days_elapsed = max((as_of_date - month_start).days + 1, 1)

        pl = self._financial_statements.get_pl(company_id, month_start, as_of_date)
        revenue_mtd = pl["total_revenue"]
        net_income_mtd = pl["net_income"]
        net_profit_margin = _safe_div(net_income_mtd, revenue_mtd) * 100

        cogs_rows = self._gl_reports.pl_query(
            company_id, month_start, as_of_date, group_code="COGS"
        )
        cogs_mtd = sum(
            (r["total_debit"] - r["total_credit"] for r in cogs_rows), Decimal("0")
        )
        gross_profit_margin = _safe_div(revenue_mtd - cogs_mtd, revenue_mtd) * 100

        current_assets, current_liabilities, inventory = self._current_position(
            company_id, as_of_date
        )
        current_ratio = _safe_div(current_assets, current_liabilities)
        quick_ratio = _safe_div(current_assets - inventory, current_liabilities)

        dso = _safe_div(ar_total, revenue_mtd) * days_elapsed
        dpo = _safe_div(ap_total, cogs_mtd) * days_elapsed

        cash_flow = self._financial_statements.get_cash_flow(
            company_id, month_start, as_of_date
        )
        operating_cash_flow = cash_flow["net_cash_from_operating_activities"]

        tax_liability_balance = self._tax_liability_balance(company_id, as_of_date)

        return _RawKPISet(
            cash_position=cash_position,
            accounts_receivable_total=ar_total,
            accounts_payable_total=ap_total,
            ar_overdue_pct=ar_overdue_pct,
            ap_overdue_pct=ap_overdue_pct,
            revenue_mtd=revenue_mtd,
            gross_profit_margin=gross_profit_margin,
            net_profit_margin=net_profit_margin,
            current_ratio=current_ratio,
            quick_ratio=quick_ratio,
            days_sales_outstanding=dso,
            days_payable_outstanding=dpo,
            operating_cash_flow=operating_cash_flow,
            tax_liability_balance=tax_liability_balance,
        )

    def _current_position(
        self, company_id: UUID, as_of_date: date
    ) -> tuple[Decimal, Decimal, Decimal]:
        rows = self._gl_reports.current_position_query(company_id, as_of_date)
        current_assets = Decimal("0")
        current_liabilities = Decimal("0")
        inventory = Decimal("0")
        for row in rows:
            balance_debit_normal = row["total_debit"] - row["total_credit"]
            if row["group_code"] == "CUR-AST":
                current_assets += balance_debit_normal
                if "inventory" in row["account_name"].lower():
                    inventory += balance_debit_normal
            elif row["group_code"] == "CUR-LIA":
                current_liabilities += -balance_debit_normal
        return current_assets, current_liabilities, inventory

    def _tax_liability_balance(self, company_id: UUID, as_of_date: date) -> Decimal:
        balance = Decimal("0")
        for tax_code in self._tax_codes.list_all(company_id):
            totals = self._gl_reports.account_balance_query(
                company_id=company_id,
                account_id=tax_code.gl_account_id,
                end_date=as_of_date,
            )
            balance += totals["total_credit"] - totals["total_debit"]
        return balance

    def _period_close_status(self, company_id: UUID) -> list[dict[str, Any]]:
        fiscal_year = self._fiscal_years.find_current(company_id)
        if fiscal_year is None:
            return []
        periods = self._fiscal_periods.list_periods(company_id, fiscal_year.id)
        return [
            {
                "period_name": p.period_name,
                "period_number": p.period_number,
                "status": p.status,
            }
            for p in periods
        ]

    @staticmethod
    def _kpi_value(
        label: str, current_value: Decimal, prior_value: Decimal
    ) -> dict[str, Any]:
        if prior_value == 0:
            change_pct = None
        else:
            change_pct = (current_value - prior_value) / abs(prior_value) * 100

        trend: Trend
        if current_value > prior_value:
            trend = "up"
        elif current_value < prior_value:
            trend = "down"
        else:
            trend = "flat"

        return {
            "label": label,
            "current_value": current_value,
            "prior_value": prior_value,
            "change_pct": change_pct,
            "trend": trend,
        }
