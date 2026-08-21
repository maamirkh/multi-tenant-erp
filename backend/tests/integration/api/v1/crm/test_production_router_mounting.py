"""Production router-mounting smoke test (T079; updated for Epic 9A
Phase 9's T133).

Every other CRM API test file uses the test-only ``crm_client`` fixture
(``tests/integration/api/v1/crm/conftest.py``), which manually mounts
``crm_router`` to exercise the Router -> Service -> Repository stack
before T079 landed. This file instead uses the SHARED ``test_client``
fixture (``tests/conftest.py``), which builds its app via the real
``main.create_app()`` -> ``api/v1/router.py`` -> ``crm_router`` chain —
proving the actual production mounting works end-to-end: the CRM API is
live under ``/api/v1/companies/{company_id}/crm/...``, gated by
``get_current_company_member`` (tenant membership),
``require_capability_entitled("crm")`` (Epic 9A Plan-ceiling + toggle
resolution, T133), and ``require_crm_enabled`` (feature flag), in that
order, exactly as configured in ``api/v1/router.py``.

Task: T079 (tasks.md Phase 9, original CRM epic numbering) — "Tests:
covered by every prior API test file, re-run once against the
fully-mounted router." Extended by Epic 9A's T133.
"""

from __future__ import annotations

from datetime import date
from uuid import UUID

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from modules.auth.models.user import User
from modules.companies.repositories.company_repository import CompanyRepository
from modules.crm.repositories.feature_flag_repository import CrmFeatureFlagRepository
from modules.crm.services.feature_flag_service import CrmFeatureFlagService
from modules.platform_admin.models.platform_administrator import PlatformAdministrator
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
from tests.integration.api.v1.crm.conftest import (
    auth_header,
    create_company,
    new_user_and_token,
)


def _enable_crm(db_session: Session, company_id: str) -> None:
    service = CrmFeatureFlagService(
        db=db_session, flag_repo=CrmFeatureFlagRepository(db_session)
    )
    service.enable(UUID(company_id))


def _give_crm_allowing_subscription(db_session: Session, company_id: str) -> None:
    """Assign an active Subscription whose Plan allows `crm` (Epic 9A
    Phase 9, T129-T133) — isolates this file's CRM-toggle-specific
    assertions from the separate Plan-ceiling gate mounted in front of
    `require_crm_enabled`, exactly matching a real onboarded tenant (a
    company that predates any Subscription resolves the Plan ceiling as
    inapplicable and defers to the toggle alone; this fixture instead
    represents the common case of a tenant genuinely on an allowing
    Plan)."""
    actor_user = User(
        email=f"t133-actor-{company_id[:8]}@example.com", display_name="T133 Actor"
    )
    db_session.add(actor_user)
    db_session.flush()
    actor = PlatformAdministrator(user_id=actor_user.id, is_active=True)
    db_session.add(actor)
    db_session.flush()

    plan_service = PlanService(
        db=db_session,
        repo=PlanRepository(db_session),
        audit=PlatformAuditService(db_session, PlatformAuditRepository(db_session)),
    )
    plan = plan_service.create(
        code=f"t133-crm-plan-{company_id[:8]}",
        name="T133 CRM-Allowing Plan",
        capability_map={"crm": True},
        actor_platform_administrator_id=actor.id,
    )
    plan = plan_service.publish(plan, actor_platform_administrator_id=actor.id)

    subscription_service = SubscriptionService(
        db=db_session,
        repo=SubscriptionRepository(db_session),
        company_repo=CompanyRepository(db_session),
        quota_service=QuotaService(QuotaRepository(db_session)),
        audit=PlatformAuditService(db_session, PlatformAuditRepository(db_session)),
    )
    subscription_service.assign_or_change(
        company_id=UUID(company_id),
        plan_id=plan.id,
        effective_date=date.today(),
        actor_platform_administrator_id=actor.id,
    )


class TestProductionRouterMounting:
    def test_crm_endpoint_reachable_via_production_router(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """A real CRM endpoint, hit through the production app (not the
        test-only manual-mount fixture), returns 200 once the flag is on."""
        _, token = new_user_and_token(test_client, db_session)
        company_id = create_company(test_client, token)
        _enable_crm(db_session, company_id)

        resp = test_client.get(
            f"/api/v1/companies/{company_id}/crm/leads",
            headers=auth_header(token),
        )

        assert resp.status_code == 200, resp.text

    def test_feature_flag_gate_applied_at_production_mount(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """Flag off (default) -> the documented 403, proving CRM's
        feature-toggle state is genuinely load-bearing at the production
        mount — not merely available as an unused import.

        **Epic 9A Phase 9 update (T133)**: the production mount is now
        ``get_current_company_member -> require_capability_entitled("crm")
        -> require_crm_enabled``. The company is given a CRM-allowing
        Subscription first so the Plan ceiling itself is satisfied — the
        denial below comes specifically from the tenant's own toggle
        being off. The error code is ``CAPABILITY_NOT_ENTITLED``, not
        ``FEATURE_DISABLED``: ``require_capability_entitled``'s resolver
        implements spec.md §17.2's full Plan x Toggle resolution (not the
        Plan ceiling alone), so it already denies once it sees the toggle
        is off — the same fact ``require_crm_enabled`` would also have
        denied on, had the request reached it. This does not weaken
        anything (the request is still correctly denied, and no CRM
        source file was modified, per T133's acceptance) — it reflects
        that the mount-level gate is now genuinely the *first and
        authoritative* Unavailable-or-not answer, exactly as plan.md
        §13.1 intends by adding it as the *primary* enforcement point.
        """
        _, token = new_user_and_token(test_client, db_session)
        company_id = create_company(test_client, token)
        _give_crm_allowing_subscription(db_session, company_id)

        resp = test_client.get(
            f"/api/v1/companies/{company_id}/crm/leads",
            headers=auth_header(token),
        )

        assert resp.status_code == 403, resp.text
        assert resp.json()["error"]["code"] == "CAPABILITY_NOT_ENTITLED"

    def test_cross_tenant_membership_gate_still_applies(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """A user with no membership in the target company is rejected by
        the existing ``get_current_company_member`` gate before
        ``require_crm_enabled`` is even reached — both dependencies are
        additive to the same ``include_router()`` call (T079), neither
        replaces the other."""
        _, owner_token = new_user_and_token(test_client, db_session)
        company_id = create_company(test_client, owner_token)
        _enable_crm(db_session, company_id)

        _, outsider_token = new_user_and_token(test_client, db_session)

        resp = test_client.get(
            f"/api/v1/companies/{company_id}/crm/leads",
            headers=auth_header(outsider_token),
        )

        assert resp.status_code in (403, 404), resp.text
