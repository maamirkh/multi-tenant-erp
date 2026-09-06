"""AI ERP Readiness ORM model — Phase 17 (tasks.md T307).

``AccountingAnomalyFlag`` persists journal entries flagged as anomalous by
an (external, future) AI model via ``POST /accounting/ai/anomaly-report``.
Unlike ``AccountingAuditLog``/``JournalLine`` (append-only, no update path),
a flag is a mutable review record — ``status`` moves OPEN -> REVIEWED/
DISMISSED as a human follow-up investigates it — so this inherits
``TenantBaseModel`` (soft-delete + audit stamps), matching every other
mutable business record in this module, not the append-only ledger pattern.

Spec ref: specs/008-accounting-finance/spec.md §54.1 AI Financial Assistant
Tasks ref: specs/008-accounting-finance/tasks.md T307
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import ForeignKey, Text
from sqlalchemy import String as SAString
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from core.database.models.tenant_base import TenantBaseModel


class AccountingAnomalyFlag(TenantBaseModel):
    """One journal entry flagged as a potential anomaly, pending human review.

    ``created_by`` (inherited) records who/what raised the flag — a human
    user today; an AI service account once/if Phase 17's stub is wired to a
    real model. ``status`` defaults OPEN; this phase does not add a review
    workflow endpoint (out of scope — see tasks.md T307's stub-only scope).
    """

    __tablename__ = "accounting_anomaly_flags"
    __table_args__ = (
        {
            "comment": "AI-flagged journal entries pending human review (Phase 17 AI readiness stub)"
        },
    )

    journal_entry_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("accounting_journal_entries.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        SAString(20), server_default="OPEN", nullable=False
    )
