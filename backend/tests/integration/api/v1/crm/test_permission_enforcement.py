"""API test: permission-denied (403) + permission-granted for a
representative endpoint from each of the 6 resource groups — T066.

Confirms T065's wiring is live at the HTTP layer (T063 already tests the
``user_has_crm_permission()`` helper in isolation; this exercises the
actual router). One denied-role request (403) + one authorized-role
request (success) per group, per the input brief's explicit pairing
requirement.

Groups: Leads, Lead Sources, Pipelines/Stages, Opportunities, Activities,
Customer 360/Reports.

Task: T066 (tasks.md Phase 8).
"""

from __future__ import annotations

from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from modules.sales.models.customer import Customer
from modules.sales.models.master import CustomerCategory
from modules.sales.repositories.customer import CustomerRepository
from modules.sales.repositories.master import CustomerCategoryRepository
from tests.fixtures.auth_fixtures import create_test_user
from tests.fixtures.users_roles_fixtures import create_member_with_role
from tests.integration.api.v1.crm.conftest import (
    auth_header,
    create_company,
    crm_url,
    login,
    new_user_and_token,
    unique_email,
)


def _add_member_and_login(
    client: TestClient, db_session: Session, company_id: str, role_slug: str
) -> tuple[str, str]:
    """Create a user, grant them ``role_slug`` in ``company_id``, log in.

    Returns (user_id, access_token).
    """
    email = unique_email()
    user, password = create_test_user(db_session, email)
    create_member_with_role(
        db_session,
        company_id=UUID(company_id),
        user_id=user.id,
        role_slug=role_slug,
    )
    return str(user.id), login(client, email, password)


def _create_customer(db_session: Session, company_id: str) -> str:
    cid = UUID(company_id)
    category = CustomerCategoryRepository(db_session).create(
        CustomerCategory(
            company_id=cid, code=f"CAT-{uuid4().hex[:6]}", name="Perm Test Category"
        )
    )
    customer = CustomerRepository(db_session).create(
        Customer(
            company_id=cid,
            customer_code=f"CUST-{uuid4().hex[:8]}",
            legal_name="Permission Test Customer",
            customer_type="COMPANY",
            category_id=str(category.id),
            currency_code="USD",
            status="ACTIVE",
        )
    )
    return str(customer.id)


class TestLeadsPermission:
    """GET /crm/leads requires crm.leads.view."""

    def test_denied_role_gets_403(
        self, crm_client: TestClient, db_session: Session
    ) -> None:
        _, owner_token = new_user_and_token(crm_client, db_session)
        company_id = create_company(crm_client, owner_token)
        _, cashier_token = _add_member_and_login(
            crm_client, db_session, company_id, "cashier"
        )

        resp = crm_client.get(
            crm_url(company_id, "/leads"), headers=auth_header(cashier_token)
        )

        assert resp.status_code == 403, resp.text

    def test_granted_role_succeeds(
        self, crm_client: TestClient, db_session: Session
    ) -> None:
        _, owner_token = new_user_and_token(crm_client, db_session)
        company_id = create_company(crm_client, owner_token)
        _, viewer_token = _add_member_and_login(
            crm_client, db_session, company_id, "viewer"
        )

        resp = crm_client.get(
            crm_url(company_id, "/leads"), headers=auth_header(viewer_token)
        )

        assert resp.status_code == 200, resp.text


class TestLeadSourcesPermission:
    """POST /crm/lead-sources requires crm.pipeline.manage."""

    def test_denied_role_gets_403(
        self, crm_client: TestClient, db_session: Session
    ) -> None:
        _, owner_token = new_user_and_token(crm_client, db_session)
        company_id = create_company(crm_client, owner_token)
        _, salesperson_token = _add_member_and_login(
            crm_client, db_session, company_id, "salesperson"
        )

        resp = crm_client.post(
            crm_url(company_id, "/lead-sources"),
            json={"code": "WEB", "name": "Website"},
            headers=auth_header(salesperson_token),
        )

        assert resp.status_code == 403, resp.text

    def test_granted_role_succeeds(
        self, crm_client: TestClient, db_session: Session
    ) -> None:
        _, owner_token = new_user_and_token(crm_client, db_session)
        company_id = create_company(crm_client, owner_token)

        resp = crm_client.post(
            crm_url(company_id, "/lead-sources"),
            json={"code": "WEB", "name": "Website"},
            headers=auth_header(owner_token),
        )

        assert resp.status_code == 201, resp.text


