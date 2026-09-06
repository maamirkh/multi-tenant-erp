"""Unit tests for FiscalPeriodStateMachine — Phase 3.

Tests:
  - All valid transitions succeed (OPEN->LOCKED, LOCKED->OPEN, LOCKED->CLOSED)
  - All invalid transitions raise InvalidFiscalPeriodTransitionError
  - CLOSED is terminal (no outgoing transition is ever valid)

Spec ref: specs/008-accounting-finance/tasks.md T084
"""

from __future__ import annotations

import pytest

from modules.accounting.exceptions import InvalidFiscalPeriodTransitionError
from modules.accounting.services.fiscal_service import FiscalPeriodStateMachine


class TestValidTransitions:
    def test_open_to_locked(self) -> None:
        FiscalPeriodStateMachine.validate_transition("OPEN", "LOCKED")

    def test_locked_to_open(self) -> None:
        FiscalPeriodStateMachine.validate_transition("LOCKED", "OPEN")

    def test_locked_to_closed(self) -> None:
        FiscalPeriodStateMachine.validate_transition("LOCKED", "CLOSED")


class TestInvalidTransitions:
    def test_open_to_closed_direct_rejected(self) -> None:
        with pytest.raises(InvalidFiscalPeriodTransitionError):
            FiscalPeriodStateMachine.validate_transition("OPEN", "CLOSED")

    def test_open_to_open_rejected(self) -> None:
        with pytest.raises(InvalidFiscalPeriodTransitionError):
            FiscalPeriodStateMachine.validate_transition("OPEN", "OPEN")

    def test_locked_to_locked_rejected(self) -> None:
        with pytest.raises(InvalidFiscalPeriodTransitionError):
            FiscalPeriodStateMachine.validate_transition("LOCKED", "LOCKED")

    def test_closed_to_open_rejected(self) -> None:
        with pytest.raises(InvalidFiscalPeriodTransitionError):
            FiscalPeriodStateMachine.validate_transition("CLOSED", "OPEN")

    def test_closed_to_locked_rejected(self) -> None:
        with pytest.raises(InvalidFiscalPeriodTransitionError):
            FiscalPeriodStateMachine.validate_transition("CLOSED", "LOCKED")

    def test_closed_to_closed_rejected(self) -> None:
        with pytest.raises(InvalidFiscalPeriodTransitionError):
            FiscalPeriodStateMachine.validate_transition("CLOSED", "CLOSED")


class TestClosedIsTerminal:
    def test_no_outgoing_transition_from_closed(self) -> None:
        for target in ("OPEN", "LOCKED", "CLOSED"):
            with pytest.raises(InvalidFiscalPeriodTransitionError):
                FiscalPeriodStateMachine.validate_transition("CLOSED", target)
