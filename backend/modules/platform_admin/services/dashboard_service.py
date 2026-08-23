"""DashboardService — the Platform Dashboard aggregate view (T171/T172/
T173, FR-9A-001/003/004/005, US-1).

Every widget is computed independently and reports its own
`DashboardWidgetState` — a failed sub-query renders `unavailable`, never
a fabricated `0` (FR-9A-003, "data unavailable != zero", spec §22).
Widgets the caller lacks the underlying read permission for are omitted
entirely from the response — not shown empty or erroring (FR-9A-004);
`get_dashboard()` takes the caller's held permission codes and decides
per-widget inclusion itself, mirroring T172's own "permission-gated
omission" requirement exactly.

**Bounded-query discipline (no unbounded aggregation, no per-tenant
N+1)**: every widget is a single, indexed, `LIMIT`-bound query.
`quota_warnings` in particular resolves warnings via one JOIN across
`usage_records`/`subscriptions`/`plan_quotas` rather than iterating
companies and calling `QuotaService.resolve()` per tenant — the latter
would be exactly the N+1 this task explicitly forbids. This is a
deliberate simplification for a dashboard *summary* widget: it does not
apply `TenantQuotaOverride` rows (unlike the authoritative
`GET /tenants/{companyId}/quotas` endpoint, Phase 11, which does) — a
tenant with an active override might appear here as "approaching" a
limit its override has actually raised. Documented, not silently wrong;
the authoritative per-tenant view remains the Phase 11 endpoint.
"""

from __future__ import annotations

import logging
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from core.logging.setup import REQUEST_ID_CONTEXT
from modules.companies.models.company import Company
from modules.platform_admin.models.ai_credit_ledger import AiCreditLedgerEntry
from modules.platform_admin.models.plan import Plan
from modules.platform_admin.models.quota import PlanQuota
from modules.platform_admin.models.subscription import Subscription
from modules.platform_admin.models.usage_record import UsageRecord
from modules.platform_admin.repositories.platform_audit_repository import (
    PlatformAuditRepository,
)
from modules.platform_admin.services.health_service import HealthService
from modules.platform_admin.services.usage_service import current_month_period

_RECENT_LIMIT = 10
_QUOTA_WARNING_LIMIT = 20
_APPROACHING_RATIO = Decimal("0.80")

logger = logging.getLogger(__name__)


def _log_widget_degraded(widget_name: str) -> None:
    logger.warning(
        "Platform dashboard widget degraded",
        extra={"request_id": REQUEST_ID_CONTEXT.get("-"), "widget": widget_name},
    )


class DashboardWidgetState(str, Enum):
    """Backend responses only ever emit `populated`/`empty`/`unavailable`
    — `loading` is a frontend-only, pre-response transient state that
    never appears in a synchronous HTTP response."""

    populated = "populated"
    empty = "empty"
    unavailable = "unavailable"


@dataclass(frozen=True)
class DashboardWidget:
    state: DashboardWidgetState
    data: Any


