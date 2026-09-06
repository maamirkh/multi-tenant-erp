"""Unit tests for sales domain events.

Tests:
  - SalesDomainEvent instantiation and serialisation
  - InProcessEventBus publish/subscribe
  - Handler exception isolation
  - Wildcard subscription

Task: T028 (events portion)
"""

from __future__ import annotations

from uuid import uuid4

from modules.sales.events import (
    InProcessEventBus,
    SalesDomainEvent,
    get_event_bus,
    set_event_bus,
)


class TestSalesDomainEvent:
    """Test SalesDomainEvent base class."""

    def test_create_event(self) -> None:
        event = SalesDomainEvent(
            event_type="customer.created",
            aggregate_type="Customer",
            aggregate_id=uuid4(),
            company_id=uuid4(),
        )
        assert event.event_type == "customer.created"
        assert event.aggregate_type == "Customer"
        assert event.event_id is not None
        assert event.occurred_at is not None

    def test_to_dict(self) -> None:
        cid = uuid4()
        aid = uuid4()
        event = SalesDomainEvent(
            event_type="customer.updated",
            aggregate_type="Customer",
            aggregate_id=aid,
            company_id=cid,
            actor_id=uuid4(),
        )
        d = event.to_dict()
        assert d["event_type"] == "customer.updated"
        assert d["aggregate_type"] == "Customer"
        assert d["company_id"] == str(cid)
        assert d["aggregate_id"] == str(aid)
        assert d["actor_id"] is not None

    def test_to_dict_no_actor(self) -> None:
        event = SalesDomainEvent(
            event_type="test",
            aggregate_type="Test",
            aggregate_id=uuid4(),
            company_id=uuid4(),
        )
        d = event.to_dict()
        assert d["actor_id"] is None


class TestInProcessEventBus:
    """Test InProcessEventBus."""

    def test_publish_subscribe(self) -> None:
        bus = InProcessEventBus()
        received = []
        bus.subscribe("test.event", lambda e: received.append(e))

        event = SalesDomainEvent(
            event_type="test.event",
            aggregate_type="Test",
            aggregate_id=uuid4(),
            company_id=uuid4(),
        )
        bus.publish(event)
        assert len(received) == 1
        assert received[0] is event

    def test_wildcard_subscription(self) -> None:
        bus = InProcessEventBus()
        received = []
        bus.subscribe("*", lambda e: received.append(e))

        event = SalesDomainEvent(
            event_type="any.event",
            aggregate_type="Test",
            aggregate_id=uuid4(),
            company_id=uuid4(),
        )
        bus.publish(event)
        assert len(received) == 1

    def test_handler_exception_does_not_propagate(self) -> None:
        bus = InProcessEventBus()
        bus.subscribe(
            "error.event", lambda e: (_ for _ in ()).throw(RuntimeError("boom"))
        )

        event = SalesDomainEvent(
            event_type="error.event",
            aggregate_type="Test",
            aggregate_id=uuid4(),
            company_id=uuid4(),
        )
        # Should not raise
        bus.publish(event)

    def test_clear_handlers(self) -> None:
        bus = InProcessEventBus()
        bus.subscribe("test", lambda e: None)
        assert bus.handler_count() > 0
        bus.clear_handlers()
        assert bus.handler_count() == 0

    def test_handler_count_by_type(self) -> None:
        bus = InProcessEventBus()
        bus.subscribe("a", lambda e: None)
        bus.subscribe("a", lambda e: None)
        bus.subscribe("b", lambda e: None)
        assert bus.handler_count("a") == 2
        assert bus.handler_count("b") == 1
        assert bus.handler_count("c") == 0

    def test_module_singleton(self) -> None:
        original = get_event_bus()
        new_bus = InProcessEventBus()
        set_event_bus(new_bus)
        assert get_event_bus() is new_bus
        set_event_bus(original)
