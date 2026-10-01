"""T264 (Scenario K) — Platform Admin governs the ``reports`` entitlement
but can never read tenant report data: not a report, an export, the
dashboard, Customer 360, or a tenant's saved views — even holding every
platform permission ("entitlement governance != data access").

Static half: ``modules/platform_admin/`` imports nothing from
``modules/reports/`` except Reports' own module-toggle (the sanctioned
T006 governance hook in the Expected File Map — the identical exception
the Installments precedent, T200, documents for ``module_enablement.py``).
"""

from __future__ import annotations

import inspect
import pkgutil
from importlib import import_module
from typing import cast

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

import modules.platform_admin as platform_admin_pkg
from modules.users_roles.constants import REPORTS_PERMISSIONS
from tests.integration.api.v1.reports.conftest import create_sales_customer
from tests.security.reports.phase10_support import (
    APPROVED_REPORTS_GOVERNANCE_IMPORTS,
    TenantHarness,
    make_platform_admin_token,
    reports_imports,
    tenant_report_paths,
)


def _tenant_with_data(
    db: Session, client: TestClient
) -> tuple[TenantHarness, tuple[str, ...]]:
    tenant = TenantHarness(db, client)
    tenant.set_permissions({p.code for p in REPORTS_PERMISSIONS})
    customer = create_sales_customer(db, tenant.company_id)
    view = client.post(
        tenant.url("/saved-views"),
        json={
            "report_key": "sales.summary",
            "name": "Tenant view",
            "filter_config": {},
        },
        headers=tenant.headers,
    )
    assert view.status_code == 201, view.text
    return tenant, tenant_report_paths(customer.id, view.json()["data"]["id"])


def test_platform_admin_token_cannot_read_any_tenant_report_surface(
    test_client: TestClient, db_session: Session
) -> None:
    tenant, paths = _tenant_with_data(db_session, test_client)
    platform = {"Authorization": f"Bearer {make_platform_admin_token(db_session)}"}
    for path in paths:
        resp = test_client.get(tenant.url(path), headers=platform)
        assert resp.status_code in (401, 403), f"{path}: {resp.status_code}"
        assert "data" not in resp.json(), path


def test_platform_admin_can_govern_reports_entitlement_with_governance_only_shape(
    test_client: TestClient, db_session: Session
) -> None:
    tenant, _paths = _tenant_with_data(db_session, test_client)
    token = make_platform_admin_token(db_session, {"platform.entitlements.override"})
    resp = test_client.post(
        f"/api/v1/platform/tenants/{tenant.company_id}/entitlement-overrides",
        json={"capability_key": "reports", "reason": "T264 governance check"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()["data"]
    assert data["capability_key"] == "reports"
    report_markers = (
        "report",
        "revenue",
        "invoice",
        "customer",
        "saved_view",
        "filter",
    )
    for key in data:
        if key == "capability_key":
            continue
        assert not any(m in key.lower() for m in report_markers), key


def test_no_platform_route_reaches_report_data(test_client: TestClient) -> None:
    spec = cast(FastAPI, test_client.app).openapi()
    platform_report_paths = {
        p
        for p in spec["paths"]
        if p.startswith("/api/v1/platform") and "report" in p.lower()
    }
    assert platform_report_paths == set()


def test_platform_admin_package_imports_only_reports_governance_hook() -> None:
    violations: dict[str, list[str]] = {}
    for info in pkgutil.walk_packages(
        platform_admin_pkg.__path__, prefix="modules.platform_admin."
    ):
        module = import_module(info.name)
        try:
            source = inspect.getsource(module)
        except (OSError, TypeError):
            continue
        bad = [
            m
            for m in reports_imports(source)
            if m not in APPROVED_REPORTS_GOVERNANCE_IMPORTS
        ]
        if bad:
            violations[info.name] = bad
    assert violations == {}
