"""[T212] Performance: pagination and index usage on the heavy list/
aggregate Platform paths (plan.md §26, resolved OQ-4).

**No numeric SLA is asserted here** — these are regression guards
proving structural correctness (bounded pagination, real indexes,
query-count that does not scale with total data volume), never
benchmarks against a latency target. Matches this repository's existing
precedent (`tests/performance/crm/test_list_performance.py`) for the
*shape* of a performance regression guard, but deliberately omits its
p95-timing assertion per this task's own explicit acceptance text.
"""

from __future__ import annotations

import uuid

from sqlalchemy import inspect
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from modules.auth.models.user import User
from modules.companies.models.company import Company
from modules.companies.repositories.company_repository import CompanyRepository
from modules.platform_admin.models.platform_administrator import PlatformAdministrator
from modules.platform_admin.repositories.platform_audit_repository import (
    PlatformAuditRepository,
)
from modules.platform_admin.services.dashboard_service import DashboardService
from modules.platform_admin.services.health_service import HealthService
from modules.platform_admin.services.tenant_directory_service import (
    TenantDirectoryService,
)

_SAMPLE_COMPANIES = 500
_SAMPLE_AUDIT_EVENTS = 500


class _QueryCounter:
    """Counts real SQL statements issued against *engine* while active —
    the direct, precise way to catch an N+1 (a query count that scales
    with row count), rather than inferring it from timing alone."""

    def __init__(self, engine: Engine) -> None:
        self.engine = engine
        self.count = 0

    def _listener(self, *_args: object, **_kwargs: object) -> None:
        self.count += 1

    def __enter__(self) -> _QueryCounter:
        from sqlalchemy import event

        event.listen(self.engine, "before_cursor_execute", self._listener)
        return self

    def __exit__(self, *exc: object) -> None:
        from sqlalchemy import event

        event.remove(self.engine, "before_cursor_execute", self._listener)


def _seed_companies(db: Session, n: int) -> list[Company]:
    owner = User(
        email=f"t212-owner-{uuid.uuid4().hex[:10]}@example.com", display_name="Owner"
    )
    db.add(owner)
    db.flush()
    companies = [
        Company(
            legal_name=f"T212 Perf Co {i} {uuid.uuid4().hex[:6]}",
            slug=f"t212-perf-co-{i}-{uuid.uuid4().hex[:6]}",
            owner_id=owner.id,
            email=f"t212-perf-{i}-{uuid.uuid4().hex[:6]}@example.com",
            status="active",
        )
        for i in range(n)
    ]
    db.add_all(companies)
    db.commit()
    return companies


def _seed_audit_events(db: Session, actor_id: uuid.UUID, n: int) -> None:
    repo = PlatformAuditRepository(db)
    for i in range(n):
        repo.record(
            action="tenant_lifecycle.suspend" if i % 2 else "admin.deactivate",
            target_type="Company",
            actor_platform_administrator_id=actor_id,
            reason=f"perf-seed-{i}",
        )
    db.commit()


def _make_actor(db: Session) -> PlatformAdministrator:
    user = User(
        email=f"t212-actor-{uuid.uuid4().hex[:10]}@example.com", display_name="Actor"
    )
    db.add(user)
    db.flush()
    administrator = PlatformAdministrator(user_id=user.id, is_active=True)
    db.add(administrator)
    db.flush()
    db.commit()
    return administrator


class TestTenantListPaginationIsBounded:
    def test_tenant_list_returns_exactly_page_size_regardless_of_total_rows(
        self, db_session: Session
    ) -> None:
        _seed_companies(db_session, _SAMPLE_COMPANIES)

        from modules.companies.repositories.company_repository import CompanyRepository

        repo = CompanyRepository(db_session)
        items, total = repo.list_all(filters={}, page=1, page_size=20)

        assert len(items) == 20
        assert total >= _SAMPLE_COMPANIES


class TestAuditListPaginationIsBounded:
    def test_audit_list_returns_exactly_page_size_regardless_of_total_rows(
        self, db_session: Session
    ) -> None:
        actor = _make_actor(db_session)
        _seed_audit_events(db_session, actor.id, _SAMPLE_AUDIT_EVENTS)

        repo = PlatformAuditRepository(db_session)
        items, total = repo.list_filtered(limit=25, offset=0)

        assert len(items) == 25
        assert total >= _SAMPLE_AUDIT_EVENTS


