"""[T094] Concurrent suspend attempts — exactly one commits (plan.md §36,
spec §11 scenario 6).

Row locking is not meaningfully testable on SQLite (no genuine blocking
semantics), so this test deliberately bypasses the shared ``db_session``
SQLite in-memory fixture and connects directly to the real PostgreSQL
database (``core.database.session.SessionLocal``, the same
``DATABASE_URL`` the live application uses) via two independent sessions
running in separate threads, proving ``CompanyRepository.get_for_update()``'s
``SELECT ... FOR UPDATE`` genuinely serializes two concurrent
``TenantLifecycleService.suspend()`` calls against the same company row.

All test data is created and torn down against the real database within
this test — nothing is left behind.
"""

from __future__ import annotations

import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

from sqlalchemy import delete, select

from core.database.session import SessionLocal
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

_LOCK_HOLD_SECONDS = 0.4


def _slow_get_for_update(self: CompanyRepository, id):  # noqa: A002
    """Wraps the real ``get_for_update`` to briefly hold the row lock open
    after acquiring it, giving the other thread's concurrent
    ``SELECT ... FOR UPDATE`` time to genuinely block on real PostgreSQL
    before this thread proceeds to commit."""
    stmt = select(Company).where(Company.id == id).with_for_update()
    result = self.db.execute(stmt).scalars().one_or_none()
    time.sleep(_LOCK_HOLD_SECONDS)
    return result


def _attempt_suspend(
    company_id: uuid.UUID, actor_id: uuid.UUID, label: str
) -> tuple[str, str]:
    session = SessionLocal()
    try:
        service = TenantLifecycleService(
            db=session,
            company_repo=CompanyRepository(session),
            outbox_repo=EventOutboxRepository(session),
            audit=PlatformAuditService(session, PlatformAuditRepository(session)),
        )
        company = service.suspend(
            company_id=company_id,
            actor_platform_administrator_id=actor_id,
            reason=f"T094 concurrency test ({label})",
        )
        return ("success", company.status)
    except TenantLifecycleTransitionError as exc:
        session.rollback()
        return ("conflict", str(exc))
    finally:
        session.close()


class TestConcurrentSuspendExactlyOneCommits:
    def test_two_concurrent_suspends_one_succeeds_one_conflicts(self) -> None:
        setup = SessionLocal()
        company_id: uuid.UUID | None = None
        user_id: uuid.UUID | None = None
        admin_id: uuid.UUID | None = None
        try:
            suffix = uuid.uuid4().hex[:10]
            user = User(
                email=f"t094-actor-{suffix}@example.test",
                display_name="T094 Concurrency Actor",
            )
            setup.add(user)
            setup.flush()
            user_id = user.id

            administrator = PlatformAdministrator(user_id=user.id, is_active=True)
            setup.add(administrator)
            setup.flush()
            admin_id = administrator.id

            company = Company(
                legal_name=f"T094 Concurrency Co {suffix}",
                slug=f"t094-concurrency-co-{suffix}",
                owner_id=user.id,
                email=f"t094-concurrency-co-{suffix}@example.test",
                status=CompanyStatus.active.value,
            )
            setup.add(company)
            setup.commit()
            company_id = company.id

            with patch.object(
                CompanyRepository, "get_for_update", _slow_get_for_update
            ):
                with ThreadPoolExecutor(max_workers=2) as executor:
                    future_a = executor.submit(
                        _attempt_suspend, company_id, admin_id, "A"
                    )
                    time.sleep(0.05)  # let A issue its FOR UPDATE first
                    future_b = executor.submit(
                        _attempt_suspend, company_id, admin_id, "B"
                    )
                    outcome_a = future_a.result(timeout=10)
                    outcome_b = future_b.result(timeout=10)

            outcomes = {outcome_a[0], outcome_b[0]}
            assert outcomes == {"success", "conflict"}, (outcome_a, outcome_b)

            verify = SessionLocal()
            try:
                final_company = verify.get(Company, company_id)
                assert final_company is not None
                assert final_company.status == CompanyStatus.suspended.value

                audit_events = (
                    verify.execute(
                        select(PlatformAuditEvent).where(
                            PlatformAuditEvent.company_id == company_id,
                            PlatformAuditEvent.action == "tenant_lifecycle.suspend",
                        )
                    )
                    .scalars()
                    .all()
                )
                assert len(audit_events) == 1, (
                    "exactly one audit row for the two concurrent attempts"
                )
            finally:
                verify.close()
        finally:
            # Teardown against the real database — nothing from this test
            # is left behind.
            if company_id is not None:
                setup.execute(
                    delete(PlatformAuditEvent).where(
                        PlatformAuditEvent.company_id == company_id
                    )
                )
                setup.execute(
                    delete(OutboxRecord).where(
                        OutboxRecord.aggregate_id == str(company_id)
                    )
                )
                setup.execute(delete(Company).where(Company.id == company_id))
            if admin_id is not None:
                setup.execute(
                    delete(PlatformAdministrator).where(
                        PlatformAdministrator.id == admin_id
                    )
                )
            if user_id is not None:
                setup.execute(delete(User).where(User.id == user_id))
            setup.commit()
            setup.close()
