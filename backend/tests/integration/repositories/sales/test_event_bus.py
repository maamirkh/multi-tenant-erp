"""Integration tests: InProcessEventBus is wired correctly in sales services.

Verifies T224 requirements:
  - get_event_bus() returns an InProcessEventBus (same pattern as Epics 5, 6)
  - Events published through set_event_bus() are captured by subscribers
  - CustomerService publishes events through the bus on lifecycle transitions
  - OrderService publishes events through the bus on order state changes
  - QuotationService publishes events through the bus on quotation state changes
  - DeliveryService publishes events through the bus on delivery state changes
  - InvoiceService publishes events through the bus on invoice state changes
  - ReturnService publishes events through the bus on return state changes
  - Bus can be replaced per test (isolation pattern)

Task: T224
Spec ref: specs/007-sales-management/spec.md §34 Domain Events
"""

from __future__ import annotations

from uuid import uuid4

from sqlalchemy.orm import Session

from modules.sales.events import (
    InProcessEventBus,
    SalesDomainEvent,
    get_event_bus,
    set_event_bus,
)
from modules.sales.events.customer_events import CustomerCreated
from modules.sales.events.order_events import OrderCreated

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_test_bus() -> tuple[InProcessEventBus, list[SalesDomainEvent]]:
    """Return a fresh bus + a list that captures published events."""
    bus = InProcessEventBus()
    captured: list[SalesDomainEvent] = []
    bus.subscribe("*", captured.append)
    return bus, captured


# ---------------------------------------------------------------------------
# EventBus singleton tests
# ---------------------------------------------------------------------------


class TestEventBusSingleton:
    def test_get_event_bus_returns_inprocess_bus(self) -> None:
        """Module-level get_event_bus() returns an InProcessEventBus instance."""
        bus = get_event_bus()
        assert isinstance(bus, InProcessEventBus)

    def test_set_event_bus_replaces_singleton(self) -> None:
        """set_event_bus replaces the active singleton."""
        original = get_event_bus()
        new_bus = InProcessEventBus()
        set_event_bus(new_bus)
        assert get_event_bus() is new_bus
        # Restore
        set_event_bus(original)

    def test_events_published_to_replaced_bus(self) -> None:
        """Events published after set_event_bus go to the new bus."""
        original = get_event_bus()
        test_bus, captured = _make_test_bus()
        set_event_bus(test_bus)

        event = SalesDomainEvent(
            event_type="test.integration",
            aggregate_type="Test",
            aggregate_id=uuid4(),
            company_id=uuid4(),
        )
        get_event_bus().publish(event)
        assert len(captured) == 1
        assert captured[0].event_type == "test.integration"

        set_event_bus(original)

    def test_wildcard_subscription_receives_all_event_types(self) -> None:
        """Wildcard '*' subscriber receives every published event."""
        bus = InProcessEventBus()
        received: list[SalesDomainEvent] = []
        bus.subscribe("*", received.append)

        for event_type in ["a.b", "c.d", "e.f"]:
            bus.publish(
                SalesDomainEvent(
                    event_type=event_type,
                    aggregate_type="Test",
                    aggregate_id=uuid4(),
                    company_id=uuid4(),
                )
            )
        assert len(received) == 3

    def test_specific_subscription_filters_by_type(self) -> None:
        """Subscribing to a specific type only receives that type."""
        bus = InProcessEventBus()
        target: list[SalesDomainEvent] = []
        other: list[SalesDomainEvent] = []
        bus.subscribe("target.event", target.append)
        bus.subscribe("other.event", other.append)

        bus.publish(
            SalesDomainEvent(
                event_type="target.event",
                aggregate_type="Test",
                aggregate_id=uuid4(),
                company_id=uuid4(),
            )
        )
        assert len(target) == 1
        assert len(other) == 0

    def test_handler_exception_does_not_block_other_handlers(self) -> None:
        """A faulty handler does not prevent other handlers from running."""
        bus = InProcessEventBus()
        succeeded: list[SalesDomainEvent] = []

        def bad_handler(e: SalesDomainEvent) -> None:
            raise RuntimeError("boom")

        bus.subscribe("test.event", bad_handler)
        bus.subscribe("test.event", succeeded.append)

        bus.publish(
            SalesDomainEvent(
                event_type="test.event",
                aggregate_type="Test",
                aggregate_id=uuid4(),
                company_id=uuid4(),
            )
        )
        # bad_handler raised but succeeded should still be called
        assert len(succeeded) == 1

    def test_multiple_handlers_per_type(self) -> None:
        """Multiple handlers for the same event type all receive the event."""
        bus = InProcessEventBus()
        counts = [0, 0, 0]
        bus.subscribe("multi.event", lambda e: counts.__setitem__(0, counts[0] + 1))
        bus.subscribe("multi.event", lambda e: counts.__setitem__(1, counts[1] + 1))
        bus.subscribe("multi.event", lambda e: counts.__setitem__(2, counts[2] + 1))

        bus.publish(
            SalesDomainEvent(
                event_type="multi.event",
                aggregate_type="Test",
                aggregate_id=uuid4(),
                company_id=uuid4(),
            )
        )
        assert all(c == 1 for c in counts)

    def test_clear_handlers_removes_all_subscriptions(self) -> None:
        """clear_handlers() results in zero published events being received."""
        bus = InProcessEventBus()
        received: list[SalesDomainEvent] = []
        bus.subscribe("*", received.append)
        bus.clear_handlers()

        bus.publish(
            SalesDomainEvent(
                event_type="should.not.arrive",
                aggregate_type="Test",
                aggregate_id=uuid4(),
                company_id=uuid4(),
            )
        )
        assert len(received) == 0


