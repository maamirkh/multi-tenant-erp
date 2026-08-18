"""Feature-flag enabled/disabled test matrix — every CRM resource group,
flag on vs off (T078).

FR-020/plan.md §21.5: extends T010's early manual check into a permanent
automated test. For a representative endpoint in each of the 6 resource
groups: flag off -> documented error response (403, ``FEATURE_DISABLED``
— never a 404/500); flag on -> normal behavior (the gate no longer
blocks the request).

``crm_client`` (the shared fixture used by every other CRM API test file)
deliberately does NOT apply ``require_crm_enabled`` at its
``include_router()`` call — that production wiring is Phase 9's T079.
This file builds its own, separate ``flag_gated_client`` fixture that DOES
apply the gate, exactly matching what T079's real mounting will look
like, without touching the shared ``crm_client`` fixture every other
Phase 3-7 test file already depends on (changing that shared fixture's
behavior would break dozens of already-passing tests that never enable
the flag).

Task: T078 (tasks.md Phase 8).
"""

from __future__ import annotations

from collections.abc import Generator
from unittest.mock import patch
from uuid import uuid4

import pytest
from fastapi import Depends
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from core.config.settings import Settings
from core.database.session import get_db
from modules.crm.dependencies import require_crm_enabled
from modules.crm.repositories.feature_flag_repository import CrmFeatureFlagRepository
from modules.crm.services.feature_flag_service import CrmFeatureFlagService
from modules.sales.models.customer import Customer
from modules.sales.models.master import CustomerCategory
from modules.sales.repositories.customer import CustomerRepository
from modules.sales.repositories.master import CustomerCategoryRepository
from tests.fixtures.auth_fixtures import create_test_user
from tests.integration.api.v1.crm.conftest import (
    _TEST_ARGON2_KWARGS,
    auth_header,
    create_company,
    crm_url,
    login,
)


@pytest.fixture
def flag_gated_client(db_session: Session) -> Generator[TestClient, None, None]:
    """Identical to ``crm_client`` but mounts ``crm_router`` WITH the
    ``require_crm_enabled`` dependency applied at include-time — the
    exact shape of Phase 9's real production mounting (plan.md §21.5)."""
    from main import create_app
    from modules.crm.router import router as crm_router

    def override_get_db() -> Generator[Session, None, None]:
        yield db_session

    app = create_app(
        Settings(
            DATABASE_URL="sqlite:///:memory:",
            SECRET_KEY="test-secret-key-minimum-32-chars-ok",
            JWT_SECRET_KEY="test-jwt-secret-key-min-32-chars-ok!",
            ENVIRONMENT="testing",
            DEBUG=True,
            JWT_ACCESS_TOKEN_EXPIRE_MINUTES=1440,
            **_TEST_ARGON2_KWARGS,
        )
    )
    app.include_router(
        crm_router,
        prefix="/api/v1/companies/{company_id}/crm",
        dependencies=[Depends(require_crm_enabled)],
    )
    app.dependency_overrides[get_db] = override_get_db

    with patch("main.run_migrations"):
        with TestClient(app, raise_server_exceptions=False) as client:
            yield client

    app.dependency_overrides.clear()


def _enable_crm(db_session: Session, company_id: str) -> None:
    from uuid import UUID

    service = CrmFeatureFlagService(
        db=db_session, flag_repo=CrmFeatureFlagRepository(db_session)
    )
    service.enable(UUID(company_id))


def _create_customer(db_session: Session, company_id: str) -> str:
    from uuid import UUID

    cid = UUID(company_id)
    category = CustomerCategoryRepository(db_session).create(
        CustomerCategory(
            company_id=cid, code=f"CAT-{uuid4().hex[:6]}", name="Flag Gate Test"
        )
    )
    customer = CustomerRepository(db_session).create(
        Customer(
            company_id=cid,
            customer_code=f"CUST-{uuid4().hex[:8]}",
            legal_name="Flag Gate Test Customer",
            customer_type="COMPANY",
            category_id=str(category.id),
            currency_code="USD",
            status="ACTIVE",
        )
    )
    return str(customer.id)


def _new_owner_and_token(client: TestClient, db_session: Session) -> tuple[str, str]:
    email = f"flaggate-{uuid4().hex[:8]}@example.com"
    user, password = create_test_user(db_session, email)
    token = login(client, email, password)
    return str(user.id), token


@pytest.mark.parametrize(
    "group,path",
    [
        ("Leads", "/leads"),
        ("LeadSources", "/lead-sources"),
        ("Pipelines", "/pipelines"),
        ("Opportunities", "/opportunities"),
        ("Activities", "/activities"),
    ],
)
class TestFeatureFlagGateListEndpoints:
    def test_flag_off_returns_documented_403(
        self, flag_gated_client: TestClient, db_session: Session, group: str, path: str
    ) -> None:
        _, token = _new_owner_and_token(flag_gated_client, db_session)
        company_id = create_company(flag_gated_client, token)

        resp = flag_gated_client.get(
            crm_url(company_id, path), headers=auth_header(token)
        )

        assert resp.status_code == 403, resp.text
        body = resp.json()
        assert body["error"]["code"] == "FEATURE_DISABLED"

    def test_flag_on_passes_through(
        self, flag_gated_client: TestClient, db_session: Session, group: str, path: str
    ) -> None:
        _, token = _new_owner_and_token(flag_gated_client, db_session)
        company_id = create_company(flag_gated_client, token)
        _enable_crm(db_session, company_id)

        resp = flag_gated_client.get(
            crm_url(company_id, path), headers=auth_header(token)
        )

        assert resp.status_code == 200, resp.text


class TestFeatureFlagGateCustomer360:
    """The 6th resource group: Customer 360/Reports."""

    def test_flag_off_returns_documented_403(
        self, flag_gated_client: TestClient, db_session: Session
    ) -> None:
        _, token = _new_owner_and_token(flag_gated_client, db_session)
        company_id = create_company(flag_gated_client, token)
        customer_id = _create_customer(db_session, company_id)

        resp = flag_gated_client.get(
            crm_url(company_id, f"/customers/{customer_id}/360"),
            headers=auth_header(token),
        )

        assert resp.status_code == 403, resp.text
        body = resp.json()
        assert body["error"]["code"] == "FEATURE_DISABLED"

    def test_flag_on_passes_through(
        self, flag_gated_client: TestClient, db_session: Session
    ) -> None:
        _, token = _new_owner_and_token(flag_gated_client, db_session)
        company_id = create_company(flag_gated_client, token)
        _enable_crm(db_session, company_id)
        customer_id = _create_customer(db_session, company_id)

        resp = flag_gated_client.get(
            crm_url(company_id, f"/customers/{customer_id}/360"),
            headers=auth_header(token),
        )

        assert resp.status_code == 200, resp.text
