"""Unit tests for Sales Order domain events — Phase 4.

Tests:
  - All 10 order events can be instantiated with correct defaults
  - event_type, aggregate_type fields are correct for each event
  - Payload fields are accessible and correctly typed
  - Events follow the SalesDomainEvent dataclass pattern

Task: T131
Spec ref: specs/007-sales-management/spec.md §34 Domain Events
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from modules.sales.events.order_events import (
    OrderApproved,
    OrderCancelled,
    OrderClosed,
    OrderCreated,
    OrderCreditHold,
    OrderDelivered,
    OrderInvoiced,
    OrderPartiallyDelivered,
    OrderRejected,
    OrderSubmitted,
)


class TestOrderCreated:
    def test_event_type(self) -> None:
        assert OrderCreated().event_type == "sales.order.created"

    def test_aggregate_type(self) -> None:
        assert OrderCreated().aggregate_type == "SalesOrder"

    def test_has_event_id(self) -> None:
        assert isinstance(OrderCreated().event_id, UUID)

    def test_event_ids_are_unique(self) -> None:
        assert OrderCreated().event_id != OrderCreated().event_id

    def test_has_occurred_at(self) -> None:
        assert isinstance(OrderCreated().occurred_at, datetime)

    def test_default_aggregate_id(self) -> None:
        event = OrderCreated()
        assert isinstance(event.aggregate_id, UUID)

    def test_payload_fields(self) -> None:
        o_id = uuid4()
        c_id = uuid4()
        rep_id = uuid4()
        event = OrderCreated(
            aggregate_id=o_id,
            company_id=c_id,
            order_id=o_id,
            order_number="SO-2026-000001",
            customer_id=str(c_id),
            total_amount="1500.00",
            currency_code="EUR",
            sales_rep_id=str(rep_id),
            from_quotation=True,
            quotation_id=str(uuid4()),
        )
        assert event.order_number == "SO-2026-000001"
        assert event.total_amount == "1500.00"
        assert event.currency_code == "EUR"
        assert event.from_quotation is True
        assert event.quotation_id is not None

    def test_from_quotation_defaults_false(self) -> None:
        assert OrderCreated().from_quotation is False

    def test_quotation_id_defaults_none(self) -> None:
        assert OrderCreated().quotation_id is None


class TestOrderSubmitted:
    def test_event_type(self) -> None:
        assert OrderSubmitted().event_type == "sales.order.submitted"

    def test_aggregate_type(self) -> None:
        assert OrderSubmitted().aggregate_type == "SalesOrder"

    def test_payload_fields(self) -> None:
        o_id = uuid4()
        c_id = uuid4()
        rep_id = uuid4()
        event = OrderSubmitted(
            order_id=o_id,
            order_number="SO-2026-000002",
            customer_id=str(c_id),
            total_amount="2500.00",
            submitted_by=str(rep_id),
            approval_version=1,
        )
        assert event.order_number == "SO-2026-000002"
        assert event.submitted_by == str(rep_id)
        assert event.approval_version == 1

    def test_approval_version_default(self) -> None:
        assert OrderSubmitted().approval_version == 1


class TestOrderApproved:
    def test_event_type(self) -> None:
        assert OrderApproved().event_type == "sales.order.approved"

    def test_aggregate_type(self) -> None:
        assert OrderApproved().aggregate_type == "SalesOrder"

    def test_auto_approved_default_false(self) -> None:
        assert OrderApproved().auto_approved is False

    def test_payload_fields(self) -> None:
        o_id = uuid4()
        approver_id = uuid4()
        event = OrderApproved(
            order_id=o_id,
            order_number="SO-2026-000003",
            approved_by=str(approver_id),
            auto_approved=True,
            total_amount="500.00",
        )
        assert event.auto_approved is True
        assert event.approved_by == str(approver_id)


class TestOrderRejected:
    def test_event_type(self) -> None:
        assert OrderRejected().event_type == "sales.order.rejected"

    def test_aggregate_type(self) -> None:
        assert OrderRejected().aggregate_type == "SalesOrder"

    def test_rejection_reason_nullable(self) -> None:
        assert OrderRejected().rejection_reason is None

    def test_payload_fields(self) -> None:
        o_id = uuid4()
        approver_id = uuid4()
        event = OrderRejected(
            order_id=o_id,
            order_number="SO-2026-000004",
            rejected_by=str(approver_id),
            rejection_reason="Price too high",
        )
        assert event.rejected_by == str(approver_id)
        assert event.rejection_reason == "Price too high"


class TestOrderCancelled:
    def test_event_type(self) -> None:
        assert OrderCancelled().event_type == "sales.order.cancelled"

    def test_aggregate_type(self) -> None:
        assert OrderCancelled().aggregate_type == "SalesOrder"

    def test_payload_fields(self) -> None:
        o_id = uuid4()
        user_id = uuid4()
        event = OrderCancelled(
            order_id=o_id,
            order_number="SO-2026-000005",
            customer_id=str(uuid4()),
            previous_status="DRAFT",
            cancellation_reason="Customer requested cancellation",
            cancelled_by=str(user_id),
        )
        assert event.previous_status == "DRAFT"
        assert event.cancellation_reason == "Customer requested cancellation"
        assert event.cancelled_by == str(user_id)


class TestOrderPartiallyDelivered:
    def test_event_type(self) -> None:
        assert OrderPartiallyDelivered().event_type == "sales.order.partially_delivered"

    def test_aggregate_type(self) -> None:
        assert OrderPartiallyDelivered().aggregate_type == "SalesOrder"

    def test_payload_fields(self) -> None:
        o_id = uuid4()
        dn_id = str(uuid4())
        event = OrderPartiallyDelivered(
            order_id=o_id,
            order_number="SO-2026-000006",
            customer_id=str(uuid4()),
            delivery_note_id=dn_id,
        )
        assert event.delivery_note_id == dn_id


class TestOrderDelivered:
    def test_event_type(self) -> None:
        assert OrderDelivered().event_type == "sales.order.delivered"

    def test_aggregate_type(self) -> None:
        assert OrderDelivered().aggregate_type == "SalesOrder"

    def test_payload_fields(self) -> None:
        o_id = uuid4()
        c_id = uuid4()
        event = OrderDelivered(
            order_id=o_id,
            order_number="SO-2026-000007",
            customer_id=str(c_id),
        )
        assert event.order_number == "SO-2026-000007"
        assert event.customer_id == str(c_id)


class TestOrderInvoiced:
    def test_event_type(self) -> None:
        assert OrderInvoiced().event_type == "sales.order.invoiced"

    def test_aggregate_type(self) -> None:
        assert OrderInvoiced().aggregate_type == "SalesOrder"

    def test_invoice_id_field(self) -> None:
        inv_id = str(uuid4())
        event = OrderInvoiced(invoice_id=inv_id)
        assert event.invoice_id == inv_id

    def test_payload_fields(self) -> None:
        o_id = uuid4()
        event = OrderInvoiced(
            order_id=o_id,
            order_number="SO-2026-000008",
            customer_id=str(uuid4()),
            invoice_id="INV-2026-000001",
        )
        assert event.invoice_id == "INV-2026-000001"


class TestOrderClosed:
    def test_event_type(self) -> None:
        assert OrderClosed().event_type == "sales.order.closed"

    def test_aggregate_type(self) -> None:
        assert OrderClosed().aggregate_type == "SalesOrder"

    def test_payload_fields(self) -> None:
        o_id = uuid4()
        event = OrderClosed(
            order_id=o_id,
            order_number="SO-2026-000009",
            customer_id=str(uuid4()),
        )
        assert event.order_number == "SO-2026-000009"


class TestOrderCreditHold:
    def test_event_type(self) -> None:
        assert OrderCreditHold().event_type == "sales.order.credit_hold"

    def test_aggregate_type(self) -> None:
        assert OrderCreditHold().aggregate_type == "SalesOrder"

    def test_payload_fields(self) -> None:
        o_id = uuid4()
        event = OrderCreditHold(
            order_id=o_id,
            order_number="SO-2026-000010",
            customer_id=str(uuid4()),
            credit_status="HOLD",
            credit_limit="10000.00",
            outstanding_balance="9800.00",
            order_total="500.00",
        )
        assert event.credit_status == "HOLD"
        assert event.credit_limit == "10000.00"
        assert event.outstanding_balance == "9800.00"
        assert event.order_total == "500.00"

    def test_credit_status_exceeded(self) -> None:
        event = OrderCreditHold(credit_status="EXCEEDED")
        assert event.credit_status == "EXCEEDED"

    def test_default_amounts(self) -> None:
        event = OrderCreditHold()
        assert event.credit_limit == "0.00"
        assert event.outstanding_balance == "0.00"
        assert event.order_total == "0.00"
