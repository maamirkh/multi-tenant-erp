"""``AccountingAdapter`` — wraps Accounting's already-implemented
financial-statement/AR/AP/bank/cash/KPI services behind the Reports
``ReportAdapter`` Protocol. Every figure is computed by an existing
Accounting service method; this adapter re-derives nothing (FR-RPT-081).

**Stateless by design** (base.py's Protocol docstring): this adapter holds
no pre-built service instances. Every call builds the one specific
Accounting service it needs, fresh, from ``modules.accounting.dependencies``'s
existing ``build_<x>_service(db)`` factory functions — the same
``Depends()``-free factories Accounting's own router already uses.

Response *types* reuse Accounting's own already-tested Pydantic schemas
verbatim (``modules/reports/schemas/accounting.py`` module docstring) —
the only Reports-owned response type here is ``BankCashBookRow``, a thin
union of two pre-existing row shapes for one combined report key.
"""

from __future__ import annotations

import base64
from collections.abc import Iterator
from datetime import date
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy.orm import Session

from modules.accounting.dependencies import (
    build_ap_service,
    build_ar_service,
    build_bank_account_service,
    build_cash_account_service,
    build_financial_statement_service,
    build_kpi_service,
    build_report_service,
)
from modules.accounting.exceptions import PostingValidationError
from modules.accounting.schemas.ap import APAgingRow
from modules.accounting.schemas.ar import ARAgingRow
from modules.accounting.schemas.dashboard import FinancialKPIResponse
from modules.accounting.schemas.gl import GLReportRow
from modules.accounting.schemas.reports import (
    BalanceSheetReport,
    CashFlowReport,
    PLReport,
    TrialBalanceReport,
)
from modules.reports.exceptions import ReportNotFoundError, UnavailablePrerequisiteError
from modules.reports.schemas.accounting import (
    AccountingKpiFilter,
    ApAgingFilter,
    ArAgingFilter,
    BalanceSheetFilter,
    BankCashBookFilter,
    BankCashBookRow,
    CashFlowFilter,
    GlFilter,
    ProfitLossFilter,
    TrialBalanceFilter,
)
from modules.reports.schemas.common import ComparisonRequest, ReportEnvelopeMeta
from modules.reports.services.adapters.base import (
    AggregateReportResult,
    BaseReportResult,
    CursorReportResult,
    PaginatedReportResult,
)

# Four PDF-eligible keys — **narrowed from spec §30/§211's stated six**
# (Trial Balance, P&L, Balance Sheet, Cash Flow, AR/AP aging+statements)
# after discovering a genuine template-shape mismatch during
# implementation: ``report_export.py``'s only statement-shaped template,
# ``"ledger_statement"``, calls ``getattr(t, "transaction_date", ...)`` /
# ``"amount_base"`` / ``"outstanding_amount"`` on each row, expecting real
# ``ARTransaction``/``APTransaction`` ORM objects (a *customer/supplier
# statement*) — not the ``AgingRow``/``APAgingRow`` bucket-total dataclass
# ``get_aging_report()`` actually returns (no ``transaction_date``/
# ``amount_base`` attributes at all). Forcing aging rows through that
# template would silently render blank/``None`` PDF cells rather than
# raise — a real defect, not a acceptable gap. No template shaped for the
# cross-customer aging aggregate exists anywhere in ``report_export.py``
# today. Smallest correct fix: AR/AP aging PDF export is not implemented
# in this phase (CSV/XLSX remain fully available for both); a future
# phase can add a dedicated aging PDF template or wire the *per-customer*
# statement path (which does fit ``ledger_statement``) once Reports
# exposes a customer/supplier-scoped statement report key.
_PDF_ELIGIBLE_KEYS = frozenset(
    {
        "accounting.trial_balance",
        "accounting.profit_loss",
        "accounting.balance_sheet",
        "accounting.cash_flow",
    }
)

_ARAP_AGING_KEYS = frozenset({"accounting.ar_aging", "accounting.ap_aging"})

_TEMPLATE_BY_KEY = {
    "accounting.trial_balance": "trial_balance",
    "accounting.profit_loss": "profit_loss",
    "accounting.balance_sheet": "balance_sheet",
    "accounting.cash_flow": "cash_flow",
}


def encode_cursor(cursor: tuple[date, UUID, int]) -> str:
    posting_date, journal_entry_id, line_number = cursor
    raw = f"{posting_date.isoformat()}|{journal_entry_id}|{line_number}"
    return base64.urlsafe_b64encode(raw.encode("utf-8")).decode("ascii")


def decode_cursor(cursor: str) -> tuple[date, UUID, int]:
    raw = base64.urlsafe_b64decode(cursor.encode("ascii")).decode("utf-8")
    date_part, uuid_part, line_part = raw.split("|")
    return date.fromisoformat(date_part), UUID(uuid_part), int(line_part)


