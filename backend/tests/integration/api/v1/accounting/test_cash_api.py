"""API integration tests for Cash Management endpoints — Phase 9.

Tests (tasks.md T203):
  - GET/POST cash-accounts
  - POST cash-accounts/{id}/receipts, /payments
  - GET/POST cash-accounts/{id}/petty-cash-vouchers
  - POST cash-accounts/{id}/replenish
  - POST cash-accounts/{id}/reconcile
  - GET cash-accounts/{id}/cash-book
  - 401 enforcement
  - Cross-tenant isolation

Spec ref: specs/008-accounting-finance/tasks.md T203
"""

from __future__ import annotations

import uuid
from datetime import date
from typing import Any

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
    return str(resp.json()["data"]["access_token"])


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
            "legal_name": f"Cash Test Co {suffix}",
            "email": f"contact-{suffix}@cash-test.example.com",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201, resp.text
    return uuid.UUID(resp.json()["data"]["id"])


def _setup_gl(db_session: Session, company_id: uuid.UUID) -> dict[str, Any]:
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
    till_gl = account_repo.create(
        Account(
            company_id=company_id,
            account_code="1010",
            account_name="Cash Till",
            account_type="ASSET",
        )
    )
    petty_cash_gl = account_repo.create(
        Account(
            company_id=company_id,
            account_code="1011",
            account_name="Petty Cash",
            account_type="ASSET",
        )
    )
    bank_gl = account_repo.create(
        Account(
            company_id=company_id,
            account_code="1000",
            account_name="Bank",
            account_type="ASSET",
        )
    )
    revenue_gl = account_repo.create(
        Account(
            company_id=company_id,
            account_code="4000",
            account_name="Revenue",
            account_type="REVENUE",
        )
    )
    expense_gl = account_repo.create(
        Account(
            company_id=company_id,
            account_code="5100",
            account_name="Travel Expense",
            account_type="EXPENSE",
        )
    )
    short_over_gl = account_repo.create(
        Account(
            company_id=company_id,
            account_code="5900",
            account_name="Cash Short/Over",
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
    return {
        "till_gl": till_gl,
        "petty_cash_gl": petty_cash_gl,
        "bank_gl": bank_gl,
        "revenue_gl": revenue_gl,
        "expense_gl": expense_gl,
        "short_over_gl": short_over_gl,
        "today": today,
    }


def _create_cash_account(
    test_client: TestClient,
    token: str,
    cid: str,
    gl_account_id: str,
    is_petty_cash: bool = False,
) -> dict[str, Any]:
    resp = test_client.post(
        _url(cid, "/cash-accounts"),
        json={
            "account_name": "Petty Cash Box 1" if is_petty_cash else "Main Till",
            "currency_code": "USD",
            "gl_account_id": gl_account_id,
            "is_petty_cash": is_petty_cash,
            "float_amount": "150.00" if is_petty_cash else "0",
        },
        headers=_auth(token),
    )
    assert resp.status_code == 201, resp.text
    return dict(resp.json()["data"])


class TestUnauthenticated:
    def test_cash_accounts_require_auth(self, test_client: TestClient) -> None:
        resp = test_client.get(_url(str(uuid.uuid4()), "/cash-accounts"))
        assert resp.status_code == 401


class TestCashAccountCRUD:
    def test_create_and_list(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        token = _user_token(test_client, db_session, "cash_crud@example.com")
        cid = str(_create_company(test_client, token))
        gl = _setup_gl(db_session, uuid.UUID(cid))
        account = _create_cash_account(test_client, token, cid, str(gl["till_gl"].id))

        resp = test_client.get(_url(cid, "/cash-accounts"), headers=_auth(token))
        assert resp.status_code == 200
        assert len(resp.json()["data"]) == 1
        assert resp.json()["data"][0]["account_name"] == account["account_name"]


class TestCashReceiptsAndPayments:
    def test_receipt_and_payment(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        token = _user_token(test_client, db_session, "cash_receipt@example.com")
        cid = str(_create_company(test_client, token))
        gl = _setup_gl(db_session, uuid.UUID(cid))
        account = _create_cash_account(test_client, token, cid, str(gl["till_gl"].id))

        resp = test_client.post(
            _url(cid, f"/cash-accounts/{account['id']}/receipts"),
            json={
                "amount": "200.00",
                "contra_account_id": str(gl["revenue_gl"].id),
                "receipt_date": gl["today"].isoformat(),
            },
            headers=_auth(token),
        )
        assert resp.status_code == 201, resp.text
        assert resp.json()["data"]["amount"] == "200.000000"

        resp = test_client.post(
            _url(cid, f"/cash-accounts/{account['id']}/payments"),
            json={
                "amount": "50.00",
                "contra_account_id": str(gl["expense_gl"].id),
                "payment_date": gl["today"].isoformat(),
            },
            headers=_auth(token),
        )
        assert resp.status_code == 201, resp.text
        assert resp.json()["data"]["amount"] == "-50.000000"

        resp = test_client.get(
            _url(
                cid,
                f"/cash-accounts/{account['id']}/cash-book"
                f"?from_date={gl['today'].isoformat()}&to_date={gl['today'].isoformat()}",
            ),
            headers=_auth(token),
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["data"]["closing_balance"] == "150.000000"


class TestPettyCashWorkflow:
    def test_voucher_and_replenishment(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        token = _user_token(test_client, db_session, "cash_petty@example.com")
        cid = str(_create_company(test_client, token))
        gl = _setup_gl(db_session, uuid.UUID(cid))
        box = _create_cash_account(
            test_client, token, cid, str(gl["petty_cash_gl"].id), is_petty_cash=True
        )

        resp = test_client.post(
            _url(cid, f"/cash-accounts/{box['id']}/petty-cash-vouchers"),
            json={
                "voucher_date": gl["today"].isoformat(),
                "amount": "150.00",
                "expense_account_id": str(gl["expense_gl"].id),
                "recipient_name": "Alice",
                "purpose": "Taxi fare",
                "voucher_number": "PCV-API-0001",
            },
            headers=_auth(token),
        )
        assert resp.status_code == 201, resp.text
        voucher = resp.json()["data"]
        assert voucher["journal_entry_id"] is None

        resp = test_client.get(
            _url(cid, f"/cash-accounts/{box['id']}/petty-cash-vouchers"),
            headers=_auth(token),
        )
        assert resp.status_code == 200
        assert len(resp.json()["data"]) == 1

        resp = test_client.post(
            _url(cid, f"/cash-accounts/{box['id']}/replenish"),
            json={
                "voucher_ids": [voucher["id"]],
                "bank_gl_account_id": str(gl["bank_gl"].id),
                "replenishment_date": gl["today"].isoformat(),
            },
            headers=_auth(token),
        )
        assert resp.status_code == 201, resp.text
        data = resp.json()["data"]
        assert data["cash_transaction"]["amount"] == "150.000000"
        assert data["vouchers"][0]["journal_entry_id"] == data["journal_entry_id"]

        resp = test_client.post(
            _url(cid, f"/cash-accounts/{box['id']}/replenish"),
            json={
                "voucher_ids": [voucher["id"]],
                "bank_gl_account_id": str(gl["bank_gl"].id),
                "replenishment_date": gl["today"].isoformat(),
            },
            headers=_auth(token),
        )
        assert resp.status_code == 422


class TestCashReconciliation:
    def test_reconcile_with_overage(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        token = _user_token(test_client, db_session, "cash_recon@example.com")
        cid = str(_create_company(test_client, token))
        gl = _setup_gl(db_session, uuid.UUID(cid))
        account = _create_cash_account(test_client, token, cid, str(gl["till_gl"].id))

        resp = test_client.post(
            _url(cid, f"/cash-accounts/{account['id']}/receipts"),
            json={
                "amount": "300.00",
                "contra_account_id": str(gl["revenue_gl"].id),
                "receipt_date": gl["today"].isoformat(),
            },
            headers=_auth(token),
        )
        assert resp.status_code == 201, resp.text

        resp = test_client.post(
            _url(cid, f"/cash-accounts/{account['id']}/reconcile"),
            json={
                "reconciliation_date": gl["today"].isoformat(),
                "physical_count_amount": "310.00",
                "difference_account_id": str(gl["short_over_gl"].id),
            },
            headers=_auth(token),
        )
        assert resp.status_code == 201, resp.text
        data = resp.json()["data"]
        assert data["difference"] == "10.000000"
        assert data["status"] == "COMPLETED"

    def test_reconcile_difference_without_account_fails(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        token = _user_token(test_client, db_session, "cash_recon_fail@example.com")
        cid = str(_create_company(test_client, token))
        gl = _setup_gl(db_session, uuid.UUID(cid))
        account = _create_cash_account(test_client, token, cid, str(gl["till_gl"].id))

        resp = test_client.post(
            _url(cid, f"/cash-accounts/{account['id']}/reconcile"),
            json={
                "reconciliation_date": gl["today"].isoformat(),
                "physical_count_amount": "10.00",
            },
            headers=_auth(token),
        )
        assert resp.status_code == 422


class TestCrossTenantIsolation:
    def test_cash_account_not_visible_across_tenants(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        token = _user_token(test_client, db_session, "cash_tenant@example.com")
        cid_a = str(_create_company(test_client, token))
        cid_b = str(_create_company(test_client, token))
        gl = _setup_gl(db_session, uuid.UUID(cid_a))
        account = _create_cash_account(test_client, token, cid_a, str(gl["till_gl"].id))

        resp = test_client.post(
            _url(cid_b, f"/cash-accounts/{account['id']}/receipts"),
            json={
                "amount": "10.00",
                "contra_account_id": str(gl["revenue_gl"].id),
                "receipt_date": gl["today"].isoformat(),
            },
            headers=_auth(token),
        )
        assert resp.status_code == 404
