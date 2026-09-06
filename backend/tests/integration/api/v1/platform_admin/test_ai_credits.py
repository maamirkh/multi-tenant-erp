"""[T156] AI credit views show "not yet active" until real activity
exists — Epic 9A Phase 11 (FR-9A-235, T154/T155/T157).

Real HTTP throughout (test_client), matching this module's own
established convention for proving route-level behaviour, not just
service-level unit behaviour.
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
from modules.platform_admin.repositories.platform_rbac_repository import (
    PlatformRbacRepository,
)
from modules.platform_admin.services.platform_jwt_service import PlatformJwtService
from modules.platform_admin.services.platform_rbac_seed_service import (
    PlatformRbacSeedService,
)


def _make_platform_administrator(db: Session) -> PlatformAdministrator:
    user = User(
        email=f"t156-admin-{uuid.uuid4().hex[:12]}@example.test",
        display_name="T156 Platform Admin",
    )
    db.add(user)
    db.flush()
    administrator = PlatformAdministrator(user_id=user.id, is_active=True)
    db.add(administrator)
    db.flush()
    db.commit()
    return administrator


def _make_token_with_permissions(
    db: Session, codes: set[str]
) -> tuple[PlatformAdministrator, str]:
    administrator = _make_platform_administrator(db)
    rbac_repo = PlatformRbacRepository(db)
    PlatformRbacSeedService(db, rbac_repo).seed_all()
    role = rbac_repo.create_role(
        code=f"t156-route-role-{uuid.uuid4().hex[:10]}", name="T156 Test Route Role"
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


def _make_company(db: Session, *, owner_id: uuid.UUID) -> Company:
    suffix = uuid.uuid4().hex[:10]
    company = Company(
        legal_name=f"T156 AI Credits Co {suffix}",
        slug=f"t156-ai-credits-co-{suffix}",
        owner_id=owner_id,
        email=f"t156-ai-credits-co-{suffix}@example.com",
        status="active",
    )
    db.add(company)
    db.flush()
    db.commit()
    return company


class TestAiCreditsNotYetActive:
    def test_get_ai_credits_shows_not_yet_active_when_ledger_is_empty(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        _, token = _make_token_with_permissions(db_session, {"platform.ai_usage.read"})
        owner_user = User(
            email=f"t156-owner-{uuid.uuid4().hex[:10]}@example.test",
            display_name="T156 Owner",
        )
        db_session.add(owner_user)
        db_session.flush()
        company = _make_company(db_session, owner_id=owner_user.id)

        response = test_client.get(
            f"/api/v1/platform/tenants/{company.id}/ai-credits",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200, response.text
        data = response.json()["data"]
        assert data["status"] == "not_yet_active"
        assert data["entries"] == []
        assert float(data["balance"]) == 0.0

    def test_adjustment_flips_status_to_active_and_updates_balance(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        _, token = _make_token_with_permissions(
            db_session, {"platform.ai_usage.read", "platform.ai_credits.adjust"}
        )
        owner_user = User(
            email=f"t156-owner2-{uuid.uuid4().hex[:10]}@example.test",
            display_name="T156 Owner 2",
        )
        db_session.add(owner_user)
        db_session.flush()
        company = _make_company(db_session, owner_id=owner_user.id)
        headers = {"Authorization": f"Bearer {token}"}

        adjust_response = test_client.post(
            f"/api/v1/platform/tenants/{company.id}/ai-credits",
            json={"delta": "100.0000", "reason": "T156 initial manual credit grant."},
            headers=headers,
        )
        assert adjust_response.status_code == 201, adjust_response.text
        entry = adjust_response.json()["data"]
        assert entry["reason"] == "T156 initial manual credit grant."
        assert entry["provider"] is None
        assert entry["model"] is None

        get_response = test_client.get(
            f"/api/v1/platform/tenants/{company.id}/ai-credits", headers=headers
        )
        assert get_response.status_code == 200, get_response.text
        data = get_response.json()["data"]
        assert data["status"] == "active"
        assert float(data["balance"]) == 100.0
        assert len(data["entries"]) == 1

    def test_adjustment_without_reason_is_rejected(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        _, token = _make_token_with_permissions(
            db_session, {"platform.ai_credits.adjust"}
        )
        owner_user = User(
            email=f"t156-owner3-{uuid.uuid4().hex[:10]}@example.test",
            display_name="T156 Owner 3",
        )
        db_session.add(owner_user)
        db_session.flush()
        company = _make_company(db_session, owner_id=owner_user.id)

        response = test_client.post(
            f"/api/v1/platform/tenants/{company.id}/ai-credits",
            json={"delta": "10", "reason": ""},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 422, response.text

    def test_adjustment_without_permission_is_forbidden(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        _, token = _make_token_with_permissions(db_session, {"platform.ai_usage.read"})
        owner_user = User(
            email=f"t156-owner4-{uuid.uuid4().hex[:10]}@example.test",
            display_name="T156 Owner 4",
        )
        db_session.add(owner_user)
        db_session.flush()
        company = _make_company(db_session, owner_id=owner_user.id)

        response = test_client.post(
            f"/api/v1/platform/tenants/{company.id}/ai-credits",
            json={"delta": "10", "reason": "Should be forbidden."},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 403, response.text
