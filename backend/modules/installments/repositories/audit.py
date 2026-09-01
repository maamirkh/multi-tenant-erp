"""InstallmentAuditLogRepository — append-only data access.

Deliberately NOT a ``BaseRepository`` subclass — that base class's
``create()``/``update()`` methods commit internally and expose mutation
this table must never have (plan.md §17). A standalone class with
exactly two methods (``create``, ``list_for_entity``), matching
``AccountingAuditLogRepository``/``CrmAuditLogRepository``'s identical
precedent.

Spec ref: specs/010-installments/plan.md §17.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from modules.installments.models.audit import InstallmentAuditLog


class InstallmentAuditLogRepository:
    """Append-only data access for ``installment_audit_log``."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, log: InstallmentAuditLog) -> InstallmentAuditLog:
        """Stage a new audit record for insert. Caller commits."""
        self.db.add(log)
        self.db.flush()
        return log

    def list_for_entity(
        self, company_id: UUID, entity_type: str, entity_id: UUID
    ) -> list[InstallmentAuditLog]:
        stmt = (
            select(InstallmentAuditLog)
            .where(InstallmentAuditLog.company_id == company_id)
            .where(InstallmentAuditLog.entity_type == entity_type)
            .where(InstallmentAuditLog.entity_id == entity_id)
            .order_by(InstallmentAuditLog.occurred_at)
        )
        return list(self.db.execute(stmt).scalars().all())

    def list_by_action_for_company(
        self,
        company_id: UUID,
        *,
        entity_type: str,
        action: str,
        skip: int = 0,
        limit: int = 20,
    ) -> tuple[list[InstallmentAuditLog], int]:
        """Company-wide, action-filtered audit listing — the Settlement
        report's base query (tasks.md T204: "Installments (SETTLED audit
        events + contract closure data)"), most-recent first."""
        base_stmt = (
            select(InstallmentAuditLog)
            .where(InstallmentAuditLog.company_id == company_id)
            .where(InstallmentAuditLog.entity_type == entity_type)
            .where(InstallmentAuditLog.action == action)
        )
        count_stmt = select(func.count()).select_from(base_stmt.subquery())
        total: int = self.db.execute(count_stmt).scalar_one()

        rows_stmt = (
            base_stmt.order_by(InstallmentAuditLog.occurred_at.desc())
            .offset(skip)
            .limit(limit)
        )
        items = list(self.db.execute(rows_stmt).scalars().all())
        return items, total
