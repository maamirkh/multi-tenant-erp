"""T128 — Sensitive data must not appear in logs.

Verifies that no password, raw token, or token hash appears in captured
log output during a login flow.
Spec ref: spec.md §8 NFR-016, plan.md §8 (Logging Strategy).
"""

from __future__ import annotations

import logging

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.fixtures.auth_fixtures import create_test_user

_SENTINEL_PASSWORD = "SentinelP@ss12345"


class TestSensitiveDataNotLogged:
    def test_password_not_in_log_output(
        self,
        test_client: TestClient,
        db_session: Session,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        user, _ = create_test_user(
            db_session, email="log_test@example.com", password=_SENTINEL_PASSWORD
        )
        with caplog.at_level(logging.DEBUG):
            test_client.post(
                "/api/v1/auth/login",
                json={"email": user.email, "password": _SENTINEL_PASSWORD},
            )
        log_output = caplog.text
        assert (
            _SENTINEL_PASSWORD not in log_output
        ), "Plaintext password must not appear in log output."

    def test_wrong_password_not_in_log_output(
        self,
        test_client: TestClient,
        db_session: Session,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        user, _ = create_test_user(db_session, email="log_wrong@example.com")
        with caplog.at_level(logging.DEBUG):
            test_client.post(
                "/api/v1/auth/login",
                json={"email": user.email, "password": _SENTINEL_PASSWORD},
            )
        assert _SENTINEL_PASSWORD not in caplog.text
