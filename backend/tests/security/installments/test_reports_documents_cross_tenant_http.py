"""[Epic 10, Phase 12 — closure fix] Real, live-ASGI cross-tenant evidence
for the Reports/Dashboard and Documents/Statements endpoint groups —
closes the HTTP-layer tenant-isolation evidence gap identified in Phase-12
closure verification (prior HTTP tests for these endpoints only proved
single-tenant happy-path/401/403/404-unknown-type; none attempted a real
cross-tenant resource or the company-id path-swap vector).

Two vectors, mirroring ``test_http_security_closure.py``'s
``TestHttpTenantIsolation`` established pattern (Phase 11):

1. IDOR: Tenant A's own ``company_id`` in the path, but a ``contractId``/
   ``customerId`` that actually belongs to Tenant B.
2. Path-swap: Tenant A's real, valid token, but Tenant B's ``company_id``
   placed directly in the URL path (rejected by
   ``get_current_company_member`` itself — no real membership row).

Every request goes through ``installments_http_client`` — a real
``main.create_app()`` instance, the real mounted router, real
authentication/RBAC/entitlement, nothing Installments-specific stubbed.

Real PostgreSQL throughout (schedule persistence requires it).
"""

from __future__ import annotations

import uuid
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from modules.auth.models.user import User
from modules.companies.models.company import Company
from modules.installments.repositories.feature_flag import (
    InstallmentsFeatureFlagRepository,
)
from modules.installments.services.feature_flag_service import (
    InstallmentsFeatureFlagService,
)
from modules.users_roles.models.company_member import CompanyMember
from modules.users_roles.models.enums import MembershipStatus
from modules.users_roles.models.permission import Permission
from modules.users_roles.models.role import Role
from modules.users_roles.models.role_permission import RolePermission
from tests.fixtures.auth_fixtures import create_test_user
from tests.integration.api.v1.installments.conftest import (
    build_active_contract_with_schedule,
)

_INSTALLMENTS_PREFIX = "/api/v1/companies/{company_id}/installments"


def _make_company(db: Session, *, company_id: uuid.UUID | None = None) -> Company:
    suffix = uuid.uuid4().hex[:10]
    owner = User(
        email=f"xt-owner-{suffix}@example.test", display_name="Cross-Tenant Owner"
    )
    db.add(owner)
    db.flush()
    company = Company(
        id=company_id or uuid.uuid4(),
        legal_name=f"Cross Tenant Co {suffix}",
        slug=f"cross-tenant-co-{suffix}",
        owner_id=owner.id,
        email=f"cross-tenant-co-{suffix}@example.com",
        status="active",
    )
    db.add(company)
    db.flush()
    db.commit()
    return company


def _login(test_client: TestClient, db: Session, *, email: str) -> str:
    password = "CrossTenant@1234"
    create_test_user(db, email=email, password=password)
    db.commit()
    response = test_client.post(
        "/api/v1/auth/login", json={"email": email, "password": password}
    )
    assert response.status_code == 200, response.text
    return str(response.json()["data"]["access_token"])


def _ensure_permission(db: Session, code: str) -> None:
    if db.get(Permission, code) is not None:
        return
    db.add(
        Permission(
            id=code, code=code, label=code, module="installments", action="manage"
        )
    )
    db.flush()


def _grant_membership_with_permissions(
    db: Session, *, company_id: uuid.UUID, user_id: uuid.UUID, codes: set[str]
) -> None:
    for code in codes:
        _ensure_permission(db, code)
    role = Role(
        company_id=company_id,
        name=f"Cross Tenant Role {uuid.uuid4().hex[:8]}",
        slug=f"cross-tenant-role-{uuid.uuid4().hex[:10]}",
        rank=50,
        is_system=False,
        is_active=True,
    )
    db.add(role)
    db.flush()
    for code in codes:
        db.add(RolePermission(role_id=role.id, permission_id=code))
    db.flush()
    db.add(
        CompanyMember(
            company_id=company_id,
            user_id=user_id,
            role_id=role.id,
            status=MembershipStatus.active.value,
        )
    )
    db.commit()


