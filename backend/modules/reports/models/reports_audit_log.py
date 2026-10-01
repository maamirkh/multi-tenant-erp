"""ReportsAuditLog ORM model (spec §39, plan.md §22, data-model.md).

Module-local, append-only audit trail for reporting actions — every
export (``entity_type="ReportExport"``) and every saved-view
create/update/delete (``entity_type="SavedReportView"``). Ordinary report
and dashboard *views* are never written here (FR-RPT-301).

Follows the per-module audit-table convention (plan.md §2.8 — no shared
``core/`` audit model exists): no FK to any other table, and append-only
at the application layer (``ReportsAuditService.record()`` only ever
inserts). Inherits ``TenantBaseModel`` per tasks.md T178, so ``company_id``
tenant scoping is structural.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import Index, Integer, String, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from core.database.models.tenant_base import TenantBaseModel
from modules.reports.schemas.common import JsonValue


class ReportsAuditLog(TenantBaseModel):
    """Immutable audit record for one reporting action."""

    __tablename__ = "reports_audit_log"
    __table_args__ = (
        Index("ix_reports_audit_log_company_created_at", "company_id", "created_at"),
        Index("ix_reports_audit_log_company_actor", "company_id", "actor_id"),
        {"comment": "Append-only Reports & Analytics audit trail"},
    )

    entity_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        doc='"ReportExport" | "SavedReportView".',
    )

    entity_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        nullable=False,
        doc="The export event's own generated ID, or the SavedReportView.id.",
    )

    action: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        doc='"EXPORTED" | "CREATED" | "UPDATED" | "DELETED".',
    )

    actor_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)

    before: Mapped[JsonValue | None] = mapped_column(JSONB, nullable=True)

    after: Mapped[JsonValue | None] = mapped_column(JSONB, nullable=True)

    report_key: Mapped[str | None] = mapped_column(String(100), nullable=True)

    filter_scope: Mapped[JsonValue | None] = mapped_column(
        JSONB,
        nullable=True,
        doc="The exact validated filters an export applied.",
    )

    format: Mapped[str | None] = mapped_column(String(10), nullable=True)

    row_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
