"""API integration tests for Tax Engine and Cost Center endpoints — Phase 11.

Tests (tasks.md T246):
  - GET/POST tax-codes, GET/PUT tax-codes/{id}
  - POST tax-codes/{id}/rates
  - GET/POST tax-groups, tax-groups/{id}/lines
  - POST tax/calculate
  - GET reports/tax-summary, reports/tax-detail, reports/wht
  - GET/POST cost-centers, departments, projects
  - GET reports/cost-center-pl, reports/project-pl
  - 401 enforcement
  - Cross-tenant isolation

Spec ref: specs/008-accounting-finance/tasks.md T246
"""

from __future__ import annotations

import uuid
from datetime import date

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from modules.accounting.models.coa import Account
from modules.accounting.repositories.coa import AccountRepository
from modules.accounting.repositories.fiscal import (
    FiscalPeriodRepository,
    FiscalYearRepository,
    OpeningBalanceRepository,
)
from modules.accounting.repositories.gl import AccountingAuditLogRepository
from modules.accounting.services.audit_service import AuditLogService
from modules.accounting.services.fiscal_service import FiscalCalendarService
from tests.fixtures.auth_fixtures import create_test_user


def _login(client: TestClient, email: str, password: str) -> str:
    resp = client.post(
        "/api/v1/auth/login", json={"email": email, "password": password}
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]["access_token"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _url(company_id: str, path: str) -> str:
    return f"/api/v1/companies/{company_id}/accounting{path}"


def _user_token(test_client: TestClient, db_session: Session, email: str) -> str:
    user, pw = create_test_user(db_session, email=email)
    return _login(test_client, user.email, pw)


def _create_company(client: TestClient, token: str) -> uuid.UUID:
    """Create a real company (via the API) so the caller becomes its owner
    and active member — required now that company-scoped routes enforce
    membership (see api/v1/router.py's get_current_company_member gate)."""
    suffix = uuid.uuid4().hex[:8]
    resp = client.post(
        "/api/v1/companies",
        json={
            "legal_name": f"Tax Test Co {suffix}",
            "email": f"contact-{suffix}@tax-test.example.com",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201, resp.text
    return uuid.UUID(resp.json()["data"]["id"])


def _setup_gl(db_session: Session, company_id: uuid.UUID) -> dict:
    account_repo = AccountRepository(db_session)
    fiscal_service = FiscalCalendarService(
        db=db_session,
        year_repo=FiscalYearRepository(db_session),
        period_repo=FiscalPeriodRepository(db_session),
        opening_balance_repo=OpeningBalanceRepository(db_session),
        audit_service=AuditLogService(
            db=db_session, audit_repo=AccountingAuditLogRepository(db_session)
        ),
    )
    vat_payable = account_repo.create(
        Account(
            company_id=company_id,
            account_code="2200",
            account_name="VAT Payable",
            account_type="LIABILITY",
        )
    )
    today = date.today()
    fiscal_service.create_fiscal_year(
        company_id,
        f"FY-{uuid.uuid4().hex[:8]}",
        date(today.year, 1, 1),
        date(today.year, 12, 31),
        "USD",
    )
    return {"vat_payable": vat_payable, "today": today}


def _create_tax_code(test_client: TestClient, token: str, cid: str, gl: dict) -> dict:
    resp = test_client.post(
        _url(cid, "/tax-codes"),
        json={
            "tax_code": "VAT-15",
            "tax_name": "Standard VAT",
            "tax_type": "VAT",
            "applicability": "SALES",
            "gl_account_id": str(gl["vat_payable"].id),
        },
        headers=_auth(token),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]


class TestUnauthenticated:
    def test_tax_codes_require_auth(self, test_client: TestClient) -> None:
        resp = test_client.get(_url(str(uuid.uuid4()), "/tax-codes"))
        assert resp.status_code == 401

    def test_cost_centers_require_auth(self, test_client: TestClient) -> None:
        resp = test_client.get(_url(str(uuid.uuid4()), "/cost-centers"))
        assert resp.status_code == 401


class TestTaxCodeCRUD:
    def test_create_list_get_update(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        token = _user_token(test_client, db_session, "tax_crud@example.com")
        cid = str(_create_company(test_client, token))
        gl = _setup_gl(db_session, uuid.UUID(cid))
        tax_code = _create_tax_code(test_client, token, cid, gl)

        resp = test_client.get(_url(cid, "/tax-codes"), headers=_auth(token))
        assert resp.status_code == 200
        assert len(resp.json()["data"]) == 1

        resp = test_client.get(
            _url(cid, f"/tax-codes/{tax_code['id']}"), headers=_auth(token)
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["tax_code"] == "VAT-15"

        resp = test_client.put(
            _url(cid, f"/tax-codes/{tax_code['id']}"),
            json={"tax_name": "Renamed VAT"},
            headers=_auth(token),
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["tax_name"] == "Renamed VAT"

    def test_get_tax_code_not_found(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        token = _user_token(test_client, db_session, "tax_404@example.com")
        cid = str(_create_company(test_client, token))
        resp = test_client.get(
            _url(cid, f"/tax-codes/{uuid.uuid4()}"), headers=_auth(token)
        )
        assert resp.status_code == 404

    def test_duplicate_tax_code_rejected_with_clean_error(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        token = _user_token(test_client, db_session, "tax_dup@example.com")
        cid = str(_create_company(test_client, token))
        gl = _setup_gl(db_session, uuid.UUID(cid))
        _create_tax_code(test_client, token, cid, gl)

        resp = test_client.post(
            _url(cid, "/tax-codes"),
            json={
                "tax_code": "VAT-15",
                "tax_name": "Duplicate",
                "tax_type": "VAT",
                "applicability": "SALES",
                "gl_account_id": str(gl["vat_payable"].id),
            },
            headers=_auth(token),
        )
        assert resp.status_code == 409, resp.text
        assert resp.json()["error"]["code"] == "DUPLICATE_TAX_CODE"


class TestTaxRates:
    def test_add_rate_and_reject_overlap(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        token = _user_token(test_client, db_session, "tax_rates@example.com")
        cid = str(_create_company(test_client, token))
        gl = _setup_gl(db_session, uuid.UUID(cid))
        tax_code = _create_tax_code(test_client, token, cid, gl)

        resp = test_client.post(
            _url(cid, f"/tax-codes/{tax_code['id']}/rates"),
            json={
                "effective_from": "2026-01-01",
                "effective_to": "2026-05-31",
                "rate": "15.0",
            },
            headers=_auth(token),
        )
        assert resp.status_code == 201, resp.text

        resp = test_client.post(
            _url(cid, f"/tax-codes/{tax_code['id']}/rates"),
            json={
                "effective_from": "2026-03-01",
                "effective_to": "2026-04-01",
                "rate": "20.0",
            },
            headers=_auth(token),
        )
        assert resp.status_code == 422

        resp = test_client.get(
            _url(cid, f"/tax-codes/{tax_code['id']}/rates"), headers=_auth(token)
        )
        assert resp.status_code == 200
        assert len(resp.json()["data"]) == 1


class TestTaxGroups:
    def test_create_group_and_add_line(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        token = _user_token(test_client, db_session, "tax_groups@example.com")
        cid = str(_create_company(test_client, token))
        gl = _setup_gl(db_session, uuid.UUID(cid))
        tax_code = _create_tax_code(test_client, token, cid, gl)

        resp = test_client.post(
            _url(cid, "/tax-groups"),
            json={
                "group_code": "COMBO",
                "group_name": "Federal + Provincial",
                "applicability": "SALES",
            },
            headers=_auth(token),
        )
        assert resp.status_code == 201, resp.text
        group = resp.json()["data"]

        resp = test_client.post(
            _url(cid, f"/tax-groups/{group['id']}/lines"),
            json={"tax_code_id": tax_code["id"], "display_order": 1},
            headers=_auth(token),
        )
        assert resp.status_code == 201, resp.text

        resp = test_client.get(
            _url(cid, f"/tax-groups/{group['id']}/lines"), headers=_auth(token)
        )
        assert resp.status_code == 200
        assert len(resp.json()["data"]) == 1

        resp = test_client.get(_url(cid, "/tax-groups"), headers=_auth(token))
        assert resp.status_code == 200
        assert len(resp.json()["data"]) == 1

    def test_duplicate_tax_group_code_rejected_with_clean_error(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        token = _user_token(test_client, db_session, "tax_group_dup@example.com")
        cid = str(_create_company(test_client, token))
        _setup_gl(db_session, uuid.UUID(cid))

        resp = test_client.post(
            _url(cid, "/tax-groups"),
            json={
                "group_code": "COMBO",
                "group_name": "Federal + Provincial",
                "applicability": "SALES",
            },
            headers=_auth(token),
        )
        assert resp.status_code == 201, resp.text

        resp = test_client.post(
            _url(cid, "/tax-groups"),
            json={
                "group_code": "COMBO",
                "group_name": "Duplicate",
                "applicability": "SALES",
            },
            headers=_auth(token),
        )
        assert resp.status_code == 409, resp.text
        assert resp.json()["error"]["code"] == "DUPLICATE_TAX_GROUP_CODE"


class TestTaxCalculationAndReports:
    def test_calculate_tax_endpoint(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        token = _user_token(test_client, db_session, "tax_calc@example.com")
        cid = str(_create_company(test_client, token))
        gl = _setup_gl(db_session, uuid.UUID(cid))
        tax_code = _create_tax_code(test_client, token, cid, gl)
        test_client.post(
            _url(cid, f"/tax-codes/{tax_code['id']}/rates"),
            json={"effective_from": gl["today"].isoformat(), "rate": "15.0"},
            headers=_auth(token),
        )

        resp = test_client.post(
            _url(cid, "/tax/calculate"),
            json={
                "tax_code_or_group_id": tax_code["id"],
                "base_amount": "1000.00",
                "transaction_date": gl["today"].isoformat(),
            },
            headers=_auth(token),
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert data["total_tax_amount"] == "150.00"
        assert len(data["lines"]) == 1

    def test_tax_summary_and_detail_reports_empty_when_no_activity(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        token = _user_token(test_client, db_session, "tax_reports@example.com")
        cid = str(_create_company(test_client, token))
        gl = _setup_gl(db_session, uuid.UUID(cid))
        _create_tax_code(test_client, token, cid, gl)

        resp = test_client.get(
            _url(
                cid,
                f"/reports/tax-summary?period_start={gl['today'].isoformat()}&period_end={gl['today'].isoformat()}",
            ),
            headers=_auth(token),
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["data"]["rows"] == []

        resp = test_client.get(
            _url(
                cid,
                f"/reports/tax-detail?period_start={gl['today'].isoformat()}&period_end={gl['today'].isoformat()}",
            ),
            headers=_auth(token),
        )
        assert resp.status_code == 200
        assert resp.json()["data"] == []

    def test_wht_report_empty_when_no_activity(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        token = _user_token(test_client, db_session, "wht_reports@example.com")
        cid = str(_create_company(test_client, token))
        gl = _setup_gl(db_session, uuid.UUID(cid))

        resp = test_client.get(
            _url(
                cid,
                f"/reports/wht?period_start={gl['today'].isoformat()}&period_end={gl['today'].isoformat()}",
            ),
            headers=_auth(token),
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["data"]["rows"] == []
        assert resp.json()["data"]["total_wht"] == "0"


class TestCostCenterAndDepartmentAndProject:
    def test_create_department_and_cost_center(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        token = _user_token(test_client, db_session, "cc_crud@example.com")
        cid = str(_create_company(test_client, token))
        _setup_gl(db_session, uuid.UUID(cid))

        resp = test_client.post(
            _url(cid, "/departments"),
            json={"dept_code": "OPS", "dept_name": "Operations"},
            headers=_auth(token),
        )
        assert resp.status_code == 201, resp.text
        department = resp.json()["data"]

        resp = test_client.post(
            _url(cid, "/cost-centers"),
            json={
                "center_code": "CC-01",
                "center_name": "Main Store",
                "department_id": department["id"],
            },
            headers=_auth(token),
        )
        assert resp.status_code == 201, resp.text

        resp = test_client.get(_url(cid, "/cost-centers"), headers=_auth(token))
        assert resp.status_code == 200
        assert len(resp.json()["data"]) == 1

        resp = test_client.get(_url(cid, "/departments"), headers=_auth(token))
        assert resp.status_code == 200
        assert len(resp.json()["data"]) == 1

    def test_create_project(self, test_client: TestClient, db_session: Session) -> None:
        token = _user_token(test_client, db_session, "project_crud@example.com")
        cid = str(_create_company(test_client, token))
        _setup_gl(db_session, uuid.UUID(cid))

        resp = test_client.post(
            _url(cid, "/projects"),
            json={
                "project_code": "PRJ-01",
                "project_name": "New Warehouse",
                "budget_amount": "50000.00",
            },
            headers=_auth(token),
        )
        assert resp.status_code == 201, resp.text

        resp = test_client.get(_url(cid, "/projects"), headers=_auth(token))
        assert resp.status_code == 200
        assert len(resp.json()["data"]) == 1


class TestCostCenterPLReport:
    def test_cost_center_pl_report_with_no_activity(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        token = _user_token(test_client, db_session, "cc_pl@example.com")
        cid = str(_create_company(test_client, token))
        gl = _setup_gl(db_session, uuid.UUID(cid))

        resp = test_client.post(
            _url(cid, "/cost-centers"),
            json={"center_code": "CC-02", "center_name": "Branch B"},
            headers=_auth(token),
        )
        cost_center = resp.json()["data"]

        resp = test_client.get(
            _url(
                cid,
                f"/reports/cost-center-pl?cost_center_id={cost_center['id']}"
                f"&period_start={gl['today'].isoformat()}&period_end={gl['today'].isoformat()}",
            ),
            headers=_auth(token),
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert data["total_revenue"] == "0"
        assert data["total_expense"] == "0"
        assert data["net_income"] == "0"

    def test_cost_center_pl_report_not_found(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        token = _user_token(test_client, db_session, "cc_pl_404@example.com")
        cid = str(_create_company(test_client, token))
        resp = test_client.get(
            _url(cid, f"/reports/cost-center-pl?cost_center_id={uuid.uuid4()}"),
            headers=_auth(token),
        )
        assert resp.status_code == 404


class TestCrossTenantIsolation:
    def test_tax_code_not_visible_across_tenants(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        token = _user_token(test_client, db_session, "tax_tenant@example.com")
        cid_a = str(_create_company(test_client, token))
        cid_b = str(_create_company(test_client, token))
        gl = _setup_gl(db_session, uuid.UUID(cid_a))
        tax_code = _create_tax_code(test_client, token, cid_a, gl)

        resp = test_client.get(
            _url(cid_b, f"/tax-codes/{tax_code['id']}"), headers=_auth(token)
        )
        assert resp.status_code == 404
