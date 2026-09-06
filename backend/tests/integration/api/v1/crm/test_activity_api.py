"""API integration tests for CRM Activity endpoints — Phase 6.

Tests:
  - POST/GET/PATCH/DELETE /crm/activities, GET /crm/activities/{id}
  - POST .../complete (idempotency, Lead-cascade over real HTTP)
  - BR-006 (relation required) rejected at 422
  - Overdue-list filter
  - Tenant isolation (cross-company GET returns 404)

Task: T053 (tasks.md Phase 6).
"""

from __future__ import annotations

from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.integration.api.v1.crm.conftest import (
    auth_header,
    create_company,
    crm_url,
    new_user_and_token,
)


def _create_lead(client: TestClient, company_id: str, token: str) -> str:
    """A Lead relation is the simplest way to satisfy BR-006 in these
    tests — created via CRM's own API, no cross-module Sales Customer
    setup needed (unlike ``test_opportunity_api.py``, which genuinely
    needs a real Customer)."""
    resp = client.post(
        crm_url(company_id, "/leads"),
        json={
            "first_name": "Jane",
            "last_name": "Prospect",
            "email": f"jane-{uuid4().hex[:8]}@example.com",
        },
        headers=auth_header(token),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]["id"]


def _create_activity_payload(
    assigned_to: str, lead_id: str, **overrides: object
) -> dict:
    payload = {
        "activity_type": "CALL",
        "subject": "Intro call",
        "assigned_to": assigned_to,
        "lead_id": lead_id,
    }
    payload.update(overrides)
    return payload


def _current_user_id(client: TestClient, token: str) -> str:
    resp = client.get("/api/v1/profile", headers=auth_header(token))
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]["id"]


def _setup(crm_client: TestClient, db_session: Session) -> tuple[str, str, str, str]:
    """Returns (company_id, token, assigned_to, lead_id)."""
    _, token = new_user_and_token(crm_client, db_session)
    company_id = create_company(crm_client, token)
    assigned_to = _current_user_id(crm_client, token)
    lead_id = _create_lead(crm_client, company_id, token)
    return company_id, token, assigned_to, lead_id


class TestActivityCreate:
    def test_create_returns_201(
        self, crm_client: TestClient, db_session: Session
    ) -> None:
        company_id, token, assigned_to, lead_id = _setup(crm_client, db_session)

        resp = crm_client.post(
            crm_url(company_id, "/activities"),
            json=_create_activity_payload(assigned_to, lead_id),
            headers=auth_header(token),
        )

        assert resp.status_code == 201, resp.text
        data = resp.json()["data"]
        assert data["status"] == "PLANNED"
        assert data["completed_at"] is None

    def test_create_without_relation_rejected(
        self, crm_client: TestClient, db_session: Session
    ) -> None:
        _, token = new_user_and_token(crm_client, db_session)
        company_id = create_company(crm_client, token)
        assigned_to = _current_user_id(crm_client, token)

        resp = crm_client.post(
            crm_url(company_id, "/activities"),
            json={
                "activity_type": "NOTE",
                "subject": "Orphan note",
                "assigned_to": assigned_to,
            },
            headers=auth_header(token),
        )

        assert resp.status_code == 422, resp.text

    def test_create_task_without_due_date_rejected(
        self, crm_client: TestClient, db_session: Session
    ) -> None:
        company_id, token, assigned_to, lead_id = _setup(crm_client, db_session)

        resp = crm_client.post(
            crm_url(company_id, "/activities"),
            json=_create_activity_payload(assigned_to, lead_id, activity_type="TASK"),
            headers=auth_header(token),
        )

        assert resp.status_code == 422, resp.text

    def test_create_assignee_outside_company_rejected(
        self, crm_client: TestClient, db_session: Session
    ) -> None:
        company_id, token, _, lead_id = _setup(crm_client, db_session)

        resp = crm_client.post(
            crm_url(company_id, "/activities"),
            json=_create_activity_payload(str(uuid4()), lead_id),
            headers=auth_header(token),
        )

        assert resp.status_code == 422, resp.text

    def test_create_with_cross_tenant_lead_rejected(
        self, crm_client: TestClient, db_session: Session
    ) -> None:
        _, token = new_user_and_token(crm_client, db_session)
        company_a = create_company(crm_client, token)
        company_b = create_company(crm_client, token)
        assigned_to = _current_user_id(crm_client, token)
        lead_in_b = _create_lead(crm_client, company_b, token)

        resp = crm_client.post(
            crm_url(company_a, "/activities"),
            json=_create_activity_payload(assigned_to, lead_in_b),
            headers=auth_header(token),
        )

        assert resp.status_code == 422, resp.text


