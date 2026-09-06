"""[T078] [FR-9A-200] Platform audit query service — filter + paginate.

Exercises ``PlatformAuditQueryService`` (a thin pass-through) via
``PlatformAuditRepository.list_filtered()`` against real audit rows.
Every test scopes its assertions to actor/action values it creates
itself, since the shared ``db_session`` fixture does not isolate
committed rows across test functions within one pytest session
(documented cross-test leakage property, Phase 3/4/5 PHRs).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from modules.auth.models.user import User
from modules.platform_admin.models.platform_administrator import PlatformAdministrator
from modules.platform_admin.repositories.platform_audit_repository import (
    PlatformAuditRepository,
)
from modules.platform_admin.services.platform_audit_query_service import (
    PlatformAuditQueryService,
)


def _make_administrator(db: Session) -> PlatformAdministrator:
    user = User(
        email=f"audit-query-{uuid.uuid4().hex[:12]}@example.test",
        display_name="Audit Query Admin",
    )
    db.add(user)
    db.flush()
    administrator = PlatformAdministrator(user_id=user.id, is_active=True)
    db.add(administrator)
    db.flush()
    db.commit()
    return administrator


def _service(db: Session) -> PlatformAuditQueryService:
    return PlatformAuditQueryService(PlatformAuditRepository(db))


class TestFilterByActor:
    def test_filters_to_exactly_the_requested_actor(self, db_session: Session) -> None:
        actor_a = _make_administrator(db_session)
        actor_b = _make_administrator(db_session)
        repo = PlatformAuditRepository(db_session)
        tag = uuid.uuid4().hex[:8]
        repo.record(
            action=f"test.audit_query.{tag}.a1",
            target_type="Widget",
            actor_platform_administrator_id=actor_a.id,
        )
        repo.record(
            action=f"test.audit_query.{tag}.b1",
            target_type="Widget",
            actor_platform_administrator_id=actor_b.id,
        )
        db_session.commit()

        items, total = _service(db_session).query(
            actor_platform_administrator_id=actor_a.id
        )

        assert total >= 1
        assert all(i.actor_platform_administrator_id == actor_a.id for i in items)
        assert any(i.action == f"test.audit_query.{tag}.a1" for i in items)
        assert not any(i.action == f"test.audit_query.{tag}.b1" for i in items)


class TestFilterByCompany:
    def test_filters_to_exactly_the_requested_company(
        self, db_session: Session
    ) -> None:
        from modules.companies.models.company import Company

        actor = _make_administrator(db_session)
        suffix = uuid.uuid4().hex[:10]
        company = Company(
            legal_name=f"Audit Query Co {suffix}",
            slug=f"audit-query-co-{suffix}",
            owner_id=actor.user_id,
            email=f"audit-query-co-{suffix}@example.test",
        )
        db_session.add(company)
        db_session.flush()
        db_session.commit()

        repo = PlatformAuditRepository(db_session)
        repo.record(
            action="test.audit_query.company_scoped",
            target_type="Company",
            actor_platform_administrator_id=actor.id,
            company_id=company.id,
        )
        repo.record(
            action="test.audit_query.company_scoped",
            target_type="Company",
            actor_platform_administrator_id=actor.id,
            company_id=None,
        )
        db_session.commit()

        items, total = _service(db_session).query(company_id=company.id)

        assert total >= 1
        assert all(i.company_id == company.id for i in items)


class TestFilterByAction:
    def test_filters_by_exact_action_match(self, db_session: Session) -> None:
        actor = _make_administrator(db_session)
        tag = uuid.uuid4().hex[:8]
        exact_action = f"test.audit_query.{tag}.exact"
        repo = PlatformAuditRepository(db_session)
        repo.record(
            action=exact_action,
            target_type="Widget",
            actor_platform_administrator_id=actor.id,
        )
        repo.record(
            action=f"test.audit_query.{tag}.exact.but_longer",
            target_type="Widget",
            actor_platform_administrator_id=actor.id,
        )
        db_session.commit()

        items, total = _service(db_session).query(
            actor_platform_administrator_id=actor.id, action=exact_action
        )

        assert total == 1
        assert items[0].action == exact_action


class TestFilterByResource:
    def test_filters_by_target_type_and_target_id(self, db_session: Session) -> None:
        actor = _make_administrator(db_session)
        target_id = uuid.uuid4()
        repo = PlatformAuditRepository(db_session)
        repo.record(
            action="test.audit_query.resource_match",
            target_type="Widget",
            target_id=target_id,
            actor_platform_administrator_id=actor.id,
        )
        repo.record(
            action="test.audit_query.resource_match",
            target_type="Widget",
            target_id=uuid.uuid4(),
            actor_platform_administrator_id=actor.id,
        )
        db_session.commit()

        items, total = _service(db_session).query(
            actor_platform_administrator_id=actor.id,
            target_type="Widget",
            target_id=target_id,
        )

        assert total == 1
        assert items[0].target_id == target_id


class TestFilterByDateRange:
    def test_filters_by_created_after_and_before(self, db_session: Session) -> None:
        actor = _make_administrator(db_session)
        repo = PlatformAuditRepository(db_session)
        repo.record(
            action="test.audit_query.date_range",
            target_type="Widget",
            actor_platform_administrator_id=actor.id,
        )
        db_session.commit()

        far_future = datetime.now(UTC) + timedelta(days=3650)
        far_past = datetime.now(UTC) - timedelta(days=3650)

        items_within, total_within = _service(db_session).query(
            actor_platform_administrator_id=actor.id,
            created_after=far_past,
            created_before=far_future,
        )
        assert total_within >= 1

        items_after_future, total_after_future = _service(db_session).query(
            actor_platform_administrator_id=actor.id, created_after=far_future
        )
        assert total_after_future == 0
        assert items_after_future == []

        items_before_past, total_before_past = _service(db_session).query(
            actor_platform_administrator_id=actor.id, created_before=far_past
        )
        assert total_before_past == 0


class TestFilterByOutcome:
    def test_denied_outcome_matches_only_dot_denied_actions(
        self, db_session: Session
    ) -> None:
        actor = _make_administrator(db_session)
        tag = uuid.uuid4().hex[:8]
        repo = PlatformAuditRepository(db_session)
        repo.record(
            action=f"test.audit_query.{tag}.assign",
            target_type="Widget",
            actor_platform_administrator_id=actor.id,
        )
        repo.record(
            action=f"test.audit_query.{tag}.assign.denied",
            target_type="Widget",
            actor_platform_administrator_id=actor.id,
        )
        db_session.commit()

        denied_items, denied_total = _service(db_session).query(
            actor_platform_administrator_id=actor.id, outcome="denied"
        )
        success_items, success_total = _service(db_session).query(
            actor_platform_administrator_id=actor.id, outcome="success"
        )

        assert denied_total == 1
        assert denied_items[0].action == f"test.audit_query.{tag}.assign.denied"
        assert success_total == 1
        assert success_items[0].action == f"test.audit_query.{tag}.assign"


class TestPagination:
    def test_offset_and_limit_paginate_correctly_with_accurate_total(
        self, db_session: Session
    ) -> None:
        actor = _make_administrator(db_session)
        tag = uuid.uuid4().hex[:8]
        repo = PlatformAuditRepository(db_session)
        for i in range(5):
            repo.record(
                action=f"test.audit_query.{tag}.page.{i}",
                target_type="Widget",
                actor_platform_administrator_id=actor.id,
            )
        db_session.commit()

        page1, total1 = _service(db_session).query(
            actor_platform_administrator_id=actor.id, offset=0, limit=2
        )
        page2, total2 = _service(db_session).query(
            actor_platform_administrator_id=actor.id, offset=2, limit=2
        )
        page3, total3 = _service(db_session).query(
            actor_platform_administrator_id=actor.id, offset=4, limit=2
        )

        assert total1 == total2 == total3 == 5
        assert len(page1) == 2
        assert len(page2) == 2
        assert len(page3) == 1
        all_ids = {i.id for i in page1} | {i.id for i in page2} | {i.id for i in page3}
        assert len(all_ids) == 5

    def test_results_ordered_newest_first(self, db_session: Session) -> None:
        # created_at is set explicitly (not left to server_default `now()`)
        # since two rows committed back-to-back can otherwise land in the
        # same timestamp tick under SQLite's resolution, making relative
        # order between them nondeterministic — the property under test is
        # "given events with distinct timestamps, the newer one sorts
        # first", not "the DB clock has sub-millisecond resolution".
        actor = _make_administrator(db_session)
        tag = uuid.uuid4().hex[:8]
        repo = PlatformAuditRepository(db_session)
        older = repo.record(
            action=f"test.audit_query.{tag}.order.first",
            target_type="Widget",
            actor_platform_administrator_id=actor.id,
        )
        older.created_at = datetime.now(UTC) - timedelta(hours=1)
        newer = repo.record(
            action=f"test.audit_query.{tag}.order.second",
            target_type="Widget",
            actor_platform_administrator_id=actor.id,
        )
        newer.created_at = datetime.now(UTC)
        db_session.commit()

        items, _ = _service(db_session).query(actor_platform_administrator_id=actor.id)

        ours = [
            i for i in items if i.action.startswith(f"test.audit_query.{tag}.order")
        ]
        assert len(ours) == 2
        assert ours[0].action == f"test.audit_query.{tag}.order.second"
        assert ours[1].action == f"test.audit_query.{tag}.order.first"
