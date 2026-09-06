"""Unit tests for Delivery Note entity — Phase 5.

Tests:
  - All DN status transitions (valid + invalid)
  - Terminal statuses cannot be transitioned
  - _assert_dn_transition raises ConflictException on invalid transitions
  - DN immutability after dispatch (tested at service layer via state machine)
  - Quantity validation (dispatched <= remaining) — service layer logic

Task: T153
Spec ref: specs/007-sales-management/spec.md §Order Fulfilment
"""

from __future__ import annotations

import pytest

from core.exceptions.base import ConflictException
from modules.sales.services.delivery_service import (
    _TERMINAL_STATUSES,
    _VALID_TRANSITIONS,
    _assert_dn_transition,
)

# ---------------------------------------------------------------------------
# Valid transitions
# ---------------------------------------------------------------------------


class TestValidTransitions:
    def test_draft_to_dispatched(self) -> None:
        _assert_dn_transition("DRAFT", "DISPATCHED")

    def test_draft_to_cancelled(self) -> None:
        _assert_dn_transition("DRAFT", "CANCELLED")

    def test_dispatched_to_delivered(self) -> None:
        _assert_dn_transition("DISPATCHED", "DELIVERED")

    def test_all_valid_transitions_do_not_raise(self) -> None:
        for current, targets in _VALID_TRANSITIONS.items():
            for target in targets:
                _assert_dn_transition(current, target)


# ---------------------------------------------------------------------------
# Invalid transitions
# ---------------------------------------------------------------------------


class TestInvalidTransitions:
    def test_draft_to_delivered_raises(self) -> None:
        with pytest.raises(
            ConflictException, match="Invalid delivery note status transition"
        ):
            _assert_dn_transition("DRAFT", "DELIVERED")

    def test_dispatched_to_draft_raises(self) -> None:
        with pytest.raises(ConflictException):
            _assert_dn_transition("DISPATCHED", "DRAFT")

    def test_dispatched_to_cancelled_raises(self) -> None:
        """DISPATCHED → CANCELLED is not a valid direct transition."""
        with pytest.raises(ConflictException):
            _assert_dn_transition("DISPATCHED", "CANCELLED")

    def test_delivered_to_dispatched_raises(self) -> None:
        with pytest.raises(ConflictException):
            _assert_dn_transition("DELIVERED", "DISPATCHED")

    def test_delivered_to_cancelled_raises(self) -> None:
        with pytest.raises(ConflictException):
            _assert_dn_transition("DELIVERED", "CANCELLED")

    def test_cancelled_to_draft_raises(self) -> None:
        with pytest.raises(ConflictException):
            _assert_dn_transition("CANCELLED", "DRAFT")

    def test_cancelled_to_dispatched_raises(self) -> None:
        with pytest.raises(ConflictException):
            _assert_dn_transition("CANCELLED", "DISPATCHED")

    def test_unknown_status_raises(self) -> None:
        with pytest.raises(ConflictException):
            _assert_dn_transition("BOGUS", "DISPATCHED")


# ---------------------------------------------------------------------------
# Terminal statuses
# ---------------------------------------------------------------------------


class TestTerminalStatuses:
    def test_delivered_is_terminal(self) -> None:
        assert "DELIVERED" in _TERMINAL_STATUSES

    def test_cancelled_is_terminal(self) -> None:
        assert "CANCELLED" in _TERMINAL_STATUSES

    def test_draft_is_not_terminal(self) -> None:
        assert "DRAFT" not in _TERMINAL_STATUSES

    def test_dispatched_is_not_terminal(self) -> None:
        assert "DISPATCHED" not in _TERMINAL_STATUSES

    def test_terminal_statuses_have_no_outgoing_transitions(self) -> None:
        for status in _TERMINAL_STATUSES:
            assert _VALID_TRANSITIONS.get(status, []) == [], (
                f"Terminal status {status!r} must have no outgoing transitions"
            )


# ---------------------------------------------------------------------------
# Eligible order statuses
# ---------------------------------------------------------------------------


class TestEligibleOrderStatuses:
    def test_approved_eligible(self) -> None:
        from modules.sales.services.delivery_service import _ELIGIBLE_ORDER_STATUSES

        assert "APPROVED" in _ELIGIBLE_ORDER_STATUSES

    def test_partially_delivered_eligible(self) -> None:
        from modules.sales.services.delivery_service import _ELIGIBLE_ORDER_STATUSES

        assert "PARTIALLY_DELIVERED" in _ELIGIBLE_ORDER_STATUSES

    def test_draft_not_eligible(self) -> None:
        from modules.sales.services.delivery_service import _ELIGIBLE_ORDER_STATUSES

        assert "DRAFT" not in _ELIGIBLE_ORDER_STATUSES

    def test_pending_approval_not_eligible(self) -> None:
        from modules.sales.services.delivery_service import _ELIGIBLE_ORDER_STATUSES

        assert "PENDING_APPROVAL" not in _ELIGIBLE_ORDER_STATUSES

    def test_delivered_not_eligible(self) -> None:
        from modules.sales.services.delivery_service import _ELIGIBLE_ORDER_STATUSES

        assert "DELIVERED" not in _ELIGIBLE_ORDER_STATUSES

    def test_cancelled_not_eligible(self) -> None:
        from modules.sales.services.delivery_service import _ELIGIBLE_ORDER_STATUSES

        assert "CANCELLED" not in _ELIGIBLE_ORDER_STATUSES