def _enable_installments(db: Session, company_id: uuid.UUID) -> None:
    InstallmentsFeatureFlagService(
        flag_repo=InstallmentsFeatureFlagRepository(db)
    ).enable(company_id)
    db.commit()


def _auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _setup_tenant_a(
    pg_db_session: Session,
    installments_http_client: TestClient,
    *,
    codes: set[str],
) -> tuple[Company, str]:
    company_a = _make_company(pg_db_session)
    email = f"xt-a-{uuid.uuid4().hex[:10]}@example.com"
    token = _login(installments_http_client, pg_db_session, email=email)
    user_row = pg_db_session.query(User).filter_by(email=email).one()
    _grant_membership_with_permissions(
        pg_db_session, company_id=company_a.id, user_id=user_row.id, codes=codes
    )
    _enable_installments(pg_db_session, company_a.id)
    return company_a, token


class TestReportsDashboardCrossTenantHttp:
    def test_reports_idor_own_company_wrong_report_target_is_scoped(
        self, installments_http_client: TestClient, pg_db_session: Session
    ) -> None:
        """Reports have no per-resource ID (they're company-scoped list
        endpoints) — the IDOR-equivalent proof here is that Tenant A's
        own report, requested through Tenant A's own company_id, never
        contains a Tenant B contract even though Tenant B was seeded
        first (same shape as the aggregate-isolation service tests, now
        proven at the HTTP layer)."""
        ctx_b = build_active_contract_with_schedule(
            pg_db_session, installment_count=1, installment_amount=Decimal("500.00")
        )
        _make_company(pg_db_session, company_id=ctx_b["company_id"])
        ctx_a = build_active_contract_with_schedule(
            pg_db_session, installment_count=1, installment_amount=Decimal("100.00")
        )
        company_a = _make_company(pg_db_session, company_id=ctx_a["company_id"])
        email = f"xt-reports-{uuid.uuid4().hex[:10]}@example.com"
        token = _login(installments_http_client, pg_db_session, email=email)
        user_row = pg_db_session.query(User).filter_by(email=email).one()
        _grant_membership_with_permissions(
            pg_db_session,
            company_id=company_a.id,
            user_id=user_row.id,
            codes={"installments.report.view"},
        )
        _enable_installments(pg_db_session, company_a.id)

        response = installments_http_client.get(
            _INSTALLMENTS_PREFIX.format(company_id=company_a.id)
            + "/reports/contract-register",
            headers=_auth_header(token),
        )
        assert response.status_code == 200, response.text
        body = response.json()["data"]
        assert body["total"] == 1
        assert body["items"][0]["contract_id"] == str(ctx_a["contract"].id)

    def test_reports_company_id_path_swap_is_rejected(
        self, installments_http_client: TestClient, pg_db_session: Session
    ) -> None:
        company_a, token = _setup_tenant_a(
            pg_db_session,
            installments_http_client,
            codes={"installments.report.view"},
        )
        company_b = _make_company(pg_db_session)

        response = installments_http_client.get(
            _INSTALLMENTS_PREFIX.format(company_id=company_b.id)
            + "/reports/contract-register",
            headers=_auth_header(token),
        )
        assert response.status_code == 403, response.text

    def test_dashboard_company_id_path_swap_is_rejected(
        self, installments_http_client: TestClient, pg_db_session: Session
    ) -> None:
        company_a, token = _setup_tenant_a(
            pg_db_session,
            installments_http_client,
            codes={"installments.report.view"},
        )
        company_b = _make_company(pg_db_session)

        response = installments_http_client.get(
            _INSTALLMENTS_PREFIX.format(company_id=company_b.id) + "/dashboard",
            headers=_auth_header(token),
        )
        assert response.status_code == 403, response.text


