"""Unit tests for GR domain events — Phase 6.

Tests:
  - All 4 events instantiable via create()
  - All events JSON-serialisable via to_dict()
  - Correct event_type and aggregate_type per event

Task: T165
"""

from __future__ import annotations

import json
from uuid import uuid4

from modules.purchase.events.gr_events import (
    GoodsPartiallyReceived,
    GoodsReceived,
    GoodsRejected,
    OverReceiptDetected,
)

COMPANY_ID = uuid4()
GR_ID = uuid4()
ACTOR_ID = uuid4()
PO_ID = str(uuid4())
SUPPLIER_ID = str(uuid4())
GR_NUMBER = "GR-2026-000001"


class TestGoodsReceived:
    def test_instantiate(self):
        ev = GoodsReceived.create(
            aggregate_id=GR_ID,
            company_id=COMPANY_ID,
            gr_number=GR_NUMBER,
            po_id=PO_ID,
            supplier_id=SUPPLIER_ID,
            total_received="10.000",
            actor_id=ACTOR_ID,
        )
        assert ev.event_type == "purchase.gr.confirmed"
        assert ev.aggregate_type == "GoodsReceipt"
        assert ev.gr_number == GR_NUMBER
        assert ev.total_received == "10.000"

    def test_to_dict_json_serialisable(self):
        ev = GoodsReceived.create(
            aggregate_id=GR_ID,
            company_id=COMPANY_ID,
            gr_number=GR_NUMBER,
            po_id=PO_ID,
            supplier_id=SUPPLIER_ID,
        )
        d = ev.to_dict()
        assert isinstance(d, dict)
        json_str = json.dumps(d)
        assert GR_NUMBER in json_str

    def test_aggregate_id_is_string(self):
        ev = GoodsReceived.create(
            aggregate_id=GR_ID,
            company_id=COMPANY_ID,
            gr_number=GR_NUMBER,
            po_id=PO_ID,
            supplier_id=SUPPLIER_ID,
        )
        assert isinstance(ev.aggregate_id, str)
        assert isinstance(ev.company_id, str)

    def test_no_actor_id(self):
        ev = GoodsReceived.create(
            aggregate_id=GR_ID,
            company_id=COMPANY_ID,
            gr_number=GR_NUMBER,
            po_id=PO_ID,
            supplier_id=SUPPLIER_ID,
        )
        assert ev.actor_id is None


class TestGoodsRejected:
    def test_instantiate(self):
        ev = GoodsRejected.create(
            aggregate_id=GR_ID,
            company_id=COMPANY_ID,
            gr_number=GR_NUMBER,
            po_id=PO_ID,
            supplier_id=SUPPLIER_ID,
            total_rejected="2.500",
        )
        assert ev.event_type == "purchase.gr.goods_rejected"
        assert ev.aggregate_type == "GoodsReceipt"
        assert ev.total_rejected == "2.500"

    def test_to_dict_contains_total_rejected(self):
        ev = GoodsRejected.create(
            aggregate_id=GR_ID,
            company_id=COMPANY_ID,
            gr_number=GR_NUMBER,
            po_id=PO_ID,
            supplier_id=SUPPLIER_ID,
            total_rejected="5.000",
        )
        d = ev.to_dict()
        assert d["total_rejected"] == "5.000"
        assert d["gr_number"] == GR_NUMBER


class TestGoodsPartiallyReceived:
    def test_instantiate(self):
        ev = GoodsPartiallyReceived.create(
            aggregate_id=GR_ID,
            company_id=COMPANY_ID,
            gr_number=GR_NUMBER,
            po_id=PO_ID,
            supplier_id=SUPPLIER_ID,
        )
        assert ev.event_type == "purchase.gr.partially_received"
        assert ev.aggregate_type == "GoodsReceipt"

    def test_to_dict_json_serialisable(self):
        ev = GoodsPartiallyReceived.create(
            aggregate_id=GR_ID,
            company_id=COMPANY_ID,
            gr_number=GR_NUMBER,
            po_id=PO_ID,
            supplier_id=SUPPLIER_ID,
            actor_id=ACTOR_ID,
        )
        d = ev.to_dict()
        json_str = json.dumps(d)
        assert "partially_received" in json_str


class TestOverReceiptDetected:
    def test_instantiate(self):
        ev = OverReceiptDetected.create(
            aggregate_id=GR_ID,
            company_id=COMPANY_ID,
            gr_number=GR_NUMBER,
            po_id=PO_ID,
            supplier_id=SUPPLIER_ID,
            over_received_lines=3,
        )
        assert ev.event_type == "purchase.gr.over_receipt"
        assert ev.aggregate_type == "GoodsReceipt"
        assert ev.over_received_lines == 3

    def test_to_dict_contains_over_received_lines(self):
        ev = OverReceiptDetected.create(
            aggregate_id=GR_ID,
            company_id=COMPANY_ID,
            gr_number=GR_NUMBER,
            po_id=PO_ID,
            supplier_id=SUPPLIER_ID,
            over_received_lines=2,
        )
        d = ev.to_dict()
        assert d["over_received_lines"] == 2

    def test_default_over_received_lines_is_zero(self):
        ev = OverReceiptDetected.create(
            aggregate_id=GR_ID,
            company_id=COMPANY_ID,
            gr_number=GR_NUMBER,
            po_id=PO_ID,
            supplier_id=SUPPLIER_ID,
        )
        assert ev.over_received_lines == 0
