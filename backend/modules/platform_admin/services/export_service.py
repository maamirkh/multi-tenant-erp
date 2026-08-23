"""ExportService — platform export (T176, FR-9A-120/121, US-1).

**No HTTP route** — the finalized OpenAPI contract
(`contracts/platform-admin-v1.yaml`, "28 paths / 33 operations", verified
by a full re-read) declares no `/export` path at all. `platform.tenants.
export`/`platform.export.generate` exist in the Phase 5 permission
catalogue (anticipating this capability) but were never wired to a
route — inventing one here would violate plan.md §10's API Contract Lock
and would make T177's contract-conformance test fail by design (an
implemented-but-undeclared route). This mirrors Phase 11's T149
(`QuotaAdminService.revoke()`) and Phase 12's T161 (`SupportAccessService
.record_action()`): a genuine, permission-checked service capability
with no corresponding HTTP surface, proven directly by its own tests.

**Scope** (FR-9A-120/121): exports are scoped to exactly what the
caller's permissions already allow them to view online — the same
principle T172 applies to dashboard widgets, here applied to export
availability instead of a UI element. **Never** includes a tenant
business transaction record; this service imports no business-record
repository from any of the five modules, the same statically-provable
guarantee Phase 12 established for support access.

Each export is a single bounded query (`_EXPORT_ROW_CAP`) — a genuine
export is a bulk operation by nature, but "bounded" still means a hard
safety cap, never a literal unbounded `SELECT *`.
"""

from __future__ import annotations

from collections.abc import Set as AbstractSet
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from modules.companies.repositories.company_repository import CompanyRepository
from modules.platform_admin.exceptions import InsufficientPlatformPermissionError
from modules.platform_admin.models.plan import Plan
from modules.platform_admin.models.subscription import Subscription
from modules.platform_admin.models.usage_record import UsageRecord
from modules.platform_admin.repositories.platform_audit_repository import (
    PlatformAuditRepository,
)
from modules.platform_admin.repositories.usage_repository import UsageRepository
from modules.platform_admin.services.usage_service import current_month_period

_EXPORT_ROW_CAP = 5000


def _require_any(held_permissions: AbstractSet[str], *codes: str) -> None:
    if not any(code in held_permissions for code in codes):
        raise InsufficientPlatformPermissionError(
            message=(
                "Export requires one of the following permissions: " + ", ".join(codes)
            )
        )


class ExportService:
    """Domain service for bounded, permission-scoped platform exports.
    Service-level only — no router wires this (see module docstring)."""

    def __init__(
        self,
        db: Session,
        company_repo: CompanyRepository,
        usage_repo: UsageRepository,
        audit_repo: PlatformAuditRepository,
    ) -> None:
        self._db = db
        self._company_repo = company_repo
        self._usage_repo = usage_repo
        self._audit_repo = audit_repo

    def export_tenant_directory(
        self, *, held_permissions: AbstractSet[str]
    ) -> list[dict[str, Any]]:
        _require_any(
            held_permissions, "platform.tenants.read", "platform.tenants.export"
        )
        items, _ = self._company_repo.list_all(
            filters={"include_deleted": True}, page=1, page_size=_EXPORT_ROW_CAP
        )
        return [
            {
                "id": str(c.id),
                "legal_name": c.legal_name,
                "slug": c.slug,
                "status": c.status,
                "country": c.country,
                "email": c.email,
                "created_at": c.created_at.isoformat(),
            }
            for c in items
        ]

    def export_subscription_summary(
        self, *, held_permissions: AbstractSet[str]
    ) -> list[dict[str, Any]]:
        _require_any(held_permissions, "platform.subscriptions.read")
        rows = self._db.execute(
            select(
                Subscription.company_id,
                Subscription.status,
                Subscription.effective_date,
                Plan.code,
            )
            .join(Plan, Plan.id == Subscription.plan_id)
            .limit(_EXPORT_ROW_CAP)
        ).all()
        return [
            {
                "company_id": str(r.company_id),
                "status": r.status,
                "effective_date": r.effective_date.isoformat(),
                "plan_code": r.code,
            }
            for r in rows
        ]

    def export_usage_summary(
        self, *, held_permissions: AbstractSet[str]
    ) -> list[dict[str, Any]]:
        _require_any(held_permissions, "platform.quotas.read")
        period_start, period_end = current_month_period()

        rows = (
            self._db.execute(
                select(UsageRecord)
                .where(
                    UsageRecord.period_start == period_start,
                    UsageRecord.period_end == period_end,
                )
                .limit(_EXPORT_ROW_CAP)
            )
            .scalars()
            .all()
        )
        return [
            {
                "company_id": str(r.company_id),
                "metric_key": r.metric_key,
                "quantity": str(r.quantity),
                "period_start": r.period_start.isoformat(),
                "period_end": r.period_end.isoformat(),
            }
            for r in rows
        ]

    def export_audit_data(
        self, *, held_permissions: AbstractSet[str]
    ) -> list[dict[str, Any]]:
        _require_any(held_permissions, "platform.audit.read")
        items, _ = self._audit_repo.list_filtered(limit=_EXPORT_ROW_CAP)
        return [
            {
                "id": str(e.id),
                "action": e.action,
                "actor_platform_administrator_id": (
                    str(e.actor_platform_administrator_id)
                    if e.actor_platform_administrator_id
                    else None
                ),
                "company_id": str(e.company_id) if e.company_id else None,
                "target_type": e.target_type,
                "reason": e.reason,
                "created_at": e.created_at.isoformat(),
            }
            for e in items
        ]
