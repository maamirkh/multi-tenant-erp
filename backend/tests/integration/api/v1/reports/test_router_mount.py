"""T010 — Reports router-mount integration test.

``reports_router`` was intentionally empty at Phase 0 (no report-key
endpoints existed until Phase 3) — at that point, no route was registered
for any path under ``/companies/{company_id}/reports/...``, so a live
HTTP request to that prefix 404'd via FastAPI's own unmatched-route
handling regardless of tenant/entitlement state, before any dependency
(including auth) ever ran.

**Corrected post-Phase-3**: T132 added ``GET /{report_key}``, a
catch-all matching any single path segment under this prefix. An
unauthenticated request to ``.../reports/anything-not-registered`` now
*matches a real route* and is denied by FastAPI's own dependency
resolution (``require_authenticated``) with 401, before ``ReportExecutionService``
is ever reached — a stricter, more correct security default (never
confirming or denying a path's existence to an unauthenticated caller)
than the old bare 404. The *authenticated* 404-for-a-genuinely-
unregistered-key case is now covered end-to-end by
``test_error_envelope_mapping_phase3.py::test_report_not_found_404``.

The gate chain itself (``reports_entitlement_gate`` =
``require_capability_entitled("reports")``, then
``require_reports_enabled``) is proven wired by importing and invoking
the **exact same objects** ``api/v1/router.py`` mounted in T008 — not
reimplemented copies — against a real company: disabled ``reports`` ->
the documented module-not-entitled error; enabled -> both gates pass.
"""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from starlette.requests import Request

from api.v1.router import reports_entitlement_gate
from modules.auth.models.user import User
from modules.companies.models.company import Company
from modules.platform_admin.exceptions import CapabilityNotEntitledError
from modules.platform_admin.repositories.capability_repository import (
    CapabilityRepository,
)
from modules.platform_admin.services.capability_seed_service import (
    CapabilitySeedService,
)
from modules.reports.dependencies import require_reports_enabled
from modules.reports.exceptions import ReportNotEntitledError
from modules.reports.repositories.feature_flag import ReportsFeatureFlagRepository
from modules.reports.services.feature_flag_service import REPORTS_ENABLED_FLAG_KEY


def _fake_request() -> Request:
    """A minimal ``Request`` sufficient for
    ``require_capability_entitled``'s request-scoped memoisation cache
    (``request.state``) — no real ASGI connection is needed."""
    return Request(scope={"type": "http", "headers": [], "state": {}})


def _make_company(db: Session) -> Company:
    user = User(
        email=f"t010-owner-{uuid.uuid4().hex[:10]}@example.test",
        display_name="T010 Owner",
    )
    db.add(user)
    db.flush()
    company = Company(
        legal_name=f"T010 Reports Co {uuid.uuid4().hex[:6]}",
        slug=f"t010-reports-co-{uuid.uuid4().hex[:8]}",
        owner_id=user.id,
        email=f"t010-reports-co-{uuid.uuid4().hex[:8]}@example.test",
        status="active",
    )
    db.add(company)
    db.flush()
    db.commit()
    return company


class TestUnregisteredPathReturns404:
    def test_unauthenticated_request_under_reports_prefix_401s(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """Post-Phase-3: ``GET /{report_key}`` matches any single path
        segment under this prefix, so an unauthenticated request is
        denied by ``require_authenticated`` (401) before any registry
        lookup runs — proving the mount is reachable without leaking
        path-existence to an unauthenticated caller."""
        company = _make_company(db_session)

        resp = test_client.get(
            f"/api/v1/companies/{company.id}/reports/anything-not-registered"
        )

        assert resp.status_code == 401


class TestEntitlementGateChainIsWired:
    def test_disabled_reports_denies_via_capability_gate(
        self, db_session: Session
    ) -> None:
        CapabilitySeedService(
            db_session, CapabilityRepository(db_session)
        ).seed_capabilities()
        company = _make_company(db_session)

        with pytest.raises(CapabilityNotEntitledError):
            reports_entitlement_gate(
                request=_fake_request(), company_id=company.id, db=db_session
            )

    def test_enabled_reports_passes_capability_gate_then_feature_flag_gate(
        self, db_session: Session
    ) -> None:
        CapabilitySeedService(
            db_session, CapabilityRepository(db_session)
        ).seed_capabilities()
        company = _make_company(db_session)

        ReportsFeatureFlagRepository(db_session).upsert(
            company_id=company.id,
            flag_key=REPORTS_ENABLED_FLAG_KEY,
            is_enabled=True,
        )
        db_session.commit()

        reports_entitlement_gate(
            request=_fake_request(), company_id=company.id, db=db_session
        )
        require_reports_enabled(company_id=company.id, db=db_session)

    def test_disabled_feature_flag_denies_via_require_reports_enabled(
        self, db_session: Session
    ) -> None:
        company = _make_company(db_session)

        with pytest.raises(ReportNotEntitledError):
            require_reports_enabled(company_id=company.id, db=db_session)