class TestEpic9AIndexesExist:
    """T014's four `platform_audit_events` indexes and T018's partial
    unique override indexes — verified directly against the schema
    `Base.metadata.create_all()` builds for tests (the same `Index(...)`
    declarations the real Alembic migrations also carry), not inferred
    from query timing."""

    def test_platform_audit_events_has_its_four_declared_indexes(
        self, db_session: Session
    ) -> None:
        engine = db_session.get_bind()
        index_names = {
            ix["name"] for ix in inspect(engine).get_indexes("platform_audit_events")
        }
        expected = {
            "ix_platform_audit_events_actor_id",
            "ix_platform_audit_events_company_id",
            "ix_platform_audit_events_action",
            "ix_platform_audit_events_created_at",
        }
        assert expected.issubset(index_names)

    def test_override_tables_have_their_company_scoping_index(
        self, db_session: Session
    ) -> None:
        # The `WHERE is_active` partial unique index itself is a
        # PostgreSQL-only construct (migration 059) deliberately not
        # mirrored into the SQLAlchemy model's `__table_args__` — every
        # override model's own docstring documents this, and it was
        # already verified directly against real PostgreSQL during
        # Phase 8's closure (`\d+ entitlement_overrides` /
        # `\d+ tenant_quota_overrides`), not re-litigated here. What
        # *is* mirrored into the test schema, and checked here, is the
        # ordinary company-scoping index every override lookup relies on.
        engine = db_session.get_bind()
        for table in ("entitlement_overrides", "tenant_quota_overrides"):
            index_names = {
                ix["name"] for ix in inspect(engine).get_indexes(table) if ix["name"]
            }
            assert any("company" in name for name in index_names), (
                f"{table} is missing its company-scoping index (found: {index_names})"
            )


class TestNoNPlusOneInTenantDetailAndDashboard:
    def test_tenant_detail_query_count_does_not_scale_with_total_tenant_count(
        self, db_session: Session, test_db_engine: Engine
    ) -> None:
        from modules.platform_admin.repositories.capability_repository import (
            CapabilityRepository,
        )
        from modules.platform_admin.repositories.plan_repository import PlanRepository
        from modules.platform_admin.repositories.quota_repository import QuotaRepository
        from modules.platform_admin.repositories.subscription_repository import (
            SubscriptionRepository,
        )
        from modules.platform_admin.repositories.usage_repository import UsageRepository
        from modules.platform_admin.services.capability_seed_service import (
            CapabilitySeedService,
        )

        CapabilitySeedService(
            db_session, CapabilityRepository(db_session)
        ).seed_capabilities()

        def _build_service() -> TenantDirectoryService:
            return TenantDirectoryService(
                db=db_session,
                company_repo=CompanyRepository(db_session),
                subscription_repo=SubscriptionRepository(db_session),
                plan_repo=PlanRepository(db_session),
                quota_repo=QuotaRepository(db_session),
                usage_repo=UsageRepository(db_session),
                capability_repo=CapabilityRepository(db_session),
                audit_repo=PlatformAuditRepository(db_session),
            )

        target = _seed_companies(db_session, 5)[0]
        service = _build_service()
        with _QueryCounter(test_db_engine) as counter_small:
            service.get_tenant_detail(target.id)
        small_count = counter_small.count

        # A much larger total company population must not change the
        # query count for detailing *one* tenant.
        other_target = _seed_companies(db_session, _SAMPLE_COMPANIES)[0]
        service2 = _build_service()
        with _QueryCounter(test_db_engine) as counter_large:
            service2.get_tenant_detail(other_target.id)
        large_count = counter_large.count

        assert small_count == large_count, (
            f"get_tenant_detail() issued {small_count} queries against a small "
            f"dataset but {large_count} against a large one — query count must "
            "not scale with total tenant count (N+1 regression)."
        )

    def test_dashboard_query_count_does_not_scale_with_total_data_volume(
        self, db_session: Session, test_db_engine: Engine
    ) -> None:
        from core.config.settings import get_settings
        from core.events.outbox import EventOutboxRepository

        held_permissions = {
            "platform.tenants.read",
            "platform.subscriptions.read",
            "platform.quotas.read",
            "platform.audit.read",
            "platform.monitoring.read",
            "platform.ai_usage.read",
        }

        def _build_dashboard() -> DashboardService:
            return DashboardService(
                db=db_session,
                audit_repo=PlatformAuditRepository(db_session),
                health_service=HealthService(
                    db=db_session,
                    outbox_repo=EventOutboxRepository(db_session),
                    settings=get_settings(),
                ),
            )

        _seed_companies(db_session, 5)
        with _QueryCounter(test_db_engine) as counter_small:
            _build_dashboard().get_dashboard(held_permissions=held_permissions)
        small_count = counter_small.count

        _seed_companies(db_session, _SAMPLE_COMPANIES)
        with _QueryCounter(test_db_engine) as counter_large:
            _build_dashboard().get_dashboard(held_permissions=held_permissions)
        large_count = counter_large.count

        assert small_count == large_count, (
            f"get_dashboard() issued {small_count} queries against a small "
            f"dataset but {large_count} against a large one — every widget "
            "must be a single bounded query, never per-row iteration."
        )
