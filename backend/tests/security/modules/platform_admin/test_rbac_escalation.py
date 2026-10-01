"""[T075] Self-escalation and last-Platform-Owner removal are both
rejected, cause no state change, and are both audited.

Exercises `PlatformRbacService` directly (Deps: T066 only — this proof
must stand on Phase 1-5 service-layer work alone, independent of the
T068/T069 HTTP routes, which T076 covers separately).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from modules.auth.models.user import User
from modules.platform_admin.exceptions import (
    LastPlatformOwnerError,
    SelfEscalationError,
)
from modules.platform_admin.models.platform_administrator import PlatformAdministrator
from modules.platform_admin.models.platform_audit_event import PlatformAuditEvent
from modules.platform_admin.models.platform_rbac import PlatformAdminRoleAssignment
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
from modules.platform_admin.services.platform_rbac_service import PlatformRbacService


def _make_administrator(db: Session, *, label: str) -> PlatformAdministrator:
    user = User(
        email=f"rbac-escalation-{label}-{uuid.uuid4().hex[:10]}@example.test",
        display_name=f"RBAC Escalation {label}",
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


def _seed_and_get_owner_role(rbac_repo: PlatformRbacRepository, db: Session):
    from modules.platform_admin.services.platform_rbac_seed_service import (
        PlatformRbacSeedService,
    )

    PlatformRbacSeedService(db, rbac_repo).seed_all()
    role = rbac_repo.get_role_by_code("platform_owner")
    assert role is not None
    return role


def _count_owner_assignments(db: Session, administrator_id) -> int:
    return (
        db.query(PlatformAdminRoleAssignment)
        .filter(
            PlatformAdminRoleAssignment.platform_administrator_id == administrator_id
        )
        .count()
    )


class TestSelfEscalationRejected:
    def test_non_owner_actor_cannot_grant_platform_owner_role(
        self, db_session: Session
    ) -> None:
        rbac_repo = PlatformRbacRepository(db_session)
        owner_role = _seed_and_get_owner_role(rbac_repo, db_session)

        actor = _make_administrator(db_session, label="non-owner-actor")
        target = _make_administrator(db_session, label="escalation-target")
        service = _make_service(db_session)

        assignments_before = _count_owner_assignments(db_session, target.id)
        audit_count_before = db_session.query(PlatformAuditEvent).count()

        with pytest.raises(SelfEscalationError):
            service.assign_role(
                platform_administrator_id=target.id,
                role_id=owner_role.id,
                actor_platform_administrator_id=actor.id,
                reason="attempted self-escalation",
            )

        # No state change: target gained no role assignment at all.
        assert _count_owner_assignments(db_session, target.id) == assignments_before

        # The rejected attempt IS audited.
        audit_events = (
            db_session.execute(
                select(PlatformAuditEvent)
                .where(PlatformAuditEvent.action == "platform_rbac.role.assign.denied")
                .where(PlatformAuditEvent.actor_platform_administrator_id == actor.id)
            )
            .scalars()
            .all()
        )
        assert len(audit_events) == 1
        after_state = audit_events[0].after_state
        assert after_state is not None
        assert after_state["denial_reason"] == "self_escalation"
        assert after_state["platform_administrator_id"] == str(target.id)
        assert db_session.query(PlatformAuditEvent).count() == audit_count_before + 1

    def test_actor_who_already_holds_owner_role_can_grant_it(
        self, db_session: Session
    ) -> None:
        """Negative-of-the-negative: proves the guard is specific to
        non-owner actors, not a blanket ban on granting the role at all."""
        rbac_repo = PlatformRbacRepository(db_session)
        owner_role = _seed_and_get_owner_role(rbac_repo, db_session)

        actor = _make_administrator(db_session, label="existing-owner-actor")
        # assigned_by=actor.id (self), NOT None: migration 057 reserves
        # assigned_by IS NULL exclusively for the genuine bootstrap-created
        # first assignment (see test_bootstrap.py) — this is direct test
        # setup, not a bootstrap flow.
        rbac_repo.assign_role(
            platform_administrator_id=actor.id,
            role_id=owner_role.id,
            assigned_by=actor.id,
            assigned_at=datetime.now(UTC),
        )
        db_session.commit()

        target = _make_administrator(db_session, label="legitimate-grant-target")
        service = _make_service(db_session)

        assignment = service.assign_role(
            platform_administrator_id=target.id,
            role_id=owner_role.id,
            actor_platform_administrator_id=actor.id,
        )

        assert assignment.platform_administrator_id == target.id
        assert assignment.role_id == owner_role.id
        assert _count_owner_assignments(db_session, target.id) == 1


def _isolate_as_sole_owner(
    db: Session, rbac_repo: PlatformRbacRepository, owner_role, keep_admin_id
) -> None:
    """Remove every OTHER `platform_owner` assignment so *keep_admin_id* is
    deterministically the last one. Necessary because `count_active_
    administrators_with_role()` is a genuine global count with no
    per-test scope, and this test file's own earlier tests (plus
    cross-test leakage from the shared `db_session` fixture, documented
    in Phase 3/4/5 PHRs) can otherwise leave other owner-holding
    administrators in the same session's database. Uses the repository
    directly — not `PlatformRbacService.remove_role_assignment()` — to
    bypass the very guard under test while setting up its precondition.
    """
    stmt = select(PlatformAdminRoleAssignment.platform_administrator_id).where(
        PlatformAdminRoleAssignment.role_id == owner_role.id,
        PlatformAdminRoleAssignment.platform_administrator_id != keep_admin_id,
    )
    for other_admin_id in db.execute(stmt).scalars().all():
        rbac_repo.remove_assignment(
            platform_administrator_id=other_admin_id, role_id=owner_role.id
        )
    db.commit()


class TestLastPlatformOwnerRemovalRejected:
    def test_removing_the_sole_owners_role_assignment_is_rejected(
        self, db_session: Session
    ) -> None:
        rbac_repo = PlatformRbacRepository(db_session)
        owner_role = _seed_and_get_owner_role(rbac_repo, db_session)

        sole_owner = _make_administrator(db_session, label="sole-owner")
        rbac_repo.assign_role(
            platform_administrator_id=sole_owner.id,
            role_id=owner_role.id,
            assigned_by=sole_owner.id,
            assigned_at=datetime.now(UTC),
        )
        db_session.commit()
        _isolate_as_sole_owner(db_session, rbac_repo, owner_role, sole_owner.id)

        actor = _make_administrator(db_session, label="removal-actor")
        service = _make_service(db_session)

        assignments_before = _count_owner_assignments(db_session, sole_owner.id)
        audit_count_before = db_session.query(PlatformAuditEvent).count()

        with pytest.raises(LastPlatformOwnerError):
            service.remove_role_assignment(
                platform_administrator_id=sole_owner.id,
                role_id=owner_role.id,
                actor_platform_administrator_id=actor.id,
                reason="attempted last-owner removal",
            )

        # No state change: the assignment still exists.
        assert _count_owner_assignments(db_session, sole_owner.id) == assignments_before
        assert rbac_repo.has_role(sole_owner.id, "platform_owner")

        # The rejected attempt IS audited.
        audit_events = (
            db_session.execute(
                select(PlatformAuditEvent)
                .where(
                    PlatformAuditEvent.action
                    == "platform_rbac.last_owner_removal.denied"
                )
                .where(PlatformAuditEvent.actor_platform_administrator_id == actor.id)
            )
            .scalars()
            .all()
        )
        assert len(audit_events) == 1
        after_state = audit_events[0].after_state
        assert after_state is not None
        assert after_state["denial_reason"] == "last_platform_owner"
        assert audit_events[0].target_id == sole_owner.id
        assert db_session.query(PlatformAuditEvent).count() == audit_count_before + 1

    def test_removing_owner_role_when_a_second_owner_exists_succeeds(
        self, db_session: Session
    ) -> None:
        """Negative-of-the-negative: the guard blocks the LAST owner only,
        not owner-role removal in general."""
        rbac_repo = PlatformRbacRepository(db_session)
        owner_role = _seed_and_get_owner_role(rbac_repo, db_session)

        first_owner = _make_administrator(db_session, label="first-owner")
        second_owner = _make_administrator(db_session, label="second-owner")
        for admin in (first_owner, second_owner):
            rbac_repo.assign_role(
                platform_administrator_id=admin.id,
                role_id=owner_role.id,
                assigned_by=admin.id,
                assigned_at=datetime.now(UTC),
            )
        db_session.commit()

        actor = _make_administrator(db_session, label="removal-actor-2")
        service = _make_service(db_session)

        service.remove_role_assignment(
            platform_administrator_id=first_owner.id,
            role_id=owner_role.id,
            actor_platform_administrator_id=actor.id,
        )

        assert not rbac_repo.has_role(first_owner.id, "platform_owner")
        assert rbac_repo.has_role(second_owner.id, "platform_owner")
