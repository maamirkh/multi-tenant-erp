"""[Epic 10, Phase 11, T202] Security test — a cross-tenant
``sales_invoice_id``/``customer_id`` reference at contract creation is
rejected, indistinguishable from an unrelated validation failure
(BR-INST-015).

Extends the Phase 3 proof (``test_contract_creation.py::
TestCreateDraftCrossTenantRejection``, T055/T056 — which already
established the ``sales_invoice_id`` case using fake Sales gateways) by
additionally proving:

1. The cross-tenant-invoice error is byte-for-byte indistinguishable
   (same exception type, ``code``, ``http_status``) from a genuinely
   non-existent invoice — never a distinguishable signal an attacker
   could use to enumerate other tenants' invoice ids.
2. A ``customer_id`` reachable only via a legitimate, same-tenant
   invoice but pointing at a customer that exists only in a DIFFERENT
   company is rejected identically (the transitive BR-INST-015 check
   inside ``check_invoice_eligibility()``'s own customer lookup).

Uses the same fake Sales/Accounting read-gateway technique as the Phase
3 precedent (unit-level — exercises only
``InstallmentContractService``/``InstallmentEligibilityService``'s own
company_id-scoping logic, not real cross-module Sales tables).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from modules.installments.exceptions import InstallmentNotFoundError
from modules.installments.repositories.audit import InstallmentAuditLogRepository
from modules.installments.repositories.contract import InstallmentContractRepository
from modules.installments.repositories.sequence import InstallmentSequenceRepository
from modules.installments.services.audit_service import InstallmentAuditService
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
    """company_id-keyed, mirroring the real
    ``SalesInvoiceRepository.get_by_id_or_none()``'s own tenant
    scoping."""

    def __init__(self, invoices_by_company: dict[uuid.UUID, dict]) -> None:
        self._invoices = invoices_by_company

    def get_invoice(self, company_id, sales_invoice_id):
        return self._invoices.get(company_id, {}).get(sales_invoice_id)


class _FakeCustomerGateway:
    """company_id-keyed, mirroring the real
    ``CustomerRepository.get_by_id_or_none()``'s own tenant scoping."""

    def __init__(self, customers_by_company: dict[uuid.UUID, dict]) -> None:
        self._customers = customers_by_company

    def get_customer(self, company_id, customer_id):
        return self._customers.get(company_id, {}).get(customer_id)


class _FakeAccountingGateway:
    def __init__(self, outstanding_amount: Decimal) -> None:
        self.outstanding_amount = outstanding_amount

    def get_invoice_outstanding_amount(self, company_id, sales_invoice_id):
        return self.outstanding_amount


class _FakeConfigurationService:
    def get_effective_config(self, company_id, branch_id=None):
        return None


def _base_create_kwargs(sales_invoice_id: uuid.UUID) -> dict:
    return {
        "sales_invoice_id": sales_invoice_id,
        "down_payment_amount": Decimal("100.00"),
        "installment_count": 12,
        "frequency": "MONTHLY",
        "first_due_date": date(2026, 2, 1),
        "maturity_date": date(2027, 1, 1),
    }


def _build_service(
    db_session: Session,
    *,
    invoices_by_company: dict[uuid.UUID, dict],
    customers_by_company: dict[uuid.UUID, dict],
    outstanding_amount: Decimal = Decimal("1000.00"),
) -> InstallmentContractService:
    eligibility_service = InstallmentEligibilityService(
        invoice_gateway=_FakeInvoiceGateway(invoices_by_company),
        customer_gateway=_FakeCustomerGateway(customers_by_company),
        ar_gateway=_FakeAccountingGateway(outstanding_amount),
    )
    return InstallmentContractService(
        repo=InstallmentContractRepository(db_session),
        sequence_repo=InstallmentSequenceRepository(db_session),
        eligibility_service=eligibility_service,
        accounting_gateway=_FakeAccountingGateway(outstanding_amount),
        configuration_service=_FakeConfigurationService(),
        audit_service=InstallmentAuditService(
            db=db_session, audit_repo=InstallmentAuditLogRepository(db_session)
        ),
    )


class TestCrossTenantInvoiceReferenceIndistinguishableFromNonExistent:
    def test_cross_tenant_and_never_existed_raise_identical_errors(
        self, db_session: Session
    ) -> None:
        company_a = uuid.uuid4()
        company_b = uuid.uuid4()
        invoice = _FakeInvoice(
            id=uuid.uuid4(),
            status="ISSUED",
            currency_code="USD",
            customer_id=uuid.uuid4(),
        )
        service = _build_service(
            db_session,
            invoices_by_company={company_a: {invoice.id: invoice}},
            customers_by_company={
                company_a: {
                    invoice.customer_id: _FakeCustomer(
                        id=invoice.customer_id, status="ACTIVE"
                    )
                }
            },
        )

        # Case 1: sales_invoice_id genuinely belongs to company_a, but
        # company_b attempts to reference it.
        with pytest.raises(InstallmentNotFoundError) as exc_cross_tenant:
            service.create_draft(
                company_id=company_b,
                actor_id=None,
                **_base_create_kwargs(invoice.id),
            )

        # Case 2: sales_invoice_id has never existed for ANY company.
        with pytest.raises(InstallmentNotFoundError) as exc_never_existed:
            service.create_draft(
                company_id=company_b,
                actor_id=None,
                **_base_create_kwargs(uuid.uuid4()),
            )

        assert type(exc_cross_tenant.value) is type(exc_never_existed.value)
        assert exc_cross_tenant.value.code == exc_never_existed.value.code
        assert exc_cross_tenant.value.http_status == exc_never_existed.value.http_status
        assert exc_cross_tenant.value.details == {
            "entity_type": "SalesInvoice",
            "entity_id": str(invoice.id),
        }


class TestCrossTenantCustomerReferenceRejected:
    def test_invoice_owned_by_caller_but_customer_owned_by_another_company_rejected(
        self, db_session: Session
    ) -> None:
        """The invoice itself legitimately belongs to the caller's own
        company, but the customer it references only exists under a
        DIFFERENT company (a data-integrity edge case, or a deliberately
        crafted cross-tenant probe) — the transitive customer lookup
        inside ``check_invoice_eligibility()`` denies it identically,
        never silently trusting the invoice's own ``customer_id`` field
        as sufficient authorization on its own."""
        company_a = uuid.uuid4()
        company_b = uuid.uuid4()
        shared_customer_id = uuid.uuid4()
        invoice = _FakeInvoice(
            id=uuid.uuid4(),
            status="ISSUED",
            currency_code="USD",
            customer_id=shared_customer_id,
        )
        service = _build_service(
            db_session,
            invoices_by_company={company_a: {invoice.id: invoice}},
            # The customer with this id exists only under company_b —
            # NOT company_a, despite company_a's own invoice naming it.
            customers_by_company={
                company_b: {
                    shared_customer_id: _FakeCustomer(
                        id=shared_customer_id, status="ACTIVE"
                    )
                }
            },
        )

        with pytest.raises(InstallmentNotFoundError) as exc_info:
            service.create_draft(
                company_id=company_a,
                actor_id=None,
                **_base_create_kwargs(invoice.id),
            )
        assert exc_info.value.details == {
            "entity_type": "Customer",
            "entity_id": str(shared_customer_id),
        }