class TestPipelinesPermission:
    """GET /crm/pipelines requires crm.pipeline.view."""

    def test_denied_role_gets_403(
        self, crm_client: TestClient, db_session: Session
    ) -> None:
        _, owner_token = new_user_and_token(crm_client, db_session)
        company_id = create_company(crm_client, owner_token)
        _, cashier_token = _add_member_and_login(
            crm_client, db_session, company_id, "cashier"
        )

        resp = crm_client.get(
            crm_url(company_id, "/pipelines"), headers=auth_header(cashier_token)
        )

        assert resp.status_code == 403, resp.text

    def test_granted_role_succeeds(
        self, crm_client: TestClient, db_session: Session
    ) -> None:
        _, owner_token = new_user_and_token(crm_client, db_session)
        company_id = create_company(crm_client, owner_token)
        _, viewer_token = _add_member_and_login(
            crm_client, db_session, company_id, "viewer"
        )

        resp = crm_client.get(
            crm_url(company_id, "/pipelines"), headers=auth_header(viewer_token)
        )

        assert resp.status_code == 200, resp.text


class TestOpportunitiesPermission:
    """GET /crm/opportunities requires crm.opportunities.view."""

    def test_denied_role_gets_403(
        self, crm_client: TestClient, db_session: Session
    ) -> None:
        _, owner_token = new_user_and_token(crm_client, db_session)
        company_id = create_company(crm_client, owner_token)
        _, cashier_token = _add_member_and_login(
            crm_client, db_session, company_id, "cashier"
        )

        resp = crm_client.get(
            crm_url(company_id, "/opportunities"), headers=auth_header(cashier_token)
        )

        assert resp.status_code == 403, resp.text

    def test_granted_role_succeeds(
        self, crm_client: TestClient, db_session: Session
    ) -> None:
        _, owner_token = new_user_and_token(crm_client, db_session)
        company_id = create_company(crm_client, owner_token)
        _, salesperson_token = _add_member_and_login(
            crm_client, db_session, company_id, "salesperson"
        )

        resp = crm_client.get(
            crm_url(company_id, "/opportunities"),
            headers=auth_header(salesperson_token),
        )

        assert resp.status_code == 200, resp.text


class TestActivitiesPermission:
    """POST /crm/activities requires crm.activities.create."""

    def test_denied_role_gets_403(
        self, crm_client: TestClient, db_session: Session
    ) -> None:
        _, owner_token = new_user_and_token(crm_client, db_session)
        company_id = create_company(crm_client, owner_token)
        _, accountant_token = _add_member_and_login(
            crm_client, db_session, company_id, "accountant"
        )
        customer_id = _create_customer(db_session, company_id)

        resp = crm_client.post(
            crm_url(company_id, "/activities"),
            json={
                "activity_type": "CALL",
                "subject": "Denied attempt",
                "customer_id": customer_id,
                "assigned_to": str(uuid4()),
            },
            headers=auth_header(accountant_token),
        )

        assert resp.status_code == 403, resp.text

    def test_granted_role_succeeds(
        self, crm_client: TestClient, db_session: Session
    ) -> None:
        _, owner_token = new_user_and_token(crm_client, db_session)
        company_id = create_company(crm_client, owner_token)
        salesperson_id, salesperson_token = _add_member_and_login(
            crm_client, db_session, company_id, "salesperson"
        )
        customer_id = _create_customer(db_session, company_id)

        resp = crm_client.post(
            crm_url(company_id, "/activities"),
            json={
                "activity_type": "CALL",
                "subject": "Granted attempt",
                "customer_id": customer_id,
                "assigned_to": salesperson_id,
            },
            headers=auth_header(salesperson_token),
        )

        assert resp.status_code == 201, resp.text


class TestCustomer360Permission:
    """GET /crm/customers/{id}/360 requires BOTH crm.opportunities.view
    AND crm.activities.view (spec.md §38.6's explicit dual-permission
    design)."""

    def test_denied_role_gets_403(
        self, crm_client: TestClient, db_session: Session
    ) -> None:
        _, owner_token = new_user_and_token(crm_client, db_session)
        company_id = create_company(crm_client, owner_token)
        _, cashier_token = _add_member_and_login(
            crm_client, db_session, company_id, "cashier"
        )
        customer_id = _create_customer(db_session, company_id)

        resp = crm_client.get(
            crm_url(company_id, f"/customers/{customer_id}/360"),
            headers=auth_header(cashier_token),
        )

        assert resp.status_code == 403, resp.text

    def test_granted_role_succeeds(
        self, crm_client: TestClient, db_session: Session
    ) -> None:
        _, owner_token = new_user_and_token(crm_client, db_session)
        company_id = create_company(crm_client, owner_token)
        customer_id = _create_customer(db_session, company_id)

        resp = crm_client.get(
            crm_url(company_id, f"/customers/{customer_id}/360"),
            headers=auth_header(owner_token),
        )

        assert resp.status_code == 200, resp.text
