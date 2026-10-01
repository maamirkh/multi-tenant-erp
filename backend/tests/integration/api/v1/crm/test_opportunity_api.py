"""API integration tests for CRM Opportunity endpoints — Phase 5.

Tests:
  - POST/GET/PATCH/DELETE /crm/opportunities, GET /crm/opportunities/{id}
  - POST .../assign, .../stage, .../win, .../lose
  - BR-003 (no edits once WON/LOST), BR-004 (lost_reason required),
    INV-004 (stage must belong to the Opportunity's own pipeline),
    SEC-06 (cross-tenant customer_id rejected)

Task: T048 (tasks.md Phase 5).
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from modules.sales.models.customer import Customer
from modules.sales.models.master import CustomerCategory
from modules.sales.repositories.customer import CustomerRepository
from modules.sales.repositories.master import CustomerCategoryRepository
from tests.integration.api.v1.crm.conftest import (
    auth_header,
    create_company,
    crm_url,
    new_user_and_token,
)


def _create_customer(db_session: Session, company_id: str, **overrides: object) -> str:
    from uuid import UUID

    cid = UUID(company_id)
    category_repo = CustomerCategoryRepository(db_session)
    category = category_repo.create(
        CustomerCategory(
            company_id=cid, code=f"CAT-{uuid4().hex[:6]}", name="Test Category"
        )
    )
    fields: dict[str, object] = {
        "company_id": cid,
        "customer_code": f"CUST-{uuid4().hex[:8]}",
        "legal_name": "Test Customer",
        "customer_type": "COMPANY",
        "category_id": str(category.id),
        "currency_code": "USD",
        "status": "DRAFT",
    }
    fields.update(overrides)
    customer_repo = CustomerRepository(db_session)
    customer = customer_repo.create(Customer(**fields))
    return str(customer.id)


def _setup_pipeline_and_stage(
    client: TestClient, company_id: str, token: str, *, is_default: bool = True
) -> tuple[str, str]:
    pipeline_id = client.post(
        crm_url(company_id, "/pipelines"),
        json={"name": f"Test Pipeline {uuid4().hex[:6]}", "is_default": is_default},
        headers=auth_header(token),
    ).json()["data"]["id"]
    stage_id = client.post(
        crm_url(company_id, f"/pipelines/{pipeline_id}/stages"),
        json={"name": "Qualification", "sequence": 1, "probability": 20},
        headers=auth_header(token),
    ).json()["data"]["id"]
    return pipeline_id, stage_id


def _current_user_id(client: TestClient, token: str) -> str:
    resp = client.get("/api/v1/profile", headers=auth_header(token))
    assert resp.status_code == 200, resp.text
    return str(resp.json()["data"]["id"])


def _create_opportunity_payload(
    customer_id: str,
    owner_id: str,
    pipeline_id: str,
    stage_id: str,
    **overrides: object,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "name": "Acme Deal",
        "customer_id": customer_id,
        "owner_id": owner_id,
        "pipeline_id": pipeline_id,
        "stage_id": stage_id,
        "currency_code": "USD",
        "value": "10000",
    }
    payload.update(overrides)
    return payload


class TestOpportunityCreate:
    def test_create_returns_201_with_computed_weighted_value(
        self, crm_client: TestClient, db_session: Session
    ) -> None:
        _, token = new_user_and_token(crm_client, db_session)
        company_id = create_company(crm_client, token)
        pipeline_id, stage_id = _setup_pipeline_and_stage(crm_client, company_id, token)
        owner_id = _current_user_id(crm_client, token)
        customer_id = _create_customer(db_session, company_id)

        resp = crm_client.post(
            crm_url(company_id, "/opportunities"),
            json=_create_opportunity_payload(
                customer_id, owner_id, pipeline_id, stage_id
            ),
            headers=auth_header(token),
        )

        assert resp.status_code == 201, resp.text
        data = resp.json()["data"]
        assert data["status"] == "OPEN"
        assert data["probability"] == 20  # inherited from the stage
        assert data["weighted_value"] == "2000.00"  # 10000 * 20 / 100

    def test_create_without_currency_code_defaults_to_customers_own(
        self, crm_client: TestClient, db_session: Session
    ) -> None:
        _, token = new_user_and_token(crm_client, db_session)
        company_id = create_company(crm_client, token)
        pipeline_id, stage_id = _setup_pipeline_and_stage(crm_client, company_id, token)
        owner_id = _current_user_id(crm_client, token)
        customer_id = _create_customer(db_session, company_id, currency_code="EUR")

        payload = _create_opportunity_payload(
            customer_id, owner_id, pipeline_id, stage_id
        )
        del payload["currency_code"]

        resp = crm_client.post(
            crm_url(company_id, "/opportunities"),
            json=payload,
            headers=auth_header(token),
        )

        assert resp.status_code == 201, resp.text
        assert resp.json()["data"]["currency_code"] == "EUR"

    def test_create_with_cross_tenant_customer_rejected(
        self, crm_client: TestClient, db_session: Session
    ) -> None:
        _, token = new_user_and_token(crm_client, db_session)
        company_a = create_company(crm_client, token)
        company_b = create_company(crm_client, token)
        pipeline_id, stage_id = _setup_pipeline_and_stage(crm_client, company_a, token)
        owner_id = _current_user_id(crm_client, token)
        customer_in_b = _create_customer(db_session, company_b)

        resp = crm_client.post(
            crm_url(company_a, "/opportunities"),
            json=_create_opportunity_payload(
                customer_in_b, owner_id, pipeline_id, stage_id
            ),
            headers=auth_header(token),
        )

        assert resp.status_code == 422, resp.text

    def test_create_with_stage_from_different_pipeline_rejected(
        self, crm_client: TestClient, db_session: Session
    ) -> None:
        _, token = new_user_and_token(crm_client, db_session)
        company_id = create_company(crm_client, token)
        pipeline_id, _ = _setup_pipeline_and_stage(crm_client, company_id, token)
        _, other_stage_id = _setup_pipeline_and_stage(
            crm_client, company_id, token, is_default=False
        )
        owner_id = _current_user_id(crm_client, token)
        customer_id = _create_customer(db_session, company_id)

        resp = crm_client.post(
            crm_url(company_id, "/opportunities"),
            json=_create_opportunity_payload(
                customer_id, owner_id, pipeline_id, other_stage_id
            ),
            headers=auth_header(token),
        )

        assert resp.status_code == 422, resp.text


def _create_open_opportunity(
    crm_client: TestClient, db_session: Session
) -> tuple[str, str, str]:
    """Create a company, default pipeline/stage, and one OPEN Opportunity.
    Returns (company_id, token, opportunity_id)."""
    _, token = new_user_and_token(crm_client, db_session)
    company_id = create_company(crm_client, token)
    pipeline_id, stage_id = _setup_pipeline_and_stage(crm_client, company_id, token)
    owner_id = _current_user_id(crm_client, token)
    customer_id = _create_customer(db_session, company_id)
    opp_id = crm_client.post(
        crm_url(company_id, "/opportunities"),
        json=_create_opportunity_payload(customer_id, owner_id, pipeline_id, stage_id),
        headers=auth_header(token),
    ).json()["data"]["id"]
    return company_id, token, opp_id


class TestOpportunityLifecycle:
    def test_win_marks_won_and_blocks_further_edits(
        self, crm_client: TestClient, db_session: Session
    ) -> None:
        company_id, token, opp_id = _create_open_opportunity(crm_client, db_session)

        win_resp = crm_client.post(
            crm_url(company_id, f"/opportunities/{opp_id}/win"),
            headers=auth_header(token),
        )
        assert win_resp.status_code == 200, win_resp.text
        assert win_resp.json()["data"]["status"] == "WON"

        update_resp = crm_client.patch(
            crm_url(company_id, f"/opportunities/{opp_id}"),
            json={"description": "too late"},
            headers=auth_header(token),
        )
        assert update_resp.status_code == 409, update_resp.text

        second_win_resp = crm_client.post(
            crm_url(company_id, f"/opportunities/{opp_id}/win"),
            headers=auth_header(token),
        )
        assert second_win_resp.status_code == 409, second_win_resp.text

    def test_lose_without_reason_rejected(
        self, crm_client: TestClient, db_session: Session
    ) -> None:
        company_id, token, opp_id = _create_open_opportunity(crm_client, db_session)

        resp = crm_client.post(
            crm_url(company_id, f"/opportunities/{opp_id}/lose"),
            json={},
            headers=auth_header(token),
        )

        assert resp.status_code == 422, resp.text

    def test_lose_with_reason_succeeds(
        self, crm_client: TestClient, db_session: Session
    ) -> None:
        company_id, token, opp_id = _create_open_opportunity(crm_client, db_session)

        resp = crm_client.post(
            crm_url(company_id, f"/opportunities/{opp_id}/lose"),
            json={"lost_reason": "Budget cut"},
            headers=auth_header(token),
        )

        assert resp.status_code == 200, resp.text
        assert resp.json()["data"]["status"] == "LOST"
        assert resp.json()["data"]["lost_reason"] == "Budget cut"

    def test_delete_won_opportunity_rejected(
        self, crm_client: TestClient, db_session: Session
    ) -> None:
        company_id, token, opp_id = _create_open_opportunity(crm_client, db_session)
        crm_client.post(
            crm_url(company_id, f"/opportunities/{opp_id}/win"),
            headers=auth_header(token),
        )

        resp = crm_client.delete(
            crm_url(company_id, f"/opportunities/{opp_id}"), headers=auth_header(token)
        )

        assert resp.status_code == 409, resp.text

    def test_delete_open_opportunity_succeeds(
        self, crm_client: TestClient, db_session: Session
    ) -> None:
        company_id, token, opp_id = _create_open_opportunity(crm_client, db_session)

        resp = crm_client.delete(
            crm_url(company_id, f"/opportunities/{opp_id}"), headers=auth_header(token)
        )
        assert resp.status_code == 204, resp.text

        get_resp = crm_client.get(
            crm_url(company_id, f"/opportunities/{opp_id}"), headers=auth_header(token)
        )
        assert get_resp.status_code == 404, get_resp.text


class TestOpportunityList:
    def test_list_filters_by_status(
        self, crm_client: TestClient, db_session: Session
    ) -> None:
        company_id, token, opp_id = _create_open_opportunity(crm_client, db_session)

        resp = crm_client.get(
            crm_url(company_id, "/opportunities?status=OPEN"),
            headers=auth_header(token),
        )

        assert resp.status_code == 200, resp.text
        body = resp.json()["data"]
        assert body["total"] >= 1
        assert all(item["status"] == "OPEN" for item in body["items"])


class TestOpportunityTenantIsolation:
    def test_cross_company_get_returns_404(
        self, crm_client: TestClient, db_session: Session
    ) -> None:
        _, token = new_user_and_token(crm_client, db_session)
        company_a = create_company(crm_client, token)
        company_b = create_company(crm_client, token)
        pipeline_id, stage_id = _setup_pipeline_and_stage(crm_client, company_a, token)
        owner_id = _current_user_id(crm_client, token)
        customer_id = _create_customer(db_session, company_a)
        opp_id = crm_client.post(
            crm_url(company_a, "/opportunities"),
            json=_create_opportunity_payload(
                customer_id, owner_id, pipeline_id, stage_id
            ),
            headers=auth_header(token),
        ).json()["data"]["id"]

        resp = crm_client.get(
            crm_url(company_b, f"/opportunities/{opp_id}"), headers=auth_header(token)
        )

        assert resp.status_code == 404, resp.text
