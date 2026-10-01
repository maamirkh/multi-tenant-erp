"""ReportsAuditRepository — append-only data access for
``reports_audit_log`` (plan.md §22).

Deliberately NOT a ``BaseRepository`` subclass — that base class's
``create()``/``update()`` commit internally, and an audit row must be
committed by the *caller*, in the same transaction as the action it
documents. Mirrors ``InstallmentAuditLogRepository``'s identical
precedent: ``create()`` stages (``add()`` + ``flush()``) and never
commits.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from modules.reports.models.reports_audit_log import ReportsAuditLog


class ReportsAuditRepository:
    """Append-only data access for ``reports_audit_log``."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, log: ReportsAuditLog) -> ReportsAuditLog:
        """Stage a new audit record for insert. Caller commits."""
        self.db.add(log)
        self.db.flush()
        return log

    def list_for_company(
        self, company_id: UUID, entity_type: str | None = None
    ) -> list[ReportsAuditLog]:
        stmt = select(ReportsAuditLog).where(ReportsAuditLog.company_id == company_id)
        if entity_type is not None:
            stmt = stmt.where(ReportsAuditLog.entity_type == entity_type)
        stmt = stmt.order_by(ReportsAuditLog.created_at)
        return list(self.db.execute(stmt).scalars().all())
