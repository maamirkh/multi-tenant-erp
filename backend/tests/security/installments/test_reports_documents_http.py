"""[Epic 10, Phase 12] Live HTTP verification for the Reports/Dashboard
and Documents/Statements endpoint groups (T209/T210) — real ASGI
requests through the actual mounted router, real authentication, real
RBAC, real entitlement, mirroring Phase 11's
``test_http_security_closure.py`` established pattern (master prompt
§32: "Do not mark live-verification tasks complete from static
inspection").

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


def _make_company(db: Session, *, company_id: uuid.UUID) -> Company:
    suffix = uuid.uuid4().hex[:10]
    owner = User(
        email=f"reports-owner-{suffix}@example.test", display_name="Reports Owner"
    )
    db.add(owner)
    db.flush()
    company = Company(
        id=company_id,
        legal_name=f"Reports HTTP Co {suffix}",
        slug=f"reports-http-co-{suffix}",
        owner_id=owner.id,
        email=f"reports-http-co-{suffix}@example.com",
        status="active",
    )
    db.add(company)
    db.flush()
    db.commit()
    return company


def _login(pg_db_session: Session, test_client: TestClient, *, email: str) -> str:
    password = "ReportsHttp@1234"
    create_test_user(pg_db_session, email=email, password=password)
    pg_db_session.commit()
    response = test_client.post(
        "/api/v1/auth/login", json={"email": email, "password": password}
    )
    assert response.status_code == 200, response.text
    return response.json()["data"]["access_token"]


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
        name=f"Reports HTTP Role {uuid.uuid4().hex[:8]}",
        slug=f"reports-http-role-{uuid.uuid4().hex[:10]}",
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


class TestReportsAndDashboardHttp:
    def test_contract_register_report_reachable_and_returns_seeded_contract(
        self, installments_http_client: TestClient, pg_db_session: Session
    ) -> None:
        ctx = build_active_contract_with_schedule(
            pg_db_session, installment_count=1, installment_amount=Decimal("100.00")
        )
        company = _make_company(pg_db_session, company_id=ctx["company_id"])
        email = f"reports-{uuid.uuid4().hex[:10]}@example.com"
        token = _login(pg_db_session, installments_http_client, email=email)
        user_row = pg_db_session.query(User).filter_by(email=email).one()
        _grant_membership_with_permissions(
            pg_db_session,
            company_id=company.id,
            user_id=user_row.id,
            codes={"installments.report.view"},
        )
        _enable_installments(pg_db_session, company.id)

        response = installments_http_client.get(
            _INSTALLMENTS_PREFIX.format(company_id=company.id)
            + "/reports/contract-register",
            headers=_auth_header(token),
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["data"]["total"] == 1
        assert body["data"]["items"][0]["contract_id"] == str(ctx["contract"].id)

    def test_report_missing_permission_denied(
        self, installments_http_client: TestClient, pg_db_session: Session
    ) -> None:
        company = _make_company(pg_db_session, company_id=uuid.uuid4())
        email = f"reports-denied-{uuid.uuid4().hex[:10]}@example.com"
        token = _login(pg_db_session, installments_http_client, email=email)
        user_row = pg_db_session.query(User).filter_by(email=email).one()
        _grant_membership_with_permissions(
            pg_db_session,
            company_id=company.id,
            user_id=user_row.id,
            codes={"installments.contract.view"},
        )

        response = installments_http_client.get(
            _INSTALLMENTS_PREFIX.format(company_id=company.id) + "/reports/overdue",
            headers=_auth_header(token),
        )
        assert response.status_code == 403, response.text

    def test_unknown_report_type_is_not_found(
        self, installments_http_client: TestClient, pg_db_session: Session
    ) -> None:
        company = _make_company(pg_db_session, company_id=uuid.uuid4())
        email = f"reports-unknown-{uuid.uuid4().hex[:10]}@example.com"
        token = _login(pg_db_session, installments_http_client, email=email)
        user_row = pg_db_session.query(User).filter_by(email=email).one()
        _grant_membership_with_permissions(
            pg_db_session,
            company_id=company.id,
            user_id=user_row.id,
            codes={"installments.report.view"},
        )

        response = installments_http_client.get(
            _INSTALLMENTS_PREFIX.format(company_id=company.id)
            + "/reports/not-a-real-report-type",
            headers=_auth_header(token),
        )
        assert response.status_code == 404, response.text

    def test_dashboard_reachable_and_reflects_active_contract(
        self, installments_http_client: TestClient, pg_db_session: Session
    ) -> None:
        ctx = build_active_contract_with_schedule(
            pg_db_session, installment_count=1, installment_amount=Decimal("100.00")
        )
        company = _make_company(pg_db_session, company_id=ctx["company_id"])
        email = f"dashboard-{uuid.uuid4().hex[:10]}@example.com"
        token = _login(pg_db_session, installments_http_client, email=email)
        user_row = pg_db_session.query(User).filter_by(email=email).one()
        _grant_membership_with_permissions(
            pg_db_session,
            company_id=company.id,
            user_id=user_row.id,
            codes={"installments.report.view"},
        )
        _enable_installments(pg_db_session, company.id)

        response = installments_http_client.get(
            _INSTALLMENTS_PREFIX.format(company_id=company.id) + "/dashboard",
            headers=_auth_header(token),
        )
        assert response.status_code == 200, response.text
        data = response.json()["data"]
        assert data["active_contract_count"] == 1
        assert Decimal(data["outstanding_amount"]) == Decimal("100.00")


class TestDocumentsAndStatementsHttp:
    def test_agreement_document_reachable(
        self, installments_http_client: TestClient, pg_db_session: Session
    ) -> None:
        ctx = build_active_contract_with_schedule(
            pg_db_session, installment_count=1, installment_amount=Decimal("100.00")
        )
        company = _make_company(pg_db_session, company_id=ctx["company_id"])
        email = f"agreement-{uuid.uuid4().hex[:10]}@example.com"
        token = _login(pg_db_session, installments_http_client, email=email)
        user_row = pg_db_session.query(User).filter_by(email=email).one()
        _grant_membership_with_permissions(
            pg_db_session,
            company_id=company.id,
            user_id=user_row.id,
            codes={"installments.contract.view"},
        )
        _enable_installments(pg_db_session, company.id)

        response = installments_http_client.get(
            _INSTALLMENTS_PREFIX.format(company_id=company.id)
            + f"/contracts/{ctx['contract'].id}/documents/agreement",
            headers=_auth_header(token),
        )
        assert response.status_code == 200, response.text
        data = response.json()["data"]
        assert data["contract_id"] == str(ctx["contract"].id)

    def test_schedule_document_reachable(
        self, installments_http_client: TestClient, pg_db_session: Session
    ) -> None:
        ctx = build_active_contract_with_schedule(
            pg_db_session, installment_count=2, installment_amount=Decimal("100.00")
        )
        company = _make_company(pg_db_session, company_id=ctx["company_id"])
        email = f"schedule-doc-{uuid.uuid4().hex[:10]}@example.com"
        token = _login(pg_db_session, installments_http_client, email=email)
        user_row = pg_db_session.query(User).filter_by(email=email).one()
        _grant_membership_with_permissions(
            pg_db_session,
            company_id=company.id,
            user_id=user_row.id,
            codes={"installments.contract.view"},
        )
        _enable_installments(pg_db_session, company.id)

        response = installments_http_client.get(
            _INSTALLMENTS_PREFIX.format(company_id=company.id)
            + f"/contracts/{ctx['contract'].id}/documents/schedule",
            headers=_auth_header(token),
        )
        assert response.status_code == 200, response.text
        data = response.json()["data"]
        assert len(data["lines"]) == 2

    def test_customer_statement_reachable(
        self, installments_http_client: TestClient, pg_db_session: Session
    ) -> None:
        ctx = build_active_contract_with_schedule(
            pg_db_session, installment_count=1, installment_amount=Decimal("100.00")
        )
        company = _make_company(pg_db_session, company_id=ctx["company_id"])
        email = f"statement-{uuid.uuid4().hex[:10]}@example.com"
        token = _login(pg_db_session, installments_http_client, email=email)
        user_row = pg_db_session.query(User).filter_by(email=email).one()
        _grant_membership_with_permissions(
            pg_db_session,
            company_id=company.id,
            user_id=user_row.id,
            codes={"installments.contract.view"},
        )
        _enable_installments(pg_db_session, company.id)

        response = installments_http_client.get(
            _INSTALLMENTS_PREFIX.format(company_id=company.id)
            + f"/customers/{ctx['customer_id']}/statement",
            headers=_auth_header(token),
        )
        assert response.status_code == 200, response.text
        data = response.json()["data"]
        assert len(data["contracts"]) == 1

    def test_documents_unreachable_without_authentication(
        self, installments_http_client: TestClient, pg_db_session: Session
    ) -> None:
        company = _make_company(pg_db_session, company_id=uuid.uuid4())

        response = installments_http_client.get(
            _INSTALLMENTS_PREFIX.format(company_id=company.id)
            + f"/customers/{uuid.uuid4()}/statement"
        )
        assert response.status_code == 401, response.text