# ---------------------------------------------------------------------------
# DeliveryService creation (unit — mocked DB)
# ---------------------------------------------------------------------------


class TestDeliveryServiceInit:
    def test_can_instantiate_with_mock_db(self) -> None:
        from unittest.mock import MagicMock

        from modules.sales.services.delivery_service import DeliveryService

        db = MagicMock()
        svc = DeliveryService(db)
        assert svc is not None
        assert svc._dn_repo is not None
        assert svc._order_repo is not None


class TestDeliveryServiceEligibleOrder:
    def test_create_raises_for_draft_order(self) -> None:
        from decimal import Decimal
        from unittest.mock import MagicMock
        from uuid import uuid4

        from modules.sales.schemas.delivery import (
            DeliveryNoteCreate,
            DeliveryNoteLineCreate,
        )
        from modules.sales.services.delivery_service import DeliveryService

        db = MagicMock()
        svc = DeliveryService(db)
        order = MagicMock()
        order.status = "DRAFT"
        svc._order_repo = MagicMock()
        svc._order_repo.get_by_id_or_none.return_value = order

        order_id = uuid4()
        data = DeliveryNoteCreate(
            order_id=order_id,
            lines=[
                DeliveryNoteLineCreate(
                    order_line_id=uuid4(),
                    description="Test product",
                    quantity_dispatched=Decimal("1"),
                    unit_of_measure="EA",
                )
            ],
        )
        with pytest.raises(ConflictException, match="APPROVED or PARTIALLY_DELIVERED"):
            svc.create_delivery_note(
                company_id=uuid4(),
                data=data,
                created_by=uuid4(),
            )

    def test_create_raises_for_nonexistent_order(self) -> None:
        from decimal import Decimal
        from unittest.mock import MagicMock
        from uuid import uuid4

        from modules.sales.schemas.delivery import (
            DeliveryNoteCreate,
            DeliveryNoteLineCreate,
        )
        from modules.sales.services.delivery_service import DeliveryService

        db = MagicMock()
        svc = DeliveryService(db)
        svc._order_repo = MagicMock()
        svc._order_repo.get_by_id_or_none.return_value = None

        order_id = uuid4()
        data = DeliveryNoteCreate(
            order_id=order_id,
            lines=[
                DeliveryNoteLineCreate(
                    order_line_id=uuid4(),
                    description="Test",
                    quantity_dispatched=Decimal("1"),
                    unit_of_measure="EA",
                )
            ],
        )
        from core.exceptions.base import NotFoundException

        with pytest.raises(NotFoundException):
            svc.create_delivery_note(
                company_id=uuid4(),
                data=data,
                created_by=uuid4(),
            )

    def test_dispatch_raises_for_invalid_transition(self) -> None:
        from unittest.mock import MagicMock
        from uuid import uuid4

        from modules.sales.schemas.delivery import DeliveryNoteDispatch
        from modules.sales.services.delivery_service import DeliveryService

        db = MagicMock()
        svc = DeliveryService(db)
        dn = MagicMock()
        dn.status = "DELIVERED"
        svc._dn_repo = MagicMock()
        svc._dn_repo.get_by_id_or_none.return_value = dn

        with pytest.raises(ConflictException):
            svc.dispatch(
                company_id=uuid4(),
                delivery_note_id=uuid4(),
                data=DeliveryNoteDispatch(dispatch_date="2026-08-03"),
                dispatched_by=uuid4(),
            )

    def test_cancel_delivered_raises(self) -> None:
        from unittest.mock import MagicMock
        from uuid import uuid4

        from modules.sales.services.delivery_service import DeliveryService

        db = MagicMock()
        svc = DeliveryService(db)
        dn = MagicMock()
        dn.status = "DELIVERED"
        svc._dn_repo = MagicMock()
        svc._dn_repo.get_by_id_or_none.return_value = dn

        with pytest.raises(ConflictException):
            svc.cancel(
                company_id=uuid4(),
                delivery_note_id=uuid4(),
                cancelled_by=uuid4(),
            )
