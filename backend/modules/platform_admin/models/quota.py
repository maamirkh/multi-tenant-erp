"""Quota foundation ORM models — `QuotaDefinition`, `PlanQuota`,
`TenantQuotaOverride` (T107).

Persistence for `quota_definitions`, `plan_quotas`, `tenant_quota_overrides`
(migration 059, data-model.md "Quotas & Overrides"). Generic key-based
registry — no per-quota-type column anywhere; adding a future quota
category needs one `QuotaDefinition` row, no schema change.

`PlanQuota.limit_value`/`TenantQuotaOverride.override_limit` are nullable
where **NULL means unlimited** (FR-9A-182) — never a large sentinel
number. `enforcement_style` is declared explicitly per quota category,
never defaulted silently (BR-9A-030).

`EntitlementOverride` (also in migration 059) is deliberately NOT mapped
here — it belongs to Phase 9's entitlement resolver, out of this phase's
scope.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from core.database.base import Base
from core.database.models.base_model import BaseModel


class QuotaDefinition(Base):
    """Quota category catalogue entry — e.g. `"users"`, `"branches"`,
    `"transactions"`, `"storage"`, `"api_calls"`, `"ai_credits"`."""

    __tablename__ = "quota_definitions"
    __table_args__ = (
        CheckConstraint(
            "enforcement_style IN ('hard', 'soft', 'informational')",
            name="ck_quota_definitions_enforcement_style",
        ),
    )

    key: Mapped[str] = mapped_column(
        String(50), primary_key=True, doc="e.g. 'users'. Also the primary key."
    )

    display_name: Mapped[str] = mapped_column(String(150), nullable=False)

    unit: Mapped[str] = mapped_column(String(50), nullable=False)

    enforcement_style: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        doc="hard | soft | informational (BR-9A-030) — declared "
        "explicitly, never defaults silently.",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class PlanQuota(BaseModel):
    """The quota ceiling a `Plan` grants for a given `QuotaDefinition`
    key. NULL `limit_value` means unlimited (FR-9A-182)."""

    __tablename__ = "plan_quotas"
    __table_args__ = (
        Index("uq_plan_quotas_plan_quota", "plan_id", "quota_key", unique=True),
        CheckConstraint(
            "limit_value IS NULL OR limit_value >= 0",
            name="ck_plan_quotas_limit_value",
        ),
    )

    plan_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("plans.id", ondelete="CASCADE"), nullable=False
    )

    quota_key: Mapped[str] = mapped_column(
        String(50),
        ForeignKey("quota_definitions.key", ondelete="RESTRICT"),
        nullable=False,
    )

    limit_value: Mapped[Decimal | None] = mapped_column(
        Numeric(18, 2),
        nullable=True,
        doc="NULL means unlimited (FR-9A-182) — never a large sentinel.",
    )


class TenantQuotaOverride(BaseModel):
    """A Platform-granted, tenant-specific override of a quota limit —
    reason-bound, actor-attributed, optionally time-boxed."""

    __tablename__ = "tenant_quota_overrides"
    __table_args__ = (
        Index("ix_tenant_quota_overrides_company_id", "company_id"),
        CheckConstraint(
            "override_limit IS NULL OR override_limit >= 0",
            name="ck_tenant_quota_overrides_override_limit",
        ),
        CheckConstraint(
            "expires_at IS NULL OR expires_at > granted_at",
            name="ck_tenant_quota_overrides_expiry",
        ),
    )

    company_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("companies.id"), nullable=False
    )

    quota_key: Mapped[str] = mapped_column(
        String(50), ForeignKey("quota_definitions.key"), nullable=False
    )

    override_limit: Mapped[Decimal | None] = mapped_column(
        Numeric(18, 2), nullable=True, doc="NULL means unlimited override."
    )

    reason: Mapped[str] = mapped_column(Text, nullable=False)

    actor_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("platform_administrators.id"), nullable=False
    )

    granted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        doc="NULL = permanent, explicitly distinguishable (not implicit).",
    )

    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
