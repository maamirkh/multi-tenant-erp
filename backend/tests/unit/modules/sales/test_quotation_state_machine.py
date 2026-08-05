"""Unit tests for QuotationService state machine — Phase 3.

Tests:
  - All valid state transitions
  - Invalid state transitions raise ValueError
  - _assert_transition helper
  - terminal state blocking

Task: T100
Spec ref: specs/007-sales-management/data-model.md §SalesQuotation State Machine
"""

from __future__ import annotations

import pytest

from modules.sales.services.quotation_service import (
    _TERMINAL_STATUSES,
    _VALID_TRANSITIONS,
    _assert_transition,
)


class TestStateMachineDefinition:
    """Validate the state machine transition table."""

    def test_draft_transitions(self) -> None:
        allowed = _VALID_TRANSITIONS["DRAFT"]
        assert "SENT_TO_CUSTOMER" in allowed
        assert "CANCELLED" in allowed

    def test_sent_to_customer_transitions(self) -> None:
        allowed = _VALID_TRANSITIONS["SENT_TO_CUSTOMER"]
        assert "ACCEPTED" in allowed
        assert "REJECTED" in allowed
        assert "EXPIRED" in allowed
        assert "CANCELLED" in allowed

    def test_accepted_transitions(self) -> None:
        allowed = _VALID_TRANSITIONS["ACCEPTED"]
        assert "CONVERTED" in allowed
        assert "CANCELLED" in allowed

    def test_terminal_statuses_have_no_transitions(self) -> None:
        for terminal in _TERMINAL_STATUSES:
            assert (
                _VALID_TRANSITIONS[terminal] == []
            ), f"{terminal} should have no transitions"

    def test_terminal_statuses_set(self) -> None:
        assert _TERMINAL_STATUSES == {
            "REJECTED",
            "CONVERTED",
            "EXPIRED",
            "CANCELLED",
        }


class TestAssertTransition:
    """Test _assert_transition helper raises on invalid transitions."""

    # --- Valid transitions ---

    def test_draft_to_sent(self) -> None:
        _assert_transition("DRAFT", "SENT_TO_CUSTOMER")  # should not raise

    def test_draft_to_cancelled(self) -> None:
        _assert_transition("DRAFT", "CANCELLED")

    def test_sent_to_accepted(self) -> None:
        _assert_transition("SENT_TO_CUSTOMER", "ACCEPTED")

    def test_sent_to_rejected(self) -> None:
        _assert_transition("SENT_TO_CUSTOMER", "REJECTED")

    def test_sent_to_expired(self) -> None:
        _assert_transition("SENT_TO_CUSTOMER", "EXPIRED")

    def test_sent_to_cancelled(self) -> None:
        _assert_transition("SENT_TO_CUSTOMER", "CANCELLED")

    def test_accepted_to_converted(self) -> None:
        _assert_transition("ACCEPTED", "CONVERTED")

    def test_accepted_to_cancelled(self) -> None:
        _assert_transition("ACCEPTED", "CANCELLED")

    # --- Invalid transitions ---

    def test_draft_cannot_go_to_accepted(self) -> None:
        with pytest.raises(ValueError, match="Invalid quotation status transition"):
            _assert_transition("DRAFT", "ACCEPTED")

    def test_draft_cannot_go_to_converted(self) -> None:
        with pytest.raises(ValueError, match="Invalid quotation status transition"):
            _assert_transition("DRAFT", "CONVERTED")

    def test_draft_cannot_go_to_expired(self) -> None:
        with pytest.raises(ValueError, match="Invalid quotation status transition"):
            _assert_transition("DRAFT", "EXPIRED")

    def test_sent_cannot_go_to_converted_directly(self) -> None:
        with pytest.raises(ValueError, match="Invalid quotation status transition"):
            _assert_transition("SENT_TO_CUSTOMER", "CONVERTED")

    def test_accepted_cannot_go_to_rejected(self) -> None:
        with pytest.raises(ValueError, match="Invalid quotation status transition"):
            _assert_transition("ACCEPTED", "REJECTED")

    def test_accepted_cannot_go_to_expired(self) -> None:
        with pytest.raises(ValueError, match="Invalid quotation status transition"):
            _assert_transition("ACCEPTED", "EXPIRED")

    def test_rejected_is_terminal(self) -> None:
        with pytest.raises(ValueError, match="Invalid quotation status transition"):
            _assert_transition("REJECTED", "DRAFT")

    def test_converted_is_terminal(self) -> None:
        with pytest.raises(ValueError, match="Invalid quotation status transition"):
            _assert_transition("CONVERTED", "DRAFT")

    def test_expired_is_terminal(self) -> None:
        with pytest.raises(ValueError, match="Invalid quotation status transition"):
            _assert_transition("EXPIRED", "DRAFT")

    def test_cancelled_is_terminal(self) -> None:
        with pytest.raises(ValueError, match="Invalid quotation status transition"):
            _assert_transition("CANCELLED", "DRAFT")

    def test_error_message_includes_from_to(self) -> None:
        with pytest.raises(ValueError, match="DRAFT.*ACCEPTED"):
            _assert_transition("DRAFT", "ACCEPTED")

    def test_error_message_includes_allowed_list(self) -> None:
        with pytest.raises(ValueError, match="Allowed:"):
            _assert_transition("DRAFT", "ACCEPTED")
