"""`EntitlementOverride` ORM model (T145).

Persistence for `entitlement_overrides` (migration 059, data-model.md
"Quotas & Overrides"). Deliberately not mapped alongside `TenantQuotaOverride`
in `models/quota.py` — Phase 8's own docstring there explicitly deferred
this model to Phase 9's entitlement resolver (T120's `OverrideChecker`
seam), whose real implementation is this phase's T146/T147.

`expires_at` NULL means permanent, explicitly distinguishable — never
implicit (data-model.md). "No duplicate active override" is enforced by
a PostgreSQL partial unique index on `(company_id, capability_key) WHERE
is_active = true` (migration 059), matching `TenantQuotaOverride`'s own
pattern exactly.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from core.database.models.base_model import BaseModel


class EntitlementOverride(BaseModel):
    """A Platform-granted, tenant-specific override of an entitlement
    ceiling — reason-bound, actor-attributed, optionally time-boxed."""

    __tablename__ = "entitlement_overrides"
    __table_args__ = (
        Index("ix_entitlement_overrides_company_id", "company_id"),
        CheckConstraint(
            "expires_at IS NULL OR expires_at > granted_at",
            name="ck_entitlement_overrides_expiry",
        ),
    )

    company_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("companies.id"), nullable=False
    )

    capability_key: Mapped[str] = mapped_column(
        String(50), ForeignKey("capabilities.key"), nullable=False
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
