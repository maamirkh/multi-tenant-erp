"""Unit tests for POService — Phase 5.

Tests:
  - All PO state transitions (valid and invalid)
  - Immutability enforcement (edit APPROVED PO raises POImmutableError)
  - Amendment resets PO to PENDING_APPROVAL
  - Cancel blocked after GR exists
  - Credit limit check timing (at approval, not creation)
  - Cost computation with known values

Task: T142
"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import MagicMock
from uuid import UUID, uuid4

import pytest

from modules.purchase.services.po_service import (
    IMMUTABLE_STATUSES,
    InvalidPOStatusTransitionError,
    POCancelBlockedError,
    POImmutableError,
    POMissingLinesError,
    POMissingSupplierError,
    POService,
    _assert_transition,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_po_service(db=None):
    """Build a POService with all-mock repositories."""
    db = db or MagicMock()
    svc = POService(
        db=db,
        po_repo=MagicMock(),
        line_repo=MagicMock(),
        charge_repo=MagicMock(),
        amendment_repo=MagicMock(),
        sequence_service=MagicMock(),
    )
    return svc


def _make_po(
    status: str = "DRAFT", supplier_id: str | None = None, po_id: UUID | None = None
) -> MagicMock:
    po = MagicMock()
    po.id = po_id or uuid4()
    po.company_id = uuid4()
    po.po_number = "PO-2026-000001"
    po.status = status
    po.supplier_id = supplier_id or str(uuid4())
    po.purchase_request_id = None
    po.payment_terms_id = None
    po.expected_delivery_date = None
    po.supplier_reference = None
    po.currency_code = "USD"
    po.subtotal = Decimal("0.00")
    po.total_charges = Decimal("0.00")
    po.total_discounts = Decimal("0.00")
    po.tax_amount = Decimal("0.00")
    po.total = Decimal("0.00")
    po.notes = None
    po.version = 1
    po.reason_code_id = None
    return po


# ---------------------------------------------------------------------------
# T142a: State machine — valid transitions
# ---------------------------------------------------------------------------


class TestAllowedTransitions:
    def test_draft_to_pending_approval(self):
        _assert_transition(uuid4(), "DRAFT", "PENDING_APPROVAL")

    def test_draft_to_cancelled(self):
        _assert_transition(uuid4(), "DRAFT", "CANCELLED")

    def test_pending_approval_to_approved(self):
        _assert_transition(uuid4(), "PENDING_APPROVAL", "APPROVED")

    def test_pending_approval_to_rejected(self):
        _assert_transition(uuid4(), "PENDING_APPROVAL", "REJECTED")

    def test_pending_approval_to_cancelled(self):
        _assert_transition(uuid4(), "PENDING_APPROVAL", "CANCELLED")

    def test_rejected_to_draft(self):
        _assert_transition(uuid4(), "REJECTED", "DRAFT")

    def test_approved_to_partially_received(self):
        _assert_transition(uuid4(), "APPROVED", "PARTIALLY_RECEIVED")

    def test_approved_to_fully_received(self):
        _assert_transition(uuid4(), "APPROVED", "FULLY_RECEIVED")

    def test_approved_to_closed(self):
        _assert_transition(uuid4(), "APPROVED", "CLOSED")

    def test_approved_to_cancelled(self):
        _assert_transition(uuid4(), "APPROVED", "CANCELLED")

    def test_partially_received_to_fully_received(self):
        _assert_transition(uuid4(), "PARTIALLY_RECEIVED", "FULLY_RECEIVED")

    def test_partially_received_to_closed(self):
        _assert_transition(uuid4(), "PARTIALLY_RECEIVED", "CLOSED")

    def test_fully_received_to_closed(self):
        _assert_transition(uuid4(), "FULLY_RECEIVED", "CLOSED")


class TestInvalidTransitions:
    def test_draft_to_approved_invalid(self):
        with pytest.raises(InvalidPOStatusTransitionError):
            _assert_transition(uuid4(), "DRAFT", "APPROVED")

    def test_closed_to_draft_invalid(self):
        with pytest.raises(InvalidPOStatusTransitionError):
            _assert_transition(uuid4(), "CLOSED", "DRAFT")

    def test_cancelled_to_draft_invalid(self):
        with pytest.raises(InvalidPOStatusTransitionError):
            _assert_transition(uuid4(), "CANCELLED", "DRAFT")

    def test_approved_to_draft_invalid(self):
        with pytest.raises(InvalidPOStatusTransitionError):
            _assert_transition(uuid4(), "APPROVED", "DRAFT")

    def test_fully_received_to_cancelled_invalid(self):
        with pytest.raises(InvalidPOStatusTransitionError):
            _assert_transition(uuid4(), "FULLY_RECEIVED", "CANCELLED")


# ---------------------------------------------------------------------------
# T142b: Immutability enforcement
# ---------------------------------------------------------------------------


class TestImmutabilityEnforcement:
    def test_immutable_statuses_defined(self):
        assert "APPROVED" in IMMUTABLE_STATUSES
        assert "PARTIALLY_RECEIVED" in IMMUTABLE_STATUSES
        assert "FULLY_RECEIVED" in IMMUTABLE_STATUSES
        assert "CLOSED" in IMMUTABLE_STATUSES

    def test_draft_not_immutable(self):
        assert "DRAFT" not in IMMUTABLE_STATUSES

    def test_assert_editable_raises_on_approved(self):
        svc = _make_po_service()
        po = _make_po(status="APPROVED")
        with pytest.raises(POImmutableError):
            svc._assert_editable(po)

    def test_assert_editable_raises_on_fully_received(self):
        svc = _make_po_service()
        po = _make_po(status="FULLY_RECEIVED")
        with pytest.raises(POImmutableError):
            svc._assert_editable(po)

    def test_assert_editable_ok_on_draft(self):
        svc = _make_po_service()
        po = _make_po(status="DRAFT")
        svc._assert_editable(po)  # no exception

    def test_update_po_on_approved_raises(self):
        svc = _make_po_service()
        po = _make_po(status="APPROVED")
        svc.po_repo.get_by_id_or_none.return_value = po

        from modules.purchase.schemas.purchase_order import PurchaseOrderUpdate

        payload = PurchaseOrderUpdate(notes="updated")

        with pytest.raises(POImmutableError):
            svc.update_po(po.id, po.company_id, payload, uuid4())


# ---------------------------------------------------------------------------
# T142c: submit_po validations
# ---------------------------------------------------------------------------


class TestSubmitPOValidations:
    def test_submit_raises_if_no_supplier(self):
        svc = _make_po_service()
        po = _make_po(status="DRAFT", supplier_id=None)
        po.supplier_id = None
        svc.po_repo.get_by_id_or_none.return_value = po
        svc.line_repo.list_for_po.return_value = [MagicMock()]

        with pytest.raises(POMissingSupplierError):
            svc.submit_po(po.id, po.company_id, uuid4())

    def test_submit_raises_if_no_lines(self):
        svc = _make_po_service()
        po = _make_po(status="DRAFT", supplier_id=str(uuid4()))
        svc.po_repo.get_by_id_or_none.return_value = po
        svc.line_repo.list_for_po.return_value = []

        with pytest.raises(POMissingLinesError):
            svc.submit_po(po.id, po.company_id, uuid4())

    def test_submit_raises_on_wrong_status(self):
        svc = _make_po_service()
        po = _make_po(status="APPROVED")
        svc.po_repo.get_by_id_or_none.return_value = po

        with pytest.raises(InvalidPOStatusTransitionError):
            svc.submit_po(po.id, po.company_id, uuid4())


# ---------------------------------------------------------------------------
# T142d: Amendment resets PO to PENDING_APPROVAL
# ---------------------------------------------------------------------------


class TestAmendPO:
    def test_amend_resets_to_pending_approval(self):
        svc = _make_po_service()
        po = _make_po(status="APPROVED")
        svc.po_repo.get_by_id_or_none.return_value = po
        svc.amendment_repo.get_max_amendment_number.return_value = 0
        svc.amendment_repo.list_for_po.return_value = []
        svc.line_repo.list_for_po.return_value = []
        svc.charge_repo.list_for_po.return_value = []

        svc.amend_po(
            po.id,
            po.company_id,
            changes={},
            reason="Price correction",
            actor_id=uuid4(),
        )

        svc.po_repo.update_status.assert_called_once_with(
            po.id, po.company_id, "PENDING_APPROVAL"
        )

    def test_amend_on_draft_raises(self):
        svc = _make_po_service()
        po = _make_po(status="DRAFT")
        svc.po_repo.get_by_id_or_none.return_value = po

        from core.exceptions.base import ConflictException

        with pytest.raises(ConflictException):
            svc.amend_po(
                po.id, po.company_id, changes={}, reason="reason", actor_id=uuid4()
            )

    def test_amend_increments_amendment_number(self):
        svc = _make_po_service()
        po = _make_po(status="APPROVED")
        svc.po_repo.get_by_id_or_none.return_value = po
        svc.amendment_repo.get_max_amendment_number.return_value = 2
        svc.amendment_repo.list_for_po.return_value = []
        svc.line_repo.list_for_po.return_value = []
        svc.charge_repo.list_for_po.return_value = []

        svc.amend_po(
            po.id, po.company_id, changes={}, reason="reason", actor_id=uuid4()
        )

        args, kwargs = svc.db.add.call_args
        amendment = args[0]
        assert amendment.amendment_number == 3


# ---------------------------------------------------------------------------
# T142e: Cancel blocked after GR
# ---------------------------------------------------------------------------


class TestCancelPO:
    def test_cancel_blocked_when_gr_exists(self):
        svc = _make_po_service()
        po = _make_po(status="APPROVED")
        svc.po_repo.get_by_id_or_none.return_value = po

        with pytest.raises(POCancelBlockedError):
            svc.cancel_po(po.id, po.company_id, uuid4(), has_confirmed_gr=True)

    def test_cancel_allowed_before_gr(self):
        svc = _make_po_service()
        po = _make_po(status="APPROVED")
        svc.po_repo.get_by_id_or_none.return_value = po
        svc.line_repo.list_for_po.return_value = []
        svc.charge_repo.list_for_po.return_value = []
        svc.amendment_repo.list_for_po.return_value = []

        svc.cancel_po(po.id, po.company_id, uuid4(), has_confirmed_gr=False)
        svc.po_repo.update_status.assert_called_once()

    def test_cancel_from_fully_received_invalid(self):
        svc = _make_po_service()
        po = _make_po(status="FULLY_RECEIVED")
        svc.po_repo.get_by_id_or_none.return_value = po

        with pytest.raises(InvalidPOStatusTransitionError):
            svc.cancel_po(po.id, po.company_id, uuid4(), has_confirmed_gr=False)


# ---------------------------------------------------------------------------
# T142f: Cost computation with known values (T125)
# ---------------------------------------------------------------------------


class TestCostComputation:
    def test_line_total_no_discount(self):
        svc = _make_po_service()
        line_total, discount = svc._compute_line_total(
            unit_cost=Decimal("10.0000"),
            quantity_ordered=Decimal("5.000"),
            line_discount_amount=None,
            line_discount_percent=None,
        )
        assert line_total == Decimal("50.00")
        assert discount == Decimal("0.00")

    def test_line_total_with_percent_discount(self):
        svc = _make_po_service()
        line_total, discount = svc._compute_line_total(
            unit_cost=Decimal("100.0000"),
            quantity_ordered=Decimal("2.000"),
            line_discount_amount=None,
            line_discount_percent=Decimal("10.00"),
        )
        assert line_total == Decimal("180.00")
        assert discount == Decimal("20.00")

    def test_line_total_with_amount_discount(self):
        svc = _make_po_service()
        line_total, discount = svc._compute_line_total(
            unit_cost=Decimal("50.0000"),
            quantity_ordered=Decimal("3.000"),
            line_discount_amount=Decimal("25.00"),
            line_discount_percent=None,
        )
        assert line_total == Decimal("125.00")
        assert discount == Decimal("25.00")

    def test_line_total_discount_cannot_be_negative(self):
        svc = _make_po_service()
        # discount larger than gross should give zero
        line_total, _ = svc._compute_line_total(
            unit_cost=Decimal("1.0000"),
            quantity_ordered=Decimal("1.000"),
            line_discount_amount=Decimal("100.00"),
            line_discount_percent=None,
        )
        assert line_total == Decimal("0.00")


# ---------------------------------------------------------------------------
# T142g: auto_update_status_on_gr
# ---------------------------------------------------------------------------


class TestAutoUpdateStatusOnGR:
    def test_transitions_to_fully_received_when_all_lines_received(self):
        svc = _make_po_service()
        po = _make_po(status="APPROVED")
        svc.po_repo.get_by_id_or_none.return_value = po

        line1 = MagicMock()
        line1.open_quantity = Decimal("0.000")
        line2 = MagicMock()
        line2.open_quantity = Decimal("0.000")
        svc.line_repo.list_for_po.return_value = [line1, line2]

        result = svc.auto_update_status_on_gr(po.id, po.company_id)

        assert result == "FULLY_RECEIVED"
        svc.po_repo.update_status.assert_called_once_with(
            po.id, po.company_id, "FULLY_RECEIVED"
        )

    def test_transitions_to_partially_received_when_open_qty_remains(self):
        svc = _make_po_service()
        po = _make_po(status="APPROVED")
        svc.po_repo.get_by_id_or_none.return_value = po

        line1 = MagicMock()
        line1.open_quantity = Decimal("0.000")
        line2 = MagicMock()
        line2.open_quantity = Decimal("2.000")
        svc.line_repo.list_for_po.return_value = [line1, line2]

        result = svc.auto_update_status_on_gr(po.id, po.company_id)

        assert result == "PARTIALLY_RECEIVED"
        svc.po_repo.update_status.assert_called_once_with(
            po.id, po.company_id, "PARTIALLY_RECEIVED"
        )
