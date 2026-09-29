"""T263 — every Reports endpoint rejects or hides cross-tenant IDs
**identically** to IDs that don't exist at all, so no response ever
reveals whether another tenant's company, customer or saved view exists.

Endpoints covered: discovery, ``{report_key}``, ``{report_key}/export``,
``dashboard``, ``customer-360/{id}``, and every ``saved-views*`` route.
Tenant B holds real data (invoices, a customer, a saved view); tenant A's
own reports never include it.
"""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from modules.users_roles.constants import REPORTS_PERMISSIONS
from tests.integration.api.v1.reports.conftest import (
    create_sales_customer,
    parse_csv,
    seed_sales_invoice,
)
from tests.security.reports.phase10_support import TenantHarness

_ALL_CODES = {p.code for p in REPORTS_PERMISSIONS}

_COMPANY_SCOPED_PATHS = (
    "/discovery",
    "/sales.summary",
    "/sales.summary/export?format=csv",
    "/dashboard",
    "/saved-views",
)


def _body(resp_json: dict[str, object]) -> object:
    """The response minus per-request metadata, for identity comparison."""
    error = resp_json.get("error")
    if isinstance(error, dict):
        details = dict(error.get("details") or {})
        details.pop("view_id", None)  # echoes the probed id back
        return {"code": error.get("code"), "details": details}
    return resp_json


def _pair(
    tenant: TenantHarness, other: str, missing: str
) -> tuple[tuple[int, object], tuple[int, object]]:
    a = tenant.client.get(tenant.url(other), headers=tenant.headers)
    b = tenant.client.get(tenant.url(missing), headers=tenant.headers)
    return (a.status_code, _body(a.json())), (b.status_code, _body(b.json()))


def _setup(
    db: Session, client: TestClient
) -> tuple[TenantHarness, TenantHarness, uuid.UUID, str]:
    tenant_a = TenantHarness(db, client)
    tenant_a.set_permissions(_ALL_CODES)
    tenant_b = TenantHarness(db, client)
    tenant_b.set_permissions(_ALL_CODES)

    customer_b = create_sales_customer(db, tenant_b.company_id)
    for amount in ("500.00", "700.00"):
        seed_sales_invoice(
            db, tenant_b.company_id, amount=amount, customer_id=customer_b.id
        )
    created = client.post(
        tenant_b.url("/saved-views"),
        json={"report_key": "sales.summary", "name": "B's view", "filter_config": {}},
        headers=tenant_b.headers,
    )
    assert created.status_code == 201, created.text
    return tenant_a, tenant_b, customer_b.id, str(created.json()["data"]["id"])


def test_company_scoped_paths_reject_other_tenant_like_a_missing_company(
    test_client: TestClient, db_session: Session
) -> None:
    tenant_a, tenant_b, _customer_b, _view_b = _setup(db_session, test_client)
    missing_company = uuid.uuid4()
    for path in _COMPANY_SCOPED_PATHS:
        other = test_client.get(
            tenant_a.url(path, tenant_b.company_id), headers=tenant_a.headers
        )
        missing = test_client.get(
            tenant_a.url(path, missing_company), headers=tenant_a.headers
        )
        assert other.status_code in (403, 404), f"{path}: {other.status_code}"
        assert other.status_code == missing.status_code, path
        assert _body(other.json()) == _body(missing.json()), path


def test_customer_360_cross_tenant_id_is_identical_to_nonexistent(
    test_client: TestClient, db_session: Session
) -> None:
    tenant_a, _tenant_b, customer_b, _view_b = _setup(db_session, test_client)
    other, missing = _pair(
        tenant_a, f"/customer-360/{customer_b}", f"/customer-360/{uuid.uuid4()}"
    )
    assert other[0] == 404
    assert other == missing


def test_saved_view_routes_cross_tenant_id_is_identical_to_nonexistent(
    test_client: TestClient, db_session: Session
) -> None:
    tenant_a, _tenant_b, _customer_b, view_b = _setup(db_session, test_client)
    missing_view = str(uuid.uuid4())

    other, missing = _pair(
        tenant_a, f"/saved-views/{view_b}", f"/saved-views/{missing_view}"
    )
    assert other[0] == 404 and other == missing

    for method in ("patch", "delete"):
        kwargs: dict[str, object] = {"headers": tenant_a.headers}
        if method == "patch":
            kwargs["json"] = {"name": "hijack"}
        a = getattr(test_client, method)(
            tenant_a.url(f"/saved-views/{view_b}"), **kwargs
        )
        b = getattr(test_client, method)(
            tenant_a.url(f"/saved-views/{missing_view}"), **kwargs
        )
        assert a.status_code == b.status_code == 404, method
        assert _body(a.json()) == _body(b.json()), method

    listed = test_client.get(tenant_a.url("/saved-views"), headers=tenant_a.headers)
    assert listed.status_code == 200
    assert view_b not in {v["id"] for v in listed.json()["data"]["items"]}


def test_reports_exports_and_dashboard_never_include_other_tenant_data(
    test_client: TestClient, db_session: Session
) -> None:
    tenant_a, _tenant_b, customer_b, _view_b = _setup(db_session, test_client)

    online = test_client.get(
        tenant_a.url("/sales.by_customer"), headers=tenant_a.headers
    )
    assert online.status_code == 200
    assert online.json()["data"]["total"] == 0

    exported = test_client.get(
        tenant_a.url("/sales.by_customer/export?format=csv"), headers=tenant_a.headers
    )
    assert exported.status_code == 200
    rows = parse_csv(exported.content)
    assert len(rows) == 1  # headers only
    assert str(customer_b) not in exported.text

    dashboard = test_client.get(tenant_a.url("/dashboard"), headers=tenant_a.headers)
    assert dashboard.status_code == 200
    assert dashboard.json()["data"]["net_sales"]["value"] in ("0", "0.00", "0.000000")

    # A cannot filter its way into B's data either.
    filtered = test_client.get(
        tenant_a.url(f"/sales.summary?filters[customer_id]={customer_b}"),
        headers=tenant_a.headers,
    )
    assert filtered.status_code == 200
    assert filtered.json()["data"]["total"] == 0
