"""[T091-T093] ``TenantLifecycleService.suspend()``/``reactivate()`` —
the active/inactive round-trip (ADR-12), and repeated-transition
rejection (spec Edge Cases #1/#2).
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from core.events.outbox import EventOutboxRepository, OutboxRecord
from modules.auth.models.user import User
from modules.companies.models.company import Company
from modules.companies.models.enums import CompanyStatus
from modules.companies.repositories.company_repository import CompanyRepository
from modules.platform_admin.exceptions import TenantLifecycleTransitionError
from modules.platform_admin.models.platform_administrator import PlatformAdministrator
from modules.platform_admin.models.platform_audit_event import PlatformAuditEvent
from modules.platform_admin.repositories.platform_audit_repository import (
    PlatformAuditRepository,
)
from modules.platform_admin.services.platform_audit_service import PlatformAuditService
from modules.platform_admin.services.tenant_lifecycle_service import (
    TenantLifecycleService,
)


def _make_actor(db: Session) -> PlatformAdministrator:
    user = User(
        email=f"tenant-lifecycle-actor-{uuid.uuid4().hex[:10]}@example.test",
        display_name="Tenant Lifecycle Actor",
    )
    db.add(user)
    db.flush()
    administrator = PlatformAdministrator(user_id=user.id, is_active=True)
    db.add(administrator)
    db.flush()
    db.commit()
    return administrator


def _make_company(
    db: Session, *, owner_id, status: str = CompanyStatus.active.value
) -> Company:
    suffix = uuid.uuid4().hex[:10]
    company = Company(
        legal_name=f"Tenant Lifecycle Co {suffix}",
        slug=f"tenant-lifecycle-co-{suffix}",
        owner_id=owner_id,
        email=f"tenant-lifecycle-co-{suffix}@example.test",
        status=status,
    )
    db.add(company)
    db.flush()
    db.commit()
    return company


def _make_service(db: Session) -> TenantLifecycleService:
    return TenantLifecycleService(
        db=db,
        company_repo=CompanyRepository(db),
        outbox_repo=EventOutboxRepository(db),
        audit=PlatformAuditService(db, PlatformAuditRepository(db)),
    )


def _audit_events(db: Session, *, company_id, action: str) -> list[PlatformAuditEvent]:
    return list(
        db.execute(
            select(PlatformAuditEvent).where(
                PlatformAuditEvent.company_id == company_id,
                PlatformAuditEvent.action == action,
            )
        )
        .scalars()
        .all()
    )


class TestActiveSuspendedActiveRoundTrip:
    def test_active_to_suspended_to_active(self, db_session: Session) -> None:
        actor = _make_actor(db_session)
        company = _make_company(db_session, owner_id=actor.user_id)
        service = _make_service(db_session)

        suspended = service.suspend(
            company_id=company.id,
            actor_platform_administrator_id=actor.id,
            reason="T091 suspend",
        )
        assert suspended.status == CompanyStatus.suspended.value
        assert suspended.pre_suspension_status == CompanyStatus.active.value
        assert suspended.access_invalidated_at is not None

        reactivated = service.reactivate(
            company_id=company.id,
            actor_platform_administrator_id=actor.id,
            reason="T091 reactivate",
        )
        assert reactivated.status == CompanyStatus.active.value
        assert reactivated.pre_suspension_status is None
        # access_invalidated_at is deliberately never cleared (ADR-6).
        assert reactivated.access_invalidated_at is not None

        suspend_events = _audit_events(
            db_session, company_id=company.id, action="tenant_lifecycle.suspend"
        )
        reactivate_events = _audit_events(
            db_session, company_id=company.id, action="tenant_lifecycle.reactivate"
        )
        assert len(suspend_events) == 1
        suspend_before = suspend_events[0].before_state
        suspend_after = suspend_events[0].after_state
        assert suspend_before is not None
        assert suspend_after is not None
        assert suspend_before["status"] == CompanyStatus.active.value
        assert suspend_after["status"] == CompanyStatus.suspended.value
        assert len(reactivate_events) == 1
        reactivate_before = reactivate_events[0].before_state
        reactivate_after = reactivate_events[0].after_state
        assert reactivate_before is not None
        assert reactivate_after is not None
        assert reactivate_before["status"] == CompanyStatus.suspended.value
        assert reactivate_after["status"] == CompanyStatus.active.value

        outbox_events = list(
            db_session.execute(
                select(OutboxRecord).where(OutboxRecord.aggregate_id == str(company.id))
            )
            .scalars()
            .all()
        )
        event_types = {e.event_type for e in outbox_events}
        assert "company.suspended" in event_types
        assert "company.suspension_lifted" in event_types


class TestInactiveSuspendedInactiveRoundTrip:
    def test_inactive_to_suspended_to_inactive_not_active(
        self, db_session: Session
    ) -> None:
        """The case a hardcoded 'active' restore would silently corrupt."""
        actor = _make_actor(db_session)
        company = _make_company(
            db_session, owner_id=actor.user_id, status=CompanyStatus.inactive.value
        )
        service = _make_service(db_session)

        suspended = service.suspend(
            company_id=company.id,
            actor_platform_administrator_id=actor.id,
            reason="T092 suspend",
        )
        assert suspended.pre_suspension_status == CompanyStatus.inactive.value

        reactivated = service.reactivate(
            company_id=company.id,
            actor_platform_administrator_id=actor.id,
            reason="T092 reactivate",
        )
        assert reactivated.status == CompanyStatus.inactive.value
        assert reactivated.status != CompanyStatus.active.value


class TestRepeatedTransitionsRejected:
    def test_repeated_suspension_is_rejected(self, db_session: Session) -> None:
        actor = _make_actor(db_session)
        company = _make_company(db_session, owner_id=actor.user_id)
        service = _make_service(db_session)

        service.suspend(
            company_id=company.id,
            actor_platform_administrator_id=actor.id,
            reason="first suspend",
        )
        events_before = _audit_events(
            db_session, company_id=company.id, action="tenant_lifecycle.suspend"
        )
        assert len(events_before) == 1

        with pytest.raises(TenantLifecycleTransitionError):
            service.suspend(
                company_id=company.id,
                actor_platform_administrator_id=actor.id,
                reason="second suspend attempt",
            )

        events_after = _audit_events(
            db_session, company_id=company.id, action="tenant_lifecycle.suspend"
        )
        assert len(events_after) == 1, "no duplicate audit row for the rejected attempt"

    def test_repeated_reactivation_is_rejected(self, db_session: Session) -> None:
        actor = _make_actor(db_session)
        company = _make_company(db_session, owner_id=actor.user_id)
        service = _make_service(db_session)

        service.suspend(
            company_id=company.id,
            actor_platform_administrator_id=actor.id,
            reason="suspend before double-reactivate test",
        )
        service.reactivate(
            company_id=company.id,
            actor_platform_administrator_id=actor.id,
            reason="first reactivate",
        )
        events_before = _audit_events(
            db_session, company_id=company.id, action="tenant_lifecycle.reactivate"
        )
        assert len(events_before) == 1

        with pytest.raises(TenantLifecycleTransitionError):
            service.reactivate(
                company_id=company.id,
                actor_platform_administrator_id=actor.id,
                reason="second reactivate attempt",
            )

        events_after = _audit_events(
            db_session, company_id=company.id, action="tenant_lifecycle.reactivate"
        )
        assert len(events_after) == 1, "no duplicate audit row for the rejected attempt"
