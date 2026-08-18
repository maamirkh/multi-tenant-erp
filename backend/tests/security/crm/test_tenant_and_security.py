"""T096 — CRM Security test suite: all 12 SEC-01-SEC-12 cases (spec.md §46).

Every case here is asserted as a real HTTP request against the live-mounted
CRM router (via the shared ``crm_client`` fixture), matching plan.md
§27.3/§27.4's explicit "exhaustive, not spot-checked" requirement — a
dedicated file distinct from ``test_rbac.py``'s 152-cell permission
matrix (T063/T066) and from the individual CRUD test files' incidental
tenant-isolation checks, gathering all 12 documented security cases from
spec.md §46 in one place for Epic-9 closure verification.

Task: T096 (tasks.md Phase 10). Spec ref: spec.md §46.
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
    email = unique_email()
    user, password = create_test_user(db_session, email)
    create_member_with_role(
        db_session,
        company_id=UUID(company_id),
        user_id=user.id,
        role_slug=role_slug,
    )
    return str(user.id), login(client, email, password)


def _current_user_id(client: TestClient, token: str) -> str:
    resp = client.get("/api/v1/profile", headers=auth_header(token))
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]["id"]


def _create_customer(client: TestClient, db_session: Session, company_id: str) -> str:
    cid = UUID(company_id)
    category = CustomerCategoryRepository(db_session).create(
        CustomerCategory(
            company_id=cid, code=f"CAT-{uuid4().hex[:6]}", name="Security Test Category"
        )
    )
    customer = CustomerRepository(db_session).create(
        Customer(
            company_id=cid,
            customer_code=f"CUST-{uuid4().hex[:8]}",
            legal_name="Security Test Customer",
            customer_type="COMPANY",
            category_id=str(category.id),
            currency_code="USD",
            status="ACTIVE",
        )
    )
    return str(customer.id)


def _create_lead(
    client: TestClient, company_id: str, token: str, **overrides: object
) -> str:
    payload = {
        "first_name": "Sec",
        "last_name": "Test",
        "email": f"sec-test-{uuid4().hex[:8]}@example.com",
    }
    payload.update(overrides)
    resp = client.post(
        crm_url(company_id, "/leads"), json=payload, headers=auth_header(token)
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]["id"]


def _qualify_lead(
    client: TestClient, company_id: str, lead_id: str, token: str
) -> None:
    resp = client.patch(
        crm_url(company_id, f"/leads/{lead_id}"),
        json={"status": "CONTACTED"},
        headers=auth_header(token),
    )
    assert resp.status_code == 200, resp.text
    resp = client.patch(
        crm_url(company_id, f"/leads/{lead_id}"),
        json={"status": "QUALIFIED", "qualification_notes": "Confirmed"},
        headers=auth_header(token),
    )
    assert resp.status_code == 200, resp.text


def _setup_pipeline_and_stage(
    client: TestClient, company_id: str, token: str
) -> tuple[str, str]:
    pipeline_id = client.post(
        crm_url(company_id, "/pipelines"),
        json={"name": f"Sec Pipeline {uuid4().hex[:6]}", "is_default": True},
        headers=auth_header(token),
    ).json()["data"]["id"]
    stage_id = client.post(
        crm_url(company_id, f"/pipelines/{pipeline_id}/stages"),
        json={"name": "Qualification", "sequence": 1, "probability": 20},
        headers=auth_header(token),
    ).json()["data"]["id"]
    return pipeline_id, stage_id


def _create_opportunity(
    client: TestClient,
    company_id: str,
    token: str,
    customer_id: str,
    owner_id: str,
    pipeline_id: str,
    stage_id: str,
    **overrides: object,
) -> str:
    payload = {
        "name": "Sec Test Deal",
        "customer_id": customer_id,
        "owner_id": owner_id,
        "pipeline_id": pipeline_id,
        "stage_id": stage_id,
        "currency_code": "USD",
        "value": "5000",
    }
    payload.update(overrides)
    resp = client.post(
        crm_url(company_id, "/opportunities"), json=payload, headers=auth_header(token)
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]["id"]


def _create_activity(
    client: TestClient, company_id: str, token: str, assigned_to: str, lead_id: str
) -> str:
    resp = client.post(
        crm_url(company_id, "/activities"),
        json={
            "activity_type": "CALL",
            "subject": "Sec test activity",
            "assigned_to": assigned_to,
            "lead_id": lead_id,
        },
        headers=auth_header(token),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]["id"]


# ---------------------------------------------------------------------------
# SEC-01 — Unauthenticated request to any /crm/* endpoint -> 401
# ---------------------------------------------------------------------------


class TestSec01Unauthenticated:
    def test_unauthenticated_requests_return_401(
        self, crm_client: TestClient, db_session: Session
    ) -> None:
        _, token = new_user_and_token(crm_client, db_session)
        company_id = create_company(crm_client, token)

        endpoints = [
            ("GET", "/leads"),
            ("POST", "/leads"),
            ("GET", "/opportunities"),
            ("POST", "/opportunities"),
            ("GET", "/activities"),
            ("GET", "/pipelines"),
            ("GET", "/dashboard"),
            ("GET", "/reports/pipeline"),
        ]
        for method, path in endpoints:
            resp = crm_client.request(method, crm_url(company_id, path), json={})
            assert resp.status_code == 401, f"{method} {path}: {resp.text}"


# ---------------------------------------------------------------------------
# SEC-02 — Authenticated user without the specific crm.* permission -> 403
# ---------------------------------------------------------------------------


class TestSec02PermissionDenied:
    def test_denied_role_gets_403(
        self, crm_client: TestClient, db_session: Session
    ) -> None:
        _, owner_token = new_user_and_token(crm_client, db_session)
        company_id = create_company(crm_client, owner_token)
        _, cashier_token = _add_member_and_login(
            crm_client, db_session, company_id, "cashier"
        )

        resp = crm_client.post(
            crm_url(company_id, "/leads"),
            json={"first_name": "X", "email": "x@example.com"},
            headers=auth_header(cashier_token),
        )
        assert resp.status_code == 403, resp.text


# ---------------------------------------------------------------------------
# SEC-03/04/05 — Cross-tenant GET/UPDATE/DELETE of Lead/Opportunity/Activity
# by ID -> 404
# ---------------------------------------------------------------------------


class TestSec03Sec04Sec05CrossTenantAccess:
    def test_cross_tenant_lead_get_update_delete_return_404(
        self, crm_client: TestClient, db_session: Session
    ) -> None:
        _, token_a = new_user_and_token(crm_client, db_session)
        company_a = create_company(crm_client, token_a)
        lead_id = _create_lead(crm_client, company_a, token_a)

        _, token_b = new_user_and_token(crm_client, db_session)
        company_b = create_company(crm_client, token_b)

        get_resp = crm_client.get(
            crm_url(company_b, f"/leads/{lead_id}"), headers=auth_header(token_b)
        )
        assert get_resp.status_code == 404, get_resp.text

        update_resp = crm_client.patch(
            crm_url(company_b, f"/leads/{lead_id}"),
            json={"status": "CONTACTED"},
            headers=auth_header(token_b),
        )
        assert update_resp.status_code == 404, update_resp.text

        delete_resp = crm_client.delete(
            crm_url(company_b, f"/leads/{lead_id}"), headers=auth_header(token_b)
        )
        assert delete_resp.status_code == 404, delete_resp.text

    def test_cross_tenant_opportunity_get_update_delete_return_404(
        self, crm_client: TestClient, db_session: Session
    ) -> None:
        _, token_a = new_user_and_token(crm_client, db_session)
        company_a = create_company(crm_client, token_a)
        pipeline_id, stage_id = _setup_pipeline_and_stage(
            crm_client, company_a, token_a
        )
        owner_id = _current_user_id(crm_client, token_a)
        customer_id = _create_customer(crm_client, db_session, company_a)
        opportunity_id = _create_opportunity(
            crm_client, company_a, token_a, customer_id, owner_id, pipeline_id, stage_id
        )

        _, token_b = new_user_and_token(crm_client, db_session)
        company_b = create_company(crm_client, token_b)

        get_resp = crm_client.get(
            crm_url(company_b, f"/opportunities/{opportunity_id}"),
            headers=auth_header(token_b),
        )
        assert get_resp.status_code == 404, get_resp.text

        update_resp = crm_client.patch(
            crm_url(company_b, f"/opportunities/{opportunity_id}"),
            json={"description": "hijacked"},
            headers=auth_header(token_b),
        )
        assert update_resp.status_code == 404, update_resp.text

        delete_resp = crm_client.delete(
            crm_url(company_b, f"/opportunities/{opportunity_id}"),
            headers=auth_header(token_b),
        )
        assert delete_resp.status_code == 404, delete_resp.text

    def test_cross_tenant_activity_get_update_delete_return_404(
        self, crm_client: TestClient, db_session: Session
    ) -> None:
        _, token_a = new_user_and_token(crm_client, db_session)
        company_a = create_company(crm_client, token_a)
        assigned_to = _current_user_id(crm_client, token_a)
        lead_id = _create_lead(crm_client, company_a, token_a)
        activity_id = _create_activity(
            crm_client, company_a, token_a, assigned_to, lead_id
        )

        _, token_b = new_user_and_token(crm_client, db_session)
        company_b = create_company(crm_client, token_b)

        get_resp = crm_client.get(
            crm_url(company_b, f"/activities/{activity_id}"),
            headers=auth_header(token_b),
        )
        assert get_resp.status_code == 404, get_resp.text

        update_resp = crm_client.patch(
            crm_url(company_b, f"/activities/{activity_id}"),
            json={"subject": "hijacked"},
            headers=auth_header(token_b),
        )
        assert update_resp.status_code == 404, update_resp.text

        delete_resp = crm_client.delete(
            crm_url(company_b, f"/activities/{activity_id}"),
            headers=auth_header(token_b),
        )
        assert delete_resp.status_code == 404, delete_resp.text


# ---------------------------------------------------------------------------
# SEC-06 — Opportunity create with a customer_id belonging to another
# tenant -> 422
# ---------------------------------------------------------------------------


class TestSec06ForeignEntityCompanyValidation:
    def test_opportunity_create_with_cross_tenant_customer_id_returns_422(
        self, crm_client: TestClient, db_session: Session
    ) -> None:
        _, token_a = new_user_and_token(crm_client, db_session)
        company_a = create_company(crm_client, token_a)
        pipeline_id, stage_id = _setup_pipeline_and_stage(
            crm_client, company_a, token_a
        )
        owner_id = _current_user_id(crm_client, token_a)

        _, token_b = new_user_and_token(crm_client, db_session)
        company_b = create_company(crm_client, token_b)
        foreign_customer_id = _create_customer(crm_client, db_session, company_b)

        resp = crm_client.post(
            crm_url(company_a, "/opportunities"),
            json={
                "name": "Foreign Customer Deal",
                "customer_id": foreign_customer_id,
                "owner_id": owner_id,
                "pipeline_id": pipeline_id,
                "stage_id": stage_id,
                "currency_code": "USD",
                "value": "1000",
            },
            headers=auth_header(token_a),
        )
        assert resp.status_code == 422, resp.text


# ---------------------------------------------------------------------------
# SEC-07 — Lead convert with a manually-forged converted_customer_id in the
# request body -> field ignored/rejected; conversion always computes it
# server-side
# ---------------------------------------------------------------------------


class TestSec07ForgedConversionField:
    def test_forged_converted_customer_id_in_body_is_ignored(
        self, crm_client: TestClient, db_session: Session
    ) -> None:
        _, token = new_user_and_token(crm_client, db_session)
        company_id = create_company(crm_client, token)
        lead_id = _create_lead(crm_client, company_id, token)
        _qualify_lead(crm_client, company_id, lead_id, token)

        forged_customer_id = str(uuid4())
        resp = crm_client.post(
            crm_url(company_id, f"/leads/{lead_id}/convert"),
            json={"converted_customer_id": forged_customer_id},
            headers=auth_header(token),
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        # The endpoint accepts no request body at all — any JSON sent is
        # inert; the returned customer_id is always server-computed, never
        # the forged value.
        assert data["customer_id"] != forged_customer_id


# ---------------------------------------------------------------------------
# SEC-08 — Activity create with a lead_id/opportunity_id belonging to
# another tenant -> 422
# ---------------------------------------------------------------------------


class TestSec08ActivityForeignEntity:
    def test_activity_create_with_cross_tenant_lead_id_returns_422(
        self, crm_client: TestClient, db_session: Session
    ) -> None:
        _, token_a = new_user_and_token(crm_client, db_session)
        company_a = create_company(crm_client, token_a)
        assigned_to = _current_user_id(crm_client, token_a)

        _, token_b = new_user_and_token(crm_client, db_session)
        company_b = create_company(crm_client, token_b)
        foreign_lead_id = _create_lead(crm_client, company_b, token_b)

        resp = crm_client.post(
            crm_url(company_a, "/activities"),
            json={
                "activity_type": "CALL",
                "subject": "Foreign lead activity",
                "assigned_to": assigned_to,
                "lead_id": foreign_lead_id,
            },
            headers=auth_header(token_a),
        )
        assert resp.status_code == 422, resp.text

    def test_activity_create_with_cross_tenant_opportunity_id_returns_422(
        self, crm_client: TestClient, db_session: Session
    ) -> None:
        _, token_a = new_user_and_token(crm_client, db_session)
        company_a = create_company(crm_client, token_a)
        assigned_to = _current_user_id(crm_client, token_a)

        _, token_b = new_user_and_token(crm_client, db_session)
        company_b = create_company(crm_client, token_b)
        pipeline_id, stage_id = _setup_pipeline_and_stage(
            crm_client, company_b, token_b
        )
        owner_id_b = _current_user_id(crm_client, token_b)
        customer_id_b = _create_customer(crm_client, db_session, company_b)
        foreign_opportunity_id = _create_opportunity(
            crm_client,
            company_b,
            token_b,
            customer_id_b,
            owner_id_b,
            pipeline_id,
            stage_id,
        )

        resp = crm_client.post(
            crm_url(company_a, "/activities"),
            json={
                "activity_type": "CALL",
                "subject": "Foreign opportunity activity",
                "assigned_to": assigned_to,
                "opportunity_id": foreign_opportunity_id,
            },
            headers=auth_header(token_a),
        )
        assert resp.status_code == 422, resp.text


# ---------------------------------------------------------------------------
# SEC-09 — Invalid state transition -> 409
# ---------------------------------------------------------------------------


class TestSec09InvalidStateTransition:
    def test_convert_new_lead_returns_409(
        self, crm_client: TestClient, db_session: Session
    ) -> None:
        _, token = new_user_and_token(crm_client, db_session)
        company_id = create_company(crm_client, token)
        lead_id = _create_lead(crm_client, company_id, token)

        resp = crm_client.post(
            crm_url(company_id, f"/leads/{lead_id}/convert"), headers=auth_header(token)
        )
        assert resp.status_code == 409, resp.text

    def test_win_already_won_opportunity_returns_409(
        self, crm_client: TestClient, db_session: Session
    ) -> None:
        _, token = new_user_and_token(crm_client, db_session)
        company_id = create_company(crm_client, token)
        pipeline_id, stage_id = _setup_pipeline_and_stage(crm_client, company_id, token)
        owner_id = _current_user_id(crm_client, token)
        customer_id = _create_customer(crm_client, db_session, company_id)
        opportunity_id = _create_opportunity(
            crm_client, company_id, token, customer_id, owner_id, pipeline_id, stage_id
        )

        first_win = crm_client.post(
            crm_url(company_id, f"/opportunities/{opportunity_id}/win"),
            headers=auth_header(token),
        )
        assert first_win.status_code == 200, first_win.text

        second_win = crm_client.post(
            crm_url(company_id, f"/opportunities/{opportunity_id}/win"),
            headers=auth_header(token),
        )
        assert second_win.status_code == 409, second_win.text


# ---------------------------------------------------------------------------
# SEC-10 — Duplicate/repeated lead conversion -> 200 with existing result,
# not a duplicate
# ---------------------------------------------------------------------------


class TestSec10IdempotentConversion:
    def test_repeated_conversion_returns_same_result_no_duplicate(
        self, crm_client: TestClient, db_session: Session
    ) -> None:
        _, token = new_user_and_token(crm_client, db_session)
        company_id = create_company(crm_client, token)
        lead_id = _create_lead(crm_client, company_id, token)
        _qualify_lead(crm_client, company_id, lead_id, token)

        first = crm_client.post(
            crm_url(company_id, f"/leads/{lead_id}/convert"), headers=auth_header(token)
        )
        second = crm_client.post(
            crm_url(company_id, f"/leads/{lead_id}/convert"), headers=auth_header(token)
        )

        assert first.status_code == 200, first.text
        assert second.status_code == 200, second.text
        assert first.json()["data"] == second.json()["data"]


# ---------------------------------------------------------------------------
# SEC-11 — Unauthorized assignment (assign without crm.leads.assign /
# crm.opportunities.assign) -> 403
# ---------------------------------------------------------------------------


class TestSec11UnauthorizedAssignment:
    def test_lead_assign_without_permission_returns_403(
        self, crm_client: TestClient, db_session: Session
    ) -> None:
        _, owner_token = new_user_and_token(crm_client, db_session)
        company_id = create_company(crm_client, owner_token)
        lead_id = _create_lead(crm_client, company_id, owner_token)
        target_user_id, _ = _add_member_and_login(
            crm_client, db_session, company_id, "salesperson"
        )
        _, cashier_token = _add_member_and_login(
            crm_client, db_session, company_id, "cashier"
        )

        resp = crm_client.post(
            crm_url(company_id, f"/leads/{lead_id}/assign"),
            json={"owner_id": target_user_id},
            headers=auth_header(cashier_token),
        )
        assert resp.status_code == 403, resp.text

    def test_opportunity_assign_without_permission_returns_403(
        self, crm_client: TestClient, db_session: Session
    ) -> None:
        _, owner_token = new_user_and_token(crm_client, db_session)
        company_id = create_company(crm_client, owner_token)
        pipeline_id, stage_id = _setup_pipeline_and_stage(
            crm_client, company_id, owner_token
        )
        owner_id = _current_user_id(crm_client, owner_token)
        customer_id = _create_customer(crm_client, db_session, company_id)
        opportunity_id = _create_opportunity(
            crm_client,
            company_id,
            owner_token,
            customer_id,
            owner_id,
            pipeline_id,
            stage_id,
        )
        target_user_id, _ = _add_member_and_login(
            crm_client, db_session, company_id, "salesperson"
        )
        _, cashier_token = _add_member_and_login(
            crm_client, db_session, company_id, "cashier"
        )

        resp = crm_client.post(
            crm_url(company_id, f"/opportunities/{opportunity_id}/assign"),
            json={"owner_id": target_user_id},
            headers=auth_header(cashier_token),
        )
        assert resp.status_code == 403, resp.text


# ---------------------------------------------------------------------------
# SEC-12 — Assign a lead/opportunity to a user who is not an active member
# of the company -> 422
# ---------------------------------------------------------------------------


class TestSec12AssignToNonMember:
    def test_lead_assign_to_non_member_returns_422(
        self, crm_client: TestClient, db_session: Session
    ) -> None:
        _, token = new_user_and_token(crm_client, db_session)
        company_id = create_company(crm_client, token)
        lead_id = _create_lead(crm_client, company_id, token)

        non_member_email = unique_email()
        non_member, _ = create_test_user(db_session, non_member_email)

        resp = crm_client.post(
            crm_url(company_id, f"/leads/{lead_id}/assign"),
            json={"owner_id": str(non_member.id)},
            headers=auth_header(token),
        )
        assert resp.status_code == 422, resp.text

    def test_opportunity_assign_to_non_member_returns_422(
        self, crm_client: TestClient, db_session: Session
    ) -> None:
        _, token = new_user_and_token(crm_client, db_session)
        company_id = create_company(crm_client, token)
        pipeline_id, stage_id = _setup_pipeline_and_stage(crm_client, company_id, token)
        owner_id = _current_user_id(crm_client, token)
        customer_id = _create_customer(crm_client, db_session, company_id)
        opportunity_id = _create_opportunity(
            crm_client, company_id, token, customer_id, owner_id, pipeline_id, stage_id
        )

        non_member_email = unique_email()
        non_member, _ = create_test_user(db_session, non_member_email)

        resp = crm_client.post(
            crm_url(company_id, f"/opportunities/{opportunity_id}/assign"),
            json={"owner_id": str(non_member.id)},
            headers=auth_header(token),
        )
        assert resp.status_code == 422, resp.text
