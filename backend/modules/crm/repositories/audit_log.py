"""CrmAuditLogRepository — append-only data access for ``crm_audit_log``.

Deliberately NOT a ``BaseRepository`` subclass — that base class provides
``update()``/``soft_delete()`` methods this table must never expose
(plan.md §18.2). A standalone class with exactly two methods (``create``,
``list_for_entity``), matching ``AccountingAuditLogRepository``'s exact
precedent (confirmed via inspection: it defines only ``create``/
``list_*``, no mutation methods at all).

Spec ref: specs/009-crm/spec.md §44; plan.md §18.2.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from modules.crm.models.audit import CrmAuditLog


class CrmAuditLogRepository:
    """Append-only data access for ``crm_audit_log``."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, log: CrmAuditLog) -> CrmAuditLog:
        """Stage a new audit record for insert. Caller commits."""
        self.db.add(log)
        self.db.flush()
        return log

    def list_for_entity(
        self, company_id: UUID, entity_type: str, entity_id: UUID
    ) -> list[CrmAuditLog]:
        stmt = (
            select(CrmAuditLog)
            .where(CrmAuditLog.company_id == company_id)
            .where(CrmAuditLog.entity_type == entity_type)
            .where(CrmAuditLog.entity_id == entity_id)
            .order_by(CrmAuditLog.created_at)
        )
        return list(self.db.execute(stmt).scalars().all())
