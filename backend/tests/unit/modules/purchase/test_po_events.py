"""Unit tests for PO domain events — Phase 5.

Tests:
  - All 7 events are instantiable via create()
  - All events are JSON-serialisable via to_dict()
  - Each event has the correct event_type
  - All events have aggregate_type = "PurchaseOrder"

Task: T143
"""

from __future__ import annotations

import json
from uuid import uuid4

from modules.purchase.events.po_events import (
    PurchaseOrderAmended,
    PurchaseOrderApproved,
    PurchaseOrderCancelled,
    PurchaseOrderClosed,
    PurchaseOrdered,
    PurchaseOrderFullyReceived,
    PurchaseOrderRejected,
)

COMPANY_ID = uuid4()
PO_ID = uuid4()
ACTOR_ID = uuid4()
SUPPLIER_ID = str(uuid4())


class TestPurchaseOrdered:
    def test_instantiate(self):
        ev = PurchaseOrdered.create(
            aggregate_id=PO_ID,
            company_id=COMPANY_ID,
            po_number="PO-2026-000001",
            supplier_id=SUPPLIER_ID,
            total="1250.00",
            actor_id=ACTOR_ID,
        )
        assert ev.event_type == "purchase.po.submitted"
        assert ev.aggregate_type == "PurchaseOrder"
        assert ev.po_number == "PO-2026-000001"
        assert ev.supplier_id == SUPPLIER_ID
        assert ev.total == "1250.00"

    def test_to_dict_json_serialisable(self):
        ev = PurchaseOrdered.create(
            aggregate_id=PO_ID,
            company_id=COMPANY_ID,
            po_number="PO-2026-000001",
            supplier_id=SUPPLIER_ID,
            total="500.00",
        )
        d = ev.to_dict()
        assert json.dumps(d)  # no exception
        assert d["event_type"] == "purchase.po.submitted"
        assert d["po_number"] == "PO-2026-000001"
        assert d["aggregate_id"] == str(PO_ID)


class TestPurchaseOrderApproved:
    def test_instantiate(self):
        ev = PurchaseOrderApproved.create(
            aggregate_id=PO_ID,
            company_id=COMPANY_ID,
            po_number="PO-2026-000001",
            supplier_id=SUPPLIER_ID,
            auto_approved=False,
            actor_id=ACTOR_ID,
        )
        assert ev.event_type == "purchase.po.approved"
        assert ev.auto_approved is False

    def test_auto_approved_flag(self):
        ev = PurchaseOrderApproved.create(
            aggregate_id=PO_ID,
            company_id=COMPANY_ID,
            po_number="PO-2026-000001",
            supplier_id=SUPPLIER_ID,
            auto_approved=True,
        )
        assert ev.auto_approved is True

    def test_to_dict_json_serialisable(self):
        ev = PurchaseOrderApproved.create(
            aggregate_id=PO_ID,
            company_id=COMPANY_ID,
            po_number="PO-2026-000001",
            supplier_id=SUPPLIER_ID,
        )
        assert json.dumps(ev.to_dict())


class TestPurchaseOrderRejected:
    def test_instantiate(self):
        ev = PurchaseOrderRejected.create(
            aggregate_id=PO_ID,
            company_id=COMPANY_ID,
            po_number="PO-2026-000001",
            rejection_reason="Budget exceeded",
            rejected_by=str(ACTOR_ID),
            actor_id=ACTOR_ID,
        )
        assert ev.event_type == "purchase.po.rejected"
        assert ev.rejection_reason == "Budget exceeded"

    def test_to_dict_json_serialisable(self):
        ev = PurchaseOrderRejected.create(
            aggregate_id=PO_ID,
            company_id=COMPANY_ID,
            po_number="PO-2026-000001",
            rejection_reason="reason",
            rejected_by=str(ACTOR_ID),
        )
        assert json.dumps(ev.to_dict())


class TestPurchaseOrderAmended:
    def test_instantiate(self):
        ev = PurchaseOrderAmended.create(
            aggregate_id=PO_ID,
            company_id=COMPANY_ID,
            po_number="PO-2026-000001",
            amendment_number=1,
            reason="Price correction",
            actor_id=ACTOR_ID,
        )
        assert ev.event_type == "purchase.po.amended"
        assert ev.amendment_number == 1
        assert ev.reason == "Price correction"

    def test_to_dict_json_serialisable(self):
        ev = PurchaseOrderAmended.create(
            aggregate_id=PO_ID,
            company_id=COMPANY_ID,
            po_number="PO-2026-000001",
            amendment_number=2,
            reason="qty change",
        )
        assert json.dumps(ev.to_dict())


