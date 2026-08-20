"""SubscriptionRepository — data access for `Subscription`, a tenant's
plan assignment (T110, BR-9A-014).

Deliberately does **not** inherit `BaseRepository`. Write paths
`flush()` only, never `commit()` (ADR-5) — `SubscriptionService` (T112)
owns the transaction boundary alongside its audit row and the
`companies.subscription_id` pointer sync. The one-active-subscription-
per-company invariant is enforced by a real PostgreSQL partial unique
index (migration 058) — not by this repository (T116).
"""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from modules.platform_admin.models.subscription import Subscription


class SubscriptionRepository:
    """Data access for the `subscriptions` table."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, subscription_id: UUID) -> Subscription | None:
        return self.db.get(Subscription, subscription_id)

    def get_active_for_company(self, company_id: UUID) -> Subscription | None:
        stmt = select(Subscription).where(
            Subscription.company_id == company_id, Subscription.status == "active"
        )
        return self.db.execute(stmt).scalars().one_or_none()

    def list_for_company(self, company_id: UUID) -> list[Subscription]:
        """Full history, newest first."""
        stmt = (
            select(Subscription)
            .where(Subscription.company_id == company_id)
            .order_by(Subscription.created_at.desc())
        )
        return list(self.db.execute(stmt).scalars().all())

    def create(
        self,
        *,
        company_id: UUID,
        plan_id: UUID,
        status: str,
        effective_date: date,
        actor_id: UUID,
        reason: str | None = None,
    ) -> Subscription:
        """Stage a new Subscription. Caller commits."""
        subscription = Subscription(
            company_id=company_id,
            plan_id=plan_id,
            status=status,
            effective_date=effective_date,
            actor_id=actor_id,
            reason=reason,
        )
        self.db.add(subscription)
        self.db.flush()
        return subscription

    def end(self, subscription: Subscription, *, ended_at: datetime) -> Subscription:
        """Stage a Subscription as ended. Caller commits."""
        subscription.status = "ended"
        subscription.ended_at = ended_at
        self.db.flush()
        return subscription
