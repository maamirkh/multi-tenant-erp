"""InstallmentContractService — the Installments aggregate-root service.

Phase 3 implements only ``create_draft()`` — the DRAFT-creation path.
Named lifecycle-transition methods (``submit()``, ``approve()``, etc.)
are Phase 5's scope; this file intentionally does not pre-create them.

Spec ref: specs/010-installments/plan.md §9 (Lifecycle), §13 (Sales
Integration).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy.exc import IntegrityError

from core.exceptions.base import ConflictException
from modules.installments.exceptions import InstallmentNotFoundError
from modules.installments.models.contract import InstallmentContract
from modules.installments.repositories.contract import InstallmentContractRepository
from modules.installments.repositories.sequence import InstallmentSequenceRepository
from modules.installments.services.accounting_gateway import (
    AccountingIntegrationGateway,
)
from modules.installments.services.eligibility_service import (
    InstallmentEligibilityService,
)


def build_terms_snapshot(
    *,
    sales_invoice_id: UUID,
    customer_id: UUID,
    plan_template_id: UUID | None,
    contract_date: date,
    principal_amount: Decimal,
    down_payment_amount: Decimal,
    markup_amount: Decimal,
    contractual_total: Decimal,
    installment_count: int,
    frequency: str,
    first_due_date: date,
    maturity_date: date,
    currency_code: str,
) -> dict[str, Any]:
    """Pure function — a self-sufficient JSONB explanation of the full
    obligation (FR-INST-041), readable independently of whatever the
    originating Sales invoice, plan template, or tenant configuration
    look like later (those may change or be deleted; this snapshot never
    does)."""
    return {
        "sales_invoice_id": str(sales_invoice_id),
        "customer_id": str(customer_id),
        "plan_template_id": str(plan_template_id) if plan_template_id else None,
        "contract_date": contract_date.isoformat(),
        "principal_amount": str(principal_amount),
        "down_payment_amount": str(down_payment_amount),
        "markup_amount": str(markup_amount),
        "contractual_total": str(contractual_total),
        "installment_count": installment_count,
        "frequency": frequency,
        "first_due_date": first_due_date.isoformat(),
        "maturity_date": maturity_date.isoformat(),
        "currency_code": currency_code,
    }


class InstallmentContractService:
    """Service layer for the InstallmentContract aggregate root."""

    def __init__(
        self,
        repo: InstallmentContractRepository,
        sequence_repo: InstallmentSequenceRepository,
        eligibility_service: InstallmentEligibilityService,
        accounting_gateway: AccountingIntegrationGateway,
    ) -> None:
        self._repo = repo
        self._sequences = sequence_repo
        self._eligibility = eligibility_service
        self._accounting = accounting_gateway

    def create_draft(
        self,
        company_id: UUID,
        actor_id: UUID | None,
        *,
        sales_invoice_id: UUID,
        down_payment_amount: Decimal,
        installment_count: int,
        frequency: str,
        first_due_date: date,
        maturity_date: date,
        markup_amount: Decimal = Decimal("0"),
        plan_template_id: UUID | None = None,
        branch_id: UUID | None = None,
        contract_date: date | None = None,
    ) -> InstallmentContract:
        """Create a DRAFT installment contract against an eligible Sales
        invoice.

        ``financed_principal`` is computed from the invoice's LIVE
        outstanding amount (never a stale/duplicated field, FR-INST-261)
        minus the down payment — correctly excluding any pre-existing
        partial payments already applied to the invoice.

        Raises:
            InstallmentNotFoundError: invoice/customer not found for this
                tenant (BR-INST-015).
            ValidationException: invoice/customer ineligible (see
                ``InstallmentEligibilityService``).
            ConflictException: an existing non-terminal contract already
                covers this invoice (BR-INST-042) — the service-layer
                pre-check; the DB partial unique index is the real
                backstop against a concurrent race (T053).
        """
        eligibility = self._eligibility.check_invoice_eligibility(
            company_id, sales_invoice_id
        )

        existing = self._repo.find_active_by_sales_invoice(company_id, sales_invoice_id)
        if existing is not None:
            raise ConflictException(
                message=(
                    f"Installment contract '{existing.contract_number}' already "
                    f"covers sales invoice '{sales_invoice_id}'."
                ),
                details={
                    "sales_invoice_id": str(sales_invoice_id),
                    "existing_contract_id": str(existing.id),
                },
            )

        financed_principal = eligibility.outstanding_amount - down_payment_amount
        contractual_total = financed_principal + markup_amount
        effective_contract_date = contract_date or date.today()

        contract_number = self._sequences.generate_next_number(company_id)

        terms_snapshot = build_terms_snapshot(
            sales_invoice_id=sales_invoice_id,
            customer_id=eligibility.customer_id,
            plan_template_id=plan_template_id,
            contract_date=effective_contract_date,
            principal_amount=financed_principal,
            down_payment_amount=down_payment_amount,
            markup_amount=markup_amount,
            contractual_total=contractual_total,
            installment_count=installment_count,
            frequency=frequency,
            first_due_date=first_due_date,
            maturity_date=maturity_date,
            currency_code=eligibility.currency_code,
        )

        contract = InstallmentContract(
            company_id=company_id,
            created_by=actor_id,
            contract_number=contract_number,
            branch_id=branch_id,
            customer_id=eligibility.customer_id,
            sales_invoice_id=sales_invoice_id,
            plan_template_id=plan_template_id,
            contract_date=effective_contract_date,
            principal_amount=financed_principal,
            down_payment_amount=down_payment_amount,
            markup_amount=markup_amount,
            contractual_total=contractual_total,
            installment_count=installment_count,
            frequency=frequency,
            first_due_date=first_due_date,
            maturity_date=maturity_date,
            currency_code=eligibility.currency_code,
            status="DRAFT",
            terms_snapshot=terms_snapshot,
        )
        try:
            return self._repo.create(contract)
        except IntegrityError as exc:
            self._repo.db.rollback()
            constraint = getattr(getattr(exc, "orig", None), "diag", None)
            constraint_name = getattr(constraint, "constraint_name", None)
            if (
                constraint_name
                == "uq_installment_contracts_one_nonterminal_per_obligation"
            ):
                raise ConflictException(
                    message=(
                        "An existing non-terminal contract already covers "
                        f"sales invoice '{sales_invoice_id}'."
                    ),
                    details={"sales_invoice_id": str(sales_invoice_id)},
                ) from exc
            raise

    def get(self, company_id: UUID, contract_id: UUID) -> InstallmentContract:
        contract = self._repo.get_by_id_or_none(contract_id, company_id)
        if contract is None:
            raise InstallmentNotFoundError("InstallmentContract", str(contract_id))
        return contract

    def list(
        self, company_id: UUID, skip: int = 0, limit: int = 20
    ) -> tuple[list[InstallmentContract], int]:
        return self._repo.list(company_id, skip=skip, limit=limit)