class TestDocumentsCrossTenantHttp:
    def test_agreement_idor_tenant_b_contract_via_tenant_a_company_is_not_found(
        self, installments_http_client: TestClient, pg_db_session: Session
    ) -> None:
        ctx_b = build_active_contract_with_schedule(
            pg_db_session, installment_count=1, installment_amount=Decimal("100.00")
        )
        _make_company(pg_db_session, company_id=ctx_b["company_id"])
        company_a, token = _setup_tenant_a(
            pg_db_session,
            installments_http_client,
            codes={"installments.contract.view"},
        )

        response = installments_http_client.get(
            _INSTALLMENTS_PREFIX.format(company_id=company_a.id)
            + f"/contracts/{ctx_b['contract'].id}/documents/agreement",
            headers=_auth_header(token),
        )
        assert response.status_code == 404, response.text

    def test_schedule_document_idor_tenant_b_contract_is_not_found(
        self, installments_http_client: TestClient, pg_db_session: Session
    ) -> None:
        ctx_b = build_active_contract_with_schedule(
            pg_db_session, installment_count=2, installment_amount=Decimal("100.00")
        )
        _make_company(pg_db_session, company_id=ctx_b["company_id"])
        company_a, token = _setup_tenant_a(
            pg_db_session,
            installments_http_client,
            codes={"installments.contract.view"},
        )

        response = installments_http_client.get(
            _INSTALLMENTS_PREFIX.format(company_id=company_a.id)
            + f"/contracts/{ctx_b['contract'].id}/documents/schedule",
            headers=_auth_header(token),
        )
        assert response.status_code == 404, response.text

    def test_agreement_company_id_path_swap_is_rejected(
        self, installments_http_client: TestClient, pg_db_session: Session
    ) -> None:
        ctx_b = build_active_contract_with_schedule(
            pg_db_session, installment_count=1, installment_amount=Decimal("100.00")
        )
        company_b = _make_company(pg_db_session, company_id=ctx_b["company_id"])
        _company_a, token = _setup_tenant_a(
            pg_db_session,
            installments_http_client,
            codes={"installments.contract.view"},
        )

        response = installments_http_client.get(
            _INSTALLMENTS_PREFIX.format(company_id=company_b.id)
            + f"/contracts/{ctx_b['contract'].id}/documents/agreement",
            headers=_auth_header(token),
        )
        assert response.status_code == 403, response.text

    def test_customer_statement_for_tenant_b_customer_via_tenant_a_is_empty(
        self, installments_http_client: TestClient, pg_db_session: Session
    ) -> None:
        """Not a 404 case (a customer_id is not itself a protected
        resource) — the correct, safe behavior is an empty statement,
        never Tenant B's contracts."""
        ctx_b = build_active_contract_with_schedule(
            pg_db_session, installment_count=1, installment_amount=Decimal("100.00")
        )
        _make_company(pg_db_session, company_id=ctx_b["company_id"])
        company_a, token = _setup_tenant_a(
            pg_db_session,
            installments_http_client,
            codes={"installments.contract.view"},
        )

        response = installments_http_client.get(
            _INSTALLMENTS_PREFIX.format(company_id=company_a.id)
            + f"/customers/{ctx_b['customer_id']}/statement",
            headers=_auth_header(token),
        )
        assert response.status_code == 200, response.text
        assert response.json()["data"]["contracts"] == []

    def test_customer_statement_company_id_path_swap_is_rejected(
        self, installments_http_client: TestClient, pg_db_session: Session
    ) -> None:
        ctx_b = build_active_contract_with_schedule(
            pg_db_session, installment_count=1, installment_amount=Decimal("100.00")
        )
        company_b = _make_company(pg_db_session, company_id=ctx_b["company_id"])
        _company_a, token = _setup_tenant_a(
            pg_db_session,
            installments_http_client,
            codes={"installments.contract.view"},
        )

        response = installments_http_client.get(
            _INSTALLMENTS_PREFIX.format(company_id=company_b.id)
            + f"/customers/{ctx_b['customer_id']}/statement",
            headers=_auth_header(token),
        )
        assert response.status_code == 403, response.text
