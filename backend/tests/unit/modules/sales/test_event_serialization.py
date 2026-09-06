"""Unit tests: all sales domain events are JSON-serialisable with event_version.

Verifies T223 requirements:
  - Every event class can be instantiated with defaults
  - Every event has event_version >= 1
  - to_dict() returns a JSON-serialisable dict including event_version
  - event_type is set correctly (not empty, dot-notation)

Task: T223
Spec ref: specs/007-sales-management/spec.md §34 Domain Events
"""

from __future__ import annotations

import json
from uuid import uuid4

import pytest

from modules.sales.events import SalesDomainEvent
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
# All event classes under test — 44 concrete events
# ---------------------------------------------------------------------------

ALL_EVENT_CLASSES = [
    # Customer (11)
    CustomerCreated,
    CustomerActivated,
    CustomerUpdated,
    CustomerOnHold,
    CustomerHoldReleased,
    CustomerBlocked,
    CustomerUnblocked,
    CustomerDeactivated,
    CustomerCreditLimitChanged,
    CustomerCreditHoldPlaced,
    CustomerCreditHoldReleased,
    # Quotation (8)
    QuotationCreated,
    QuotationSent,
    QuotationAccepted,
    QuotationRejected,
    QuotationConverted,
    QuotationExpired,
    QuotationCancelled,
    QuotationExpiringSoon,
    # Order (10)
    OrderCreated,
    OrderSubmitted,
    OrderApproved,
    OrderRejected,
    OrderCancelled,
    OrderPartiallyDelivered,
    OrderDelivered,
    OrderInvoiced,
    OrderClosed,
    OrderCreditHold,
    # Delivery (4)
    DeliveryNoteCreated,
    DeliveryNoteDispatched,
    DeliveryNoteDelivered,
    DeliveryNoteCancelled,
    # Invoice (4)
    InvoiceCreated,
    InvoiceIssued,
    InvoiceCancelled,
    InvoiceCreditNoteIssued,
    # Return (7)
    ReturnCreated,
    ReturnSubmitted,
    ReturnApproved,
    ReturnRejected,
    ReturnReceived,
    ReturnCompleted,
    ReturnRefundReady,
]


# ---------------------------------------------------------------------------
# Parametrised tests
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("event_cls", ALL_EVENT_CLASSES, ids=lambda c: c.__name__)
class TestEventSerialization:
    def test_instantiable_with_defaults(self, event_cls: type) -> None:
        """Event can be instantiated using default field values."""
        event = event_cls()
        assert isinstance(event, SalesDomainEvent)

    def test_has_event_version(self, event_cls: type) -> None:
        """event_version field exists and is >= 1."""
        event = event_cls()
        assert hasattr(event, "event_version")
        assert event.event_version >= 1

    def test_event_type_is_dot_notation(self, event_cls: type) -> None:
        """event_type follows dot-notation convention."""
        event = event_cls()
        assert "." in event.event_type
        assert event.event_type.strip() != ""

    def test_to_dict_is_json_serialisable(self, event_cls: type) -> None:
        """to_dict() returns a dict that round-trips through json.dumps."""
        event = event_cls()
        d = event.to_dict()
        serialised = json.dumps(d)
        parsed = json.loads(serialised)
        assert parsed["event_type"] == event.event_type

    def test_to_dict_contains_event_version(self, event_cls: type) -> None:
        """to_dict() includes 'event_version' key."""
        event = event_cls()
        d = event.to_dict()
        assert "event_version" in d
        assert d["event_version"] >= 1

    def test_to_dict_contains_required_base_fields(self, event_cls: type) -> None:
        """to_dict() always contains all mandatory base fields."""
        event = event_cls()
        d = event.to_dict()
        required = {
            "event_id",
            "event_type",
            "event_version",
            "aggregate_type",
            "aggregate_id",
            "company_id",
            "occurred_at",
        }
        assert required.issubset(set(d.keys()))

    def test_event_id_is_uuid_string(self, event_cls: type) -> None:
        """event_id in to_dict() is a valid UUID string."""
        from uuid import UUID

        event = event_cls()
        d = event.to_dict()
        UUID(d["event_id"])  # raises ValueError if not a UUID

    def test_company_id_is_uuid_string(self, event_cls: type) -> None:
        """company_id in to_dict() is a valid UUID string."""
        from uuid import UUID

        event = event_cls()
        d = event.to_dict()
        UUID(d["company_id"])

    def test_occurred_at_is_iso_format(self, event_cls: type) -> None:
        """occurred_at in to_dict() is an ISO 8601 string."""
        from datetime import datetime

        event = event_cls()
        d = event.to_dict()
        # Should parse without raising
        datetime.fromisoformat(d["occurred_at"])


# ---------------------------------------------------------------------------
# Verify total event count
# ---------------------------------------------------------------------------


class TestEventInventory:
    def test_total_event_class_count(self) -> None:
        """We have at least 38 domain event classes defined."""
        assert len(ALL_EVENT_CLASSES) >= 38

    def test_all_event_types_are_unique(self) -> None:
        """No two event classes share the same event_type value."""
        types = [cls().event_type for cls in ALL_EVENT_CLASSES]
        assert len(types) == len(set(types)), f"Duplicate event_types: {types}"

    def test_base_class_event_version_default(self) -> None:
        """SalesDomainEvent base class has event_version defaulting to 1."""
        event = SalesDomainEvent(
            event_type="test.event",
            aggregate_type="Test",
            aggregate_id=uuid4(),
            company_id=uuid4(),
        )
        assert event.event_version == 1

    def test_custom_event_version(self) -> None:
        """event_version can be set to a custom value."""
        event = SalesDomainEvent(
            event_type="test.v2",
            aggregate_type="Test",
            aggregate_id=uuid4(),
            company_id=uuid4(),
            event_version=2,
        )
        assert event.event_version == 2
        assert event.to_dict()["event_version"] == 2
