"""InstallmentScheduleRepository — persists a schedule version + its lines
atomically.

``flush()`` only, never ``commit()`` — the caller (a later-phase service
such as ``InstallmentContractService.activate()``) owns the transaction
and commits once, together with the rest of that unit of work (plan.md
§21). Mirrors ``JournalLineRepository``/``AccountingAuditLogRepository``'s
established flush-only convention.

No ``update_schedule_line()``/``update_version()`` method exists anywhere
on this class — immutability is enforced by omission, not a DB trigger
(T072 proves this structurally).

Spec ref: specs/010-installments/plan.md §21; specs/010-installments/
data-model.md "InstallmentScheduleVersion"/"InstallmentScheduleLine".
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from modules.installments.models.schedule import (
    InstallmentScheduleLine,
    InstallmentScheduleVersion,
)


class InstallmentScheduleRepository:
    """Data-access layer for schedule versions + their append-only lines."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def create_version_with_lines(
        self,
        version: InstallmentScheduleVersion,
        lines: list[InstallmentScheduleLine],
    ) -> InstallmentScheduleVersion:
        """Stage a new version and its lines in one atomic unit — flush
        only, the caller commits. ``lines`` must already carry
        ``company_id`` and ``sequence``; ``schedule_version_id`` is
        populated here once ``version.id`` is available post-flush."""
        self.db.add(version)
        self.db.flush()
        for line in lines:
            line.schedule_version_id = version.id
            self.db.add(line)
        self.db.flush()
        return version

    def get_active_version(
        self, company_id: UUID, contract_id: UUID
    ) -> InstallmentScheduleVersion | None:
        stmt = (
            select(InstallmentScheduleVersion)
            .where(InstallmentScheduleVersion.company_id == company_id)
            .where(InstallmentScheduleVersion.contract_id == contract_id)
            .where(InstallmentScheduleVersion.status == "ACTIVE")
            .where(InstallmentScheduleVersion.is_deleted == False)  # noqa: E712
        )
        return self.db.execute(stmt).scalars().one_or_none()

    def get_version(
        self, company_id: UUID, contract_id: UUID, version_number: int
    ) -> InstallmentScheduleVersion | None:
        stmt = (
            select(InstallmentScheduleVersion)
            .where(InstallmentScheduleVersion.company_id == company_id)
            .where(InstallmentScheduleVersion.contract_id == contract_id)
            .where(InstallmentScheduleVersion.version_number == version_number)
            .where(InstallmentScheduleVersion.is_deleted == False)  # noqa: E712
        )
        return self.db.execute(stmt).scalars().one_or_none()

    def get_lines(
        self, company_id: UUID, schedule_version_id: UUID
    ) -> list[InstallmentScheduleLine]:
        stmt = (
            select(InstallmentScheduleLine)
            .where(InstallmentScheduleLine.company_id == company_id)
            .where(InstallmentScheduleLine.schedule_version_id == schedule_version_id)
            .order_by(InstallmentScheduleLine.sequence)
        )
        return list(self.db.execute(stmt).scalars().all())

    def get_line_by_id(
        self, company_id: UUID, schedule_line_id: UUID
    ) -> InstallmentScheduleLine | None:
        """Tenant-scoped lookup of a single schedule line by id (Phase 8,
        T142) — used by ``InstallmentDelinquencyService.apply_late_charge()``
        to resolve the line a late charge targets."""
        stmt = select(InstallmentScheduleLine).where(
            InstallmentScheduleLine.company_id == company_id,
            InstallmentScheduleLine.id == schedule_line_id,
        )
        return self.db.execute(stmt).scalars().one_or_none()
