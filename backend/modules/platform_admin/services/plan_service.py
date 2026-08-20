"""PlanService — create/update/publish/retire a `Plan` (T111, BR-9A-018).

Fail-closed atomicity (ADR-5): every write stages its state change
(flush-only, `PlanRepository`) and its audit row (flush-only,
`PlatformAuditService`), then performs a single service-level
`db.commit()`.

Retiring a Plan blocks only **new** assignments — it never touches
existing `Subscription` rows, so tenants already on a retired plan keep
their entitlements completely unchanged until an explicit subscription
change is made for them individually (BR-9A-018, FR-9A-152).
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from modules.platform_admin.exceptions import PlanTransitionError
from modules.platform_admin.models.plan import Plan
from modules.platform_admin.repositories.plan_repository import PlanRepository
from modules.platform_admin.services.platform_audit_service import PlatformAuditService

_STATUS_DRAFT = "draft"
_STATUS_PUBLISHED = "published"
_STATUS_RETIRED = "retired"


def _plan_snapshot(plan: Plan, capability_map: dict[str, bool]) -> dict[str, Any]:
    return {
        "code": plan.code,
        "name": plan.name,
        "status": plan.status,
        "is_commercially_available": plan.is_commercially_available,
        "capability_map": capability_map,
    }


class PlanService:
    """Domain service for Plan lifecycle."""

    def __init__(
        self, db: Session, repo: PlanRepository, audit: PlatformAuditService
    ) -> None:
        self._db = db
        self._repo = repo
        self._audit = audit

    def create(
        self,
        *,
        code: str,
        name: str,
        description: str | None = None,
        billing_cycle_metadata: dict[str, Any] | None = None,
        pricing_metadata: dict[str, Any] | None = None,
        capability_map: dict[str, bool] | None = None,
        actor_platform_administrator_id: UUID,
        reason: str | None = None,
    ) -> Plan:
        """Create a new Plan, always starting as `draft` (per the
        contract: "Create a plan (draft)") — a fresh plan is never
        commercially available or published on creation."""
        plan = self._repo.create(
            code=code,
            name=name,
            status=_STATUS_DRAFT,
            description=description,
            is_commercially_available=False,
            billing_cycle_metadata=billing_cycle_metadata,
            pricing_metadata=pricing_metadata,
        )
        if capability_map:
            self._repo.set_capabilities(plan.id, capability_map)

        self._audit.record(
            action="plan.create",
            target_type="Plan",
            target_id=plan.id,
            actor_platform_administrator_id=actor_platform_administrator_id,
            reason=reason,
            before_state=None,
            after_state=_plan_snapshot(plan, capability_map or {}),
        )
        self._db.commit()
        return plan

    def update(
        self,
        plan: Plan,
        *,
        name: str | None = None,
        description: str | None = None,
        is_commercially_available: bool | None = None,
        billing_cycle_metadata: dict[str, Any] | None = None,
        pricing_metadata: dict[str, Any] | None = None,
        capability_map: dict[str, bool] | None = None,
        actor_platform_administrator_id: UUID,
        reason: str | None = None,
    ) -> Plan:
        """Update a Plan's fields/capability ceiling. Does NOT change
        `status` — use `publish()`/`retire()` for that."""
        before = _plan_snapshot(plan, self._repo.get_capability_map(plan.id))

        fields: dict[str, Any] = {}
        if name is not None:
            fields["name"] = name
        if description is not None:
            fields["description"] = description
        if is_commercially_available is not None:
            fields["is_commercially_available"] = is_commercially_available
        if billing_cycle_metadata is not None:
            fields["billing_cycle_metadata"] = billing_cycle_metadata
        if pricing_metadata is not None:
            fields["pricing_metadata"] = pricing_metadata
        if fields:
            self._repo.update_fields(plan, **fields)
        if capability_map is not None:
            self._repo.set_capabilities(plan.id, capability_map)

        self._audit.record(
            action="plan.update",
            target_type="Plan",
            target_id=plan.id,
            actor_platform_administrator_id=actor_platform_administrator_id,
            reason=reason,
            before_state=before,
            after_state=_plan_snapshot(plan, self._repo.get_capability_map(plan.id)),
        )
        self._db.commit()
        return plan

    def publish(
        self,
        plan: Plan,
        *,
        actor_platform_administrator_id: UUID,
        reason: str | None = None,
    ) -> Plan:
        """`draft` -> `published`. Makes the Plan assignable to tenants."""
        if plan.status != _STATUS_DRAFT:
            raise PlanTransitionError(
                f"Cannot publish a Plan with status '{plan.status}'. "
                "Only a 'draft' Plan may be published."
            )
        before = {"status": plan.status}
        self._repo.update_fields(plan, status=_STATUS_PUBLISHED)
        self._audit.record(
            action="plan.publish",
            target_type="Plan",
            target_id=plan.id,
            actor_platform_administrator_id=actor_platform_administrator_id,
            reason=reason,
            before_state=before,
            after_state={"status": plan.status},
        )
        self._db.commit()
        return plan

    def retire(
        self,
        plan: Plan,
        *,
        actor_platform_administrator_id: UUID,
        reason: str | None = None,
    ) -> Plan:
        """`published` -> `retired`. Blocks only **new** assignments
        (BR-9A-018) — existing `Subscription` rows are never touched by
        this method."""
        if plan.status != _STATUS_PUBLISHED:
            raise PlanTransitionError(
                f"Cannot retire a Plan with status '{plan.status}'. "
                "Only a 'published' Plan may be retired."
            )
        before = {"status": plan.status}
        self._repo.update_fields(plan, status=_STATUS_RETIRED)
        self._audit.record(
            action="plan.retire",
            target_type="Plan",
            target_id=plan.id,
            actor_platform_administrator_id=actor_platform_administrator_id,
            reason=reason,
            before_state=before,
            after_state={"status": plan.status},
        )
        self._db.commit()
        return plan
