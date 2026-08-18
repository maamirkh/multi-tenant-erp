"""ActivityRepository — data access for the ``crm_activities`` table.

Spec ref: specs/009-crm/spec.md §19, §41 (overdue follow-ups), §42; plan.md §8.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from core.repositories.base import BaseRepository
from core.utils.datetime import utcnow
from modules.crm.models.activity import Activity


class ActivityRepository(BaseRepository[Activity]):
    """Data-access layer for ``crm_activities``."""

    def __init__(self, db: Session) -> None:
        super().__init__(db=db, model=Activity)

    def list_filtered(
        self,
        company_id: UUID,
        *,
        activity_type: str | None = None,
        status: str | None = None,
        assigned_to: UUID | None = None,
        lead_id: UUID | None = None,
        customer_id: UUID | None = None,
        opportunity_id: UUID | None = None,
        due_from: datetime | None = None,
        due_to: datetime | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Activity], int]:
        """Return a page of Activities and the total matching count
        (spec.md §42's filter set)."""
        stmt = (
            select(Activity)
            .where(Activity.company_id == company_id)
            .where(Activity.is_deleted == False)  # noqa: E712
        )
        if activity_type is not None:
            stmt = stmt.where(Activity.activity_type == activity_type)
        if status is not None:
            stmt = stmt.where(Activity.status == status)
        if assigned_to is not None:
            stmt = stmt.where(Activity.assigned_to == str(assigned_to))
        if lead_id is not None:
            stmt = stmt.where(Activity.lead_id == lead_id)
        if customer_id is not None:
            stmt = stmt.where(Activity.customer_id == str(customer_id))
        if opportunity_id is not None:
            stmt = stmt.where(Activity.opportunity_id == opportunity_id)
        if due_from is not None:
            stmt = stmt.where(Activity.due_date >= due_from)
        if due_to is not None:
            stmt = stmt.where(Activity.due_date <= due_to)

        total = self.db.execute(
            select(func.count()).select_from(stmt.subquery())
        ).scalar_one()

        stmt = (
            stmt.order_by(Activity.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        items = list(self.db.execute(stmt).scalars().all())
        return items, total

    def list_overdue(
        self, company_id: UUID, *, owner_id: UUID | None = None
    ) -> list[Activity]:
        """Return PLANNED Activities whose ``due_date`` has passed (spec.md
        §41's "overdue follow-ups" report), earliest first."""
        stmt = (
            select(Activity)
            .where(Activity.company_id == company_id)
            .where(Activity.is_deleted == False)  # noqa: E712
            .where(Activity.status == "PLANNED")
            .where(Activity.due_date < utcnow())
        )
        if owner_id is not None:
            stmt = stmt.where(Activity.assigned_to == str(owner_id))
        stmt = stmt.order_by(Activity.due_date.asc())
        return list(self.db.execute(stmt).scalars().all())

    # ------------------------------------------------------------------
    # Aggregate methods (Phase 9, T081) — raw values only, no report-
    # shaping, consumed by CrmReportingService. Spec ref: spec.md §40.3.
    # ------------------------------------------------------------------

    def count_completed_by_type_in_period(
        self, company_id: UUID, date_from: datetime | None, date_to: datetime | None
    ) -> dict[str, int]:
        """Count of COMPLETED Activities in the period, grouped by
        ``activity_type`` (spec.md §40.3)."""
        stmt = (
            select(Activity.activity_type, func.count())
            .where(Activity.company_id == company_id)
            .where(Activity.is_deleted == False)  # noqa: E712
            .where(Activity.status == "COMPLETED")
        )
        if date_from is not None:
            stmt = stmt.where(Activity.completed_at >= date_from)
        if date_to is not None:
            stmt = stmt.where(Activity.completed_at <= date_to)
        stmt = stmt.group_by(Activity.activity_type)
        return {row[0]: row[1] for row in self.db.execute(stmt).all()}

    def count_overdue_by_owner(self, company_id: UUID) -> dict[str, int]:
        """Count of overdue (PLANNED, past-due) Activities grouped by
        ``assigned_to`` (spec.md §40.3's "overdue follow-ups... by
        owner")."""
        stmt = (
            select(Activity.assigned_to, func.count())
            .where(Activity.company_id == company_id)
            .where(Activity.is_deleted == False)  # noqa: E712
            .where(Activity.status == "PLANNED")
            .where(Activity.due_date < utcnow())
            .group_by(Activity.assigned_to)
        )
        return {row[0]: row[1] for row in self.db.execute(stmt).all()}
