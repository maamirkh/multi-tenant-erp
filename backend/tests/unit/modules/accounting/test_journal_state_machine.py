"""Unit tests for JournalEntryStateMachine — Phase 4.

Tests:
  - All valid transitions succeed
  - All invalid transitions raise InvalidJournalStateTransitionError
  - POSTED is immutable except for the single REVERSED outgoing edge
  - REJECTED and REVERSED are terminal

Spec ref: specs/008-accounting-finance/tasks.md T108
"""

from __future__ import annotations

import pytest

from modules.accounting.exceptions import InvalidJournalStateTransitionError
from modules.accounting.services.posting_engine import JournalEntryStateMachine

ALL_STATUSES = ["DRAFT", "SUBMITTED", "APPROVED", "POSTED", "REJECTED", "REVERSED"]


class TestValidTransitions:
    @pytest.mark.parametrize(
        "current,target",
        [
            ("DRAFT", "SUBMITTED"),
            ("DRAFT", "POSTED"),
            ("SUBMITTED", "APPROVED"),
            ("SUBMITTED", "REJECTED"),
            ("APPROVED", "POSTED"),
            ("POSTED", "REVERSED"),
        ],
    )
    def test_valid_transition_does_not_raise(self, current: str, target: str) -> None:
        JournalEntryStateMachine.validate_transition(current, target)


class TestInvalidTransitions:
    @pytest.mark.parametrize(
        "current,target",
        [
            ("DRAFT", "APPROVED"),
            ("DRAFT", "REJECTED"),
            ("DRAFT", "REVERSED"),
            ("DRAFT", "DRAFT"),
            ("SUBMITTED", "POSTED"),
            ("SUBMITTED", "DRAFT"),
            ("SUBMITTED", "REVERSED"),
            ("APPROVED", "DRAFT"),
            ("APPROVED", "SUBMITTED"),
            ("APPROVED", "REJECTED"),
            ("APPROVED", "REVERSED"),
            ("POSTED", "DRAFT"),
            ("POSTED", "SUBMITTED"),
            ("POSTED", "APPROVED"),
            ("POSTED", "POSTED"),
            ("POSTED", "REJECTED"),
        ],
    )
    def test_invalid_transition_raises(self, current: str, target: str) -> None:
        with pytest.raises(InvalidJournalStateTransitionError):
            JournalEntryStateMachine.validate_transition(current, target)


class TestTerminalStates:
    @pytest.mark.parametrize("target", ALL_STATUSES)
    def test_rejected_has_no_outgoing_transition(self, target: str) -> None:
        with pytest.raises(InvalidJournalStateTransitionError):
            JournalEntryStateMachine.validate_transition("REJECTED", target)

    @pytest.mark.parametrize("target", ALL_STATUSES)
    def test_reversed_has_no_outgoing_transition(self, target: str) -> None:
        with pytest.raises(InvalidJournalStateTransitionError):
            JournalEntryStateMachine.validate_transition("REVERSED", target)


class TestPostedImmutableExceptReversal:
    def test_posted_only_valid_outgoing_edge_is_reversed(self) -> None:
        for target in ALL_STATUSES:
            if target == "REVERSED":
                JournalEntryStateMachine.validate_transition("POSTED", target)
            else:
                with pytest.raises(InvalidJournalStateTransitionError):
                    JournalEntryStateMachine.validate_transition("POSTED", target)
