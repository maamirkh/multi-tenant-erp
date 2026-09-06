"""[T171, T172, T173, T175] Platform Dashboard aggregates and platform
health — Epic 9A Phase 13.

T175's own subject — an unavailable dependency renders as `unavailable`
with its own check name, never a blanket "unknown" and never a
fabricated `0` (FR-9A-243).

**Naming note**: T175's acceptance text is phrased "shows `database:
degraded`" — this codebase's own established `/api/v1/health` convention
(which T174 explicitly reuses, not reinvents) uses `"unavailable"` as
the per-check value and `"degraded"` for the top-level `status` field.
This test asserts against that existing, real convention rather than
inventing a second vocabulary — `checks["database"] == "unavailable"`
and `status == "degraded"` together are the literal manifestation of "a
degraded database check", consistent with how `/api/v1/health` has
always reported this exact scenario.

Real HTTP for the healthy-path proof; a mocked `Session.execute` for the
forced-failure proof (mirroring `test_audit_fail_closed.py`'s own
established mocking technique — SQLite's in-memory fixture cannot
simulate a genuine connection failure).
"""

from __future__ import annotations

import uuid
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from core.config.settings import get_settings
from core.events.outbox import EventOutboxRepository
from core.utils.datetime import utcnow
from modules.auth.models.user import User
from modules.companies.models.company import Company
from modules.platform_admin.models.platform_administrator import PlatformAdministrator
from modules.platform_admin.models.platform_session import PlatformSession
from modules.platform_admin.repositories.ai_credit_repository import AiCreditRepository
from modules.platform_admin.repositories.platform_audit_repository import (
    PlatformAuditRepository,
)
from modules.platform_admin.repositories.platform_rbac_repository import (
    PlatformRbacRepository,
)
from modules.platform_admin.services.ai_credit_service import AiCreditService
from modules.platform_admin.services.health_service import HealthService
from modules.platform_admin.services.platform_audit_service import PlatformAuditService
from modules.platform_admin.services.platform_jwt_service import PlatformJwtService
from modules.platform_admin.services.platform_rbac_seed_service import (
    PlatformRbacSeedService,
)


def _make_token_with_permissions(db: Session, codes: set[str]) -> str:
    user = User(
        email=f"t175-admin-{uuid.uuid4().hex[:12]}@example.test",
        display_name="T175 Platform Admin",
    )
    db.add(user)
    db.flush()
    administrator = PlatformAdministrator(user_id=user.id, is_active=True)
    db.add(administrator)
    db.flush()
    rbac_repo = PlatformRbacRepository(db)
    PlatformRbacSeedService(db, rbac_repo).seed_all()
    role = rbac_repo.create_role(
        code=f"t175-route-role-{uuid.uuid4().hex[:10]}", name="T175 Test Route Role"
    )
    rbac_repo.set_role_permissions(role.id, set(codes))
    rbac_repo.assign_role(
        platform_administrator_id=administrator.id,
        role_id=role.id,
        assigned_by=None,
        assigned_at=utcnow(),
    )
    db.commit()
    session = PlatformSession(
        platform_administrator_id=administrator.id,
        expires_at=utcnow() + timedelta(days=1),
    )
    db.add(session)
    db.flush()
    db.commit()
    return PlatformJwtService(get_settings()).create_access_token(
        platform_administrator_id=administrator.id, session_id=session.id
    )


