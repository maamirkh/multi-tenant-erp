"""InstallmentEligibilityService — Sales invoice/customer eligibility for
an installment offer.

Spec ref: specs/010-installments/plan.md §13 (Sales Integration);
specs/010-installments/contracts/installments-api.yaml `/eligibility`.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from core.exceptions.base import ValidationException
from modules.installments.exceptions import InstallmentNotFoundError
from modules.installments.services.accounting_gateway import (
    AccountingIntegrationGateway,
)
from modules.installments.services.sales_read_gateway import (
    SalesCustomerReadGateway,
    SalesInvoiceReadGateway,
)


@dataclass(frozen=True)
class EligibilityResult:
    """The outcome of a passed eligibility check — never returned for a
    failed check (those raise instead, per the OpenAPI contract's
    "422: ineligible, with documented reason code")."""

    sales_invoice_id: UUID
    customer_id: UUID
    currency_code: str
    outstanding_amount: Decimal


class InstallmentEligibilityService:
    """Evaluates whether a Sales invoice/customer pair is eligible for an
    installment offer."""

    def __init__(
        self,
        invoice_gateway: SalesInvoiceReadGateway,
        customer_gateway: SalesCustomerReadGateway,
        ar_gateway: AccountingIntegrationGateway,
    ) -> None:
        self._invoices = invoice_gateway
        self._customers = customer_gateway
        self._ar = ar_gateway

    def check_invoice_eligibility(
        self, company_id: UUID, sales_invoice_id: UUID
    ) -> EligibilityResult:
        """Raises on any ineligibility reason; returns an
        ``EligibilityResult`` only when every check passes.

        Raises:
            InstallmentNotFoundError: the invoice does not exist for this
                company (BR-INST-015 — indistinguishable from cross-tenant).
            ValidationException: invoice not ``ISSUED``, no outstanding
                balance, or customer not ``ACTIVE`` — each with a
                documented ``code``.
        """
        invoice = self._invoices.get_invoice(company_id, sales_invoice_id)
        if invoice is None:
            raise InstallmentNotFoundError("SalesInvoice", str(sales_invoice_id))

        if invoice.status != "ISSUED":
            exc = ValidationException(
                message=(
                    f"Sales invoice '{sales_invoice_id}' is {invoice.status!r}, "
                    "not ISSUED."
                ),
                details={
                    "sales_invoice_id": str(sales_invoice_id),
                    "status": invoice.status,
                },
            )
            exc.code = "INVOICE_NOT_ISSUED"
            raise exc

        outstanding = self._ar.get_invoice_outstanding_amount(
            company_id, sales_invoice_id
        )
        if outstanding <= 0:
            exc = ValidationException(
                message=f"Sales invoice '{sales_invoice_id}' has no outstanding balance.",
                details={"sales_invoice_id": str(sales_invoice_id)},
            )
            exc.code = "NO_OUTSTANDING_BALANCE"
            raise exc

        customer_id = UUID(str(invoice.customer_id))
        customer = self._customers.get_customer(company_id, customer_id)
        if customer is None:
            raise InstallmentNotFoundError("Customer", str(customer_id))
        if customer.status != "ACTIVE":
            exc = ValidationException(
                message=f"Customer '{customer_id}' is {customer.status!r}, not ACTIVE.",
                details={"customer_id": str(customer_id), "status": customer.status},
            )
            exc.code = "CUSTOMER_NOT_ACTIVE"
            raise exc

        return EligibilityResult(
            sales_invoice_id=sales_invoice_id,
            customer_id=customer_id,
            currency_code=invoice.currency_code,
            outstanding_amount=outstanding,
        )
