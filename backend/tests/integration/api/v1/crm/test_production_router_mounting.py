"""Production router-mounting smoke test (T079).

Every other CRM API test file uses the test-only ``crm_client`` fixture
(``tests/integration/api/v1/crm/conftest.py``), which manually mounts
``crm_router`` to exercise the Router -> Service -> Repository stack
before T079 landed. This file instead uses the SHARED ``test_client``
fixture (``tests/conftest.py``), which builds its app via the real
``main.create_app()`` -> ``api/v1/router.py`` -> ``crm_router`` chain —
proving the actual production mounting (T079) works end-to-end: the CRM
API is live under ``/api/v1/companies/{company_id}/crm/...``, gated by
BOTH ``get_current_company_member`` (tenant membership) AND
``require_crm_enabled`` (feature flag), exactly as configured in
``api/v1/router.py``.

Task: T079 (tasks.md Phase 9) — "Tests: covered by every prior API test
file, re-run once against the fully-mounted router."
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from modules.crm.repositories.feature_flag_repository import CrmFeatureFlagRepository
from modules.crm.services.feature_flag_service import CrmFeatureFlagService
from tests.integration.api.v1.crm.conftest import (
    auth_header,
    create_company,
    new_user_and_token,
)


def _enable_crm(db_session: Session, company_id: str) -> None:
    from uuid import UUID

    service = CrmFeatureFlagService(
        db=db_session, flag_repo=CrmFeatureFlagRepository(db_session)
    )
    service.enable(UUID(company_id))


class TestProductionRouterMounting:
    def test_crm_endpoint_reachable_via_production_router(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """A real CRM endpoint, hit through the production app (not the
        test-only manual-mount fixture), returns 200 once the flag is on."""
        _, token = new_user_and_token(test_client, db_session)
        company_id = create_company(test_client, token)
        _enable_crm(db_session, company_id)

        resp = test_client.get(
            f"/api/v1/companies/{company_id}/crm/leads",
            headers=auth_header(token),
        )

        assert resp.status_code == 200, resp.text

    def test_feature_flag_gate_applied_at_production_mount(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """Flag off (default) -> the documented 403, proving
        ``require_crm_enabled`` is genuinely wired at include-time in
        ``api/v1/router.py``, not merely available as an unused import."""
        _, token = new_user_and_token(test_client, db_session)
        company_id = create_company(test_client, token)

        resp = test_client.get(
            f"/api/v1/companies/{company_id}/crm/leads",
            headers=auth_header(token),
        )

        assert resp.status_code == 403, resp.text
        assert resp.json()["error"]["code"] == "FEATURE_DISABLED"

    def test_cross_tenant_membership_gate_still_applies(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """A user with no membership in the target company is rejected by
        the existing ``get_current_company_member`` gate before
        ``require_crm_enabled`` is even reached — both dependencies are
        additive to the same ``include_router()`` call (T079), neither
        replaces the other."""
        _, owner_token = new_user_and_token(test_client, db_session)
        company_id = create_company(test_client, owner_token)
        _enable_crm(db_session, company_id)

        _, outsider_token = new_user_and_token(test_client, db_session)

        resp = test_client.get(
            f"/api/v1/companies/{company_id}/crm/leads",
            headers=auth_header(outsider_token),
        )

        assert resp.status_code in (403, 404), resp.text