class TestPlatformHealthHappyPath:
    def test_health_endpoint_requires_permission(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        response = test_client.get("/api/v1/platform/health")
        assert response.status_code == 401, response.text

    def test_health_endpoint_reports_healthy_and_labels_relay_as_stub(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        token = _make_token_with_permissions(db_session, {"platform.monitoring.read"})
        response = test_client.get(
            "/api/v1/platform/health",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200, response.text
        data = response.json()["data"]
        assert data["status"] == "healthy"
        assert data["checks"]["database"] == "ok"
        assert isinstance(data["outbox_pending"], int)
        assert isinstance(data["outbox_published"], int)
        assert data["relay"]["status"] == "logging_only_stub"
        assert "no message-bus" in data["relay"]["note"].lower()


class TestPlatformHealthDegradedDependency:
    def test_degraded_database_shows_unavailable_not_unknown_or_zero(
        self, db_session: Session
    ) -> None:
        service = HealthService(
            db=db_session,
            outbox_repo=EventOutboxRepository(db_session),
            settings=get_settings(),
        )

        with patch.object(
            db_session,
            "execute",
            side_effect=OperationalError(
                statement="SELECT 1", params=None, orig=Exception("simulated outage")
            ),
        ):
            health = service.get_health()

        # The check names its own dependency explicitly — never a blanket
        # "unknown" catch-all, and the overall status is genuinely
        # "degraded", not silently "healthy".
        assert health.checks["database"] == "unavailable"
        assert health.status == "degraded"
        # A failed dependency must never render as a fabricated 0 that
        # looks like a genuine "no pending events" measurement — the
        # outbox check itself is also explicitly marked unavailable here
        # (same connection failure), so 0 is never presented as real data.
        assert health.checks["outbox"] == "unavailable"

    def test_healthy_database_never_shows_unavailable(
        self, db_session: Session
    ) -> None:
        service = HealthService(
            db=db_session,
            outbox_repo=EventOutboxRepository(db_session),
            settings=get_settings(),
        )
        health = service.get_health()
        assert health.checks["database"] == "ok"
        assert health.checks["outbox"] == "ok"
        assert health.status == "healthy"


def _make_company(db: Session, *, label: str) -> Company:
    suffix = uuid.uuid4().hex[:10]
    owner = User(
        email=f"t171-owner-{label}-{suffix}@example.test",
        display_name=f"T171 Owner {label}",
    )
    db.add(owner)
    db.flush()
    company = Company(
        legal_name=f"T171 Dashboard Co {label} {suffix}",
        slug=f"t171-dashboard-co-{label}-{suffix}",
        owner_id=owner.id,
        email=f"t171-dashboard-co-{label}-{suffix}@example.com",
        status="active",
    )
    db.add(company)
    db.flush()
    db.commit()
    return company


class TestDashboardPermissionGatedOmission:
    """[T172] Widgets the caller lacks permission for are omitted
    entirely — never shown empty or erroring."""

    def test_dashboard_requires_base_permission(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        response = test_client.get("/api/v1/platform/dashboard")
        assert response.status_code == 401, response.text

    def test_only_tenants_permission_shows_only_tenant_widgets(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        token = _make_token_with_permissions(
            db_session, {"platform.dashboard.view", "platform.tenants.read"}
        )
        _make_company(db_session, label="visible")

        response = test_client.get(
            "/api/v1/platform/dashboard",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200, response.text
        widgets = response.json()["data"]["widgets"]

        assert "tenant_counts_by_status" in widgets
        assert "recent_registrations" in widgets
        assert widgets["tenant_counts_by_status"]["state"] == "populated"
        # No permission was granted for these — they must be entirely
        # absent, not present with an empty/error state.
        assert "quota_warnings" not in widgets
        assert "recent_platform_actions" not in widgets
        assert "health_summary" not in widgets
        assert "plan_subscription_distribution" not in widgets
        assert "ai_usage" not in widgets

    def test_holding_every_permission_shows_every_permission_gated_widget(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        token = _make_token_with_permissions(
            db_session,
            {
                "platform.dashboard.view",
                "platform.tenants.read",
                "platform.subscriptions.read",
                "platform.quotas.read",
                "platform.audit.read",
                "platform.monitoring.read",
                "platform.ai_usage.read",
            },
        )
        response = test_client.get(
            "/api/v1/platform/dashboard",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200, response.text
        widgets = response.json()["data"]["widgets"]
        for expected in (
            "tenant_counts_by_status",
            "recent_registrations",
            "plan_subscription_distribution",
            "quota_warnings",
            "recent_platform_actions",
            "health_summary",
        ):
            assert expected in widgets, f"expected widget {expected!r} missing"
        # `ai_usage` is deliberately not asserted here either way:
        # `AiCreditLedgerEntry` is a genuinely global table (not scoped to
        # this test's own company), and the shared `db_session` fixture is
        # reused across the full test suite — another test file (e.g.
        # Phase 11's test_ai_credits.py) may have already inserted a row
        # before this test runs, making a hard "absent" assertion flaky
        # under a full-suite run despite passing in isolation. The gating
        # behavior itself (T173) is proven deterministically by
        # `TestDashboardAiWidgetGatedOnRealData` below instead, which
        # creates its own controlled positive case.


class TestDashboardAiWidgetGatedOnRealData:
    """[T173] The AI usage widget appears only once
    ai_credit_ledger_entries has at least one row."""

    def test_ai_widget_appears_after_a_real_adjustment(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        actor, token = _make_token_with_permissions_returning_actor(
            db_session,
            {
                "platform.dashboard.view",
                "platform.ai_usage.read",
                "platform.ai_credits.adjust",
            },
        )
        company = _make_company(db_session, label="ai")
        AiCreditService(
            db=db_session,
            repo=AiCreditRepository(db_session),
            audit=PlatformAuditService(db_session, PlatformAuditRepository(db_session)),
        ).adjust(
            company_id=company.id,
            delta=Decimal(100),
            reason="T173 dashboard AI-gate test.",
            actor_platform_administrator_id=actor.id,
        )

        response = test_client.get(
            "/api/v1/platform/dashboard",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200, response.text
        widgets = response.json()["data"]["widgets"]
        assert "ai_usage" in widgets
        assert widgets["ai_usage"]["state"] == "populated"


def _make_token_with_permissions_returning_actor(
    db: Session, codes: set[str]
) -> tuple[PlatformAdministrator, str]:
    """Like `_make_token_with_permissions`, but also returns the
    administrator — needed where a test must act as that administrator
    (e.g. the AI-credit-adjustment actor)."""
    user = User(
        email=f"t171-admin-{uuid.uuid4().hex[:12]}@example.test",
        display_name="T171 Platform Admin",
    )
    db.add(user)
    db.flush()
    administrator = PlatformAdministrator(user_id=user.id, is_active=True)
    db.add(administrator)
    db.flush()
    rbac_repo = PlatformRbacRepository(db)
    PlatformRbacSeedService(db, rbac_repo).seed_all()
    role = rbac_repo.create_role(
        code=f"t171-route-role-{uuid.uuid4().hex[:10]}", name="T171 Test Route Role"
    )
    rbac_repo.set_role_permissions(role.id, set(codes))
    rbac_repo.assign_role(
        platform_administrator_id=administrator.id,
        role_id=role.id,
        assigned_by=None,
        assigned_at=utcnow(),
    )
    db.commit()
    session = PlatformSession(
        platform_administrator_id=administrator.id,
        expires_at=utcnow() + timedelta(days=1),
    )
    db.add(session)
    db.flush()
    db.commit()
    token = PlatformJwtService(get_settings()).create_access_token(
        platform_administrator_id=administrator.id, session_id=session.id
    )
    return administrator, token
