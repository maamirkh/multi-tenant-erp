"""T103 [P] — Domain event outbox completeness test.

Verifies that every state-changing company operation writes the correct
event_type record to the event_outbox table with:
  - Correct event_type string (e.g. "company.created")
  - Correct aggregate_type ("Company" — as defined in events.py _AGGREGATE_TYPE)
  - Matching aggregate_id (company UUID as string)
  - Non-null, non-empty payload

Spec ref: spec.md §14.1, AC-009.

Event types verified:
  - company.created     → POST /companies
  - company.updated     → PATCH /companies/{id}
  - company.activated   → POST /companies/{id}/activate  (requires country set)
  - company.deactivated → POST /companies/{id}/deactivate (requires active status)
  - company.deleted     → DELETE /companies/{id}
  - company.restored    → POST /companies/{id}/restore   (after delete)

Note: company.logo_uploaded is tested via test_company_logo.py.
      company.settings_updated does not exist — the settings PATCH endpoint
      updates the company directly via the repository without emitting a
      separate outbox event (it goes through company.updated via CompanyService
      when called from update_company, but the /settings endpoint in the router
      bypasses the service event emission).
"""

from __future__ import annotations

import json as _json

from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from tests.fixtures.auth_fixtures import create_test_user

# The aggregate_type used by all company domain events (see events.py _AGGREGATE_TYPE)
_AGGREGATE_TYPE = "Company"


