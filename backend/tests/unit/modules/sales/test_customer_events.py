"""Unit tests for customer domain events — Phase 1.

Tests:
  - Each event type can be instantiated with required fields
  - event_type field is correct for each event class
  - InProcessEventBus can publish customer events

Task: T056
"""

from __future__ import annotations

from uuid import uuid4

from modules.sales.events import InProcessEventBus
from modules.sales.events.customer_events import (
    CustomerActivated,
    CustomerBlocked,
    CustomerCreated,
    CustomerCreditHoldPlaced,
    CustomerCreditHoldReleased,
    CustomerCreditLimitChanged,
    CustomerDeactivated,
    CustomerHoldReleased,
    CustomerOnHold,
    CustomerUnblocked,
    CustomerUpdated,
)


def _cid() -> dict:
    return {"aggregate_id": uuid4(), "company_id": uuid4()}


class TestCustomerEventTypes:
    """Verify event_type strings match the taxonomy."""

    def test_created_event_type(self) -> None:
        event = CustomerCreated(
            **_cid(),
            customer_id=uuid4(),
            customer_code="CUST-001",
            legal_name="ACME Corp",
            customer_type="COMPANY",
        )
        assert event.event_type == "customer.created"

    def test_activated_event_type(self) -> None:
        event = CustomerActivated(
            **_cid(),
            customer_id=uuid4(),
            previous_status="DRAFT",
        )
        assert event.event_type == "customer.activated"

    def test_updated_event_type(self) -> None:
        event = CustomerUpdated(
            **_cid(),
            customer_id=uuid4(),
            changed_fields=["legal_name"],
        )
        assert event.event_type == "customer.updated"

    def test_on_hold_event_type(self) -> None:
        event = CustomerOnHold(
            **_cid(),
            customer_id=uuid4(),
            reason="Payment overdue",
        )
        assert event.event_type == "customer.on_hold"

    def test_hold_released_event_type(self) -> None:
        event = CustomerHoldReleased(**_cid(), customer_id=uuid4())
        assert event.event_type == "customer.hold_released"

    def test_blocked_event_type(self) -> None:
        event = CustomerBlocked(
            **_cid(),
            customer_id=uuid4(),
            reason="Credit exceeded",
        )
        assert event.event_type == "customer.blocked"

    def test_unblocked_event_type(self) -> None:
        event = CustomerUnblocked(**_cid(), customer_id=uuid4())
        assert event.event_type == "customer.unblocked"

    def test_deactivated_event_type(self) -> None:
        event = CustomerDeactivated(**_cid(), customer_id=uuid4())
        assert event.event_type == "customer.deactivated"

    def test_credit_limit_changed_event_type(self) -> None:
        event = CustomerCreditLimitChanged(
            **_cid(),
            customer_id=uuid4(),
            previous_credit_limit=5000.0,
            new_credit_limit=10000.0,
        )
        assert event.event_type == "customer.credit_limit_changed"
        assert event.previous_credit_limit == 5000.0
        assert event.new_credit_limit == 10000.0

    def test_credit_hold_placed_event_type(self) -> None:
        event = CustomerCreditHoldPlaced(
            **_cid(),
            customer_id=uuid4(),
            credit_limit=10000.0,
            credit_used=12000.0,
        )
        assert event.event_type == "customer.credit_hold_placed"

    def test_credit_hold_released_event_type(self) -> None:
        event = CustomerCreditHoldReleased(
            **_cid(),
            customer_id=uuid4(),
            new_credit_status="GOOD",
        )
        assert event.event_type == "customer.credit_hold_released"


class TestEventBusWithCustomerEvents:
    """Verify InProcessEventBus can publish customer events."""

    def test_publish_customer_created(self) -> None:
        bus = InProcessEventBus()
        received = []
        bus.subscribe("customer.created", lambda e: received.append(e))

        event = CustomerCreated(
            customer_id=uuid4(),
            company_id=uuid4(),
            customer_code="CUST-001",
            legal_name="Test Corp",
            customer_type="COMPANY",
        )
        bus.publish(event)
        assert len(received) == 1
        assert received[0].customer_code == "CUST-001"

    def test_publish_multiple_events(self) -> None:
        bus = InProcessEventBus()
        all_events = []
        bus.subscribe("customer.activated", lambda e: all_events.append(e))
        bus.subscribe("customer.blocked", lambda e: all_events.append(e))

        bus.publish(
            CustomerActivated(
                customer_id=uuid4(),
                company_id=uuid4(),
                previous_status="DRAFT",
            )
        )
        bus.publish(
            CustomerBlocked(
                customer_id=uuid4(),
                company_id=uuid4(),
                reason="test",
            )
        )
        assert len(all_events) == 2

    def test_event_has_unique_event_id(self) -> None:
        """Each event instance should have a unique event_id."""
        event1 = CustomerCreated(
            aggregate_id=uuid4(),
            company_id=uuid4(),
            customer_id=uuid4(),
            customer_code="CUST-001",
            legal_name="Test",
            customer_type="COMPANY",
        )
        event2 = CustomerCreated(
            aggregate_id=uuid4(),
            company_id=uuid4(),
            customer_id=uuid4(),
            customer_code="CUST-002",
            legal_name="Test2",
            customer_type="COMPANY",
        )
        assert event1.event_id != event2.event_id