def _meta(report_key: str, filters: BaseModel) -> ReportEnvelopeMeta:
    from modules.reports.schemas.common import FreshnessClassification, PeriodResolution

    return ReportEnvelopeMeta(
        report_key=report_key,
        applied_filters=filters.model_dump(mode="json"),
        period=PeriodResolution(
            start="1970-01-01T00:00:00+00:00",
            end="1970-01-01T00:00:00+00:00",
            timezone="UTC",
        ),
        freshness=FreshnessClassification.TRANSACTIONAL_LIVE,
    )


class AccountingAdapter:
    """Stateless domain adapter for ``ReportDomain.ACCOUNTING``'s 9 "Now"
    reports — see module docstring."""

    def run(
        self,
        db: Session,
        company_id: UUID,
        report_key: str,
        filters: BaseModel,
        page: int,
        page_size: int,
        sort: str | None,
        comparison: ComparisonRequest | None,
    ) -> BaseReportResult:
        if report_key == "accounting.trial_balance":
            assert isinstance(filters, TrialBalanceFilter)
            statements = build_financial_statement_service(db)
            data = statements.get_trial_balance(
                company_id, filters.period_id, filters.comparative_period_id
            )
            return AggregateReportResult[TrialBalanceReport](
                meta=_meta(report_key, filters),
                data=TrialBalanceReport.model_validate(data),
            )
        if report_key == "accounting.profit_loss":
            assert isinstance(filters, ProfitLossFilter)
            statements = build_financial_statement_service(db)
            data = statements.get_pl(
                company_id,
                filters.period_from,
                filters.period_to,
                filters.comparative_from,
                filters.comparative_to,
                filters.cost_center_id,
                filters.report_currency,
            )
            return AggregateReportResult[PLReport](
                meta=_meta(report_key, filters), data=PLReport.from_service_dict(data)
            )
        if report_key == "accounting.balance_sheet":
            assert isinstance(filters, BalanceSheetFilter)
            statements = build_financial_statement_service(db)
            data = statements.get_balance_sheet(
                company_id,
                filters.as_of_date,
                filters.comparative_date,
                filters.report_currency,
            )
            return AggregateReportResult[BalanceSheetReport](
                meta=_meta(report_key, filters),
                data=BalanceSheetReport.from_service_dict(data),
            )
        if report_key == "accounting.cash_flow":
            assert isinstance(filters, CashFlowFilter)
            statements = build_financial_statement_service(db)
            data = statements.get_cash_flow(
                company_id, filters.period_from, filters.period_to
            )
            return AggregateReportResult[CashFlowReport](
                meta=_meta(report_key, filters),
                data=CashFlowReport.model_validate(data),
            )
        if report_key == "accounting.kpis":
            assert isinstance(filters, AccountingKpiFilter)
            kpis = build_kpi_service(db)
            try:
                data = kpis.get_dashboard_kpis(company_id, filters.as_of_date)
            except PostingValidationError as exc:
                # ``get_dashboard_kpis``'s own ``_require_configuration()``
                # is its *only* raise site reachable from this call — a
                # tenant with no ``AccountingConfiguration`` row yet, a
                # genuine "not yet configured" prerequisite (this
                # exception's own module docstring names this exact case),
                # never an unhandled 500 (FR-RPT-272/341). Exposed by
                # Phase 4's Executive Dashboard, which must render a
                # defined UNAVAILABLE widget rather than fail the whole
                # request for any company that hasn't configured
                # Accounting yet (FR-RPT-044).
                raise UnavailablePrerequisiteError(report_key, str(exc)) from exc
            return AggregateReportResult[FinancialKPIResponse](
                meta=_meta(report_key, filters),
                data=FinancialKPIResponse.model_validate(data),
            )
        if report_key == "accounting.ar_aging":
            assert isinstance(filters, ArAgingFilter)
            ar = build_ar_service(db)
            offset = (page - 1) * page_size
            report = ar.get_aging_page(
                company_id, filters.as_of_date, page_size, offset
            )
            total = ar.count_aging_rows(company_id, filters.as_of_date)
            return PaginatedReportResult[ARAgingRow](
                meta=_meta(report_key, filters),
                items=[ARAgingRow.model_validate(r) for r in report.rows],
                total=total,
            )
        if report_key == "accounting.ap_aging":
            assert isinstance(filters, ApAgingFilter)
            ap = build_ap_service(db)
            offset = (page - 1) * page_size
            ap_report = ap.get_aging_page(
                company_id, filters.as_of_date, page_size, offset
            )
            total = ap.count_aging_rows(company_id, filters.as_of_date)
            return PaginatedReportResult[APAgingRow](
                meta=_meta(report_key, filters),
                items=[APAgingRow.model_validate(r) for r in ap_report.rows],
                total=total,
            )
        if report_key == "accounting.bank_cash_book":
            assert isinstance(filters, BankCashBookFilter)
            offset = (page - 1) * page_size
            rows, total = self._bank_cash_page(
                db, company_id, filters, page_size, offset
            )
            return PaginatedReportResult[BankCashBookRow](
                meta=_meta(report_key, filters), items=rows, total=total
            )
        if report_key == "accounting.gl":
            assert isinstance(filters, GlFilter)
            reports = build_report_service(db)
            cursor = decode_cursor(filters.cursor) if filters.cursor else None
            gl_filters = {
                "account_id": filters.account_id,
                "cost_center_id": filters.cost_center_id,
                "fiscal_period_id": filters.fiscal_period_id,
                "start_date": filters.start_date,
                "end_date": filters.end_date,
            }
            result = reports.get_gl_report(company_id, gl_filters, cursor, page_size)
            next_cursor = (
                encode_cursor(result["next_cursor"]) if result["has_more"] else None
            )
            return CursorReportResult[GLReportRow](
                meta=_meta(report_key, filters),
                items=[GLReportRow.model_validate(r) for r in result["items"]],
                has_more=result["has_more"],
                next_cursor=next_cursor,
            )
        raise ReportNotFoundError(report_key)

    def export_row_model(self, report_key: str) -> type[BaseModel]:
        if report_key == "accounting.ar_aging":
            return ARAgingRow
        if report_key == "accounting.ap_aging":
            return APAgingRow
        if report_key == "accounting.bank_cash_book":
            return BankCashBookRow
        if report_key == "accounting.gl":
            return GLReportRow
        raise ValueError(f"'{report_key}' has no export-row iteration seam.")

    def count_export_rows(
        self, db: Session, company_id: UUID, report_key: str, filters: BaseModel
    ) -> int:
        if report_key == "accounting.ar_aging":
            assert isinstance(filters, ArAgingFilter)
            return build_ar_service(db).count_aging_rows(company_id, filters.as_of_date)
        if report_key == "accounting.ap_aging":
            assert isinstance(filters, ApAgingFilter)
            return build_ap_service(db).count_aging_rows(company_id, filters.as_of_date)
        if report_key == "accounting.bank_cash_book":
            assert isinstance(filters, BankCashBookFilter)
            if filters.account_type == "bank":
                return build_bank_account_service(db).count_bank_transactions(
                    company_id,
                    filters.account_id,
                    from_date=filters.from_date,
                    to_date=filters.to_date,
                )
            return build_cash_account_service(db).count_cash_transactions(
                company_id,
                filters.account_id,
                from_date=filters.from_date,
                to_date=filters.to_date,
            )
        raise ValueError(f"'{report_key}' has no export-row count seam.")

    def iter_export_rows(
        self,
        db: Session,
        company_id: UUID,
        report_key: str,
        filters: BaseModel,
        sort: str | None,
        batch_size: int,
    ) -> Iterator[list[BaseModel]]:
        if report_key in _ARAP_AGING_KEYS:
            offset = 0
            while True:
                rows, count = self._page_for_export(
                    db, company_id, report_key, filters, batch_size, offset
                )
                if not rows:
                    return
                yield rows
                offset += batch_size
                if offset >= count:
                    return
        elif report_key == "accounting.bank_cash_book":
            assert isinstance(filters, BankCashBookFilter)
            offset = 0
            while True:
                bank_cash_rows, _total = self._bank_cash_page(
                    db, company_id, filters, batch_size, offset
                )
                if not bank_cash_rows:
                    return
                yield_rows: list[BaseModel] = list(bank_cash_rows)
                yield yield_rows
                offset += batch_size
        elif report_key == "accounting.gl":
            assert isinstance(filters, GlFilter)
            reports = build_report_service(db)
            cursor: tuple[date, UUID, int] | None = None
            gl_filters = {
                "account_id": filters.account_id,
                "cost_center_id": filters.cost_center_id,
                "fiscal_period_id": filters.fiscal_period_id,
                "start_date": filters.start_date,
                "end_date": filters.end_date,
            }
            while True:
                result = reports.get_gl_report(
                    company_id, gl_filters, cursor, batch_size
                )
                items: list[BaseModel] = [
                    GLReportRow.model_validate(r) for r in result["items"]
                ]
                if items:
                    yield items
                if not result["has_more"]:
                    return
                cursor = result["next_cursor"]
        else:
            raise ValueError(f"'{report_key}' has no export-row iteration seam.")

    def export_pdf(
        self, db: Session, company_id: UUID, report_key: str, filters: BaseModel
    ) -> bytes:
        """Delegates to Accounting's existing ``report_export.py::
        export_to_pdf()`` for the six PDF-eligible keys only.

        Calls the underlying service directly for the **raw, flat**
        service dict ``export_to_pdf()``'s own ``_rows_for_template()``
        expects — never the Reports-reshaped Pydantic schema ``run()``
        returns (``BalanceSheetReport``/``PLReport`` restructure the flat
        dict into nested sections via ``from_service_dict()``, a shape
        ``export_to_pdf()`` does not understand)."""
        from modules.accounting.services.report_export import export_to_pdf

        if report_key not in _PDF_ELIGIBLE_KEYS:
            raise ValueError(f"'{report_key}' is not PDF-eligible.")

        data = self._raw_service_dict(db, company_id, report_key, filters)
        return export_to_pdf(data, template=_TEMPLATE_BY_KEY[report_key])

    def _raw_service_dict(
        self, db: Session, company_id: UUID, report_key: str, filters: BaseModel
    ) -> dict[str, object]:
        if report_key == "accounting.trial_balance":
            assert isinstance(filters, TrialBalanceFilter)
            return build_financial_statement_service(db).get_trial_balance(
                company_id, filters.period_id, filters.comparative_period_id
            )
        if report_key == "accounting.profit_loss":
            assert isinstance(filters, ProfitLossFilter)
            return build_financial_statement_service(db).get_pl(
                company_id,
                filters.period_from,
                filters.period_to,
                filters.comparative_from,
                filters.comparative_to,
                filters.cost_center_id,
                filters.report_currency,
            )
        if report_key == "accounting.balance_sheet":
            assert isinstance(filters, BalanceSheetFilter)
            return build_financial_statement_service(db).get_balance_sheet(
                company_id,
                filters.as_of_date,
                filters.comparative_date,
                filters.report_currency,
            )
        assert report_key == "accounting.cash_flow"
        assert isinstance(filters, CashFlowFilter)
        return build_financial_statement_service(db).get_cash_flow(
            company_id, filters.period_from, filters.period_to
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _page_for_export(
        self,
        db: Session,
        company_id: UUID,
        report_key: str,
        filters: BaseModel,
        limit: int,
        offset: int,
    ) -> tuple[list[BaseModel], int]:
        if report_key == "accounting.ar_aging":
            assert isinstance(filters, ArAgingFilter)
            ar = build_ar_service(db)
            report = ar.get_aging_page(company_id, filters.as_of_date, limit, offset)
            total = ar.count_aging_rows(company_id, filters.as_of_date)
            ar_rows: list[BaseModel] = [
                ARAgingRow.model_validate(r) for r in report.rows
            ]
            return ar_rows, total
        assert isinstance(filters, ApAgingFilter)
        ap = build_ap_service(db)
        ap_report = ap.get_aging_page(company_id, filters.as_of_date, limit, offset)
        ap_total = ap.count_aging_rows(company_id, filters.as_of_date)
        ap_rows: list[BaseModel] = [
            APAgingRow.model_validate(r) for r in ap_report.rows
        ]
        return ap_rows, ap_total

    def _bank_cash_page(
        self,
        db: Session,
        company_id: UUID,
        filters: BankCashBookFilter,
        limit: int,
        offset: int,
    ) -> tuple[list[BankCashBookRow], int]:
        if filters.account_type == "bank":
            bank = build_bank_account_service(db)
            total = bank.count_bank_transactions(
                company_id,
                filters.account_id,
                from_date=filters.from_date,
                to_date=filters.to_date,
            )
            bank_txns = bank.get_bank_transactions_page(
                company_id,
                filters.account_id,
                from_date=filters.from_date,
                to_date=filters.to_date,
                limit=limit,
                offset=offset,
            )
            rows = [
                BankCashBookRow(
                    transaction_id=t.id,
                    transaction_date=t.transaction_date,
                    transaction_type=t.transaction_type,
                    amount=t.amount,
                    reference=t.reference,
                    description=t.description,
                    is_reconciled=t.is_reconciled,
                )
                for t in bank_txns
            ]
            return rows, total

        cash = build_cash_account_service(db)
        total = cash.count_cash_transactions(
            company_id,
            filters.account_id,
            from_date=filters.from_date,
            to_date=filters.to_date,
        )
        cash_txns = cash.get_cash_transactions_page(
            company_id,
            filters.account_id,
            from_date=filters.from_date,
            to_date=filters.to_date,
            limit=limit,
            offset=offset,
        )
        rows = [
            BankCashBookRow(
                transaction_id=t.id,
                transaction_date=t.transaction_date,
                transaction_type=t.transaction_type,
                amount=t.amount,
                reference=t.reference,
                description=t.description,
                is_reconciled=None,
            )
            for t in cash_txns
        ]
        return rows, total
