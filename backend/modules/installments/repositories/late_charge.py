"""InstallmentLateChargeRepository — data access for ``installment_late_charges``.

Deliberately NOT a ``BaseRepository`` subclass — that base class's
``create()``/``update()`` methods commit internally, which would break
the staged/finalize atomic unit a late charge is created inside (plan.md
§12.1/§12.2: ``InstallmentLateCharge`` must commit together with GL/AR/
ledger, in the same call to Accounting's ``finalize_adjustment()``/
``reverse_adjustment()``, never on its own). Mirrors
``InstallmentAllocationReferenceRepository``'s identical precedent, and
the same "not ``self._transactions.update()``" finding plan.md §12.3.3
made for Accounting's own ``stage_write_off()``.

Spec ref: specs/010-installments/data-model.md "InstallmentLateCharge";
specs/010-installments/plan.md §12.1/§12.2.
"""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from modules.installments.models.late_charge import InstallmentLateCharge


class InstallmentLateChargeRepository:
    """Data access for ``installment_late_charges`` — flush-only writes."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, late_charge: InstallmentLateCharge) -> InstallmentLateCharge:
        """Stage a new late-charge row for insert. Flush only — the
        caller commits together with the Accounting effect it explains
        (``AccountsReceivableService.finalize_adjustment()``)."""
        self.db.add(late_charge)
        self.db.flush()
        return late_charge

    def get_by_line_and_occurrence(
        self, company_id: UUID, schedule_line_id: UUID, overdue_occurrence_date: date
    ) -> InstallmentLateCharge | None:
        """Used to enforce FR-INST-171's "never applied more than once
        for the same overdue occurrence" — the service-layer pre-check;
        the DB unique constraint (migration 066) is the real backstop
        against a concurrent race."""
        stmt = (
            select(InstallmentLateCharge)
            .where(InstallmentLateCharge.company_id == company_id)
            .where(InstallmentLateCharge.schedule_line_id == schedule_line_id)
            .where(
                InstallmentLateCharge.overdue_occurrence_date == overdue_occurrence_date
            )
            .where(InstallmentLateCharge.is_deleted == False)  # noqa: E712
        )
        return self.db.execute(stmt).scalars().one_or_none()

    def get_by_id_or_none(
        self, company_id: UUID, late_charge_id: UUID
    ) -> InstallmentLateCharge | None:
        stmt = (
            select(InstallmentLateCharge)
            .where(InstallmentLateCharge.id == late_charge_id)
            .where(InstallmentLateCharge.company_id == company_id)
            .where(InstallmentLateCharge.is_deleted == False)  # noqa: E712
        )
        return self.db.execute(stmt).scalars().one_or_none()

    def list_for_contract(
        self, company_id: UUID, contract_id: UUID
    ) -> list[InstallmentLateCharge]:
        stmt = (
            select(InstallmentLateCharge)
            .where(InstallmentLateCharge.company_id == company_id)
            .where(InstallmentLateCharge.contract_id == contract_id)
            .where(InstallmentLateCharge.is_deleted == False)  # noqa: E712
            .order_by(InstallmentLateCharge.charged_at)
        )
        return list(self.db.execute(stmt).scalars().all())

    def list_for_company(
        self, company_id: UUID, *, exclude_waived: bool = True
    ) -> list[InstallmentLateCharge]:
        """Every late charge across the company — the dashboard
        "outstanding" KPI's late-charge component (tasks.md T205),
        typically a much smaller row count than the full schedule-line
        population, so a bounded per-charge Accounting AR-status check
        (the same live-read ``InstallmentOutstandingService`` already
        does per-contract) stays acceptable here without a dedicated
        bulk Accounting-side query."""
        stmt = (
            select(InstallmentLateCharge)
            .where(InstallmentLateCharge.company_id == company_id)
            .where(InstallmentLateCharge.is_deleted == False)  # noqa: E712
        )
        if exclude_waived:
            stmt = stmt.where(InstallmentLateCharge.waived_at.is_(None))
        return list(self.db.execute(stmt).scalars().all())

    def mark_waived(
        self,
        late_charge: InstallmentLateCharge,
        waived_at: datetime,
        waived_by: UUID | None,
        reason: str,
    ) -> InstallmentLateCharge:
        """Flush-only waiver mutation — direct attribute assignment +
        ``db.add()``/``db.flush()``, never ``BaseRepository.update()``
        (whose internal commit would break the atomic unit shared with
        Accounting's ``reverse_adjustment()`` call, plan.md §12.2)."""
        late_charge.waived_at = waived_at
        late_charge.waived_by = waived_by
        late_charge.waived_reason = reason
        self.db.add(late_charge)
        self.db.flush()
        return late_charge
