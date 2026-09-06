"""T102 — Integration tests for AuditLogRepository.

Verifies append-only semantics: create, list with filters, and absence of
update/delete methods.
"""

from __future__ import annotations

import uuid
from datetime import timedelta

from sqlalchemy.orm import Session

from core.utils.datetime import utcnow
from modules.auth.models.enums import AuditEventType
from modules.auth.repositories.audit_log_repository import AuditLogRepository


class TestCreate:
    def test_persists_audit_event(self, db_session: Session) -> None:
        user_id = uuid.uuid4()
        repo = AuditLogRepository(db_session)
        entry = repo.create(
            event_type=AuditEventType.LOGIN_SUCCESS,
            outcome="SUCCESS",
            user_id=user_id,
            ip_address="192.168.1.1",
            user_agent="TestAgent/1.0",
        )
        assert entry.id is not None
        assert entry.event_type == AuditEventType.LOGIN_SUCCESS
        assert entry.outcome == "SUCCESS"
        assert entry.user_id == user_id


class TestListByUserId:
    def test_filters_by_user_id(self, db_session: Session) -> None:
        uid_a = uuid.uuid4()
        uid_b = uuid.uuid4()
        repo = AuditLogRepository(db_session)
        repo.create(AuditEventType.LOGIN_SUCCESS, "SUCCESS", user_id=uid_a)
        repo.create(AuditEventType.LOGIN_FAILURE, "FAILURE", user_id=uid_b)

        results = repo.list_by_user_id(uid_a)
        assert len(results) == 1
        assert results[0].user_id == uid_a

    def test_filters_by_time_range(self, db_session: Session) -> None:
        uid = uuid.uuid4()
        repo = AuditLogRepository(db_session)
        repo.create(AuditEventType.LOGIN_SUCCESS, "SUCCESS", user_id=uid)

        future = utcnow() + timedelta(hours=1)
        # from_dt in the future → no results.
        results = repo.list_by_user_id(uid, from_dt=future)
        assert results == []

    def test_returns_empty_list_for_unknown_user(self, db_session: Session) -> None:
        repo = AuditLogRepository(db_session)
        assert repo.list_by_user_id(uuid.uuid4()) == []


class TestAppendOnly:
    def test_no_update_method_exposed(self) -> None:
        """AuditLogRepository must NOT expose an update method."""
        assert not hasattr(AuditLogRepository, "update"), (
            "AuditLogRepository must be append-only — no update method allowed."
        )

    def test_no_delete_method_exposed(self) -> None:
        """AuditLogRepository must NOT expose a delete method."""
        assert not hasattr(AuditLogRepository, "delete"), (
            "AuditLogRepository must be append-only — no delete method allowed."
        )
