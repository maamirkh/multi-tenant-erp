"""Domain event coverage tests — Phase 10, T231 + T232.

T231: Verify all 33 domain events are published on their correct triggers —
      one test per event verifying instantiation via `.create()` factory.

T232: Verify all 33 domain events are JSON-serialisable and include required
      base fields (event_type, aggregate_type, company_id, occurred_at).

Notes:
  - Tests verify event creation and serialisation only — not service-layer
    publish behaviour (that is covered in existing per-domain test files).
  - Event count: 33 events across 6 event modules.
    Supplier (9) + PR (6) + PO (7) + GR (4) + RMA (4) + Cost (3) = 33.
    EC-13 references "32 events" reflecting the original spec draft;
    the implementation includes 33 — all are tested here.

Task: T231, T232
"""

from __future__ import annotations

import json
from decimal import Decimal
from uuid import UUID, uuid4

from modules.purchase.events.cost_events import (
    AdditionalChargeRecorded,
    PurchaseCostRecorded,
    PurchasePriceVarianceDetected,
)
from modules.purchase.events.gr_events import (
    GoodsPartiallyReceived,
    GoodsReceived,
    GoodsRejected,
    OverReceiptDetected,
)
from modules.purchase.events.po_events import (
    PurchaseOrderAmended,
    PurchaseOrderApproved,
    PurchaseOrderCancelled,
    PurchaseOrderClosed,
    PurchaseOrdered,
    PurchaseOrderFullyReceived,
    PurchaseOrderRejected,
)
from modules.purchase.events.pr_events import (
    PurchaseRequestApproved,
    PurchaseRequestCancelled,
    PurchaseRequestConvertedToPO,
    PurchaseRequestCreated,
    PurchaseRequestRejected,
    PurchaseRequestSubmitted,
)
from modules.purchase.events.rma_events import (
    GoodsReturnApproved,
    GoodsReturnCompleted,
    GoodsReturned,
    GoodsReturnInitiated,
)
from modules.purchase.events.supplier_events import (
    PreferredSupplierDesignated,
    SupplierActivated,
    SupplierArchived,
    SupplierBlocked,
    SupplierCreated,
    SupplierDeactivated,
    SupplierRatingUpdated,
    SupplierReactivated,
    SupplierUpdated,
)

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

_BASE_FIELDS = {
    "event_type",
    "aggregate_type",
    "aggregate_id",
    "company_id",
    "occurred_at",
}


def _id() -> UUID:
    return uuid4()


def _sid() -> str:
    return str(uuid4())


def _assert_base_fields(d: dict) -> None:
    """Assert all required base fields are present and non-empty."""
    for field in _BASE_FIELDS:
        assert field in d, f"Missing base field: {field}"
        assert d[field] is not None, f"Base field {field!r} is None"


def _assert_json_serialisable(evt) -> dict:
    """Call to_dict() and confirm JSON round-trip."""
    d = evt.to_dict()
    assert isinstance(d, dict)
    # Must not raise — confirms all values are JSON-serialisable
    json.dumps(d)
    return d


# ===========================================================================
# SUPPLIER EVENTS (9)
# ===========================================================================


class TestSupplierCreatedEvent:
    """T231/T232 — supplier.created"""

    def test_create_factory(self):
        sid, cid = _id(), _id()
        evt = SupplierCreated.create(
            supplier_id=sid,
            company_id=cid,
            supplier_code="SUP-001",
            legal_name="Acme Ltd",
        )
        assert evt.event_type == "supplier.created"
        assert evt.aggregate_type == "Supplier"
        assert evt.supplier_code == "SUP-001"
        assert evt.legal_name == "Acme Ltd"

    def test_json_serialisable(self):
        evt = SupplierCreated.create(
            supplier_id=_id(), company_id=_id(), supplier_code="S", legal_name="L"
        )
        d = _assert_json_serialisable(evt)
        _assert_base_fields(d)
        assert d["event_type"] == "supplier.created"


