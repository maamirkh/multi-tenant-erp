"""Unit tests for CreditCheckService — Phase 4.

Tests:
  - GOOD status + within limit → allowed
  - HOLD status → blocked
  - EXCEEDED status → blocked
  - WARNING status → allowed with message
  - Projected balance exceeds limit → blocked (even if GOOD status)
  - Customer not found → blocked
  - No credit limit (limit=0) → skip limit check
  - exclude_order_id correctly reduces outstanding balance

Task: T130
Spec ref: specs/007-sales-management/spec.md §Credit Control
"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import MagicMock
from uuid import uuid4

from modules.sales.services.credit_check_service import (
    CreditCheckService,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_service() -> CreditCheckService:
    db = MagicMock()
    svc = CreditCheckService(db)
    return svc


def _make_customer(
    credit_status: str = "GOOD",
    credit_limit: str = "10000.00",
) -> MagicMock:
    customer = MagicMock()
    customer.credit_status = credit_status
    customer.credit_limit = Decimal(credit_limit)
    return customer


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestCreditCheckService:
    def setup_method(self) -> None:
        self.svc = _make_service()
        self.svc._order_repo = MagicMock()
        self.company_id = uuid4()
        self.customer_id = uuid4()

    def _setup(
        self,
        credit_status: str = "GOOD",
        credit_limit: str = "10000.00",
        outstanding: str = "0.00",
        customer_found: bool = True,
    ) -> None:
        if customer_found:
            self.svc._db.query.return_value.filter.return_value.first.return_value = (
                _make_customer(credit_status, credit_limit)
            )
        else:
            self.svc._db.query.return_value.filter.return_value.first.return_value = (
                None
            )
        self.svc._order_repo.get_outstanding_total_for_customer.return_value = Decimal(
            outstanding
        )

    def test_good_status_within_limit_allowed(self) -> None:
        self._setup("GOOD", "10000.00", "2000.00")
        result = self.svc.evaluate_credit(
            self.company_id, self.customer_id, Decimal("1000.00")
        )
        assert result.allowed is True
        assert result.credit_status == "GOOD"
        assert result.message == "Credit check passed."

    def test_good_status_projected_exact_limit_allowed(self) -> None:
        self._setup("GOOD", "10000.00", "5000.00")
        result = self.svc.evaluate_credit(
            self.company_id, self.customer_id, Decimal("5000.00")
        )
        assert result.allowed is True  # projected == limit, not over

    def test_good_status_projected_exceeds_limit_blocked(self) -> None:
        self._setup("GOOD", "10000.00", "8000.00")
        result = self.svc.evaluate_credit(
            self.company_id, self.customer_id, Decimal("3000.00")
        )
        assert result.allowed is False
        assert "exceed" in result.message.lower()

    def test_hold_status_blocked(self) -> None:
        self._setup("HOLD", "10000.00", "0.00")
        result = self.svc.evaluate_credit(
            self.company_id, self.customer_id, Decimal("100.00")
        )
        assert result.allowed is False
        assert result.credit_status == "HOLD"
        assert "hold" in result.message.lower()

    def test_exceeded_status_blocked(self) -> None:
        self._setup("EXCEEDED", "10000.00", "10500.00")
        result = self.svc.evaluate_credit(
            self.company_id, self.customer_id, Decimal("500.00")
        )
        assert result.allowed is False
        assert result.credit_status == "EXCEEDED"

    def test_warning_status_allowed_with_message(self) -> None:
        self._setup("WARNING", "10000.00", "9000.00")
        result = self.svc.evaluate_credit(
            self.company_id, self.customer_id, Decimal("500.00")
        )
        assert result.allowed is True
        assert result.credit_status == "WARNING"
        assert "warning" in result.message.lower()

    def test_customer_not_found_blocked(self) -> None:
        self._setup(customer_found=False)
        result = self.svc.evaluate_credit(
            self.company_id, self.customer_id, Decimal("500.00")
        )
        assert result.allowed is False
        assert "not found" in result.message.lower()

    def test_no_credit_limit_skips_limit_check(self) -> None:
        """credit_limit=0 means no limit enforced."""
        self._setup("GOOD", "0.00", "99999.00")
        result = self.svc.evaluate_credit(
            self.company_id, self.customer_id, Decimal("50000.00")
        )
        assert result.allowed is True

    def test_result_contains_projected_balance(self) -> None:
        self._setup("GOOD", "10000.00", "2000.00")
        result = self.svc.evaluate_credit(
            self.company_id, self.customer_id, Decimal("1000.00")
        )
        assert result.projected_balance == Decimal("3000.00")
        assert result.outstanding_balance == Decimal("2000.00")
        assert result.order_total == Decimal("1000.00")

    def test_exclude_order_id_reduces_outstanding(self) -> None:
        """When exclude_order_id is passed, the existing order's total is subtracted."""
        order_id = uuid4()
        existing_order = MagicMock()
        existing_order.total_amount = Decimal("1000.00")

        # Customer query returns customer
        self.svc._db.query.return_value.filter.return_value.first.side_effect = [
            _make_customer("GOOD", "10000.00"),  # Customer query
            existing_order,  # Existing order query
        ]
        self.svc._order_repo.get_outstanding_total_for_customer.return_value = Decimal(
            "5000.00"
        )

        result = self.svc.evaluate_credit(
            self.company_id,
            self.customer_id,
            Decimal("4500.00"),
            exclude_order_id=order_id,
        )
        # outstanding 5000 - existing 1000 = 4000; + order 4500 = 8500 < limit 10000
        assert result.allowed is True

    def test_warning_blocking_when_projected_exceeds_limit(self) -> None:
        """WARNING status does NOT override projected balance > limit block."""
        self._setup("WARNING", "10000.00", "9500.00")
        result = self.svc.evaluate_credit(
            self.company_id, self.customer_id, Decimal("1000.00")
        )
        # projected = 10500 > limit 10000 → blocked
        assert result.allowed is False
