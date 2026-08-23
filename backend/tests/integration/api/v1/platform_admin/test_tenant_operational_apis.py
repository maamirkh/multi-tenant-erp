"""[T167, T168, T169, T170] Platform operational APIs — tenant directory,
360° detail, lifecycle history, and the platform audit view — Epic 9A
Phase 13 (FR-9A-010/016/020/021, FR-9A-200).

Real HTTP throughout, real Postgres, matching this module's established
convention.
"""

from __future__ import annotations

import uuid
from datetime import date, timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from core.config.settings import get_settings
from core.events.outbox import EventOutboxRepository
from core.utils.datetime import utcnow
from modules.auth.models.user import User
from modules.companies.models.company import Company
from modules.companies.repositories.company_repository import CompanyRepository
from modules.platform_admin.models.plan import Plan
from modules.platform_admin.models.platform_administrator import PlatformAdministrator
from modules.platform_admin.models.platform_session import PlatformSession
from modules.platform_admin.repositories.plan_repository import PlanRepository
from modules.platform_admin.repositories.platform_audit_repository import (
    PlatformAuditRepository,
)
from modules.platform_admin.repositories.platform_rbac_repository import (
    PlatformRbacRepository,
)
from modules.platform_admin.repositories.quota_repository import QuotaRepository
from modules.platform_admin.repositories.subscription_repository import (
    SubscriptionRepository,
)
from modules.platform_admin.services.platform_audit_service import PlatformAuditService
from modules.platform_admin.services.platform_jwt_service import PlatformJwtService
from modules.platform_admin.services.platform_rbac_seed_service import (
    PlatformRbacSeedService,
)
from modules.platform_admin.services.quota_service import QuotaService
from modules.platform_admin.services.subscription_service import SubscriptionService
from modules.platform_admin.services.tenant_lifecycle_service import (
    TenantLifecycleService,
)


def _make_token_with_permissions(
    db: Session, codes: set[str]
) -> tuple[PlatformAdministrator, str]:
    user = User(
        email=f"t167-admin-{uuid.uuid4().hex[:12]}@example.test",
        display_name="T167 Platform Admin",
    )
    db.add(user)
    db.flush()
    administrator = PlatformAdministrator(user_id=user.id, is_active=True)
    db.add(administrator)
    db.flush()
    rbac_repo = PlatformRbacRepository(db)
    PlatformRbacSeedService(db, rbac_repo).seed_all()
    role = rbac_repo.create_role(
        code=f"t167-route-role-{uuid.uuid4().hex[:10]}", name="T167 Test Route Role"
    )
    rbac_repo.set_role_permissions(role.id, set(codes))
    rbac_repo.assign_role(
        platform_administrator_id=administrator.id,
        role_id=role.id,
        assigned_by=None,
        assigned_at=utcnow(),
    )
    db.commit()
    session = PlatformSession(
        platform_administrator_id=administrator.id,
        expires_at=utcnow() + timedelta(days=1),
    )
    db.add(session)
    db.flush()
    db.commit()
    token = PlatformJwtService(get_settings()).create_access_token(
        platform_administrator_id=administrator.id, session_id=session.id
    )
    return administrator, token


def _make_company(db: Session, *, label: str) -> Company:
    suffix = uuid.uuid4().hex[:10]
    owner = User(
        email=f"t167-owner-{label}-{suffix}@example.test",
        display_name=f"T167 Owner {label}",
    )
    db.add(owner)
    db.flush()
    company = Company(
        legal_name=f"T167 Directory Co {label} {suffix}",
        slug=f"t167-directory-co-{label}-{suffix}",
        owner_id=owner.id,
        email=f"t167-directory-co-{label}-{suffix}@example.com",
        status="active",
    )
    db.add(company)
    db.flush()
    db.commit()
    return company


