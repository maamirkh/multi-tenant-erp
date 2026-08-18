"""API integration tests for CRM Lead + LeadSource endpoints — Phase 3.

Tests:
  - POST/GET/PATCH/DELETE /crm/leads, GET /crm/leads/{id}
  - POST /crm/leads/{id}/assign
  - GET/POST/PATCH /crm/lead-sources
  - 401/404/422/409 coverage per spec.md §38.7
  - Tenant isolation (cross-company GET returns 404)

``modules.crm.router`` is not mounted into ``api/v1/router.py`` yet — see
``conftest.py`` in this directory for the ``crm_client`` fixture and why
(tasks.md T079, Phase 8/9).

Task: T032 (tasks.md Phase 3).
Spec ref: specs/007-sales-management (test fixture pattern precedent),
specs/009-crm/spec.md §38.1-38.2, §38.7.
"""

from __future__ import annotations

from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.integration.api.v1.crm.conftest import (
    auth_header as _auth,
)
from tests.integration.api.v1.crm.conftest import (
    create_company as _create_company,
)
from tests.integration.api.v1.crm.conftest import (
    crm_url as _crm_url,
)
from tests.integration.api.v1.crm.conftest import (
    new_user_and_token as _new_user_and_token,
)


def _create_lead_payload(**overrides: object) -> dict:
    payload = {
        "first_name": "Jane",
        "last_name": "Prospect",
        "email": f"jane-{uuid4().hex[:8]}@example.com",
    }
    payload.update(overrides)
    return payload


# ---------------------------------------------------------------------------
# Lead CRUD + lifecycle
# ---------------------------------------------------------------------------


class TestLeadCreate:
    def test_create_lead_returns_201(
        self, crm_client: TestClient, db_session: Session
    ) -> None:
        _, token = _new_user_and_token(crm_client, db_session)
        company_id = _create_company(crm_client, token)

        resp = crm_client.post(
            _crm_url(company_id, "/leads"),
            json=_create_lead_payload(),
            headers=_auth(token),
        )

        assert resp.status_code == 201, resp.text
        data = resp.json()["data"]
        assert data["status"] == "NEW"
        assert data["first_name"] == "Jane"

    def test_create_lead_missing_name_and_company_rejected(
        self, crm_client: TestClient, db_session: Session
    ) -> None:
        _, token = _new_user_and_token(crm_client, db_session)
        company_id = _create_company(crm_client, token)

        resp = crm_client.post(
            _crm_url(company_id, "/leads"),
            json={"email": "orphan@example.com"},
            headers=_auth(token),
        )

        assert resp.status_code == 422, resp.text

    def test_create_lead_missing_contact_rejected(
        self, crm_client: TestClient, db_session: Session
    ) -> None:
        _, token = _new_user_and_token(crm_client, db_session)
        company_id = _create_company(crm_client, token)

        resp = crm_client.post(
            _crm_url(company_id, "/leads"),
            json={"first_name": "NoContact"},
            headers=_auth(token),
        )

        assert resp.status_code == 422, resp.text

    def test_create_lead_unauthenticated_rejected(self, crm_client: TestClient) -> None:
        resp = crm_client.post(
            _crm_url(str(uuid4()), "/leads"), json=_create_lead_payload()
        )
        assert resp.status_code == 401, resp.text


