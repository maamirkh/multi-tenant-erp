"""`SupportAccessGrant` ORM model (T158).

Persistence for `support_access_grants` (migration 061, data-model.md
"Support Access"). Time-bounded, reason-required, inspection-only —
exactly one target tenant per grant (FR-9A-191); `expires_at` is NOT
NULL, there is no indefinite grant (FR-9A-193).

**State transitions**: `active` -> `expired` (lazy, checked at read time
when `expires_at < now()`) or `active` -> `terminated` (explicit action
by the initiator or another actor holding `platform.support_access.
initiate`). Both are terminal — enforced at the service layer
(`SupportAccessService`), not by a DB constraint (mirrors
`TenantLifecycleService`'s own state-machine precedent).
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from core.database.models.base_model import BaseModel


class SupportAccessGrant(BaseModel):
    """A Platform-initiated, time-bounded, reason-required support-access
    session scoped to exactly one tenant."""

    __tablename__ = "support_access_grants"
    __table_args__ = (
        Index("ix_support_access_grants_admin_id", "platform_administrator_id"),
        Index("ix_support_access_grants_company_id", "company_id"),
        CheckConstraint(
            "status IN ('active', 'expired', 'terminated')",
            name="ck_support_access_grants_status",
        ),
        CheckConstraint(
            "expires_at > started_at", name="ck_support_access_grants_expiry"
        ),
    )

    platform_administrator_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("platform_administrators.id"),
        nullable=False,
    )

    company_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("companies.id"), nullable=False
    )

    reason: Mapped[str] = mapped_column(Text, nullable=False)

    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        doc="No indefinite grant (FR-9A-193) — always required.",
    )

    ended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    ended_by: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("platform_administrators.id"), nullable=True
    )

    status: Mapped[str] = mapped_column(String(20), nullable=False)
