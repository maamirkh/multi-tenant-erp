"""Unit tests for Supplier domain business rules — Phase 1.

Tests:
  - BLOCKED supplier rejected when used for purchase document creation
  - ARCHIVED supplier rejected when used for purchase document creation
  - ACTIVE/INACTIVE/DRAFT supplier passes eligibility check
  - Supplier with open POs cannot be archived (SupplierArchiveBlockedError)
  - Supplier without open POs can be archived (guard does not fire)
  - archive() guard fires before DB lookup (has_open_pos=True raises immediately)

Task: T053
Spec ref: specs/006-purchase-management/spec.md §14.3 Supplier Lifecycle Rules
"""

from __future__ import annotations

from unittest.mock import MagicMock
from uuid import UUID, uuid4

import pytest

from modules.purchase.services.supplier_service import (
    InvalidSupplierTransitionError,
    SupplierArchiveBlockedError,
    SupplierIneligibleError,
    SupplierService,
    _assert_transition,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_supplier(status: str = "ACTIVE") -> MagicMock:
    s = MagicMock()
    s.id = uuid4()
    s.company_id = str(uuid4())
    s.supplier_code = "SUP-001"
    s.legal_name = "Test Supplier Ltd"
    s.status = status
    s.is_deleted = False
    return s


def _service_with_supplier(
    status: str,
) -> tuple[SupplierService, MagicMock, UUID, UUID]:
    """Return a SupplierService with a mocked supplier of the given status."""
    svc = object.__new__(SupplierService)

    supplier = _mock_supplier(status)
    supplier_id = supplier.id
    company_id = uuid4()

    # Wire up minimal mocks so _get_or_raise works
    repo = MagicMock()
    repo.get_by_id_or_none.return_value = supplier

    svc._repo = repo
    svc._contact_repo = MagicMock()
    svc._address_repo = MagicMock()
    svc.db = MagicMock()
    svc._event_bus = MagicMock()

    return svc, supplier, supplier_id, company_id


# ---------------------------------------------------------------------------
# Eligibility guard — BLOCKED supplier
# ---------------------------------------------------------------------------


class TestBlockedSupplierIneligible:
    def test_blocked_supplier_raises_ineligible(self) -> None:
        svc, supplier, sid, cid = _service_with_supplier("BLOCKED")

        with pytest.raises(SupplierIneligibleError) as exc_info:
            svc.check_supplier_eligible(supplier_id=sid, company_id=cid)

        err = exc_info.value
        assert err.supplier_id == sid
        assert err.status == "BLOCKED"

    def test_blocked_error_message_contains_blocked(self) -> None:
        err = SupplierIneligibleError(supplier_id=uuid4(), status="BLOCKED")
        assert "BLOCKED" in str(err)

    def test_blocked_error_exposes_supplier_id_and_status(self) -> None:
        sid = uuid4()
        err = SupplierIneligibleError(supplier_id=sid, status="BLOCKED")
        assert err.supplier_id == sid
        assert err.status == "BLOCKED"


# ---------------------------------------------------------------------------
# Eligibility guard — ARCHIVED supplier
# ---------------------------------------------------------------------------


class TestArchivedSupplierIneligible:
    def test_archived_supplier_raises_ineligible(self) -> None:
        svc, supplier, sid, cid = _service_with_supplier("ARCHIVED")

        with pytest.raises(SupplierIneligibleError) as exc_info:
            svc.check_supplier_eligible(supplier_id=sid, company_id=cid)

        err = exc_info.value
        assert err.supplier_id == sid
        assert err.status == "ARCHIVED"

    def test_archived_error_message_contains_archived(self) -> None:
        err = SupplierIneligibleError(supplier_id=uuid4(), status="ARCHIVED")
        assert "ARCHIVED" in str(err)


# ---------------------------------------------------------------------------
# Eligibility guard — eligible statuses pass
# ---------------------------------------------------------------------------


class TestEligibleSupplier:
    @pytest.mark.parametrize("status", ["ACTIVE", "DRAFT", "INACTIVE"])
    def test_eligible_status_does_not_raise(self, status: str) -> None:
        svc, supplier, sid, cid = _service_with_supplier(status)
        result = svc.check_supplier_eligible(supplier_id=sid, company_id=cid)
        assert result is supplier

    def test_active_supplier_returns_supplier_object(self) -> None:
        svc, supplier, sid, cid = _service_with_supplier("ACTIVE")
        result = svc.check_supplier_eligible(supplier_id=sid, company_id=cid)
        assert result.status == "ACTIVE"


# ---------------------------------------------------------------------------
# Archive guard — open PO check
# ---------------------------------------------------------------------------


class TestArchiveGuard:
    def test_archive_with_open_pos_raises_immediately(self) -> None:
        """has_open_pos=True must raise before any DB lookup."""
        svc = object.__new__(SupplierService)
        # No DB or repo wired — if the guard fires before DB access this is fine.

        with pytest.raises(SupplierArchiveBlockedError):
            svc.archive(
                supplier_id=uuid4(),
                company_id=uuid4(),
                has_open_pos=True,
            )

    def test_archive_error_message_contains_supplier_id(self) -> None:
        sid = uuid4()
        err = SupplierArchiveBlockedError(supplier_id=sid)
        assert str(sid) in str(err)

    def test_archive_error_is_exception_subclass(self) -> None:
        err = SupplierArchiveBlockedError(supplier_id=uuid4())
        assert isinstance(err, Exception)

    def test_archive_without_open_pos_does_not_raise_guard(self) -> None:
        """archive() with has_open_pos=False must NOT raise SupplierArchiveBlockedError.

        It will raise later (NotFoundException or AttributeError) because we
        pass no real DB, but the open-PO guard must not fire.
        """
        svc = object.__new__(SupplierService)
        sid = uuid4()

        try:
            svc.archive(supplier_id=sid, company_id=uuid4(), has_open_pos=False)
        except SupplierArchiveBlockedError:
            pytest.fail("SupplierArchiveBlockedError raised when has_open_pos=False")
        except Exception:
            # Other errors expected (no real DB/repo attached)
            pass


# ---------------------------------------------------------------------------
# Transition guards — invalid transitions trigger error
# ---------------------------------------------------------------------------


class TestInvalidTransitionGuards:
    @pytest.mark.parametrize(
        "current, target",
        [
            ("DRAFT", "INACTIVE"),
            ("DRAFT", "BLOCKED"),
            ("DRAFT", "ARCHIVED"),
            ("INACTIVE", "BLOCKED"),
            ("BLOCKED", "ARCHIVED"),
            ("ARCHIVED", "ACTIVE"),
            ("ARCHIVED", "INACTIVE"),
            ("ARCHIVED", "BLOCKED"),
        ],
    )
    def test_invalid_transition_raises(self, current: str, target: str) -> None:
        with pytest.raises(InvalidSupplierTransitionError) as exc_info:
            _assert_transition(current, target)

        err = exc_info.value
        assert err.current == current
        assert err.requested == target

    def test_error_message_contains_both_statuses(self) -> None:
        try:
            _assert_transition("DRAFT", "BLOCKED")
        except InvalidSupplierTransitionError as err:
            assert "DRAFT" in str(err)
            assert "BLOCKED" in str(err)


# ---------------------------------------------------------------------------
# Compound business rule: BLOCKED/ARCHIVED → cannot use in purchase doc
# ---------------------------------------------------------------------------


class TestPurchaseDocumentEligibilityRule:
    """Verify the compound rule: when a supplier is BLOCKED or ARCHIVED,
    the service must reject purchase document creation attempts.
    """

    def test_blocked_supplier_rejected_for_new_purchase(self) -> None:
        svc, _, sid, cid = _service_with_supplier("BLOCKED")

        with pytest.raises(SupplierIneligibleError) as exc_info:
            svc.check_supplier_eligible(supplier_id=sid, company_id=cid)

        assert "BLOCKED" in str(exc_info.value)

    def test_archived_supplier_rejected_for_new_purchase(self) -> None:
        svc, _, sid, cid = _service_with_supplier("ARCHIVED")

        with pytest.raises(SupplierIneligibleError) as exc_info:
            svc.check_supplier_eligible(supplier_id=sid, company_id=cid)

        assert "ARCHIVED" in str(exc_info.value)

    def test_active_supplier_allowed_for_new_purchase(self) -> None:
        svc, supplier, sid, cid = _service_with_supplier("ACTIVE")
        result = svc.check_supplier_eligible(supplier_id=sid, company_id=cid)
        assert result is not None

    def test_inactive_supplier_allowed_for_new_purchase(self) -> None:
        """INACTIVE suppliers are not blocked — they can be reactivated."""
        svc, supplier, sid, cid = _service_with_supplier("INACTIVE")
        result = svc.check_supplier_eligible(supplier_id=sid, company_id=cid)
        assert result is not None
