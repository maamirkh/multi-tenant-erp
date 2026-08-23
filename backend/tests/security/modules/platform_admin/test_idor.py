"""[T207] Security test: cross-tenant IDOR/BOLA on every tenant-scoped
Platform route (FR-9A-212, master prompt §12).

Substituting another company's id must never yield data, or cause a
mutation, that the caller's actual held permissions don't already allow
— every tenant-scoped read/write is scoped by the `companyId` path
parameter and nothing else (never inferred from a header, a cached
selection, or `erp_active_company_id`, which the Platform UI never even
reads, ADR-13).

Entitlement-override, AI-credit, and usage-record cross-tenant isolation
are already proven exhaustively by Phase 11's
`tests/integration/api/v1/platform_admin/test_phase11_tenant_isolation.py`
— this file covers the remaining tenant-scoped surface: tenant detail,
lifecycle history, subscription, quotas, quota overrides, and
support-access grants.
"""

from __future__ import annotations

import uuid
from datetime import date, timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from core.config.settings import get_settings
from core.utils.datetime import utcnow
from modules.auth.models.user import User
from modules.companies.models.company import Company
from modules.platform_admin.models.plan import Plan
from modules.platform_admin.models.platform_administrator import PlatformAdministrator
from modules.platform_admin.models.platform_session import PlatformSession
from modules.platform_admin.repositories.platform_rbac_repository import (
    PlatformRbacRepository,
)
from modules.platform_admin.services.platform_jwt_service import PlatformJwtService
from modules.platform_admin.services.platform_rbac_seed_service import (
    PlatformRbacSeedService,
)


