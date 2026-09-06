"""Unit tests for Sales Order state machine — Phase 4.

Tests:
  - All valid state transitions per _VALID_TRANSITIONS
  - Invalid transitions raise ConflictException
  - Terminal statuses (CLOSED, CANCELLED) have no outgoing transitions
  - _IMMUTABLE_STATUSES contains expected statuses
  - Error message includes from/to and allowed list

Task: T128
Spec ref: specs/007-sales-management/spec.md §Sales Orders
"""

from __future__ import annotations

import pytest

from core.exceptions.base import ConflictException
from modules.sales.services.order_service import (
    _IMMUTABLE_STATUSES,
    _TERMINAL_STATUSES,
    _VALID_TRANSITIONS,
    _assert_transition,
)


class TestStateMachineDefinition:
    """Validate the state machine transition table structure."""

    def test_draft_transitions(self) -> None:
        allowed = _VALID_TRANSITIONS["DRAFT"]
        assert "PENDING_APPROVAL" in allowed
        assert "CANCELLED" in allowed

    def test_pending_approval_transitions(self) -> None:
        allowed = _VALID_TRANSITIONS["PENDING_APPROVAL"]
        assert "APPROVED" in allowed
        assert "REJECTED" in allowed

    def test_approved_transitions(self) -> None:
        allowed = _VALID_TRANSITIONS["APPROVED"]
        assert "PARTIALLY_DELIVERED" in allowed
        assert "DELIVERED" in allowed
        assert "CANCELLED" in allowed

    def test_rejected_transitions(self) -> None:
        # Rejection path returns to DRAFT for revision
        allowed = _VALID_TRANSITIONS["REJECTED"]
        assert "DRAFT" in allowed

    def test_partially_delivered_transitions(self) -> None:
        allowed = _VALID_TRANSITIONS["PARTIALLY_DELIVERED"]
        assert "DELIVERED" in allowed

    def test_delivered_transitions(self) -> None:
        allowed = _VALID_TRANSITIONS["DELIVERED"]
        assert "INVOICED" in allowed

    def test_invoiced_transitions(self) -> None:
        allowed = _VALID_TRANSITIONS["INVOICED"]
        assert "CLOSED" in allowed

    def test_terminal_statuses_have_no_transitions(self) -> None:
        for terminal in _TERMINAL_STATUSES:
            assert _VALID_TRANSITIONS[terminal] == [], (
                f"{terminal} should have no transitions"
            )

    def test_terminal_statuses_set(self) -> None:
        assert "CLOSED" in _TERMINAL_STATUSES
        assert "CANCELLED" in _TERMINAL_STATUSES

    def test_immutable_statuses_set(self) -> None:
        assert "PENDING_APPROVAL" in _IMMUTABLE_STATUSES
        assert "APPROVED" in _IMMUTABLE_STATUSES
        assert "PARTIALLY_DELIVERED" in _IMMUTABLE_STATUSES
        assert "DELIVERED" in _IMMUTABLE_STATUSES
        assert "INVOICED" in _IMMUTABLE_STATUSES
        assert "CLOSED" in _IMMUTABLE_STATUSES
        assert "CANCELLED" in _IMMUTABLE_STATUSES
        # DRAFT is NOT immutable
        assert "DRAFT" not in _IMMUTABLE_STATUSES

    def test_all_states_represented(self) -> None:
        expected_states = {
            "DRAFT",
            "PENDING_APPROVAL",
            "APPROVED",
            "REJECTED",
            "PARTIALLY_DELIVERED",
            "DELIVERED",
            "INVOICED",
            "CLOSED",
            "CANCELLED",
        }
        assert set(_VALID_TRANSITIONS.keys()) == expected_states