class TestTenantDirectory:
    def test_list_tenants_requires_permission(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        _, token = _make_token_with_permissions(db_session, {"platform.audit.read"})
        response = test_client.get(
            "/api/v1/platform/tenants",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 403, response.text

    def test_list_tenants_search_filters_by_legal_name(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        _, token = _make_token_with_permissions(db_session, {"platform.tenants.read"})
        company = _make_company(db_session, label="searchable")

        response = test_client.get(
            "/api/v1/platform/tenants",
            params={"search": company.legal_name[:20]},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200, response.text
        items = response.json()["data"]["items"]
        assert any(item["id"] == str(company.id) for item in items)

    def test_list_tenants_is_bounded_by_page_size(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        _, token = _make_token_with_permissions(db_session, {"platform.tenants.read"})
        response = test_client.get(
            "/api/v1/platform/tenants",
            params={"page_size": 500},
            headers={"Authorization": f"Bearer {token}"},
        )
        # page_size is capped at 100 by the router's own Query(..., le=100).
        assert response.status_code == 422, response.text


class TestTenantDetail:
    def test_get_tenant_detail_not_found(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        _, token = _make_token_with_permissions(db_session, {"platform.tenants.read"})
        response = test_client.get(
            f"/api/v1/platform/tenants/{uuid.uuid4()}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 404, response.text

    def test_get_tenant_detail_shape_and_no_business_records(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        actor, token = _make_token_with_permissions(
            db_session, {"platform.tenants.read"}
        )
        company = _make_company(db_session, label="detail")

        suffix = uuid.uuid4().hex[:10]
        plan = Plan(code=f"t167-plan-{suffix}", name="T167 Plan", status="published")
        db_session.add(plan)
        db_session.flush()
        PlanRepository(db_session).set_capabilities(plan.id, {"inventory": True})
        QuotaRepository(db_session).set_plan_quota(plan.id, "users", None)
        db_session.commit()

        SubscriptionService(
            db=db_session,
            repo=SubscriptionRepository(db_session),
            company_repo=CompanyRepository(db_session),
            quota_service=QuotaService(QuotaRepository(db_session)),
            audit=PlatformAuditService(db_session, PlatformAuditRepository(db_session)),
        ).assign_or_change(
            company_id=company.id,
            plan_id=plan.id,
            effective_date=date.today(),
            actor_platform_administrator_id=actor.id,
        )

        response = test_client.get(
            f"/api/v1/platform/tenants/{company.id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200, response.text
        data = response.json()["data"]
        assert data["id"] == str(company.id)
        assert data["plan"]["code"] == plan.code
        assert data["subscription"] is not None
        assert isinstance(data["entitlements"], list)
        assert isinstance(data["quotas"], list)
        assert data["user_count"] == 0
        assert isinstance(data["lifecycle_history"], list)
        assert isinstance(data["recent_audit_events"], list)
        # FR-9A-021: never a business transaction record field/term.
        body_text = response.text.lower()
        for forbidden in ("invoice", "journal_entry", "sales_order", "purchase_order"):
            assert forbidden not in body_text


class TestTenantLifecycleHistory:
    def test_lifecycle_history_shows_suspend_and_reactivate_with_actor_and_reason(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        actor, token = _make_token_with_permissions(
            db_session, {"platform.tenants.read"}
        )
        company = _make_company(db_session, label="lifecycle")

        lifecycle_service = TenantLifecycleService(
            db=db_session,
            company_repo=CompanyRepository(db_session),
            outbox_repo=EventOutboxRepository(db_session),
            audit=PlatformAuditService(db_session, PlatformAuditRepository(db_session)),
        )
        lifecycle_service.suspend(
            company_id=company.id,
            actor_platform_administrator_id=actor.id,
            reason="T167 lifecycle-history test — suspend.",
        )
        lifecycle_service.reactivate(
            company_id=company.id,
            actor_platform_administrator_id=actor.id,
            reason="T167 lifecycle-history test — reactivate.",
        )

        response = test_client.get(
            f"/api/v1/platform/tenants/{company.id}/lifecycle-history",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200, response.text
        events = response.json()["data"]["events"]
        actions = {e["action"] for e in events}
        assert actions == {"tenant_lifecycle.suspend", "tenant_lifecycle.reactivate"}
        for event in events:
            assert event["actor_platform_administrator_id"] == str(actor.id)
            assert event["reason"] is not None


class TestPlatformAuditView:
    def test_audit_requires_permission(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        _, token = _make_token_with_permissions(db_session, {"platform.tenants.read"})
        response = test_client.get(
            "/api/v1/platform/audit", headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 403, response.text

    def test_audit_filters_by_action(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        actor, token = _make_token_with_permissions(
            db_session, {"platform.audit.read", "platform.tenants.read"}
        )
        company = _make_company(db_session, label="audit")
        TenantLifecycleService(
            db=db_session,
            company_repo=CompanyRepository(db_session),
            outbox_repo=EventOutboxRepository(db_session),
            audit=PlatformAuditService(db_session, PlatformAuditRepository(db_session)),
        ).suspend(
            company_id=company.id,
            actor_platform_administrator_id=actor.id,
            reason="T170 audit filter test.",
        )

        response = test_client.get(
            "/api/v1/platform/audit",
            params={
                "action": "tenant_lifecycle.suspend",
                "company_id": str(company.id),
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200, response.text
        items = response.json()["data"]["items"]
        assert len(items) == 1
        assert items[0]["action"] == "tenant_lifecycle.suspend"

    def test_audit_view_is_append_only_no_mutation_route(
        self, test_client: TestClient
    ) -> None:
        spec = test_client.get("/openapi.json").json()
        assert list(spec["paths"]["/api/v1/platform/audit"].keys()) == ["get"]