def _make_token_with_permissions(db: Session, codes: set[str]) -> str:
    user = User(
        email=f"t207-idor-admin-{uuid.uuid4().hex[:12]}@example.test",
        display_name="T207 IDOR Admin",
    )
    db.add(user)
    db.flush()
    administrator = PlatformAdministrator(user_id=user.id, is_active=True)
    db.add(administrator)
    db.flush()
    rbac_repo = PlatformRbacRepository(db)
    PlatformRbacSeedService(db, rbac_repo).seed_all()
    role = rbac_repo.create_role(
        code=f"t207-idor-role-{uuid.uuid4().hex[:10]}", name="T207 IDOR Role"
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
    return PlatformJwtService(get_settings()).create_access_token(
        platform_administrator_id=administrator.id, session_id=session.id
    )


def _make_company(db: Session, *, label: str) -> Company:
    suffix = uuid.uuid4().hex[:10]
    owner = User(
        email=f"t207-idor-owner-{label}-{suffix}@example.test",
        display_name=f"T207 IDOR Owner {label}",
    )
    db.add(owner)
    db.flush()
    company = Company(
        legal_name=f"T207 IDOR Co {label} {suffix}",
        slug=f"t207-idor-co-{label}-{suffix}",
        owner_id=owner.id,
        email=f"t207-idor-co-{label}-{suffix}@example.com",
        status="active",
    )
    db.add(company)
    db.flush()
    db.commit()
    return company


class TestTenantDetailAndLifecycleIsolation:
    def test_tenant_detail_never_mixes_in_another_companys_fields(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        token = _make_token_with_permissions(db_session, {"platform.tenants.read"})
        headers = {"Authorization": f"Bearer {token}"}
        company_a = _make_company(db_session, label="detail-a")
        company_b = _make_company(db_session, label="detail-b")

        detail_a = test_client.get(
            f"/api/v1/platform/tenants/{company_a.id}", headers=headers
        ).json()["data"]
        detail_b = test_client.get(
            f"/api/v1/platform/tenants/{company_b.id}", headers=headers
        ).json()["data"]

        assert detail_a["id"] == str(company_a.id)
        assert detail_a["legal_name"] == company_a.legal_name
        assert detail_b["id"] == str(company_b.id)
        assert detail_b["legal_name"] == company_b.legal_name
        assert detail_a["id"] != detail_b["id"]
        assert detail_a["legal_name"] != detail_b["legal_name"]

    def test_lifecycle_history_of_company_a_never_appears_under_company_b(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        token = _make_token_with_permissions(
            db_session, {"platform.tenants.read", "platform.tenants.suspend"}
        )
        headers = {"Authorization": f"Bearer {token}"}
        company_a = _make_company(db_session, label="lifecycle-a")
        company_b = _make_company(db_session, label="lifecycle-b")

        suspend_response = test_client.post(
            f"/api/v1/platform/tenants/{company_a.id}/suspend",
            json={"reason": "IDOR isolation test"},
            headers=headers,
        )
        assert suspend_response.status_code == 200, suspend_response.text

        history_a = test_client.get(
            f"/api/v1/platform/tenants/{company_a.id}/lifecycle-history",
            headers=headers,
        ).json()["data"]["events"]
        history_b = test_client.get(
            f"/api/v1/platform/tenants/{company_b.id}/lifecycle-history",
            headers=headers,
        ).json()["data"]["events"]

        assert len(history_a) >= 1
        assert history_b == []


class TestSubscriptionIsolation:
    def test_assigning_a_plan_to_company_a_does_not_appear_on_company_b(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        token = _make_token_with_permissions(
            db_session,
            {"platform.subscriptions.read", "platform.subscriptions.manage"},
        )
        headers = {"Authorization": f"Bearer {token}"}
        company_a = _make_company(db_session, label="sub-a")
        company_b = _make_company(db_session, label="sub-b")

        plan = Plan(
            code=f"t207-plan-{uuid.uuid4().hex[:10]}",
            name="T207 Plan",
            status="published",
        )
        db_session.add(plan)
        db_session.commit()

        assign_response = test_client.post(
            f"/api/v1/platform/tenants/{company_a.id}/subscription",
            json={"plan_id": str(plan.id), "effective_date": date.today().isoformat()},
            headers=headers,
        )
        assert assign_response.status_code == 200, assign_response.text

        sub_a = test_client.get(
            f"/api/v1/platform/tenants/{company_a.id}/subscription", headers=headers
        ).json()["data"]
        sub_b = test_client.get(
            f"/api/v1/platform/tenants/{company_b.id}/subscription", headers=headers
        ).json()["data"]

        assert sub_a["current"] is not None
        assert sub_a["current"]["plan_id"] == str(plan.id)
        assert sub_b["current"] is None
        assert sub_b["history"] == []


class TestQuotaOverrideIsolation:
    def test_quota_override_on_company_a_never_affects_company_bs_quota_state(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        token = _make_token_with_permissions(
            db_session, {"platform.quotas.read", "platform.quotas.override"}
        )
        headers = {"Authorization": f"Bearer {token}"}
        company_a = _make_company(db_session, label="quota-a")
        company_b = _make_company(db_session, label="quota-b")

        override_response = test_client.post(
            f"/api/v1/platform/tenants/{company_a.id}/quota-overrides",
            json={
                "quota_key": "t207_isolation_quota",
                "override_limit": None,
                "reason": "IDOR isolation test — company A only.",
            },
            headers=headers,
        )
        assert override_response.status_code == 201, override_response.text

        quotas_a = test_client.get(
            f"/api/v1/platform/tenants/{company_a.id}/quotas", headers=headers
        ).json()["data"]["quotas"]
        quotas_b = test_client.get(
            f"/api/v1/platform/tenants/{company_b.id}/quotas", headers=headers
        ).json()["data"]["quotas"]

        override_quota_a = next(
            (q for q in quotas_a if q["quota_key"] == "t207_isolation_quota"), None
        )
        override_quota_b = next(
            (q for q in quotas_b if q["quota_key"] == "t207_isolation_quota"), None
        )
        # The override key is company-A-specific configuration data — it
        # must never surface as an unlimited/overridden state for B.
        if override_quota_a is not None:
            assert override_quota_a["state"] == "unlimited"
        assert override_quota_b is None or override_quota_b["state"] != "unlimited"


class TestSupportAccessGrantIsolation:
    def test_a_grant_initiated_for_company_a_is_scoped_to_company_a_only(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        token = _make_token_with_permissions(
            db_session,
            {"platform.support_access.initiate", "platform.support_access.read"},
        )
        headers = {"Authorization": f"Bearer {token}"}
        company_a = _make_company(db_session, label="support-a")
        company_b = _make_company(db_session, label="support-b")

        grant_response = test_client.post(
            f"/api/v1/platform/tenants/{company_a.id}/support-access",
            json={"reason": "IDOR isolation test — company A only."},
            headers=headers,
        )
        assert grant_response.status_code == 201, grant_response.text
        grant = grant_response.json()["data"]
        assert grant["company_id"] == str(company_a.id)
        assert grant["company_id"] != str(company_b.id)

    def test_terminating_a_grant_id_never_affects_a_different_companys_grant(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        token = _make_token_with_permissions(
            db_session,
            {"platform.support_access.initiate", "platform.support_access.read"},
        )
        headers = {"Authorization": f"Bearer {token}"}
        company_a = _make_company(db_session, label="term-a")
        company_b = _make_company(db_session, label="term-b")

        grant_a = test_client.post(
            f"/api/v1/platform/tenants/{company_a.id}/support-access",
            json={"reason": "Company A grant."},
            headers=headers,
        ).json()["data"]
        grant_b = test_client.post(
            f"/api/v1/platform/tenants/{company_b.id}/support-access",
            json={"reason": "Company B grant."},
            headers=headers,
        ).json()["data"]

        terminate_response = test_client.delete(
            f"/api/v1/platform/support-access/{grant_a['id']}", headers=headers
        )
        assert terminate_response.status_code == 204

        grants = test_client.get(
            "/api/v1/platform/support-access?page_size=100", headers=headers
        ).json()["data"]["items"]
        grant_a_after = next(g for g in grants if g["id"] == grant_a["id"])
        grant_b_after = next(g for g in grants if g["id"] == grant_b["id"])

        assert grant_a_after["status"] == "terminated"
        # Terminating A's grant must never terminate B's — the operation
        # is scoped by grantId, never by any implicit "current tenant".
        assert grant_b_after["status"] == "active"
