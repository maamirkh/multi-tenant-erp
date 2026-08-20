"""[T086] [FR-9A-017] A NULL ``access_invalidated_at`` (every company
that predates Epic 9A, and any company that has never been suspended)
denies nothing — rollout safety proof.

Real HTTP, real login, real company + membership. Hits a representative
read endpoint in each of the five business modules through the
``get_current_company_member``-gated mount to prove
``assert_company_access_allowed`` (T083/T084) does not regress existing
tenant access.
"""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from modules.companies.models.company import Company
from tests.fixtures.auth_fixtures import create_test_user
from tests.fixtures.users_roles_fixtures import (
    create_member_with_role,
    seed_system_roles,
)


class TestNullWatermarkAllowsAllFiveBusinessModules:
    def test_null_watermark_company_reaches_all_five_modules(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        email = f"null-watermark-{uuid.uuid4().hex[:12]}@example.com"
        password = "NullWatermarkTest@123"
        user, _ = create_test_user(db_session, email=email, password=password)

        suffix = uuid.uuid4().hex[:10]
        company = Company(
            legal_name=f"Null Watermark Co {suffix}",
            slug=f"null-watermark-co-{suffix}",
            owner_id=user.id,
            email=f"null-watermark-co-{suffix}@example.test",
            status="active",
        )
        db_session.add(company)
        db_session.flush()
        # The property under test: this is the default state for every
        # existing company at Epic 9A rollout time.
        assert company.access_invalidated_at is None

        seed_system_roles(db_session, company.id)
        create_member_with_role(
            db_session, company_id=company.id, user_id=user.id, role_slug="owner"
        )
        db_session.commit()

        login = test_client.post(
            "/api/v1/auth/login", json={"email": email, "password": password}
        )
        assert login.status_code == 200
        token = login.json()["data"]["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        endpoints = [
            f"/api/v1/companies/{company.id}/inventory/health",
            f"/api/v1/companies/{company.id}/purchase/health",
            f"/api/v1/companies/{company.id}/sales/health",
            f"/api/v1/companies/{company.id}/accounting/health",
            f"/api/v1/companies/{company.id}/crm/status",
        ]
        for path in endpoints:
            response = test_client.get(path, headers=headers)
            assert (
                response.status_code == 200
            ), f"{path} -> {response.status_code}: {response.text}"
