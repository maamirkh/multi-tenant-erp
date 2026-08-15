"""API integration tests for the CFO Financial Intelligence & KPI Dashboard — Phase 15.

Tests (tasks.md T293):
  - GET /dashboard/kpis returns all 15 KPIs with the documented structure
  - GET /dashboard/cash-position reflects a customer payment immediately
  - 401 without a token
  - RBAC: granted for a role with ``accounting.reports.view`` (manager,
    standing in for "CFO" — this system has no literal "cfo" role slug;
    see migration 049's ``_ROLE_PERMISSION_CODES``), denied for cashier
  - Cross-tenant isolation

Spec ref: specs/008-accounting-finance/tasks.md T293
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from modules.accounting.dependencies import build_posting_engine
from modules.accounting.models.coa import Account, AccountGroup
from modules.accounting.models.foundation import AccountingConfiguration
from modules.accounting.repositories.coa import (
    AccountGroupRepository,
    AccountRepository,
)
from modules.accounting.repositories.fiscal import (
    FiscalPeriodRepository,
    FiscalYearRepository,
    OpeningBalanceRepository,
)
from modules.accounting.repositories.foundation import AccountingConfigurationRepository
from modules.accounting.repositories.gl import AccountingAuditLogRepository
from modules.accounting.services.audit_service import AuditLogService
from modules.accounting.services.fiscal_service import FiscalCalendarService
from tests.fixtures.auth_fixtures import create_test_user
from tests.fixtures.users_roles_fixtures import create_member_with_role

_TEST_PASSWORD = "DashboardApi@12345"


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


def _user_token_and_id(
    test_client: TestClient, db_session: Session, email: str
) -> tuple[str, uuid.UUID]:
    user, pw = create_test_user(db_session, email=email, password=_TEST_PASSWORD)
    return _login(test_client, user.email, pw), user.id


def _create_company(client: TestClient, token: str) -> uuid.UUID:
    suffix = uuid.uuid4().hex[:8]
    resp = client.post(
        "/api/v1/companies",
        json={
            "legal_name": f"Dashboard Test Co {suffix}",
            "email": f"contact-{suffix}@dashboard-test.example.com",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201, resp.text
    return uuid.UUID(resp.json()["data"]["id"])


def _setup(db_session: Session, company_id: uuid.UUID) -> dict:
    account_repo = AccountRepository(db_session)
    group_repo = AccountGroupRepository(db_session)
    cur_ast = group_repo.create(
        AccountGroup(
            company_id=company_id,
            group_code="CUR-AST",
            group_name="Current Assets",
            account_type="ASSET",
        )
    )
    cash = account_repo.create(
        Account(
            company_id=company_id,
            account_code="1000",
            account_name="Cash",
            account_type="ASSET",
            account_group_id=cur_ast.id,
            is_cash_account=True,
        )
    )
    ar = account_repo.create(
        Account(
            company_id=company_id,
            account_code="1100",
            account_name="Accounts Receivable",
            account_type="ASSET",
            account_group_id=cur_ast.id,
        )
    )
    equity = account_repo.create(
        Account(
            company_id=company_id,
            account_code="3000",
            account_name="Equity",
            account_type="EQUITY",
        )
    )
    revenue = account_repo.create(
        Account(
            company_id=company_id,
            account_code="4000",
            account_name="Revenue",
            account_type="REVENUE",
        )
    )

    fiscal_service = FiscalCalendarService(
        db=db_session,
        year_repo=FiscalYearRepository(db_session),
        period_repo=FiscalPeriodRepository(db_session),
        opening_balance_repo=OpeningBalanceRepository(db_session),
        audit_service=AuditLogService(
            db=db_session, audit_repo=AccountingAuditLogRepository(db_session)
        ),
    )
    today = date.today()
    fiscal_service.create_fiscal_year(
        company_id,
        f"FY-{uuid.uuid4().hex[:8]}",
        date(today.year, 1, 1),
        date(today.year, 12, 31),
        "USD",
        is_current=True,
    )

    AccountingConfigurationRepository(db_session).create(
        AccountingConfiguration(
            company_id=company_id, base_currency_code="USD", default_ar_account_id=ar.id
        )
    )

    return {
        "cash": cash,
        "ar": ar,
        "equity": equity,
        "revenue": revenue,
        "today": today,
    }


class TestUnauthenticated:
    def test_dashboard_endpoints_require_auth(self, test_client: TestClient) -> None:
        cid = str(uuid.uuid4())
        for path in ("/dashboard/kpis", "/dashboard/cash-position"):
            resp = test_client.get(_url(cid, path))
            assert resp.status_code == 401, path


class TestDashboardKPIs:
    def test_kpis_endpoint_returns_all_fifteen(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        token, _oid = _user_token_and_id(
            test_client, db_session, f"kpi-owner-{uuid.uuid4().hex[:8]}@example.com"
        )
        cid = str(_create_company(test_client, token))
        ctx = _setup(db_session, uuid.UUID(cid))

        posting_engine = build_posting_engine(db_session)
        posting_engine.post_direct(
            company_id=uuid.UUID(cid),
            journal_type="OPENING_BALANCE",
            posting_source="MANUAL",
            posting_date=ctx["today"],
            lines=[
                {
                    "account_id": ctx["cash"].id,
                    "debit_amount": Decimal("1000.00"),
                    "credit_amount": Decimal("0"),
                },
                {
                    "account_id": ctx["equity"].id,
                    "debit_amount": Decimal("0"),
                    "credit_amount": Decimal("1000.00"),
                },
            ],
            currency_code="USD",
        )

        resp = test_client.get(_url(cid, "/dashboard/kpis"), headers=_auth(token))
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]

        expected_keys = {
            "cash_position",
            "accounts_receivable_total",
            "accounts_payable_total",
            "ar_overdue_pct",
            "ap_overdue_pct",
            "revenue_mtd",
            "gross_profit_margin",
            "net_profit_margin",
            "current_ratio",
            "quick_ratio",
            "days_sales_outstanding",
            "days_payable_outstanding",
            "operating_cash_flow",
            "tax_liability_balance",
        }
        assert set(data["kpis"].keys()) == expected_keys
        for key in expected_keys:
            kpi = data["kpis"][key]
            assert {
                "label",
                "current_value",
                "prior_value",
                "change_pct",
                "trend",
            } <= set(kpi.keys())
            assert kpi["trend"] in ("up", "down", "flat")
        assert Decimal(data["kpis"]["cash_position"]["current_value"]) == Decimal(
            "1000.00"
        )
        assert isinstance(data["period_close_status"], list)
        assert len(data["period_close_status"]) == 12

    def test_kpis_endpoint_accepts_as_of_date(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        token, _oid = _user_token_and_id(
            test_client, db_session, f"kpi-asof-{uuid.uuid4().hex[:8]}@example.com"
        )
        cid = str(_create_company(test_client, token))
        ctx = _setup(db_session, uuid.UUID(cid))

        resp = test_client.get(
            _url(cid, f"/dashboard/kpis?as_of_date={ctx['today'].isoformat()}"),
            headers=_auth(token),
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["data"]["as_of_date"] == ctx["today"].isoformat()


class TestCashPositionAfterPayment:
    def test_cash_position_updates_after_customer_payment(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        token, _oid = _user_token_and_id(
            test_client, db_session, f"cash-pos-{uuid.uuid4().hex[:8]}@example.com"
        )
        cid = str(_create_company(test_client, token))
        ctx = _setup(db_session, uuid.UUID(cid))
        posting_engine = build_posting_engine(db_session)

        # Sale on credit: DR AR / CR Revenue. Cash position untouched.
        posting_engine.post_direct(
            company_id=uuid.UUID(cid),
            journal_type="STANDARD",
            posting_source="SALES",
            posting_date=ctx["today"],
            lines=[
                {
                    "account_id": ctx["ar"].id,
                    "debit_amount": Decimal("400.00"),
                    "credit_amount": Decimal("0"),
                },
                {
                    "account_id": ctx["revenue"].id,
                    "debit_amount": Decimal("0"),
                    "credit_amount": Decimal("400.00"),
                },
            ],
            currency_code="USD",
        )

        resp = test_client.get(
            _url(cid, "/dashboard/cash-position"), headers=_auth(token)
        )
        assert resp.status_code == 200, resp.text
        before = Decimal(resp.json()["data"]["total_cash_position"])
        assert before == Decimal("0")

        # Customer payment: DR Cash / CR AR — the AR "verify Cash Position
        # KPI updates" independent test from tasks.md's Phase 15 goal.
        posting_engine.post_direct(
            company_id=uuid.UUID(cid),
            journal_type="STANDARD",
            posting_source="PAYMENT",
            posting_date=ctx["today"],
            lines=[
                {
                    "account_id": ctx["cash"].id,
                    "debit_amount": Decimal("400.00"),
                    "credit_amount": Decimal("0"),
                },
                {
                    "account_id": ctx["ar"].id,
                    "debit_amount": Decimal("0"),
                    "credit_amount": Decimal("400.00"),
                },
            ],
            currency_code="USD",
        )

        resp = test_client.get(
            _url(cid, "/dashboard/cash-position"), headers=_auth(token)
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert Decimal(data["total_cash_position"]) == before + Decimal("400.00")
        assert len(data["accounts"]) == 1
        assert data["accounts"][0]["account_code"] == "1000"
        assert Decimal(data["accounts"][0]["balance"]) == Decimal("400.00")
        assert len(data["trend"]) == 7

        # AR KPI should also reflect the payment: total AR did not move via
        # the subsidiary ledger in this test (no ARTransaction rows were
        # created), so accounts_receivable_total stays 0 — this asserts the
        # KPI endpoint is independently queryable in the same scenario
        # without erroring, not a subsidiary-ledger assertion.
        resp = test_client.get(_url(cid, "/dashboard/kpis"), headers=_auth(token))
        assert resp.status_code == 200, resp.text
        assert Decimal(
            resp.json()["data"]["kpis"]["cash_position"]["current_value"]
        ) == (before + Decimal("400.00"))


def _assert_permission_denied(resp, code: str) -> None:
    assert resp.status_code == 403, resp.text
    assert resp.json()["error"]["code"] == "APPROVAL_PERMISSION_DENIED"
    assert resp.json()["error"]["details"]["permission_code"] == code


def _assert_permission_granted(resp, code: str) -> None:
    if resp.status_code == 403:
        assert resp.json()["error"].get("code") != "APPROVAL_PERMISSION_DENIED", (
            f"expected permission '{code}' to be granted, but got "
            f"APPROVAL_PERMISSION_DENIED: {resp.text}"
        )


class TestDashboardRBAC:
    def test_cashier_denied_manager_granted(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        owner_token, _oid = _user_token_and_id(
            test_client, db_session, f"dash-owner-{uuid.uuid4().hex[:8]}@example.com"
        )
        cid = str(_create_company(test_client, owner_token))
        _setup(db_session, uuid.UUID(cid))

        cashier_token, cashier_id = _user_token_and_id(
            test_client, db_session, f"dash-cash-{uuid.uuid4().hex[:8]}@example.com"
        )
        create_member_with_role(
            db_session,
            company_id=uuid.UUID(cid),
            user_id=cashier_id,
            role_slug="cashier",
        )
        for path in ("/dashboard/kpis", "/dashboard/cash-position"):
            resp = test_client.get(_url(cid, path), headers=_auth(cashier_token))
            _assert_permission_denied(resp, "accounting.reports.view")

        manager_token, manager_id = _user_token_and_id(
            test_client, db_session, f"dash-mgr-{uuid.uuid4().hex[:8]}@example.com"
        )
        create_member_with_role(
            db_session,
            company_id=uuid.UUID(cid),
            user_id=manager_id,
            role_slug="manager",
        )
        for path in ("/dashboard/kpis", "/dashboard/cash-position"):
            resp = test_client.get(_url(cid, path), headers=_auth(manager_token))
            _assert_permission_granted(resp, "accounting.reports.view")
            assert resp.status_code == 200, resp.text


class TestCrossTenantIsolation:
    def test_company_a_cannot_see_company_b_kpis(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        token_a, _ = _user_token_and_id(
            test_client, db_session, f"tenant-a-{uuid.uuid4().hex[:8]}@example.com"
        )
        cid_a = str(_create_company(test_client, token_a))
        ctx_a = _setup(db_session, uuid.UUID(cid_a))
        build_posting_engine(db_session).post_direct(
            company_id=uuid.UUID(cid_a),
            journal_type="OPENING_BALANCE",
            posting_source="MANUAL",
            posting_date=ctx_a["today"],
            lines=[
                {
                    "account_id": ctx_a["cash"].id,
                    "debit_amount": Decimal("7000.00"),
                    "credit_amount": Decimal("0"),
                },
                {
                    "account_id": ctx_a["equity"].id,
                    "debit_amount": Decimal("0"),
                    "credit_amount": Decimal("7000.00"),
                },
            ],
            currency_code="USD",
        )

        token_b, _ = _user_token_and_id(
            test_client, db_session, f"tenant-b-{uuid.uuid4().hex[:8]}@example.com"
        )
        cid_b = str(_create_company(test_client, token_b))
        _setup(db_session, uuid.UUID(cid_b))

        resp = test_client.get(_url(cid_b, "/dashboard/kpis"), headers=_auth(token_b))
        assert resp.status_code == 200, resp.text
        assert Decimal(
            resp.json()["data"]["kpis"]["cash_position"]["current_value"]
        ) == Decimal("0")

        # Company B's token cannot even read Company A's endpoint (not a
        # member of Company A).
        resp = test_client.get(_url(cid_a, "/dashboard/kpis"), headers=_auth(token_b))
        assert resp.status_code in (403, 404), resp.text
