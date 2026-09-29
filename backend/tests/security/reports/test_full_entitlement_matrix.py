"""T261 — full entitlement matrix, direct API calls only.

For each of the 7 report families (Sales, Purchase, Inventory,
Accounting, CRM, Installments, Executive):

    {reports on/off} × {domain on/off} × {domain .view present/absent}
                     × {domain .export present/absent}

every cell asserts the exact outcome of both the online route
(``GET /reports/{key}``) and the export route
(``GET /reports/{key}/export``). The gate order under test is the
production one: ``reports`` mount (Plan ceiling + toggle) → registry →
domain entitlement → RBAC permission.

Domain on/off uses the platform's real Plan capability ceiling (see
``phase10_support``). Installments "off" has no existing contracts, so it
is Case A (Case B is covered by T142/T259 and
``postgres/test_discovery_installments_case_b.py``).
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.integration.api.v1.reports.conftest import configure_accounting_minimal
from tests.security.reports.phase10_support import TenantHarness


@dataclass(frozen=True)
class Family:
    name: str
    capability: str
    view_permission: str
    export_permission: str | None  # None → the family has no export at all
    view_path: str
    export_path: str


FAMILIES = (
    Family(
        "sales",
        "sales",
        "reports.sales.view",
        "reports.sales.export",
        "/sales.summary",
        "/sales.summary/export?format=csv",
    ),
    Family(
        "purchase",
        "purchase",
        "reports.purchase.view",
        "reports.purchase.export",
        "/purchase.summary",
        "/purchase.summary/export?format=csv",
    ),
    Family(
        "inventory",
        "inventory",
        "reports.inventory.view",
        "reports.inventory.export",
        "/inventory.stock_position",
        "/inventory.stock_position/export?format=csv",
    ),
    Family(
        "accounting",
        "accounting",
        "reports.accounting.view",
        "reports.accounting.export",
        "/accounting.ar_aging?filters[as_of_date]=2026-01-31",
        "/accounting.ar_aging/export?format=csv&filters[as_of_date]=2026-01-31",
    ),
    Family(
        "crm",
        "crm",
        "reports.crm.view",
        None,
        "/crm.pipeline",
        "/crm.pipeline/export?format=csv",
    ),
    Family(
        "installments",
        "installments",
        "reports.installments.view",
        "reports.installments.export",
        "/installments.register",
        "/installments.register/export?format=csv",
    ),
)

CELLS = list(
    itertools.product([True, False], repeat=4)
)  # reports, domain, view, export


def _expected_view(
    family: Family, reports: bool, domain: bool, view: bool
) -> tuple[int, str | None]:
    if not reports:
        return 403, None  # rejected at the router mount, before Reports code runs
    if not domain:
        return 403, "REPORT_NOT_ENTITLED"
    if not view:
        return 403, "REPORT_PERMISSION_DENIED"
    return 200, None


def _expected_export(
    family: Family, reports: bool, domain: bool, export: bool
) -> tuple[int, str | None]:
    if not reports:
        return 403, None
    if family.export_permission is None:
        # No export permission exists for this family: denied before any
        # entitlement lookup, in every cell.
        return 403, "REPORT_PERMISSION_DENIED"
    if not domain:
        return 403, "REPORT_NOT_ENTITLED"
    if not export:
        return 403, "REPORT_PERMISSION_DENIED"
    return 200, None


def _assert_outcome(
    actual: tuple[int, str | None], expected: tuple[int, str | None], label: str
) -> None:
    status, code = actual
    assert status == expected[0], f"{label}: status {status} != {expected[0]} ({code})"
    if expected[1] is not None:
        assert code == expected[1], f"{label}: code {code} != {expected[1]}"


@pytest.mark.parametrize("family", FAMILIES, ids=lambda f: f.name)
def test_domain_family_matrix(
    family: Family, test_client: TestClient, db_session: Session
) -> None:
    tenant = TenantHarness(db_session, test_client)
    if family.name == "accounting":
        configure_accounting_minimal(db_session, tenant.company_id)

    for reports, domain, view, export in CELLS:
        tenant.set_capabilities(**{"reports": reports, family.capability: domain})
        codes = set()
        if view:
            codes.add(family.view_permission)
        if export and family.export_permission is not None:
            codes.add(family.export_permission)
        tenant.set_permissions(codes)
        label = f"{family.name} reports={reports} domain={domain} view={view} export={export}"

        _assert_outcome(
            tenant.get(family.view_path),
            _expected_view(family, reports, domain, view),
            f"{label} [view]",
        )
        _assert_outcome(
            tenant.get(family.export_path),
            _expected_export(family, reports, domain, export),
            f"{label} [export]",
        )


def test_executive_family_matrix(test_client: TestClient, db_session: Session) -> None:
    """The 7th family. The dashboard composes several domains, so "domain
    off" means a source domain (Sales) is off: the dashboard still renders
    and that widget is OMITTED — it never fails the page. Executive has no
    export: its key is COMPOSITE and unreachable through the generic
    export route (identical 404 to an unknown key)."""
    tenant = TenantHarness(db_session, test_client)
    for reports, domain, view, export in CELLS:
        tenant.set_capabilities(reports=reports, sales=domain)
        # Each widget also needs its own domain's .view (compound
        # authorization, T148) — granted so the widget reflects only the
        # domain entitlement axis under test.
        codes = {"reports.executive.view", "reports.sales.view"} if view else set()
        if export:
            codes.add(
                "reports.sales.export"
            )  # an unrelated export grant changes nothing
        tenant.set_permissions(codes)
        label = (
            f"executive reports={reports} sales={domain} view={view} export={export}"
        )

        resp = test_client.get(tenant.url("/dashboard"), headers=tenant.headers)
        if not reports:
            assert resp.status_code == 403, label
        elif not view:
            assert resp.status_code == 403, label
            assert resp.json()["error"]["code"] == "REPORT_PERMISSION_DENIED", label
        else:
            assert resp.status_code == 200, f"{label}: {resp.text}"
            state = resp.json()["data"]["net_sales"]["state"]
            assert state == ("present" if domain else "omitted"), label

        status, code = tenant.get("/exec.dashboard/export?format=csv")
        if reports:
            assert (status, code) == (404, "REPORT_NOT_FOUND"), label
        else:
            assert status == 403, label

    # Compound authorization: the dashboard permission alone never
    # exposes a domain figure the user can't view directly.
    tenant.set_capabilities()
    tenant.set_permissions({"reports.executive.view"})
    resp = test_client.get(tenant.url("/dashboard"), headers=tenant.headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["net_sales"]["state"] == "omitted"
