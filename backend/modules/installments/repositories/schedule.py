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

from decimal import Decimal
from uuid import UUID

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from modules.installments.models.allocation_reference import (
    InstallmentAllocationReference,
)
from modules.installments.models.contract import InstallmentContract
from modules.installments.models.schedule import (
    InstallmentScheduleLine,
    InstallmentScheduleVersion,
)

#: Contracts still capable of carrying a live, servicing-relevant schedule
#: obligation — matches InstallmentCollectionService's own
#: _REVERSIBLE_STATUSES (plan.md §25's due/overdue/aging population).
_SERVICEABLE_STATUSES = ("ACTIVE", "DEFAULTED")


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

    def get_lines_for_versions(
        self, company_id: UUID, schedule_version_ids: list[UUID]
    ) -> dict[UUID, list[InstallmentScheduleLine]]:
        """Batch line fetch for a SET of schedule versions in ONE query —
        grouped by ``schedule_version_id`` — for callers that need every
        line of every contract in a customer/company-wide set without a
        per-contract ``get_lines()`` call (the exact N+1 pattern T213
        forbids; found in ``InstallmentDocumentService
        .get_customer_statement()``/``InstallmentCustomerSummaryService
        .get_summary()`` and fixed by routing both through this method).
        Returns an empty dict for an empty input list (no query issued)."""
        if not schedule_version_ids:
            return {}
        stmt = (
            select(InstallmentScheduleLine)
            .where(InstallmentScheduleLine.company_id == company_id)
            .where(
                InstallmentScheduleLine.schedule_version_id.in_(schedule_version_ids)
            )
            .order_by(
                InstallmentScheduleLine.schedule_version_id,
                InstallmentScheduleLine.sequence,
            )
        )
        lines_by_version: dict[UUID, list[InstallmentScheduleLine]] = {}
        for line in self.db.execute(stmt).scalars().all():
            lines_by_version.setdefault(line.schedule_version_id, []).append(line)
        return lines_by_version

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

    def list_active_lines_for_company(
        self, company_id: UUID, *, skip: int = 0, limit: int = 20
    ) -> tuple[list[tuple[InstallmentScheduleLine, InstallmentContract]], int]:
        """The base population every due/overdue/aging report page draws
        from (tasks.md T204/T213): every non-waived, non-voided line
        belonging to its owning contract's currently-``ACTIVE`` schedule
        version, for contracts still capable of carrying a live
        obligation. Returns each line paired with its owning contract in
        the SAME query (one JOIN) so a report page never issues a
        separate per-line or per-contract follow-up lookup — the join
        condition (``InstallmentContract.active_schedule_version_id ==
        InstallmentScheduleLine.schedule_version_id``) is exactly how
        ``InstallmentContractService.get_active_schedule()`` already
        identifies "the" active version for a contract, reused here at
        set level instead of one-contract-at-a-time.
        """
        base_stmt = (
            select(InstallmentScheduleLine, InstallmentContract)
            .join(
                InstallmentContract,
                InstallmentContract.active_schedule_version_id
                == InstallmentScheduleLine.schedule_version_id,
            )
            .where(InstallmentScheduleLine.company_id == company_id)
            .where(InstallmentContract.company_id == company_id)
            .where(InstallmentContract.status.in_(_SERVICEABLE_STATUSES))
            .where(InstallmentContract.is_deleted == False)  # noqa: E712
            .where(InstallmentScheduleLine.waived_at.is_(None))
            .where(InstallmentScheduleLine.voided_at.is_(None))
        )
        count_stmt = select(func.count()).select_from(base_stmt.subquery())
        total: int = self.db.execute(count_stmt).scalar_one()

        rows_stmt = (
            base_stmt.order_by(InstallmentScheduleLine.due_date)
            .offset(skip)
            .limit(limit)
        )
        rows = self.db.execute(rows_stmt).all()
        items = [(row[0], row[1]) for row in rows]
        return items, total

    def sum_schedule_outstanding_for_company(self, company_id: UUID) -> Decimal:
        """One aggregate query for the dashboard's "outstanding" KPI
        (tasks.md T205): ``SUM(scheduled_amount) - SUM(net allocated)``
        across every active line of every serviceable contract, via a
        correlated subquery on ``installment_allocation_references`` —
        never a Python loop over per-contract
        ``InstallmentOutstandingService`` calls (which would be one
        query per contract, the exact N+1 T213 forbids)."""
        return self._sum_outstanding_for_statuses(
            company_id, statuses=_SERVICEABLE_STATUSES
        )

    def sum_schedule_outstanding_for_statuses(
        self, company_id: UUID, *, statuses: tuple[str, ...]
    ) -> Decimal:
        """Same aggregate as ``sum_schedule_outstanding_for_company`` but
        for an arbitrary contract-status set (e.g. ``WRITTEN_OFF``)
        rather than the hardcoded serviceable set — lets dashboard KPIs
        for terminal-status balances (e.g. written-off balance) be a
        single query instead of a per-contract loop (T213's N+1
        prohibition applies to this KPI too, not just the paginated
        report list endpoints)."""
        return self._sum_outstanding_for_statuses(company_id, statuses=statuses)

    def _sum_outstanding_for_statuses(
        self, company_id: UUID, *, statuses: tuple[str, ...]
    ) -> Decimal:
        net_allocated_subq = (
            select(
                InstallmentAllocationReference.schedule_line_id.label("line_id"),
                func.sum(
                    case(
                        (
                            InstallmentAllocationReference.is_reversal,
                            -InstallmentAllocationReference.allocated_amount,
                        ),
                        else_=InstallmentAllocationReference.allocated_amount,
                    )
                ).label("net_allocated"),
            )
            .where(InstallmentAllocationReference.company_id == company_id)
            .group_by(InstallmentAllocationReference.schedule_line_id)
            .subquery()
        )
        stmt = (
            select(
                func.coalesce(
                    func.sum(
                        InstallmentScheduleLine.scheduled_amount
                        - func.coalesce(net_allocated_subq.c.net_allocated, 0)
                    ),
                    0,
                )
            )
            .select_from(InstallmentScheduleLine)
            .join(
                InstallmentContract,
                InstallmentContract.active_schedule_version_id
                == InstallmentScheduleLine.schedule_version_id,
            )
            .outerjoin(
                net_allocated_subq,
                net_allocated_subq.c.line_id == InstallmentScheduleLine.id,
            )
            .where(InstallmentScheduleLine.company_id == company_id)
            .where(InstallmentContract.company_id == company_id)
            .where(InstallmentContract.status.in_(statuses))
            .where(InstallmentContract.is_deleted == False)  # noqa: E712
            .where(InstallmentScheduleLine.waived_at.is_(None))
            .where(InstallmentScheduleLine.voided_at.is_(None))
        )
        return Decimal(self.db.execute(stmt).scalar_one())
