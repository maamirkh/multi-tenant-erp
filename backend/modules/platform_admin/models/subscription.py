"""Subscription ORM model — a tenant's plan assignment, distinct from the
Plan definition itself (T106, BR-9A-014).

Persistence for `subscriptions` (migration 058, data-model.md
"Subscription"). `status` is deliberately limited to `active`/`ended` —
no `trial` (resolved OQ-1) — though the VARCHAR+CHECK column design means
adding it later needs only a CHECK-constraint update, not a migration
redesign. The one-active-subscription-per-company invariant is enforced
by a PostgreSQL partial unique index (`uq_subscriptions_company_active`,
migration 058) — not merely in application code (T116).
"""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from core.database.models.base_model import BaseModel


class Subscription(BaseModel):
    """A tenant's assignment to a `Plan`, with an effective date and an
    auditable actor/reason trail."""

    __tablename__ = "subscriptions"
    __table_args__ = (
        Index("ix_subscriptions_company_id", "company_id"),
        CheckConstraint(
            "status IN ('active', 'ended')", name="ck_subscriptions_status"
        ),
    )

    company_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("companies.id", ondelete="RESTRICT"),
        nullable=False,
    )

    plan_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("plans.id", ondelete="RESTRICT"),
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(20), nullable=False, doc="active | ended. No 'trial' (resolved OQ-1)."
    )

    effective_date: Mapped[date] = mapped_column(Date, nullable=False)

    ended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    actor_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("platform_administrators.id"),
        nullable=False,
    )

    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
