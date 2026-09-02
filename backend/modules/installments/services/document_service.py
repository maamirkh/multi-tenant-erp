"""InstallmentDocumentService — read-only structured-JSON documents
(tasks.md T206, plan.md §27).

No PDF/document-rendering infrastructure exists anywhere in the backend
(plan.md §2/§27) — mirrors ``AccountsPayableService
.generate_remittance_advice()``'s exact precedent: plain structured
dict/schema output, never a rendered artifact. Every method here makes
zero repository *write* calls, by construction (T212 proves this
structurally) — read-only with respect to contract/financial state.

Spec ref: specs/010-installments/plan.md §9.7/§27; specs/010-installments/
spec.md FR-INST-060/061.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any
from uuid import UUID

from modules.installments.exceptions import InstallmentNotFoundError
from modules.installments.repositories.allocation_reference import (
    InstallmentAllocationReferenceRepository,
)
from modules.installments.repositories.contract import InstallmentContractRepository
from modules.installments.repositories.schedule import InstallmentScheduleRepository
from modules.installments.services.access_policy import (
    InstallmentAccessPolicy,
    InstallmentOperationClass,
)


class InstallmentDocumentService:
    """Read-only — assembles a dict/schema from already-persisted
    Installments state. Never calls a repository write method, never
    calls an Accounting mutation."""

    def __init__(
        self,
        contract_repo: InstallmentContractRepository,
        schedule_repo: InstallmentScheduleRepository,
        allocation_ref_repo: InstallmentAllocationReferenceRepository,
        access_policy: InstallmentAccessPolicy | None = None,
    ) -> None:
        self._contracts = contract_repo
        self._schedule = schedule_repo
        self._allocation_refs = allocation_ref_repo
        self._access_policy = access_policy

    def _authorize_read(self, company_id: UUID) -> None:
        if self._access_policy is not None:
            self._access_policy.authorize(
                company_id=company_id, operation=InstallmentOperationClass.READ
            )

    def _get_contract_or_404(self, company_id: UUID, contract_id: UUID) -> Any:
        contract = self._contracts.get_by_id_or_none(contract_id, company_id)
        if contract is None:
            raise InstallmentNotFoundError("InstallmentContract", str(contract_id))
        return contract

    def get_agreement(self, company_id: UUID, contract_id: UUID) -> dict[str, Any]:
        """Assembles a read-only dict from ``terms_snapshot`` + contract
        fields — the self-sufficient JSONB explanation of the obligation
        already captured at activation (FR-INST-041), never re-derived."""
        self._authorize_read(company_id)
        contract = self._get_contract_or_404(company_id, contract_id)
        return {
            "document_type": "agreement",
            "contract_id": str(contract.id),
            "contract_number": contract.contract_number,
            "customer_id": str(contract.customer_id),
            "status": contract.status,
            "contract_date": contract.contract_date.isoformat(),
            "contractual_total": str(contract.contractual_total),
            "principal_amount": str(contract.principal_amount),
            "down_payment_amount": str(contract.down_payment_amount),
            "markup_amount": str(contract.markup_amount),
            "installment_count": contract.installment_count,
            "frequency": contract.frequency,
            "first_due_date": contract.first_due_date.isoformat(),
            "maturity_date": contract.maturity_date.isoformat(),
            "currency_code": contract.currency_code,
            "terms_snapshot": contract.terms_snapshot,
        }

    def get_schedule_document(
        self, company_id: UUID, contract_id: UUID
    ) -> dict[str, Any]:
        """Schedule lines + allocation summary, same read-only JSON
        pattern — never re-derives the schedule, reads exactly what
        ``activate()``/``reschedule()`` already persisted."""
        self._authorize_read(company_id)
        contract = self._get_contract_or_404(company_id, contract_id)
        version = self._schedule.get_active_version(company_id, contract_id)
        if version is None:
            raise InstallmentNotFoundError(
                "InstallmentScheduleVersion", str(contract_id)
            )
        lines = self._schedule.get_lines(company_id, version.id)
        line_ids = [line.id for line in lines]
        net_allocated = self._allocation_refs.get_net_allocated_by_line(
            company_id, line_ids
        )
        return {
            "document_type": "schedule",
            "contract_id": str(contract.id),
            "contract_number": contract.contract_number,
            "version_number": version.version_number,
            "generated_at": (
                version.generated_at.isoformat() if version.generated_at else None
            ),
            "lines": [
                {
                    "sequence": line.sequence,
                    "due_date": line.due_date.isoformat(),
                    "scheduled_amount": str(line.scheduled_amount),
                    "allocated_amount": str(net_allocated.get(line.id, 0)),
                    "waived_at": (
                        line.waived_at.isoformat() if line.waived_at else None
                    ),
                    "voided_at": (
                        line.voided_at.isoformat() if line.voided_at else None
                    ),
                }
                for line in lines
            ],
        }

    def get_customer_statement(
        self, company_id: UUID, customer_id: UUID
    ) -> dict[str, Any]:
        """Composes across every one of a customer's contracts, read-only
        (plan.md §27's fourth document). Batch-loads every contract's
        schedule lines and net-allocated amounts in two queries total —
        never one ``get_active_version()``/``get_lines()``/
        ``get_net_allocated_by_line()`` round trip per contract (T213's
        N+1 prohibition; ``active_schedule_version_id`` is read directly
        off each contract row rather than re-queried via
        ``get_active_version()``, exactly as
        ``list_active_lines_for_company()``'s own join condition already
        establishes as this module's canonical way to identify "the"
        active version for a contract)."""
        self._authorize_read(company_id)
        customer_contracts, _total = self._contracts.list_filtered(
            company_id, customer_id=customer_id, skip=0, limit=1000
        )

        version_ids = [
            c.active_schedule_version_id
            for c in customer_contracts
            if c.active_schedule_version_id is not None
        ]
        lines_by_version = self._schedule.get_lines_for_versions(
            company_id, version_ids
        )
        all_active_line_ids = [
            line.id
            for lines in lines_by_version.values()
            for line in lines
            if line.waived_at is None and line.voided_at is None
        ]
        net_allocated = self._allocation_refs.get_net_allocated_by_line(
            company_id, all_active_line_ids
        )

        contract_summaries: list[dict[str, Any]] = []
        for contract in customer_contracts:
            outstanding = None
            if contract.active_schedule_version_id is not None:
                lines = lines_by_version.get(contract.active_schedule_version_id, [])
                active_lines = [
                    line
                    for line in lines
                    if line.waived_at is None and line.voided_at is None
                ]
                outstanding = str(
                    sum(
                        (
                            line.scheduled_amount
                            - net_allocated.get(line.id, Decimal("0"))
                            for line in active_lines
                        ),
                        Decimal("0"),
                    )
                )
            contract_summaries.append(
                {
                    "contract_id": str(contract.id),
                    "contract_number": contract.contract_number,
                    "status": contract.status,
                    "contractual_total": str(contract.contractual_total),
                    "schedule_outstanding": outstanding,
                }
            )

        return {
            "document_type": "customer_statement",
            "customer_id": str(customer_id),
            "contracts": contract_summaries,
        }