class TestLeadQualifyDisqualify:
    def test_qualify_without_notes_rejected(
        self, crm_client: TestClient, db_session: Session
    ) -> None:
        _, token = _new_user_and_token(crm_client, db_session)
        company_id = _create_company(crm_client, token)
        lead_id = crm_client.post(
            _crm_url(company_id, "/leads"),
            json=_create_lead_payload(),
            headers=_auth(token),
        ).json()["data"]["id"]

        resp = crm_client.patch(
            _crm_url(company_id, f"/leads/{lead_id}"),
            json={"status": "CONTACTED"},
            headers=_auth(token),
        )
        assert resp.status_code == 200, resp.text

        resp = crm_client.patch(
            _crm_url(company_id, f"/leads/{lead_id}"),
            json={"status": "QUALIFIED"},
            headers=_auth(token),
        )
        assert resp.status_code == 422, resp.text

    def test_qualify_with_notes_succeeds(
        self, crm_client: TestClient, db_session: Session
    ) -> None:
        _, token = _new_user_and_token(crm_client, db_session)
        company_id = _create_company(crm_client, token)
        lead_id = crm_client.post(
            _crm_url(company_id, "/leads"),
            json=_create_lead_payload(),
            headers=_auth(token),
        ).json()["data"]["id"]
        crm_client.patch(
            _crm_url(company_id, f"/leads/{lead_id}"),
            json={"status": "CONTACTED"},
            headers=_auth(token),
        )

        resp = crm_client.patch(
            _crm_url(company_id, f"/leads/{lead_id}"),
            json={
                "status": "QUALIFIED",
                "qualification_notes": "Confirmed budget and timeline",
            },
            headers=_auth(token),
        )

        assert resp.status_code == 200, resp.text
        assert resp.json()["data"]["status"] == "QUALIFIED"

    def test_disqualify_without_reason_rejected(
        self, crm_client: TestClient, db_session: Session
    ) -> None:
        _, token = _new_user_and_token(crm_client, db_session)
        company_id = _create_company(crm_client, token)
        lead_id = crm_client.post(
            _crm_url(company_id, "/leads"),
            json=_create_lead_payload(),
            headers=_auth(token),
        ).json()["data"]["id"]

        resp = crm_client.patch(
            _crm_url(company_id, f"/leads/{lead_id}"),
            json={"status": "LOST"},
            headers=_auth(token),
        )

        assert resp.status_code == 422, resp.text

    def test_invalid_transition_returns_409(
        self, crm_client: TestClient, db_session: Session
    ) -> None:
        _, token = _new_user_and_token(crm_client, db_session)
        company_id = _create_company(crm_client, token)
        lead_id = crm_client.post(
            _crm_url(company_id, "/leads"),
            json=_create_lead_payload(),
            headers=_auth(token),
        ).json()["data"]["id"]

        # NEW -> QUALIFIED is not a legal direct transition.
        resp = crm_client.patch(
            _crm_url(company_id, f"/leads/{lead_id}"),
            json={"status": "QUALIFIED", "qualification_notes": "x"},
            headers=_auth(token),
        )

        assert resp.status_code == 409, resp.text

    def test_unknown_status_value_rejected_at_schema_layer(
        self, crm_client: TestClient, db_session: Session
    ) -> None:
        _, token = _new_user_and_token(crm_client, db_session)
        company_id = _create_company(crm_client, token)
        lead_id = crm_client.post(
            _crm_url(company_id, "/leads"),
            json=_create_lead_payload(),
            headers=_auth(token),
        ).json()["data"]["id"]

        resp = crm_client.patch(
            _crm_url(company_id, f"/leads/{lead_id}"),
            json={"status": "NOT_A_REAL_STATUS"},
            headers=_auth(token),
        )

        assert resp.status_code == 422, resp.text


class TestLeadList:
    def test_list_filters_by_status(
        self, crm_client: TestClient, db_session: Session
    ) -> None:
        _, token = _new_user_and_token(crm_client, db_session)
        company_id = _create_company(crm_client, token)
        crm_client.post(
            _crm_url(company_id, "/leads"),
            json=_create_lead_payload(),
            headers=_auth(token),
        )

        resp = crm_client.get(
            _crm_url(company_id, "/leads?status=NEW"), headers=_auth(token)
        )

        assert resp.status_code == 200, resp.text
        body = resp.json()["data"]
        assert body["total"] >= 1
        assert all(item["status"] == "NEW" for item in body["items"])

    def test_list_pagination_page_size_capped_at_100(
        self, crm_client: TestClient, db_session: Session
    ) -> None:
        _, token = _new_user_and_token(crm_client, db_session)
        company_id = _create_company(crm_client, token)

        resp = crm_client.get(
            _crm_url(company_id, "/leads?page_size=101"), headers=_auth(token)
        )

        assert resp.status_code == 422, resp.text