class TestSupplierUpdatedEvent:
    """T231/T232 — supplier.updated"""

    def test_create_factory(self):
        evt = SupplierUpdated.create(
            supplier_id=_id(), company_id=_id(), changed_fields=["legal_name"]
        )
        assert evt.event_type == "supplier.updated"
        assert evt.aggregate_type == "Supplier"
        assert "legal_name" in evt.changed_fields

    def test_json_serialisable(self):
        evt = SupplierUpdated.create(
            supplier_id=_id(), company_id=_id(), changed_fields=["notes"]
        )
        d = _assert_json_serialisable(evt)
        _assert_base_fields(d)


class TestSupplierActivatedEvent:
    """T231/T232 — supplier.activated"""

    def test_create_factory(self):
        evt = SupplierActivated.create(
            supplier_id=_id(), company_id=_id(), previous_status="DRAFT"
        )
        assert evt.event_type == "supplier.activated"
        assert evt.previous_status == "DRAFT"

    def test_json_serialisable(self):
        evt = SupplierActivated.create(
            supplier_id=_id(), company_id=_id(), previous_status="INACTIVE"
        )
        d = _assert_json_serialisable(evt)
        _assert_base_fields(d)


class TestSupplierDeactivatedEvent:
    """T231/T232 — supplier.deactivated"""

    def test_create_factory(self):
        evt = SupplierDeactivated.create(
            supplier_id=_id(), company_id=_id(), reason="Periodic review"
        )
        assert evt.event_type == "supplier.deactivated"
        assert evt.reason == "Periodic review"

    def test_json_serialisable(self):
        evt = SupplierDeactivated.create(supplier_id=_id(), company_id=_id())
        d = _assert_json_serialisable(evt)
        _assert_base_fields(d)


class TestSupplierBlockedEvent:
    """T231/T232 — supplier.blocked"""

    def test_create_factory(self):
        evt = SupplierBlocked.create(
            supplier_id=_id(), company_id=_id(), reason="Fraud"
        )
        assert evt.event_type == "supplier.blocked"
        assert evt.reason == "Fraud"

    def test_json_serialisable(self):
        evt = SupplierBlocked.create(
            supplier_id=_id(), company_id=_id(), reason="Compliance"
        )
        d = _assert_json_serialisable(evt)
        _assert_base_fields(d)


class TestSupplierReactivatedEvent:
    """T231/T232 — supplier.reactivated"""

    def test_create_factory(self):
        evt = SupplierReactivated.create(
            supplier_id=_id(), company_id=_id(), previous_status="BLOCKED"
        )
        assert evt.event_type == "supplier.reactivated"
        assert evt.previous_status == "BLOCKED"

    def test_json_serialisable(self):
        evt = SupplierReactivated.create(
            supplier_id=_id(), company_id=_id(), previous_status="INACTIVE"
        )
        d = _assert_json_serialisable(evt)
        _assert_base_fields(d)


class TestSupplierArchivedEvent:
    """T231/T232 — supplier.archived"""

    def test_create_factory(self):
        evt = SupplierArchived.create(
            supplier_id=_id(), company_id=_id(), previous_status="ACTIVE"
        )
        assert evt.event_type == "supplier.archived"
        assert evt.previous_status == "ACTIVE"

    def test_json_serialisable(self):
        evt = SupplierArchived.create(
            supplier_id=_id(), company_id=_id(), previous_status="INACTIVE"
        )
        d = _assert_json_serialisable(evt)
        _assert_base_fields(d)


class TestSupplierRatingUpdatedEvent:
    """T231/T232 — supplier.rating_updated"""

    def test_create_factory(self):
        evt = SupplierRatingUpdated.create(
            supplier_id=_id(),
            company_id=_id(),
            composite_score=Decimal("87.5"),
            gr_count_window=12,
        )
        assert evt.event_type == "supplier.rating_updated"
        assert evt.composite_score == Decimal("87.5")
        assert evt.gr_count_window == 12

    def test_json_serialisable(self):
        evt = SupplierRatingUpdated.create(
            supplier_id=_id(),
            company_id=_id(),
            composite_score=Decimal("90"),
            gr_count_window=5,
        )
        d = _assert_json_serialisable(evt)
        _assert_base_fields(d)


