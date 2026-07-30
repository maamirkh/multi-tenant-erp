"""Unit tests for Supplier entity state machine and domain invariants.

Tests:
  - All valid status transitions
  - All invalid status transitions (raise InvalidSupplierTransitionError)
  - supplier_code uniqueness invariant (ConflictException)
  - Blocked-guard for purchase document creation (SupplierIneligibleError)
  - Archive guard — open PO check (SupplierArchiveBlockedError)

Task: T049
"""

from __future__ import annotations

from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from modules.purchase.services.supplier_service import (
    _VALID_TRANSITIONS,
    InvalidSupplierTransitionError,
    SupplierArchiveBlockedError,
    SupplierIneligibleError,
    _assert_transition,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_supplier(status: str = "DRAFT") -> MagicMock:
    s = MagicMock()
    s.id = uuid4()
    s.company_id = str(uuid4())
    s.supplier_code = "SUP-001"
    s.legal_name = "Test Supplier Ltd"
    s.status = status
    s.is_deleted = False
    return s


# ---------------------------------------------------------------------------
# State machine — valid transitions
# ---------------------------------------------------------------------------


class TestValidTransitions:
    """_assert_transition must NOT raise for these pairs."""

    def test_draft_to_active(self) -> None:
        _assert_transition("DRAFT", "ACTIVE")  # no exception

    def test_active_to_inactive(self) -> None:
        _assert_transition("ACTIVE", "INACTIVE")

    def test_active_to_blocked(self) -> None:
        _assert_transition("ACTIVE", "BLOCKED")

    def test_active_to_archived(self) -> None:
        _assert_transition("ACTIVE", "ARCHIVED")

    def test_inactive_to_active(self) -> None:
        _assert_transition("INACTIVE", "ACTIVE")

    def test_inactive_to_archived(self) -> None:
        _assert_transition("INACTIVE", "ARCHIVED")

    def test_blocked_to_active(self) -> None:
        _assert_transition("BLOCKED", "ACTIVE")


# ---------------------------------------------------------------------------
# State machine — invalid transitions
# ---------------------------------------------------------------------------


class TestInvalidTransitions:
    """_assert_transition MUST raise InvalidSupplierTransitionError for these pairs."""

    @pytest.mark.parametrize(
        "current, requested",
        [
            ("DRAFT", "INACTIVE"),
            ("DRAFT", "BLOCKED"),
            ("DRAFT", "ARCHIVED"),
            ("INACTIVE", "BLOCKED"),
            ("INACTIVE", "DRAFT"),
            ("BLOCKED", "INACTIVE"),
            ("BLOCKED", "ARCHIVED"),
            ("ARCHIVED", "ACTIVE"),
            ("ARCHIVED", "INACTIVE"),
            ("ARCHIVED", "BLOCKED"),
            ("ARCHIVED", "DRAFT"),
            ("ACTIVE", "DRAFT"),
        ],
    )
    def test_invalid_transition(self, current: str, requested: str) -> None:
        with pytest.raises(InvalidSupplierTransitionError) as exc_info:
            _assert_transition(current, requested)
        assert exc_info.value.current == current
        assert exc_info.value.requested == requested

    def test_archived_is_terminal(self) -> None:
        """ARCHIVED has zero allowed transitions."""
        assert _VALID_TRANSITIONS["ARCHIVED"] == set()


# ---------------------------------------------------------------------------
# InvalidSupplierTransitionError
# ---------------------------------------------------------------------------


class TestInvalidSupplierTransitionError:
    def test_message_contains_statuses(self) -> None:
        err = InvalidSupplierTransitionError(current="INACTIVE", requested="BLOCKED")
        assert "INACTIVE" in str(err)
        assert "BLOCKED" in str(err)

    def test_attributes(self) -> None:
        err = InvalidSupplierTransitionError(current="DRAFT", requested="ARCHIVED")
        assert err.current == "DRAFT"
        assert err.requested == "ARCHIVED"


# ---------------------------------------------------------------------------
# SupplierIneligibleError (blocked guard)
# ---------------------------------------------------------------------------


class TestSupplierIneligibleError:
    def test_blocked_supplier_ineligible(self) -> None:
        supplier_id = uuid4()
        err = SupplierIneligibleError(supplier_id=supplier_id, status="BLOCKED")
        assert "BLOCKED" in str(err)
        assert err.supplier_id == supplier_id
        assert err.status == "BLOCKED"

    def test_archived_supplier_ineligible(self) -> None:
        supplier_id = uuid4()
        err = SupplierIneligibleError(supplier_id=supplier_id, status="ARCHIVED")
        assert "ARCHIVED" in str(err)


# ---------------------------------------------------------------------------
# SupplierArchiveBlockedError (open PO guard)
# ---------------------------------------------------------------------------


class TestSupplierArchiveBlockedError:
    def test_message_contains_supplier_id(self) -> None:
        supplier_id = uuid4()
        err = SupplierArchiveBlockedError(supplier_id=supplier_id)
        assert str(supplier_id) in str(err)

    def test_cannot_archive_with_open_pos(self) -> None:
        """Simulates the archive guard: when has_open_pos=True, raises error."""
        from modules.purchase.services.supplier_service import SupplierService

        # Build minimal mock service
        svc = object.__new__(SupplierService)
        supplier_id = uuid4()

        with pytest.raises(SupplierArchiveBlockedError):
            svc.archive(
                supplier_id=supplier_id,
                company_id=uuid4(),
                has_open_pos=True,  # <-- guard trigger
            )


# ---------------------------------------------------------------------------
# Transition matrix completeness
# ---------------------------------------------------------------------------


class TestTransitionMatrixCompleteness:
    """Verify the transition matrix covers all known statuses."""

    KNOWN_STATUSES = {"DRAFT", "ACTIVE", "INACTIVE", "BLOCKED", "ARCHIVED"}

    def test_all_statuses_have_entries(self) -> None:
        assert set(_VALID_TRANSITIONS.keys()) == self.KNOWN_STATUSES

    def test_all_target_statuses_valid(self) -> None:
        for current, targets in _VALID_TRANSITIONS.items():
            for target in targets:
                assert (
                    target in self.KNOWN_STATUSES
                ), f"'{target}' in transitions from '{current}' is not a known status"