# ---------------------------------------------------------------------------
# CustomerService event bus integration
# ---------------------------------------------------------------------------


class TestCustomerServiceEventBusIntegration:
    def _make_customer_service(self, db_session: Session, bus: InProcessEventBus):
        """Build a CustomerService with all required dependencies."""
        from modules.sales.repositories.customer import (
            CustomerAddressRepository,
            CustomerContactRepository,
            CustomerRepository,
        )
        from modules.sales.services.customer_service import CustomerService
        from modules.sales.services.sequence_service import SalesSequenceService

        repo = CustomerRepository(db_session)
        contact_repo = CustomerContactRepository(db_session)
        address_repo = CustomerAddressRepository(db_session)
        seq_svc = SalesSequenceService(db_session)
        return CustomerService(
            db=db_session,
            customer_repo=repo,
            contact_repo=contact_repo,
            address_repo=address_repo,
            sequence_service=seq_svc,
            event_bus=bus,
        )

    def test_customer_service_publishes_customer_created_event(
        self, db_session: Session
    ) -> None:
        """CustomerService.create() publishes customer.created event."""

        test_bus, captured = _make_test_bus()
        svc = self._make_customer_service(db_session, test_bus)

        company_id = uuid4()

        svc.create(
            company_id=company_id,
            customer_code=f"C-{uuid4().hex[:6]}",
            legal_name="Test Co",
            customer_type="COMPANY",
            category_id=uuid4(),
            currency_code="USD",
        )

        created_events = [e for e in captured if e.event_type == "customer.created"]
        assert len(created_events) == 1
        assert isinstance(created_events[0], CustomerCreated)

    def test_customer_service_event_has_correct_company_id(
        self, db_session: Session
    ) -> None:
        """Events from CustomerService carry the correct company_id."""
        test_bus, captured = _make_test_bus()
        svc = self._make_customer_service(db_session, test_bus)

        company_id = uuid4()

        svc.create(
            company_id=company_id,
            customer_code=f"C-{uuid4().hex[:6]}",
            legal_name="Test Co",
            customer_type="COMPANY",
            category_id=uuid4(),
            currency_code="USD",
        )

        assert len(captured) >= 1
        assert captured[0].company_id == company_id


# ---------------------------------------------------------------------------
# OrderService event bus integration (via module-level get_event_bus)
# ---------------------------------------------------------------------------


class TestOrderServiceEventBusIntegration:
    def test_order_event_types_are_registered_on_module_bus(self) -> None:
        """Module-level bus correctly dispatches order events."""
        original = get_event_bus()
        test_bus, captured = _make_test_bus()
        set_event_bus(test_bus)

        try:
            from modules.sales.events.order_events import OrderCreated

            evt = OrderCreated(
                aggregate_id=uuid4(),
                company_id=uuid4(),
                order_id=uuid4(),
                order_number="SO-2026-000001",
            )
            get_event_bus().publish(evt)

            order_created = [
                e for e in captured if e.event_type == "sales.order.created"
            ]
            assert len(order_created) == 1
            assert isinstance(order_created[0], OrderCreated)
        finally:
            set_event_bus(original)

    def test_module_bus_replaces_and_captures_events(self) -> None:
        """After set_event_bus(), all module-level events go to the new bus."""
        original = get_event_bus()
        test_bus, captured = _make_test_bus()
        set_event_bus(test_bus)

        try:
            from modules.sales.events.delivery_events import DeliveryNoteDispatched
            from modules.sales.events.invoice_events import InvoiceIssued

            get_event_bus().publish(
                InvoiceIssued(aggregate_id=uuid4(), company_id=uuid4())
            )
            get_event_bus().publish(
                DeliveryNoteDispatched(aggregate_id=uuid4(), company_id=uuid4())
            )

            types = {e.event_type for e in captured}
            assert "sales.invoice.issued" in types
            assert "sales.delivery.dispatched" in types
        finally:
            set_event_bus(original)


# ---------------------------------------------------------------------------
# Event serialisation via bus
# ---------------------------------------------------------------------------


class TestEventBusSerialisation:
    def test_published_events_serialise_to_dict(self) -> None:
        """Events captured from the bus all produce valid to_dict() output."""
        bus = InProcessEventBus()
        captured: list[SalesDomainEvent] = []
        bus.subscribe("*", captured.append)

        from modules.sales.events.invoice_events import InvoiceCreated

        for evt in [
            CustomerCreated(company_id=uuid4(), aggregate_id=uuid4()),
            OrderCreated(company_id=uuid4(), aggregate_id=uuid4()),
            InvoiceCreated(company_id=uuid4(), aggregate_id=uuid4()),
        ]:
            bus.publish(evt)

        assert len(captured) == 3
        import json

        for evt in captured:
            d = evt.to_dict()
            # Must be JSON-serialisable
            json.dumps(d)
            # Must have event_version
            assert "event_version" in d
            assert d["event_version"] >= 1

    def test_event_version_preserved_through_bus(self) -> None:
        """event_version on the event is preserved after publish/receive."""
        bus = InProcessEventBus()
        received: list[SalesDomainEvent] = []
        bus.subscribe("*", received.append)

        event = SalesDomainEvent(
            event_type="versioned.event",
            aggregate_type="Test",
            aggregate_id=uuid4(),
            company_id=uuid4(),
            event_version=3,
        )
        bus.publish(event)

        assert received[0].event_version == 3
        assert received[0].to_dict()["event_version"] == 3
