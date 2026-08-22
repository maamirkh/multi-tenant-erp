"""SupportAccessRepository — data access for `SupportAccessGrant` (T158).

Write paths `flush()` only, never `commit()` (ADR-5) — the calling
service owns the transaction boundary, matching every other Platform
repository in this module.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from modules.platform_admin.models.support_access_grant import SupportAccessGrant


class SupportAccessRepository:
    """Data access for `support_access_grants`."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, grant_id: UUID) -> SupportAccessGrant | None:
        return self.db.get(SupportAccessGrant, grant_id)

    def list_paginated(
        self, *, offset: int = 0, limit: int = 50
    ) -> tuple[list[SupportAccessGrant], int]:
        """Grant history, newest first (T162's `GET /support-access`)."""
        total = self.db.execute(
            select(func.count()).select_from(SupportAccessGrant)
        ).scalar_one()
        stmt = (
            select(SupportAccessGrant)
            .order_by(SupportAccessGrant.started_at.desc())
            .offset(offset)
            .limit(limit)
        )
        items = list(self.db.execute(stmt).scalars().all())
        return items, total

    def create_grant(
        self,
        *,
        platform_administrator_id: UUID,
        company_id: UUID,
        reason: str,
        started_at: datetime,
        expires_at: datetime,
    ) -> SupportAccessGrant:
        """Stage a new support-access grant. Caller commits."""
        grant = SupportAccessGrant(
            platform_administrator_id=platform_administrator_id,
            company_id=company_id,
            reason=reason,
            started_at=started_at,
            expires_at=expires_at,
            status="active",
        )
        self.db.add(grant)
        self.db.flush()
        return grant

    def mark_expired(self, grant: SupportAccessGrant) -> None:
        """Lazy transition: `active` -> `expired`. Never touches
        `ended_at`/`ended_by` — nothing "ended" it, time passed
        (distinguishes from an explicit `terminate()`). Caller commits."""
        grant.status = "expired"
        self.db.flush()

    def terminate(
        self, grant: SupportAccessGrant, *, ended_at: datetime, ended_by: UUID
    ) -> None:
        """Explicit transition: `active` -> `terminated`. Caller commits."""
        grant.status = "terminated"
        grant.ended_at = ended_at
        grant.ended_by = ended_by
        self.db.flush()