class TestLeadAssign:
    def test_assign_to_outside_company_user_rejected(
        self, crm_client: TestClient, db_session: Session
    ) -> None:
        _, token = _new_user_and_token(crm_client, db_session)
        company_id = _create_company(crm_client, token)
        lead_id = crm_client.post(
            _crm_url(company_id, "/leads"),
            json=_create_lead_payload(),
            headers=_auth(token),
        ).json()["data"]["id"]

        # A random UUID is guaranteed to have no membership in this company.
        resp = crm_client.post(
            _crm_url(company_id, f"/leads/{lead_id}/assign"),
            json={"owner_id": str(uuid4())},
            headers=_auth(token),
        )

        assert resp.status_code == 422, resp.text

    def test_assign_to_company_owner_succeeds(
        self, crm_client: TestClient, db_session: Session
    ) -> None:
        owner_user_id, token = _new_user_and_token(crm_client, db_session)
        company_id = _create_company(crm_client, token)
        lead_id = crm_client.post(
            _crm_url(company_id, "/leads"),
            json=_create_lead_payload(),
            headers=_auth(token),
        ).json()["data"]["id"]

        resp = crm_client.post(
            _crm_url(company_id, f"/leads/{lead_id}/assign"),
            json={"owner_id": owner_user_id},
            headers=_auth(token),
        )

        assert resp.status_code == 200, resp.text
        assert resp.json()["data"]["owner_id"] == owner_user_id


class TestLeadTenantIsolation:
    def test_cross_company_get_returns_404(
        self, crm_client: TestClient, db_session: Session
    ) -> None:
        _, token = _new_user_and_token(crm_client, db_session)
        company_a = _create_company(crm_client, token)
        company_b = _create_company(crm_client, token)
        lead_id = crm_client.post(
            _crm_url(company_a, "/leads"),
            json=_create_lead_payload(),
            headers=_auth(token),
        ).json()["data"]["id"]

        resp = crm_client.get(
            _crm_url(company_b, f"/leads/{lead_id}"), headers=_auth(token)
        )

        assert resp.status_code == 404, resp.text

    def test_unknown_lead_returns_404(
        self, crm_client: TestClient, db_session: Session
    ) -> None:
        _, token = _new_user_and_token(crm_client, db_session)
        company_id = _create_company(crm_client, token)

        resp = crm_client.get(
            _crm_url(company_id, f"/leads/{uuid4()}"), headers=_auth(token)
        )

        assert resp.status_code == 404, resp.text


class TestLeadDelete:
    def test_soft_delete_then_get_returns_404(
        self, crm_client: TestClient, db_session: Session
    ) -> None:
        _, token = _new_user_and_token(crm_client, db_session)
        company_id = _create_company(crm_client, token)
        lead_id = crm_client.post(
            _crm_url(company_id, "/leads"),
            json=_create_lead_payload(),
            headers=_auth(token),
        ).json()["data"]["id"]

        resp = crm_client.delete(
            _crm_url(company_id, f"/leads/{lead_id}"), headers=_auth(token)
        )
        assert resp.status_code == 204, resp.text

        resp = crm_client.get(
            _crm_url(company_id, f"/leads/{lead_id}"), headers=_auth(token)
        )
        assert resp.status_code == 404, resp.text


# ---------------------------------------------------------------------------
# Lead Sources
# ---------------------------------------------------------------------------


class TestLeadSourceCrud:
    def test_create_list_update_lead_source(
        self, crm_client: TestClient, db_session: Session
    ) -> None:
        _, token = _new_user_and_token(crm_client, db_session)
        company_id = _create_company(crm_client, token)

        create_resp = crm_client.post(
            _crm_url(company_id, "/lead-sources"),
            json={"code": "WEBSITE", "name": "Website"},
            headers=_auth(token),
        )
        assert create_resp.status_code == 201, create_resp.text
        source_id = create_resp.json()["data"]["id"]

        list_resp = crm_client.get(
            _crm_url(company_id, "/lead-sources"), headers=_auth(token)
        )
        assert list_resp.status_code == 200, list_resp.text
        assert list_resp.json()["data"]["total"] >= 1

        update_resp = crm_client.patch(
            _crm_url(company_id, f"/lead-sources/{source_id}"),
            json={"name": "Website (Updated)"},
            headers=_auth(token),
        )
        assert update_resp.status_code == 200, update_resp.text
        assert update_resp.json()["data"]["name"] == "Website (Updated)"
