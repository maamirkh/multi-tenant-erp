"""T115 — Integration tests for POST /api/v1/auth/forgot-password.

Spec ref: spec.md §7 FR-021, US-04. Anti-enumeration: responses must be
identical for registered and unregistered emails.
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.fixtures.auth_fixtures import create_test_user


class TestForgotPasswordAntiEnumeration:
    def test_registered_email_returns_200(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, _ = create_test_user(db_session, email="fp_reg@example.com")
        resp = test_client.post(
            "/api/v1/auth/forgot-password",
            json={"email": user.email},
        )
        assert resp.status_code == 200

    def test_unknown_email_returns_200(self, test_client: TestClient) -> None:
        resp = test_client.post(
            "/api/v1/auth/forgot-password",
            json={"email": "no-account@unknown.example.com"},
        )
        assert resp.status_code == 200

    def test_responses_are_identical(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, _ = create_test_user(db_session, email="fp_enum@example.com")
        resp_known = test_client.post(
            "/api/v1/auth/forgot-password",
            json={"email": user.email},
        )
        resp_unknown = test_client.post(
            "/api/v1/auth/forgot-password",
            json={"email": "definitely-not@registered.example.com"},
        )
        assert resp_known.json() == resp_unknown.json()


class TestForgotPasswordTokenGenerated:
    def test_reset_token_generated_for_registered_email(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        from sqlalchemy import select

        from modules.auth.models.password_reset_token import PasswordResetToken

        user, _ = create_test_user(db_session, email="fp_token_check@example.com")
        test_client.post(
            "/api/v1/auth/forgot-password",
            json={"email": user.email},
        )
        # Verify a reset token record was created for the user.
        stmt = select(PasswordResetToken).where(
            PasswordResetToken.user_id == user.id,
            PasswordResetToken.is_consumed == False,  # noqa: E712
        )
        records = list(db_session.execute(stmt).scalars().all())
        assert len(records) >= 1