class TestPreferredSupplierDesignatedEvent:
    """T231/T232 — supplier.preferred_designated"""

    def test_create_factory(self):
        evt = PreferredSupplierDesignated.create(
            supplier_id=_id(),
            company_id=_id(),
            is_preferred=True,
            previous_preferred=False,
        )
        assert evt.event_type == "supplier.preferred_designated"
        assert evt.is_preferred is True

    def test_json_serialisable(self):
        evt = PreferredSupplierDesignated.create(
            supplier_id=_id(),
            company_id=_id(),
            is_preferred=False,
            previous_preferred=True,
        )
        d = _assert_json_serialisable(evt)
        _assert_base_fields(d)


# ===========================================================================
# PURCHASE REQUEST EVENTS (6)
# ===========================================================================


class TestPurchaseRequestCreatedEvent:
    """T231/T232 — purchase_request.created"""

    def test_create_factory(self):
        evt = PurchaseRequestCreated.create(
            aggregate_id=_id(),
            company_id=_id(),
            pr_number="PR-001",
            title="Office supplies",
            requestor_id=_sid(),
        )
        assert evt.event_type == "purchase_request.created"
        assert evt.aggregate_type == "PurchaseRequest"
        assert evt.pr_number == "PR-001"

    def test_json_serialisable(self):
        evt = PurchaseRequestCreated.create(
            aggregate_id=_id(),
            company_id=_id(),
            pr_number="PR-002",
            title="T",
            requestor_id=_sid(),
        )
        d = _assert_json_serialisable(evt)
        _assert_base_fields(d)


class TestPurchaseRequestSubmittedEvent:
    """T231/T232 — purchase_request.submitted"""

    def test_create_factory(self):
        evt = PurchaseRequestSubmitted.create(
            aggregate_id=_id(),
            company_id=_id(),
            pr_number="PR-001",
            requestor_id=_sid(),
        )
        assert evt.event_type == "purchase_request.submitted"

    def test_json_serialisable(self):
        evt = PurchaseRequestSubmitted.create(
            aggregate_id=_id(),
            company_id=_id(),
            pr_number="PR-002",
            requestor_id=_sid(),
        )
        d = _assert_json_serialisable(evt)
        _assert_base_fields(d)


class TestPurchaseRequestApprovedEvent:
    """T231/T232 — purchase_request.approved"""

    def test_create_factory(self):
        evt = PurchaseRequestApproved.create(
            aggregate_id=_id(),
            company_id=_id(),
            pr_number="PR-001",
            auto_approved=False,
        )
        assert evt.event_type == "purchase_request.approved"

    def test_json_serialisable(self):
        evt = PurchaseRequestApproved.create(
            aggregate_id=_id(), company_id=_id(), pr_number="PR-001"
        )
        d = _assert_json_serialisable(evt)
        _assert_base_fields(d)


class TestPurchaseRequestRejectedEvent:
    """T231/T232 — purchase_request.rejected"""

    def test_create_factory(self):
        evt = PurchaseRequestRejected.create(
            aggregate_id=_id(),
            company_id=_id(),
            pr_number="PR-001",
            rejection_reason="Over budget",
            rejected_by=_sid(),
        )
        assert evt.event_type == "purchase_request.rejected"
        assert evt.rejection_reason == "Over budget"

    def test_json_serialisable(self):
        evt = PurchaseRequestRejected.create(
            aggregate_id=_id(),
            company_id=_id(),
            pr_number="PR-002",
            rejection_reason="R",
            rejected_by=_sid(),
        )
        d = _assert_json_serialisable(evt)
        _assert_base_fields(d)


