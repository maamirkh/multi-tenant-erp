"""Unit/service tests for InstallmentContractService.create_draft().

Covers tasks.md T055/T056: cross-tenant sales_invoice_id rejection,
currency-mismatch-is-impossible-by-construction, and pre-existing
partial invoice payments correctly reducing financed_principal
(FR-INST-261). Uses fake Sales/Accounting read gateways (unit-level,
not the real cross-module services) so these tests exercise only
``InstallmentContractService``'s own business logic — the real gateway
wiring is proven separately by T053 (real Postgres) and the live HTTP
smoke test.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from core.exceptions.base import ConflictException, ValidationException
from modules.installments.exceptions import InstallmentNotFoundError
from modules.installments.repositories.contract import InstallmentContractRepository
from modules.installments.repositories.sequence import InstallmentSequenceRepository
from modules.installments.services.contract_service import InstallmentContractService
from modules.installments.services.eligibility_service import (
    InstallmentEligibilityService,
)


@dataclass
class _FakeInvoice:
    id: uuid.UUID
    status: str
    currency_code: str
    customer_id: uuid.UUID


@dataclass
class _FakeCustomer:
    id: uuid.UUID
    status: str


class _FakeInvoiceGateway:
    def __init__(self, invoices_by_company: dict[uuid.UUID, dict]) -> None:
        self._invoices = invoices_by_company

    def get_invoice(self, company_id, sales_invoice_id):
        return self._invoices.get(company_id, {}).get(sales_invoice_id)


class _FakeCustomerGateway:
    def __init__(self, customer: _FakeCustomer) -> None:
        self._customer = customer

    def get_customer(self, company_id, customer_id):
        if customer_id != self._customer.id:
            return None
        return self._customer


class _FakeAccountingGateway:
    def __init__(self, outstanding_amount: Decimal) -> None:
        self.outstanding_amount = outstanding_amount

    def get_invoice_outstanding_amount(self, company_id, sales_invoice_id):
        return self.outstanding_amount


def _build_service(
    db_session: Session,
    *,
    invoice: _FakeInvoice,
    company_id: uuid.UUID,
    outstanding_amount: Decimal,
    customer_status: str = "ACTIVE",
) -> InstallmentContractService:
    invoice_gateway = _FakeInvoiceGateway({company_id: {invoice.id: invoice}})
    customer_gateway = _FakeCustomerGateway(
        _FakeCustomer(id=invoice.customer_id, status=customer_status)
    )
    accounting_gateway = _FakeAccountingGateway(outstanding_amount)
    eligibility_service = InstallmentEligibilityService(
        invoice_gateway=invoice_gateway,
        customer_gateway=customer_gateway,
        ar_gateway=accounting_gateway,
    )
    return InstallmentContractService(
        repo=InstallmentContractRepository(db_session),
        sequence_repo=InstallmentSequenceRepository(db_session),
        eligibility_service=eligibility_service,
        accounting_gateway=accounting_gateway,
    )


def _base_create_kwargs(sales_invoice_id: uuid.UUID) -> dict:
    return {
        "sales_invoice_id": sales_invoice_id,
        "down_payment_amount": Decimal("100.00"),
        "installment_count": 12,
        "frequency": "MONTHLY",
        "first_due_date": date(2026, 2, 1),
        "maturity_date": date(2027, 1, 1),
    }


class TestCreateDraftCrossTenantRejection:
    def test_cross_tenant_sales_invoice_id_rejected(self, db_session: Session) -> None:
        """A sales_invoice_id that exists for a DIFFERENT company must be
        indistinguishable from a genuinely non-existent invoice (BR-INST-015)."""
        company_a = uuid.uuid4()
        company_b = uuid.uuid4()
        invoice = _FakeInvoice(
            id=uuid.uuid4(),
            status="ISSUED",
            currency_code="USD",
            customer_id=uuid.uuid4(),
        )
        # The fake invoice gateway only knows about company_a's invoice.
        service = _build_service(
            db_session,
            invoice=invoice,
            company_id=company_a,
            outstanding_amount=Decimal("1000.00"),
        )

        with pytest.raises(InstallmentNotFoundError):
            service.create_draft(
                company_id=company_b,
                actor_id=None,
                **_base_create_kwargs(invoice.id),
            )


class TestCreateDraftCurrencyIsNeverAnInput:
    def test_currency_code_always_sourced_from_invoice(
        self, db_session: Session
    ) -> None:
        """currency_code is not (and cannot be) a create_draft() parameter
        at all — it is always read from the invoice, making a currency
        mismatch structurally impossible, not merely validated away."""
        import inspect

        sig = inspect.signature(InstallmentContractService.create_draft)
        assert "currency_code" not in sig.parameters

        company_id = uuid.uuid4()
        invoice = _FakeInvoice(
            id=uuid.uuid4(),
            status="ISSUED",
            currency_code="PKR",
            customer_id=uuid.uuid4(),
        )
        service = _build_service(
            db_session,
            invoice=invoice,
            company_id=company_id,
            outstanding_amount=Decimal("1000.00"),
        )

        contract = service.create_draft(
            company_id=company_id,
            actor_id=None,
            **_base_create_kwargs(invoice.id),
        )
        assert contract.currency_code == "PKR"
        assert contract.terms_snapshot["currency_code"] == "PKR"


class TestCreateDraftPartialPaymentsReduceFinancedPrincipal:
    def test_pre_existing_partial_payment_reduces_financed_principal(
        self, db_session: Session
    ) -> None:
        """FR-INST-261: financed_principal is computed from the invoice's
        LIVE outstanding amount (which already excludes any pre-existing
        partial payment), never the invoice's original full total."""
        company_id = uuid.uuid4()
        invoice = _FakeInvoice(
            id=uuid.uuid4(),
            status="ISSUED",
            currency_code="USD",
            customer_id=uuid.uuid4(),
        )
        # Invoice's original total might have been 1000.00, but 400.00
        # was already paid before this contract is drafted — the AR
        # gateway reports the LIVE outstanding amount, not the original.
        live_outstanding = Decimal("600.00")
        down_payment = Decimal("100.00")

        service = _build_service(
            db_session,
            invoice=invoice,
            company_id=company_id,
            outstanding_amount=live_outstanding,
        )

        contract = service.create_draft(
            company_id=company_id,
            actor_id=None,
            sales_invoice_id=invoice.id,
            down_payment_amount=down_payment,
            installment_count=6,
            frequency="MONTHLY",
            first_due_date=date(2026, 2, 1),
            maturity_date=date(2026, 7, 1),
        )

        expected_financed_principal = live_outstanding - down_payment
        assert contract.principal_amount == expected_financed_principal
        assert contract.principal_amount == Decimal("500.00")
        assert contract.contractual_total == expected_financed_principal

    def test_no_outstanding_balance_raises_validation_error(
        self, db_session: Session
    ) -> None:
        """An invoice with zero live outstanding (e.g. fully paid already)
        must be rejected as ineligible, never silently financed at zero."""
        company_id = uuid.uuid4()
        invoice = _FakeInvoice(
            id=uuid.uuid4(),
            status="ISSUED",
            currency_code="USD",
            customer_id=uuid.uuid4(),
        )
        service = _build_service(
            db_session,
            invoice=invoice,
            company_id=company_id,
            outstanding_amount=Decimal("0"),
        )

        with pytest.raises(ValidationException) as exc_info:
            service.create_draft(
                company_id=company_id,
                actor_id=None,
                **_base_create_kwargs(invoice.id),
            )
        assert exc_info.value.code == "NO_OUTSTANDING_BALANCE"


class TestCreateDraftOneContractPerObligation:
    def test_second_draft_against_same_invoice_rejected(
        self, db_session: Session
    ) -> None:
        company_id = uuid.uuid4()
        invoice = _FakeInvoice(
            id=uuid.uuid4(),
            status="ISSUED",
            currency_code="USD",
            customer_id=uuid.uuid4(),
        )
        service = _build_service(
            db_session,
            invoice=invoice,
            company_id=company_id,
            outstanding_amount=Decimal("1000.00"),
        )

        service.create_draft(
            company_id=company_id,
            actor_id=None,
            **_base_create_kwargs(invoice.id),
        )

        with pytest.raises(ConflictException):
            service.create_draft(
                company_id=company_id,
                actor_id=None,
                **_base_create_kwargs(invoice.id),
            )
