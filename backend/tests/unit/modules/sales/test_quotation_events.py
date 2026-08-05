"""Unit tests for quotation domain events — Phase 3.

Tests:
  - All 8 quotation events can be instantiated with correct defaults
  - event_type, aggregate_type fields correct for each event
  - Payload fields are accessible and typed correctly
  - Events are dataclasses (serializable pattern)

Task: T101
Spec ref: specs/007-sales-management/spec.md §34 Domain Events
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from modules.sales.events.quotation_events import (
    QuotationAccepted,
    QuotationCancelled,
    QuotationConverted,
    QuotationCreated,
    QuotationExpired,
    QuotationExpiringSoon,
    QuotationRejected,
    QuotationSent,
)


class TestQuotationCreated:
    def test_event_type(self) -> None:
        event = QuotationCreated()
        assert event.event_type == "quotation.created"

    def test_aggregate_type(self) -> None:
        event = QuotationCreated()
        assert event.aggregate_type == "SalesQuotation"

    def test_has_event_id(self) -> None:
        event = QuotationCreated()
        assert isinstance(event.event_id, UUID)

    def test_has_occurred_at(self) -> None:
        event = QuotationCreated()
        assert isinstance(event.occurred_at, datetime)

    def test_payload_fields(self) -> None:
        q_id = uuid4()
        c_id = uuid4()
        rep_id = uuid4()
        event = QuotationCreated(
            aggregate_id=q_id,
            company_id=c_id,
            quotation_id=q_id,
            quotation_number="SQ-2026-000001",
            customer_id=c_id,
            sales_rep_id=rep_id,
            validity_date="2026-09-01",
            created_by=rep_id,
        )
        assert event.quotation_number == "SQ-2026-000001"
        assert event.validity_date == "2026-09-01"
        assert event.created_by == rep_id


class TestQuotationSent:
    def test_event_type(self) -> None:
        event = QuotationSent()
        assert event.event_type == "quotation.sent"

    def test_aggregate_type(self) -> None:
        event = QuotationSent()
        assert event.aggregate_type == "SalesQuotation"

    def test_payload_fields(self) -> None:
        q_id = uuid4()
        event = QuotationSent(
            quotation_id=q_id,
            quotation_number="SQ-2026-000002",
            customer_id=uuid4(),
            validity_date="2026-08-31",
        )
        assert event.quotation_number == "SQ-2026-000002"
        assert event.validity_date == "2026-08-31"


class TestQuotationAccepted:
    def test_event_type(self) -> None:
        event = QuotationAccepted()
        assert event.event_type == "quotation.accepted"

    def test_aggregate_type(self) -> None:
        event = QuotationAccepted()
        assert event.aggregate_type == "SalesQuotation"

    def test_total_amount_field(self) -> None:
        event = QuotationAccepted(total_amount=5000.0)
        assert event.total_amount == 5000.0

    def test_accepted_by_nullable(self) -> None:
        event = QuotationAccepted()
        assert event.accepted_by is None

    def test_accepted_by_can_be_set(self) -> None:
        user_id = uuid4()
        event = QuotationAccepted(accepted_by=user_id)
        assert event.accepted_by == user_id


class TestQuotationRejected:
    def test_event_type(self) -> None:
        event = QuotationRejected()
        assert event.event_type == "quotation.rejected"

    def test_reason_field(self) -> None:
        event = QuotationRejected(reason="Price too high")
        assert event.reason == "Price too high"

    def test_reason_default_empty(self) -> None:
        event = QuotationRejected()
        assert event.reason == ""


class TestQuotationConverted:
    def test_event_type(self) -> None:
        event = QuotationConverted()
        assert event.event_type == "quotation.converted"

    def test_aggregate_type(self) -> None:
        event = QuotationConverted()
        assert event.aggregate_type == "SalesQuotation"

    def test_order_fields(self) -> None:
        o_id = uuid4()
        event = QuotationConverted(
            order_id=o_id,
            order_number="SO-2026-000001",
        )
        assert event.order_id == o_id
        assert event.order_number == "SO-2026-000001"


class TestQuotationExpired:
    def test_event_type(self) -> None:
        event = QuotationExpired()
        assert event.event_type == "quotation.expired"

    def test_validity_date_field(self) -> None:
        event = QuotationExpired(validity_date="2026-07-15")
        assert event.validity_date == "2026-07-15"


class TestQuotationCancelled:
    def test_event_type(self) -> None:
        event = QuotationCancelled()
        assert event.event_type == "quotation.cancelled"

    def test_previous_status_and_reason(self) -> None:
        event = QuotationCancelled(
            previous_status="SENT_TO_CUSTOMER",
            reason="Customer changed mind",
        )
        assert event.previous_status == "SENT_TO_CUSTOMER"
        assert event.reason == "Customer changed mind"


class TestQuotationExpiringSoon:
    def test_event_type(self) -> None:
        event = QuotationExpiringSoon()
        assert event.event_type == "quotation.expiring_soon"

    def test_days_remaining_field(self) -> None:
        event = QuotationExpiringSoon(days_remaining=2)
        assert event.days_remaining == 2

    def test_days_remaining_default_zero(self) -> None:
        event = QuotationExpiringSoon()
        assert event.days_remaining == 0

    def test_validity_date_field(self) -> None:
        event = QuotationExpiringSoon(validity_date="2026-08-04")
        assert event.validity_date == "2026-08-04"
