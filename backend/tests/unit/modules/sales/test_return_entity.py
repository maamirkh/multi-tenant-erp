"""Unit tests for Sales Return entity — Phase 7.

Tests:
  - State machine: valid transitions
  - State machine: invalid transitions
  - Schema validators: ReturnLineCreate, SalesReturnCreate, ReturnRejectRequest
  - Resolution types: CREDIT_NOTE, REPLACEMENT, REFUND_READINESS

Task: T199
Spec ref: specs/007-sales-management/spec.md §19 Sales Returns
"""

from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

import pytest

from core.exceptions.base import ConflictException
from modules.sales.schemas.sales_return import (
    ReturnLineCreate,
    ReturnRejectRequest,
    SalesReturnCreate,
)
from modules.sales.services.return_service import (
    _VALID_TRANSITIONS,
    _assert_return_transition,
)

# ---------------------------------------------------------------------------
# State machine tests
# ---------------------------------------------------------------------------


class TestReturnStateMachine:
    """State machine transition rules."""

    def test_draft_to_pending_approval(self) -> None:
        _assert_return_transition("DRAFT", "PENDING_APPROVAL")  # should not raise

    def test_draft_to_cancelled(self) -> None:
        _assert_return_transition("DRAFT", "CANCELLED")

    def test_pending_approval_to_approved(self) -> None:
        _assert_return_transition("PENDING_APPROVAL", "APPROVED")

    def test_pending_approval_to_rejected(self) -> None:
        _assert_return_transition("PENDING_APPROVAL", "REJECTED")

    def test_pending_approval_to_cancelled(self) -> None:
        _assert_return_transition("PENDING_APPROVAL", "CANCELLED")

    def test_approved_to_received(self) -> None:
        _assert_return_transition("APPROVED", "RECEIVED")

    def test_received_to_completed(self) -> None:
        _assert_return_transition("RECEIVED", "COMPLETED")

    def test_completed_is_terminal(self) -> None:
        with pytest.raises(ConflictException):
            _assert_return_transition("COMPLETED", "RECEIVED")

    def test_rejected_is_terminal(self) -> None:
        with pytest.raises(ConflictException):
            _assert_return_transition("REJECTED", "APPROVED")

    def test_cancelled_is_terminal(self) -> None:
        with pytest.raises(ConflictException):
            _assert_return_transition("CANCELLED", "DRAFT")

    def test_invalid_transition_raises(self) -> None:
        with pytest.raises(ConflictException, match="Invalid return status transition"):
            _assert_return_transition("DRAFT", "RECEIVED")

    def test_draft_cannot_skip_to_approved(self) -> None:
        with pytest.raises(ConflictException):
            _assert_return_transition("DRAFT", "APPROVED")

    def test_approved_cannot_skip_to_completed(self) -> None:
        with pytest.raises(ConflictException):
            _assert_return_transition("APPROVED", "COMPLETED")

    def test_valid_transitions_all_states_covered(self) -> None:
        expected_states = {
            "DRAFT",
            "PENDING_APPROVAL",
            "APPROVED",
            "REJECTED",
            "RECEIVED",
            "COMPLETED",
            "CANCELLED",
        }
        assert set(_VALID_TRANSITIONS.keys()) == expected_states


# ---------------------------------------------------------------------------
# Schema validator tests
# ---------------------------------------------------------------------------


class TestReturnLineCreateSchema:
    """ReturnLineCreate field validators."""

    def test_valid_line(self) -> None:
        line = ReturnLineCreate(
            description="Widget A",
            quantity_returned=Decimal("2"),
            unit_price=Decimal("10.00"),
            condition="USED",
        )
        assert line.quantity_returned == Decimal("2")

    def test_quantity_must_be_positive(self) -> None:
        with pytest.raises(ValueError, match="positive"):
            ReturnLineCreate(
                description="Widget",
                quantity_returned=Decimal("0"),
                unit_price=Decimal("10.00"),
            )

    def test_negative_quantity_rejected(self) -> None:
        with pytest.raises(ValueError, match="positive"):
            ReturnLineCreate(
                description="Widget",
                quantity_returned=Decimal("-1"),
                unit_price=Decimal("10.00"),
            )

    def test_negative_unit_price_rejected(self) -> None:
        with pytest.raises(ValueError, match="negative"):
            ReturnLineCreate(
                description="Widget",
                quantity_returned=Decimal("1"),
                unit_price=Decimal("-0.01"),
            )

    def test_zero_unit_price_allowed(self) -> None:
        line = ReturnLineCreate(
            description="Freebie",
            quantity_returned=Decimal("1"),
            unit_price=Decimal("0"),
        )
        assert line.unit_price == Decimal("0")

    def test_with_product_id(self) -> None:
        pid = uuid4()
        line = ReturnLineCreate(
            product_id=pid,
            description="Widget",
            quantity_returned=Decimal("1"),
            unit_price=Decimal("5"),
        )
        assert line.product_id == pid

    def test_condition_default_used(self) -> None:
        line = ReturnLineCreate(
            description="Item",
            quantity_returned=Decimal("1"),
            unit_price=Decimal("1"),
        )
        assert line.condition == "USED"

    def test_valid_conditions(self) -> None:
        for cond in ("NEW", "USED", "DAMAGED", "DEFECTIVE"):
            line = ReturnLineCreate(
                description="Item",
                quantity_returned=Decimal("1"),
                unit_price=Decimal("1"),
                condition=cond,
            )
            assert line.condition == cond


class TestSalesReturnCreateSchema:
    """SalesReturnCreate validators."""

    def _make_line(self) -> ReturnLineCreate:
        return ReturnLineCreate(
            description="Widget",
            quantity_returned=Decimal("1"),
            unit_price=Decimal("10"),
        )

    def test_valid_return(self) -> None:
        ret = SalesReturnCreate(
            customer_id=uuid4(),
            return_date="2026-08-04",
            reason_code_id=uuid4(),
            lines=[self._make_line()],
        )
        assert ret.resolution_type == "CREDIT_NOTE"

    def test_empty_lines_rejected(self) -> None:
        with pytest.raises(ValueError, match="At least one"):
            SalesReturnCreate(
                customer_id=uuid4(),
                return_date="2026-08-04",
                reason_code_id=uuid4(),
                lines=[],
            )

    def test_resolution_types(self) -> None:
        for rt in ("CREDIT_NOTE", "REPLACEMENT", "REFUND_READINESS"):
            ret = SalesReturnCreate(
                customer_id=uuid4(),
                return_date="2026-08-04",
                reason_code_id=uuid4(),
                resolution_type=rt,
                lines=[self._make_line()],
            )
            assert ret.resolution_type == rt

    def test_with_order_id(self) -> None:
        oid = uuid4()
        ret = SalesReturnCreate(
            customer_id=uuid4(),
            order_id=oid,
            return_date="2026-08-04",
            reason_code_id=uuid4(),
            lines=[self._make_line()],
        )
        assert ret.order_id == oid


class TestReturnRejectRequestSchema:
    """ReturnRejectRequest validators."""

    def test_valid_reason(self) -> None:
        req = ReturnRejectRequest(rejection_reason="Items were not defective")
        assert req.rejection_reason == "Items were not defective"

    def test_empty_reason_rejected(self) -> None:
        with pytest.raises(ValueError, match="cannot be empty"):
            ReturnRejectRequest(rejection_reason="")

    def test_whitespace_only_rejected(self) -> None:
        with pytest.raises(ValueError, match="cannot be empty"):
            ReturnRejectRequest(rejection_reason="   ")
