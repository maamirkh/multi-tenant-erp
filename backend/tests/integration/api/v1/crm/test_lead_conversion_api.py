"""API integration test: POST /crm/leads/{id}/convert (tasks.md T041).

HTTP-level coverage of the endpoint, distinct from
``test_lead_conversion.py``'s service-level coverage of the conversion
logic itself. Uses the shared ``crm_client`` fixture — see this
directory's ``conftest.py`` for why the CRM router isn't yet mounted into
the production app.

Task: T041 (tasks.md Phase 4).
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.integration.api.v1.crm.conftest import (
    auth_header,
    create_company,
    crm_url,
    new_user_and_token,
)


def _create_lead(
    client: TestClient, company_id: str, token: str, **overrides: object
) -> str:
    payload: dict[str, Any] = {
        "first_name": "Jane",
        "last_name": "Prospect",
        "email": f"jane-{uuid4().hex[:8]}@example.com",
    }
    payload.update(overrides)
    resp = client.post(
        crm_url(company_id, "/leads"), json=payload, headers=auth_header(token)
    )
    assert resp.status_code == 201, resp.text
    return str(resp.json()["data"]["id"])


def _qualify(client: TestClient, company_id: str, lead_id: str, token: str) -> None:
    resp = client.patch(
        crm_url(company_id, f"/leads/{lead_id}"),
        json={"status": "CONTACTED"},
        headers=auth_header(token),
    )
    assert resp.status_code == 200, resp.text
    resp = client.patch(
        crm_url(company_id, f"/leads/{lead_id}"),
        json={"status": "QUALIFIED", "qualification_notes": "Confirmed budget"},
        headers=auth_header(token),
    )
    assert resp.status_code == 200, resp.text


class TestConvertLead:
    def test_convert_new_lead_returns_409_not_qualified(
        self, crm_client: TestClient, db_session: Session
    ) -> None:
        _, token = new_user_and_token(crm_client, db_session)
        company_id = create_company(crm_client, token)
        lead_id = _create_lead(crm_client, company_id, token)

        resp = crm_client.post(
            crm_url(company_id, f"/leads/{lead_id}/convert"),
            headers=auth_header(token),
        )

        assert resp.status_code == 409, resp.text

    def test_convert_qualified_lead_returns_200_with_correct_shape(
        self, crm_client: TestClient, db_session: Session
    ) -> None:
        _, token = new_user_and_token(crm_client, db_session)
        company_id = create_company(crm_client, token)
        lead_id = _create_lead(crm_client, company_id, token)
        _qualify(crm_client, company_id, lead_id, token)

        resp = crm_client.post(
            crm_url(company_id, f"/leads/{lead_id}/convert"),
            headers=auth_header(token),
        )

        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert data["lead_id"] == lead_id
        assert "customer_id" in data
        assert "opportunity_id" in data
        assert data["customer_matched"] is False

        # Fresh GET confirms real persistence, not just an in-request view.
        get_resp = crm_client.get(
            crm_url(company_id, f"/leads/{lead_id}"), headers=auth_header(token)
        )
        assert get_resp.status_code == 200, get_resp.text
        lead_data = get_resp.json()["data"]
        assert lead_data["status"] == "CONVERTED"
        assert lead_data["converted_customer_id"] == data["customer_id"]
        assert lead_data["converted_opportunity_id"] == data["opportunity_id"]

    def test_convert_already_converted_lead_returns_same_result(
        self, crm_client: TestClient, db_session: Session
    ) -> None:
        _, token = new_user_and_token(crm_client, db_session)
        company_id = create_company(crm_client, token)
        lead_id = _create_lead(crm_client, company_id, token)
        _qualify(crm_client, company_id, lead_id, token)

        first = crm_client.post(
            crm_url(company_id, f"/leads/{lead_id}/convert"),
            headers=auth_header(token),
        )
        second = crm_client.post(
            crm_url(company_id, f"/leads/{lead_id}/convert"),
            headers=auth_header(token),
        )

        assert first.status_code == 200, first.text
        assert second.status_code == 200, second.text
        assert (
            first.json()["data"]["customer_id"] == second.json()["data"]["customer_id"]
        )
        assert (
            first.json()["data"]["opportunity_id"]
            == second.json()["data"]["opportunity_id"]
        )

    def test_convert_cross_tenant_lead_returns_404(
        self, crm_client: TestClient, db_session: Session
    ) -> None:
        _, token = new_user_and_token(crm_client, db_session)
        company_a = create_company(crm_client, token)
        company_b = create_company(crm_client, token)
        lead_id = _create_lead(crm_client, company_a, token)
        _qualify(crm_client, company_a, lead_id, token)

        resp = crm_client.post(
            crm_url(company_b, f"/leads/{lead_id}/convert"),
            headers=auth_header(token),
        )

        assert resp.status_code == 404, resp.text

    def test_convert_unauthenticated_returns_401(self, crm_client: TestClient) -> None:
        resp = crm_client.post(crm_url(str(uuid4()), f"/leads/{uuid4()}/convert"))
        assert resp.status_code == 401, resp.text
