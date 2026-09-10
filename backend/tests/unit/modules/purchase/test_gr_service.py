"""Unit tests for GRService — Phase 6.

Tests:
  - GR creation validates PO status (must be APPROVED or PARTIALLY_RECEIVED)
  - _assert_draft raises GRImmutableError on CONFIRMED GR
  - PPV computation with known values
  - Over-receipt policy: BLOCK raises GROverReceiptError
  - Over-receipt policy: WARN publishes OverReceiptDetected event
  - confirm_gr raises ConflictException when no lines
  - update_gr blocked on CONFIRMED GR

Task: T163
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from core.exceptions.base import ConflictException, NotFoundException
from modules.purchase.services.gr_service import (
    GRImmutableError,
    GRInvalidPOStatusError,
    GROverReceiptError,
    GRService,
    _compute_ppv,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


@dataclass
class _ServiceUnderTest:
    service: GRService
    gr_repo: MagicMock
    line_repo: MagicMock
    po_repo: MagicMock
    po_line_repo: MagicMock
    sequence_service: MagicMock


def _make_gr_service(db: MagicMock | None = None) -> _ServiceUnderTest:
    db = db or MagicMock()
    gr_repo = MagicMock()
    line_repo = MagicMock()
    po_repo = MagicMock()
    po_line_repo = MagicMock()
    sequence_service = MagicMock()
    svc = GRService(
        db=db,
        gr_repo=gr_repo,
        line_repo=line_repo,
        po_repo=po_repo,
        po_line_repo=po_line_repo,
        sequence_service=sequence_service,
    )
    return _ServiceUnderTest(
        service=svc,
        gr_repo=gr_repo,
        line_repo=line_repo,
        po_repo=po_repo,
        po_line_repo=po_line_repo,
        sequence_service=sequence_service,
    )


def _make_gr(status: str = "DRAFT") -> MagicMock:
    gr = MagicMock()
    gr.id = uuid4()
    gr.company_id = uuid4()
    gr.gr_number = "GR-2026-000001"
    gr.status = status
    gr.po_id = str(uuid4())
    gr.supplier_id = str(uuid4())
    gr.warehouse_id = None
    gr.received_at = None
    return gr


def _make_po(status: str = "APPROVED") -> MagicMock:
    po = MagicMock()
    po.id = uuid4()
    po.status = status
    po.supplier_id = str(uuid4())
    po.expected_delivery_date = None
    return po


def _make_gr_line(
    quantity_received: str = "10.000",
    quantity_rejected: str = "0.000",
    po_line_id: str | None = None,
    product_id: str | None = None,
) -> MagicMock:
    ln = MagicMock()
    ln.id = uuid4()
    ln.po_line_id = po_line_id or str(uuid4())
    ln.product_id = product_id
    ln.quantity_received = Decimal(quantity_received)
    ln.quantity_rejected = Decimal(quantity_rejected)
    ln.unit_cost = Decimal("100.0000")
    ln.po_unit_cost = Decimal("95.0000")
    ln.notes = None
    return ln


# ---------------------------------------------------------------------------
# T163a: _compute_ppv — PPV computation
# ---------------------------------------------------------------------------


class TestComputePPV:
    def test_positive_ppv_when_gr_cost_higher(self):
        ppv_amt, ppv_pct = _compute_ppv(
            unit_cost=Decimal("110"),
            po_unit_cost=Decimal("100"),
            quantity_received=Decimal("10"),
        )
        assert ppv_amt == Decimal("100.00")
        assert ppv_pct == Decimal("10.0000")

    def test_negative_ppv_when_gr_cost_lower(self):
        ppv_amt, ppv_pct = _compute_ppv(
            unit_cost=Decimal("90"),
            po_unit_cost=Decimal("100"),
            quantity_received=Decimal("5"),
        )
        assert ppv_amt == Decimal("-50.00")
        assert ppv_pct == Decimal("-10.0000")

    def test_zero_ppv_when_costs_equal(self):
        ppv_amt, ppv_pct = _compute_ppv(
            unit_cost=Decimal("100"),
            po_unit_cost=Decimal("100"),
            quantity_received=Decimal("100"),
        )
        assert ppv_amt == Decimal("0.00")
        assert ppv_pct == Decimal("0.0000")

    def test_zero_ppv_when_po_cost_zero(self):
        """When PO cost is zero, percentage should be 0 to avoid ZeroDivisionError."""
        ppv_amt, ppv_pct = _compute_ppv(
            unit_cost=Decimal("50"),
            po_unit_cost=Decimal("0"),
            quantity_received=Decimal("10"),
        )
        assert ppv_amt == Decimal("500.00")
        assert ppv_pct == Decimal("0.0000")  # base is zero


# ---------------------------------------------------------------------------
# T163b: _assert_draft — immutability guard
# ---------------------------------------------------------------------------


class TestAssertDraft:
    def test_draft_passes(self):
        m = _make_gr_service()
        gr = _make_gr(status="DRAFT")
        m.service._assert_draft(gr)  # should not raise

    def test_confirmed_raises_immutable_error(self):
        m = _make_gr_service()
        gr = _make_gr(status="CONFIRMED")
        with pytest.raises(GRImmutableError):
            m.service._assert_draft(gr)


# ---------------------------------------------------------------------------
# T163c: create_gr — PO status validation
# ---------------------------------------------------------------------------


class TestCreateGR:
    def test_invalid_po_status_raises_error(self):
        m = _make_gr_service()
        po = _make_po(status="DRAFT")
        m.po_repo.get_by_id_or_none.return_value = po

        from modules.purchase.schemas.goods_receipt import GoodsReceiptCreate

        payload = GoodsReceiptCreate(po_id=po.id, lines=[])

        with pytest.raises(GRInvalidPOStatusError):
            m.service.create_gr(payload=payload, company_id=uuid4(), user_id=uuid4())

    def test_closed_po_raises_error(self):
        m = _make_gr_service()
        po = _make_po(status="CLOSED")
        m.po_repo.get_by_id_or_none.return_value = po

        from modules.purchase.schemas.goods_receipt import GoodsReceiptCreate

        payload = GoodsReceiptCreate(po_id=po.id, lines=[])

        with pytest.raises(GRInvalidPOStatusError):
            m.service.create_gr(payload=payload, company_id=uuid4(), user_id=uuid4())

    def test_po_not_found_raises_404(self):
        m = _make_gr_service()
        m.po_repo.get_by_id_or_none.return_value = None

        from modules.purchase.schemas.goods_receipt import GoodsReceiptCreate

        payload = GoodsReceiptCreate(po_id=uuid4(), lines=[])

        with pytest.raises(NotFoundException):
            m.service.create_gr(payload=payload, company_id=uuid4(), user_id=uuid4())


# ---------------------------------------------------------------------------
# T163d: _validate_over_receipt — over-receipt policy
# ---------------------------------------------------------------------------


class TestOverReceiptPolicy:
    def _make_svc_with_open_qty(self, open_qty: Decimal) -> GRService:
        m = _make_gr_service()
        # Mock _compute_open_qty to return the given open_qty
        m.service._compute_open_qty = MagicMock(return_value=open_qty)
        m.service._get_po_line = MagicMock(
            return_value=MagicMock(quantity_ordered=Decimal("5"))
        )
        return m.service

    def test_block_policy_raises_when_over(self):
        svc = self._make_svc_with_open_qty(Decimal("5"))
        gr = _make_gr()
        ln = _make_gr_line(quantity_received="10.000")  # > 5

        with pytest.raises(GROverReceiptError):
            svc._validate_over_receipt(gr, [ln], policy="BLOCK")

    def test_block_policy_allows_when_within(self):
        svc = self._make_svc_with_open_qty(Decimal("15"))
        gr = _make_gr()
        ln = _make_gr_line(quantity_received="10.000")  # < 15

        # Should not raise
        svc._validate_over_receipt(gr, [ln], policy="BLOCK")

    def test_warn_policy_publishes_event(self):
        svc = self._make_svc_with_open_qty(Decimal("5"))
        gr = _make_gr()
        ln = _make_gr_line(quantity_received="10.000")  # > 5

        with patch("modules.purchase.services.gr_service.get_event_bus") as mock_bus:
            bus = MagicMock()
            mock_bus.return_value = bus
            svc._validate_over_receipt(gr, [ln], policy="WARN")
            bus.publish.assert_called_once()

    def test_allow_policy_allows_silently(self):
        svc = self._make_svc_with_open_qty(Decimal("5"))
        gr = _make_gr()
        ln = _make_gr_line(quantity_received="10.000")

        with patch("modules.purchase.services.gr_service.get_event_bus") as mock_bus:
            bus = MagicMock()
            mock_bus.return_value = bus
            svc._validate_over_receipt(gr, [ln], policy="ALLOW")
            bus.publish.assert_not_called()


# ---------------------------------------------------------------------------
# T163e: confirm_gr — no lines raises ConflictException
# ---------------------------------------------------------------------------


class TestConfirmGR:
    def test_no_lines_raises_conflict(self):
        m = _make_gr_service()
        gr = _make_gr(status="DRAFT")
        m.gr_repo.get_by_id_or_none.return_value = gr
        m.line_repo.list_for_gr.return_value = []  # no lines

        with pytest.raises(ConflictException):
            m.service.confirm_gr(gr_id=gr.id, company_id=gr.company_id, user_id=uuid4())

    def test_already_confirmed_raises_immutable(self):
        m = _make_gr_service()
        gr = _make_gr(status="CONFIRMED")
        m.gr_repo.get_by_id_or_none.return_value = gr

        with pytest.raises(GRImmutableError):
            m.service.confirm_gr(gr_id=gr.id, company_id=gr.company_id, user_id=uuid4())


# ---------------------------------------------------------------------------
# T163f: update_gr — blocked on CONFIRMED GR
# ---------------------------------------------------------------------------


class TestUpdateGR:
    def test_update_confirmed_raises_immutable(self):
        m = _make_gr_service()
        gr = _make_gr(status="CONFIRMED")
        m.gr_repo.get_by_id_or_none.return_value = gr

        from modules.purchase.schemas.goods_receipt import GoodsReceiptUpdate

        payload = GoodsReceiptUpdate(notes="Attempted edit")

        with pytest.raises(GRImmutableError):
            m.service.update_gr(gr_id=gr.id, company_id=gr.company_id, payload=payload)
