"""``inventory.valuation`` never reports a cross-currency grand total
(FR-RPT-152, Phase 12 T300)."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from modules.reports.schemas.inventory import (
    InventoryValuationFilter,
    InventoryValuationResponse,
)
from modules.reports.services.adapters import inventory_adapter as inv_mod
from modules.reports.services.adapters.base import AggregateReportResult
from modules.reports.services.adapters.inventory_adapter import InventoryAdapter


def _valuation(totals: list[tuple[str | None, str]]) -> dict[str, Any]:
    return {
        "rows": [],
        "grand_total_value": sum((Decimal(v) for _, v in totals), Decimal("0")),
        "currency_code": totals[-1][0] if totals else None,
        "grand_totals_by_currency": [
            {"currency_code": code, "total_value": Decimal(value)}
            for code, value in totals
        ],
        "as_of": datetime(2026, 9, 30, tzinfo=UTC),
    }


def _run(monkeypatch: pytest.MonkeyPatch, data: dict[str, Any]) -> Any:
    service = MagicMock()
    service.inventory_valuation.return_value = data
    monkeypatch.setattr(inv_mod, "get_report_service", lambda db: service)
    result = InventoryAdapter().run(
        MagicMock(),
        uuid4(),
        "inventory.valuation",
        InventoryValuationFilter(),
        1,
        1,
        None,
        None,
    )
    assert isinstance(result, AggregateReportResult)
    assert isinstance(result.data, InventoryValuationResponse)
    return result.data


def test_several_currencies_have_no_single_total(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    data = _run(monkeypatch, _valuation([("PKR", "5000.00"), ("USD", "100.00")]))
    assert data.grand_total_value is None
    assert data.currency_code is None
    assert {t.currency_code: t.amount for t in data.grand_totals_by_currency} == {
        "PKR": Decimal("5000.00"),
        "USD": Decimal("100.00"),
    }


def test_one_currency_keeps_its_single_total(monkeypatch: pytest.MonkeyPatch) -> None:
    data = _run(monkeypatch, _valuation([("USD", "100.00")]))
    assert data.grand_total_value == Decimal("100.00")
    assert data.currency_code == "USD"


def test_no_stock_is_an_empty_breakdown(monkeypatch: pytest.MonkeyPatch) -> None:
    data = _run(monkeypatch, _valuation([]))
    assert data.grand_totals_by_currency == []
    assert data.grand_total_value == Decimal("0")  # a real zero, not "unknown"
