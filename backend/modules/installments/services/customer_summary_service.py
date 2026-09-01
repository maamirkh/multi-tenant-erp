"""InstallmentCustomerSummaryService — read-only cross-contract customer
summary (tasks.md T207).

Importable directly by CRM's ``Customer360Service`` for a unified
customer view — no CRM-side change is made in this Epic (that import is
out of scope); the interface exists here so a future, separately-scoped
change can wire it in without any Installments-side rework.

Spec ref: specs/010-installments/plan.md §25.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from modules.installments.repositories.allocation_reference import (
    InstallmentAllocationReferenceRepository,
)
from modules.installments.repositories.contract import InstallmentContractRepository
from modules.installments.repositories.schedule import InstallmentScheduleRepository
from modules.installments.services.access_policy import (
    InstallmentAccessPolicy,
    InstallmentOperationClass,
)


@dataclass(frozen=True)
class InstallmentCustomerSummary:
    customer_id: UUID
    contract_count: int
    active_contract_count: int
    total_contractual_amount: Decimal
    total_outstanding_amount: Decimal
    defaulted_contract_count: int
    written_off_contract_count: int


class InstallmentCustomerSummaryService:
    """Read-only — no repository write call anywhere in this class."""

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

    def get_summary(
        self, company_id: UUID, customer_id: UUID
    ) -> InstallmentCustomerSummary:
        if self._access_policy is not None:
            self._access_policy.authorize(
                company_id=company_id, operation=InstallmentOperationClass.READ
            )
        contracts, total = self._contracts.list_filtered(
            company_id, customer_id=customer_id, skip=0, limit=1000
        )

        active_count = sum(1 for c in contracts if c.status == "ACTIVE")
        defaulted_count = sum(1 for c in contracts if c.status == "DEFAULTED")
        written_off_count = sum(1 for c in contracts if c.status == "WRITTEN_OFF")
        total_contractual = sum((c.contractual_total for c in contracts), Decimal("0"))

        total_outstanding = Decimal("0")
        for contract in contracts:
            if contract.status not in ("ACTIVE", "DEFAULTED"):
                continue
            version = self._schedule.get_active_version(company_id, contract.id)
            if version is None:
                continue
            lines = self._schedule.get_lines(company_id, version.id)
            active_lines = [
                line
                for line in lines
                if line.waived_at is None and line.voided_at is None
            ]
            net_allocated = self._allocation_refs.get_net_allocated_by_line(
                company_id, [line.id for line in active_lines]
            )
            total_outstanding += sum(
                (
                    line.scheduled_amount - net_allocated.get(line.id, Decimal("0"))
                    for line in active_lines
                ),
                Decimal("0"),
            )

        return InstallmentCustomerSummary(
            customer_id=customer_id,
            contract_count=total,
            active_contract_count=active_count,
            total_contractual_amount=total_contractual,
            total_outstanding_amount=total_outstanding,
            defaulted_contract_count=defaulted_count,
            written_off_contract_count=written_off_count,
        )
