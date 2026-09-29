"""T196 — bounded retrieval per export category (plan.md §21.2/§21.5):

- **Category A**: ``count_export_rows()`` is called exactly once, before
  any batch is pulled; over-limit never touches ``iter_export_rows()``.
- **Category B** (Installments ``due_overdue``/``aging``): the count-time
  and iterate-time population fetches are independent calls — iteration
  never reuses the count-time result.
- **Category B-cursor** (GL): a cursor sequence that could yield
  ``limit+2`` rows stops being pulled the instant ``limit+1`` is observed.

Pure unit test: the authorization preamble is stubbed (it has its own
tests, T127) and the ``Session`` is a mock, so only the export service's
own retrieval ordering is under test.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any
from unittest.mock import MagicMock
from uuid import UUID, uuid4

import pytest
from pydantic import BaseModel

import modules.reports.registry.load_all  # noqa: F401 — full catalog
from modules.reports import constants
from modules.reports.exceptions import ExportTooLargeError
from modules.reports.registry.definitions import (
    REPORT_REGISTRY,
    ExportFormat,
    ReportDomain,
)
from modules.reports.schemas.accounting import GlFilter
from modules.reports.schemas.common import ComparisonRequest
from modules.reports.schemas.installments import DueOverdueFilter
from modules.reports.schemas.sales import SalesByCustomerFilter, SalesByCustomerRow
from modules.reports.services.adapters import installments_adapter as inst_mod
from modules.reports.services.adapters.base import ADAPTER_REGISTRY, BaseReportResult
from modules.reports.services.adapters.installments_adapter import InstallmentsAdapter
from modules.reports.services.execution_service import ReportExecutionService
from modules.reports.services.export_service import (
    ExportCategory,
    ReportExportService,
    export_category,
)

COMPANY_ID = uuid4()
USER_ID = uuid4()


def _row(n: int) -> SalesByCustomerRow:
    return SalesByCustomerRow(
        customer_id=str(n), customer_name=f"c{n}", invoice_count=1, revenue=n
    )


class FakeAdapter:
    """Records every seam call in order; yields ``pages`` lazily so page
    fetches are observable one at a time."""

    def __init__(self, count: int, pages: list[list[BaseModel]]) -> None:
        self.count = count
        self.pages = pages
        self.events: list[str] = []

    def run(
        self,
        db: Any,
        company_id: UUID,
        report_key: str,
        filters: BaseModel,
        page: int,
        page_size: int,
        sort: str | None,
        comparison: ComparisonRequest | None,
    ) -> BaseReportResult:
        raise AssertionError("list exports never call run()")

    def count_export_rows(
        self, db: Any, company_id: UUID, report_key: str, filters: BaseModel
    ) -> int:
        self.events.append("count")
        return self.count

    def iter_export_rows(
        self,
        db: Any,
        company_id: UUID,
        report_key: str,
        filters: BaseModel,
        sort: str | None,
        batch_size: int,
    ) -> Iterator[list[BaseModel]]:
        self.events.append("iter")
        for index, page in enumerate(self.pages):
            self.events.append(f"page{index + 1}")
            yield page

    def export_row_model(self, report_key: str) -> type[BaseModel]:
        return SalesByCustomerRow


def _export(
    monkeypatch: pytest.MonkeyPatch,
    report_key: str,
    filters: BaseModel,
    adapter: FakeAdapter,
    domain: ReportDomain,
) -> bytes:
    definition = REPORT_REGISTRY[report_key]

    def fake_preamble(
        self: ReportExecutionService, db: Any, **kwargs: object
    ) -> tuple[object, BaseModel, bool]:
        assert kwargs["permission_kind"] == "export"
        return definition, filters, False

    monkeypatch.setattr(
        ReportExecutionService, "_authorize_and_validate", fake_preamble
    )
    monkeypatch.setitem(ADAPTER_REGISTRY, domain, adapter)
    result = ReportExportService().export(
        MagicMock(),
        company_id=COMPANY_ID,
        user_id=USER_ID,
        report_key=report_key,
        raw_filters={},
        sort=None,
        export_format=ExportFormat.CSV,
    )
    return result.content


def test_category_classification_matches_final_matrix() -> None:
    assert (
        export_category(REPORT_REGISTRY["sales.by_customer"])
        is ExportCategory.BOUNDED_SQL
    )
    assert (
        export_category(REPORT_REGISTRY["accounting.ar_aging"])
        is ExportCategory.BOUNDED_SQL
    )
    assert (
        export_category(REPORT_REGISTRY["installments.due_overdue"])
        is ExportCategory.BOUNDED_POPULATION
    )
    assert (
        export_category(REPORT_REGISTRY["installments.aging"])
        is ExportCategory.BOUNDED_POPULATION
    )
    assert (
        export_category(REPORT_REGISTRY["accounting.gl"])
        is ExportCategory.CURSOR_LIMIT_PLUS_ONE
    )
    assert (
        export_category(REPORT_REGISTRY["inventory.valuation"])
        is ExportCategory.AGGREGATE
    )


def test_category_a_counts_exactly_once_before_any_batch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter = FakeAdapter(count=3, pages=[[_row(1), _row(2)], [_row(3)]])
    _export(
        monkeypatch,
        "sales.by_customer",
        SalesByCustomerFilter(),
        adapter,
        ReportDomain.SALES,
    )
    assert adapter.events == ["count", "iter", "page1", "page2"]


def test_category_a_over_limit_never_iterates(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(constants, "EXPORT_ROW_LIMIT_CSV", 2)
    adapter = FakeAdapter(count=3, pages=[[_row(1), _row(2)], [_row(3)]])
    with pytest.raises(ExportTooLargeError):
        _export(
            monkeypatch,
            "sales.by_customer",
            SalesByCustomerFilter(),
            adapter,
            ReportDomain.SALES,
        )
    assert adapter.events == ["count"]


def test_category_b_cursor_stops_at_limit_plus_one(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    limit = 4
    monkeypatch.setattr(constants, "EXPORT_ROW_LIMIT_CSV", limit)
    # Three 2-row pages = limit+2 rows available; the limit+1th row is on
    # page 3, the 5th page would never exist — but pages 1..3 only must be
    # pulled, and nothing after.
    pages: list[list[BaseModel]] = [[_row(i), _row(i + 1)] for i in (1, 3, 5)]
    pages.append([_row(7)])
    adapter = FakeAdapter(count=-1, pages=pages)
    with pytest.raises(ExportTooLargeError):
        _export(
            monkeypatch, "accounting.gl", GlFilter(), adapter, ReportDomain.ACCOUNTING
        )
    assert "count" not in adapter.events
    assert adapter.events == ["iter", "page1", "page2", "page3"]


def test_category_b_cursor_within_limit_uses_every_batch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(constants, "EXPORT_ROW_LIMIT_CSV", 4)
    pages: list[list[BaseModel]] = [[_row(1), _row(2)], [_row(3), _row(4)]]
    adapter = FakeAdapter(count=-1, pages=pages)
    content = _export(
        monkeypatch, "accounting.gl", GlFilter(), adapter, ReportDomain.ACCOUNTING
    )
    assert adapter.events == ["iter", "page1", "page2"]
    assert content.decode("utf-8-sig").count("\n") == 1 + 4


def test_category_b_count_and_iterate_fetch_population_independently(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Real ``InstallmentsAdapter`` over a mocked reporting service: the
    count call and the iteration each perform their own fetch — the
    count-time rows are never reused for the file. The 50,000 population
    cap is applied inside ``get_due_overdue_report()`` itself."""
    fetches: list[tuple[str, int, int]] = []
    rows = [{"line_id": f"d{i}", "amount": "1.00"} for i in range(3)] + [
        {"line_id": f"o{i}", "amount": "2.00"} for i in range(2)
    ]
    service = MagicMock()

    def get_due_overdue_report(
        company_id: UUID, *, skip: int, limit: int
    ) -> tuple[list[dict[str, str]], int]:
        fetches.append(("due_overdue", skip, limit))
        return rows[skip : skip + limit], len(rows)

    service.get_due_overdue_report.side_effect = get_due_overdue_report
    monkeypatch.setattr(inst_mod, "_build_reporting_service", lambda db: service)

    adapter = InstallmentsAdapter()
    filters = DueOverdueFilter()
    count = adapter.count_export_rows(
        MagicMock(), COMPANY_ID, "installments.due_overdue", filters
    )
    count_fetches = list(fetches)
    batches = list(
        adapter.iter_export_rows(
            MagicMock(), COMPANY_ID, "installments.due_overdue", filters, None, 1_000
        )
    )

    assert count == 5
    assert count_fetches == [("due_overdue", 0, 1)]
    assert fetches[len(count_fetches) :] == [("due_overdue", 0, 1_000)]
    assert sum(len(b) for b in batches) == 5