class TestActivityComplete:
    def test_complete_is_idempotent(
        self, crm_client: TestClient, db_session: Session
    ) -> None:
        company_id, token, assigned_to, lead_id = _setup(crm_client, db_session)
        activity_id = crm_client.post(
            crm_url(company_id, "/activities"),
            json=_create_activity_payload(assigned_to, lead_id),
            headers=auth_header(token),
        ).json()["data"]["id"]

        first = crm_client.post(
            crm_url(company_id, f"/activities/{activity_id}/complete"),
            headers=auth_header(token),
        )
        second = crm_client.post(
            crm_url(company_id, f"/activities/{activity_id}/complete"),
            headers=auth_header(token),
        )

        assert first.status_code == 200, first.text
        assert second.status_code == 200, second.text
        assert first.json()["data"]["status"] == "COMPLETED"
        assert (
            first.json()["data"]["completed_at"]
            == second.json()["data"]["completed_at"]
        )

    def test_complete_linked_to_new_lead_advances_status(
        self, crm_client: TestClient, db_session: Session
    ) -> None:
        company_id, token, assigned_to, lead_id = _setup(crm_client, db_session)
        activity_id = crm_client.post(
            crm_url(company_id, "/activities"),
            json=_create_activity_payload(assigned_to, lead_id),
            headers=auth_header(token),
        ).json()["data"]["id"]

        complete_resp = crm_client.post(
            crm_url(company_id, f"/activities/{activity_id}/complete"),
            headers=auth_header(token),
        )
        assert complete_resp.status_code == 200, complete_resp.text

        lead_resp = crm_client.get(
            crm_url(company_id, f"/leads/{lead_id}"), headers=auth_header(token)
        )
        assert lead_resp.status_code == 200, lead_resp.text
        assert lead_resp.json()["data"]["status"] == "CONTACTED"
        assert lead_resp.json()["data"]["last_contact_date"] is not None


class TestActivityList:
    def test_list_filters_by_status(
        self, crm_client: TestClient, db_session: Session
    ) -> None:
        company_id, token, assigned_to, lead_id = _setup(crm_client, db_session)
        crm_client.post(
            crm_url(company_id, "/activities"),
            json=_create_activity_payload(assigned_to, lead_id),
            headers=auth_header(token),
        )

        resp = crm_client.get(
            crm_url(company_id, "/activities?status=PLANNED"),
            headers=auth_header(token),
        )

        assert resp.status_code == 200, resp.text
        body = resp.json()["data"]
        assert body["total"] >= 1
        assert all(item["status"] == "PLANNED" for item in body["items"])

    def test_overdue_activities_appear_after_due_date_passes(
        self, crm_client: TestClient, db_session: Session
    ) -> None:
        company_id, token, assigned_to, lead_id = _setup(crm_client, db_session)
        crm_client.post(
            crm_url(company_id, "/activities"),
            json=_create_activity_payload(
                assigned_to,
                lead_id,
                activity_type="TASK",
                due_date="2020-01-01T00:00:00Z",
            ),
            headers=auth_header(token),
        )

        resp = crm_client.get(
            crm_url(company_id, "/activities?due_to=2021-01-01T00:00:00Z"),
            headers=auth_header(token),
        )

        assert resp.status_code == 200, resp.text
        assert resp.json()["data"]["total"] >= 1


class TestActivityUpdateAndDelete:
    def test_update_subject(self, crm_client: TestClient, db_session: Session) -> None:
        company_id, token, assigned_to, lead_id = _setup(crm_client, db_session)
        activity_id = crm_client.post(
            crm_url(company_id, "/activities"),
            json=_create_activity_payload(assigned_to, lead_id),
            headers=auth_header(token),
        ).json()["data"]["id"]

        resp = crm_client.patch(
            crm_url(company_id, f"/activities/{activity_id}"),
            json={"subject": "Updated subject"},
            headers=auth_header(token),
        )

        assert resp.status_code == 200, resp.text
        assert resp.json()["data"]["subject"] == "Updated subject"

    def test_soft_delete_then_get_returns_404(
        self, crm_client: TestClient, db_session: Session
    ) -> None:
        company_id, token, assigned_to, lead_id = _setup(crm_client, db_session)
        activity_id = crm_client.post(
            crm_url(company_id, "/activities"),
            json=_create_activity_payload(assigned_to, lead_id),
            headers=auth_header(token),
        ).json()["data"]["id"]

        delete_resp = crm_client.delete(
            crm_url(company_id, f"/activities/{activity_id}"),
            headers=auth_header(token),
        )
        assert delete_resp.status_code == 204, delete_resp.text

        get_resp = crm_client.get(
            crm_url(company_id, f"/activities/{activity_id}"),
            headers=auth_header(token),
        )
        assert get_resp.status_code == 404, get_resp.text


class TestActivityTenantIsolation:
    def test_cross_company_get_returns_404(
        self, crm_client: TestClient, db_session: Session
    ) -> None:
        company_a, token, assigned_to, lead_id = _setup(crm_client, db_session)
        company_b = create_company(crm_client, token)
        activity_id = crm_client.post(
            crm_url(company_a, "/activities"),
            json=_create_activity_payload(assigned_to, lead_id),
            headers=auth_header(token),
        ).json()["data"]["id"]

        resp = crm_client.get(
            crm_url(company_b, f"/activities/{activity_id}"), headers=auth_header(token)
        )

        assert resp.status_code == 404, resp.text
