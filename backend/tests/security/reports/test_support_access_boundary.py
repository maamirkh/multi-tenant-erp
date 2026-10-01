"""T265 (FR-RPT-291) — an active Epic 9A ``SupportAccessGrant`` does not
extend into report data, saved views, or exports: the grant is an
inspection-only governance record, and the Platform Administrator holding
it is still rejected by every tenant Reports route. Mirrors the
Installments precedent (T199) and Epic 9A's T163.
"""

from __future__ import annotations

import inspect
import uuid

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from modules.platform_admin.models.platform_administrator import (
    PlatformAdministrator,
)
from modules.platform_admin.repositories.platform_audit_repository import (
    PlatformAuditRepository,
)
from modules.platform_admin.repositories.support_access_repository import (
    SupportAccessRepository,
)
from modules.platform_admin.services.platform_audit_service import (
    PlatformAuditService,
)
from modules.platform_admin.services.support_access_service import (
    SupportAccessService,
)
from modules.users_roles.constants import REPORTS_PERMISSIONS
from tests.integration.api.v1.reports.conftest import (
    create_sales_customer,
    seed_sales_invoice,
)
from tests.security.reports.phase10_support import (
    TenantHarness,
    make_platform_admin_token,
    reports_imports,
    tenant_report_paths,
)


def _grant(db: Session, company_id: uuid.UUID) -> None:
    from modules.auth.models.user import User

    user = User(email=f"t265-{uuid.uuid4().hex[:10]}@example.test", display_name="T265")
    db.add(user)
    db.flush()
    actor = PlatformAdministrator(user_id=user.id, is_active=True)
    db.add(actor)
    db.flush()
    db.commit()
    SupportAccessService(
        db=db,
        repo=SupportAccessRepository(db),
        audit=PlatformAuditService(db, PlatformAuditRepository(db)),
    ).initiate(
        company_id=company_id,
        reason="T265 — proving support access never reaches report data.",
        actor_platform_administrator_id=actor.id,
    )
    db.commit()


def test_active_support_grant_does_not_open_report_data(
    test_client: TestClient, db_session: Session
) -> None:
    tenant = TenantHarness(db_session, test_client)
    tenant.set_permissions({p.code for p in REPORTS_PERMISSIONS})
    customer = create_sales_customer(db_session, tenant.company_id)
    seed_sales_invoice(
        db_session, tenant.company_id, amount="999.00", customer_id=customer.id
    )
    view = test_client.post(
        tenant.url("/saved-views"),
        json={"report_key": "sales.summary", "name": "Private", "filter_config": {}},
        headers=tenant.headers,
    )
    assert view.status_code == 201
    _grant(db_session, tenant.company_id)

    platform = {"Authorization": f"Bearer {make_platform_admin_token(db_session)}"}
    for path in tenant_report_paths(customer.id, view.json()["data"]["id"]):
        resp = test_client.get(tenant.url(path), headers=platform)
        assert resp.status_code in (401, 403), f"{path}: {resp.status_code}"
        assert "999" not in resp.text, path


def test_support_access_listing_carries_no_report_data(
    test_client: TestClient, db_session: Session
) -> None:
    tenant = TenantHarness(db_session, test_client)
    _grant(db_session, tenant.company_id)
    token = make_platform_admin_token(db_session, {"platform.support_access.read"})
    resp = test_client.get(
        "/api/v1/platform/support-access", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 200, resp.text
    for grant in resp.json()["data"]["items"]:
        for key in grant:
            assert not any(
                m in key.lower() for m in ("report", "revenue", "invoice", "saved_view")
            ), key


def test_support_access_service_imports_nothing_from_reports() -> None:
    import modules.platform_admin.services.support_access_service as mod

    assert reports_imports(inspect.getsource(mod)) == []
