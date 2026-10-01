"""T262 — every one of the 16 ``reports.*`` permission codes, granted
**alone**, unlocks exactly its own action(s) and nothing else: zero
implicit grants (FR-RPT-240..242), ``.view`` never implies ``.export`` or
vice versa, and no code implies another domain's.

Every domain is fully entitled here, so a denial can only come from RBAC.
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from modules.users_roles.constants import REPORTS_PERMISSIONS
from tests.integration.api.v1.reports.conftest import (
    configure_accounting_minimal,
    create_sales_customer,
)
from tests.security.reports.phase10_support import TenantHarness

_AS_OF = "filters[as_of_date]=2026-01-31"


def _probes(customer_id: str) -> dict[str, str]:
    """Action name → GET path. One probe per gateable action."""
    return {
        "executive.view": "/dashboard",
        "sales.view": "/sales.summary",
        "sales.export": "/sales.summary/export?format=csv",
        "purchase.view": "/purchase.summary",
        "purchase.export": "/purchase.summary/export?format=csv",
        "inventory.view": "/inventory.stock_position",
        "inventory.export": "/inventory.stock_position/export?format=csv",
        "accounting.view": f"/accounting.ar_aging?{_AS_OF}",
        "accounting.export": f"/accounting.ar_aging/export?format=csv&{_AS_OF}",
        "crm.view": "/crm.pipeline",
        "installments.view": "/installments.register",
        "installments.export": "/installments.register/export?format=csv",
        "customer_360.view": f"/customer-360/{customer_id}",
        "saved_view.manage": "/saved-views",
    }


# What each code is expected to unlock — nothing more, nothing less.
EXPECTED: dict[str, set[str]] = {
    "reports.executive.view": {"executive.view"},
    "reports.sales.view": {"sales.view"},
    "reports.sales.export": {"sales.export"},
    "reports.purchase.view": {"purchase.view"},
    "reports.purchase.export": {"purchase.export"},
    "reports.inventory.view": {"inventory.view"},
    "reports.inventory.export": {"inventory.export"},
    "reports.accounting.view": {"accounting.view"},
    "reports.accounting.export": {"accounting.export"},
    "reports.crm.view": {"crm.view"},
    # No CRM report exports (registry export_permission is None), so this
    # code exists in the catalog but unlocks nothing.
    "reports.crm.export": set(),
    "reports.installments.view": {"installments.view"},
    "reports.installments.export": {"installments.export"},
    "reports.customer_360.view": {"customer_360.view"},
    # Gates only the DEFERRED branch_performance report — unreachable.
    "reports.branch_performance.view": set(),
    "reports.saved_view.manage": {"saved_view.manage"},
}


def test_expected_table_covers_exactly_the_16_seeded_codes() -> None:
    assert set(EXPECTED) == {p.code for p in REPORTS_PERMISSIONS}
    assert len(EXPECTED) == 16


def test_each_code_alone_unlocks_exactly_its_own_actions(
    test_client: TestClient, db_session: Session
) -> None:
    tenant = TenantHarness(db_session, test_client)
    configure_accounting_minimal(db_session, tenant.company_id)
    probes = _probes(str(create_sales_customer(db_session, tenant.company_id).id))

    for code, expected in EXPECTED.items():
        tenant.set_permissions({code})
        unlocked: set[str] = set()
        for action, path in probes.items():
            status, error = tenant.get(path)
            if status == 200:
                unlocked.add(action)
            else:
                # Every denial here is RBAC — domains are all entitled.
                assert (status, error) == (403, "REPORT_PERMISSION_DENIED"), (
                    f"{code} → {action}: unexpected {status} {error}"
                )
        assert unlocked == expected, f"{code} unlocked {sorted(unlocked)}"


def test_no_permission_unlocks_nothing(
    test_client: TestClient, db_session: Session
) -> None:
    tenant = TenantHarness(db_session, test_client)
    configure_accounting_minimal(db_session, tenant.company_id)
    probes = _probes(str(create_sales_customer(db_session, tenant.company_id).id))
    tenant.set_permissions(set())
    for action, path in probes.items():
        assert tenant.get(path) == (403, "REPORT_PERMISSION_DENIED"), action
    # Discovery degrades to an empty catalog rather than an error.
    resp = test_client.get(tenant.url("/discovery"), headers=tenant.headers)
    assert resp.status_code == 200
    assert resp.json()["data"]["reports"] == []


def test_discovery_lists_only_the_granted_domain(
    test_client: TestClient, db_session: Session
) -> None:
    tenant = TenantHarness(db_session, test_client)
    tenant.set_permissions({"reports.purchase.view"})
    resp = test_client.get(tenant.url("/discovery"), headers=tenant.headers)
    assert resp.status_code == 200
    domains = {r["domain"] for r in resp.json()["data"]["reports"]}
    assert domains == {"purchase"}
