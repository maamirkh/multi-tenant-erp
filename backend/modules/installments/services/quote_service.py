"""InstallmentQuoteService — deterministic, non-persisting installment
quote/preview (FR-INST-030–032).

Calls ``ScheduleEngine.generate()`` directly and returns the result to
the caller with **zero persistence and zero audit event** — indistin-
guishable from an ordinary read (FR-INST-032). Reuses the already-built
Phase 3 eligibility/invoice gateways and Phase 2 configuration service
(earlier-phase artifacts) to resolve the invoice's live outstanding
amount and the tenant's configured rounding policy; introduces no new
Accounting or Sales integration of its own.

Spec ref: specs/010-installments/plan.md §10.5 (Preview vs. authoritative
schedule); specs/010-installments/spec.md §9.4 (FR-INST-030–032).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from uuid import UUID

from core.exceptions.base import ValidationException
from modules.installments.services.configuration_service import (
    InstallmentConfigurationService,
)
from modules.installments.services.eligibility_service import (
    InstallmentEligibilityService,
)
from modules.installments.services.sales_read_gateway import SalesInvoiceReadGateway
from modules.installments.services.schedule_engine import ScheduleEngine

_DEFAULT_ROUNDING_POLICY = "ROUND_HALF_UP"


@dataclass(frozen=True)
class InstallmentQuotePreview:
    """The full FR-INST-030 preview payload — never persisted, never
    audited."""

    sales_invoice_id: UUID
    invoice_amount: Decimal
    eligible_amount: Decimal
    down_payment_amount: Decimal
    financed_principal: Decimal
    markup_amount: Decimal
    contractual_total: Decimal
    installment_count: int
    frequency: str
    first_due_date: date
    per_installment_amounts: tuple[Decimal, ...]
    final_installment_amount: Decimal
    expected_completion_date: date
    currency_code: str


class InstallmentQuoteService:
    """Service layer for the non-persisting quote/preview operation."""

    def __init__(
        self,
        eligibility_service: InstallmentEligibilityService,
        invoice_gateway: SalesInvoiceReadGateway,
        configuration_service: InstallmentConfigurationService,
    ) -> None:
        self._eligibility = eligibility_service
        self._invoices = invoice_gateway
        self._configuration = configuration_service

    def preview(
        self,
        company_id: UUID,
        *,
        sales_invoice_id: UUID,
        down_payment_amount: Decimal,
        installment_count: int,
        frequency: str,
        first_due_date: date,
        markup_amount: Decimal = Decimal("0"),
        branch_id: UUID | None = None,
    ) -> InstallmentQuotePreview:
        """Raises the same ``InstallmentNotFoundError``/``ValidationException``
        as ``InstallmentEligibilityService.check_invoice_eligibility()`` for
        an ineligible invoice/customer (422, per the OpenAPI contract) —
        no separate eligibility re-check logic is introduced here."""
        eligibility = self._eligibility.check_invoice_eligibility(
            company_id, sales_invoice_id
        )
        invoice = self._invoices.get_invoice(company_id, sales_invoice_id)

        config = self._configuration.get_effective_config(company_id, branch_id)
        rounding_policy = (
            config.rounding_policy if config is not None else _DEFAULT_ROUNDING_POLICY
        )

        try:
            result = ScheduleEngine.generate(
                principal=eligibility.outstanding_amount,
                down_payment=down_payment_amount,
                markup=markup_amount,
                installment_count=installment_count,
                frequency=frequency,
                first_due_date=first_due_date,
                rounding_policy=rounding_policy,
            )
        except ValueError as exc:
            # ScheduleEngine treats an unsupported frequency/rounding
            # policy as a pure-function input-contract violation
            # (ValueError); at this client-facing boundary it must
            # surface as a documented 422, never an unhandled 500
            # (contracts/installments-api.yaml `/quotes` 422 response).
            error = ValidationException(
                message=str(exc),
                details={"frequency": frequency, "rounding_policy": rounding_policy},
            )
            error.code = "INVALID_SCHEDULE_TERMS"
            raise error from exc

        return InstallmentQuotePreview(
            sales_invoice_id=sales_invoice_id,
            invoice_amount=invoice.total_amount,
            eligible_amount=eligibility.outstanding_amount,
            down_payment_amount=down_payment_amount,
            financed_principal=eligibility.outstanding_amount - down_payment_amount,
            markup_amount=markup_amount,
            contractual_total=result.contractual_total,
            installment_count=installment_count,
            frequency=frequency,
            first_due_date=first_due_date,
            per_installment_amounts=tuple(
                line.scheduled_amount for line in result.lines
            ),
            final_installment_amount=result.lines[-1].scheduled_amount,
            expected_completion_date=result.lines[-1].due_date,
            currency_code=eligibility.currency_code,
        )
