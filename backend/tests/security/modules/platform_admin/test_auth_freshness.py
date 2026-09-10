"""[T095-T097, T099-T100] [Gate C] Company-scoped access invalidation,
keyed on authentication time (ADR-6) — proves plan.md §9-§10.

Uses a real HTTP login flow, real suspend/reactivate calls through the
Phase-7 Platform routes, and probes a representative business-module
endpoint (``GET /companies/{id}/inventory/health``, itself gated by
``get_current_company_member`` -> ``assert_company_access_allowed``).
"""

from __future__ import annotations

import time
import uuid
from datetime import timedelta
from uuid import UUID

from fastapi.testclient import TestClient
from httpx import Response
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
from tests.fixtures.auth_fixtures import create_test_user
from tests.fixtures.users_roles_fixtures import (
    create_member_with_role,
    seed_system_roles,
)


def _make_platform_token_with_permissions(db: Session, codes: set[str]) -> str:
    user = User(
        email=f"freshness-platform-{uuid.uuid4().hex[:12]}@example.test",
        display_name="Freshness Platform Admin",
    )
    db.add(user)
    db.flush()
    administrator = PlatformAdministrator(user_id=user.id, is_active=True)
    db.add(administrator)
    db.flush()

    rbac_repo = PlatformRbacRepository(db)
    PlatformRbacSeedService(db, rbac_repo).seed_all()
    role = rbac_repo.create_role(
        code=f"freshness-test-role-{uuid.uuid4().hex[:10]}", name="Freshness Test Role"
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


def _make_tenant_company_and_member(
    db: Session, *, email: str, password: str
) -> tuple[User, Company]:
    user, _ = create_test_user(db, email=email, password=password)
    suffix = uuid.uuid4().hex[:10]
    company = Company(
        legal_name=f"Freshness Co {suffix}",
        slug=f"freshness-co-{suffix}",
        owner_id=user.id,
        email=f"freshness-co-{suffix}@example.test",
        status="active",
    )
    db.add(company)
    db.flush()
    seed_system_roles(db, company.id)
    create_member_with_role(
        db, company_id=company.id, user_id=user.id, role_slug="owner"
    )
    db.commit()
    return user, company


def _suspend(
    test_client: TestClient, platform_token: str, company_id: UUID
) -> Response:
    resp: Response = test_client.post(
        f"/api/v1/platform/tenants/{company_id}/suspend",
        json={"reason": "Gate C freshness test suspend"},
        headers={"Authorization": f"Bearer {platform_token}"},
    )
    return resp


def _reactivate(
    test_client: TestClient, platform_token: str, company_id: UUID
) -> Response:
    resp: Response = test_client.post(
        f"/api/v1/platform/tenants/{company_id}/reactivate",
        json={"reason": "Gate C freshness test reactivate"},
        headers={"Authorization": f"Bearer {platform_token}"},
    )
    return resp


def _probe(
    test_client: TestClient,
    token: str,
    company_id: UUID,
    *,
    extra_headers: dict[str, str] | None = None,
) -> Response:
    headers = {"Authorization": f"Bearer {token}"}
    if extra_headers:
        headers.update(extra_headers)
    resp: Response = test_client.get(
        f"/api/v1/companies/{company_id}/inventory/health", headers=headers
    )
    return resp


class TestOldAccessTokenDeniedAfterSuspendReactivate:
    """T095."""

    def test_original_access_token_denied_after_suspend_and_reactivate(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        email = f"t095-{uuid.uuid4().hex[:12]}@example.com"
        password = "T095TestPassword@123"
        _, company = _make_tenant_company_and_member(
            db_session, email=email, password=password
        )
        platform_token = _make_platform_token_with_permissions(
            db_session, {"platform.tenants.suspend", "platform.tenants.reactivate"}
        )

        login = test_client.post(
            "/api/v1/auth/login", json={"email": email, "password": password}
        )
        assert login.status_code == 200
        access_token = login.json()["data"]["access_token"]

        assert _probe(test_client, access_token, company.id).status_code == 200

        assert _suspend(test_client, platform_token, company.id).status_code == 200
        assert _probe(test_client, access_token, company.id).status_code == 403

        assert _reactivate(test_client, platform_token, company.id).status_code == 200
        # The critical assertion: reactivation does NOT resurrect the
        # pre-suspension access token (FR-9A-018).
        assert _probe(test_client, access_token, company.id).status_code == 403


class TestOldRefreshTokenCannotRestoreAccess:
    """T096 — the refresh-bypass regression guard. Must fail if the check
    is ever re-keyed to the new access token's `iat`."""

    def test_refreshed_access_token_still_denied(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        email = f"t096-{uuid.uuid4().hex[:12]}@example.com"
        password = "T096TestPassword@123"
        _, company = _make_tenant_company_and_member(
            db_session, email=email, password=password
        )
        platform_token = _make_platform_token_with_permissions(
            db_session, {"platform.tenants.suspend", "platform.tenants.reactivate"}
        )

        login = test_client.post(
            "/api/v1/auth/login", json={"email": email, "password": password}
        )
        assert login.status_code == 200
        refresh_token = login.json()["data"]["refresh_token"]

        assert _suspend(test_client, platform_token, company.id).status_code == 200
        assert _reactivate(test_client, platform_token, company.id).status_code == 200

        refresh_response = test_client.post(
            "/api/v1/auth/refresh", json={"refresh_token": refresh_token}
        )
        assert refresh_response.status_code == 200
        new_access_token = refresh_response.json()["data"]["access_token"]

        # A refresh reuses the same Session, so authentication time never
        # advances past the watermark, regardless of the new token's iat.
        assert _probe(test_client, new_access_token, company.id).status_code == 403


class TestGenuineNewLoginRestoresAccess:
    """T097."""

    def test_new_login_after_reactivation_restores_access(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        email = f"t097-{uuid.uuid4().hex[:12]}@example.com"
        password = "T097TestPassword@123"
        _, company = _make_tenant_company_and_member(
            db_session, email=email, password=password
        )
        platform_token = _make_platform_token_with_permissions(
            db_session, {"platform.tenants.suspend", "platform.tenants.reactivate"}
        )

        first_login = test_client.post(
            "/api/v1/auth/login", json={"email": email, "password": password}
        )
        assert first_login.status_code == 200

        assert _suspend(test_client, platform_token, company.id).status_code == 200
        assert _reactivate(test_client, platform_token, company.id).status_code == 200

        # The test DB's Session.created_at uses SQLite's whole-second-
        # resolution CURRENT_TIMESTAMP (no fractional seconds), unlike
        # access_invalidated_at's Python-side microsecond-precision
        # datetime.now(UTC) — a real human always logs back in more than
        # a second after suspending a tenant, but this fast automated
        # test needs an explicit gap to avoid a same-second tie landing
        # on the `<=` rule's deny side.
        time.sleep(1.1)

        second_login = test_client.post(
            "/api/v1/auth/login", json={"email": email, "password": password}
        )
        assert second_login.status_code == 200
        new_access_token = second_login.json()["data"]["access_token"]

        assert _probe(test_client, new_access_token, company.id).status_code == 200


class TestMultiDeviceSemantics:
    """T099 (plan.md §10.3.1)."""

    def test_two_devices_denied_then_only_relogged_in_device_restored(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        email = f"t099-{uuid.uuid4().hex[:12]}@example.com"
        password = "T099TestPassword@123"
        user, company_a = _make_tenant_company_and_member(
            db_session, email=email, password=password
        )
        suffix = uuid.uuid4().hex[:10]
        company_b = Company(
            legal_name=f"Freshness Co B {suffix}",
            slug=f"freshness-co-b-{suffix}",
            owner_id=user.id,
            email=f"freshness-co-b-{suffix}@example.test",
            status="active",
        )
        db_session.add(company_b)
        db_session.flush()
        seed_system_roles(db_session, company_b.id)
        create_member_with_role(
            db_session, company_id=company_b.id, user_id=user.id, role_slug="owner"
        )
        db_session.commit()

        platform_token = _make_platform_token_with_permissions(
            db_session, {"platform.tenants.suspend", "platform.tenants.reactivate"}
        )

        device1_login = test_client.post(
            "/api/v1/auth/login", json={"email": email, "password": password}
        )
        device2_login = test_client.post(
            "/api/v1/auth/login", json={"email": email, "password": password}
        )
        assert device1_login.status_code == 200
        assert device2_login.status_code == 200
        device1_token = device1_login.json()["data"]["access_token"]
        device2_token = device2_login.json()["data"]["access_token"]

        # Both devices work on A and B pre-suspension.
        assert _probe(test_client, device1_token, company_a.id).status_code == 200
        assert _probe(test_client, device2_token, company_a.id).status_code == 200

        assert _suspend(test_client, platform_token, company_a.id).status_code == 200
        assert _reactivate(test_client, platform_token, company_a.id).status_code == 200

        # Both denied for A after reactivation.
        assert _probe(test_client, device1_token, company_a.id).status_code == 403
        assert _probe(test_client, device2_token, company_a.id).status_code == 403
        # Both keep B throughout — suspending A never touches B.
        assert _probe(test_client, device1_token, company_b.id).status_code == 200
        assert _probe(test_client, device2_token, company_b.id).status_code == 200

        # Device 1 performs a genuine new login -> regains A, for Device 1 only.
        # See the identical note in TestGenuineNewLoginRestoresAccess about
        # SQLite's whole-second Session.created_at resolution.
        time.sleep(1.1)
        device1_relogin = test_client.post(
            "/api/v1/auth/login", json={"email": email, "password": password}
        )
        assert device1_relogin.status_code == 200
        device1_new_token = device1_relogin.json()["data"]["access_token"]

        assert _probe(test_client, device1_new_token, company_a.id).status_code == 200
        # Device 2's original (pre-suspension) token remains denied.
        assert _probe(test_client, device2_token, company_a.id).status_code == 403
        # Both still keep B.
        assert _probe(test_client, device1_new_token, company_b.id).status_code == 200
        assert _probe(test_client, device2_token, company_b.id).status_code == 200


class TestManipulationCannotFabricateFreshness:
    """T100."""

    def test_decoy_headers_do_not_restore_access(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """Simulates a client sending manipulated
        `erp_active_company_id`-style state via extra headers — the
        server derives authorization solely from the verified session_id
        and the URL path's company_id, never from any client-supplied
        header."""
        email = f"t100-{uuid.uuid4().hex[:12]}@example.com"
        password = "T100TestPassword@123"
        _, company = _make_tenant_company_and_member(
            db_session, email=email, password=password
        )
        platform_token = _make_platform_token_with_permissions(
            db_session, {"platform.tenants.suspend", "platform.tenants.reactivate"}
        )

        login = test_client.post(
            "/api/v1/auth/login", json={"email": email, "password": password}
        )
        access_token = login.json()["data"]["access_token"]

        assert _suspend(test_client, platform_token, company.id).status_code == 200

        response = _probe(
            test_client,
            access_token,
            company.id,
            extra_headers={
                "X-Erp-Active-Company-Id": str(uuid.uuid4()),
                "X-Company-Id": str(uuid.uuid4()),
            },
        )
        assert response.status_code == 403

    def test_no_route_anywhere_accepts_a_client_supplied_created_at_for_sessions(
        self,
    ) -> None:
        """Structural proof: Session.created_at (the authentication-
        freshness value the watermark is compared against) is
        server-generated and unwritable via any API — no request schema
        in modules/auth/ declares a `created_at` field."""
        import inspect

        import modules.auth.schemas as auth_schemas

        offenders = []
        for name, obj in inspect.getmembers(auth_schemas):
            if inspect.isclass(obj) and hasattr(obj, "model_fields"):
                if "created_at" in getattr(obj, "model_fields", {}) and name.endswith(
                    "Request"
                ):
                    offenders.append(name)

        assert offenders == [], (
            f"Request schema(s) accept a client-supplied created_at: {offenders}"
        )
