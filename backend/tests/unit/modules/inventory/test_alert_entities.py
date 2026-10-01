"""Unit tests for alert entity business rules — Phase 8.

Tests cover:
  - AlertEvaluationService threshold logic
  - Alert deduplication (no duplicate OPEN alert for same product/warehouse/type)
  - Auto-resolve when stock rises above threshold
  - ReorderSuggestion creation on LOW_STOCK when rule exists
  - Feature flag gating of OVERSTOCK alerts
  - Event publication on alert creation

Spec ref: specs/005-inventory-management/spec.md §15 / FR-IO-016
"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import MagicMock
from uuid import uuid4

from modules.inventory.models.alerts import (
    LowStockAlert,
    ReorderRule,
    ReorderSuggestion,
)
from modules.inventory.models.stock import StockPosition
from modules.inventory.services.alert_service import AlertEvaluationService

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_position(
    *,
    qty: Decimal = Decimal("10"),
    reorder_level: Decimal = Decimal("5"),
    safety_stock: Decimal = Decimal("2"),
    maximum_stock: Decimal | None = None,
) -> StockPosition:
    pos = MagicMock(spec=StockPosition)
    pos.product_id = str(uuid4())
    pos.warehouse_id = str(uuid4())
    pos.variant_id = None
    pos.qty_on_hand = qty
    pos.reorder_level = reorder_level
    pos.safety_stock = safety_stock
    pos.maximum_stock = maximum_stock
    return pos


def _make_service(
    *,
    existing_alert: LowStockAlert | None = None,
    rules: list[ReorderRule] | None = None,
    flag_enabled: bool = False,
) -> tuple[AlertEvaluationService, MagicMock]:
    """Build AlertEvaluationService with mocked repos."""
    db = MagicMock()
    alert_repo = MagicMock()
    alert_repo.get_open_alert.return_value = existing_alert
    rule_repo = MagicMock()
    rule_repo.get_for_product.return_value = rules or []
    suggestion_repo = MagicMock()
    flag_repo = MagicMock()

    svc = AlertEvaluationService(
        db=db,
        alert_repo=alert_repo,
        rule_repo=rule_repo,
        suggestion_repo=suggestion_repo,
        flag_repo=flag_repo,
    )
    # Patch feature-flag lookup to control OVERSTOCK gating
    svc._is_flag_enabled = MagicMock(return_value=flag_enabled)
    return svc, db


# ---------------------------------------------------------------------------
# Threshold detection tests
# ---------------------------------------------------------------------------


class TestThresholdDetection:
    """Verify that the correct alert type is triggered for each stock scenario."""

    def test_out_of_stock_zero_qty(self) -> None:
        pos = _make_position(qty=Decimal("0"))
        svc, db = _make_service()
        company_id = uuid4()
        svc.evaluate(company_id=company_id, position=pos)
        # Should create an OUT_OF_STOCK alert
        calls = db.add.call_args_list
        created_alerts = [
            c.args[0] for c in calls if isinstance(c.args[0], LowStockAlert)
        ]
        assert any(a.alert_type == "OUT_OF_STOCK" for a in created_alerts)

    def test_low_stock_at_reorder_level(self) -> None:
        pos = _make_position(
            qty=Decimal("5"),
            reorder_level=Decimal("5"),
            safety_stock=Decimal("1"),
        )
        svc, db = _make_service()
        company_id = uuid4()
        svc.evaluate(company_id=company_id, position=pos)
        calls = db.add.call_args_list
        created_alerts = [
            c.args[0] for c in calls if isinstance(c.args[0], LowStockAlert)
        ]
        assert any(a.alert_type == "LOW_STOCK" for a in created_alerts)

    def test_safety_stock_breach(self) -> None:
        # qty=1, safety=3, reorder=5 → SAFETY_STOCK_BREACH (not LOW_STOCK because safety > 0)
        pos = _make_position(
            qty=Decimal("1"),
            safety_stock=Decimal("3"),
            reorder_level=Decimal("5"),
        )
        svc, db = _make_service()
        company_id = uuid4()
        svc.evaluate(company_id=company_id, position=pos)
        calls = db.add.call_args_list
        created_alerts = [
            c.args[0] for c in calls if isinstance(c.args[0], LowStockAlert)
        ]
        assert any(a.alert_type == "SAFETY_STOCK_BREACH" for a in created_alerts)

    def test_no_alert_when_stock_healthy(self) -> None:
        pos = _make_position(
            qty=Decimal("100"),
            reorder_level=Decimal("5"),
            safety_stock=Decimal("2"),
        )
        svc, db = _make_service()
        company_id = uuid4()
        svc.evaluate(company_id=company_id, position=pos)
        calls = db.add.call_args_list
        created_alerts = [
            c.args[0] for c in calls if isinstance(c.args[0], LowStockAlert)
        ]
        assert len(created_alerts) == 0

    def test_overstock_when_flag_enabled(self) -> None:
        pos = _make_position(
            qty=Decimal("200"),
            maximum_stock=Decimal("100"),
            reorder_level=Decimal("5"),
            safety_stock=Decimal("1"),
        )
        svc, db = _make_service(flag_enabled=True)
        company_id = uuid4()
        svc.evaluate(company_id=company_id, position=pos)
        calls = db.add.call_args_list
        created_alerts = [
            c.args[0] for c in calls if isinstance(c.args[0], LowStockAlert)
        ]
        assert any(a.alert_type == "OVERSTOCK" for a in created_alerts)

    def test_overstock_not_created_when_flag_disabled(self) -> None:
        pos = _make_position(
            qty=Decimal("200"),
            maximum_stock=Decimal("100"),
            reorder_level=Decimal("5"),
            safety_stock=Decimal("1"),
        )
        svc, db = _make_service(flag_enabled=False)  # flag off
        company_id = uuid4()
        svc.evaluate(company_id=company_id, position=pos)
        calls = db.add.call_args_list
        created_alerts = [
            c.args[0] for c in calls if isinstance(c.args[0], LowStockAlert)
        ]
        assert not any(a.alert_type == "OVERSTOCK" for a in created_alerts)


# ---------------------------------------------------------------------------
# Deduplication tests
# ---------------------------------------------------------------------------


class TestAlertDeduplication:
    """No new OPEN alert if an OPEN alert of the same type already exists."""

    def test_no_duplicate_open_alert(self) -> None:
        existing = MagicMock(spec=LowStockAlert)
        existing.current_quantity = Decimal("3")
        pos = _make_position(
            qty=Decimal("3"),
            reorder_level=Decimal("5"),
            safety_stock=Decimal("1"),
        )
        svc, db = _make_service(existing_alert=existing)
        company_id = uuid4()
        svc.evaluate(company_id=company_id, position=pos)
        # db.add should NOT be called with a new LowStockAlert
        calls = db.add.call_args_list
        created_alerts = [
            c.args[0] for c in calls if isinstance(c.args[0], LowStockAlert)
        ]
        assert len(created_alerts) == 0

    def test_existing_alert_qty_updated(self) -> None:
        existing = MagicMock(spec=LowStockAlert)
        existing.current_quantity = Decimal("5")
        pos = _make_position(
            qty=Decimal("3"),
            reorder_level=Decimal("5"),
            safety_stock=Decimal("1"),
        )
        svc, db = _make_service(existing_alert=existing)
        company_id = uuid4()
        svc.evaluate(company_id=company_id, position=pos)
        # The existing alert's current_quantity should be updated
        assert existing.current_quantity == Decimal("3")


# ---------------------------------------------------------------------------
# Auto-resolve tests
# ---------------------------------------------------------------------------


class TestAutoResolve:
    """Open alerts should auto-resolve when stock rises above threshold."""

    def test_open_alert_resolved_when_stock_replenished(self) -> None:
        existing = MagicMock(spec=LowStockAlert)
        existing.status = "OPEN"
        # Return existing for non-breached type; simulate that stock is now healthy
        alert_repo = MagicMock()
        # For a healthy position, all alert types are not breached
        alert_repo.get_open_alert.return_value = existing
        db = MagicMock()
        svc = AlertEvaluationService(
            db=db,
            alert_repo=alert_repo,
            rule_repo=MagicMock(return_value=[]),
            suggestion_repo=MagicMock(),
            flag_repo=MagicMock(),
        )
        svc._is_flag_enabled = MagicMock(return_value=False)
        pos = _make_position(
            qty=Decimal("50"),
            reorder_level=Decimal("5"),
            safety_stock=Decimal("2"),
        )
        svc.evaluate(company_id=uuid4(), position=pos)
        # existing.status must be set to RESOLVED
        assert existing.status == "RESOLVED"


# ---------------------------------------------------------------------------
# Reorder suggestion tests
# ---------------------------------------------------------------------------


class TestReorderSuggestion:
    """ReorderSuggestion is created when LOW_STOCK alert is raised and rule exists."""

    def test_suggestion_created_when_rule_exists(self) -> None:
        rule = MagicMock(spec=ReorderRule)
        rule.reorder_quantity = Decimal("50")
        pos = _make_position(
            qty=Decimal("3"),
            reorder_level=Decimal("5"),
            safety_stock=Decimal("0"),
        )
        svc, db = _make_service(rules=[rule])
        company_id = uuid4()
        svc.evaluate(company_id=company_id, position=pos)
        calls = db.add.call_args_list
        suggestions = [
            c.args[0] for c in calls if isinstance(c.args[0], ReorderSuggestion)
        ]
        assert len(suggestions) == 1
        assert suggestions[0].suggested_quantity == Decimal("50")

    def test_no_suggestion_when_no_rule(self) -> None:
        pos = _make_position(
            qty=Decimal("3"),
            reorder_level=Decimal("5"),
            safety_stock=Decimal("0"),
        )
        svc, db = _make_service(rules=[])
        company_id = uuid4()
        svc.evaluate(company_id=company_id, position=pos)
        calls = db.add.call_args_list
        suggestions = [
            c.args[0] for c in calls if isinstance(c.args[0], ReorderSuggestion)
        ]
        assert len(suggestions) == 0


# ---------------------------------------------------------------------------
# Error isolation tests
# ---------------------------------------------------------------------------


class TestErrorIsolation:
    """Alert evaluation errors must never block stock writes."""

    def test_exception_in_evaluation_is_caught(self) -> None:
        pos = _make_position(qty=Decimal("3"), reorder_level=Decimal("5"))
        svc, db = _make_service()
        # Inject a failure into _evaluate_unsafe
        svc._evaluate_unsafe = MagicMock(side_effect=RuntimeError("DB down"))
        # Should NOT raise — error is swallowed
        svc.evaluate(company_id=uuid4(), position=pos)  # no exception
