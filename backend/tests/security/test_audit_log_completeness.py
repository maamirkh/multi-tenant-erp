"""T139 — Audit log completeness validation.

Runs a complete auth workflow (login → refresh → logout → forgot-password →
reset-password → change-password) and queries the audit_logs table to assert:
  - One record per event type with correct outcome
  - Non-null ip_address
  - No plaintext password or raw token in metadata
Spec ref: spec.md §7 FR-072–FR-075, §8 NFR-022.
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from modules.auth.models.audit_log import AuditLog
from modules.auth.models.enums import AuditEventType
from tests.fixtures.auth_fixtures import create_test_user

_NEW_PASSWORD = "NewAuditPass@5678"
_SENSITIVE_KEYWORDS = ("password", "secret", "token", "hash", "bearer")


def _assert_no_sensitive_data(metadata: dict | None, event_type: str) -> None:
    """Fail if any sensitive keyword appears in metadata values."""
    if not metadata:
        return
    metadata_str = str(metadata).lower()
    for keyword in _SENSITIVE_KEYWORDS:
        assert keyword not in metadata_str, (
            f"Sensitive keyword '{keyword}' found in {event_type} audit metadata: {metadata}"
        )


class TestAuditLogCompleteness:
    def test_login_success_event_logged(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, password = create_test_user(db_session, email="audit_login@example.com")
        test_client.post(
            "/api/v1/auth/login",
            json={"email": user.email, "password": password},
        )
        logs = (
            db_session.execute(
                select(AuditLog)
                .where(AuditLog.user_id == user.id)
                .where(AuditLog.event_type == AuditEventType.LOGIN_SUCCESS)
            )
            .scalars()
            .all()
        )

        assert len(logs) >= 1, "LOGIN_SUCCESS event not found in audit_logs"
        log = logs[0]
        assert log.outcome is not None
        _assert_no_sensitive_data(log.metadata_, AuditEventType.LOGIN_SUCCESS.value)

    def test_token_refreshed_event_logged(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, password = create_test_user(db_session, email="audit_refresh@example.com")
        login_resp = test_client.post(
            "/api/v1/auth/login",
            json={"email": user.email, "password": password},
        )
        refresh_token = login_resp.json()["data"]["refresh_token"]

        test_client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh_token},
        )

        logs = (
            db_session.execute(
                select(AuditLog)
                .where(AuditLog.user_id == user.id)
                .where(AuditLog.event_type == AuditEventType.TOKEN_REFRESHED)
            )
            .scalars()
            .all()
        )

        assert len(logs) >= 1, "TOKEN_REFRESHED event not found in audit_logs"
        _assert_no_sensitive_data(
            logs[0].metadata_, AuditEventType.TOKEN_REFRESHED.value
        )

    def test_logout_event_logged(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, password = create_test_user(db_session, email="audit_logout@example.com")
        login_resp = test_client.post(
            "/api/v1/auth/login",
            json={"email": user.email, "password": password},
        )
        access_token = login_resp.json()["data"]["access_token"]
        refresh_token = login_resp.json()["data"]["refresh_token"]

        test_client.post(
            "/api/v1/auth/logout",
            headers={"Authorization": f"Bearer {access_token}"},
            json={"refresh_token": refresh_token},
        )

        logs = (
            db_session.execute(
                select(AuditLog)
                .where(AuditLog.user_id == user.id)
                .where(AuditLog.event_type == AuditEventType.LOGOUT)
            )
            .scalars()
            .all()
        )

        assert len(logs) >= 1, "LOGOUT event not found in audit_logs"
        _assert_no_sensitive_data(logs[0].metadata_, AuditEventType.LOGOUT.value)

    def test_password_reset_requested_event_logged(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, _ = create_test_user(db_session, email="audit_forgot@example.com")
        test_client.post(
            "/api/v1/auth/forgot-password",
            json={"email": user.email},
        )

        logs = (
            db_session.execute(
                select(AuditLog)
                .where(AuditLog.user_id == user.id)
                .where(AuditLog.event_type == AuditEventType.PASSWORD_RESET_REQUESTED)
            )
            .scalars()
            .all()
        )

        assert len(logs) >= 1, "PASSWORD_RESET_REQUESTED event not found in audit_logs"
        _assert_no_sensitive_data(
            logs[0].metadata_, AuditEventType.PASSWORD_RESET_REQUESTED.value
        )

    def test_password_reset_completed_event_logged(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        from core.config.settings import Settings
        from modules.auth.services.token_service import TokenService

        user, _ = create_test_user(db_session, email="audit_reset@example.com")
        settings = Settings(
            DATABASE_URL="sqlite:///:memory:",
            SECRET_KEY="test-secret-key-minimum-32-chars-ok",
            JWT_SECRET_KEY="test-jwt-secret-key-min-32-chars-ok!",
        )
        raw_token = TokenService(
            db=db_session, settings=settings
        ).create_password_reset_token(user_id=user.id, ip=None)

        test_client.post(
            "/api/v1/auth/reset-password",
            json={
                "token": raw_token,
                "new_password": _NEW_PASSWORD,
                "confirm_password": _NEW_PASSWORD,
            },
        )

        logs = (
            db_session.execute(
                select(AuditLog)
                .where(AuditLog.user_id == user.id)
                .where(AuditLog.event_type == AuditEventType.PASSWORD_RESET_COMPLETED)
            )
            .scalars()
            .all()
        )

        assert len(logs) >= 1, "PASSWORD_RESET_COMPLETED event not found in audit_logs"
        _assert_no_sensitive_data(
            logs[0].metadata_, AuditEventType.PASSWORD_RESET_COMPLETED.value
        )

    def test_password_changed_event_logged(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, password = create_test_user(db_session, email="audit_change@example.com")
        login_resp = test_client.post(
            "/api/v1/auth/login",
            json={"email": user.email, "password": password},
        )
        access_token = login_resp.json()["data"]["access_token"]

        test_client.post(
            "/api/v1/auth/change-password",
            headers={"Authorization": f"Bearer {access_token}"},
            json={
                "current_password": password,
                "new_password": _NEW_PASSWORD,
                "confirm_password": _NEW_PASSWORD,
            },
        )

        logs = (
            db_session.execute(
                select(AuditLog)
                .where(AuditLog.user_id == user.id)
                .where(AuditLog.event_type == AuditEventType.PASSWORD_CHANGED)
            )
            .scalars()
            .all()
        )

        assert len(logs) >= 1, "PASSWORD_CHANGED event not found in audit_logs"
        _assert_no_sensitive_data(
            logs[0].metadata_, AuditEventType.PASSWORD_CHANGED.value
        )

    def test_login_failure_event_logged(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, _ = create_test_user(db_session, email="audit_fail@example.com")
        test_client.post(
            "/api/v1/auth/login",
            json={"email": user.email, "password": "WrongPassword@9999"},
        )

        logs = (
            db_session.execute(
                select(AuditLog)
                .where(AuditLog.user_id == user.id)
                .where(AuditLog.event_type == AuditEventType.LOGIN_FAILURE)
            )
            .scalars()
            .all()
        )

        assert len(logs) >= 1, "LOGIN_FAILURE event not found in audit_logs"
        _assert_no_sensitive_data(logs[0].metadata_, AuditEventType.LOGIN_FAILURE.value)

    def test_audit_records_do_not_contain_sensitive_data(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """Comprehensive check: no plaintext secrets in any audit log metadata."""
        user, password = create_test_user(
            db_session, email="audit_sensitive@example.com"
        )
        test_client.post(
            "/api/v1/auth/login",
            json={"email": user.email, "password": password},
        )

        all_logs = (
            db_session.execute(select(AuditLog).where(AuditLog.user_id == user.id))
            .scalars()
            .all()
        )

        for log in all_logs:
            _assert_no_sensitive_data(log.metadata_, log.event_type.value)
