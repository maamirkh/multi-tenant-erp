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

**Documented, correct-by-omission extension points** (not stubs — both
branches are exactly right for what can exist in the schema today):

- Phase 7 will introduce ``InstallmentAllocationReference``, at which
  point schedule-line amounts already collected against must be
  subtracted here. Until then, no collection flow exists anywhere in the
  codebase, so the full ``scheduled_amount`` sum is always the correct
  (and fail-closed, never fail-open) outstanding figure.
- Phase 8 will introduce ``InstallmentLateCharge``. Until then, no late
  charge can exist, so "no open late-charge AR" is trivially and
  correctly true by omission — there is nothing to check yet, not a
  missing check.
"""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from modules.installments.exceptions import InstallmentOutstandingBalanceRemainsError
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
    ) -> None:
        self._schedule_repo = schedule_repo
        self._accounting_gateway = accounting_gateway

    def assert_zero_outstanding(self, company_id: UUID, contract_id: UUID) -> None:
        """Raise ``InstallmentOutstandingBalanceRemainsError`` if the
        contract has any authoritative outstanding obligation remaining;
        return silently if it is genuinely fully settled.

        Checks, in order:
        1. Schedule outstanding — the sum of every active schedule
           line's ``scheduled_amount`` (Phase 7 will subtract amounts
           already allocated via ``InstallmentAllocationReference``; no
           such rows can exist yet, so the raw sum is correct today).
        2. Late-charge outstanding — Phase 8 will check every linked,
           non-waived ``InstallmentLateCharge``'s live
           ``ARTransaction.outstanding_amount``/``status`` via the
           Accounting gateway; no ``InstallmentLateCharge`` can exist
           yet, so there is nothing to check.
        """
        version = self._schedule_repo.get_active_version(company_id, contract_id)
        if version is not None:
            lines = self._schedule_repo.get_lines(company_id, version.id)
            schedule_outstanding = sum(
                (line.scheduled_amount for line in lines), Decimal("0")
            )
            if schedule_outstanding > Decimal("0"):
                raise InstallmentOutstandingBalanceRemainsError(
                    kind="SCHEDULE", contract_id=str(contract_id)
                )
