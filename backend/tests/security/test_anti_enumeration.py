"""T124 — Anti-enumeration security tests.

Verifies that:
1. Login with valid email+wrong password and login with nonexistent email
   both return 401 with identical response bodies.
2. POST /forgot-password with registered and unregistered email returns
   identical 200 response bodies.
Spec ref: spec.md §8 NFR-003, FR-002.
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.fixtures.auth_fixtures import create_test_user


class TestLoginAntiEnumeration:
    def test_wrong_password_and_unknown_email_return_identical_body(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, _ = create_test_user(db_session, email="enum_login@example.com")

        resp_wrong_pass = test_client.post(
            "/api/v1/auth/login",
            json={"email": user.email, "password": "WrongPassword@1234"},
        )
        resp_unknown = test_client.post(
            "/api/v1/auth/login",
            json={
                "email": "nobody@nowhere.example.com",
                "password": "WrongPassword@1234",
            },
        )

        assert resp_wrong_pass.status_code == 401
        assert resp_unknown.status_code == 401
        # Response bodies must be structurally identical to prevent enumeration.
        wrong_body = resp_wrong_pass.json()
        unknown_body = resp_unknown.json()
        assert wrong_body["error"]["code"] == unknown_body["error"]["code"]
        assert wrong_body["error"]["message"] == unknown_body["error"]["message"]


class TestForgotPasswordAntiEnumeration:
    def test_registered_and_unregistered_responses_identical(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, _ = create_test_user(db_session, email="enum_forgot@example.com")

        resp_known = test_client.post(
            "/api/v1/auth/forgot-password",
            json={"email": user.email},
        )
        resp_unknown = test_client.post(
            "/api/v1/auth/forgot-password",
            json={"email": "totally-unknown@enum-test.example.com"},
        )

        assert resp_known.status_code == 200
        assert resp_unknown.status_code == 200
        assert resp_known.json() == resp_unknown.json()