class TestAssertTransition:
    """Test _assert_transition raises ConflictException on invalid transitions."""

    # --- Valid transitions (should not raise) ---

    def test_draft_to_pending_approval(self) -> None:
        _assert_transition("DRAFT", "PENDING_APPROVAL")

    def test_draft_to_cancelled(self) -> None:
        _assert_transition("DRAFT", "CANCELLED")

    def test_pending_approval_to_approved(self) -> None:
        _assert_transition("PENDING_APPROVAL", "APPROVED")

    def test_pending_approval_to_rejected(self) -> None:
        _assert_transition("PENDING_APPROVAL", "REJECTED")

    def test_approved_to_partially_delivered(self) -> None:
        _assert_transition("APPROVED", "PARTIALLY_DELIVERED")

    def test_approved_to_delivered(self) -> None:
        _assert_transition("APPROVED", "DELIVERED")

    def test_approved_to_cancelled(self) -> None:
        _assert_transition("APPROVED", "CANCELLED")

    def test_rejected_to_draft(self) -> None:
        _assert_transition("REJECTED", "DRAFT")

    def test_partially_delivered_to_delivered(self) -> None:
        _assert_transition("PARTIALLY_DELIVERED", "DELIVERED")

    def test_delivered_to_invoiced(self) -> None:
        _assert_transition("DELIVERED", "INVOICED")

    def test_invoiced_to_closed(self) -> None:
        _assert_transition("INVOICED", "CLOSED")

    # --- Invalid transitions ---

    def test_draft_cannot_go_to_approved(self) -> None:
        with pytest.raises(ConflictException):
            _assert_transition("DRAFT", "APPROVED")

    def test_draft_cannot_go_to_delivered(self) -> None:
        with pytest.raises(ConflictException):
            _assert_transition("DRAFT", "DELIVERED")

    def test_draft_cannot_go_to_closed(self) -> None:
        with pytest.raises(ConflictException):
            _assert_transition("DRAFT", "CLOSED")

    def test_pending_approval_cannot_go_to_draft(self) -> None:
        with pytest.raises(ConflictException):
            _assert_transition("PENDING_APPROVAL", "DRAFT")

    def test_pending_approval_cannot_go_to_delivered(self) -> None:
        with pytest.raises(ConflictException):
            _assert_transition("PENDING_APPROVAL", "DELIVERED")

    def test_approved_cannot_go_to_draft(self) -> None:
        with pytest.raises(ConflictException):
            _assert_transition("APPROVED", "DRAFT")

    def test_approved_cannot_go_to_pending_approval(self) -> None:
        with pytest.raises(ConflictException):
            _assert_transition("APPROVED", "PENDING_APPROVAL")

    def test_approved_cannot_go_to_closed(self) -> None:
        with pytest.raises(ConflictException):
            _assert_transition("APPROVED", "CLOSED")

    def test_delivered_cannot_go_to_cancelled(self) -> None:
        with pytest.raises(ConflictException):
            _assert_transition("DELIVERED", "CANCELLED")

    def test_closed_is_terminal(self) -> None:
        with pytest.raises(ConflictException):
            _assert_transition("CLOSED", "DRAFT")

    def test_closed_cannot_go_anywhere(self) -> None:
        for target in [
            "DRAFT",
            "PENDING_APPROVAL",
            "APPROVED",
            "CANCELLED",
            "INVOICED",
        ]:
            with pytest.raises(ConflictException):
                _assert_transition("CLOSED", target)

    def test_cancelled_is_terminal(self) -> None:
        with pytest.raises(ConflictException):
            _assert_transition("CANCELLED", "DRAFT")

    def test_cancelled_cannot_go_anywhere(self) -> None:
        for target in ["DRAFT", "PENDING_APPROVAL", "APPROVED", "CLOSED", "DELIVERED"]:
            with pytest.raises(ConflictException):
                _assert_transition("CANCELLED", target)

    def test_error_message_includes_from_to(self) -> None:
        with pytest.raises(ConflictException, match="DRAFT"):
            _assert_transition("DRAFT", "APPROVED")

    def test_error_message_includes_allowed_list(self) -> None:
        with pytest.raises(ConflictException, match="Allowed:"):
            _assert_transition("DRAFT", "APPROVED")

    def test_error_message_includes_target(self) -> None:
        with pytest.raises(ConflictException, match="CLOSED"):
            _assert_transition("DRAFT", "CLOSED")
