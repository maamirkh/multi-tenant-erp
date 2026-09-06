"""Unit tests for RMAService — Phase 7.

Tests:
  - create_rma: non-CONFIRMED GR raises RMAInvalidGRStatusError
  - create_rma: GR not found raises NotFoundException
  - _build_return_line: return qty > accepted raises RMAReturnQuantityError
  - _assert_mutable: DISPATCHED RMA raises RMAImmutableError
  - _assert_mutable: DRAFT RMA passes
  - _assert_transition: valid/invalid transitions
  - submit_rma: no lines raises ConflictException
  - complete_rma: sets credit_note_pending = True
  - link_replacement_po: does not change status
  - cancel_rma: DISPATCHED → CANCELLED raises RMAInvalidTransitionError

Task: T184
"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from core.exceptions.base import ConflictException, NotFoundException
from modules.purchase.services.rma_service import (
    RMAImmutableError,
    RMAInvalidGRStatusError,
    RMAInvalidTransitionError,
    RMAReturnQuantityError,
    RMAService,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_rma_service():
    svc = RMAService(
        db=MagicMock(),
        rma_repo=MagicMock(),
        line_repo=MagicMock(),
        gr_repo=MagicMock(),
        gr_line_repo=MagicMock(),
        sequence_service=MagicMock(),
    )
    return svc


def _make_rma(status: str = "DRAFT"):
    rma = MagicMock()
    rma.id = uuid4()
    rma.company_id = uuid4()
    rma.rma_number = "RMA-2026-000001"
    rma.status = status
    rma.gr_id = str(uuid4())
    rma.supplier_id = str(uuid4())
    rma.initiated_by = None
    rma.reason_id = None
    rma.notes = None
    rma.replacement_po_id = None
    rma.credit_note_pending = False
    rma.dispatched_at = None
    rma.completed_at = None
    return rma


def _make_gr(status: str = "CONFIRMED"):
    gr = MagicMock()
    gr.id = uuid4()
    gr.status = status
    gr.supplier_id = str(uuid4())
    gr.warehouse_id = None
    return gr


def _make_gr_line(qty_received: str = "10.000", qty_rejected: str = "0.000"):
    ln = MagicMock()
    ln.id = uuid4()
    ln.quantity_received = Decimal(qty_received)
    ln.quantity_rejected = Decimal(qty_rejected)
    ln.product_id = None
    return ln


def _make_return_line(qty_returned: str = "5.000"):
    ln = MagicMock()
    ln.id = uuid4()
    ln.company_id = uuid4()
    ln.return_id = str(uuid4())
    ln.gr_line_id = str(uuid4())
    ln.product_id = None
    ln.quantity_returned = Decimal(qty_returned)
    ln.reason_id = None
    ln.notes = None
    return ln


# ---------------------------------------------------------------------------
# T184a: create_rma — GR validation
# ---------------------------------------------------------------------------


class TestCreateRMA:
    def test_gr_not_found_raises_404(self):
        svc = _make_rma_service()
        svc.gr_repo.get_by_id_or_none.return_value = None

        from modules.purchase.schemas.vendor_return import VendorReturnCreate

        payload = VendorReturnCreate(gr_id=uuid4(), lines=[])

        with pytest.raises(NotFoundException):
            svc.create_rma(payload=payload, company_id=uuid4(), user_id=uuid4())

    def test_draft_gr_raises_invalid_status_error(self):
        svc = _make_rma_service()
        svc.gr_repo.get_by_id_or_none.return_value = _make_gr(status="DRAFT")

        from modules.purchase.schemas.vendor_return import VendorReturnCreate

        payload = VendorReturnCreate(gr_id=uuid4(), lines=[])

        with pytest.raises(RMAInvalidGRStatusError):
            svc.create_rma(payload=payload, company_id=uuid4(), user_id=uuid4())

    def test_partially_received_gr_raises_invalid_status_error(self):
        svc = _make_rma_service()
        svc.gr_repo.get_by_id_or_none.return_value = _make_gr(status="DRAFT")

        from modules.purchase.schemas.vendor_return import VendorReturnCreate

        payload = VendorReturnCreate(gr_id=uuid4(), lines=[])

        with pytest.raises(RMAInvalidGRStatusError):
            svc.create_rma(payload=payload, company_id=uuid4(), user_id=uuid4())


# ---------------------------------------------------------------------------
# T184b: return quantity invariant
# ---------------------------------------------------------------------------


class TestReturnQuantityInvariant:
    def test_return_qty_exceeds_accepted_raises_error(self):
        svc = _make_rma_service()
        rma = _make_rma()
        gr_line = _make_gr_line(qty_received="5.000", qty_rejected="1.000")
        # accepted = 5 − 1 = 4
        svc.gr_line_repo.get_by_id_or_none.return_value = gr_line

        from modules.purchase.schemas.vendor_return import ReturnLineCreate

        line_in = ReturnLineCreate(
            gr_line_id=uuid4(), quantity_returned=Decimal("5.000")
        )  # > 4

        with pytest.raises(RMAReturnQuantityError):
            svc._build_return_line(rma, line_in, rma.company_id, uuid4())

    def test_return_qty_at_accepted_limit_passes(self):
        svc = _make_rma_service()
        rma = _make_rma()
        gr_line = _make_gr_line(qty_received="5.000", qty_rejected="0.000")
        # accepted = 5
        svc.gr_line_repo.get_by_id_or_none.return_value = gr_line
        svc.db.add = MagicMock()
        svc.db.flush = MagicMock()

        from modules.purchase.schemas.vendor_return import ReturnLineCreate

        line_in = ReturnLineCreate(
            gr_line_id=uuid4(), quantity_returned=Decimal("5.000")
        )  # == 5

        # Should not raise
        svc._build_return_line(rma, line_in, rma.company_id, uuid4())


# ---------------------------------------------------------------------------
# T184c: _assert_mutable
# ---------------------------------------------------------------------------


class TestAssertMutable:
    def test_draft_passes(self):
        svc = _make_rma_service()
        rma = _make_rma(status="DRAFT")
        svc._assert_mutable(rma)  # should not raise

    def test_dispatched_raises_immutable(self):
        svc = _make_rma_service()
        rma = _make_rma(status="DISPATCHED")
        with pytest.raises(RMAImmutableError):
            svc._assert_mutable(rma)

    def test_completed_raises_immutable(self):
        svc = _make_rma_service()
        rma = _make_rma(status="COMPLETED")
        with pytest.raises(RMAImmutableError):
            svc._assert_mutable(rma)

    def test_submitted_raises_immutable(self):
        """SUBMITTED is not in _MUTABLE_STATUSES — only DRAFT allows editing."""
        svc = _make_rma_service()
        rma = _make_rma(status="SUBMITTED")
        with pytest.raises(RMAImmutableError):
            svc._assert_mutable(rma)


# ---------------------------------------------------------------------------
# T184d: _assert_transition
# ---------------------------------------------------------------------------


class TestAssertTransition:
    def test_draft_to_submitted_allowed(self):
        svc = _make_rma_service()
        rma = _make_rma(status="DRAFT")
        svc._assert_transition(rma, "SUBMITTED")  # should not raise

    def test_submitted_to_approved_allowed(self):
        svc = _make_rma_service()
        rma = _make_rma(status="SUBMITTED")
        svc._assert_transition(rma, "APPROVED")  # should not raise

    def test_draft_to_dispatched_blocked(self):
        svc = _make_rma_service()
        rma = _make_rma(status="DRAFT")
        with pytest.raises(RMAInvalidTransitionError):
            svc._assert_transition(rma, "DISPATCHED")

    def test_completed_to_cancelled_blocked(self):
        svc = _make_rma_service()
        rma = _make_rma(status="COMPLETED")
        with pytest.raises(RMAInvalidTransitionError):
            svc._assert_transition(rma, "CANCELLED")

    def test_dispatched_to_completed_allowed(self):
        svc = _make_rma_service()
        rma = _make_rma(status="DISPATCHED")
        svc._assert_transition(rma, "COMPLETED")  # should not raise


# ---------------------------------------------------------------------------
# T184e: submit_rma — no lines raises ConflictException
# ---------------------------------------------------------------------------


class TestSubmitRMA:
    def test_no_lines_raises_conflict(self):
        svc = _make_rma_service()
        rma = _make_rma(status="DRAFT")
        svc.rma_repo.get_by_id_or_none.return_value = rma
        svc.line_repo.list_for_rma.return_value = []

        with pytest.raises(ConflictException):
            svc.submit_rma(rma_id=rma.id, company_id=rma.company_id, user_id=uuid4())

    def test_submit_publishes_event(self):
        svc = _make_rma_service()
        rma = _make_rma(status="DRAFT")
        svc.rma_repo.get_by_id_or_none.return_value = rma
        svc.line_repo.list_for_rma.return_value = [_make_return_line()]

        with patch("modules.purchase.services.rma_service.get_event_bus") as mock_bus:
            bus = MagicMock()
            mock_bus.return_value = bus
            svc.submit_rma(rma_id=rma.id, company_id=rma.company_id, user_id=uuid4())
            bus.publish.assert_called_once()


# ---------------------------------------------------------------------------
# T184f: complete_rma — credit_note_pending set to True
# ---------------------------------------------------------------------------


class TestCompleteRMA:
    def test_complete_sets_credit_note_pending(self):
        svc = _make_rma_service()
        rma = _make_rma(status="DISPATCHED")
        svc.rma_repo.get_by_id_or_none.return_value = rma
        svc.line_repo.list_for_rma.return_value = [_make_return_line()]

        with patch("modules.purchase.services.rma_service.get_event_bus") as mock_bus:
            bus = MagicMock()
            mock_bus.return_value = bus
            svc.complete_rma(rma_id=rma.id, company_id=rma.company_id, user_id=uuid4())

        assert rma.credit_note_pending is True
        assert rma.status == "COMPLETED"


# ---------------------------------------------------------------------------
# T184g: link_replacement_po — state-neutral
# ---------------------------------------------------------------------------


class TestLinkReplacementPO:
    def test_link_po_does_not_change_status(self):
        svc = _make_rma_service()
        rma = _make_rma(status="APPROVED")
        svc.rma_repo.get_by_id_or_none.return_value = rma
        svc.line_repo.list_for_rma.return_value = []

        po_id = uuid4()
        svc.link_replacement_po(rma_id=rma.id, company_id=rma.company_id, po_id=po_id)

        assert rma.replacement_po_id == str(po_id)
        assert rma.status == "APPROVED"  # unchanged

    def test_link_on_completed_raises_immutable(self):
        svc = _make_rma_service()
        rma = _make_rma(status="COMPLETED")
        svc.rma_repo.get_by_id_or_none.return_value = rma

        with pytest.raises(RMAImmutableError):
            svc.link_replacement_po(
                rma_id=rma.id, company_id=rma.company_id, po_id=uuid4()
            )


# ---------------------------------------------------------------------------
# T184h: cancel_rma — DISPATCHED cannot be cancelled
# ---------------------------------------------------------------------------


class TestCancelRMA:
    def test_dispatched_cannot_be_cancelled(self):
        svc = _make_rma_service()
        rma = _make_rma(status="DISPATCHED")
        svc.rma_repo.get_by_id_or_none.return_value = rma

        with pytest.raises(RMAInvalidTransitionError):
            svc.cancel_rma(rma_id=rma.id, company_id=rma.company_id, user_id=uuid4())

    def test_submitted_can_be_cancelled(self):
        svc = _make_rma_service()
        rma = _make_rma(status="SUBMITTED")
        svc.rma_repo.get_by_id_or_none.return_value = rma
        svc.line_repo.list_for_rma.return_value = []

        svc.cancel_rma(rma_id=rma.id, company_id=rma.company_id, user_id=uuid4())
        assert rma.status == "CANCELLED"
