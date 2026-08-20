"""[T079] [Gate E] The single most important correctness test in the
Epic (plan.md §32): a forced constraint violation on the audit insert
rolls back the privileged mutation it was meant to accompany.

Uses the Phase-5 role-assignment mutation (T065,
``PlatformRbacService.assign_role()``) as the real privileged mutation
under test — quickstart.md §9 explicitly permits "whichever privileged
mutation was under test", and this is the correct choice per Revision 2's
own note on T079: it legally exists in Phase 1-6 work, unlike the
tenant-suspension mutation (Phase 7, T101), which would be a forward
reference.

Simulates the constraint violation via ``unittest.mock.patch.object``
raising a real ``sqlalchemy.exc.IntegrityError`` from
``PlatformAuditService.record()`` — the same technique T044 (Phase 3)
already established and this Epic accepted as sufficient evidence for
this exact atomicity property. A literal FK-violation-based test is not
feasible under this suite's SQLite in-memory fixture, which does not
enable ``PRAGMA foreign_keys`` (verified: no such pragma exists anywhere
in ``tests/conftest.py``) — so a bad foreign key would silently insert
rather than raise. Raising the exact exception TYPE a real PostgreSQL
constraint violation surfaces as (``IntegrityError``) keeps this
simulation faithful to "constraint violation" while remaining runnable
under the existing test infrastructure.
"""

from __future__ import annotations

import uuid
from unittest.mock import patch

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from modules.auth.models.user import User
from modules.platform_admin.models.platform_administrator import PlatformAdministrator
from modules.platform_admin.models.platform_audit_event import PlatformAuditEvent
from modules.platform_admin.repositories.platform_administrator_repository import (
    PlatformAdministratorRepository,
)
from modules.platform_admin.repositories.platform_audit_repository import (
    PlatformAuditRepository,
)
from modules.platform_admin.repositories.platform_rbac_repository import (
    PlatformRbacRepository,
)
from modules.platform_admin.services.platform_audit_service import PlatformAuditService
from modules.platform_admin.services.platform_rbac_seed_service import (
    PlatformRbacSeedService,
)
from modules.platform_admin.services.platform_rbac_service import PlatformRbacService


def _make_administrator(db: Session, *, label: str) -> PlatformAdministrator:
    user = User(
        email=f"audit-fail-closed-{label}-{uuid.uuid4().hex[:10]}@example.test",
        display_name=f"Audit Fail Closed {label}",
    )
    db.add(user)
    db.flush()
    administrator = PlatformAdministrator(user_id=user.id, is_active=True)
    db.add(administrator)
    db.flush()
    db.commit()
    return administrator


def _make_service(db: Session) -> PlatformRbacService:
    return PlatformRbacService(
        db=db,
        repo=PlatformRbacRepository(db),
        admin_repo=PlatformAdministratorRepository(db),
        audit=PlatformAuditService(db, PlatformAuditRepository(db)),
    )


def _simulated_constraint_violation() -> IntegrityError:
    return IntegrityError(
        statement="INSERT INTO platform_audit_events (...) VALUES (...)",
        params=None,
        orig=Exception(
            "simulated NOT NULL constraint violation on platform_audit_events"
        ),
    )


class TestGateEAuditFailClosedOnRoleAssignment:
    def test_forced_audit_write_failure_rolls_back_the_role_assignment_too(
        self, db_session: Session
    ) -> None:
        rbac_repo = PlatformRbacRepository(db_session)
        PlatformRbacSeedService(db_session, rbac_repo).seed_all()
        # A non-owner role — keeps this test orthogonal to self-escalation
        # (T065/T075's separate, already-proven concern).
        role = rbac_repo.get_role_by_code("read_only_platform_analyst")
        assert role is not None

        actor = _make_administrator(db_session, label="actor")
        target = _make_administrator(db_session, label="target")
        service = _make_service(db_session)

        with patch.object(
            PlatformAuditService,
            "record",
            side_effect=_simulated_constraint_violation(),
        ):
            with pytest.raises(IntegrityError):
                service.assign_role(
                    platform_administrator_id=target.id,
                    role_id=role.id,
                    actor_platform_administrator_id=actor.id,
                    reason="Gate E forced-failure test",
                )

        # No db.commit() was ever reached inside assign_role() — simulate
        # the request-teardown rollback a real unhandled exception
        # triggers (get_db()'s finally: db.close() rolls back any
        # uncommitted transaction).
        db_session.rollback()

        # The role assignment must NOT exist — it was staged (flush-only,
        # ADR-5) but never committed, and the rollback undid the flush too.
        assert rbac_repo.has_role(target.id, role.code) is False

        # No audit row exists for this attempt either — the simulated
        # exception was raised before the (mocked) insert could genuinely
        # persist, and nothing else in the transaction survived.
        events = (
            db_session.query(PlatformAuditEvent)
            .filter(PlatformAuditEvent.actor_platform_administrator_id == actor.id)
            .all()
        )
        assert events == []

    def test_normal_audit_success_still_commits_the_role_assignment(
        self, db_session: Session
    ) -> None:
        """The positive control: without a forced failure, the exact same
        mutation genuinely commits both rows together — proving the test
        harness isn't accidentally preventing success in general."""
        rbac_repo = PlatformRbacRepository(db_session)
        PlatformRbacSeedService(db_session, rbac_repo).seed_all()
        role = rbac_repo.get_role_by_code("read_only_platform_analyst")
        assert role is not None

        actor = _make_administrator(db_session, label="actor-ok")
        target = _make_administrator(db_session, label="target-ok")
        service = _make_service(db_session)

        service.assign_role(
            platform_administrator_id=target.id,
            role_id=role.id,
            actor_platform_administrator_id=actor.id,
            reason="Gate E success-path control",
        )

        assert rbac_repo.has_role(target.id, role.code) is True
        events = (
            db_session.query(PlatformAuditEvent)
            .filter(
                PlatformAuditEvent.actor_platform_administrator_id == actor.id,
                PlatformAuditEvent.action == "platform_rbac.role.assign",
            )
            .all()
        )
        assert len(events) == 1
