"""UsageRepository — data access for `UsageRecord` (T150).

Write paths `flush()` only, never `commit()` (ADR-5) — the calling
service owns the transaction boundary.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from modules.platform_admin.models.usage_record import UsageRecord


class UsageRepository:
    """Data access for `usage_records`."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def get_for_period(
        self,
        *,
        company_id: UUID,
        metric_key: str,
        period_start: datetime,
        period_end: datetime,
    ) -> UsageRecord | None:
        """The current-period row for this company/metric, if it has
        been computed. Absence means "measurement unavailable", never
        implicit zero (FR-9A-062) — callers must not substitute a
        default value when this returns None."""
        stmt = select(UsageRecord).where(
            UsageRecord.company_id == company_id,
            UsageRecord.metric_key == metric_key,
            UsageRecord.period_start == period_start,
            UsageRecord.period_end == period_end,
        )
        return self.db.execute(stmt).scalars().one_or_none()

    def list_for_company(self, company_id: UUID) -> list[UsageRecord]:
        stmt = (
            select(UsageRecord)
            .where(UsageRecord.company_id == company_id)
            .order_by(UsageRecord.period_start.desc(), UsageRecord.metric_key)
        )
        return list(self.db.execute(stmt).scalars().all())

    def upsert(
        self,
        *,
        company_id: UUID,
        metric_key: str,
        quantity: Decimal,
        period_start: datetime,
        period_end: datetime,
        source: str,
        recorded_at: datetime,
    ) -> UsageRecord:
        """Create-or-update the usage row for this company/metric/period
        (idempotent per period, T151). Caller commits."""
        existing = self.get_for_period(
            company_id=company_id,
            metric_key=metric_key,
            period_start=period_start,
            period_end=period_end,
        )
        if existing is not None:
            existing.quantity = quantity
            existing.source = source
            existing.recorded_at = recorded_at
            self.db.flush()
            return existing

        record = UsageRecord(
            company_id=company_id,
            metric_key=metric_key,
            quantity=quantity,
            period_start=period_start,
            period_end=period_end,
            source=source,
            recorded_at=recorded_at,
        )
        self.db.add(record)
        self.db.flush()
        return record
