"""[T044, ADR-5] The audit foundation writes atomically on a trivial
audited action.

plan.md §36 Phase A: "audit foundation proven with a trivial first
audited action", before any complex mutation depends on it. Also covers
the master-prompt's §20 fail-closed proof requirement: BOTH the normal
success path (mutation + audit commit together) AND the forced-failure
path (audit write fails → the state change is rolled back too) — a test
that only checks an audit row eventually exists is insufficient.
"""

from __future__ import annotations

import uuid
from unittest.mock import patch

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from modules.auth.models.user import User
from modules.platform_admin.models.platform_audit_event import PlatformAuditEvent
from modules.platform_admin.repositories.platform_administrator_repository import (
    PlatformAdministratorRepository,
)
from modules.platform_admin.repositories.platform_audit_repository import (
    PlatformAuditRepository,
)
from modules.platform_admin.services.platform_administrator_service import (
    PlatformAdministratorService,
)
from modules.platform_admin.services.platform_audit_service import PlatformAuditService


def _make_service(db: Session) -> PlatformAdministratorService:
    admin_repo = PlatformAdministratorRepository(db)
    audit_repo = PlatformAuditRepository(db)
    audit_service = PlatformAuditService(db, audit_repo)
    return PlatformAdministratorService(db, admin_repo, audit_service)


def _create_active_administrator(db: Session, service: PlatformAdministratorService):
    # Unique email per call: the shared test database may carry rows
    # committed by other tests in the same session.
    email = f"audit-trivial-{uuid.uuid4().hex[:12]}@example.test"
    user = User(email=email, display_name="Audit Trivial")
    db.add(user)
    db.flush()
    return service.create(user_id=user.id, actor_platform_administrator_id=None)


class TestAuditFoundationSuccess:
    def test_deactivation_writes_exactly_one_audit_event_atomically(
        self, db_session: Session
    ) -> None:
        service = _make_service(db_session)
        administrator = _create_active_administrator(db_session, service)

        service.deactivate(
            administrator,
            actor_platform_administrator_id=None,
            reason="trivial audited action test",
        )

        assert administrator.is_active is False

        events = (
            db_session.execute(
                select(PlatformAuditEvent).where(
                    PlatformAuditEvent.target_id == administrator.id,
                    PlatformAuditEvent.action == "platform_administrator.deactivate",
                )
            )
            .scalars()
            .all()
        )
        assert len(events) == 1
        event = events[0]
        assert event.before_state == {"is_active": True}
        assert event.after_state == {"is_active": False}
        assert event.target_type == "PlatformAdministrator"
        assert event.reason == "trivial audited action test"


class TestAuditFoundationFailClosed:
    def test_forced_audit_write_failure_rolls_back_the_state_change_too(
        self, db_session: Session
    ) -> None:
        service = _make_service(db_session)
        administrator = _create_active_administrator(db_session, service)
        administrator_id = administrator.id

        with patch.object(
            PlatformAuditService,
            "record",
            side_effect=RuntimeError("simulated audit-write failure"),
        ):
            with pytest.raises(RuntimeError, match="simulated audit-write failure"):
                service.deactivate(
                    administrator,
                    actor_platform_administrator_id=None,
                    reason="forced failure test",
                )

        # No db.commit() was ever reached — simulate the request-teardown
        # rollback that a real unhandled exception triggers (get_db()'s
        # finally: db.close() internally rolls back any uncommitted
        # transaction).
        db_session.rollback()

        repo = PlatformAdministratorRepository(db_session)
        reloaded = repo.get_by_id(administrator_id)
        assert reloaded is not None
        assert (
            reloaded.is_active is True
        ), "the state change must not survive a failed audit write"
        assert reloaded.deactivated_at is None

        # Scoped to the "deactivate" action specifically — the earlier,
        # successful "create" call (before the patch was installed) legally
        # committed its own audit event for the same target_id, and must
        # NOT be mistaken for a leftover from the failed mutation.
        deactivate_events = (
            db_session.execute(
                select(PlatformAuditEvent).where(
                    PlatformAuditEvent.target_id == administrator_id,
                    PlatformAuditEvent.action == "platform_administrator.deactivate",
                )
            )
            .scalars()
            .all()
        )
        assert (
            deactivate_events == []
        ), "no deactivate audit row may exist for a rolled-back mutation"
