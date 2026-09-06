"""Unit tests for CustomerService — Phase 1.

Tests:
  - create: happy path + duplicate code raises ConflictException
  - state machine: valid/invalid transitions
  - activation validation: missing contact, missing address, missing payment term
  - credit management: compute_credit_status
  - credit hold events

Task: T057
"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from core.exceptions.base import ConflictException, NotFoundException
from modules.sales.models.customer import Customer
from modules.sales.services.customer_service import CustomerService


def _make_service(
    existing_customer: Customer | None = None,
    contact_count: int = 0,
    billing_count: int = 0,
) -> CustomerService:
    """Build a CustomerService with mocked repositories."""
    customer_repo = MagicMock()
    contact_repo = MagicMock()
    address_repo = MagicMock()
    sequence_service = MagicMock()

    customer_repo.get_by_code.return_value = existing_customer
    customer_repo.create.side_effect = lambda c: c
    customer_repo.update.side_effect = lambda c: c
    customer_repo.update_tsvector.return_value = None
    customer_repo.get_by_id_or_none.return_value = existing_customer

    contact_repo.count_for_customer.return_value = contact_count
    address_repo.count_billing_addresses.return_value = billing_count

    db = MagicMock()

    return CustomerService(
        db=db,
        customer_repo=customer_repo,
        contact_repo=contact_repo,
        address_repo=address_repo,
        sequence_service=sequence_service,
    )


def _make_customer(status: str = "DRAFT") -> Customer:
    c = Customer()
    c.id = uuid4()
    c.company_id = uuid4()
    c.customer_code = "CUST-001"
    c.legal_name = "ACME Corp"
    c.customer_type = "COMPANY"
    c.status = status
    c.credit_limit = Decimal("10000")
    c.credit_status = "GOOD"
    c.version = 1
    c.payment_term_id = str(uuid4())
    c.is_deleted = False
    return c


class TestCustomerServiceCreate:
    def test_create_success(self) -> None:
        service = _make_service(existing_customer=None)
        company_id = uuid4()
        customer = service.create(
            company_id=company_id,
            customer_code="CUST-001",
            legal_name="ACME Corp",
            customer_type="COMPANY",
            category_id=uuid4(),
            currency_code="USD",
        )
        assert customer is not None
        assert customer.customer_code == "CUST-001"
        assert customer.status == "DRAFT"

    def test_create_duplicate_code_raises_conflict(self) -> None:
        existing = _make_customer()
        service = _make_service(existing_customer=existing)
        with pytest.raises(ConflictException):
            service.create(
                company_id=uuid4(),
                customer_code="CUST-001",
                legal_name="ACME Corp",
                customer_type="COMPANY",
                category_id=uuid4(),
                currency_code="USD",
            )

    def test_create_starts_as_draft(self) -> None:
        service = _make_service(existing_customer=None)
        customer = service.create(
            company_id=uuid4(),
            customer_code="C001",
            legal_name="Test",
            customer_type="INDIVIDUAL",
            category_id=uuid4(),
            currency_code="USD",
        )
        assert customer.status == "DRAFT"


class TestCustomerStateMachine:
    def test_activate_from_draft_succeeds(self) -> None:
        customer = _make_customer(status="DRAFT")
        service = _make_service(
            existing_customer=customer, contact_count=1, billing_count=1
        )
        result = service.transition(
            company_id=customer.company_id,
            customer_id=customer.id,
            action="activate",
        )
        assert result.status == "ACTIVE"

    def test_activate_from_draft_fails_no_contact(self) -> None:
        customer = _make_customer(status="DRAFT")
        service = _make_service(
            existing_customer=customer, contact_count=0, billing_count=1
        )
        with pytest.raises(ValueError, match="contact"):
            service.transition(
                company_id=customer.company_id,
                customer_id=customer.id,
                action="activate",
            )

    def test_activate_from_draft_fails_no_billing_address(self) -> None:
        customer = _make_customer(status="DRAFT")
        service = _make_service(
            existing_customer=customer, contact_count=1, billing_count=0
        )
        with pytest.raises(ValueError, match="billing address"):
            service.transition(
                company_id=customer.company_id,
                customer_id=customer.id,
                action="activate",
            )

    def test_activate_from_draft_fails_no_payment_term(self) -> None:
        customer = _make_customer(status="DRAFT")
        customer.payment_term_id = None
        service = _make_service(
            existing_customer=customer, contact_count=1, billing_count=1
        )
        with pytest.raises(ValueError, match="payment term"):
            service.transition(
                company_id=customer.company_id,
                customer_id=customer.id,
                action="activate",
            )

    def test_hold_from_active(self) -> None:
        customer = _make_customer(status="ACTIVE")
        service = _make_service(existing_customer=customer)
        result = service.transition(
            company_id=customer.company_id,
            customer_id=customer.id,
            action="hold",
        )
        assert result.status == "ON_HOLD"

    def test_hold_from_inactive_fails(self) -> None:
        customer = _make_customer(status="INACTIVE")
        service = _make_service(existing_customer=customer)
        with pytest.raises(ValueError, match="ACTIVE"):
            service.transition(
                company_id=customer.company_id,
                customer_id=customer.id,
                action="hold",
            )

    def test_block_from_active(self) -> None:
        customer = _make_customer(status="ACTIVE")
        service = _make_service(existing_customer=customer)
        result = service.transition(
            company_id=customer.company_id,
            customer_id=customer.id,
            action="block",
        )
        assert result.status == "BLOCKED"

    def test_unblock_from_blocked(self) -> None:
        customer = _make_customer(status="BLOCKED")
        service = _make_service(existing_customer=customer)
        result = service.transition(
            company_id=customer.company_id,
            customer_id=customer.id,
            action="unblock",
        )
        assert result.status == "ACTIVE"

    def test_release_hold_from_on_hold(self) -> None:
        customer = _make_customer(status="ON_HOLD")
        service = _make_service(existing_customer=customer)
        result = service.transition(
            company_id=customer.company_id,
            customer_id=customer.id,
            action="release_hold",
        )
        assert result.status == "ACTIVE"

    def test_deactivate_from_active(self) -> None:
        customer = _make_customer(status="ACTIVE")
        service = _make_service(existing_customer=customer)
        result = service.transition(
            company_id=customer.company_id,
            customer_id=customer.id,
            action="deactivate",
        )
        assert result.status == "INACTIVE"

    def test_reactivate_from_inactive(self) -> None:
        customer = _make_customer(status="INACTIVE")
        service = _make_service(existing_customer=customer)
        result = service.transition(
            company_id=customer.company_id,
            customer_id=customer.id,
            action="reactivate",
        )
        assert result.status == "ACTIVE"

    def test_invalid_action_raises(self) -> None:
        customer = _make_customer(status="ACTIVE")
        service = _make_service(existing_customer=customer)
        with pytest.raises(ValueError, match="Unknown action"):
            service.transition(
                company_id=customer.company_id,
                customer_id=customer.id,
                action="invalid_action",
            )

    def test_not_found_raises(self) -> None:
        service = _make_service(existing_customer=None)
        with pytest.raises(NotFoundException):
            service.transition(
                company_id=uuid4(),
                customer_id=uuid4(),
                action="activate",
            )


class TestCreditStatusComputation:
    def _svc(self) -> CustomerService:
        return _make_service()

    def test_zero_limit_is_good(self) -> None:
        svc = self._svc()
        assert svc.compute_credit_status(Decimal("0"), Decimal("0")) == "GOOD"

    def test_below_threshold_is_good(self) -> None:
        svc = self._svc()
        assert svc.compute_credit_status(Decimal("10000"), Decimal("5000")) == "GOOD"

    def test_at_threshold_is_warning(self) -> None:
        svc = self._svc()
        # 80% usage triggers WARNING
        assert svc.compute_credit_status(Decimal("10000"), Decimal("8000")) == "WARNING"

    def test_exceeded_100pct_is_exceeded(self) -> None:
        svc = self._svc()
        assert (
            svc.compute_credit_status(Decimal("10000"), Decimal("11000")) == "EXCEEDED"
        )
