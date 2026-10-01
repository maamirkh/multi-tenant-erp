"""T057 — Contract test (mocked services): typed output stability for all
9 Accounting report keys.
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from modules.reports.schemas.accounting import (
    AccountingKpiFilter,
    ApAgingFilter,
    ArAgingFilter,
    BankCashBookFilter,
    GlFilter,
    ProfitLossFilter,
    TrialBalanceFilter,
)
from modules.reports.services.adapters import (
    accounting_adapter as accounting_adapter_mod,
)
from modules.reports.services.adapters.accounting_adapter import AccountingAdapter
from modules.reports.services.adapters.base import (
    AggregateReportResult,
    CursorReportResult,
    PaginatedReportResult,
)

COMPANY_ID = uuid.uuid4()


class TestAccountingAdapterContract:
    def test_trial_balance_returns_aggregate(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        statements = MagicMock()
        statements.get_trial_balance.return_value = {
            "company_id": COMPANY_ID,
            "fiscal_period_id": uuid.uuid4(),
            "rows": [],
            "total_debit": Decimal("0"),
            "total_credit": Decimal("0"),
            "is_balanced": True,
        }
        monkeypatch.setattr(
            accounting_adapter_mod,
            "build_financial_statement_service",
            lambda db: statements,
        )
        result = AccountingAdapter().run(
            MagicMock(),
            COMPANY_ID,
            "accounting.trial_balance",
            TrialBalanceFilter(period_id=uuid.uuid4()),
            page=1,
            page_size=20,
            sort=None,
            comparison=None,
        )
        assert isinstance(result, AggregateReportResult)

    def test_ar_aging_returns_paginated(self, monkeypatch: pytest.MonkeyPatch) -> None:
        ar = MagicMock()
        fake_report = MagicMock()
        fake_report.rows = []
        ar.get_aging_page.return_value = fake_report
        ar.count_aging_rows.return_value = 0
        monkeypatch.setattr(accounting_adapter_mod, "build_ar_service", lambda db: ar)
        result = AccountingAdapter().run(
            MagicMock(),
            COMPANY_ID,
            "accounting.ar_aging",
            ArAgingFilter(as_of_date=date(2026, 1, 1)),
            page=1,
            page_size=20,
            sort=None,
            comparison=None,
        )
        assert isinstance(result, PaginatedReportResult)
        assert result.total == 0

    def test_ap_aging_returns_paginated(self, monkeypatch: pytest.MonkeyPatch) -> None:
        ap = MagicMock()
        fake_report = MagicMock()
        fake_report.rows = []
        ap.get_aging_page.return_value = fake_report
        ap.count_aging_rows.return_value = 0
        monkeypatch.setattr(accounting_adapter_mod, "build_ap_service", lambda db: ap)
        result = AccountingAdapter().run(
            MagicMock(),
            COMPANY_ID,
            "accounting.ap_aging",
            ApAgingFilter(as_of_date=date(2026, 1, 1)),
            page=1,
            page_size=20,
            sort=None,
            comparison=None,
        )
        assert isinstance(result, PaginatedReportResult)

    def test_gl_returns_cursor_result(self, monkeypatch: pytest.MonkeyPatch) -> None:
        reports = MagicMock()
        reports.get_gl_report.return_value = {
            "items": [],
            "has_more": False,
            "next_cursor": None,
        }
        monkeypatch.setattr(
            accounting_adapter_mod, "build_report_service", lambda db: reports
        )
        result = AccountingAdapter().run(
            MagicMock(),
            COMPANY_ID,
            "accounting.gl",
            GlFilter(),
            page=1,
            page_size=20,
            sort=None,
            comparison=None,
        )
        assert isinstance(result, CursorReportResult)
        assert result.has_more is False
        assert result.next_cursor is None

    def test_kpis_returns_aggregate(self, monkeypatch: pytest.MonkeyPatch) -> None:
        kpis = MagicMock()
        kpis.get_dashboard_kpis.return_value = {
            "company_id": COMPANY_ID,
            "as_of_date": date(2026, 1, 1),
            "kpis": {},
            "period_close_status": [],
        }
        monkeypatch.setattr(
            accounting_adapter_mod, "build_kpi_service", lambda db: kpis
        )
        result = AccountingAdapter().run(
            MagicMock(),
            COMPANY_ID,
            "accounting.kpis",
            AccountingKpiFilter(as_of_date=date(2026, 1, 1)),
            page=1,
            page_size=20,
            sort=None,
            comparison=None,
        )
        assert isinstance(result, AggregateReportResult)

    def test_bank_cash_book_bank_branch_returns_paginated(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        bank = MagicMock()
        bank.count_bank_transactions.return_value = 0
        bank.get_bank_transactions_page.return_value = []
        monkeypatch.setattr(
            accounting_adapter_mod, "build_bank_account_service", lambda db: bank
        )
        result = AccountingAdapter().run(
            MagicMock(),
            COMPANY_ID,
            "accounting.bank_cash_book",
            BankCashBookFilter(
                account_type="bank",
                account_id=uuid.uuid4(),
                from_date=date(2026, 1, 1),
                to_date=date(2026, 1, 31),
            ),
            page=1,
            page_size=20,
            sort=None,
            comparison=None,
        )
        assert isinstance(result, PaginatedReportResult)

    def test_unregistered_key_raises_not_found(self) -> None:
        from modules.reports.exceptions import ReportNotFoundError

        with pytest.raises(ReportNotFoundError):
            AccountingAdapter().run(
                MagicMock(),
                COMPANY_ID,
                "accounting.not_a_real_key",
                ProfitLossFilter(
                    period_from=date(2026, 1, 1), period_to=date(2026, 1, 1)
                ),
                page=1,
                page_size=20,
                sort=None,
                comparison=None,
            )
