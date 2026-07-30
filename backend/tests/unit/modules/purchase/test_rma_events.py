"""Unit tests for RMA domain events — T185.

Tests:
  - GoodsReturnInitiated: create(), to_dict(), event_type, aggregate_type
  - GoodsReturnApproved: create(), to_dict(), event_type, aggregate_type
  - GoodsReturned: create(), to_dict(), event_type, aggregate_type, total_returned
  - GoodsReturnCompleted: create(), to_dict(), credit_note_pending field

Task: T185
"""

from __future__ import annotations

import json
from uuid import uuid4

from modules.purchase.events.rma_events import (
    GoodsReturnApproved,
    GoodsReturnCompleted,
    GoodsReturned,
    GoodsReturnInitiated,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

AGGREGATE_ID = uuid4()
COMPANY_ID = uuid4()
GR_ID = str(uuid4())
SUPPLIER_ID = str(uuid4())
ACTOR_ID = uuid4()
RMA_NUMBER = "RMA-2026-000001"


class TestGoodsReturnInitiated:
    def test_create_instantiates(self):
        evt = GoodsReturnInitiated.create(
            aggregate_id=AGGREGATE_ID,
            company_id=COMPANY_ID,
            rma_number=RMA_NUMBER,
            gr_id=GR_ID,
            supplier_id=SUPPLIER_ID,
            actor_id=ACTOR_ID,
        )
        assert evt.rma_number == RMA_NUMBER
        assert evt.gr_id == GR_ID
        assert evt.supplier_id == SUPPLIER_ID
        assert evt.actor_id == str(ACTOR_ID)

    def test_event_type(self):
        evt = GoodsReturnInitiated.create(
            aggregate_id=AGGREGATE_ID,
            company_id=COMPANY_ID,
            rma_number=RMA_NUMBER,
            gr_id=GR_ID,
            supplier_id=SUPPLIER_ID,
        )
        assert evt.event_type == "purchase.rma.initiated"

    def test_aggregate_type(self):
        evt = GoodsReturnInitiated.create(
            aggregate_id=AGGREGATE_ID,
            company_id=COMPANY_ID,
            rma_number=RMA_NUMBER,
            gr_id=GR_ID,
            supplier_id=SUPPLIER_ID,
        )
        assert evt.aggregate_type == "VendorReturn"

    def test_to_dict_json_serialisable(self):
        evt = GoodsReturnInitiated.create(
            aggregate_id=AGGREGATE_ID,
            company_id=COMPANY_ID,
            rma_number=RMA_NUMBER,
            gr_id=GR_ID,
            supplier_id=SUPPLIER_ID,
        )
        d = evt.to_dict()
        assert json.dumps(d)  # must not raise
        assert d["rma_number"] == RMA_NUMBER

    def test_actor_id_none(self):
        evt = GoodsReturnInitiated.create(
            aggregate_id=AGGREGATE_ID,
            company_id=COMPANY_ID,
            rma_number=RMA_NUMBER,
            gr_id=GR_ID,
            supplier_id=SUPPLIER_ID,
            actor_id=None,
        )
        assert evt.actor_id is None


class TestGoodsReturnApproved:
    def test_create_and_to_dict(self):
        evt = GoodsReturnApproved.create(
            aggregate_id=AGGREGATE_ID,
            company_id=COMPANY_ID,
            rma_number=RMA_NUMBER,
            gr_id=GR_ID,
            supplier_id=SUPPLIER_ID,
        )
        d = evt.to_dict()
        assert evt.event_type == "purchase.rma.approved"
        assert evt.aggregate_type == "VendorReturn"
        assert json.dumps(d)
        assert d["rma_number"] == RMA_NUMBER


class TestGoodsReturned:
    def test_create_with_total_returned(self):
        evt = GoodsReturned.create(
            aggregate_id=AGGREGATE_ID,
            company_id=COMPANY_ID,
            rma_number=RMA_NUMBER,
            gr_id=GR_ID,
            supplier_id=SUPPLIER_ID,
            total_returned="12.500",
        )
        assert evt.event_type == "purchase.rma.dispatched"
        assert evt.total_returned == "12.500"

    def test_to_dict_has_total_returned(self):
        evt = GoodsReturned.create(
            aggregate_id=AGGREGATE_ID,
            company_id=COMPANY_ID,
            rma_number=RMA_NUMBER,
            gr_id=GR_ID,
            supplier_id=SUPPLIER_ID,
            total_returned="3.000",
        )
        d = evt.to_dict()
        assert d["total_returned"] == "3.000"
        assert json.dumps(d)


class TestGoodsReturnCompleted:
    def test_create_with_credit_note_pending(self):
        evt = GoodsReturnCompleted.create(
            aggregate_id=AGGREGATE_ID,
            company_id=COMPANY_ID,
            rma_number=RMA_NUMBER,
            gr_id=GR_ID,
            supplier_id=SUPPLIER_ID,
            credit_note_pending=True,
        )
        assert evt.event_type == "purchase.rma.completed"
        assert evt.credit_note_pending is True

    def test_to_dict_has_credit_note_pending(self):
        evt = GoodsReturnCompleted.create(
            aggregate_id=AGGREGATE_ID,
            company_id=COMPANY_ID,
            rma_number=RMA_NUMBER,
            gr_id=GR_ID,
            supplier_id=SUPPLIER_ID,
        )
        d = evt.to_dict()
        assert d["credit_note_pending"] is True
        assert json.dumps(d)
