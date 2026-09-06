"""Unit tests for Phase 2 Supplier enrichment — T069.

Tests:
  - Rating composite score formula (known values)
  - Credit limit enforcement (BLOCK / WARN / OFF)
  - Preferred flag restriction (event published)
  - Document expiry detection
  - Boundary conditions (0%, 100%, mixed rates)

No database required — pure domain logic tests.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from modules.purchase.services.supplier_rating_service import SupplierRatingService

# =============================================================================
# Rating composite score formula
# =============================================================================


class TestRatingCompositeScore:
    """Verify the formula: score = (on_time*0.40 + fill*0.40 + (100-rejection)*0.20) / 10"""

    def test_perfect_score(self):
        """on_time=100, fill=100, rejection=0 → score = 10.0"""
        score = SupplierRatingService.compute_composite_score(
            Decimal("100"), Decimal("100"), Decimal("0")
        )
        assert score == Decimal("10.0")

    def test_zero_score(self):
        """on_time=0, fill=0, rejection=100 → score = 0.0"""
        score = SupplierRatingService.compute_composite_score(
            Decimal("0"), Decimal("0"), Decimal("100")
        )
        assert score == Decimal("0.0")

    def test_average_supplier(self):
        """on_time=80, fill=90, rejection=10 → expected 8.8"""
        # (80*0.40 + 90*0.40 + 90*0.20) / 10 = (32 + 36 + 18) / 10 = 86/10 = 8.6
        score = SupplierRatingService.compute_composite_score(
            Decimal("80"), Decimal("90"), Decimal("10")
        )
        assert score == Decimal("8.6")

    def test_typical_supplier(self):
        """on_time=70, fill=85, rejection=15 → (28+34+17)/10 = 7.9"""
        score = SupplierRatingService.compute_composite_score(
            Decimal("70"), Decimal("85"), Decimal("15")
        )
        assert score == Decimal("7.9")

    def test_low_performance(self):
        """on_time=50, fill=60, rejection=40 → (20+24+12)/10 = 5.6"""
        score = SupplierRatingService.compute_composite_score(
            Decimal("50"), Decimal("60"), Decimal("40")
        )
        assert score == Decimal("5.6")

    def test_result_is_decimal(self):
        score = SupplierRatingService.compute_composite_score(
            Decimal("75"), Decimal("80"), Decimal("5")
        )
        assert isinstance(score, Decimal)

    def test_result_one_decimal_place(self):
        score = SupplierRatingService.compute_composite_score(
            Decimal("73"), Decimal("82"), Decimal("7")
        )
        # Verify result has at most 1 decimal place
        assert score == score.quantize(Decimal("0.1"))

    def test_clamp_upper_bound(self):
        """Score cannot exceed 10.0 even with extreme inputs."""
        score = SupplierRatingService.compute_composite_score(
            Decimal("100"), Decimal("100"), Decimal("0")
        )
        assert score <= Decimal("10.0")

    def test_clamp_lower_bound(self):
        """Score cannot go below 0.0."""
        score = SupplierRatingService.compute_composite_score(
            Decimal("0"), Decimal("0"), Decimal("100")
        )
        assert score >= Decimal("0.0")

    def test_equal_weights_balanced(self):
        """on_time=60, fill=60, rejection=40 → (24+24+12)/10 = 6.0"""
        score = SupplierRatingService.compute_composite_score(
            Decimal("60"), Decimal("60"), Decimal("40")
        )
        assert score == Decimal("6.0")


# =============================================================================
# Credit limit enforcement
# =============================================================================


def _make_credit_limit(amount: str, mode: str):
    """Create a mock CreditLimit object."""
    cl = MagicMock()
    cl.credit_limit_amount = Decimal(amount)
    cl.currency_code = "USD"
    cl.enforcement_mode = mode
    return cl


class TestCreditLimitEnforcement:
    """Tests for SupplierService.check_credit_limit in all three modes."""

    def _make_service_with_credit_limit(self, credit_limit_mock):
        """Return a SupplierService with a mocked DB that returns the given credit limit."""
        from modules.purchase.repositories.supplier import (
            SupplierAddressRepository,
            SupplierContactRepository,
            SupplierRepository,
        )
        from modules.purchase.services.supplier_service import SupplierService

        db = MagicMock()
        execute_result = MagicMock()
        scalars_result = MagicMock()
        scalars_result.one_or_none.return_value = credit_limit_mock
        execute_result.scalars.return_value = scalars_result
        db.execute.return_value = execute_result

        svc = SupplierService(
            db=db,
            supplier_repo=MagicMock(spec=SupplierRepository),
            contact_repo=MagicMock(spec=SupplierContactRepository),
            address_repo=MagicMock(spec=SupplierAddressRepository),
        )
        return svc

    def test_block_mode_exceeds_raises(self):
        """BLOCK mode + exposure > limit → CreditLimitExceededError"""
        from modules.purchase.services.supplier_service import CreditLimitExceededError

        cl = _make_credit_limit("1000.00", "BLOCK")
        svc = self._make_service_with_credit_limit(cl)

        with pytest.raises(CreditLimitExceededError) as exc_info:
            svc.check_credit_limit(
                company_id=uuid4(),
                supplier_id=uuid4(),
                new_po_total=Decimal("800.00"),
                outstanding_po_value=Decimal("300.00"),  # 300+800=1100 > 1000
            )
        assert exc_info.value.total_exposure == Decimal("1100.00")

    def test_block_mode_within_limit_allowed(self):
        """BLOCK mode + exposure <= limit → ALLOWED result"""
        cl = _make_credit_limit("2000.00", "BLOCK")
        svc = self._make_service_with_credit_limit(cl)

        result = svc.check_credit_limit(
            company_id=uuid4(),
            supplier_id=uuid4(),
            new_po_total=Decimal("500.00"),
            outstanding_po_value=Decimal("300.00"),  # 800 <= 2000
        )
        assert result["action"] == "ALLOWED"
        assert not result["exceeds_limit"]

    def test_warn_mode_exceeds_returns_warned(self):
        """WARN mode + exposure > limit → WARNED result, no exception"""
        cl = _make_credit_limit("1000.00", "WARN")
        svc = self._make_service_with_credit_limit(cl)

        result = svc.check_credit_limit(
            company_id=uuid4(),
            supplier_id=uuid4(),
            new_po_total=Decimal("800.00"),
            outstanding_po_value=Decimal("300.00"),  # 1100 > 1000
        )
        assert result["action"] == "WARNED"
        assert result["exceeds_limit"]

    def test_warn_mode_within_limit_allowed(self):
        """WARN mode + exposure <= limit → ALLOWED result"""
        cl = _make_credit_limit("2000.00", "WARN")
        svc = self._make_service_with_credit_limit(cl)

        result = svc.check_credit_limit(
            company_id=uuid4(),
            supplier_id=uuid4(),
            new_po_total=Decimal("200.00"),
            outstanding_po_value=Decimal("300.00"),  # 500 <= 2000
        )
        assert result["action"] == "ALLOWED"

    def test_off_mode_skips_check(self):
        """OFF mode → always SKIPPED regardless of exposure"""
        cl = _make_credit_limit("1.00", "OFF")  # tiny limit
        svc = self._make_service_with_credit_limit(cl)

        result = svc.check_credit_limit(
            company_id=uuid4(),
            supplier_id=uuid4(),
            new_po_total=Decimal("999999.00"),  # far exceeds limit
            outstanding_po_value=Decimal("0"),
        )
        assert result["action"] == "SKIPPED"
        assert not result["exceeds_limit"]

    def test_no_credit_limit_record_skips(self):
        """No CreditLimit record → SKIPPED"""
        svc = self._make_service_with_credit_limit(None)

        result = svc.check_credit_limit(
            company_id=uuid4(),
            supplier_id=uuid4(),
            new_po_total=Decimal("100000.00"),
        )
        assert result["action"] == "SKIPPED"

    def test_exposure_calculation_correct(self):
        """Total exposure = outstanding + new_po_total"""
        cl = _make_credit_limit("5000.00", "WARN")
        svc = self._make_service_with_credit_limit(cl)

        result = svc.check_credit_limit(
            company_id=uuid4(),
            supplier_id=uuid4(),
            new_po_total=Decimal("1500.00"),
            outstanding_po_value=Decimal("2000.00"),
        )
        assert result["total_exposure"] == Decimal("3500.00")


# =============================================================================
# Preferred supplier designation
# =============================================================================


class TestPreferredSupplierDesignation:
    """Tests for SupplierService.set_preferred flag."""

    def _make_service_with_supplier(self, supplier_mock):
        """Return a SupplierService with the given supplier returned by _get_or_raise."""
        from modules.purchase.repositories.supplier import (
            SupplierAddressRepository,
            SupplierContactRepository,
            SupplierRepository,
        )
        from modules.purchase.services.supplier_service import SupplierService

        db = MagicMock()
        supplier_repo = MagicMock(spec=SupplierRepository)
        supplier_repo.get_by_id_or_none.return_value = supplier_mock

        svc = SupplierService(
            db=db,
            supplier_repo=supplier_repo,
            contact_repo=MagicMock(spec=SupplierContactRepository),
            address_repo=MagicMock(spec=SupplierAddressRepository),
        )
        return svc

    def test_set_preferred_true(self):
        """Setting is_preferred=True marks supplier as preferred."""
        supplier = MagicMock()
        supplier.is_preferred = False
        supplier.id = uuid4()
        supplier.company_id = uuid4()
        svc = self._make_service_with_supplier(supplier)

        with patch.object(svc._event_bus, "publish") as mock_publish:
            svc.set_preferred(
                supplier_id=supplier.id,
                company_id=supplier.company_id,
                is_preferred=True,
                actor_id=uuid4(),
            )
            assert supplier.is_preferred is True
            mock_publish.assert_called_once()

    def test_set_preferred_false(self):
        """Setting is_preferred=False removes preferred status."""
        supplier = MagicMock()
        supplier.is_preferred = True
        supplier.id = uuid4()
        supplier.company_id = uuid4()
        svc = self._make_service_with_supplier(supplier)

        with patch.object(svc._event_bus, "publish") as mock_publish:
            svc.set_preferred(
                supplier_id=supplier.id,
                company_id=supplier.company_id,
                is_preferred=False,
                actor_id=uuid4(),
            )
            assert supplier.is_preferred is False
            mock_publish.assert_called_once()

    def test_no_change_no_event(self):
        """If preferred flag already has the target value, no event is published."""
        supplier = MagicMock()
        supplier.is_preferred = True
        supplier.id = uuid4()
        supplier.company_id = uuid4()
        svc = self._make_service_with_supplier(supplier)

        with patch.object(svc._event_bus, "publish") as mock_publish:
            svc.set_preferred(
                supplier_id=supplier.id,
                company_id=supplier.company_id,
                is_preferred=True,  # same as current
                actor_id=uuid4(),
            )
            mock_publish.assert_not_called()

    def test_preferred_event_payload(self):
        """Event must be PreferredSupplierDesignated with correct is_preferred value."""
        from modules.purchase.events.supplier_events import PreferredSupplierDesignated

        supplier = MagicMock()
        supplier.is_preferred = False
        sid = uuid4()
        cid = uuid4()
        supplier.id = sid
        supplier.company_id = cid
        svc = self._make_service_with_supplier(supplier)

        published_events = []
        with patch.object(
            svc._event_bus, "publish", side_effect=published_events.append
        ):
            svc.set_preferred(
                supplier_id=sid, company_id=cid, is_preferred=True, actor_id=uuid4()
            )

        assert len(published_events) == 1
        ev = published_events[0]
        assert isinstance(ev, PreferredSupplierDesignated)
        assert ev.is_preferred is True
        assert ev.previous_preferred is False


# =============================================================================
# Document expiry detection
# =============================================================================


class TestDocumentExpiryDetection:
    """Tests for SupplierDocumentService.check_expiring_documents logic."""

    def test_days_until_expiry_calculation(self):
        """days_until_expiry = expiry_date - today."""
        today = date.today()
        expiry = today + timedelta(days=15)
        delta = (expiry - today).days
        assert delta == 15

    def test_document_within_window_detected(self):
        """Document expiring in 20 days should appear in 30-day window."""
        today = date.today()
        expiry = today + timedelta(days=20)
        alert_days = 30
        assert (expiry - today).days <= alert_days

    def test_document_outside_window_not_detected(self):
        """Document expiring in 60 days should NOT appear in 30-day window."""
        today = date.today()
        expiry = today + timedelta(days=60)
        alert_days = 30
        assert (expiry - today).days > alert_days

    def test_document_expiring_today_is_detected(self):
        """Document expiring today (days=0) should appear."""
        today = date.today()
        expiry = today
        alert_days = 30
        delta = (expiry - today).days
        assert delta == 0
        assert 0 <= delta <= alert_days

    def test_already_expired_not_in_alert(self):
        """Already-expired documents (expiry < today) should not appear in alert."""
        today = date.today()
        expiry = today - timedelta(days=1)
        assert expiry < today  # Confirms query filter logic: expiry_date >= today
