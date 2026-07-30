"""Unit tests for Purchase Costing domain events — Phase 8.

Tests:
  - All 3 events are instantiable via create()
  - All events are JSON-serialisable via to_dict()
  - event_type and aggregate_type match expected values

Task: T203
"""

from __future__ import annotations

import json
from uuid import uuid4

from modules.purchase.events.cost_events import (
    AdditionalChargeRecorded,
    PurchaseCostRecorded,
    PurchasePriceVarianceDetected,
)

COMPANY_ID = uuid4()
GR_ID = uuid4()
PO_ID = uuid4()
SUPPLIER_ID = uuid4()
ENTRY_ID = uuid4()
GR_LINE_ID = uuid4()
CHARGE_ID = uuid4()


# ---------------------------------------------------------------------------
# PurchaseCostRecorded
# ---------------------------------------------------------------------------


class TestPurchaseCostRecorded:
    def test_create(self):
        evt = PurchaseCostRecorded.create(
            aggregate_id=ENTRY_ID,
            company_id=COMPANY_ID,
            gr_id=str(GR_ID),
            po_id=str(PO_ID),
            supplier_id=str(SUPPLIER_ID),
            subtotal="500.00",
            total_charges="25.00",
            total_discounts="10.00",
            tax_amount="0.00",
            total="515.00",
        )

        assert evt.event_type == "purchase.cost.recorded"
        assert evt.aggregate_type == "PurchaseCostEntry"
        assert evt.gr_id == str(GR_ID)
        assert evt.po_id == str(PO_ID)
        assert evt.supplier_id == str(SUPPLIER_ID)
        assert evt.subtotal == "500.00"
        assert evt.total == "515.00"
        assert evt.aggregate_id == str(ENTRY_ID)
        assert evt.company_id == str(COMPANY_ID)

    def test_to_dict_is_json_serialisable(self):
        evt = PurchaseCostRecorded.create(
            aggregate_id=ENTRY_ID,
            company_id=COMPANY_ID,
            gr_id=str(GR_ID),
            po_id=str(PO_ID),
            supplier_id=str(SUPPLIER_ID),
            subtotal="200.00",
            total_charges="0.00",
            total_discounts="0.00",
            tax_amount="0.00",
            total="200.00",
        )

        d = evt.to_dict()
        serialised = json.dumps(d)
        parsed = json.loads(serialised)

        assert parsed["event_type"] == "purchase.cost.recorded"
        assert parsed["gr_id"] == str(GR_ID)
        assert parsed["total"] == "200.00"

    def test_occurred_at_in_dict(self):
        evt = PurchaseCostRecorded.create(
            aggregate_id=ENTRY_ID,
            company_id=COMPANY_ID,
            gr_id=str(GR_ID),
            po_id=str(PO_ID),
            supplier_id=str(SUPPLIER_ID),
        )
        d = evt.to_dict()
        assert "occurred_at" in d


# ---------------------------------------------------------------------------
# PurchasePriceVarianceDetected
# ---------------------------------------------------------------------------


class TestPurchasePriceVarianceDetected:
    def test_create(self):
        evt = PurchasePriceVarianceDetected.create(
            aggregate_id=GR_LINE_ID,
            company_id=COMPANY_ID,
            gr_id=str(GR_ID),
            gr_line_id=str(GR_LINE_ID),
            po_id=str(PO_ID),
            product_id=str(uuid4()),
            ppv_amount="20.00",
            ppv_percentage="20.0000",
            threshold_percent="5.00",
        )

        assert evt.event_type == "purchase.cost.ppv_alert"
        assert evt.aggregate_type == "GRLine"
        assert evt.ppv_amount == "20.00"
        assert evt.ppv_percentage == "20.0000"
        assert evt.threshold_percent == "5.00"

    def test_to_dict_is_json_serialisable(self):
        evt = PurchasePriceVarianceDetected.create(
            aggregate_id=GR_LINE_ID,
            company_id=COMPANY_ID,
            gr_id=str(GR_ID),
            gr_line_id=str(GR_LINE_ID),
            po_id=str(PO_ID),
            ppv_amount="-5.00",
            ppv_percentage="-10.0000",
            threshold_percent="5.00",
        )

        d = evt.to_dict()
        serialised = json.dumps(d)
        parsed = json.loads(serialised)

        assert parsed["event_type"] == "purchase.cost.ppv_alert"
        assert parsed["ppv_percentage"] == "-10.0000"

    def test_default_product_id_empty_string(self):
        evt = PurchasePriceVarianceDetected.create(
            aggregate_id=GR_LINE_ID,
            company_id=COMPANY_ID,
            gr_id=str(GR_ID),
            gr_line_id=str(GR_LINE_ID),
            po_id=str(PO_ID),
        )
        assert evt.product_id == ""


# ---------------------------------------------------------------------------
# AdditionalChargeRecorded
# ---------------------------------------------------------------------------


class TestAdditionalChargeRecorded:
    def test_create(self):
        evt = AdditionalChargeRecorded.create(
            aggregate_id=CHARGE_ID,
            company_id=COMPANY_ID,
            po_id=str(PO_ID),
            charge_type="FREIGHT",
            amount="50.00",
            description="Air freight surcharge",
        )

        assert evt.event_type == "purchase.cost.charge_recorded"
        assert evt.aggregate_type == "POAdditionalCharge"
        assert evt.charge_type == "FREIGHT"
        assert evt.amount == "50.00"
        assert evt.description == "Air freight surcharge"

    def test_to_dict_is_json_serialisable(self):
        evt = AdditionalChargeRecorded.create(
            aggregate_id=CHARGE_ID,
            company_id=COMPANY_ID,
            po_id=str(PO_ID),
            charge_type="HANDLING",
            amount="15.50",
        )

        d = evt.to_dict()
        serialised = json.dumps(d)
        parsed = json.loads(serialised)

        assert parsed["charge_type"] == "HANDLING"
        assert parsed["amount"] == "15.50"

    def test_default_description_empty(self):
        evt = AdditionalChargeRecorded.create(
            aggregate_id=CHARGE_ID,
            company_id=COMPANY_ID,
            po_id=str(PO_ID),
            charge_type="OTHER",
        )
        assert evt.description == ""