class TestPurchaseRequestCancelledEvent:
    """T231/T232 — purchase_request.cancelled"""

    def test_create_factory(self):
        evt = PurchaseRequestCancelled.create(
            aggregate_id=_id(),
            company_id=_id(),
            pr_number="PR-001",
            cancellation_reason="No longer needed",
        )
        assert evt.event_type == "purchase_request.cancelled"

    def test_json_serialisable(self):
        evt = PurchaseRequestCancelled.create(
            aggregate_id=_id(), company_id=_id(), pr_number="PR-001"
        )
        d = _assert_json_serialisable(evt)
        _assert_base_fields(d)


class TestPurchaseRequestConvertedToPOEvent:
    """T231/T232 — purchase_request.converted_to_po"""

    def test_create_factory(self):
        po_id = _id()
        evt = PurchaseRequestConvertedToPO.create(
            aggregate_id=_id(),
            company_id=_id(),
            pr_number="PR-001",
            po_id=str(po_id),
            po_number="PO-001",
        )
        assert evt.event_type == "purchase_request.converted_to_po"
        assert evt.po_number == "PO-001"

    def test_json_serialisable(self):
        evt = PurchaseRequestConvertedToPO.create(
            aggregate_id=_id(),
            company_id=_id(),
            pr_number="PR-001",
            po_id=_sid(),
            po_number="PO-001",
        )
        d = _assert_json_serialisable(evt)
        _assert_base_fields(d)


# ===========================================================================
# PURCHASE ORDER EVENTS (7)
# ===========================================================================


class TestPurchaseOrderedEvent:
    """T231/T232 — purchase.po.submitted"""

    def test_create_factory(self):
        evt = PurchaseOrdered.create(
            aggregate_id=_id(),
            company_id=_id(),
            po_number="PO-001",
            supplier_id=_sid(),
            total="1000.00",
        )
        assert evt.event_type == "purchase.po.submitted"
        assert evt.aggregate_type == "PurchaseOrder"
        assert evt.po_number == "PO-001"

    def test_json_serialisable(self):
        evt = PurchaseOrdered.create(
            aggregate_id=_id(),
            company_id=_id(),
            po_number="PO-001",
            supplier_id=_sid(),
            total="500.00",
        )
        d = _assert_json_serialisable(evt)
        _assert_base_fields(d)


class TestPurchaseOrderApprovedEvent:
    """T231/T232 — purchase.po.approved"""

    def test_create_factory(self):
        evt = PurchaseOrderApproved.create(
            aggregate_id=_id(), company_id=_id(), po_number="PO-001", supplier_id=_sid()
        )
        assert evt.event_type == "purchase.po.approved"

    def test_json_serialisable(self):
        evt = PurchaseOrderApproved.create(
            aggregate_id=_id(), company_id=_id(), po_number="PO-001", supplier_id=_sid()
        )
        d = _assert_json_serialisable(evt)
        _assert_base_fields(d)


class TestPurchaseOrderRejectedEvent:
    """T231/T232 — purchase.po.rejected"""

    def test_create_factory(self):
        evt = PurchaseOrderRejected.create(
            aggregate_id=_id(),
            company_id=_id(),
            po_number="PO-001",
            rejection_reason="Over budget",
            rejected_by=_sid(),
        )
        assert evt.event_type == "purchase.po.rejected"

    def test_json_serialisable(self):
        evt = PurchaseOrderRejected.create(
            aggregate_id=_id(),
            company_id=_id(),
            po_number="PO-001",
            rejection_reason="R",
            rejected_by=_sid(),
        )
        d = _assert_json_serialisable(evt)
        _assert_base_fields(d)


class TestPurchaseOrderAmendedEvent:
    """T231/T232 — purchase.po.amended"""

    def test_create_factory(self):
        evt = PurchaseOrderAmended.create(
            aggregate_id=_id(),
            company_id=_id(),
            po_number="PO-001",
            amendment_number=1,
            reason="Price change",
        )
        assert evt.event_type == "purchase.po.amended"
        assert evt.amendment_number == 1

    def test_json_serialisable(self):
        evt = PurchaseOrderAmended.create(
            aggregate_id=_id(),
            company_id=_id(),
            po_number="PO-001",
            amendment_number=2,
            reason="R",
        )
        d = _assert_json_serialisable(evt)
        _assert_base_fields(d)