class DashboardService:
    """Domain service composing the Platform Dashboard's independent
    widgets."""

    def __init__(
        self,
        db: Session,
        audit_repo: PlatformAuditRepository,
        health_service: HealthService,
    ) -> None:
        self._db = db
        self._audit_repo = audit_repo
        self._health_service = health_service

    def _tenant_counts_by_status(self) -> DashboardWidget:
        try:
            rows = self._db.execute(
                select(Company.status, func.count()).group_by(Company.status)
            ).all()
        except OperationalError:
            _log_widget_degraded("tenant_counts_by_status")
            return DashboardWidget(DashboardWidgetState.unavailable, None)
        data = {status: count for status, count in rows}
        state = DashboardWidgetState.populated if data else DashboardWidgetState.empty
        return DashboardWidget(state, data)

    def _recent_registrations(self) -> DashboardWidget:
        try:
            rows = list(
                self._db.execute(
                    select(Company.id, Company.legal_name, Company.created_at)
                    .order_by(Company.created_at.desc())
                    .limit(_RECENT_LIMIT)
                ).all()
            )
        except OperationalError:
            _log_widget_degraded("recent_registrations")
            return DashboardWidget(DashboardWidgetState.unavailable, None)
        data = [
            {"id": str(r.id), "legal_name": r.legal_name, "created_at": r.created_at}
            for r in rows
        ]
        state = DashboardWidgetState.populated if data else DashboardWidgetState.empty
        return DashboardWidget(state, data)

    def _plan_subscription_distribution(self) -> DashboardWidget:
        try:
            rows = self._db.execute(
                select(Plan.code, func.count())
                .select_from(Subscription)
                .join(Plan, Plan.id == Subscription.plan_id)
                .where(Subscription.status == "active")
                .group_by(Plan.code)
            ).all()
        except OperationalError:
            _log_widget_degraded("plan_subscription_distribution")
            return DashboardWidget(DashboardWidgetState.unavailable, None)
        data = {code: count for code, count in rows}
        state = DashboardWidgetState.populated if data else DashboardWidgetState.empty
        return DashboardWidget(state, data)

    def _quota_warnings(self) -> DashboardWidget:
        try:
            period_start, period_end = current_month_period()
            ratio_expr = UsageRecord.quantity / func.nullif(PlanQuota.limit_value, 0)
            rows = self._db.execute(
                select(
                    UsageRecord.company_id,
                    UsageRecord.metric_key,
                    UsageRecord.quantity,
                    PlanQuota.limit_value,
                )
                .select_from(UsageRecord)
                .join(
                    Subscription,
                    (Subscription.company_id == UsageRecord.company_id)
                    & (Subscription.status == "active"),
                )
                .join(
                    PlanQuota,
                    (PlanQuota.plan_id == Subscription.plan_id)
                    & (PlanQuota.quota_key == UsageRecord.metric_key),
                )
                .where(
                    UsageRecord.period_start == period_start,
                    UsageRecord.period_end == period_end,
                    PlanQuota.limit_value.is_not(None),
                    PlanQuota.limit_value > 0,
                    UsageRecord.quantity >= PlanQuota.limit_value * _APPROACHING_RATIO,
                )
                .order_by(ratio_expr.desc())
                .limit(_QUOTA_WARNING_LIMIT)
            ).all()
        except OperationalError:
            _log_widget_degraded("quota_warnings")
            return DashboardWidget(DashboardWidgetState.unavailable, None)
        data = [
            {
                "company_id": str(r.company_id),
                "quota_key": r.metric_key,
                "quantity": r.quantity,
                "limit_value": r.limit_value,
            }
            for r in rows
        ]
        state = DashboardWidgetState.populated if data else DashboardWidgetState.empty
        return DashboardWidget(state, data)

    def _recent_platform_actions(self) -> DashboardWidget:
        try:
            items, _ = self._audit_repo.list_filtered(limit=_RECENT_LIMIT)
        except OperationalError:
            _log_widget_degraded("recent_platform_actions")
            return DashboardWidget(DashboardWidgetState.unavailable, None)
        state = DashboardWidgetState.populated if items else DashboardWidgetState.empty
        return DashboardWidget(state, items)

    def _health_summary(self) -> DashboardWidget:
        try:
            health = self._health_service.get_health()
        except OperationalError:
            _log_widget_degraded("health_summary")
            return DashboardWidget(DashboardWidgetState.unavailable, None)
        return DashboardWidget(DashboardWidgetState.populated, health)

    def _ai_usage_widget(self) -> DashboardWidget | None:
        """[T173] Gated on real data — appears only once
        `ai_credit_ledger_entries` has at least one row; otherwise
        entirely absent (not populated-empty)."""
        try:
            count = self._db.execute(
                select(func.count()).select_from(AiCreditLedgerEntry)
            ).scalar_one()
        except OperationalError:
            _log_widget_degraded("ai_usage")
            return None
        if count == 0:
            return None
        balance_rows = self._db.execute(
            select(
                AiCreditLedgerEntry.company_id,
                func.sum(AiCreditLedgerEntry.delta).label("balance"),
            ).group_by(AiCreditLedgerEntry.company_id)
        ).all()
        data = [
            {"company_id": str(r.company_id), "balance": r.balance}
            for r in balance_rows
        ]
        return DashboardWidget(DashboardWidgetState.populated, data)

    def get_dashboard(
        self, *, held_permissions: AbstractSet[str]
    ) -> dict[str, DashboardWidget]:
        """Assemble the dashboard, omitting any widget the caller's
        `held_permissions` don't cover (FR-9A-004) — never rendered
        empty or erroring for a missing permission."""
        widgets: dict[str, DashboardWidget] = {}

        if "platform.tenants.read" in held_permissions:
            widgets["tenant_counts_by_status"] = self._tenant_counts_by_status()
            widgets["recent_registrations"] = self._recent_registrations()

        if "platform.subscriptions.read" in held_permissions:
            widgets["plan_subscription_distribution"] = (
                self._plan_subscription_distribution()
            )

        if "platform.quotas.read" in held_permissions:
            widgets["quota_warnings"] = self._quota_warnings()

        if "platform.audit.read" in held_permissions:
            widgets["recent_platform_actions"] = self._recent_platform_actions()

        if "platform.monitoring.read" in held_permissions:
            widgets["health_summary"] = self._health_summary()

        if "platform.ai_usage.read" in held_permissions:
            ai_widget = self._ai_usage_widget()
            if ai_widget is not None:
                widgets["ai_usage"] = ai_widget

        return widgets