class TestPurchaseOrderCancelled:
    def test_instantiate_with_reason(self):
        ev = PurchaseOrderCancelled.create(
            aggregate_id=PO_ID,
            company_id=COMPANY_ID,
            po_number="PO-2026-000001",
            cancellation_reason="Supplier unavailable",
            actor_id=ACTOR_ID,
        )
        assert ev.event_type == "purchase.po.cancelled"
        assert ev.cancellation_reason == "Supplier unavailable"

    def test_instantiate_without_reason(self):
        ev = PurchaseOrderCancelled.create(
            aggregate_id=PO_ID,
            company_id=COMPANY_ID,
            po_number="PO-2026-000001",
        )
        assert ev.cancellation_reason is None

    def test_to_dict_json_serialisable(self):
        ev = PurchaseOrderCancelled.create(
            aggregate_id=PO_ID,
            company_id=COMPANY_ID,
            po_number="PO-2026-000001",
        )
        assert json.dumps(ev.to_dict())


class TestPurchaseOrderClosed:
    def test_instantiate(self):
        ev = PurchaseOrderClosed.create(
            aggregate_id=PO_ID,
            company_id=COMPANY_ID,
            po_number="PO-2026-000001",
            final_status_before_close="FULLY_RECEIVED",
            actor_id=ACTOR_ID,
        )
        assert ev.event_type == "purchase.po.closed"
        assert ev.final_status_before_close == "FULLY_RECEIVED"

    def test_to_dict_json_serialisable(self):
        ev = PurchaseOrderClosed.create(
            aggregate_id=PO_ID,
            company_id=COMPANY_ID,
            po_number="PO-2026-000001",
            final_status_before_close="APPROVED",
        )
        assert json.dumps(ev.to_dict())


class TestPurchaseOrderFullyReceived:
    def test_instantiate(self):
        ev = PurchaseOrderFullyReceived.create(
            aggregate_id=PO_ID,
            company_id=COMPANY_ID,
            po_number="PO-2026-000001",
            supplier_id=SUPPLIER_ID,
            actor_id=ACTOR_ID,
        )
        assert ev.event_type == "purchase.po.fully_received"
        assert ev.supplier_id == SUPPLIER_ID

    def test_to_dict_json_serialisable(self):
        ev = PurchaseOrderFullyReceived.create(
            aggregate_id=PO_ID,
            company_id=COMPANY_ID,
            po_number="PO-2026-000001",
            supplier_id=SUPPLIER_ID,
        )
        assert json.dumps(ev.to_dict())


class TestAllEventsHaveCorrectAggregateType:
    def test_all_events_aggregate_type(self):
        events = [
            PurchaseOrdered.create(
                aggregate_id=PO_ID,
                company_id=COMPANY_ID,
                po_number="PO-001",
                supplier_id=SUPPLIER_ID,
                total="0",
            ),
            PurchaseOrderApproved.create(
                aggregate_id=PO_ID,
                company_id=COMPANY_ID,
                po_number="PO-001",
                supplier_id=SUPPLIER_ID,
            ),
            PurchaseOrderRejected.create(
                aggregate_id=PO_ID,
                company_id=COMPANY_ID,
                po_number="PO-001",
                rejection_reason="r",
                rejected_by="u",
            ),
            PurchaseOrderAmended.create(
                aggregate_id=PO_ID,
                company_id=COMPANY_ID,
                po_number="PO-001",
                amendment_number=1,
                reason="r",
            ),
            PurchaseOrderCancelled.create(
                aggregate_id=PO_ID,
                company_id=COMPANY_ID,
                po_number="PO-001",
            ),
            PurchaseOrderClosed.create(
                aggregate_id=PO_ID,
                company_id=COMPANY_ID,
                po_number="PO-001",
                final_status_before_close="APPROVED",
            ),
            PurchaseOrderFullyReceived.create(
                aggregate_id=PO_ID,
                company_id=COMPANY_ID,
                po_number="PO-001",
                supplier_id=SUPPLIER_ID,
            ),
        ]
        for ev in events:
            assert ev.aggregate_type == "PurchaseOrder", (
                f"{ev.__class__.__name__} has wrong aggregate_type"
            )