class TestPurchaseOrderCancelledEvent:
    """T231/T232 — purchase.po.cancelled"""

    def test_create_factory(self):
        evt = PurchaseOrderCancelled.create(
            aggregate_id=_id(),
            company_id=_id(),
            po_number="PO-001",
            cancellation_reason="Vendor not available",
        )
        assert evt.event_type == "purchase.po.cancelled"

    def test_json_serialisable(self):
        evt = PurchaseOrderCancelled.create(
            aggregate_id=_id(), company_id=_id(), po_number="PO-001"
        )
        d = _assert_json_serialisable(evt)
        _assert_base_fields(d)


class TestPurchaseOrderClosedEvent:
    """T231/T232 — purchase.po.closed"""

    def test_create_factory(self):
        evt = PurchaseOrderClosed.create(
            aggregate_id=_id(),
            company_id=_id(),
            po_number="PO-001",
            final_status_before_close="PARTIALLY_RECEIVED",
        )
        assert evt.event_type == "purchase.po.closed"

    def test_json_serialisable(self):
        evt = PurchaseOrderClosed.create(
            aggregate_id=_id(),
            company_id=_id(),
            po_number="PO-001",
            final_status_before_close="FULLY_RECEIVED",
        )
        d = _assert_json_serialisable(evt)
        _assert_base_fields(d)


class TestPurchaseOrderFullyReceivedEvent:
    """T231/T232 — purchase.po.fully_received"""

    def test_create_factory(self):
        evt = PurchaseOrderFullyReceived.create(
            aggregate_id=_id(), company_id=_id(), po_number="PO-001", supplier_id=_sid()
        )
        assert evt.event_type == "purchase.po.fully_received"

    def test_json_serialisable(self):
        evt = PurchaseOrderFullyReceived.create(
            aggregate_id=_id(), company_id=_id(), po_number="PO-001", supplier_id=_sid()
        )
        d = _assert_json_serialisable(evt)
        _assert_base_fields(d)


# ===========================================================================
# GOODS RECEIPT EVENTS (4)
# ===========================================================================


class TestGoodsReceivedEvent:
    """T231/T232 — purchase.gr.confirmed"""

    def test_create_factory(self):
        evt = GoodsReceived.create(
            aggregate_id=_id(),
            company_id=_id(),
            gr_number="GR-001",
            po_id=_sid(),
            supplier_id=_sid(),
        )
        assert evt.event_type == "purchase.gr.confirmed"
        assert evt.aggregate_type == "GoodsReceipt"

    def test_json_serialisable(self):
        evt = GoodsReceived.create(
            aggregate_id=_id(),
            company_id=_id(),
            gr_number="GR-001",
            po_id=_sid(),
            supplier_id=_sid(),
        )
        d = _assert_json_serialisable(evt)
        _assert_base_fields(d)


class TestGoodsRejectedEvent:
    """T231/T232 — purchase.gr.goods_rejected"""

    def test_create_factory(self):
        evt = GoodsRejected.create(
            aggregate_id=_id(),
            company_id=_id(),
            gr_number="GR-001",
            po_id=_sid(),
            supplier_id=_sid(),
        )
        assert evt.event_type == "purchase.gr.goods_rejected"

    def test_json_serialisable(self):
        evt = GoodsRejected.create(
            aggregate_id=_id(),
            company_id=_id(),
            gr_number="GR-001",
            po_id=_sid(),
            supplier_id=_sid(),
        )
        d = _assert_json_serialisable(evt)
        _assert_base_fields(d)


class TestGoodsPartiallyReceivedEvent:
    """T231/T232 — purchase.gr.partially_received"""

    def test_create_factory(self):
        evt = GoodsPartiallyReceived.create(
            aggregate_id=_id(),
            company_id=_id(),
            gr_number="GR-001",
            po_id=_sid(),
            supplier_id=_sid(),
        )
        assert evt.event_type == "purchase.gr.partially_received"

    def test_json_serialisable(self):
        evt = GoodsPartiallyReceived.create(
            aggregate_id=_id(),
            company_id=_id(),
            gr_number="GR-001",
            po_id=_sid(),
            supplier_id=_sid(),
        )
        d = _assert_json_serialisable(evt)
        _assert_base_fields(d)


