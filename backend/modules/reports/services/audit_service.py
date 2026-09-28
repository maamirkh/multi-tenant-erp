"""ReportsAuditService — synchronous audit trail writer (plan.md §22).

``record()`` only **stages** the row (``ReportsAuditRepository.create()``
is ``add()`` + ``flush()``, never a commit) — the caller commits it
together with the action it documents, in the same database transaction:
``SavedViewService`` with its own persistence write, ``ReportExportService``
before it releases any file bytes (§21.8). Mirrors
``InstallmentAuditService``/``AuditLogService`` exactly.
"""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from modules.reports.models.reports_audit_log import ReportsAuditLog
from modules.reports.repositories.reports_audit_repository import (
    ReportsAuditRepository,
)
from modules.reports.schemas.common import JsonValue

AuditEntityType = Literal["ReportExport", "SavedReportView"]
AuditAction = Literal["EXPORTED", "CREATED", "UPDATED", "DELETED"]


class ReportsAuditService:
    """Records immutable audit entries for Reports actions."""

    def __init__(self, audit_repo: ReportsAuditRepository) -> None:
        self._repo = audit_repo

    def record(
        self,
        *,
        company_id: UUID,
        entity_type: AuditEntityType,
        entity_id: UUID,
        action: AuditAction,
        actor_id: UUID | None,
        before: JsonValue | None = None,
        after: JsonValue | None = None,
        report_key: str | None = None,
        filter_scope: JsonValue | None = None,
        export_format: str | None = None,
        row_count: int | None = None,
        reason: str | None = None,
    ) -> ReportsAuditLog:
        """Stage an audit record for insert. Caller MUST commit."""
        log = ReportsAuditLog(
            company_id=company_id,
            created_by=actor_id,
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            actor_id=actor_id,
            before=before,
            after=after,
            report_key=report_key,
            filter_scope=filter_scope,
            format=export_format,
            row_count=row_count,
            reason=reason,
        )
        return self._repo.create(log)
