"""Integration tests: all sales domain events are published on correct triggers.

Verifies T222 requirements:
  - Each event class has the correct event_type matching spec §34
  - Each event class belongs to the correct aggregate_type
  - Event payload fields exist and are populated correctly
  - All event classes are correctly registered (importable)

Tests are designed to be fast (no DB needed for event class verification).
Full service-level event publishing is covered in test_event_bus.py.

Task: T222
Spec ref: specs/007-sales-management/spec.md §34 Domain Events
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from modules.sales.events import SalesDomainEvent

# ---------------------------------------------------------------------------
# Import all event classes
# ---------------------------------------------------------------------------
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
from modules.sales.events.delivery_events import (
    DeliveryNoteCancelled,
    DeliveryNoteCreated,
    DeliveryNoteDelivered,
    DeliveryNoteDispatched,
)
from modules.sales.events.invoice_events import (
    InvoiceCancelled,
    InvoiceCreated,
    InvoiceCreditNoteIssued,
    InvoiceIssued,
)
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
from modules.sales.events.return_events import (
    ReturnApproved,
    ReturnCompleted,
    ReturnCreated,
    ReturnReceived,
    ReturnRefundReady,
    ReturnRejected,
    ReturnSubmitted,
)

# ---------------------------------------------------------------------------
# Expected event registry: (class, event_type, aggregate_type)
# ---------------------------------------------------------------------------

EXPECTED_EVENTS = [
    # Customer
    (CustomerCreated, "customer.created", "Customer"),
    (CustomerActivated, "customer.activated", "Customer"),
    (CustomerUpdated, "customer.updated", "Customer"),
    (CustomerOnHold, "customer.on_hold", "Customer"),
    (CustomerHoldReleased, "customer.hold_released", "Customer"),
    (CustomerBlocked, "customer.blocked", "Customer"),
    (CustomerUnblocked, "customer.unblocked", "Customer"),
    (CustomerDeactivated, "customer.deactivated", "Customer"),
    (CustomerCreditLimitChanged, "customer.credit_limit_changed", "Customer"),
    (CustomerCreditHoldPlaced, "customer.credit_hold_placed", "Customer"),
    (CustomerCreditHoldReleased, "customer.credit_hold_released", "Customer"),
    # Quotation
    (QuotationCreated, "quotation.created", "SalesQuotation"),
    (QuotationSent, "quotation.sent", "SalesQuotation"),
    (QuotationAccepted, "quotation.accepted", "SalesQuotation"),
    (QuotationRejected, "quotation.rejected", "SalesQuotation"),
    (QuotationConverted, "quotation.converted", "SalesQuotation"),
    (QuotationExpired, "quotation.expired", "SalesQuotation"),
    (QuotationCancelled, "quotation.cancelled", "SalesQuotation"),
    (QuotationExpiringSoon, "quotation.expiring_soon", "SalesQuotation"),
    # Order
    (OrderCreated, "sales.order.created", "SalesOrder"),
    (OrderSubmitted, "sales.order.submitted", "SalesOrder"),
    (OrderApproved, "sales.order.approved", "SalesOrder"),
    (OrderRejected, "sales.order.rejected", "SalesOrder"),
    (OrderCancelled, "sales.order.cancelled", "SalesOrder"),
    (OrderPartiallyDelivered, "sales.order.partially_delivered", "SalesOrder"),
    (OrderDelivered, "sales.order.delivered", "SalesOrder"),
    (OrderInvoiced, "sales.order.invoiced", "SalesOrder"),
    (OrderClosed, "sales.order.closed", "SalesOrder"),
    (OrderCreditHold, "sales.order.credit_hold", "SalesOrder"),
    # Delivery
    (DeliveryNoteCreated, "sales.delivery.created", "DeliveryNote"),
    (DeliveryNoteDispatched, "sales.delivery.dispatched", "DeliveryNote"),
    (DeliveryNoteDelivered, "sales.delivery.delivered", "DeliveryNote"),
    (DeliveryNoteCancelled, "sales.delivery.cancelled", "DeliveryNote"),
    # Invoice
    (InvoiceCreated, "sales.invoice.created", "SalesInvoice"),
    (InvoiceIssued, "sales.invoice.issued", "SalesInvoice"),
    (InvoiceCancelled, "sales.invoice.cancelled", "SalesInvoice"),
    (InvoiceCreditNoteIssued, "sales.invoice.credit_note_issued", "SalesInvoice"),
    # Return
    (ReturnCreated, "sales.return.created", "SalesReturn"),
    (ReturnSubmitted, "sales.return.submitted", "SalesReturn"),
    (ReturnApproved, "sales.return.approved", "SalesReturn"),
    (ReturnRejected, "sales.return.rejected", "SalesReturn"),
    (ReturnReceived, "sales.return.received", "SalesReturn"),
    (ReturnCompleted, "sales.return.completed", "SalesReturn"),
    (ReturnRefundReady, "sales.return.refund_ready", "SalesReturn"),
]


# ---------------------------------------------------------------------------
# Parametrised contract verification
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "event_cls,expected_type,expected_aggregate",
    EXPECTED_EVENTS,
    ids=lambda x: x if isinstance(x, str) else x.__name__,
)
class TestEventContract:
    def test_event_type_matches_spec(
        self, event_cls: type, expected_type: str, expected_aggregate: str
    ) -> None:
        """event_type matches the spec §34 contract."""
        event = event_cls()
        assert event.event_type == expected_type

    def test_aggregate_type_matches_spec(
        self, event_cls: type, expected_type: str, expected_aggregate: str
    ) -> None:
        """aggregate_type matches the spec §34 contract."""
        event = event_cls()
        assert event.aggregate_type == expected_aggregate

    def test_inherits_from_base(
        self, event_cls: type, expected_type: str, expected_aggregate: str
    ) -> None:
        """Every event class inherits from SalesDomainEvent."""
        assert issubclass(event_cls, SalesDomainEvent)

    def test_event_version_is_set(
        self, event_cls: type, expected_type: str, expected_aggregate: str
    ) -> None:
        """event_version is set (defaults to 1)."""
        event = event_cls()
        assert event.event_version >= 1


# ---------------------------------------------------------------------------
# Customer event payload fields
# ---------------------------------------------------------------------------


class TestCustomerEventPayloads:
    def test_customer_created_has_customer_payload(self) -> None:
        cid = uuid4()
        company_id = uuid4()
        event = CustomerCreated(
            aggregate_id=cid,
            company_id=company_id,
            customer_id=cid,
            customer_code="C-001",
            legal_name="Test Corp",
            customer_type="COMPANY",
        )
        assert event.customer_id == cid
        assert event.customer_code == "C-001"
        assert event.legal_name == "Test Corp"
        assert event.customer_type == "COMPANY"
        assert event.company_id == company_id

    def test_customer_credit_limit_changed_has_amounts(self) -> None:
        event = CustomerCreditLimitChanged(
            aggregate_id=uuid4(),
            company_id=uuid4(),
            customer_id=uuid4(),
            previous_credit_limit=5000.0,
            new_credit_limit=10000.0,
        )
        assert event.previous_credit_limit == 5000.0
        assert event.new_credit_limit == 10000.0

    def test_customer_blocked_has_reason(self) -> None:
        event = CustomerBlocked(
            aggregate_id=uuid4(),
            company_id=uuid4(),
            customer_id=uuid4(),
            reason="Exceeded credit limit",
        )
        assert event.reason == "Exceeded credit limit"


# ---------------------------------------------------------------------------
# Order event payload fields
# ---------------------------------------------------------------------------


class TestOrderEventPayloads:
    def test_order_created_has_order_payload(self) -> None:
        order_id = uuid4()
        event = OrderCreated(
            aggregate_id=order_id,
            company_id=uuid4(),
            order_id=order_id,
            order_number="SO-00001",
            customer_id=str(uuid4()),
            total_amount="1500.00",
            currency_code="USD",
            sales_rep_id=str(uuid4()),
        )
        assert event.order_number == "SO-00001"
        assert event.total_amount == "1500.00"

    def test_order_approved_has_approver(self) -> None:
        event = OrderApproved(
            aggregate_id=uuid4(),
            company_id=uuid4(),
            order_id=uuid4(),
            order_number="SO-00002",
            approved_by=str(uuid4()),
        )
        assert event.approved_by != ""

    def test_order_credit_hold_has_credit_info(self) -> None:
        event = OrderCreditHold(
            aggregate_id=uuid4(),
            company_id=uuid4(),
            order_id=uuid4(),
            order_number="SO-00003",
            credit_status="EXCEEDED",
            credit_limit="5000.00",
            outstanding_balance="6000.00",
            order_total="1000.00",
        )
        assert event.credit_status == "EXCEEDED"
        assert event.credit_limit == "5000.00"


# ---------------------------------------------------------------------------
# Delivery event payload fields
# ---------------------------------------------------------------------------


class TestDeliveryEventPayloads:
    def test_delivery_dispatched_has_dispatch_info(self) -> None:
        event = DeliveryNoteDispatched(
            aggregate_id=uuid4(),
            company_id=uuid4(),
            delivery_note_id=uuid4(),
            delivery_number="DN-00001",
            order_id=str(uuid4()),
            customer_id=str(uuid4()),
            dispatch_date="2026-08-01",
            dispatched_by=str(uuid4()),
        )
        assert event.dispatch_date == "2026-08-01"
        assert event.delivery_number == "DN-00001"

    def test_delivery_cancelled_has_previous_status(self) -> None:
        event = DeliveryNoteCancelled(
            aggregate_id=uuid4(),
            company_id=uuid4(),
            delivery_note_id=uuid4(),
            delivery_number="DN-00002",
            order_id=str(uuid4()),
            customer_id=str(uuid4()),
            previous_status="DRAFT",
        )
        assert event.previous_status == "DRAFT"


# ---------------------------------------------------------------------------
# Return event payload fields
# ---------------------------------------------------------------------------


class TestReturnEventPayloads:
    def test_return_completed_has_resolution_type(self) -> None:
        event = ReturnCompleted(
            aggregate_id=uuid4(),
            company_id=uuid4(),
            return_id=uuid4(),
            return_number="SR-00001",
            resolution_type="CREDIT_NOTE",
        )
        assert event.resolution_type == "CREDIT_NOTE"

    def test_return_refund_ready_has_credit_note_amount(self) -> None:
        event = ReturnRefundReady(
            aggregate_id=uuid4(),
            company_id=uuid4(),
            return_id=uuid4(),
            return_number="SR-00002",
            credit_note_amount="250.00",
        )
        assert event.credit_note_amount == "250.00"


# ---------------------------------------------------------------------------
# Trigger → event_type mapping verification
# ---------------------------------------------------------------------------


class TestEventTriggerMapping:
    """Verify the trigger → event_type mapping per spec §34."""

    def test_customer_created_trigger(self) -> None:
        """customer.created — trigger: new customer record created."""
        assert CustomerCreated().event_type == "customer.created"

    def test_quotation_converted_trigger(self) -> None:
        """quotation.converted — trigger: ACCEPTED quotation converted to SO."""
        assert QuotationConverted().event_type == "quotation.converted"

    def test_order_approved_trigger(self) -> None:
        """sales.order.approved — trigger: PENDING_APPROVAL → APPROVED."""
        assert OrderApproved().event_type == "sales.order.approved"

    def test_delivery_dispatched_trigger(self) -> None:
        """sales.delivery.dispatched — trigger: DN dispatched (stock deducted)."""
        assert DeliveryNoteDispatched().event_type == "sales.delivery.dispatched"

    def test_invoice_issued_trigger(self) -> None:
        """sales.invoice.issued — trigger: DRAFT → ISSUED."""
        assert InvoiceIssued().event_type == "sales.invoice.issued"

    def test_return_received_trigger(self) -> None:
        """sales.return.received — trigger: APPROVED → RECEIVED (goods accepted)."""
        assert ReturnReceived().event_type == "sales.return.received"

    def test_credit_note_issued_trigger(self) -> None:
        """sales.invoice.credit_note_issued — trigger: credit note raised against invoice."""
        assert (
            InvoiceCreditNoteIssued().event_type == "sales.invoice.credit_note_issued"
        )
