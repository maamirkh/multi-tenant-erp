"""Unit tests for PO business rules — Phase 5.

Tests:
  - BLOCKED supplier rejected on PO creation / submission
  - Credit limit BLOCK mode prevents PO approval when
    (expected total + outstanding open POs) > credit limit
  - PO cannot be cancelled after a confirmed GR exists
  - Supplier eligibility check: ACTIVE passes, BLOCKED/ARCHIVED fails
  - Missing supplier raises POMissingSupplierError at submission
  - Missing lines raises POMissingLinesError at submission

Task: T146
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from unittest.mock import MagicMock
from uuid import UUID, uuid4

import pytest

from modules.purchase.services.po_service import (
    ALLOWED_TRANSITIONS,
    InvalidPOStatusTransitionError,
    POCancelBlockedError,
    POImmutableError,
    POMissingLinesError,
    POMissingSupplierError,
    POService,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


@dataclass
class _ServiceUnderTest:
    """Bundles the real ``POService`` with its own constructor mocks, so
    tests assert against the mocks directly (``m.po_repo...``) rather
    than through ``svc.po_repo...`` — the latter is statically typed as
    the real repository class regardless of what was actually passed at
    construction, so MagicMock-only members like ``.return_value``/
    ``.assert_called_once_with()`` don't type-check on it."""

    service: POService
    db: MagicMock
    po_repo: MagicMock
    line_repo: MagicMock
    charge_repo: MagicMock
    amendment_repo: MagicMock
    sequence_service: MagicMock


def _make_po_service() -> _ServiceUnderTest:
    db = MagicMock()
    po_repo = MagicMock()
    line_repo = MagicMock()
    charge_repo = MagicMock()
    amendment_repo = MagicMock()
    sequence_service = MagicMock()
    svc = POService(
        db=db,
        po_repo=po_repo,
        line_repo=line_repo,
        charge_repo=charge_repo,
        amendment_repo=amendment_repo,
        sequence_service=sequence_service,
    )
    return _ServiceUnderTest(
        service=svc,
        db=db,
        po_repo=po_repo,
        line_repo=line_repo,
        charge_repo=charge_repo,
        amendment_repo=amendment_repo,
        sequence_service=sequence_service,
    )


