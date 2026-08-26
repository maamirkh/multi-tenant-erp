"""Regression/structural tests proving single-validator reuse (tasks.md
T073E) — ``InstallmentQuoteService.preview()`` and
``InstallmentContractService.create_draft()`` share exactly one policy
check, never two independently-maintained copies, and a direct
``create_draft()`` call cannot bypass it by skipping ``/quotes``.
"""

from __future__ import annotations

import inspect
import uuid
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from modules.installments.exceptions import InstallmentTermsPolicyViolationError
from modules.installments.repositories.contract import InstallmentContractRepository
from modules.installments.repositories.sequence import InstallmentSequenceRepository
from modules.installments.services import contract_service as contract_service_module
from modules.installments.services.contract_service import InstallmentContractService
from modules.installments.services.eligibility_service import (
    InstallmentEligibilityService,
)
from modules.installments.services.quote_service import InstallmentQuoteService


@dataclass
class _FakeInvoice:
    id: uuid.UUID
    status: str
    currency_code: str
    customer_id: uuid.UUID
    total_amount: Decimal = Decimal("1000")


@dataclass
class _FakeCustomer:
    id: uuid.UUID
    status: str


@dataclass
class _FakeConfig:
    allowed_frequencies: list[str] = field(default_factory=lambda: ["MONTHLY"])
    min_term: int = 6
    max_term: int = 24
    min_down_payment_pct: Decimal | None = None
    min_down_payment_amount: Decimal | None = None
    max_financed_amount: Decimal | None = None
    rounding_policy: str = "ROUND_HALF_UP"


class _FakeInvoiceGateway:
    def __init__(self, invoice: _FakeInvoice) -> None:
        self._invoice = invoice

    def get_invoice(self, company_id, sales_invoice_id):
        return self._invoice


class _FakeCustomerGateway:
    def __init__(self, customer: _FakeCustomer) -> None:
        self._customer = customer

    def get_customer(self, company_id, customer_id):
        return self._customer


class _FakeAccountingGateway:
    def __init__(self, outstanding_amount: Decimal) -> None:
        self._outstanding_amount = outstanding_amount

    def get_invoice_outstanding_amount(self, company_id, sales_invoice_id):
        return self._outstanding_amount


class _FakeConfigurationService:
    def __init__(self, config: _FakeConfig | None) -> None:
        self._config = config

    def get_effective_config(self, company_id, branch_id=None):
        return self._config


_DISALLOWED_FREQUENCY_TERMS = dict(
    down_payment_amount=Decimal("100"),
    installment_count=12,
    frequency="WEEKLY",  # not in _FakeConfig's allowed_frequencies=["MONTHLY"]
    first_due_date=date(2026, 2, 1),
)


def _build_invoice_and_gateways(outstanding_amount: Decimal):
    invoice = _FakeInvoice(
        id=uuid.uuid4(),
        status="ISSUED",
        currency_code="USD",
        customer_id=uuid.uuid4(),
    )
    customer = _FakeCustomer(id=invoice.customer_id, status="ACTIVE")
    invoice_gateway = _FakeInvoiceGateway(invoice)
    customer_gateway = _FakeCustomerGateway(customer)
    accounting_gateway = _FakeAccountingGateway(outstanding_amount)
    eligibility_service = InstallmentEligibilityService(
        invoice_gateway=invoice_gateway,
        customer_gateway=customer_gateway,
        ar_gateway=accounting_gateway,
    )
    return invoice, invoice_gateway, eligibility_service, accounting_gateway


class TestSingleValidatorReuse:
    def test_quote_and_draft_reject_the_same_disallowed_terms_identically(
        self, db_session: Session
    ) -> None:
        outstanding_amount = Decimal("900")
        invoice, invoice_gateway, eligibility_service, accounting_gateway = (
            _build_invoice_and_gateways(outstanding_amount)
        )
        config_service = _FakeConfigurationService(_FakeConfig())

        quote_service = InstallmentQuoteService(
            eligibility_service=eligibility_service,
            invoice_gateway=invoice_gateway,
            configuration_service=config_service,
        )
        contract_service = InstallmentContractService(
            repo=InstallmentContractRepository(db_session),
            sequence_repo=InstallmentSequenceRepository(db_session),
            eligibility_service=eligibility_service,
            accounting_gateway=accounting_gateway,
            configuration_service=config_service,
        )

        with pytest.raises(InstallmentTermsPolicyViolationError) as quote_exc:
            quote_service.preview(
                uuid.uuid4(),
                sales_invoice_id=invoice.id,
                **_DISALLOWED_FREQUENCY_TERMS,
            )

        with pytest.raises(InstallmentTermsPolicyViolationError) as draft_exc:
            contract_service.create_draft(
                company_id=uuid.uuid4(),
                actor_id=None,
                sales_invoice_id=invoice.id,
                maturity_date=date(2027, 2, 1),
                **_DISALLOWED_FREQUENCY_TERMS,
            )

        assert quote_exc.value.code == draft_exc.value.code == "TERMS_POLICY_VIOLATION"
        assert (
            quote_exc.value.details["violations"]
            == draft_exc.value.details["violations"]
        )

    def test_direct_create_draft_call_cannot_bypass_validation(
        self, db_session: Session
    ) -> None:
        """Calling create_draft() directly — never touching /quotes or
        the router at all — still enforces the policy check."""
        outstanding_amount = Decimal("900")
        invoice, _invoice_gateway, eligibility_service, accounting_gateway = (
            _build_invoice_and_gateways(outstanding_amount)
        )
        contract_service = InstallmentContractService(
            repo=InstallmentContractRepository(db_session),
            sequence_repo=InstallmentSequenceRepository(db_session),
            eligibility_service=eligibility_service,
            accounting_gateway=accounting_gateway,
            configuration_service=_FakeConfigurationService(_FakeConfig()),
        )

        with pytest.raises(InstallmentTermsPolicyViolationError):
            contract_service.create_draft(
                company_id=uuid.uuid4(),
                actor_id=None,
                sales_invoice_id=invoice.id,
                maturity_date=date(2027, 2, 1),
                **_DISALLOWED_FREQUENCY_TERMS,
            )

    def test_no_independently_reimplemented_bounds_logic_in_contract_service(
        self,
    ) -> None:
        """Structural guard: contract_service.py must delegate to
        InstallmentTermsPolicyValidator, never reimplement its own
        allowed_frequencies/min_term/max_term/min_down_payment/
        max_financed_amount comparison."""
        source = inspect.getsource(contract_service_module)
        assert "InstallmentTermsPolicyValidator" in source
        forbidden = (
            "allowed_frequencies",
            "min_term",
            "max_term",
            "min_down_payment",
            "max_financed_amount",
        )
        for token in forbidden:
            assert token not in source, (
                f"contract_service.py appears to reimplement policy-bounds "
                f"logic independently (found {token!r}) instead of "
                f"delegating to InstallmentTermsPolicyValidator"
            )
