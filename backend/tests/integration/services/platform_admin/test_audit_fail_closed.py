"""[T079, T101] [Gate E, Gate C] The single most important correctness
test in the Epic (plan.md §32): a forced constraint violation on the
audit insert rolls back the privileged mutation it was meant to
accompany.

T079 (Gate E, Phase 6) uses the Phase-5 role-assignment mutation (T065,
``PlatformRbacService.assign_role()``) — quickstart.md §9 explicitly
permits "whichever privileged mutation was under test", and this was the
correct choice at Phase 6, before tenant suspension existed.

T101 (Gate C, Phase 7) adds the **fuller** 3-way (now 4-way) proof
against the real tenant-suspension mutation (T088,
``TenantLifecycleService.suspend()``), once it legally exists: a forced
audit-write failure must roll back the ``Company.status`` change, the
``pre_suspension_status`` write, the ``access_invalidated_at`` watermark,
**and** the ``OutboxRecord`` — all four, not just the state change.

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
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from core.events.outbox import EventOutboxRepository, OutboxRecord
from modules.auth.models.user import User
from modules.companies.models.company import Company
from modules.companies.models.enums import CompanyStatus
from modules.companies.repositories.company_repository import CompanyRepository
from modules.platform_admin.models.entitlement_override import EntitlementOverride
from modules.platform_admin.models.platform_administrator import PlatformAdministrator
from modules.platform_admin.models.platform_audit_event import PlatformAuditEvent
from modules.platform_admin.repositories.override_repository import OverrideRepository
from modules.platform_admin.repositories.platform_administrator_repository import (
    PlatformAdministratorRepository,
)
from modules.platform_admin.repositories.platform_audit_repository import (
    PlatformAuditRepository,
)
from modules.platform_admin.repositories.platform_rbac_repository import (
    PlatformRbacRepository,
)
from modules.platform_admin.services.override_service import OverrideService
from modules.platform_admin.services.platform_audit_service import PlatformAuditService
from modules.platform_admin.services.platform_rbac_seed_service import (
    PlatformRbacSeedService,
)
from modules.platform_admin.services.platform_rbac_service import PlatformRbacService
from modules.platform_admin.services.tenant_lifecycle_service import (
    TenantLifecycleService,
)


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


def _make_lifecycle_service(db: Session) -> TenantLifecycleService:
    return TenantLifecycleService(
        db=db,
        company_repo=CompanyRepository(db),
        outbox_repo=EventOutboxRepository(db),
        audit=PlatformAuditService(db, PlatformAuditRepository(db)),
    )


def _make_company_for_suspension(db: Session, *, owner_id) -> Company:
    suffix = uuid.uuid4().hex[:10]
    company = Company(
        legal_name=f"Audit Fail Closed Co {suffix}",
        slug=f"audit-fail-closed-co-{suffix}",
        owner_id=owner_id,
        email=f"audit-fail-closed-co-{suffix}@example.test",
        status=CompanyStatus.active.value,
    )
    db.add(company)
    db.flush()
    db.commit()
    return company


class TestGateCAuditFailClosedOnTenantSuspension:
    """[T101] The fuller 4-way proof: state + pre_suspension_status +
    access_invalidated_at + OutboxRecord all roll back together."""

    def test_forced_audit_write_failure_rolls_back_suspension_and_outbox(
        self, db_session: Session
    ) -> None:
        actor = _make_administrator(db_session, label="suspend-actor")
        company = _make_company_for_suspension(db_session, owner_id=actor.user_id)
        service = _make_lifecycle_service(db_session)

        with patch.object(
            PlatformAuditService,
            "record",
            side_effect=_simulated_constraint_violation(),
        ):
            with pytest.raises(IntegrityError):
                service.suspend(
                    company_id=company.id,
                    actor_platform_administrator_id=actor.id,
                    reason="Gate C forced-failure test",
                )

        # Nothing committed inside suspend() — simulate the real
        # request-teardown rollback.
        db_session.rollback()

        reloaded = db_session.get(Company, company.id)
        assert reloaded is not None
        # 1. Company.status was never persisted as 'suspended'.
        assert reloaded.status == CompanyStatus.active.value
        # 2. pre_suspension_status was never persisted.
        assert reloaded.pre_suspension_status is None
        # 3. The access_invalidated_at watermark was never persisted.
        assert reloaded.access_invalidated_at is None

        # 4. No OutboxRecord for this company survived either.
        outbox_events = (
            db_session.execute(
                select(OutboxRecord).where(OutboxRecord.aggregate_id == str(company.id))
            )
            .scalars()
            .all()
        )
        assert outbox_events == []

        # No audit row either.
        audit_events = (
            db_session.query(PlatformAuditEvent)
            .filter(
                PlatformAuditEvent.company_id == company.id,
                PlatformAuditEvent.action == "tenant_lifecycle.suspend",
            )
            .all()
        )
        assert audit_events == []

    def test_normal_suspension_success_still_commits_all_four(
        self, db_session: Session
    ) -> None:
        """Positive control: without a forced failure, the exact same
        mutation genuinely commits state + watermark + outbox + audit
        together."""
        actor = _make_administrator(db_session, label="suspend-actor-ok")
        company = _make_company_for_suspension(db_session, owner_id=actor.user_id)
        service = _make_lifecycle_service(db_session)

        service.suspend(
            company_id=company.id,
            actor_platform_administrator_id=actor.id,
            reason="Gate C success-path control",
        )

        reloaded = db_session.get(Company, company.id)
        assert reloaded.status == CompanyStatus.suspended.value
        assert reloaded.pre_suspension_status == CompanyStatus.active.value
        assert reloaded.access_invalidated_at is not None

        outbox_events = (
            db_session.execute(
                select(OutboxRecord).where(
                    OutboxRecord.aggregate_id == str(company.id),
                    OutboxRecord.event_type == "company.suspended",
                )
            )
            .scalars()
            .all()
        )
        assert len(outbox_events) == 1

        audit_events = (
            db_session.query(PlatformAuditEvent)
            .filter(
                PlatformAuditEvent.company_id == company.id,
                PlatformAuditEvent.action == "tenant_lifecycle.suspend",
            )
            .all()
        )
        assert len(audit_events) == 1


def _make_override_service(db: Session) -> OverrideService:
    return OverrideService(
        db=db,
        repo=OverrideRepository(db),
        audit=PlatformAuditService(db, PlatformAuditRepository(db)),
    )


def _make_company_for_override(db: Session, *, owner_id: uuid.UUID) -> Company:
    suffix = uuid.uuid4().hex[:10]
    company = Company(
        legal_name=f"Audit Fail Closed Override Co {suffix}",
        slug=f"audit-fail-closed-override-co-{suffix}",
        owner_id=owner_id,
        email=f"audit-fail-closed-override-co-{suffix}@example.test",
        status=CompanyStatus.active.value,
    )
    db.add(company)
    db.flush()
    db.commit()
    return company


class TestPhase11AuditFailClosedOnEntitlementOverrideGrant:
    """[T146/T147] Phase 11's own audit fail-closed proof — representative
    of the three new audited mutation types this phase introduces
    (entitlement override grant/revoke, quota override grant/revoke, AI
    credit adjust), all built on the identical `PlatformAuditService`
    helper already proven generically above (quickstart.md §9: "whichever
    privileged mutation was under test" is sufficient evidence)."""

    def test_forced_audit_write_failure_rolls_back_the_override_grant_too(
        self, db_session: Session
    ) -> None:
        actor = _make_administrator(db_session, label="override-actor")
        company = _make_company_for_override(db_session, owner_id=actor.user_id)
        service = _make_override_service(db_session)

        with patch.object(
            PlatformAuditService,
            "record",
            side_effect=_simulated_constraint_violation(),
        ):
            with pytest.raises(IntegrityError):
                service.grant(
                    company_id=company.id,
                    capability_key="inventory",
                    reason="Phase 11 forced-failure test",
                    actor_platform_administrator_id=actor.id,
                )

        # Nothing committed inside grant() — simulate the real
        # request-teardown rollback.
        db_session.rollback()

        overrides = (
            db_session.query(EntitlementOverride)
            .filter(EntitlementOverride.company_id == company.id)
            .all()
        )
        assert overrides == []

        audit_events = (
            db_session.query(PlatformAuditEvent)
            .filter(
                PlatformAuditEvent.company_id == company.id,
                PlatformAuditEvent.action == "entitlement_override.grant",
            )
            .all()
        )
        assert audit_events == []

    def test_normal_override_grant_success_still_commits_both(
        self, db_session: Session
    ) -> None:
        """Positive control: without a forced failure, the exact same
        mutation genuinely commits the override row and its audit event
        together."""
        actor = _make_administrator(db_session, label="override-actor-ok")
        company = _make_company_for_override(db_session, owner_id=actor.user_id)
        service = _make_override_service(db_session)

        service.grant(
            company_id=company.id,
            capability_key="inventory",
            reason="Phase 11 success-path control",
            actor_platform_administrator_id=actor.id,
        )

        overrides = (
            db_session.query(EntitlementOverride)
            .filter(EntitlementOverride.company_id == company.id)
            .all()
        )
        assert len(overrides) == 1
        assert overrides[0].is_active is True

        audit_events = (
            db_session.query(PlatformAuditEvent)
            .filter(
                PlatformAuditEvent.company_id == company.id,
                PlatformAuditEvent.action == "entitlement_override.grant",
            )
            .all()
        )
        assert len(audit_events) == 1
