"""Unit tests for Purchase Request domain events — T115.

Tests:
  - Each event has the correct event_type
  - Each event has aggregate_type == "PurchaseRequest"
  - create() factory sets all fields correctly
  - to_dict() includes event-specific fields
  - Events inherit from PurchaseDomainEvent

Task: T115
Spec ref: specs/006-purchase-management/spec.md §33 Domain Events
"""

from __future__ import annotations

from uuid import uuid4

from modules.purchase.events import PurchaseDomainEvent
from modules.purchase.events.pr_events import (
    PurchaseRequestApproved,
    PurchaseRequestCancelled,
    PurchaseRequestConvertedToPO,
    PurchaseRequestCreated,
    PurchaseRequestRejected,
    PurchaseRequestSubmitted,
)


class TestPurchaseRequestCreated:
    def test_event_type(self):
        event = PurchaseRequestCreated.create(
            aggregate_id=uuid4(),
            company_id=uuid4(),
            pr_number="PR-2026-000001",
            title="Office Supplies",
            requestor_id=str(uuid4()),
        )
        assert event.event_type == "purchase_request.created"

    def test_aggregate_type(self):
        event = PurchaseRequestCreated.create(
            aggregate_id=uuid4(),
            company_id=uuid4(),
            pr_number="PR-2026-000001",
            title="Office Supplies",
            requestor_id=str(uuid4()),
        )
        assert event.aggregate_type == "PurchaseRequest"

    def test_inherits_purchase_domain_event(self):
        event = PurchaseRequestCreated.create(
            aggregate_id=uuid4(),
            company_id=uuid4(),
            pr_number="PR-2026-000001",
            title="Test",
            requestor_id=str(uuid4()),
        )
        assert isinstance(event, PurchaseDomainEvent)

    def test_to_dict_includes_pr_number(self):
        event = PurchaseRequestCreated.create(
            aggregate_id=uuid4(),
            company_id=uuid4(),
            pr_number="PR-2026-000042",
            title="Chemicals",
            requestor_id=str(uuid4()),
            department="Lab",
        )
        d = event.to_dict()
        assert d["pr_number"] == "PR-2026-000042"
        assert d["title"] == "Chemicals"
        assert d["department"] == "Lab"


class TestPurchaseRequestSubmitted:
    def test_event_type(self):
        event = PurchaseRequestSubmitted.create(
            aggregate_id=uuid4(),
            company_id=uuid4(),
            pr_number="PR-2026-000001",
            requestor_id=str(uuid4()),
        )
        assert event.event_type == "purchase_request.submitted"

    def test_to_dict_includes_requestor(self):
        rid = str(uuid4())
        event = PurchaseRequestSubmitted.create(
            aggregate_id=uuid4(),
            company_id=uuid4(),
            pr_number="PR-2026-000001",
            requestor_id=rid,
        )
        d = event.to_dict()
        assert d["requestor_id"] == rid


class TestPurchaseRequestApproved:
    def test_event_type(self):
        event = PurchaseRequestApproved.create(
            aggregate_id=uuid4(),
            company_id=uuid4(),
            pr_number="PR-2026-000001",
        )
        assert event.event_type == "purchase_request.approved"

    def test_auto_approved_false_by_default(self):
        event = PurchaseRequestApproved.create(
            aggregate_id=uuid4(),
            company_id=uuid4(),
            pr_number="PR-2026-000001",
        )
        assert event.auto_approved is False

    def test_auto_approved_flag(self):
        event = PurchaseRequestApproved.create(
            aggregate_id=uuid4(),
            company_id=uuid4(),
            pr_number="PR-2026-000001",
            auto_approved=True,
        )
        assert event.auto_approved is True
        assert event.to_dict()["auto_approved"] is True


class TestPurchaseRequestRejected:
    def test_event_type(self):
        event = PurchaseRequestRejected.create(
            aggregate_id=uuid4(),
            company_id=uuid4(),
            pr_number="PR-2026-000001",
            rejection_reason="No budget.",
            rejected_by=str(uuid4()),
        )
        assert event.event_type == "purchase_request.rejected"

    def test_to_dict_includes_reason(self):
        event = PurchaseRequestRejected.create(
            aggregate_id=uuid4(),
            company_id=uuid4(),
            pr_number="PR-2026-000001",
            rejection_reason="Over budget.",
            rejected_by=str(uuid4()),
        )
        d = event.to_dict()
        assert d["rejection_reason"] == "Over budget."


class TestPurchaseRequestCancelled:
    def test_event_type(self):
        event = PurchaseRequestCancelled.create(
            aggregate_id=uuid4(),
            company_id=uuid4(),
            pr_number="PR-2026-000001",
        )
        assert event.event_type == "purchase_request.cancelled"

    def test_cancellation_reason_optional(self):
        event = PurchaseRequestCancelled.create(
            aggregate_id=uuid4(),
            company_id=uuid4(),
            pr_number="PR-2026-000001",
        )
        assert event.cancellation_reason is None


class TestPurchaseRequestConvertedToPO:
    def test_event_type(self):
        event = PurchaseRequestConvertedToPO.create(
            aggregate_id=uuid4(),
            company_id=uuid4(),
            pr_number="PR-2026-000001",
            po_id=str(uuid4()),
            po_number="PO-2026-000001",
        )
        assert event.event_type == "purchase_request.converted_to_po"

    def test_to_dict_includes_po_number(self):
        po_num = "PO-2026-000007"
        event = PurchaseRequestConvertedToPO.create(
            aggregate_id=uuid4(),
            company_id=uuid4(),
            pr_number="PR-2026-000001",
            po_id=str(uuid4()),
            po_number=po_num,
        )
        d = event.to_dict()
        assert d["po_number"] == po_num
