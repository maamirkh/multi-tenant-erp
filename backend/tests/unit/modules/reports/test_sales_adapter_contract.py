"""T070 — Contract test (mocked services): typed stability;
``PaginatedReportResult.total`` equals the mocked ``ReportResponse.total``
exactly (proving the real-COUNT path, not a ``len(rows)`` substitute)."""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock

import pytest

from modules.reports.schemas.sales import SalesSummaryFilter
from modules.reports.services.adapters import sales_adapter as sales_adapter_mod
from modules.reports.services.adapters.base import PaginatedReportResult
from modules.reports.services.adapters.sales_adapter import SalesAdapter


def test_total_is_real_count_not_len_rows(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_response = MagicMock()
    fake_response.rows = [
        {
            "date": None,
            "invoice_count": 1,
            "revenue": "10.00",
            "total_discount": "0",
        }
    ]
    fake_response.total = 999  # deliberately far from len(rows) == 1

    reports = MagicMock()
    reports.run_report.return_value = fake_response
    monkeypatch.setattr(sales_adapter_mod, "get_report_service", lambda db: reports)

    result = SalesAdapter().run(
        MagicMock(),
        uuid.uuid4(),
        "sales.summary",
        SalesSummaryFilter(),
        page=1,
        page_size=20,
        sort=None,
        comparison=None,
    )
    assert isinstance(result, PaginatedReportResult)
    assert result.total == 999
    assert len(result.items) == 1
