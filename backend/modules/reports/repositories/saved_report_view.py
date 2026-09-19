"""Repository for ``SavedReportView`` (spec §29, plan.md §15).

Every read/write method requires both ``company_id`` and ``user_id`` —
ownership scope is enforced structurally, never left to the caller
(FR-RPT-205). A row that doesn't exist, belongs to another user, belongs
to another tenant, or is soft-deleted all resolve to the identical
``None`` here — the service layer converts that single outcome into one
``SavedViewNotFoundError``, with no distinguishing signal (plan.md §15).
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from core.repositories.base import BaseRepository
from core.utils.datetime import utcnow
from modules.reports.models.saved_report_view import SavedReportView


class SavedReportViewRepository(BaseRepository[SavedReportView]):
    """Data-access layer for ``saved_report_views``."""

    def __init__(self, db: Session) -> None:
        super().__init__(db=db, model=SavedReportView)

    def get_for_owner(
        self, view_id: UUID, company_id: UUID, user_id: UUID
    ) -> SavedReportView | None:
        """Return the view scoped to ``(id, company_id, user_id)``, or
        ``None`` if absent, owned by another user, or soft-deleted —
        identical outcome for all three (no ownership/existence-probing
        signal)."""
        stmt = (
            select(SavedReportView)
            .where(SavedReportView.id == view_id)
            .where(SavedReportView.company_id == company_id)
            .where(SavedReportView.user_id == user_id)
            .where(SavedReportView.is_deleted == False)  # noqa: E712
        )
        return self.db.execute(stmt).scalars().one_or_none()

    def list_for_user(
        self, company_id: UUID, user_id: UUID, skip: int = 0, limit: int = 20
    ) -> tuple[list[SavedReportView], int]:
        """Return a page of the user's own saved views + total count.
        Soft-deleted rows are always excluded."""
        base_stmt = (
            select(SavedReportView)
            .where(SavedReportView.company_id == company_id)
            .where(SavedReportView.user_id == user_id)
            .where(SavedReportView.is_deleted == False)  # noqa: E712
        )
        count_stmt = select(func.count()).select_from(base_stmt.subquery())
        total: int = self.db.execute(count_stmt).scalar_one()

        rows_stmt = (
            base_stmt.order_by(SavedReportView.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        items: list[SavedReportView] = list(self.db.execute(rows_stmt).scalars().all())
        return items, total

    def soft_delete_for_owner(
        self, view_id: UUID, company_id: UUID, user_id: UUID
    ) -> bool:
        """Soft-delete the view scoped to ``(id, company_id, user_id)``.
        Returns ``False`` (no-op) if no matching, non-deleted row exists —
        the caller is responsible for raising ``SavedViewNotFoundError``."""
        entity = self.get_for_owner(
            view_id=view_id, company_id=company_id, user_id=user_id
        )
        if entity is None:
            return False
        entity.is_deleted = True
        entity.deleted_at = utcnow()
        self.db.commit()
        return True
