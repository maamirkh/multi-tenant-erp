"""`AiCreditLedgerEntry` ORM model (T154, BR-9A-026).

Persistence for `ai_credit_ledger_entries` (migration 060, data-model.md
"Usage & AI Readiness"). Signed `delta` — positive = credit grant,
negative = usage debit; current balance per company = `SUM(delta)`.
`provider`/`model` are free-text/nullable — never structurally coupled to
a vendor (FR-9A-234); no AI provider is integrated by this phase or any
other part of Epic 9A. Empty table until an AI capability epic exists
(§19) — no zero-value placeholder rows.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Index, Integer, Numeric, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from core.database.models.base_model import BaseModel


class AiCreditLedgerEntry(BaseModel):
    """One signed ledger entry against a tenant's AI credit balance."""

    __tablename__ = "ai_credit_ledger_entries"
    __table_args__ = (Index("ix_ai_credit_ledger_entries_company_id", "company_id"),)

    company_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("companies.id"), nullable=False
    )

    delta: Mapped[Decimal] = mapped_column(
        Numeric(18, 4),
        nullable=False,
        doc="Signed — positive = credit grant, negative = usage debit.",
    )

    reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        doc="Required (enforced in service) when actor_platform_administrator_id "
        "is populated.",
    )

    actor_platform_administrator_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("platform_administrators.id"),
        nullable=True,
        doc="Null = future automatic usage debit; populated = manual admin "
        "adjustment (FR-9A-233).",
    )

    platform_audit_event_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("platform_audit_events.id"),
        nullable=True,
        doc="Links manual adjustments to their audit record (BR-9A-027).",
    )

    provider: Mapped[str | None] = mapped_column(String(100), nullable=True)

    model: Mapped[str | None] = mapped_column(String(100), nullable=True)

    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)

    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)

    total_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)

    estimated_cost: Mapped[Decimal | None] = mapped_column(
        Numeric(18, 6), nullable=True
    )

    billable_cost: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)

    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
