"""Shared fixtures/helpers for CRM API integration tests.

**Phase 9 update (T079 landed)**: ``crm_router`` is now mounted into the
real ``api/v1/router.py``, gated by BOTH ``get_current_company_member``
AND ``require_crm_enabled`` at include-time. ``create_app()`` (called
below) therefore already registers every CRM route through that
production path — this fixture's own ``app.include_router(crm_router,
...)`` call at the same prefix is now a harmless no-op shadow (Starlette
matches the first-registered route for a given path, which is always the
production one built inside ``create_app()``).

Kept anyway, unchanged, rather than deleted: removing it would be a
same-session no-op behaviorally, and every earlier-phase test file already
imports this fixture by name — deleting the (now-redundant) manual mount
line is not necessary to fix the actual regression below, so it is left
as an inert historical artifact rather than churned for its own sake.

**The actual fix**: every test file built against this fixture across
Phases 3-8 (dozens of already-passing tests) was written when CRM was NOT
gated by ``feature.crm.enabled`` at all via this client — none of them
call the flag-enable endpoint before exercising a CRM route. Once T079's
production mount made ``require_crm_enabled`` real, those same requests
started failing with 403 FEATURE_DISABLED through this fixture too (both
the shadowed manual mount and the production one enforce the identical
gate). ``require_crm_enabled`` is therefore overridden to a no-op HERE,
preserving this fixture's original, long-established "flag doesn't
block" contract for every test that already depends on it — the
feature-flag gate itself is thoroughly covered by its own dedicated
fixture (``flag_gated_client`` in ``test_feature_flag_gate.py``), so
disabling it here does not remove any real coverage.

**Epic 9A Phase 9 update (T133 landed)**: the production mount also
gained ``require_capability_entitled("crm")`` ahead of
``require_crm_enabled`` (plan.md §13.1). This is a *separate* dependency
object — overriding ``require_crm_enabled`` alone does not neutralise it.
Discovered via a real-Docker/PostgreSQL full-suite regression run: every
test built on this fixture that doesn't explicitly assign a Subscription
resolves via the "no Subscription → defer to Toggle" path
(`entitlement_service.py`), and CRM's toggle defaults to *disabled* with
no override row — so every one of those requests started failing with
403 ``CAPABILITY_NOT_ENTITLED`` instead of reaching CRM's business logic
at all (~75 pre-existing tests across `test_lead_api.py`,
`test_opportunity_api.py`, `test_activity_api.py`,
`test_pipeline_api.py`, `test_customer_360_api.py`,
`test_lead_conversion_api.py`, `test_permission_enforcement.py`,
`test_reports_api.py`, `tests/security/crm/test_tenant_and_security.py`).
``crm_entitlement_gate`` (the named instance in ``api/v1/router.py``,
added for exactly this purpose) is therefore also overridden to a no-op
HERE, for the same reason and by the same mechanism as
``require_crm_enabled`` above — the Plan-ceiling/entitlement layer is not
this fixture's concern; it is covered by its own dedicated Gate D tests
(``tests/security/modules/platform_admin/test_entitlement_enforcement.py``).

Task: T032/T041 (tasks.md Phases 3-4); flag-override fix: T079 (Phase 9);
entitlement-override fix: T133 (Epic 9A Phase 9).
"""

from __future__ import annotations

from collections.abc import Generator
from unittest.mock import patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from core.config.settings import Settings
from core.database.session import get_db
from tests.fixtures.auth_fixtures import create_test_user

_TEST_ARGON2_KWARGS: dict[str, int] = {
    "ARGON2_TIME_COST": 1,
    "ARGON2_MEMORY_COST": 19456,
    "ARGON2_PARALLELISM": 1,
}


@pytest.fixture
def crm_client(db_session: Session) -> Generator[TestClient, None, None]:
    """A TestClient identical to the shared ``test_client`` fixture, with
    ``require_crm_enabled`` AND ``require_capability_entitled("crm")``
    both overridden to a no-op (see module docstring) so every CRM route
    behaves as it did before Epic 9A's production mounting — test-only,
    zero production file changes."""
    from main import create_app
    from modules.crm.dependencies import require_crm_enabled
    from modules.crm.router import router as crm_router

    def override_get_db() -> Generator[Session, None, None]:
        yield db_session

    app = create_app(
        Settings(
            DATABASE_URL="sqlite:///:memory:",
            SECRET_KEY="test-secret-key-minimum-32-chars-ok",
            JWT_SECRET_KEY="test-jwt-secret-key-min-32-chars-ok!",
            ENVIRONMENT="testing",
            DEBUG=True,
            JWT_ACCESS_TOKEN_EXPIRE_MINUTES=1440,
            **_TEST_ARGON2_KWARGS,
        )
    )
    from api.v1.router import crm_entitlement_gate

    app.include_router(crm_router, prefix="/api/v1/companies/{company_id}/crm")
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[require_crm_enabled] = lambda: None
    app.dependency_overrides[crm_entitlement_gate] = lambda: None

    with patch("main.run_migrations"):
        with TestClient(app, raise_server_exceptions=False) as client:
            yield client

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Helpers (plain functions — import explicitly, pytest does not
# auto-discover non-fixture names from conftest.py)
# ---------------------------------------------------------------------------


def unique_email() -> str:
    return f"crm-test-{uuid4().hex[:8]}@example.com"


def login(client: TestClient, email: str, password: str) -> str:
    resp = client.post(
        "/api/v1/auth/login", json={"email": email, "password": password}
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]["access_token"]


def auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def crm_url(company_id: str, path: str = "") -> str:
    return f"/api/v1/companies/{company_id}/crm{path}"


def new_user_and_token(client: TestClient, db_session: Session) -> tuple[str, str]:
    """Create a test user directly in the DB (matching the established
    ``tests/integration/api/v1/sales/test_invoice_api.py`` pattern) and log
    in via the real HTTP endpoint. Returns (user_id, access_token)."""
    email = unique_email()
    user, password = create_test_user(db_session, email)
    token = login(client, email, password)
    return str(user.id), token


def create_company(client: TestClient, token: str) -> str:
    suffix = uuid4().hex[:8]
    resp = client.post(
        "/api/v1/companies",
        json={
            "legal_name": f"CRM Test Co {suffix}",
            "email": f"contact-{suffix}@crm-test.example.com",
        },
        headers=auth_header(token),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]["id"]
