"""InstallmentOutstandingService — the single authoritative completion
guard (plan.md §9.3, tasks.md T108).

No contract may transition to ``COMPLETED`` (T122's ``complete()``) based
on schedule-outstanding alone (§14 of the Phase 6 hard-gate rules) — this
service is the one place that decides whether *every* obligation a
contract can carry is genuinely settled. It never duplicates a balance:
schedule outstanding is derived live from ``InstallmentScheduleLine`` (an
Installments-owned, already-authoritative table — no Accounting value
exists for it), and late-charge outstanding is a live read of
Accounting's own ``ARTransaction`` via ``AccountingIntegrationGateway``,
never cached or re-derived.

**[Phase 7 extension applied]** ``InstallmentAllocationReference`` (T118)
now exists, so schedule outstanding correctly subtracts net allocated
amounts (non-reversal minus reversal) per line, via
``InstallmentAllocationReferenceRepository.get_net_allocated_by_line()``
— no longer the raw ``scheduled_amount`` sum a pre-Phase-7 caller would
have seen.

**[Phase 8 extension applied]** ``InstallmentLateCharge`` (T140) now
exists — every linked, non-waived late charge's live
``ARTransaction.outstanding_amount``/``status`` is checked via the
Accounting gateway's read-only ``get_ar_transaction()`` (never a cached/
duplicated balance): a charge counts as still-outstanding unless its
``ARTransaction`` is missing, fully paid (``outstanding_amount <= 0``),
or ``status == "WRITTEN_OFF"``.
"""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from modules.installments.exceptions import InstallmentOutstandingBalanceRemainsError
from modules.installments.repositories.allocation_reference import (
    InstallmentAllocationReferenceRepository,
)
from modules.installments.repositories.late_charge import (
    InstallmentLateChargeRepository,
)
from modules.installments.repositories.schedule import InstallmentScheduleRepository
from modules.installments.services.accounting_gateway import (
    AccountingIntegrationGateway,
)


class InstallmentOutstandingService:
    """Pure live-read completion guard — no state of its own, no
    duplicated balance (plan.md §9.3)."""

    def __init__(
        self,
        schedule_repo: InstallmentScheduleRepository,
        accounting_gateway: AccountingIntegrationGateway,
        allocation_ref_repo: InstallmentAllocationReferenceRepository | None = None,
        late_charge_repo: InstallmentLateChargeRepository | None = None,
    ) -> None:
        self._schedule_repo = schedule_repo
        self._accounting_gateway = accounting_gateway
        self._allocation_refs = allocation_ref_repo
        self._late_charges = late_charge_repo

    def assert_zero_outstanding(self, company_id: UUID, contract_id: UUID) -> None:
        """Raise ``InstallmentOutstandingBalanceRemainsError`` if the
        contract has any authoritative outstanding obligation remaining;
        return silently if it is genuinely fully settled.

        Checks, in order:
        1. Schedule outstanding — the sum of every active schedule
           line's ``scheduled_amount`` minus its net allocated amount
           (``InstallmentAllocationReference``, non-reversal minus
           reversal, T118).
        2. Late-charge outstanding — every linked, non-waived
           ``InstallmentLateCharge``'s live
           ``ARTransaction.outstanding_amount``/``status`` via the
           Accounting gateway (T140).
        """
        version = self._schedule_repo.get_active_version(company_id, contract_id)
        if version is not None:
            lines = self._schedule_repo.get_lines(company_id, version.id)
            active_lines = [
                line
                for line in lines
                if line.waived_at is None and line.voided_at is None
            ]
            net_allocated: dict[UUID, Decimal] = {}
            if self._allocation_refs is not None:
                net_allocated = self._allocation_refs.get_net_allocated_by_line(
                    company_id, [line.id for line in active_lines]
                )
            schedule_outstanding = sum(
                (
                    line.scheduled_amount - net_allocated.get(line.id, Decimal("0"))
                    for line in active_lines
                ),
                Decimal("0"),
            )
            if schedule_outstanding > Decimal("0"):
                raise InstallmentOutstandingBalanceRemainsError(
                    kind="SCHEDULE", contract_id=str(contract_id)
                )

        if self._late_charges is not None:
            for charge in self._late_charges.list_for_contract(company_id, contract_id):
                if charge.waived_at is not None:
                    continue
                ar_transaction = None
                if charge.accounting_ar_transaction_id is not None:
                    ar_transaction = self._accounting_gateway.get_ar_transaction(
                        company_id, charge.accounting_ar_transaction_id
                    )
                if ar_transaction is None:
                    continue
                if (
                    ar_transaction.status != "WRITTEN_OFF"
                    and ar_transaction.outstanding_amount > Decimal("0")
                ):
                    raise InstallmentOutstandingBalanceRemainsError(
                        kind="LATE_CHARGE",
                        contract_id=str(contract_id),
                        ar_transaction_id=str(charge.accounting_ar_transaction_id),
                    )
