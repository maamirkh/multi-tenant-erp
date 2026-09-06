"""[T145-T157] Cross-tenant isolation adversarial proof — Epic 9A
Phase 11 (master prompt §12/§25E). Every new Phase-11 read endpoint
(quotas, usage, ai-credits) and the override grant are company-scoped;
this proves company A's data is never visible through company B's view,
and a grant against company A never appears against company B.

Real HTTP throughout.
"""

from __future__ import annotations

import uuid
from datetime import timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from core.config.settings import get_settings
from core.utils.datetime import utcnow
from modules.auth.models.user import User
from modules.companies.models.company import Company
from modules.platform_admin.models.platform_administrator import PlatformAdministrator
from modules.platform_admin.models.platform_session import PlatformSession
from modules.platform_admin.repositories.capability_repository import (
    CapabilityRepository,
)
from modules.platform_admin.repositories.platform_rbac_repository import (
    PlatformRbacRepository,
)
from modules.platform_admin.services.capability_seed_service import (
    CapabilitySeedService,
)
from modules.platform_admin.services.platform_jwt_service import PlatformJwtService
from modules.platform_admin.services.platform_rbac_seed_service import (
    PlatformRbacSeedService,
)


def _make_token_with_permissions(db: Session, codes: set[str]) -> str:
    user = User(
        email=f"t11-isolation-admin-{uuid.uuid4().hex[:12]}@example.test",
        display_name="T11 Isolation Admin",
    )
    db.add(user)
    db.flush()
    administrator = PlatformAdministrator(user_id=user.id, is_active=True)
    db.add(administrator)
    db.flush()
    rbac_repo = PlatformRbacRepository(db)
    PlatformRbacSeedService(db, rbac_repo).seed_all()
    role = rbac_repo.create_role(
        code=f"t11-isolation-role-{uuid.uuid4().hex[:10]}", name="T11 Isolation Role"
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
        email=f"t11-isolation-owner-{label}-{suffix}@example.test",
        display_name=f"T11 Isolation Owner {label}",
    )
    db.add(owner)
    db.flush()
    company = Company(
        legal_name=f"T11 Isolation Co {label} {suffix}",
        slug=f"t11-isolation-co-{label}-{suffix}",
        owner_id=owner.id,
        email=f"t11-isolation-co-{label}-{suffix}@example.com",
        status="active",
    )
    db.add(company)
    db.flush()
    db.commit()
    return company


class TestPhase11CrossTenantIsolation:
    def test_entitlement_override_grant_on_company_a_not_visible_via_company_b(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        CapabilitySeedService(
            db_session, CapabilityRepository(db_session)
        ).seed_capabilities()
        token = _make_token_with_permissions(
            db_session,
            {"platform.entitlements.override", "platform.entitlements.read"},
        )
        headers = {"Authorization": f"Bearer {token}"}
        company_a = _make_company(db_session, label="a")
        company_b = _make_company(db_session, label="b")

        grant_response = test_client.post(
            f"/api/v1/platform/tenants/{company_a.id}/entitlement-overrides",
            json={
                "capability_key": "inventory",
                "reason": "Isolation test — company A only.",
            },
            headers=headers,
        )
        assert grant_response.status_code == 201, grant_response.text

        # Company A: the override is genuinely in effect.
        entitlements_a = test_client.get(
            f"/api/v1/platform/tenants/{company_a.id}/entitlements", headers=headers
        ).json()["data"]["entitlements"]
        inventory_a = next(
            e for e in entitlements_a if e["capability_key"] == "inventory"
        )
        assert inventory_a["reason"] == "override"

        # Company B: no override exists for it — must NOT inherit A's grant.
        entitlements_b = test_client.get(
            f"/api/v1/platform/tenants/{company_b.id}/entitlements", headers=headers
        ).json()["data"]["entitlements"]
        inventory_b = next(
            e for e in entitlements_b if e["capability_key"] == "inventory"
        )
        assert inventory_b["reason"] != "override"

    def test_ai_credit_ledger_is_isolated_per_tenant(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        token = _make_token_with_permissions(
            db_session, {"platform.ai_usage.read", "platform.ai_credits.adjust"}
        )
        headers = {"Authorization": f"Bearer {token}"}
        company_a = _make_company(db_session, label="ai-a")
        company_b = _make_company(db_session, label="ai-b")

        adjust_response = test_client.post(
            f"/api/v1/platform/tenants/{company_a.id}/ai-credits",
            json={"delta": "50", "reason": "Isolation test — company A only."},
            headers=headers,
        )
        assert adjust_response.status_code == 201, adjust_response.text

        balance_a = test_client.get(
            f"/api/v1/platform/tenants/{company_a.id}/ai-credits", headers=headers
        ).json()["data"]
        assert balance_a["status"] == "active"
        assert float(balance_a["balance"]) == 50.0

        balance_b = test_client.get(
            f"/api/v1/platform/tenants/{company_b.id}/ai-credits", headers=headers
        ).json()["data"]
        assert balance_b["status"] == "not_yet_active"
        assert float(balance_b["balance"]) == 0.0
        assert balance_b["entries"] == []

    def test_usage_records_are_isolated_per_tenant(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        token = _make_token_with_permissions(db_session, {"platform.quotas.read"})
        headers = {"Authorization": f"Bearer {token}"}
        company_a = _make_company(db_session, label="usage-a")
        company_b = _make_company(db_session, label="usage-b")

        from modules.platform_admin.repositories.usage_repository import UsageRepository
        from modules.platform_admin.services.usage_service import (
            UsageService,
            current_month_period,
        )

        period_start, period_end = current_month_period()
        UsageService(db_session, UsageRepository(db_session)).compute_for_company(
            company_id=company_a.id, period_start=period_start, period_end=period_end
        )

        usage_a = test_client.get(
            f"/api/v1/platform/tenants/{company_a.id}/usage", headers=headers
        ).json()["data"]["records"]
        assert len(usage_a) == 1

        usage_b = test_client.get(
            f"/api/v1/platform/tenants/{company_b.id}/usage", headers=headers
        ).json()["data"]["records"]
        assert usage_b == []