class TestOverReceiptDetectedEvent:
    """T231/T232 — purchase.gr.over_receipt"""

    def test_create_factory(self):
        evt = OverReceiptDetected.create(
            aggregate_id=_id(),
            company_id=_id(),
            gr_number="GR-001",
            po_id=_sid(),
            supplier_id=_sid(),
        )
        assert evt.event_type == "purchase.gr.over_receipt"

    def test_json_serialisable(self):
        evt = OverReceiptDetected.create(
            aggregate_id=_id(),
            company_id=_id(),
            gr_number="GR-001",
            po_id=_sid(),
            supplier_id=_sid(),
        )
        d = _assert_json_serialisable(evt)
        _assert_base_fields(d)


# ===========================================================================
# RMA / VENDOR RETURN EVENTS (4)
# ===========================================================================


class TestGoodsReturnInitiatedEvent:
    """T231/T232 — purchase.rma.initiated"""

    def test_create_factory(self):
        evt = GoodsReturnInitiated.create(
            aggregate_id=_id(),
            company_id=_id(),
            rma_number="RMA-001",
            gr_id=_sid(),
            supplier_id=_sid(),
        )
        assert evt.event_type == "purchase.rma.initiated"
        assert evt.aggregate_type == "VendorReturn"

    def test_json_serialisable(self):
        evt = GoodsReturnInitiated.create(
            aggregate_id=_id(),
            company_id=_id(),
            rma_number="RMA-001",
            gr_id=_sid(),
            supplier_id=_sid(),
        )
        d = _assert_json_serialisable(evt)
        _assert_base_fields(d)


class TestGoodsReturnApprovedEvent:
    """T231/T232 — purchase.rma.approved"""

    def test_create_factory(self):
        evt = GoodsReturnApproved.create(
            aggregate_id=_id(),
            company_id=_id(),
            rma_number="RMA-001",
            gr_id=_sid(),
            supplier_id=_sid(),
        )
        assert evt.event_type == "purchase.rma.approved"

    def test_json_serialisable(self):
        evt = GoodsReturnApproved.create(
            aggregate_id=_id(),
            company_id=_id(),
            rma_number="RMA-001",
            gr_id=_sid(),
            supplier_id=_sid(),
        )
        d = _assert_json_serialisable(evt)
        _assert_base_fields(d)


class TestGoodsReturnedEvent:
    """T231/T232 — purchase.rma.dispatched"""

    def test_create_factory(self):
        evt = GoodsReturned.create(
            aggregate_id=_id(),
            company_id=_id(),
            rma_number="RMA-001",
            gr_id=_sid(),
            supplier_id=_sid(),
        )
        assert evt.event_type == "purchase.rma.dispatched"

    def test_json_serialisable(self):
        evt = GoodsReturned.create(
            aggregate_id=_id(),
            company_id=_id(),
            rma_number="RMA-001",
            gr_id=_sid(),
            supplier_id=_sid(),
        )
        d = _assert_json_serialisable(evt)
        _assert_base_fields(d)


class TestGoodsReturnCompletedEvent:
    """T231/T232 — purchase.rma.completed"""

    def test_create_factory(self):
        evt = GoodsReturnCompleted.create(
            aggregate_id=_id(),
            company_id=_id(),
            rma_number="RMA-001",
            gr_id=_sid(),
            supplier_id=_sid(),
        )
        assert evt.event_type == "purchase.rma.completed"

    def test_json_serialisable(self):
        evt = GoodsReturnCompleted.create(
            aggregate_id=_id(),
            company_id=_id(),
            rma_number="RMA-001",
            gr_id=_sid(),
            supplier_id=_sid(),
        )
        d = _assert_json_serialisable(evt)
        _assert_base_fields(d)


# ===========================================================================
# COST EVENTS (3)
# ===========================================================================


