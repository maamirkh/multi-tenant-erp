"""RolloutService — plan.md §34 Entitlement Rollout Strategy steps 3-4
(T125, T126).

Step 3 (`create_baseline_plan`): seed one published "Legacy/Unlimited"
Plan with `PlanCapability.allowed=true` for every seeded module
Capability and `PlanQuota.limit_value=NULL` (unlimited) for every quota
category — guaranteeing existing tenants lose nothing once enforcement
(Phase 9's later tasks) is activated.

Step 4 (`bulk_assign_existing_tenants`): assign every **existing** tenant
(one not yet on any Subscription) to that baseline Plan, actor = the
bootstrap Platform Owner, fully audited via
`SubscriptionService.assign_or_change()` — no separate audit call is
needed here; no new audit action code is invented.

Both steps are idempotent and safely re-runnable:
`create_baseline_plan()` re-applies the full capability/quota ceiling
every call (cheap, and resumes correctly even if a prior run's final
commit never completed); `bulk_assign_existing_tenants()` only ever
touches companies with `subscription_id IS NULL`
(`CompanyRepository.list_without_subscription()`), so a company already
assigned in a prior run is never revisited.

**Quota-definition seeding note**: `PlanQuota.quota_key` carries a real
FK to `quota_definitions.key` (RESTRICT), and no earlier phase seeds
this catalogue (Phase 8's T107 built the models/resolver only — no seed
task exists for it anywhere in tasks.md). This service seeds it as its
own necessary implementation surface, mirroring this project's
established precedent of a task creating the supporting artifact it
needs but that no prior task named explicitly (e.g. T049 creating
`PlatformRefreshTokenRepository`). This is squarely Phase 9's own
data-seeding scope, not future-phase leakage: `quota_definitions` already
exists from migration 059 (Phase 2), and the `enforcement_style` choice
below is a plain, documented default — never fabricated as a spec claim,
and adjustable later with zero schema migration (BR-9A-030's point).
"""

from __future__ import annotations

import logging
from datetime import date
from uuid import UUID

from sqlalchemy.orm import Session

from modules.companies.repositories.company_repository import CompanyRepository
from modules.platform_admin.models.plan import Plan
from modules.platform_admin.repositories.capability_repository import (
    CapabilityRepository,
)
from modules.platform_admin.repositories.plan_repository import PlanRepository
from modules.platform_admin.repositories.platform_audit_repository import (
    PlatformAuditRepository,
)
from modules.platform_admin.repositories.quota_repository import QuotaRepository
from modules.platform_admin.repositories.subscription_repository import (
    SubscriptionRepository,
)
from modules.platform_admin.services.plan_service import PlanService
from modules.platform_admin.services.platform_audit_service import PlatformAuditService
from modules.platform_admin.services.quota_service import QuotaService
from modules.platform_admin.services.subscription_service import SubscriptionService

logger = logging.getLogger(__name__)

BASELINE_PLAN_CODE = "legacy-unlimited"
BASELINE_PLAN_NAME = "Legacy/Unlimited"
_BASELINE_PLAN_DESCRIPTION = (
    "Rollout baseline plan (plan.md §34) — grants every existing tenant "
    "everything they already had access to before Epic 9A's entitlement "
    "layer was introduced. Never sold; not commercially available."
)

# spec.md §17.3's six quota categories, each with an explicitly-declared
# enforcement style (BR-9A-030) — a documented Tasks-phase default, since
# neither spec.md nor plan.md prescribes one per category.
QUOTA_DEFINITION_CATALOGUE: tuple[dict[str, str], ...] = (
    {
        "key": "users",
        "display_name": "Users",
        "unit": "count",
        "enforcement_style": "hard",
    },
    {
        "key": "branches",
        "display_name": "Branches",
        "unit": "count",
        "enforcement_style": "hard",
    },
    {
        "key": "transactions",
        "display_name": "Transactions",
        "unit": "count",
        "enforcement_style": "informational",
    },
    {
        "key": "storage",
        "display_name": "Storage",
        "unit": "MB",
        "enforcement_style": "soft",
    },
    {
        "key": "api_calls",
        "display_name": "API Calls",
        "unit": "count",
        "enforcement_style": "soft",
    },
    {
        "key": "ai_credits",
        "display_name": "AI Credits",
        "unit": "count",
        "enforcement_style": "informational",
    },
)


