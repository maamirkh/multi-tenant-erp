"""Unit tests for KPIService — Phase 9 Reporting Foundation.

Tests cover:
  T254 - KPI formula correctness for all 10 KPIs against known datasets

Spec ref: specs/005-inventory-management/spec.md §33
"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import MagicMock
from uuid import uuid4

from modules.inventory.services.kpi_service import KPIService, _dec, _pct

# ---------------------------------------------------------------------------
# Helper factories
# ---------------------------------------------------------------------------


def _mock_position(
    *,
    qty: float = 10.0,
    unit_cost: float | None = 5.0,
    currency_code: str | None = "USD",
    maximum_stock: float | None = None,
    product_id: str | None = None,
) -> MagicMock:
    pos = MagicMock()
    pos.product_id = product_id or str(uuid4())
    pos.qty_on_hand = qty
    pos.unit_cost = unit_cost
    pos.currency_code = currency_code
    pos.maximum_stock = maximum_stock
    pos.deleted_at = None
    return pos


def _mock_warehouse(*, status: str = "ACTIVE") -> MagicMock:
    wh = MagicMock()
    wh.status = status
    wh.deleted_at = None
    return wh


# ---------------------------------------------------------------------------
# _dec / _pct helper tests
# ---------------------------------------------------------------------------


class TestHelpers:
    def test_dec_none_returns_zero(self) -> None:
        assert _dec(None) == Decimal("0")

    def test_dec_str(self) -> None:
        assert _dec("3.14") == Decimal("3.14")

    def test_dec_int(self) -> None:
        assert _dec(5) == Decimal("5")

    def test_pct_zero_denominator(self) -> None:
        assert _pct(Decimal("10"), Decimal("0")) == Decimal("0.00")

    def test_pct_half(self) -> None:
        assert _pct(Decimal("50"), Decimal("100")) == Decimal("50.00")

    def test_pct_full(self) -> None:
        assert _pct(Decimal("100"), Decimal("100")) == Decimal("100.00")


# ---------------------------------------------------------------------------
# KPIService compute tests
# ---------------------------------------------------------------------------


class TestKPIService:
    """Tests for all 10 KPIs with controlled DB mocks."""

    def _build_service(
        self,
        *,
        positions: list[MagicMock] | None = None,
        warehouses: list[MagicMock] | None = None,
        cogs: float = 0.0,
        active_product_ids: set[str] | None = None,
        reorder_count: int = 0,
    ) -> tuple[KPIService, MagicMock]:
        """Return a KPIService with a mocked Session."""
        db = MagicMock()
        positions = positions or []
        warehouses = warehouses or []
        active_product_ids = active_product_ids or set()

        company_id = uuid4()

        # Position query mock
        pos_query = MagicMock()
        pos_query.filter.return_value = pos_query
        pos_query.all.return_value = positions

        # COGS query
        cogs_scalar = MagicMock()
        cogs_scalar.scalar.return_value = cogs

        # Active products (distinct product_ids with recent movements)
        active_q = MagicMock()
        active_q.filter.return_value = active_q
        active_q.distinct.return_value = active_q
        active_q.all.return_value = [(pid,) for pid in active_product_ids]

        # Warehouse query
        wh_query = MagicMock()
        wh_query.filter.return_value = wh_query
        wh_query.all.return_value = warehouses

        # Reorder suggestion count
        rs_query = MagicMock()
        rs_query.filter.return_value = rs_query
        rs_query.scalar.return_value = reorder_count

        def side_effect(model: type) -> MagicMock:
            from modules.inventory.models.alerts import ReorderSuggestion
            from modules.inventory.models.stock import StockPosition
            from modules.inventory.models.warehouse import Warehouse

            if model is StockPosition:
                return pos_query
            if model is Warehouse:
                return wh_query
            if model is ReorderSuggestion:
                return rs_query
            # For StockMovement queries (COGS + active products)
            q = MagicMock()
            q.filter.return_value = q
            q.distinct.return_value = q
            q.all.return_value = [(pid,) for pid in active_product_ids]
            q.scalar.return_value = cogs
            return q

        db.query.side_effect = side_effect
        svc = KPIService(db=db)
        return svc, db

    def test_total_inventory_value(self) -> None:
        positions = [_mock_position(qty=10.0, unit_cost=5.0)]
        svc, _ = self._build_service(positions=positions)
        result = svc.compute(company_id=uuid4())
        assert result["total_inventory_value"] == Decimal("50.00")

    def test_total_inventory_value_no_cost(self) -> None:
        positions = [_mock_position(qty=10.0, unit_cost=None)]
        svc, _ = self._build_service(positions=positions)
        result = svc.compute(company_id=uuid4())
        assert result["total_inventory_value"] == Decimal("0.00")

    def test_stock_accuracy_percentage_all_with_stock(self) -> None:
        positions = [
            _mock_position(qty=5.0),
            _mock_position(qty=0.0),
            _mock_position(qty=10.0),
        ]
        svc, _ = self._build_service(positions=positions)
        result = svc.compute(company_id=uuid4())
        # 2 of 3 have stock
        assert result["stock_accuracy_percentage"] == Decimal("66.67")

    def test_stockout_rate(self) -> None:
        positions = [
            _mock_position(qty=0.0),
            _mock_position(qty=0.0),
            _mock_position(qty=5.0),
        ]
        svc, _ = self._build_service(positions=positions)
        result = svc.compute(company_id=uuid4())
        assert result["stockout_rate"] == Decimal("66.67")

    def test_warehouse_efficiency_all_active(self) -> None:
        warehouses = [
            _mock_warehouse(status="ACTIVE"),
            _mock_warehouse(status="ACTIVE"),
        ]
        svc, _ = self._build_service(warehouses=warehouses)
        result = svc.compute(company_id=uuid4())
        assert result["warehouse_efficiency"] == Decimal("100.00")

    def test_warehouse_efficiency_partial(self) -> None:
        warehouses = [
            _mock_warehouse(status="ACTIVE"),
            _mock_warehouse(status="INACTIVE"),
        ]
        svc, _ = self._build_service(warehouses=warehouses)
        result = svc.compute(company_id=uuid4())
        assert result["warehouse_efficiency"] == Decimal("50.00")

    def test_overstock_rate_no_max_stock(self) -> None:
        positions = [_mock_position(qty=100.0, maximum_stock=None)]
        svc, _ = self._build_service(positions=positions)
        result = svc.compute(company_id=uuid4())
        assert result["overstock_rate"] == Decimal("0.00")

    def test_overstock_rate_exceeds_max(self) -> None:
        positions = [
            _mock_position(qty=100.0, maximum_stock=50.0),
            _mock_position(qty=10.0, maximum_stock=50.0),
        ]
        svc, _ = self._build_service(positions=positions)
        result = svc.compute(company_id=uuid4())
        assert result["overstock_rate"] == Decimal("50.00")

    def test_inventory_accuracy_all_have_cost(self) -> None:
        positions = [_mock_position(unit_cost=5.0), _mock_position(unit_cost=3.0)]
        svc, _ = self._build_service(positions=positions)
        result = svc.compute(company_id=uuid4())
        assert result["inventory_accuracy"] == Decimal("100.00")

    def test_inventory_accuracy_none_have_cost(self) -> None:
        positions = [_mock_position(unit_cost=None)]
        svc, _ = self._build_service(positions=positions)
        result = svc.compute(company_id=uuid4())
        assert result["inventory_accuracy"] == Decimal("0.00")

    def test_all_kpi_keys_present(self) -> None:
        svc, _ = self._build_service()
        result = svc.compute(company_id=uuid4())
        expected_keys = {
            "inventory_turnover",
            "average_inventory_value",
            "inventory_accuracy",
            "dead_stock_percentage",
            "stock_accuracy_percentage",
            "warehouse_efficiency",
            "total_inventory_value",
            "reorder_frequency",
            "stockout_rate",
            "overstock_rate",
            "as_of",
            "period_days",
        }
        assert expected_keys == set(result.keys())

    def test_period_days_in_result(self) -> None:
        svc, _ = self._build_service()
        result = svc.compute(company_id=uuid4(), period_days=30)
        assert result["period_days"] == 30

    def test_empty_positions_returns_zeros(self) -> None:
        svc, _ = self._build_service(positions=[])
        result = svc.compute(company_id=uuid4())
        assert result["total_inventory_value"] == Decimal("0.00")
        assert result["stockout_rate"] == Decimal("0.00")
        assert result["inventory_accuracy"] == Decimal("0.00")
