"""API integration tests for Accounts Receivable endpoints — Phase 6.

Tests (tasks.md T155):
  - GET customer-ledger, GET aging, GET customer-statement
  - POST credit-hold, POST credit-hold/release, POST credit-limit
  - POST transactions/{id}/write-off
  - 401 enforcement
  - Cross-tenant isolation

Spec ref: specs/008-accounting-finance/tasks.md T155
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from modules.accounting.dependencies import build_ar_service
from modules.accounting.models.coa import Account
from modules.accounting.models.foundation import AccountingConfiguration
from modules.accounting.repositories.coa import AccountRepository
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
            "legal_name": f"AR Test Co {suffix}",
            "email": f"contact-{suffix}@ar-test.example.com",
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
    ar = account_repo.create(
        Account(
            company_id=company_id,
            account_code="1100",
            account_name="AR",
            account_type="ASSET",
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
    bad_debt = account_repo.create(
        Account(
            company_id=company_id,
            account_code="6900",
            account_name="Bad Debt Expense",
            account_type="EXPENSE",
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
    AccountingConfigurationRepository(db_session).create(
        AccountingConfiguration(
            company_id=company_id,
            default_ar_account_id=ar.id,
            default_revenue_account_id=revenue.id,
            default_bad_debt_account_id=bad_debt.id,
        )
    )
    return {"ar": ar, "revenue": revenue, "bad_debt": bad_debt, "today": today}


def _seed_invoice(
    db_session: Session, company_id: uuid.UUID, gl: dict, customer_id: uuid.UUID
) -> dict:
    ar_service = build_ar_service(db_session, with_sales_sync=False)
    transaction, _ = ar_service.record_sales_invoice(
        company_id=company_id,
        customer_id=customer_id,
        invoice_id=uuid.uuid4(),
        invoice_number="INV-API-001",
        total_amount=Decimal("100"),
        currency_code="USD",
        transaction_date=gl["today"],
        due_date=gl["today"],
        actor_id=None,
    )
    db_session.commit()
    return {"transaction_id": str(transaction.id)}


class TestUnauthenticated:
    def test_ar_endpoints_require_auth(self, test_client: TestClient) -> None:
        resp = test_client.get(
            _url(str(uuid.uuid4()), f"/ar/customer-ledger/{uuid.uuid4()}")
        )
        assert resp.status_code == 401


class TestCustomerLedgerEndpoint:
    def test_get_customer_ledger(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        token = _user_token(test_client, db_session, "ar_ledger@example.com")
        cid = _create_company(test_client, token)
        customer_id = uuid.uuid4()
        gl = _setup_gl(db_session, cid)
        _seed_invoice(db_session, cid, gl, customer_id)

        resp = test_client.get(
            _url(str(cid), f"/ar/customer-ledger/{customer_id}"), headers=_auth(token)
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert data["total_outstanding_base"] == "100.000000"
        assert data["credit_status"] == "GOOD"

    def test_get_customer_ledger_not_found(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        token = _user_token(test_client, db_session, "ar_ledger_404@example.com")
        cid = _create_company(test_client, token)
        resp = test_client.get(
            _url(str(cid), f"/ar/customer-ledger/{uuid.uuid4()}"), headers=_auth(token)
        )
        assert resp.status_code == 404


class TestAgingEndpoint:
    def test_get_aging_report(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        token = _user_token(test_client, db_session, "ar_aging@example.com")
        cid = _create_company(test_client, token)
        customer_id = uuid.uuid4()
        gl = _setup_gl(db_session, cid)
        _seed_invoice(db_session, cid, gl, customer_id)

        resp = test_client.get(
            _url(str(cid), f"/ar/aging?as_of_date={gl['today'].isoformat()}"),
            headers=_auth(token),
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert len(data["rows"]) == 1
        assert data["rows"][0]["current"] == "100.000000"
        assert data["totals"]["total"] == "100.000000"


class TestCustomerStatementEndpoint:
    def test_get_customer_statement(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        token = _user_token(test_client, db_session, "ar_statement@example.com")
        cid = _create_company(test_client, token)
        customer_id = uuid.uuid4()
        gl = _setup_gl(db_session, cid)
        _seed_invoice(db_session, cid, gl, customer_id)

        resp = test_client.get(
            _url(
                str(cid),
                f"/ar/customer-statement/{customer_id}"
                f"?from_date={gl['today'].isoformat()}&to_date={gl['today'].isoformat()}",
            ),
            headers=_auth(token),
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert len(data["transactions"]) == 1
        assert data["closing_balance"] == "100.000000"


class TestCreditManagementEndpoints:
    def test_credit_limit_hold_and_release(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        token = _user_token(test_client, db_session, "ar_credit@example.com")
        cid = _create_company(test_client, token)
        customer_id = uuid.uuid4()
        _setup_gl(db_session, cid)

        resp = test_client.post(
            _url(str(cid), f"/ar/customers/{customer_id}/credit-limit"),
            json={"credit_limit": "5000.00"},
            headers=_auth(token),
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["data"]["credit_limit"] == "5000.000000"

        resp = test_client.post(
            _url(str(cid), f"/ar/customers/{customer_id}/credit-hold"),
            json={"reason": "Late payments"},
            headers=_auth(token),
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["data"]["credit_status"] == "HOLD"

        resp = test_client.post(
            _url(str(cid), f"/ar/customers/{customer_id}/credit-hold/release"),
            json={"reason": "Resolved"},
            headers=_auth(token),
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["data"]["credit_status"] == "GOOD"

    def test_credit_hold_requires_reason(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        token = _user_token(test_client, db_session, "ar_credit_noreason@example.com")
        cid = _create_company(test_client, token)
        customer_id = uuid.uuid4()
        resp = test_client.post(
            _url(str(cid), f"/ar/customers/{customer_id}/credit-hold"),
            json={"reason": ""},
            headers=_auth(token),
        )
        assert resp.status_code == 422


class TestWriteOffEndpoint:
    def test_write_off_ar_transaction(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        token = _user_token(test_client, db_session, "ar_writeoff@example.com")
        cid = _create_company(test_client, token)
        customer_id = uuid.uuid4()
        gl = _setup_gl(db_session, cid)
        seeded = _seed_invoice(db_session, cid, gl, customer_id)

        resp = test_client.post(
            _url(str(cid), f"/ar/transactions/{seeded['transaction_id']}/write-off"),
            json={"reason": "Uncollectible"},
            headers=_auth(token),
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert data["status"] == "WRITTEN_OFF"
        assert data["outstanding_amount"] == "0.000000"

    def test_write_off_already_written_off_transaction_returns_422(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        token = _user_token(test_client, db_session, "ar_writeoff_twice@example.com")
        cid = _create_company(test_client, token)
        customer_id = uuid.uuid4()
        gl = _setup_gl(db_session, cid)
        seeded = _seed_invoice(db_session, cid, gl, customer_id)

        test_client.post(
            _url(str(cid), f"/ar/transactions/{seeded['transaction_id']}/write-off"),
            json={"reason": "First write-off"},
            headers=_auth(token),
        )
        resp = test_client.post(
            _url(str(cid), f"/ar/transactions/{seeded['transaction_id']}/write-off"),
            json={"reason": "Second write-off"},
            headers=_auth(token),
        )
        assert resp.status_code == 422


class TestCrossTenantIsolation:
    def test_customer_ledger_not_visible_across_tenants(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        token = _user_token(test_client, db_session, "ar_tenant@example.com")
        cid_a = _create_company(test_client, token)
        cid_b = _create_company(test_client, token)
        customer_id = uuid.uuid4()
        gl = _setup_gl(db_session, cid_a)
        _seed_invoice(db_session, cid_a, gl, customer_id)

        resp = test_client.get(
            _url(str(cid_b), f"/ar/customer-ledger/{customer_id}"), headers=_auth(token)
        )
        assert resp.status_code == 404
