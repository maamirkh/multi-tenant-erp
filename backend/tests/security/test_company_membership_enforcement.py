"""Regression tests for cross-tenant company-membership enforcement.

Context: the accounting, sales, purchase, and inventory routers are mounted
under ``/companies/{company_id}/<module>`` but historically trusted the
``company_id`` path parameter with no check that the authenticated caller is
actually a member of that company. Any authenticated user could read (or
act on) any other company's data just by supplying its real ``company_id``.

Fixed by wiring ``get_current_company_member`` (already used correctly by
the Epic 4 members/roles/ownership routers) as a router-level dependency on
the accounting/sales/purchase/inventory ``include_router(...)`` calls in
``api/v1/router.py``, so every route under those prefixes is gated.

These tests exercise the real HTTP path (not just repository-level
``company_id`` filtering, which was already correct and is what the
existing per-module ``test_tenant_isolation.py`` suites cover) to prove an
outsider with zero membership is rejected, while the legitimate owner is
unaffected.
"""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.fixtures.auth_fixtures import create_test_user

_PASSWORD = "TestPassword@1234"


def _login(client: TestClient, email: str) -> str:
    resp = client.post(
        "/api/v1/auth/login", json={"email": email, "password": _PASSWORD}
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def membership_scenario(
    test_client: TestClient, db_session: Session
) -> tuple[TestClient, str, str, str]:
    """Returns (client, company_id, owner_token, outsider_token).

    ``company_id`` is a real company (via POST /companies) owned by the
    first user. The second user has no membership in it whatsoever.
    """
    suffix = uuid.uuid4().hex[:8]
    owner_email = f"membership-owner-{suffix}@example.com"
    outsider_email = f"membership-outsider-{suffix}@example.com"
    create_test_user(db_session, email=owner_email, password=_PASSWORD)
    create_test_user(db_session, email=outsider_email, password=_PASSWORD)
    owner_token = _login(test_client, owner_email)
    outsider_token = _login(test_client, outsider_email)

    resp = test_client.post(
        "/api/v1/companies",
        json={
            "legal_name": f"Membership Enforcement Test Co {suffix}",
            "email": f"contact-{suffix}@membership-test.example.com",
        },
        headers=_auth(owner_token),
    )
    assert resp.status_code == 201, resp.text
    company_id = resp.json()["data"]["id"]

    return test_client, company_id, owner_token, outsider_token


class TestCrossTenantMembershipEnforcement:
    """An authenticated user with no membership in a company must be
    rejected (403) on every company-scoped module, while the owner keeps
    normal access."""

    @pytest.mark.parametrize("module", ["accounting", "sales", "purchase", "inventory"])
    def test_outsider_blocked_owner_allowed(
        self,
        membership_scenario: tuple[TestClient, str, str, str],
        module: str,
    ) -> None:
        client, company_id, owner_token, outsider_token = membership_scenario
        url = f"/api/v1/companies/{company_id}/{module}/feature-flags"

        outsider_resp = client.get(url, headers=_auth(outsider_token))
        assert outsider_resp.status_code == 403

        owner_resp = client.get(url, headers=_auth(owner_token))
        assert owner_resp.status_code == 200

    def test_unauthenticated_request_rejected_before_membership_check(
        self, membership_scenario: tuple[TestClient, str, str, str]
    ) -> None:
        client, company_id, _owner_token, _outsider_token = membership_scenario

        resp = client.get(f"/api/v1/companies/{company_id}/accounting/feature-flags")
        assert resp.status_code == 401
