"""UsageService — periodic/batch usage computation (T151, FR-9A-060).

Not per-event streaming (plan.md §18) — a manually-triggerable batch
that upserts one `UsageRecord` row per (company, metric, period).
Idempotent per period: `UsageRepository.upsert()` create-or-updates the
existing row for the same `(company_id, metric_key, period_start,
period_end)` rather than inserting a duplicate, so re-running for a
period already computed converges instead of accumulating rows.

**Metric-source scope note (mirrors `SubscriptionService`'s own
documented boundary, T112)**: the only quota category with a genuine
live source available anywhere in the codebase today is `users`,
counted from `CompanyMember` — exactly the source `SubscriptionService.
_current_live_usage()` already uses for its downgrade-conflict check.
The other quota categories seeded by `RolloutService` (`branches`,
`transactions`, `storage`, `api_calls`, `ai_credits`) have no live
source in this phase; this service does not fabricate one. No
`UsageRecord` is written for them — which is precisely what makes
`QuotaService.resolve()` correctly report `unavailable` for those keys
(T152) rather than an invented zero.

No HTTP route triggers this — the OpenAPI contract's only Phase-11
`/tenants/{companyId}/usage` operation is a read-only `GET` of already-
computed rows (T157); "manually triggerable" means an operator/test can
call this service directly, not that a new endpoint was invented.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from modules.companies.models.company import Company
from modules.companies.models.enums import CompanyStatus
from modules.platform_admin.models.usage_record import UsageRecord
from modules.platform_admin.repositories.usage_repository import UsageRepository
from modules.users_roles.models.company_member import CompanyMember

_LIVE_MEASURABLE_METRIC_KEY = "users"
_SOURCE_LABEL = "live_count"


def current_month_period(now: datetime | None = None) -> tuple[datetime, datetime]:
    """The current calendar-month UTC period bucket:
    [first-of-month 00:00, first-of-next-month 00:00)."""
    reference = now if now is not None else datetime.now(UTC)
    period_start = reference.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if period_start.month == 12:
        period_end = period_start.replace(year=period_start.year + 1, month=1)
    else:
        period_end = period_start.replace(month=period_start.month + 1)
    return period_start, period_end


class UsageService:
    """Domain service computing periodic `UsageRecord` rows."""

    def __init__(self, db: Session, usage_repo: UsageRepository) -> None:
        self._db = db
        self._repo = usage_repo

    def _live_users_count(self, company_id: UUID) -> Decimal:
        count = self._db.execute(
            select(func.count())
            .select_from(CompanyMember)
            .where(
                CompanyMember.company_id == company_id,
                CompanyMember.status == "active",
            )
        ).scalar_one()
        return Decimal(count)

    def compute_for_company(
        self,
        *,
        company_id: UUID,
        period_start: datetime,
        period_end: datetime,
    ) -> list[UsageRecord]:
        """Compute and upsert this period's usage rows for one tenant.
        Idempotent — safe to re-run for the same period. Single commit."""
        quantity = self._live_users_count(company_id)
        record = self._repo.upsert(
            company_id=company_id,
            metric_key=_LIVE_MEASURABLE_METRIC_KEY,
            quantity=quantity,
            period_start=period_start,
            period_end=period_end,
            source=_SOURCE_LABEL,
            recorded_at=datetime.now(UTC),
        )
        self._db.commit()
        return [record]

    def compute_for_all_companies(
        self,
        *,
        period_start: datetime,
        period_end: datetime,
    ) -> int:
        """Batch-compute this period's usage for every non-deleted
        company. Returns the number of companies processed."""
        companies = (
            self._db.execute(
                select(Company).where(Company.status != CompanyStatus.deleted.value)
            )
            .scalars()
            .all()
        )
        for company in companies:
            self.compute_for_company(
                company_id=company.id,
                period_start=period_start,
                period_end=period_end,
            )
        return len(companies)
