"""`UsageRecord` ORM model (T150).

Persistence for `usage_records` (migration 060, data-model.md "Usage &
AI Readiness"). Periodic/batch rows, not per-event streaming (plan.md
§18) — one row per (company, metric, period). Absence of a current-period
row is treated as `unavailable` by `QuotaService.resolve()`, never
silently zero (FR-9A-062, T152).
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Index, Numeric, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from core.database.models.base_model import BaseModel


class UsageRecord(BaseModel):
    """One periodic/batch usage measurement for a tenant/metric/period."""

    __tablename__ = "usage_records"
    __table_args__ = (Index("ix_usage_records_company_id", "company_id"),)

    company_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("companies.id"), nullable=False
    )

    metric_key: Mapped[str] = mapped_column(
        String(50), ForeignKey("quota_definitions.key"), nullable=False
    )

    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)

    period_start: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    period_end: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    source: Mapped[str] = mapped_column(
        String(100), nullable=False, doc="Which computation produced this row."
    )

    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
