"""API integration tests for the Customer 360 endpoint — Phase 7 (T058).

Tests:
  - GET /crm/customers/{customer_id}/360 — 200 with populated data
  - 200 with empty CRM sections for a Customer with no CRM history (AC-17)
  - Cross-tenant 404 (SEC-03-equivalent for Customer 360)

Task: T058 (tasks.md Phase 7).
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
        "legal_name": "360 API Test Customer",
        "customer_type": "COMPANY",
        "category_id": str(category.id),
        "currency_code": "USD",
        "status": "ACTIVE",
    }
    fields.update(overrides)
    customer_repo = CustomerRepository(db_session)
    customer = customer_repo.create(Customer(**fields))
    return str(customer.id)


class TestCustomer360Endpoint:
    def test_returns_200_with_populated_shape(
        self, crm_client: TestClient, db_session: Session
    ) -> None:
        _, token = new_user_and_token(crm_client, db_session)
        company_id = create_company(crm_client, token)
        customer_id = _create_customer(db_session, company_id)

        resp = crm_client.get(
            crm_url(company_id, f"/customers/{customer_id}/360"),
            headers=auth_header(token),
        )

        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert data["customer"]["id"] == customer_id
        assert data["converted_leads"] == []
        assert data["opportunities"] == []
        assert data["activities"] == []
        assert data["sales_history"] == {
            "quotation_count": 0,
            "order_count": 0,
            "invoice_count": 0,
            "delivery_count": 0,
        }
        assert data["financial_summary"]["total_outstanding_base"] == "0"
        assert data["financial_summary"]["credit_status"] == "GOOD"
        assert data["last_interaction"] is None
        assert data["next_follow_up"] is None

    def test_empty_crm_history_degrades_gracefully_not_an_error(
        self, crm_client: TestClient, db_session: Session
    ) -> None:
        """AC-17: a Customer with zero CRM activity still returns 200."""
        _, token = new_user_and_token(crm_client, db_session)
        company_id = create_company(crm_client, token)
        customer_id = _create_customer(db_session, company_id, status="DRAFT")

        resp = crm_client.get(
            crm_url(company_id, f"/customers/{customer_id}/360"),
            headers=auth_header(token),
        )

        assert resp.status_code == 200, resp.text

    def test_cross_tenant_customer_returns_404(
        self, crm_client: TestClient, db_session: Session
    ) -> None:
        _, token_a = new_user_and_token(crm_client, db_session)
        company_a = create_company(crm_client, token_a)
        customer_id = _create_customer(db_session, company_a)

        _, token_b = new_user_and_token(crm_client, db_session)
        company_b = create_company(crm_client, token_b)

        resp = crm_client.get(
            crm_url(company_b, f"/customers/{customer_id}/360"),
            headers=auth_header(token_b),
        )

        assert resp.status_code == 404, resp.text

    def test_nonexistent_customer_returns_404(
        self, crm_client: TestClient, db_session: Session
    ) -> None:
        _, token = new_user_and_token(crm_client, db_session)
        company_id = create_company(crm_client, token)

        resp = crm_client.get(
            crm_url(company_id, f"/customers/{uuid4()}/360"),
            headers=auth_header(token),
        )

        assert resp.status_code == 404, resp.text
