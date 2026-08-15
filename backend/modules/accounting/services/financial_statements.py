"""FinancialStatementService — Phase 12 (multi-currency) + Phase 13 (full suite).

Phase 12 (tasks.md T248) shipped ``get_balance_sheet()``/``get_pl()`` with
multi-currency translation only. Phase 13 (tasks.md T255) layers onto the
SAME class/methods: comparative periods, a cost-center filter for P&L, plus
two new methods — ``get_trial_balance()`` and ``get_cash_flow()``. Both
phases' signatures are backward compatible: every Phase 13 addition is a
new keyword-only-used parameter with a default, so Phase 12's existing
call sites and tests are unaffected.

Multi-currency translation (spec.md §24, unchanged from Phase 12):
  - Balance Sheet: CLOSING rate as of the report date.
  - P&L: AVERAGE rate as of ``period_to``.

Sign convention (established throughout this module, e.g.
``CostCenterService._build_pl_result``): ASSET/EXPENSE accounts are
debit-normal (balance = debit - credit); LIABILITY/EQUITY/REVENUE accounts
are credit-normal (balance = credit - debit).

"Current Year Earnings" (Balance Sheet): this system has no automatic
period-end close (revenue/expense accounts are only zeroed by an explicit
CLOSING journal entry, if and when one is posted). Real accounting
software — and the Balance Sheet equation itself — requires Assets ==
Liabilities + Equity to hold at ANY point in time, not only right after a
formal close. So ``get_balance_sheet()`` computes unclosed YTD net income
(revenue - expense from the containing fiscal year's start through
``as_of_date``) and includes it as a synthetic "Current Year Earnings"
equity line (``account_id=None`` — it is not a real ledger account, just
computed). Once/if a CLOSING entry IS posted for some sub-range, revenue/
expense balances for that range are zeroed by the closing entry itself, so
this line naturally shrinks to whatever remains unclosed — no double
counting against the real Retained Earnings account's own balance.

Cash Flow (indirect method, spec.md §17, data-model.md §4.5 item 4,
plan.md acceptance criterion "Cash Flow closing balance matches GL cash and
bank account balances"): this is a MATHEMATICAL IDENTITY, not an
approximation — every posted journal entry balances (debit == credit,
enforced by PostingEngine), and every account belongs to exactly one of
three disjoint buckets this method sums over: (1) cash/bank accounts (the
target being explained — excluded from the adjustment), (2) P&L accounts
(collapsed into ``net_income``), (3) every other Balance Sheet account
(the "working capital" adjustment). Summing net_income + the working
capital adjustment therefore reconciles to the actual cash movement
EXACTLY, for any correctly double-entry-posted data — regardless of
whether a given movement would traditionally be classified as
"operating," "investing," or "financing" (the Account model carries no
such classification flag; this is deliberately out of Phase 13's scope —
see the module PHR).

Spec ref: specs/008-accounting-finance/spec.md §17, §24
Tasks ref: specs/008-accounting-finance/tasks.md T248, T255
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from modules.accounting.exceptions import PostingValidationError
from modules.accounting.repositories.fiscal import FiscalYearRepository
from modules.accounting.repositories.foundation import AccountingConfigurationRepository
from modules.accounting.repositories.gl import GLReportRepository
from modules.accounting.services.currency_service import CurrencyService


class FinancialStatementService:
    """Generates multi-currency-aware financial statements from posted GL data."""

    def __init__(
        self,
        db: Session,
        gl_report_repo: GLReportRepository,
        config_repo: AccountingConfigurationRepository,
        currency_service: CurrencyService,
        fiscal_year_repo: FiscalYearRepository,
    ) -> None:
        self.db = db
        self._gl_reports = gl_report_repo
        self._config_repo = config_repo
        self._currency = currency_service
        self._fiscal_years = fiscal_year_repo

    def get_balance_sheet(
        self,
        company_id: UUID,
        as_of_date: date,
        comparative_date: date | None = None,
        report_currency: str | None = None,
    ) -> dict[str, Any]:
        """Aggregate ASSET/LIABILITY/EQUITY balances as of ``as_of_date``,
        translated into ``report_currency`` using the CLOSING rate if given
        and different from the company's base currency. If
        ``comparative_date`` is given, the same report is also generated as
        of that date and attached under ``"comparative"``.
        """
        report = self._build_balance_sheet(company_id, as_of_date, report_currency)
        if comparative_date is not None:
            report["comparative"] = self._build_balance_sheet(
                company_id, comparative_date, report_currency
            )
        return report

    def _build_balance_sheet(
        self, company_id: UUID, as_of_date: date, report_currency: str | None
    ) -> dict[str, Any]:
        base_currency = self._get_base_currency(company_id)
        rate = self._resolve_rate(
            company_id, base_currency, report_currency, as_of_date, rate_type="CLOSING"
        )

        rows = self._gl_reports.balance_sheet_query(company_id, as_of_date)
        assets: list[dict[str, Any]] = []
        liabilities: list[dict[str, Any]] = []
        equity: list[dict[str, Any]] = []
        total_assets = Decimal("0")
        total_liabilities = Decimal("0")
        total_equity = Decimal("0")

        for row in rows:
            if row["account_type"] == "ASSET":
                amount = (row["total_debit"] - row["total_credit"]) * rate
                assets.append({**row, "amount": amount})
                total_assets += amount
            elif row["account_type"] == "LIABILITY":
                amount = (row["total_credit"] - row["total_debit"]) * rate
                liabilities.append({**row, "amount": amount})
                total_liabilities += amount
            else:  # EQUITY
                amount = (row["total_credit"] - row["total_debit"]) * rate
                equity.append({**row, "amount": amount})
                total_equity += amount

        current_year_earnings = (
            self._get_current_year_earnings(company_id, as_of_date) * rate
        )
        if current_year_earnings != 0:
            equity.append(
                {
                    "account_id": None,
                    "account_code": "CYE",
                    "account_name": "Current Year Earnings",
                    "account_type": "EQUITY",
                    "total_debit": Decimal("0"),
                    "total_credit": Decimal("0"),
                    "amount": current_year_earnings,
                }
            )
            total_equity += current_year_earnings

        return {
            "company_id": company_id,
            "as_of_date": as_of_date,
            "report_currency": report_currency or base_currency,
            "assets": assets,
            "liabilities": liabilities,
            "equity": equity,
            "total_assets": total_assets,
            "total_liabilities": total_liabilities,
            "total_equity": total_equity,
            "is_balanced": total_assets == total_liabilities + total_equity,
        }

    def get_pl(
        self,
        company_id: UUID,
        period_from: date,
        period_to: date,
        comparative_from: date | None = None,
        comparative_to: date | None = None,
        cost_center_id: UUID | None = None,
        report_currency: str | None = None,
    ) -> dict[str, Any]:
        """Aggregate REVENUE/EXPENSE activity for ``[period_from, period_to]``,
        optionally filtered to one ``cost_center_id`` and translated into
        ``report_currency`` using the AVERAGE rate. If ``comparative_from``/
        ``comparative_to`` are given, the same report is generated for that
        range too and attached under ``"comparative"``.
        """
        report = self._build_pl(
            company_id, period_from, period_to, cost_center_id, report_currency
        )
        if comparative_from is not None and comparative_to is not None:
            report["comparative"] = self._build_pl(
                company_id,
                comparative_from,
                comparative_to,
                cost_center_id,
                report_currency,
            )
        return report

    def _build_pl(
        self,
        company_id: UUID,
        period_from: date,
        period_to: date,
        cost_center_id: UUID | None,
        report_currency: str | None,
    ) -> dict[str, Any]:
        base_currency = self._get_base_currency(company_id)
        rate = self._resolve_rate(
            company_id, base_currency, report_currency, period_to, rate_type="AVERAGE"
        )

        rows = self._gl_reports.pl_query(
            company_id, period_from, period_to, cost_center_id
        )
        revenue_lines: list[dict[str, Any]] = []
        expense_lines: list[dict[str, Any]] = []
        total_revenue = Decimal("0")
        total_expense = Decimal("0")

        for row in rows:
            if row["account_type"] == "REVENUE":
                amount = (row["total_credit"] - row["total_debit"]) * rate
                revenue_lines.append({**row, "amount": amount})
                total_revenue += amount
            else:  # EXPENSE
                amount = (row["total_debit"] - row["total_credit"]) * rate
                expense_lines.append({**row, "amount": amount})
                total_expense += amount

        return {
            "company_id": company_id,
            "period_from": period_from,
            "period_to": period_to,
            "cost_center_id": cost_center_id,
            "report_currency": report_currency or base_currency,
            "revenue_lines": revenue_lines,
            "expense_lines": expense_lines,
            "total_revenue": total_revenue,
            "total_expense": total_expense,
            "net_income": total_revenue - total_expense,
        }

    def get_trial_balance(
        self,
        company_id: UUID,
        period_id: UUID,
        comparative_period_id: UUID | None = None,
    ) -> dict[str, Any]:
        """Per-account debit/credit totals for one fiscal period — must
        balance (total debit == total credit) by construction of
        double-entry posting; this is a verification, not an adjustment.
        """
        report = self._build_trial_balance(company_id, period_id)
        if comparative_period_id is not None:
            report["comparative"] = self._build_trial_balance(
                company_id, comparative_period_id
            )
        return report

    def _build_trial_balance(self, company_id: UUID, period_id: UUID) -> dict[str, Any]:
        rows = self._gl_reports.trial_balance_query(company_id, period_id)
        total_debit = sum((r["total_debit"] for r in rows), Decimal("0"))
        total_credit = sum((r["total_credit"] for r in rows), Decimal("0"))
        return {
            "company_id": company_id,
            "fiscal_period_id": period_id,
            "rows": rows,
            "total_debit": total_debit,
            "total_credit": total_credit,
            "is_balanced": total_debit == total_credit,
        }

    def get_cash_flow(
        self, company_id: UUID, period_from: date, period_to: date
    ) -> dict[str, Any]:
        """Indirect-method Cash Flow statement for ``[period_from, period_to]``.

        Starts from net income, adjusts for the period's working-capital
        movement (every non-cash Balance Sheet account), and reconciles the
        result to the actual GL cash/bank balance change — see the module
        docstring for why this reconciliation is an exact identity rather
        than an approximation.
        """
        pl = self._build_pl(company_id, period_from, period_to, None, None)
        net_income = pl["net_income"]

        wc_rows = self._gl_reports.working_capital_query(
            company_id, period_from, period_to
        )
        adjustments: list[dict[str, Any]] = []
        total_adjustment = Decimal("0")
        for row in wc_rows:
            if row["account_type"] == "ASSET":
                adjustment = -(row["total_debit"] - row["total_credit"])
            else:  # LIABILITY or EQUITY
                adjustment = row["total_credit"] - row["total_debit"]
            adjustments.append({**row, "adjustment": adjustment})
            total_adjustment += adjustment

        net_cash_from_operations = net_income + total_adjustment

        opening_cash_balance = self._gl_reports.cash_balance_query(
            company_id, period_from - timedelta(days=1)
        )
        closing_cash_balance = self._gl_reports.cash_balance_query(
            company_id, period_to
        )
        actual_net_change = closing_cash_balance - opening_cash_balance

        return {
            "company_id": company_id,
            "period_from": period_from,
            "period_to": period_to,
            "net_income": net_income,
            "working_capital_adjustments": adjustments,
            "net_cash_from_operating_activities": net_cash_from_operations,
            "opening_cash_balance": opening_cash_balance,
            "closing_cash_balance": closing_cash_balance,
            "net_change_in_cash": actual_net_change,
            "reconciles": net_cash_from_operations == actual_net_change,
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_current_year_earnings(self, company_id: UUID, as_of_date: date) -> Decimal:
        """YTD net income (revenue - expense) from the containing fiscal
        year's start through ``as_of_date``, in the company's BASE currency
        (translation to ``report_currency`` is applied by the caller, same
        as every other Balance Sheet line). Zero if no fiscal year covers
        ``as_of_date``.
        """
        fiscal_year = self._fiscal_years.find_containing_date(company_id, as_of_date)
        if fiscal_year is None:
            return Decimal("0")
        rows = self._gl_reports.pl_query(company_id, fiscal_year.start_date, as_of_date)
        net = Decimal("0")
        for row in rows:
            if row["account_type"] == "REVENUE":
                net += row["total_credit"] - row["total_debit"]
            else:  # EXPENSE
                net -= row["total_debit"] - row["total_credit"]
        return net

    def _get_base_currency(self, company_id: UUID) -> str:
        config = self._config_repo.get_for_company(company_id=company_id)
        if config is None:
            raise PostingValidationError(
                "Cannot generate financial statement: accounting configuration "
                "is not set up for this company."
            )
        return config.base_currency_code

    def _resolve_rate(
        self,
        company_id: UUID,
        base_currency: str,
        report_currency: str | None,
        rate_date: date,
        rate_type: str,
    ) -> Decimal:
        if report_currency is None or report_currency.upper() == base_currency.upper():
            return Decimal("1")
        return self._currency.get_rate(
            company_id, base_currency, report_currency, rate_date, rate_type=rate_type
        )
