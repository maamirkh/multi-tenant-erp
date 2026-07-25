"""Unit tests for the Inventory EventBus (Phase 0 — T020).

Tests cover:
  - InProcessEventBus publish/subscribe
  - Wildcard handler subscription
  - Handler exception isolation (faulty handlers do not propagate)
  - InventoryDomainEvent base dataclass
  - clear_handlers()
  - handler_count()
  - get_event_bus() / set_event_bus() module-level helpers
"""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock

from modules.inventory.events import (
    EventBus,
    InProcessEventBus,
    InventoryDomainEvent,
    get_event_bus,
    set_event_bus,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_event(event_type: str = "product.created") -> InventoryDomainEvent:
    """Return a minimal ``InventoryDomainEvent`` for testing."""
    return InventoryDomainEvent(
        event_type=event_type,
        aggregate_type="Product",
        aggregate_id=uuid.uuid4(),
        company_id=uuid.uuid4(),
    )


# ---------------------------------------------------------------------------
# InventoryDomainEvent
# ---------------------------------------------------------------------------


class TestInventoryDomainEvent:
    def test_auto_fields_populated(self) -> None:
        event = _make_event()
        assert event.event_id is not None
        assert event.occurred_at is not None
        assert event.actor_id is None
        assert event.correlation_id is None

    def test_to_dict_contains_required_keys(self) -> None:
        event = _make_event("warehouse.created")
        d = event.to_dict()
        assert d["event_type"] == "warehouse.created"
        assert d["aggregate_type"] == "Product"
        assert "event_id" in d
        assert "company_id" in d
        assert "occurred_at" in d
        assert d["actor_id"] is None

    def test_unique_event_ids(self) -> None:
        e1 = _make_event()
        e2 = _make_event()
        assert e1.event_id != e2.event_id


# ---------------------------------------------------------------------------
# InProcessEventBus — subscribe / publish
# ---------------------------------------------------------------------------


class TestInProcessEventBus:
    def test_handler_called_on_publish(self) -> None:
        bus = InProcessEventBus()
        handler = MagicMock()
        bus.subscribe("product.created", handler)
        event = _make_event("product.created")
        bus.publish(event)
        handler.assert_called_once_with(event)

    def test_handler_not_called_for_different_event_type(self) -> None:
        bus = InProcessEventBus()
        handler = MagicMock()
        bus.subscribe("product.created", handler)
        bus.publish(_make_event("stock.adjusted"))
        handler.assert_not_called()

    def test_multiple_handlers_all_called(self) -> None:
        bus = InProcessEventBus()
        h1 = MagicMock()
        h2 = MagicMock()
        bus.subscribe("product.created", h1)
        bus.subscribe("product.created", h2)
        event = _make_event("product.created")
        bus.publish(event)
        h1.assert_called_once_with(event)
        h2.assert_called_once_with(event)

    def test_wildcard_handler_receives_all_events(self) -> None:
        bus = InProcessEventBus()
        handler = MagicMock()
        bus.subscribe("*", handler)
        e1 = _make_event("product.created")
        e2 = _make_event("warehouse.updated")
        bus.publish(e1)
        bus.publish(e2)
        assert handler.call_count == 2

    def test_faulty_handler_does_not_propagate_exception(self) -> None:
        bus = InProcessEventBus()
        bad_handler = MagicMock(side_effect=RuntimeError("boom"))
        good_handler = MagicMock()
        bus.subscribe("product.created", bad_handler)
        bus.subscribe("product.created", good_handler)
        # Should NOT raise
        bus.publish(_make_event("product.created"))
        good_handler.assert_called_once()

    def test_clear_handlers_removes_all(self) -> None:
        bus = InProcessEventBus()
        handler = MagicMock()
        bus.subscribe("product.created", handler)
        bus.clear_handlers()
        bus.publish(_make_event("product.created"))
        handler.assert_not_called()

    def test_handler_count_specific_type(self) -> None:
        bus = InProcessEventBus()
        bus.subscribe("product.created", MagicMock())
        bus.subscribe("product.created", MagicMock())
        bus.subscribe("stock.adjusted", MagicMock())
        assert bus.handler_count("product.created") == 2
        assert bus.handler_count("stock.adjusted") == 1

    def test_handler_count_all(self) -> None:
        bus = InProcessEventBus()
        bus.subscribe("product.created", MagicMock())
        bus.subscribe("stock.adjusted", MagicMock())
        assert bus.handler_count() == 2

    def test_handler_count_zero_for_unknown_type(self) -> None:
        bus = InProcessEventBus()
        assert bus.handler_count("nonexistent.event") == 0

    def test_implements_event_bus_interface(self) -> None:
        bus = InProcessEventBus()
        assert isinstance(bus, EventBus)


# ---------------------------------------------------------------------------
# Module-level get/set helpers
# ---------------------------------------------------------------------------


class TestModuleLevelBus:
    def test_get_event_bus_returns_instance(self) -> None:
        bus = get_event_bus()
        assert isinstance(bus, EventBus)

    def test_set_event_bus_replaces_singleton(self) -> None:
        original = get_event_bus()
        new_bus = InProcessEventBus()
        set_event_bus(new_bus)
        assert get_event_bus() is new_bus
        # Restore
        set_event_bus(original)

    def test_restored_bus_works_after_replacement(self) -> None:
        original = get_event_bus()
        replacement = InProcessEventBus()
        set_event_bus(replacement)
        set_event_bus(original)
        handler = MagicMock()
        get_event_bus().subscribe("test.event", handler)
        get_event_bus().publish(_make_event("test.event"))
        handler.assert_called_once()
        get_event_bus().clear_handlers()