def _login(client: TestClient, email: str, password: str) -> str:
    resp = client.post(
        "/api/v1/auth/login", json={"email": email, "password": password}
    )
    return resp.json()["data"]["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _auth_json(token: str) -> dict:
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def _delete(client: TestClient, url: str, token: str, body: dict) -> object:
    """DELETE with a JSON body — TestClient.delete() does not support json= kwarg."""
    return client.request(
        "DELETE", url, content=_json.dumps(body), headers=_auth_json(token)
    )


def _create_company(client: TestClient, token: str, name: str, email: str) -> str:
    resp = client.post(
        "/api/v1/companies",
        json={"legal_name": name, "email": email},
        headers=_auth(token),
    )
    assert resp.status_code == 201, f"Company creation failed: {resp.json()}"
    return resp.json()["data"]["id"]


def _prepare_for_activation(client: TestClient, token: str, company_id: str) -> None:
    """Patch required fields (country) so the company can be activated.

    BR-008 requires country and default_currency to be set before activation.
    """
    resp = client.patch(
        f"/api/v1/companies/{company_id}",
        json={"country": "US", "default_currency": "USD"},
        headers=_auth(token),
    )
    assert resp.status_code == 200, f"Prepare for activation failed: {resp.json()}"


def _get_outbox_events(
    db_session: Session, company_id: str, event_type: str
) -> list[dict]:
    """Query event_outbox for events matching the given type and aggregate_id.

    SQLite stores JSONB as TEXT, so we parse the payload from a string when needed.
    """
    rows = db_session.execute(
        text(
            "SELECT event_type, aggregate_id, aggregate_type, payload "
            "FROM event_outbox "
            "WHERE aggregate_id = :cid AND event_type = :etype"
        ),
        {"cid": company_id, "etype": event_type},
    ).fetchall()
    return [
        {
            "event_type": r[0],
            "aggregate_id": r[1],
            "aggregate_type": r[2],
            "payload": _json.loads(r[3]) if isinstance(r[3], str) else r[3],
        }
        for r in rows
    ]


def _assert_event(
    events: list[dict],
    event_type: str,
    company_id: str,
    *,
    count: int = 1,
) -> None:
    """Assert that exactly `count` events exist with valid aggregate and payload."""
    assert len(events) == count, (
        f"Expected {count} '{event_type}' event(s), got {len(events)}"
    )
    for ev in events:
        assert ev["aggregate_id"] == company_id, (
            f"aggregate_id mismatch: expected {company_id}, got {ev['aggregate_id']}"
        )
        assert ev["aggregate_type"] == _AGGREGATE_TYPE, (
            f"aggregate_type mismatch: expected '{_AGGREGATE_TYPE}', got '{ev['aggregate_type']}'"
        )
        assert ev["payload"] is not None, f"Null payload for {event_type}"
        assert ev["payload"] != {}, f"Empty payload for {event_type}"


class TestCompanyCreatedEvent:
    """AC-009: POST /companies → company.created outbox event."""

    def test_company_created_event_written(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, pwd = create_test_user(db_session, email="outbox_create@example.com")
        token = _login(test_client, user.email, pwd)
        company_id = _create_company(
            test_client, token, "Outbox Create Corp", "oc@corp.com"
        )

        events = _get_outbox_events(db_session, company_id, "company.created")

        _assert_event(events, "company.created", company_id)
        # Payload must include company_id, legal_name, slug, owner_id, status
        payload = events[0]["payload"]
        assert payload["company_id"] == company_id
        assert payload["legal_name"] == "Outbox Create Corp"
        assert "slug" in payload
        assert payload["status"] == "pending_setup"


class TestCompanyUpdatedEvent:
    """AC-009: PATCH /companies/{id} → company.updated outbox event."""

    def test_company_updated_event_written(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, pwd = create_test_user(db_session, email="outbox_update@example.com")
        token = _login(test_client, user.email, pwd)
        company_id = _create_company(
            test_client, token, "Outbox Update Corp", "ou@corp.com"
        )

        resp = test_client.patch(
            f"/api/v1/companies/{company_id}",
            json={"trade_name": "Updated Trade Name"},
            headers=_auth(token),
        )
        assert resp.status_code == 200

        events = _get_outbox_events(db_session, company_id, "company.updated")

        assert len(events) >= 1, "Expected at least 1 company.updated event"
        latest = events[-1]
        assert latest["aggregate_id"] == company_id
        assert latest["aggregate_type"] == _AGGREGATE_TYPE
        assert latest["payload"] is not None
        assert "changed_fields" in latest["payload"]


class TestCompanyActivatedEvent:
    """AC-009: POST /companies/{id}/activate → company.activated outbox event."""

    def test_company_activated_event_written(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, pwd = create_test_user(db_session, email="outbox_activate@example.com")
        token = _login(test_client, user.email, pwd)
        company_id = _create_company(
            test_client, token, "Outbox Activate Corp", "oa@corp.com"
        )

        # Set required fields before activation (BR-008)
        _prepare_for_activation(test_client, token, company_id)

        resp = test_client.post(
            f"/api/v1/companies/{company_id}/activate",
            headers=_auth(token),
        )
        assert resp.status_code == 200, f"Activation failed: {resp.json()}"

        events = _get_outbox_events(db_session, company_id, "company.activated")

        _assert_event(events, "company.activated", company_id)
        assert "activated_at" in events[0]["payload"]


class TestCompanyDeactivatedEvent:
    """AC-009: POST /companies/{id}/deactivate → company.deactivated outbox event."""

    def test_company_deactivated_event_written(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, pwd = create_test_user(db_session, email="outbox_deactivate@example.com")
        token = _login(test_client, user.email, pwd)
        company_id = _create_company(
            test_client, token, "Outbox Deactivate Corp", "od@corp.com"
        )

        # Prepare and activate first
        _prepare_for_activation(test_client, token, company_id)
        test_client.post(
            f"/api/v1/companies/{company_id}/activate", headers=_auth(token)
        )

        resp = test_client.post(
            f"/api/v1/companies/{company_id}/deactivate",
            json={"reason": "Testing deactivation event for outbox completeness"},
            headers=_auth(token),
        )
        assert resp.status_code == 200, f"Deactivation failed: {resp.json()}"

        events = _get_outbox_events(db_session, company_id, "company.deactivated")

        _assert_event(events, "company.deactivated", company_id)
        payload = events[0]["payload"]
        assert "reason" in payload
        assert "deactivated_at" in payload


class TestCompanyDeletedEvent:
    """AC-009: DELETE /companies/{id} → company.deleted outbox event."""

    def test_company_deleted_event_written(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, pwd = create_test_user(db_session, email="outbox_delete@example.com")
        token = _login(test_client, user.email, pwd)
        company_id = _create_company(
            test_client, token, "Outbox Delete Corp", "del@corp.com"
        )

        # Deletion requires active or inactive status (BR spec §5.6)
        _prepare_for_activation(test_client, token, company_id)
        test_client.post(
            f"/api/v1/companies/{company_id}/activate", headers=_auth(token)
        )

        resp = _delete(
            test_client,
            f"/api/v1/companies/{company_id}",
            token,
            {
                "reason": "Testing deletion event for outbox completeness verification",
                "confirm_delete": True,
            },
        )
        assert resp.status_code == 200, f"Delete failed: {resp.json()}"

        events = _get_outbox_events(db_session, company_id, "company.deleted")

        _assert_event(events, "company.deleted", company_id)
        payload = events[0]["payload"]
        assert "reason" in payload
        assert "deleted_at" in payload


class TestCompanyRestoredEvent:
    """AC-009: POST /companies/{id}/restore → company.restored outbox event."""

    def test_company_restored_event_written(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, pwd = create_test_user(db_session, email="outbox_restore@example.com")
        token = _login(test_client, user.email, pwd)
        company_id = _create_company(
            test_client, token, "Outbox Restore Corp", "rest@corp.com"
        )

        # Deletion requires active or inactive status (BR spec §5.6)
        _prepare_for_activation(test_client, token, company_id)
        test_client.post(
            f"/api/v1/companies/{company_id}/activate", headers=_auth(token)
        )

        # Delete first
        _delete(
            test_client,
            f"/api/v1/companies/{company_id}",
            token,
            {
                "reason": "Deleting to test restore event",
                "confirm_delete": True,
            },
        )

        resp = test_client.post(
            f"/api/v1/companies/{company_id}/restore",
            headers=_auth(token),
        )
        assert resp.status_code == 200, f"Restore failed: {resp.json()}"

        events = _get_outbox_events(db_session, company_id, "company.restored")

        _assert_event(events, "company.restored", company_id)
        assert "restored_at" in events[0]["payload"]


class TestOutboxEventPayloadIntegrity:
    """Verify the full create → update → activate lifecycle produces complete events."""

    def test_lifecycle_events_all_have_non_null_payloads(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, pwd = create_test_user(db_session, email="outbox_integrity@example.com")
        token = _login(test_client, user.email, pwd)
        company_id = _create_company(
            test_client, token, "Outbox Integrity Corp", "int@corp.com"
        )

        _prepare_for_activation(test_client, token, company_id)
        test_client.post(
            f"/api/v1/companies/{company_id}/activate", headers=_auth(token)
        )

        expected_types = ["company.created", "company.updated", "company.activated"]
        for event_type in expected_types:
            events = _get_outbox_events(db_session, company_id, event_type)
            assert len(events) >= 1, f"No event found for type '{event_type}'"
            for ev in events:
                assert ev["payload"] is not None, f"Null payload for '{event_type}'"
                assert ev["payload"] != {}, f"Empty payload for '{event_type}'"
                assert ev["aggregate_type"] == _AGGREGATE_TYPE, (
                    f"Wrong aggregate_type for '{event_type}': {ev['aggregate_type']}"
                )
