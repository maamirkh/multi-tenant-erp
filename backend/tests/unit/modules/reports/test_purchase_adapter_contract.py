"""T081 — Contract test (mocked services): typed stability for all 7
Purchase report keys; for all six list-shaped reports, ``total`` comes
from the matching count-sibling call, not ``len(rows)``."""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock

import pytest
from pydantic import BaseModel

from modules.reports.schemas.purchase import (
    OpenCommitmentsFilter,
    PendingDeliveriesFilter,
    PurchaseBySupplierFilter,
    PurchaseKpiFilter,
    PurchaseSummaryFilter,
    SupplierPerformanceFilter,
    VendorReturnsFilter,
)
from modules.reports.services.adapters import purchase_adapter as purchase_adapter_mod
from modules.reports.services.adapters.base import (
    AggregateReportResult,
    PaginatedReportResult,
)
from modules.reports.services.adapters.purchase_adapter import PurchaseAdapter

COMPANY_ID = uuid.uuid4()


def _run(filters: BaseModel, report_key: str) -> object:
    return PurchaseAdapter().run(
        MagicMock(),
        COMPANY_ID,
        report_key,
        filters,
        page=1,
        page_size=20,
        sort=None,
        comparison=None,
    )


_MINIMAL_ROW_BY_KEY: dict[str, dict[str, object]] = {
    "purchase.summary": {
        "po_id": "po-1",
        "po_number": "PO-1",
        "status": "APPROVED",
        "currency_code": "USD",
        "subtotal": "100.00",
        "total_charges": "0",
        "total_discounts": "0",
        "tax_amount": "0",
        "total": "100.00",
    },
    "purchase.by_supplier": {
        "gr_count": 1,
        "total_spend": "100.00",
        "total_subtotal": "100.00",
        "total_charges": "0",
        "total_discounts": "0",
    },
    "purchase.supplier_performance": {
        "supplier_id": "sup-1",
        "total_grs": 1,
        "on_time_rate": 100.0,
        "fill_rate": 100.0,
        "rejection_rate": 0.0,
        "composite_rating": 100.0,
    },
    "purchase.open_commitments": {
        "po_line_id": "line-1",
        "po_number": "PO-1",
        "currency_code": "USD",
        "product_description": "Widget",
        "quantity_ordered": "10",
        "quantity_received": "0",
        "open_quantity": "10",
        "unit_cost": "5.00",
        "open_value": "50.00",
    },
    "purchase.pending_deliveries": {
        "po_id": "po-1",
        "po_number": "PO-1",
        "status": "APPROVED",
        "total": "100.00",
        "currency_code": "USD",
        "expected_delivery_date": "2026-01-01",
        "days_overdue": 5,
    },
    "purchase.vendor_returns": {
        "rma_id": "rma-1",
        "rma_number": "RMA-1",
        "status": "DRAFT",
    },
}


@pytest.mark.parametrize(
    "report_key,filters,list_method,count_method",
    [
        (
            "purchase.summary",
            PurchaseSummaryFilter(),
            "purchase_order_summary",
            "count_purchase_order_summary",
        ),
        (
            "purchase.by_supplier",
            PurchaseBySupplierFilter(),
            "purchase_by_supplier",
            "count_purchase_by_supplier",
        ),
        (
            "purchase.supplier_performance",
            SupplierPerformanceFilter(),
            "supplier_performance",
            "count_supplier_performance",
        ),
        (
            "purchase.open_commitments",
            OpenCommitmentsFilter(),
            "open_purchase_commitments",
            "count_open_purchase_commitments",
        ),
        (
            "purchase.pending_deliveries",
            PendingDeliveriesFilter(),
            "overdue_deliveries",
            "count_overdue_deliveries",
        ),
        (
            "purchase.vendor_returns",
            VendorReturnsFilter(),
            "vendor_return_report",
            "count_vendor_returns",
        ),
    ],
)
def test_total_is_real_count_not_len_rows(
    monkeypatch: pytest.MonkeyPatch,
    report_key: str,
    filters: BaseModel,
    list_method: str,
    count_method: str,
) -> None:
    reports = MagicMock()
    getattr(reports, list_method).return_value = [_MINIMAL_ROW_BY_KEY[report_key]]
    getattr(reports, count_method).return_value = 999  # far from len(rows) == 1
    monkeypatch.setattr(purchase_adapter_mod, "get_report_service", lambda db: reports)

    result = _run(filters, report_key)
    assert isinstance(result, PaginatedReportResult)
    assert result.total == 999
    assert len(result.items) == 1


def test_kpis_returns_aggregate(monkeypatch: pytest.MonkeyPatch) -> None:
    kpis = MagicMock()
    kpis.get_all_kpis.return_value = {"kpi_01_purchase_cycle_time_days": 5}
    monkeypatch.setattr(purchase_adapter_mod, "get_kpi_service", lambda db: kpis)

    result = _run(PurchaseKpiFilter(), "purchase.kpis")
    assert isinstance(result, AggregateReportResult)
