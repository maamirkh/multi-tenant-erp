"""API integration tests for CRM Pipeline + PipelineStage endpoints — Phase 5.

Tests:
  - GET/POST/PATCH /crm/pipelines
  - GET/POST /crm/pipelines/{id}/stages, PATCH /crm/pipeline-stages/{id}
  - BR-007: stage deactivation blocked while an OPEN Opportunity occupies it

Task: T048 (tasks.md Phase 5).
"""

from __future__ import annotations

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


def _create_customer(db_session: Session, company_id: str) -> str:
    """Create a Sales Customer directly via the DB session — matching the
    established pattern from ``test_lead_conversion.py`` — so this API
    test doesn't need to orchestrate Sales' own customer-creation HTTP
    flow just to obtain a valid ``customer_id`` for an Opportunity."""
    from uuid import UUID

    cid = UUID(company_id)
    category_repo = CustomerCategoryRepository(db_session)
    category = category_repo.create(
        CustomerCategory(
            company_id=cid, code=f"CAT-{uuid4().hex[:6]}", name="Test Category"
        )
    )
    customer_repo = CustomerRepository(db_session)
    customer = customer_repo.create(
        Customer(
            company_id=cid,
            customer_code=f"CUST-{uuid4().hex[:8]}",
            legal_name="Blocking Deal Customer",
            customer_type="COMPANY",
            category_id=str(category.id),
            currency_code="USD",
            status="DRAFT",
        )
    )
    return str(customer.id)


class TestPipelineCrud:
    def test_create_list_update_pipeline(
        self, crm_client: TestClient, db_session: Session
    ) -> None:
        _, token = new_user_and_token(crm_client, db_session)
        company_id = create_company(crm_client, token)

        create_resp = crm_client.post(
            crm_url(company_id, "/pipelines"),
            json={"name": "Enterprise Pipeline", "is_default": True},
            headers=auth_header(token),
        )
        assert create_resp.status_code == 201, create_resp.text
        pipeline_id = create_resp.json()["data"]["id"]

        list_resp = crm_client.get(
            crm_url(company_id, "/pipelines"), headers=auth_header(token)
        )
        assert list_resp.status_code == 200, list_resp.text
        assert any(p["id"] == pipeline_id for p in list_resp.json()["data"])

        update_resp = crm_client.patch(
            crm_url(company_id, f"/pipelines/{pipeline_id}"),
            json={"name": "Enterprise Pipeline (Renamed)"},
            headers=auth_header(token),
        )
        assert update_resp.status_code == 200, update_resp.text
        assert update_resp.json()["data"]["name"] == "Enterprise Pipeline (Renamed)"


class TestPipelineStageCrud:
    def test_create_list_update_stage(
        self, crm_client: TestClient, db_session: Session
    ) -> None:
        _, token = new_user_and_token(crm_client, db_session)
        company_id = create_company(crm_client, token)
        pipeline_id = crm_client.post(
            crm_url(company_id, "/pipelines"),
            json={"name": "Test Pipeline"},
            headers=auth_header(token),
        ).json()["data"]["id"]

        create_resp = crm_client.post(
            crm_url(company_id, f"/pipelines/{pipeline_id}/stages"),
            json={"name": "Qualification", "sequence": 1, "probability": 20},
            headers=auth_header(token),
        )
        assert create_resp.status_code == 201, create_resp.text
        stage_id = create_resp.json()["data"]["id"]

        list_resp = crm_client.get(
            crm_url(company_id, f"/pipelines/{pipeline_id}/stages"),
            headers=auth_header(token),
        )
        assert list_resp.status_code == 200, list_resp.text
        assert len(list_resp.json()["data"]) == 1

        update_resp = crm_client.patch(
            crm_url(company_id, f"/pipeline-stages/{stage_id}"),
            json={"probability": 25},
            headers=auth_header(token),
        )
        assert update_resp.status_code == 200, update_resp.text
        assert update_resp.json()["data"]["probability"] == 25

    def test_deactivate_stage_with_open_opportunity_rejected(
        self, crm_client: TestClient, db_session: Session
    ) -> None:
        _, token = new_user_and_token(crm_client, db_session)
        company_id = create_company(crm_client, token)
        pipeline_id = crm_client.post(
            crm_url(company_id, "/pipelines"),
            json={"name": "Test Pipeline"},
            headers=auth_header(token),
        ).json()["data"]["id"]
        stage_id = crm_client.post(
            crm_url(company_id, f"/pipelines/{pipeline_id}/stages"),
            json={"name": "Qualification", "sequence": 1, "probability": 20},
            headers=auth_header(token),
        ).json()["data"]["id"]

        profile_resp = crm_client.get("/api/v1/profile", headers=auth_header(token))
        assert profile_resp.status_code == 200, profile_resp.text
        owner_id = profile_resp.json()["data"]["id"]

        customer_id = _create_customer(db_session, company_id)
        create_opp_resp = crm_client.post(
            crm_url(company_id, "/opportunities"),
            json={
                "name": "Blocking Deal",
                "customer_id": customer_id,
                "owner_id": owner_id,
                "pipeline_id": pipeline_id,
                "stage_id": stage_id,
                "currency_code": "USD",
            },
            headers=auth_header(token),
        )
        assert create_opp_resp.status_code == 201, create_opp_resp.text

        deactivate_resp = crm_client.patch(
            crm_url(company_id, f"/pipeline-stages/{stage_id}"),
            json={"is_active": False},
            headers=auth_header(token),
        )

        assert deactivate_resp.status_code == 409, deactivate_resp.text

    def test_unknown_pipeline_returns_404(
        self, crm_client: TestClient, db_session: Session
    ) -> None:
        _, token = new_user_and_token(crm_client, db_session)
        company_id = create_company(crm_client, token)

        resp = crm_client.get(
            crm_url(company_id, f"/pipelines/{uuid4()}/stages"),
            headers=auth_header(token),
        )

        assert resp.status_code == 404, resp.text
