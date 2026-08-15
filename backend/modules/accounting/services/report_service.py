"""ReportService — GL Report + Subsidiary Ledger Reports — Phase 13.

Combines two tasks that share one file per tasks.md:
  - T256 ``GLReportService``: ``get_gl_report()`` — cursor-paginated GL
    detail, scalable to 500K+ rows (T270's performance target).
  - T257 subsidiary ledger reports: customer/supplier ledger, bank book,
    cash book, journal report.

DRY: customer/supplier statements and bank/cash books were already fully
implemented in Phases 6-9 (``AccountsReceivableService.get_customer_
statement()``, ``AccountsPayableService.get_supplier_statement()``,
``BankAccountService.get_bank_book()``, ``CashAccountService.get_cash_
book()``) — this service delegates to them rather than re-implementing the
same opening/closing-balance logic a second time. Only the GL report and
journal report are genuinely new in this phase.

Spec ref: specs/008-accounting-finance/spec.md §17 Financial Statements & Reports
Tasks ref: specs/008-accounting-finance/tasks.md T256, T257
"""

from __future__ import annotations

from datetime import date
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from modules.accounting.repositories.gl import (
    GLReportRepository,
    JournalEntryRepository,
)
from modules.accounting.services.ap_service import AccountsPayableService
from modules.accounting.services.ar_service import AccountsReceivableService
from modules.accounting.services.bank_service import BankAccountService
from modules.accounting.services.cash_service import CashAccountService


class ReportService:
    """GL detail report + subsidiary ledger report façade."""

    def __init__(
        self,
        db: Session,
        gl_report_repo: GLReportRepository,
        journal_repo: JournalEntryRepository,
        ar_service: AccountsReceivableService,
        ap_service: AccountsPayableService,
        bank_service: BankAccountService,
        cash_service: CashAccountService,
    ) -> None:
        self.db = db
        self._gl_reports = gl_report_repo
        self._journals = journal_repo
        self._ar = ar_service
        self._ap = ap_service
        self._bank = bank_service
        self._cash = cash_service

    # ------------------------------------------------------------------
    # GL report (T256) — cursor-paginated
    # ------------------------------------------------------------------

    def get_gl_report(
        self,
        company_id: UUID,
        filters: dict[str, Any] | None = None,
        cursor: tuple[date, UUID, int] | None = None,
        limit: int = 100,
    ) -> dict[str, Any]:
        """Detailed GL entries with account/date/cost-center filters,
        keyset-paginated for scale (T270: 500K+ rows).

        ``filters`` supports ``account_id``, ``cost_center_id``,
        ``fiscal_period_id``, ``start_date``, ``end_date``.
        """
        filters = filters or {}
        rows, has_more = self._gl_reports.gl_detail_cursor_query(
            company_id=company_id,
            account_id=filters.get("account_id"),
            start_date=filters.get("start_date"),
            end_date=filters.get("end_date"),
            cost_center_id=filters.get("cost_center_id"),
            fiscal_period_id=filters.get("fiscal_period_id"),
            cursor=cursor,
            limit=limit,
        )
        next_cursor = None
        if has_more and rows:
            last = rows[-1]
            next_cursor = (
                last["posting_date"],
                last["journal_entry_id"],
                last["line_number"],
            )
        return {"items": rows, "has_more": has_more, "next_cursor": next_cursor}

    # ------------------------------------------------------------------
    # Subsidiary ledger reports (T257) — delegate to existing services
    # ------------------------------------------------------------------

    def get_customer_ledger_report(
        self, company_id: UUID, customer_id: UUID, from_date: date, to_date: date
    ) -> dict[str, Any]:
        return self._ar.get_customer_statement(
            company_id, customer_id, from_date, to_date
        )

    def get_supplier_ledger_report(
        self, company_id: UUID, supplier_id: UUID, from_date: date, to_date: date
    ) -> dict[str, Any]:
        return self._ap.get_supplier_statement(
            company_id, supplier_id, from_date, to_date
        )

    def get_bank_book(
        self, company_id: UUID, bank_account_id: UUID, from_date: date, to_date: date
    ) -> dict[str, Any]:
        return self._bank.get_bank_book(company_id, bank_account_id, from_date, to_date)

    def get_cash_book(
        self, company_id: UUID, cash_account_id: UUID, from_date: date, to_date: date
    ) -> dict[str, Any]:
        return self._cash.get_cash_book(company_id, cash_account_id, from_date, to_date)

    def get_journal_report(
        self, company_id: UUID, period_id: UUID, skip: int = 0, limit: int = 500
    ) -> dict[str, Any]:
        """All POSTED journal entries for one fiscal period."""
        items, total = self._journals.search(
            company_id=company_id,
            filters={"fiscal_period_id": period_id, "status": "POSTED"},
            skip=skip,
            limit=limit,
        )
        return {
            "company_id": company_id,
            "fiscal_period_id": period_id,
            "entries": items,
            "total": total,
        }