class RolloutService:
    """One-time (idempotent, re-runnable) rollout data steps — never a
    migration (ADR-8's decoupling principle)."""

    def __init__(
        self,
        db: Session,
        capability_repo: CapabilityRepository,
        quota_repo: QuotaRepository,
        plan_repo: PlanRepository,
        plan_service: PlanService,
        company_repo: CompanyRepository,
        subscription_service: SubscriptionService,
    ) -> None:
        self._db = db
        self._capability_repo = capability_repo
        self._quota_repo = quota_repo
        self._plan_repo = plan_repo
        self._plan_service = plan_service
        self._company_repo = company_repo
        self._subscription_service = subscription_service

    def _seed_quota_definitions(self) -> None:
        for entry in QUOTA_DEFINITION_CATALOGUE:
            if self._quota_repo.get_definition(entry["key"]) is not None:
                continue
            self._quota_repo.create_definition(
                key=entry["key"],
                display_name=entry["display_name"],
                unit=entry["unit"],
                enforcement_style=entry["enforcement_style"],
            )
        self._db.commit()

    def create_baseline_plan(self, *, actor_platform_administrator_id: UUID) -> Plan:
        """Rollout step 3. Idempotent: safe to call on every deploy."""
        self._seed_quota_definitions()

        plan = self._plan_repo.get_by_code(BASELINE_PLAN_CODE)
        if plan is None:
            plan = self._plan_service.create(
                code=BASELINE_PLAN_CODE,
                name=BASELINE_PLAN_NAME,
                description=_BASELINE_PLAN_DESCRIPTION,
                actor_platform_administrator_id=actor_platform_administrator_id,
                reason="Epic 9A entitlement rollout baseline (plan.md §34 step 3).",
            )
            plan = self._plan_service.publish(
                plan,
                actor_platform_administrator_id=actor_platform_administrator_id,
                reason="Epic 9A entitlement rollout baseline (plan.md §34 step 3).",
            )

        # Re-applied unconditionally (idempotent create-or-update
        # operations) so a resumed run always converges on the full
        # all-allowed / all-unlimited ceiling, even if a prior run's
        # final commit below never completed.
        capabilities = self._capability_repo.list_all(is_active=True)
        self._plan_repo.set_capabilities(plan.id, {c.key: True for c in capabilities})
        for entry in QUOTA_DEFINITION_CATALOGUE:
            self._quota_repo.set_plan_quota(plan.id, entry["key"], None)
        self._db.commit()
        return plan

    def bulk_assign_existing_tenants(
        self, *, baseline_plan: Plan, actor_platform_administrator_id: UUID
    ) -> int:
        """Rollout step 4. Idempotent: only touches companies with
        `subscription_id IS NULL`, so a company already assigned by a
        prior run is never revisited or re-audited. Does not touch any
        tenant feature-toggle row.

        Returns the number of companies newly assigned.
        """
        companies = self._company_repo.list_without_subscription()
        for company in companies:
            self._subscription_service.assign_or_change(
                company_id=company.id,
                plan_id=baseline_plan.id,
                effective_date=date.today(),
                actor_platform_administrator_id=actor_platform_administrator_id,
                reason=(
                    "Epic 9A entitlement rollout baseline assignment "
                    "(plan.md §34 step 4)."
                ),
            )
        logger.info(
            "Rollout: existing tenants bulk-assigned to baseline plan",
            extra={"assigned_count": len(companies), "plan_id": str(baseline_plan.id)},
        )
        return len(companies)


def main() -> int:
    """Standalone rollout entrypoint (plan.md §34 steps 2-4), run once by
    an operator after the bootstrap Platform Owner (§7) exists — mirrors
    `bootstrap.py`'s own out-of-band, non-HTTP, non-migration convention.
    No Click/Typer framework introduced.
    """
    from core.database.session import SessionLocal
    from modules.platform_admin.constants import CANDIDATE_PLATFORM_ROLE_BUNDLES
    from modules.platform_admin.repositories.platform_rbac_repository import (
        PlatformRbacRepository,
    )
    from modules.platform_admin.services.capability_seed_service import (
        CapabilitySeedService,
    )

    owner_role_code = next(
        b["code"]
        for b in CANDIDATE_PLATFORM_ROLE_BUNDLES
        if b["code"] == "platform_owner"
    )

    db = SessionLocal()
    try:
        CapabilitySeedService(db, CapabilityRepository(db)).seed_capabilities()

        owner_ids = PlatformRbacRepository(db).get_active_administrator_ids_with_role(
            owner_role_code
        )
        if not owner_ids:
            print(
                "No active Platform Owner found. Run the bootstrap command "
                "(modules.platform_admin.bootstrap) before the rollout."
            )
            return 1
        actor_id = owner_ids[0]

        audit = PlatformAuditService(db, PlatformAuditRepository(db))
        service = RolloutService(
            db=db,
            capability_repo=CapabilityRepository(db),
            quota_repo=QuotaRepository(db),
            plan_repo=PlanRepository(db),
            plan_service=PlanService(db=db, repo=PlanRepository(db), audit=audit),
            company_repo=CompanyRepository(db),
            subscription_service=SubscriptionService(
                db=db,
                repo=SubscriptionRepository(db),
                company_repo=CompanyRepository(db),
                quota_service=QuotaService(QuotaRepository(db)),
                audit=audit,
            ),
        )
        plan = service.create_baseline_plan(actor_platform_administrator_id=actor_id)
        assigned = service.bulk_assign_existing_tenants(
            baseline_plan=plan, actor_platform_administrator_id=actor_id
        )
    except Exception:
        db.rollback()
        logger.exception("Rollout failed with an unexpected error")
        print("Rollout failed with an unexpected error.")
        return 1
    finally:
        db.close()

    print(
        f"Rollout complete: baseline plan '{plan.code}', {assigned} tenant(s) assigned."
    )
    return 0


if __name__ == "__main__":
    import sys

    sys.exit(main())
