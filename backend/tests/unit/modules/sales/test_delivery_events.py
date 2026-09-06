"""Unit tests for Delivery Note domain events — Phase 5.

Tests:
  - All 4 delivery events are instantiable with defaults
  - event_type, aggregate_type are correct
  - Events are JSON-serialisable via to_dict()
  - event_id is auto-generated (unique per instance)
  - occurred_at is auto-generated

Task: T153 (events portion)
Spec ref: specs/007-sales-management/spec.md §34 Domain Events
"""

from __future__ import annotations

from uuid import uuid4

from modules.sales.events.delivery_events import (
    DeliveryNoteCancelled,
    DeliveryNoteCreated,
    DeliveryNoteDelivered,
    DeliveryNoteDispatched,
)


class TestDeliveryNoteCreated:
    def test_default_instantiation(self) -> None:
        event = DeliveryNoteCreated()
        assert event.event_type == "sales.delivery.created"
        assert event.aggregate_type == "DeliveryNote"

    def test_with_payload(self) -> None:
        dn_id = uuid4()
        company_id = uuid4()
        event = DeliveryNoteCreated(
            aggregate_id=dn_id,
            company_id=company_id,
            delivery_note_id=dn_id,
            delivery_number="DN-2026-000001",
            order_id=str(uuid4()),
            customer_id=str(uuid4()),
            line_count=3,
        )
        assert event.delivery_number == "DN-2026-000001"
        assert event.line_count == 3
        assert event.company_id == company_id

    def test_unique_event_id(self) -> None:
        e1 = DeliveryNoteCreated()
        e2 = DeliveryNoteCreated()
        assert e1.event_id != e2.event_id

    def test_to_dict_serialisable(self) -> None:
        event = DeliveryNoteCreated(
            aggregate_id=uuid4(),
            company_id=uuid4(),
            delivery_note_id=uuid4(),
            delivery_number="DN-2026-000001",
            order_id=str(uuid4()),
            customer_id=str(uuid4()),
        )
        d = event.to_dict()
        assert d["event_type"] == "sales.delivery.created"
        assert "event_id" in d
        assert "aggregate_type" in d

    def test_occurred_at_is_set(self) -> None:
        event = DeliveryNoteCreated()
        assert event.occurred_at is not None


class TestDeliveryNoteDispatched:
    def test_default_instantiation(self) -> None:
        event = DeliveryNoteDispatched()
        assert event.event_type == "sales.delivery.dispatched"
        assert event.aggregate_type == "DeliveryNote"

    def test_with_payload(self) -> None:
        dn_id = uuid4()
        dispatched_by = uuid4()
        event = DeliveryNoteDispatched(
            aggregate_id=dn_id,
            company_id=uuid4(),
            delivery_note_id=dn_id,
            delivery_number="DN-2026-000002",
            order_id=str(uuid4()),
            customer_id=str(uuid4()),
            dispatch_date="2026-08-03",
            dispatched_by=str(dispatched_by),
        )
        assert event.dispatch_date == "2026-08-03"
        assert event.dispatched_by == str(dispatched_by)

    def test_to_dict_serialisable(self) -> None:
        event = DeliveryNoteDispatched(
            aggregate_id=uuid4(),
            company_id=uuid4(),
            delivery_note_id=uuid4(),
            delivery_number="DN-X",
            order_id=str(uuid4()),
            customer_id=str(uuid4()),
            dispatch_date="2026-08-03",
            dispatched_by=str(uuid4()),
        )
        d = event.to_dict()
        assert d["event_type"] == "sales.delivery.dispatched"
        assert "event_id" in d


class TestDeliveryNoteDelivered:
    def test_default_instantiation(self) -> None:
        event = DeliveryNoteDelivered()
        assert event.event_type == "sales.delivery.delivered"
        assert event.aggregate_type == "DeliveryNote"

    def test_with_payload(self) -> None:
        dn_id = uuid4()
        event = DeliveryNoteDelivered(
            aggregate_id=dn_id,
            company_id=uuid4(),
            delivery_note_id=dn_id,
            delivery_number="DN-2026-000003",
            order_id=str(uuid4()),
            customer_id=str(uuid4()),
        )
        assert event.delivery_number == "DN-2026-000003"

    def test_to_dict_serialisable(self) -> None:
        event = DeliveryNoteDelivered(
            aggregate_id=uuid4(),
            company_id=uuid4(),
            delivery_note_id=uuid4(),
            delivery_number="DN-Y",
            order_id=str(uuid4()),
            customer_id=str(uuid4()),
        )
        d = event.to_dict()
        assert d["event_type"] == "sales.delivery.delivered"
        assert "event_id" in d


class TestDeliveryNoteCancelled:
    def test_default_instantiation(self) -> None:
        event = DeliveryNoteCancelled()
        assert event.event_type == "sales.delivery.cancelled"
        assert event.aggregate_type == "DeliveryNote"

    def test_with_payload(self) -> None:
        dn_id = uuid4()
        event = DeliveryNoteCancelled(
            aggregate_id=dn_id,
            company_id=uuid4(),
            delivery_note_id=dn_id,
            delivery_number="DN-2026-000004",
            order_id=str(uuid4()),
            customer_id=str(uuid4()),
            previous_status="DRAFT",
        )
        assert event.previous_status == "DRAFT"

    def test_previous_status_dispatched(self) -> None:
        event = DeliveryNoteCancelled(previous_status="DISPATCHED")
        assert event.previous_status == "DISPATCHED"

    def test_to_dict_serialisable(self) -> None:
        event = DeliveryNoteCancelled(
            aggregate_id=uuid4(),
            company_id=uuid4(),
            delivery_note_id=uuid4(),
            delivery_number="DN-Z",
            order_id=str(uuid4()),
            customer_id=str(uuid4()),
            previous_status="DRAFT",
        )
        d = event.to_dict()
        assert d["event_type"] == "sales.delivery.cancelled"
        assert "event_id" in d


class TestEventUniqueness:
    def test_all_event_types_distinct(self) -> None:
        events = [
            DeliveryNoteCreated(),
            DeliveryNoteDispatched(),
            DeliveryNoteDelivered(),
            DeliveryNoteCancelled(),
        ]
        types = [e.event_type for e in events]
        assert len(set(types)) == 4, "All delivery event types must be unique"

    def test_all_aggregate_types_are_delivery_note(self) -> None:
        events = [
            DeliveryNoteCreated(),
            DeliveryNoteDispatched(),
            DeliveryNoteDelivered(),
            DeliveryNoteCancelled(),
        ]
        for event in events:
            assert event.aggregate_type == "DeliveryNote"
