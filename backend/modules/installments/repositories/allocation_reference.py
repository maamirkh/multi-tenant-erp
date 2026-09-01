"""InstallmentAllocationReferenceRepository — append-only data access.

Deliberately NOT a ``BaseRepository`` subclass — that base class's
``create()``/``update()`` methods commit internally and expose mutation
this table must never have (BR-INST-017: never updated or deleted, a
reversal always inserts a new row). Matches
``InstallmentAuditLogRepository``'s identical precedent.

Spec ref: specs/010-installments/data-model.md
"InstallmentAllocationReference"; specs/010-installments/plan.md §21.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from modules.installments.models.allocation_reference import (
    InstallmentAllocationReference,
)


class InstallmentAllocationReferenceRepository:
    """Append-only data access for ``installment_allocation_references``."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def create(
        self, reference: InstallmentAllocationReference
    ) -> InstallmentAllocationReference:
        """Stage a new allocation-reference row for insert. Flush only —
        the caller commits together with the Accounting effect it
        explains (plan.md §21)."""
        self.db.add(reference)
        self.db.flush()
        return reference

    def list_for_contract(
        self, company_id: UUID, contract_id: UUID
    ) -> list[InstallmentAllocationReference]:
        stmt = (
            select(InstallmentAllocationReference)
            .where(InstallmentAllocationReference.company_id == company_id)
            .where(InstallmentAllocationReference.contract_id == contract_id)
            .order_by(InstallmentAllocationReference.allocated_at)
        )
        return list(self.db.execute(stmt).scalars().all())

    def list_for_schedule_line(
        self, company_id: UUID, schedule_line_id: UUID
    ) -> list[InstallmentAllocationReference]:
        stmt = (
            select(InstallmentAllocationReference)
            .where(InstallmentAllocationReference.company_id == company_id)
            .where(InstallmentAllocationReference.schedule_line_id == schedule_line_id)
            .order_by(InstallmentAllocationReference.allocated_at)
        )
        return list(self.db.execute(stmt).scalars().all())

    def get_net_allocated_by_line(
        self, company_id: UUID, schedule_line_ids: list[UUID]
    ) -> dict[UUID, Decimal]:
        """Net allocated amount per schedule line (non-reversal minus
        reversal), for every line id in ``schedule_line_ids`` that has at
        least one reference row. Lines with no rows at all are simply
        absent from the returned mapping (caller treats missing as zero)."""
        if not schedule_line_ids:
            return {}
        signed_amount = func.sum(
            case(
                (
                    InstallmentAllocationReference.is_reversal,
                    -InstallmentAllocationReference.allocated_amount,
                ),
                else_=InstallmentAllocationReference.allocated_amount,
            )
        )
        stmt = (
            select(InstallmentAllocationReference.schedule_line_id, signed_amount)
            .where(InstallmentAllocationReference.company_id == company_id)
            .where(
                InstallmentAllocationReference.schedule_line_id.in_(schedule_line_ids)
            )
            .group_by(InstallmentAllocationReference.schedule_line_id)
        )
        return {
            schedule_line_id: amount
            for schedule_line_id, amount in self.db.execute(stmt).all()
        }

    def get_by_payment_id(
        self, company_id: UUID, accounting_payment_id: UUID
    ) -> list[InstallmentAllocationReference]:
        """All (non-reversal) allocation-reference rows created by a
        single collection event — used by ``reverse_collection()`` (T123)
        to find what to reverse."""
        stmt = (
            select(InstallmentAllocationReference)
            .where(InstallmentAllocationReference.company_id == company_id)
            .where(
                InstallmentAllocationReference.accounting_payment_id
                == accounting_payment_id
            )
            .where(InstallmentAllocationReference.is_reversal == False)  # noqa: E712
            .order_by(InstallmentAllocationReference.allocation_order)
        )
        return list(self.db.execute(stmt).scalars().all())

    def list_for_company(
        self,
        company_id: UUID,
        *,
        since: date | None = None,
        until: date | None = None,
        include_reversals: bool = False,
        skip: int = 0,
        limit: int = 20,
    ) -> tuple[list[InstallmentAllocationReference], int]:
        """Company-wide, paginated allocation-reference listing — the
        Collection report's base query (tasks.md T204) and the
        dashboard's collected-today/this-month KPI input (T205). Date
        filters apply to ``allocated_at`` (the date Accounting actually
        recorded the collection, never a schedule due date)."""
        base_stmt = select(InstallmentAllocationReference).where(
            InstallmentAllocationReference.company_id == company_id
        )
        if not include_reversals:
            base_stmt = base_stmt.where(
                InstallmentAllocationReference.is_reversal == False  # noqa: E712
            )
        if since is not None:
            base_stmt = base_stmt.where(
                func.date(InstallmentAllocationReference.allocated_at) >= since
            )
        if until is not None:
            base_stmt = base_stmt.where(
                func.date(InstallmentAllocationReference.allocated_at) <= until
            )

        count_stmt = select(func.count()).select_from(base_stmt.subquery())
        total: int = self.db.execute(count_stmt).scalar_one()

        rows_stmt = (
            base_stmt.order_by(InstallmentAllocationReference.allocated_at.desc())
            .offset(skip)
            .limit(limit)
        )
        items = list(self.db.execute(rows_stmt).scalars().all())
        return items, total

    def sum_allocated_between(
        self, company_id: UUID, *, since: date, until: date
    ) -> Decimal:
        """A single aggregate ``SUM`` for a date window — the dashboard's
        collected-today/collected-this-month KPIs (T205), never a Python
        loop summing individually-fetched rows."""
        stmt = (
            select(
                func.coalesce(
                    func.sum(InstallmentAllocationReference.allocated_amount), 0
                )
            )
            .where(InstallmentAllocationReference.company_id == company_id)
            .where(InstallmentAllocationReference.is_reversal == False)  # noqa: E712
            .where(func.date(InstallmentAllocationReference.allocated_at) >= since)
            .where(func.date(InstallmentAllocationReference.allocated_at) <= until)
        )
        return Decimal(self.db.execute(stmt).scalar_one())
