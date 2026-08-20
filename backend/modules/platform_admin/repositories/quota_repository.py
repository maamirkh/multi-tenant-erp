"""QuotaRepository — data access for `QuotaDefinition`, `PlanQuota`,
`TenantQuotaOverride` (T107).

Deliberately does **not** inherit `BaseRepository` (mandates `company_id`
filtering on every method — wrong for `QuotaDefinition`/`PlanQuota`,
which are platform-scoped, not tenant-scoped; `TenantQuotaOverride` is
company-scoped per-row but this repository serves both). Write paths
`flush()` only, never `commit()` (ADR-5) — the calling service owns the
transaction boundary, matching every other Platform repository in this
module.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from modules.platform_admin.models.quota import (
    PlanQuota,
    QuotaDefinition,
    TenantQuotaOverride,
)


class QuotaRepository:
    """Data access for the quota foundation tables."""

    def __init__(self, db: Session) -> None:
        self.db = db

    # ------------------------------------------------------------------
    # QuotaDefinition (catalogue)
    # ------------------------------------------------------------------

    def list_definitions(self) -> list[QuotaDefinition]:
        stmt = select(QuotaDefinition).order_by(QuotaDefinition.key)
        return list(self.db.execute(stmt).scalars().all())

    def get_definition(self, key: str) -> QuotaDefinition | None:
        return self.db.get(QuotaDefinition, key)

    def create_definition(
        self, *, key: str, display_name: str, unit: str, enforcement_style: str
    ) -> QuotaDefinition:
        """Stage a new quota category. Caller commits."""
        definition = QuotaDefinition(
            key=key,
            display_name=display_name,
            unit=unit,
            enforcement_style=enforcement_style,
        )
        self.db.add(definition)
        self.db.flush()
        return definition

    # ------------------------------------------------------------------
    # PlanQuota
    # ------------------------------------------------------------------

    def get_plan_quota(self, plan_id: UUID, quota_key: str) -> PlanQuota | None:
        stmt = select(PlanQuota).where(
            PlanQuota.plan_id == plan_id, PlanQuota.quota_key == quota_key
        )
        return self.db.execute(stmt).scalars().one_or_none()

    def list_plan_quotas(self, plan_id: UUID) -> list[PlanQuota]:
        stmt = select(PlanQuota).where(PlanQuota.plan_id == plan_id)
        return list(self.db.execute(stmt).scalars().all())

    def set_plan_quota(
        self, plan_id: UUID, quota_key: str, limit_value: Decimal | None
    ) -> PlanQuota:
        """Create-or-update the quota ceiling a Plan grants for a given
        key. NULL `limit_value` means unlimited (FR-9A-182). Caller
        commits."""
        existing = self.get_plan_quota(plan_id, quota_key)
        if existing is not None:
            existing.limit_value = limit_value
            self.db.flush()
            return existing
        plan_quota = PlanQuota(
            plan_id=plan_id, quota_key=quota_key, limit_value=limit_value
        )
        self.db.add(plan_quota)
        self.db.flush()
        return plan_quota

    # ------------------------------------------------------------------
    # TenantQuotaOverride
    # ------------------------------------------------------------------

    def get_active_override(
        self, company_id: UUID, quota_key: str
    ) -> TenantQuotaOverride | None:
        stmt = select(TenantQuotaOverride).where(
            TenantQuotaOverride.company_id == company_id,
            TenantQuotaOverride.quota_key == quota_key,
            TenantQuotaOverride.is_active == True,  # noqa: E712
        )
        return self.db.execute(stmt).scalars().one_or_none()

    def create_override(
        self,
        *,
        company_id: UUID,
        quota_key: str,
        override_limit: Decimal | None,
        reason: str,
        actor_id: UUID,
        granted_at: datetime,
        expires_at: datetime | None = None,
    ) -> TenantQuotaOverride:
        """Stage a new tenant quota override. Caller commits."""
        override = TenantQuotaOverride(
            company_id=company_id,
            quota_key=quota_key,
            override_limit=override_limit,
            reason=reason,
            actor_id=actor_id,
            granted_at=granted_at,
            expires_at=expires_at,
        )
        self.db.add(override)
        self.db.flush()
        return override
