"""TenantDirectoryService — tenant directory listing, the 360° detail
aggregation, and lifecycle history (T167/T168/T169, FR-9A-010/020/021,
US-2/US-3).

Read-only throughout: composes existing repositories/services (Phase 7's
`CompanyRepository`, Phase 8's `SubscriptionRepository`/`PlanRepository`/
`QuotaRepository`/`QuotaService`, Phase 9's `PlatformEntitlementService`,
Phase 11's `OverrideService`/`UsageRepository`, Phase 6's
`PlatformAuditRepository`) — no new resolver, no duplicated logic.

**FR-9A-021 boundary**: this service imports no business-record
repository from any of the five modules — the same statically-provable
guarantee Phase 12 established for support access. The 360° view is
built entirely from Platform-owned and Company-identity data.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from modules.companies.models.company import Company
from modules.companies.repositories.company_repository import CompanyRepository
from modules.platform_admin.models.platform_audit_event import PlatformAuditEvent
from modules.platform_admin.repositories.capability_repository import (
    CapabilityRepository,
)
from modules.platform_admin.repositories.override_repository import OverrideRepository
from modules.platform_admin.repositories.plan_repository import PlanRepository
from modules.platform_admin.repositories.platform_audit_repository import (
    PlatformAuditRepository,
)
from modules.platform_admin.repositories.quota_repository import QuotaRepository
from modules.platform_admin.repositories.subscription_repository import (
    SubscriptionRepository,
)
from modules.platform_admin.repositories.usage_repository import UsageRepository
from modules.platform_admin.services.entitlement_service import (
    PlatformEntitlementService,
)
from modules.platform_admin.services.override_service import OverrideService
from modules.platform_admin.services.platform_audit_service import PlatformAuditService
from modules.platform_admin.services.quota_service import QuotaService
from modules.platform_admin.services.usage_service import current_month_period
from modules.users_roles.models.company_member import CompanyMember

_LIFECYCLE_ACTIONS = ("tenant_lifecycle.suspend", "tenant_lifecycle.reactivate")


class TenantDetail:
    """Plain aggregate carrying the 360° view's assembled data — the
    router maps this onto `TenantDetailResponse`."""

    def __init__(
        self,
        *,
        company: Company,
        plan: Any | None,
        subscription: Any | None,
        entitlements: list[Any],
        quotas: list[Any],
        user_count: int,
        lifecycle_history: list[PlatformAuditEvent],
        recent_audit_events: list[PlatformAuditEvent],
    ) -> None:
        self.company = company
        self.plan = plan
        self.subscription = subscription
        self.entitlements = entitlements
        self.quotas = quotas
        self.user_count = user_count
        self.lifecycle_history = lifecycle_history
        self.recent_audit_events = recent_audit_events


class TenantDirectoryService:
    """Domain service for tenant search/list/360°-detail/lifecycle-history."""

    def __init__(
        self,
        db: Session,
        company_repo: CompanyRepository,
        subscription_repo: SubscriptionRepository,
        plan_repo: PlanRepository,
        quota_repo: QuotaRepository,
        usage_repo: UsageRepository,
        capability_repo: CapabilityRepository,
        audit_repo: PlatformAuditRepository,
    ) -> None:
        self._db = db
        self._company_repo = company_repo
        self._subscription_repo = subscription_repo
        self._plan_repo = plan_repo
        self._quota_repo = quota_repo
        self._usage_repo = usage_repo
        self._capability_repo = capability_repo
        self._audit_repo = audit_repo

    def list_tenants(
        self,
        *,
        filters: dict[str, Any],
        page: int = 1,
        page_size: int = 25,
        sort_by: str = "created_at",
        sort_order: str = "desc",
    ) -> tuple[list[Company], int]:
        """Search/filter/sort/paginate across all `CompanyStatus` values
        (T167) — a bounded query (`page_size` enforced by the router's
        own `le=100` cap), never a "load all"."""
        return self._company_repo.list_all(
            filters=filters,
            page=page,
            page_size=page_size,
            sort_by=sort_by,
            sort_order=sort_order,
        )

    def get_lifecycle_history(
        self, company_id: UUID, *, limit: int = 50
    ) -> list[PlatformAuditEvent]:
        """Every status transition for a tenant, newest first (T169,
        FR-9A-016). `PlatformAuditRepository.list_filtered()` matches a
        single `action` exactly, so the two lifecycle actions are queried
        separately and merged — both bounded by `limit`, never unbounded."""
        events: list[PlatformAuditEvent] = []
        for action in _LIFECYCLE_ACTIONS:
            rows, _ = self._audit_repo.list_filtered(
                company_id=company_id, action=action, limit=limit
            )
            events.extend(rows)
        events.sort(key=lambda e: e.created_at, reverse=True)
        return events[:limit]

    def get_tenant_detail(self, company_id: UUID) -> TenantDetail | None:
        """The 360° administrative view (T168, FR-9A-020) — aggregate/
        summary data only, never a tenant business transaction record
        (FR-9A-021)."""
        company = self._company_repo.get_by_id(company_id)
        if company is None:
            return None

        subscription = self._subscription_repo.get_active_for_company(company_id)
        plan = (
            self._plan_repo.get_by_id(subscription.plan_id)
            if subscription is not None
            else None
        )

        override_service = OverrideService(
            db=self._db,
            repo=OverrideRepository(self._db),
            audit=PlatformAuditService(self._db, PlatformAuditRepository(self._db)),
        )
        entitlement_service = PlatformEntitlementService(
            db=self._db,
            plan_repo=self._plan_repo,
            subscription_repo=self._subscription_repo,
            override_checker=override_service,
        )
        entitlements = [
            entitlement_service.resolve_effective_entitlement(
                company_id=company_id, capability_key=capability.key
            )
            for capability in self._capability_repo.list_all(is_active=True)
        ]

        quota_service = QuotaService(self._quota_repo)
        period_start, period_end = current_month_period()
        quotas = []
        for definition in self._quota_repo.list_definitions():
            usage_record = self._usage_repo.get_for_period(
                company_id=company_id,
                metric_key=definition.key,
                period_start=period_start,
                period_end=period_end,
            )
            quotas.append(
                quota_service.resolve(
                    company_id=company_id,
                    plan_id=subscription.plan_id if subscription else None,
                    quota_key=definition.key,
                    current_usage=(
                        usage_record.quantity if usage_record is not None else None
                    ),
                )
            )

        user_count = self._db.execute(
            select(func.count())
            .select_from(CompanyMember)
            .where(
                CompanyMember.company_id == company_id,
                CompanyMember.status == "active",
            )
        ).scalar_one()

        lifecycle_history = self.get_lifecycle_history(company_id)
        recent_audit_events, _ = self._audit_repo.list_filtered(
            company_id=company_id, limit=20
        )

        return TenantDetail(
            company=company,
            plan=plan,
            subscription=subscription,
            entitlements=entitlements,
            quotas=quotas,
            user_count=user_count,
            lifecycle_history=lifecycle_history,
            recent_audit_events=recent_audit_events,
        )