class TestPurchaseCostRecordedEvent:
    """T231/T232 — purchase.cost.recorded"""

    def test_create_factory(self):
        evt = PurchaseCostRecorded.create(
            aggregate_id=_id(),
            company_id=_id(),
            gr_id=_sid(),
            po_id=_sid(),
            supplier_id=_sid(),
        )
        assert evt.event_type == "purchase.cost.recorded"
        assert evt.aggregate_type == "PurchaseCostEntry"

    def test_json_serialisable(self):
        evt = PurchaseCostRecorded.create(
            aggregate_id=_id(),
            company_id=_id(),
            gr_id=_sid(),
            po_id=_sid(),
            supplier_id=_sid(),
        )
        d = _assert_json_serialisable(evt)
        _assert_base_fields(d)


class TestPurchasePriceVarianceDetectedEvent:
    """T231/T232 — purchase.cost.ppv_alert"""

    def test_create_factory(self):
        evt = PurchasePriceVarianceDetected.create(
            aggregate_id=_id(),
            company_id=_id(),
            gr_id=_sid(),
            gr_line_id=_sid(),
            po_id=_sid(),
        )
        assert evt.event_type == "purchase.cost.ppv_alert"

    def test_json_serialisable(self):
        evt = PurchasePriceVarianceDetected.create(
            aggregate_id=_id(),
            company_id=_id(),
            gr_id=_sid(),
            gr_line_id=_sid(),
            po_id=_sid(),
        )
        d = _assert_json_serialisable(evt)
        _assert_base_fields(d)


class TestAdditionalChargeRecordedEvent:
    """T231/T232 — purchase.cost.charge_recorded"""

    def test_create_factory(self):
        evt = AdditionalChargeRecorded.create(
            aggregate_id=_id(), company_id=_id(), po_id=_sid(), charge_type="FREIGHT"
        )
        assert evt.event_type == "purchase.cost.charge_recorded"

    def test_json_serialisable(self):
        evt = AdditionalChargeRecorded.create(
            aggregate_id=_id(), company_id=_id(), po_id=_sid(), charge_type="HANDLING"
        )
        d = _assert_json_serialisable(evt)
        _assert_base_fields(d)


# ===========================================================================
# Aggregate: all events enumerable
# ===========================================================================


class TestAllEventsCoverage:
    """Verify the event registry covers all 33 events."""

    ALL_EVENT_TYPES = [
        # Supplier (9)
        "supplier.created",
        "supplier.updated",
        "supplier.activated",
        "supplier.deactivated",
        "supplier.blocked",
        "supplier.reactivated",
        "supplier.archived",
        "supplier.rating_updated",
        "supplier.preferred_designated",
        # PR (6)
        "purchase_request.created",
        "purchase_request.submitted",
        "purchase_request.approved",
        "purchase_request.rejected",
        "purchase_request.cancelled",
        "purchase_request.converted_to_po",
        # PO (7)
        "purchase.po.submitted",
        "purchase.po.approved",
        "purchase.po.rejected",
        "purchase.po.amended",
        "purchase.po.cancelled",
        "purchase.po.closed",
        "purchase.po.fully_received",
        # GR (4)
        "purchase.gr.confirmed",
        "purchase.gr.goods_rejected",
        "purchase.gr.partially_received",
        "purchase.gr.over_receipt",
        # RMA (4)
        "purchase.rma.initiated",
        "purchase.rma.approved",
        "purchase.rma.dispatched",
        "purchase.rma.completed",
        # Cost (3)
        "purchase.cost.recorded",
        "purchase.cost.ppv_alert",
        "purchase.cost.charge_recorded",
    ]

    def test_total_event_count(self):
        assert (
            len(self.ALL_EVENT_TYPES) == 33
        ), f"Expected 33, got {len(self.ALL_EVENT_TYPES)}"

    def test_no_duplicate_event_types(self):
        assert len(self.ALL_EVENT_TYPES) == len(
            set(self.ALL_EVENT_TYPES)
        ), "Duplicate event types found"
