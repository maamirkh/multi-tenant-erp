"""T213 — export memory/wall-clock benchmark (evidence, **not** a pass/fail
gate): CSV and XLSX at 10K/25K/50K rows through the real
``ReportExportService`` + writers, with a lazily-batched fake adapter
(so the numbers measure the export path itself, not a database).

Opt-in — it takes tens of seconds::

    REPORTS_EXPORT_BENCHMARK=1 pytest -s tests/unit/modules/reports/test_export_memory_benchmark.py

The recorded results that finalized ``EXPORT_ROW_LIMIT_CSV``/
``EXPORT_ROW_LIMIT_XLSX``/``EXPORT_BATCH_SIZE`` (T214) live in tasks.md's
T214 completion note.
"""

from __future__ import annotations

import os
import time
import tracemalloc
from collections.abc import Iterator
from decimal import Decimal
from typing import Any
from unittest.mock import MagicMock
from uuid import UUID, uuid4

import pytest
from pydantic import BaseModel

import modules.reports.registry.load_all  # noqa: F401 — full catalog
from modules.reports import constants
from modules.reports.registry.definitions import (
    REPORT_REGISTRY,
    ExportFormat,
    ReportDomain,
)
from modules.reports.schemas.common import ComparisonRequest
from modules.reports.schemas.sales import SalesByCustomerFilter, SalesByCustomerRow
from modules.reports.services.adapters.base import ADAPTER_REGISTRY, BaseReportResult
from modules.reports.services.execution_service import ReportExecutionService
from modules.reports.services.export_service import ReportExportService

pytestmark = pytest.mark.skipif(
    os.environ.get("REPORTS_EXPORT_BENCHMARK") != "1",
    reason="benchmark evidence task (T213) — opt-in via REPORTS_EXPORT_BENCHMARK=1",
)

_SIZES = (10_000, 25_000, 50_000)


class _SyntheticAdapter:
    def __init__(self, rows: int) -> None:
        self.rows = rows

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
        raise AssertionError("not used")

    def count_export_rows(
        self, db: Any, company_id: UUID, report_key: str, filters: BaseModel
    ) -> int:
        return self.rows

    def iter_export_rows(
        self,
        db: Any,
        company_id: UUID,
        report_key: str,
        filters: BaseModel,
        sort: str | None,
        batch_size: int,
    ) -> Iterator[list[BaseModel]]:
        for start in range(0, self.rows, batch_size):
            stop = min(start + batch_size, self.rows)
            yield [
                SalesByCustomerRow(
                    customer_id=str(uuid4()),
                    customer_name=f"Customer number {n} Trading Company Ltd",
                    invoice_count=n % 97,
                    revenue=Decimal(n) + Decimal("0.45"),
                )
                for n in range(start, stop)
            ]

    def export_row_model(self, report_key: str) -> type[BaseModel]:
        return SalesByCustomerRow


@pytest.mark.parametrize("export_format", [ExportFormat.CSV, ExportFormat.XLSX])
@pytest.mark.parametrize("rows", _SIZES)
def test_export_benchmark(
    monkeypatch: pytest.MonkeyPatch, rows: int, export_format: ExportFormat
) -> None:
    definition = REPORT_REGISTRY["sales.by_customer"]

    def fake_preamble(
        self: ReportExecutionService, db: Any, **kwargs: object
    ) -> tuple[object, BaseModel, bool]:
        return definition, SalesByCustomerFilter(), False

    monkeypatch.setattr(
        ReportExecutionService, "_authorize_and_validate", fake_preamble
    )
    monkeypatch.setitem(ADAPTER_REGISTRY, ReportDomain.SALES, _SyntheticAdapter(rows))
    # Measure beyond the configured ceilings too — that is the point.
    monkeypatch.setattr(constants, "EXPORT_ROW_LIMIT_CSV", 10**9)
    monkeypatch.setattr(constants, "EXPORT_ROW_LIMIT_XLSX", 10**9)

    tracemalloc.start()
    started = time.perf_counter()
    result = ReportExportService().export(
        MagicMock(),
        company_id=uuid4(),
        user_id=uuid4(),
        report_key="sales.by_customer",
        raw_filters={},
        sort=None,
        export_format=export_format,
    )
    elapsed = time.perf_counter() - started
    _current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    assert result.row_count == rows
    print(
        f"\nBENCH format={export_format.value} rows={rows} "
        f"batch={constants.EXPORT_BATCH_SIZE} "
        f"file_mb={len(result.content) / 1_048_576:.2f} "
        f"peak_mb={peak / 1_048_576:.1f} seconds={elapsed:.2f}"
    )
