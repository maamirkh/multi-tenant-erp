"""T094 — Contract test (mocked services): typed stability for all 8
Inventory report keys; for all five list-shaped reports, ``total`` comes
from the matching count-sibling call, not ``len(rows)``; ``inventory.valuation``
always has ``valuation_basis`` set to ``"operational_wac"``."""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock

import pytest
from pydantic import BaseModel

from modules.reports.schemas.inventory import (
    DeadStockFilter,
    InventoryKpiFilter,
    InventorySummaryFilter,
    InventoryValuationFilter,
    LowStockFilter,
    MovementVelocityFilter,
    StockAgingFilter,
    StockPositionFilter,
)
from modules.reports.services.adapters import inventory_adapter as inventory_adapter_mod
from modules.reports.services.adapters.base import (
    AggregateReportResult,
    PaginatedReportResult,
)
from modules.reports.services.adapters.inventory_adapter import InventoryAdapter

COMPANY_ID = uuid.uuid4()


def _run(filters: BaseModel, report_key: str) -> object:
    return InventoryAdapter().run(
        MagicMock(),
        COMPANY_ID,
        report_key,
        filters,
        page=1,
        page_size=20,
        sort=None,
        comparison=None,
    )


@pytest.mark.parametrize(
    "report_key,filters,list_method,count_method,list_returns_dict",
    [
        (
            "inventory.dead_stock",
            DeadStockFilter(),
            "dead_stock",
            "count_dead_stock",
            True,
        ),
        (
            "inventory.movement_velocity",
            MovementVelocityFilter(),
            "movement_velocity",
            "count_movement_velocity",
            True,
        ),
        (
            "inventory.stock_aging",
            StockAgingFilter(),
            "stock_aging",
            "count_stock_aging",
            True,
        ),
    ],
)
def test_total_is_real_count_not_len_rows(
    monkeypatch: pytest.MonkeyPatch,
    report_key: str,
    filters: BaseModel,
    list_method: str,
    count_method: str,
    list_returns_dict: bool,
) -> None:
    reports = MagicMock()
    getattr(reports, list_method).return_value = {"rows": [{"product_id": "p-1"}]}
    getattr(reports, count_method).return_value = 999  # far from len(rows) == 1
    monkeypatch.setattr(inventory_adapter_mod, "get_report_service", lambda db: reports)

    result = _run(filters, report_key)
    assert isinstance(result, PaginatedReportResult)
    assert result.total == 999
    assert len(result.items) == 1


def test_stock_position_total_is_real_count_not_len_rows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``inventory.stock_position`` is backed by ``stock_ledger`` (its own
    genuine SQL count), not a T087 count-sibling."""
    reports = MagicMock()
    reports.stock_ledger.return_value = {
        "rows": [{"movement_id": "m-1"}],
        "total_rows": 999,
    }
    monkeypatch.setattr(inventory_adapter_mod, "get_report_service", lambda db: reports)

    result = _run(StockPositionFilter(), "inventory.stock_position")
    assert isinstance(result, PaginatedReportResult)
    assert result.total == 999
    assert len(result.items) == 1


def test_low_stock_total_is_real_count_not_len_rows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    alert = MagicMock()
    alert.id = uuid.uuid4()
    alert.product_id = "p-1"
    alert.variant_id = None
    alert.warehouse_id = "w-1"
    alert.alert_type = "LOW_STOCK"
    alert.status = "OPEN"
    alert.current_quantity = 1
    alert.threshold_quantity = 2
    alert.acknowledged_at = None
    alert.resolved_at = None
    alert.created_at = None

    alert_repo = MagicMock()
    alert_repo.list_for_company.return_value = [alert]
    alert_repo.count_for_company.return_value = 999
    monkeypatch.setattr(inventory_adapter_mod, "get_alert_repo", lambda db: alert_repo)

    result = _run(LowStockFilter(), "inventory.low_stock")
    assert isinstance(result, PaginatedReportResult)
    assert result.total == 999
    assert len(result.items) == 1


def test_summary_returns_aggregate(monkeypatch: pytest.MonkeyPatch) -> None:
    import datetime

    reports = MagicMock()
    reports.inventory_summary.return_value = {
        "rows": [],
        "grand_total_value": "0",
        "as_of": datetime.datetime.now(datetime.UTC),
    }
    monkeypatch.setattr(inventory_adapter_mod, "get_report_service", lambda db: reports)

    result = _run(InventorySummaryFilter(), "inventory.summary")
    assert isinstance(result, AggregateReportResult)


def test_valuation_always_has_operational_wac_basis(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import datetime

    reports = MagicMock()
    reports.inventory_valuation.return_value = {
        "rows": [],
        "grand_total_value": "0",
        "currency_code": "USD",
        "as_of": datetime.datetime.now(datetime.UTC),
    }
    monkeypatch.setattr(inventory_adapter_mod, "get_report_service", lambda db: reports)

    result = _run(InventoryValuationFilter(), "inventory.valuation")
    assert isinstance(result, AggregateReportResult)
    assert result.data.valuation_basis == "operational_wac"


def test_kpis_returns_aggregate(monkeypatch: pytest.MonkeyPatch) -> None:
    import datetime

    kpis = MagicMock()
    kpis.compute.return_value = {
        "inventory_turnover": "1.5",
        "as_of": datetime.datetime.now(datetime.UTC),
        "period_days": 90,
    }
    monkeypatch.setattr(inventory_adapter_mod, "get_kpi_service", lambda db: kpis)

    result = _run(InventoryKpiFilter(), "inventory.kpis")
    assert isinstance(result, AggregateReportResult)