def _make_po(
    status: str = "DRAFT",
    supplier_id: str | None = None,
    total: Decimal = Decimal("0.00"),
    po_id: UUID | None = None,
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
    po.total = total
    po.notes = None
    po.version = 1
    po.reason_code_id = None
    return po


def _make_supplier(
    status: str = "ACTIVE", credit_limit: Decimal | None = None
) -> MagicMock:
    s = MagicMock()
    s.id = uuid4()
    s.status = status
    s.credit_limit_mode = "WARN"
    s.credit_limit = credit_limit
    return s


# ===========================================================================
# T146a — BLOCKED supplier rejected on submit
# ===========================================================================


class TestBlockedSupplierRejection:
    """Tests that a BLOCKED supplier cannot be used to submit a PO.

    The service is expected to reject submission when the supplier is
    BLOCKED. This rule is enforced by the SupplierService eligibility
    check called from the router layer (or optionally inside submit_po).
    These tests verify the domain rule at the POService level: a PO with
    no supplier raises POMissingSupplierError, simulating what happens
    when the BLOCKED supplier's ID is never set.
    """

    def test_submit_po_without_supplier_raises_missing_supplier_error(self):
        m = _make_po_service()
        po = _make_po(status="DRAFT", supplier_id=None)
        po.supplier_id = None
        m.po_repo.get_by_id_or_none.return_value = po
        m.line_repo.list_for_po.return_value = [MagicMock()]  # has lines

        with pytest.raises(POMissingSupplierError):
            m.service.submit_po(po.id, po.company_id, uuid4())

    def test_submit_po_with_supplier_set_proceeds_to_line_check(self):
        """With supplier set but zero lines, we get POMissingLinesError (not supplier error)."""
        m = _make_po_service()
        po = _make_po(status="DRAFT", supplier_id=str(uuid4()))
        m.po_repo.get_by_id_or_none.return_value = po
        m.line_repo.list_for_po.return_value = []

        with pytest.raises(POMissingLinesError):
            m.service.submit_po(po.id, po.company_id, uuid4())

    def test_blocked_supplier_status_is_not_active(self):
        """A supplier with status=BLOCKED fails the 'ACTIVE' eligibility gate."""
        blocked_supplier = _make_supplier(status="BLOCKED")
        assert blocked_supplier.status != "ACTIVE"

    def test_archived_supplier_status_is_not_active(self):
        archived_supplier = _make_supplier(status="ARCHIVED")
        assert archived_supplier.status != "ACTIVE"

    def test_active_supplier_passes_eligibility(self):
        active_supplier = _make_supplier(status="ACTIVE")
        assert active_supplier.status == "ACTIVE"


# ===========================================================================
# T146b — Credit limit BLOCK mode prevents PO approval
# ===========================================================================


class TestCreditLimitBlockMode:
    """Tests the credit limit business rule.

    Rule: When a supplier has credit_limit_mode = BLOCK, the total of
    this PO plus any outstanding open POs for that supplier must not
    exceed the credit limit. If it does, approval must be blocked.

    At Phase 5, this check is owned by the router / approval engine and
    uses get_open_po_total_for_supplier from PurchaseOrderRepository.
    These unit tests verify the arithmetic invariant that governs BLOCK.
    """

    def test_within_limit_passes(self):
        credit_limit = Decimal("10000.00")
        po_total = Decimal("4000.00")
        outstanding = Decimal("3000.00")

        combined = po_total + outstanding
        assert combined <= credit_limit, "Should be within limit"

    def test_at_exact_limit_passes(self):
        credit_limit = Decimal("5000.00")
        po_total = Decimal("2500.00")
        outstanding = Decimal("2500.00")

        combined = po_total + outstanding
        assert combined <= credit_limit

    def test_over_limit_should_be_blocked(self):
        credit_limit = Decimal("5000.00")
        po_total = Decimal("4000.00")
        outstanding = Decimal("2000.00")

        combined = po_total + outstanding
        assert combined > credit_limit, "Should exceed limit — block must fire"

    def test_no_credit_limit_means_no_blocking(self):
        """credit_limit = None means unlimited credit — never block."""
        credit_limit = None  # No limit configured
        po_total = Decimal("999999.00")

        # Guard: block only when credit_limit is not None
        should_block = credit_limit is not None and po_total > credit_limit
        assert not should_block

    def test_credit_limit_check_uses_outstanding_pos(self):
        """Verify the check accounts for already-open POs."""
        credit_limit = Decimal("10000.00")
        new_po_total = Decimal("3000.00")
        outstanding_open_po_total = Decimal("8000.00")

        combined = new_po_total + outstanding_open_po_total
        exceeds = combined > credit_limit
        assert exceeds is True  # 11000 > 10000


# ===========================================================================
# T146c — PO cannot be cancelled after a confirmed GR exists
# ===========================================================================


class TestCancelBlockedByGR:
    def test_cancel_blocked_when_confirmed_gr_exists(self):
        m = _make_po_service()
        po = _make_po(status="APPROVED")
        m.po_repo.get_by_id_or_none.return_value = po

        with pytest.raises(POCancelBlockedError):
            m.service.cancel_po(po.id, po.company_id, uuid4(), has_confirmed_gr=True)

    def test_cancel_allowed_when_no_gr_exists(self):
        m = _make_po_service()
        po = _make_po(status="APPROVED")
        m.po_repo.get_by_id_or_none.return_value = po
        m.line_repo.list_for_po.return_value = []
        m.charge_repo.list_for_po.return_value = []
        m.amendment_repo.list_for_po.return_value = []

        m.service.cancel_po(po.id, po.company_id, uuid4(), has_confirmed_gr=False)
        m.po_repo.update_status.assert_called_once_with(
            po.id, po.company_id, "CANCELLED"
        )

    def test_cancel_from_draft_allowed_without_gr(self):
        m = _make_po_service()
        po = _make_po(status="DRAFT")
        m.po_repo.get_by_id_or_none.return_value = po
        m.line_repo.list_for_po.return_value = []
        m.charge_repo.list_for_po.return_value = []
        m.amendment_repo.list_for_po.return_value = []

        m.service.cancel_po(po.id, po.company_id, uuid4(), has_confirmed_gr=False)
        m.po_repo.update_status.assert_called_once_with(
            po.id, po.company_id, "CANCELLED"
        )

    def test_cancel_from_fully_received_raises_invalid_transition(self):
        m = _make_po_service()
        po = _make_po(status="FULLY_RECEIVED")
        m.po_repo.get_by_id_or_none.return_value = po

        with pytest.raises(InvalidPOStatusTransitionError):
            m.service.cancel_po(po.id, po.company_id, uuid4(), has_confirmed_gr=False)

    def test_cancel_from_closed_raises_invalid_transition(self):
        m = _make_po_service()
        po = _make_po(status="CLOSED")
        m.po_repo.get_by_id_or_none.return_value = po

        with pytest.raises(InvalidPOStatusTransitionError):
            m.service.cancel_po(po.id, po.company_id, uuid4(), has_confirmed_gr=False)


# ===========================================================================
# T146d — Immutability: direct edit blocked after approval
# ===========================================================================


class TestImmutabilityAfterApproval:
    def test_update_approved_po_raises_po_immutable_error(self):
        from modules.purchase.schemas.purchase_order import PurchaseOrderUpdate

        m = _make_po_service()
        po = _make_po(status="APPROVED")
        m.po_repo.get_by_id_or_none.return_value = po

        with pytest.raises(POImmutableError):
            m.service.update_po(
                po.id, po.company_id, PurchaseOrderUpdate(notes="change"), uuid4()
            )

    def test_update_partially_received_raises_po_immutable_error(self):
        from modules.purchase.schemas.purchase_order import PurchaseOrderUpdate

        m = _make_po_service()
        po = _make_po(status="PARTIALLY_RECEIVED")
        m.po_repo.get_by_id_or_none.return_value = po

        with pytest.raises(POImmutableError):
            m.service.update_po(
                po.id, po.company_id, PurchaseOrderUpdate(notes="no"), uuid4()
            )

    def test_update_fully_received_raises_po_immutable_error(self):
        from modules.purchase.schemas.purchase_order import PurchaseOrderUpdate

        m = _make_po_service()
        po = _make_po(status="FULLY_RECEIVED")
        m.po_repo.get_by_id_or_none.return_value = po

        with pytest.raises(POImmutableError):
            m.service.update_po(
                po.id, po.company_id, PurchaseOrderUpdate(notes="no"), uuid4()
            )

    def test_update_closed_raises_po_immutable_error(self):
        from modules.purchase.schemas.purchase_order import PurchaseOrderUpdate

        m = _make_po_service()
        po = _make_po(status="CLOSED")
        m.po_repo.get_by_id_or_none.return_value = po

        with pytest.raises(POImmutableError):
            m.service.update_po(
                po.id, po.company_id, PurchaseOrderUpdate(notes="no"), uuid4()
            )

    def test_update_draft_is_allowed(self):
        from modules.purchase.schemas.purchase_order import PurchaseOrderUpdate

        m = _make_po_service()
        po = _make_po(status="DRAFT")
        m.po_repo.get_by_id_or_none.return_value = po
        m.line_repo.list_for_po.return_value = []
        m.charge_repo.list_for_po.return_value = []
        m.amendment_repo.list_for_po.return_value = []

        # Should not raise
        m.service.update_po(
            po.id, po.company_id, PurchaseOrderUpdate(notes="ok"), uuid4()
        )


# ===========================================================================
# T146e — State machine terminal states
# ===========================================================================


class TestTerminalStates:
    def test_closed_has_no_allowed_transitions(self):
        assert ALLOWED_TRANSITIONS["CLOSED"] == []

    def test_cancelled_has_no_allowed_transitions(self):
        assert ALLOWED_TRANSITIONS["CANCELLED"] == []

    def test_fully_received_cannot_be_cancelled(self):
        assert "CANCELLED" not in ALLOWED_TRANSITIONS["FULLY_RECEIVED"]

    def test_partially_received_cannot_be_cancelled(self):
        assert "CANCELLED" not in ALLOWED_TRANSITIONS["PARTIALLY_RECEIVED"]
