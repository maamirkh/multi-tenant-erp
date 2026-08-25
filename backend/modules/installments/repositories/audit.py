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

from sqlalchemy import select
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
