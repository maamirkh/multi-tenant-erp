"""OverrideRepository — data access for `EntitlementOverride` (T145).

Write paths `flush()` only, never `commit()` (ADR-5) — the calling
service owns the transaction boundary, matching `QuotaRepository` and
every other Platform repository in this module.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from modules.platform_admin.models.entitlement_override import EntitlementOverride


class OverrideRepository:
    """Data access for `entitlement_overrides`."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def get_active_override(
        self, company_id: UUID, capability_key: str
    ) -> EntitlementOverride | None:
        stmt = select(EntitlementOverride).where(
            EntitlementOverride.company_id == company_id,
            EntitlementOverride.capability_key == capability_key,
            EntitlementOverride.is_active == True,  # noqa: E712
        )
        return self.db.execute(stmt).scalars().one_or_none()

    def get_by_id(self, override_id: UUID) -> EntitlementOverride | None:
        return self.db.get(EntitlementOverride, override_id)

    def create_override(
        self,
        *,
        company_id: UUID,
        capability_key: str,
        reason: str,
        actor_id: UUID,
        granted_at: datetime,
        expires_at: datetime | None = None,
    ) -> EntitlementOverride:
        """Stage a new entitlement override. Caller commits."""
        override = EntitlementOverride(
            company_id=company_id,
            capability_key=capability_key,
            reason=reason,
            actor_id=actor_id,
            granted_at=granted_at,
            expires_at=expires_at,
        )
        self.db.add(override)
        self.db.flush()
        return override

    def revoke(self, override: EntitlementOverride, *, revoked_at: datetime) -> None:
        """Mark an override inactive in place. Caller commits."""
        override.is_active = False
        override.revoked_at = revoked_at
        self.db.flush()
