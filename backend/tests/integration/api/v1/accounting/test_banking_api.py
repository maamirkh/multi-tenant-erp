"""API integration tests for Banking endpoints — Phase 8.

Tests (tasks.md T191):
  - GET/POST bank-accounts, GET/PUT bank-accounts/{id}
  - POST bank-accounts/{id}/transfer
  - Reconciliation lifecycle: start -> import-statement -> auto-match ->
    complete -> lock, plus 422 on completing with a nonzero difference and
    on modifying a locked session
  - GET/POST cheques, POST cheques/{id}/status
  - 401 enforcement
  - Cross-tenant isolation

Spec ref: specs/008-accounting-finance/tasks.md T191
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
            "legal_name": f"Banking Test Co {suffix}",
            "email": f"contact-{suffix}@banking-test.example.com",
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
    bank_gl = account_repo.create(
        Account(
            company_id=company_id,
            account_code="1000",
            account_name="Bank",
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
    today = date.today()
    fiscal_service.create_fiscal_year(
        company_id,
        f"FY-{uuid.uuid4().hex[:8]}",
        date(today.year, 1, 1),
        date(today.year, 12, 31),
        "USD",
    )
    return {"bank_gl": bank_gl, "revenue": revenue, "today": today}


def _create_bank_account(
    test_client: TestClient, token: str, cid: str, gl: dict[str, Any]
) -> dict[str, Any]:
    resp = test_client.post(
        _url(cid, "/bank-accounts"),
        json={
            "bank_name": "Main Current Account",
            "account_number": "ACC-API-001",
            "currency_code": "USD",
            "gl_account_id": str(gl["bank_gl"].id),
            "opening_balance": "0",
        },
        headers=_auth(token),
    )
    assert resp.status_code == 201, resp.text
    return dict(resp.json()["data"])


class TestUnauthenticated:
    def test_bank_accounts_require_auth(self, test_client: TestClient) -> None:
        resp = test_client.get(_url(str(uuid.uuid4()), "/bank-accounts"))
        assert resp.status_code == 401


class TestBankAccountCRUD:
    def test_create_list_get_update(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        token = _user_token(test_client, db_session, "bank_crud@example.com")
        cid = str(_create_company(test_client, token))
        gl = _setup_gl(db_session, uuid.UUID(cid))
        account = _create_bank_account(test_client, token, cid, gl)

        resp = test_client.get(_url(cid, "/bank-accounts"), headers=_auth(token))
        assert resp.status_code == 200
        assert len(resp.json()["data"]) == 1

        resp = test_client.get(
            _url(cid, f"/bank-accounts/{account['id']}"), headers=_auth(token)
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["bank_name"] == "Main Current Account"

        resp = test_client.put(
            _url(cid, f"/bank-accounts/{account['id']}"),
            json={"bank_name": "Renamed Account"},
            headers=_auth(token),
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["bank_name"] == "Renamed Account"

    def test_get_bank_account_not_found(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        token = _user_token(test_client, db_session, "bank_404@example.com")
        cid = str(_create_company(test_client, token))
        resp = test_client.get(
            _url(cid, f"/bank-accounts/{uuid.uuid4()}"), headers=_auth(token)
        )
        assert resp.status_code == 404


class TestBankTransfer:
    def test_transfer_between_accounts(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        token = _user_token(test_client, db_session, "bank_transfer@example.com")
        cid = str(_create_company(test_client, token))
        gl = _setup_gl(db_session, uuid.UUID(cid))
        from_account = _create_bank_account(test_client, token, cid, gl)

        account_repo = AccountRepository(db_session)
        savings_gl = account_repo.create(
            Account(
                company_id=uuid.UUID(cid),
                account_code="1001",
                account_name="Savings",
                account_type="ASSET",
            )
        )
        resp = test_client.post(
            _url(cid, "/bank-accounts"),
            json={
                "bank_name": "Savings Account",
                "account_number": "ACC-API-002",
                "currency_code": "USD",
                "gl_account_id": str(savings_gl.id),
            },
            headers=_auth(token),
        )
        to_account = resp.json()["data"]

        resp = test_client.post(
            _url(cid, f"/bank-accounts/{from_account['id']}/deposit"),
            json={
                "total_amount": "1000.00",
                "contra_account_id": str(gl["revenue"].id),
                "deposit_date": gl["today"].isoformat(),
            },
            headers=_auth(token),
        )
        assert resp.status_code == 201, resp.text

        resp = test_client.post(
            _url(cid, f"/bank-accounts/{from_account['id']}/transfer"),
            json={
                "to_bank_account_id": to_account["id"],
                "amount": "300.00",
                "transfer_date": gl["today"].isoformat(),
            },
            headers=_auth(token),
        )
        assert resp.status_code == 201, resp.text
        data = resp.json()["data"]
        assert data["from_transaction"]["amount"] == "-300.000000"
        assert data["to_transaction"]["amount"] == "300.000000"


class TestReconciliationLifecycle:
    def test_full_lifecycle(self, test_client: TestClient, db_session: Session) -> None:
        token = _user_token(test_client, db_session, "bank_recon@example.com")
        cid = str(_create_company(test_client, token))
        gl = _setup_gl(db_session, uuid.UUID(cid))
        account = _create_bank_account(test_client, token, cid, gl)

        resp = test_client.post(
            _url(cid, f"/bank-accounts/{account['id']}/deposit"),
            json={
                "total_amount": "500.00",
                "contra_account_id": str(gl["revenue"].id),
                "deposit_date": gl["today"].isoformat(),
            },
            headers=_auth(token),
        )
        assert resp.status_code == 201, resp.text

        resp = test_client.post(
            _url(cid, f"/bank-accounts/{account['id']}/reconciliations"),
            json={
                "statement_date": gl["today"].isoformat(),
                "statement_closing_balance": "500.00",
            },
            headers=_auth(token),
        )
        assert resp.status_code == 201, resp.text
        reconciliation = resp.json()["data"]
        rid = reconciliation["id"]
        assert reconciliation["status"] == "IN_PROGRESS"

        resp = test_client.post(
            _url(
                cid,
                f"/bank-accounts/{account['id']}/reconciliations/{rid}/import-statement",
            ),
            json={
                "lines": [
                    {"statement_date": gl["today"].isoformat(), "amount": "500.00"}
                ]
            },
            headers=_auth(token),
        )
        assert resp.status_code == 201, resp.text
        assert len(resp.json()["data"]) == 1

        resp = test_client.post(
            _url(
                cid, f"/bank-accounts/{account['id']}/reconciliations/{rid}/auto-match"
            ),
            headers=_auth(token),
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["data"]["matched_count"] == 1

        resp = test_client.post(
            _url(cid, f"/bank-accounts/{account['id']}/reconciliations/{rid}/complete"),
            headers=_auth(token),
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["data"]["status"] == "COMPLETED"
        assert resp.json()["data"]["difference"] == "0.000000"

        resp = test_client.post(
            _url(cid, f"/bank-accounts/{account['id']}/reconciliations/{rid}/lock"),
            headers=_auth(token),
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["data"]["status"] == "LOCKED"

        resp = test_client.post(
            _url(
                cid, f"/bank-accounts/{account['id']}/reconciliations/{rid}/auto-match"
            ),
            headers=_auth(token),
        )
        assert resp.status_code == 422

    def test_complete_fails_on_nonzero_difference(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        token = _user_token(
            test_client, db_session, "bank_recon_unbalanced@example.com"
        )
        cid = str(_create_company(test_client, token))
        gl = _setup_gl(db_session, uuid.UUID(cid))
        account = _create_bank_account(test_client, token, cid, gl)

        resp = test_client.post(
            _url(cid, f"/bank-accounts/{account['id']}/reconciliations"),
            json={
                "statement_date": gl["today"].isoformat(),
                "statement_closing_balance": "999.00",
            },
            headers=_auth(token),
        )
        rid = resp.json()["data"]["id"]

        resp = test_client.post(
            _url(cid, f"/bank-accounts/{account['id']}/reconciliations/{rid}/complete"),
            headers=_auth(token),
        )
        assert resp.status_code == 422


class TestChequeEndpoints:
    def test_issue_and_update_cheque_status(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        token = _user_token(test_client, db_session, "bank_cheque@example.com")
        cid = str(_create_company(test_client, token))
        gl = _setup_gl(db_session, uuid.UUID(cid))
        account = _create_bank_account(test_client, token, cid, gl)

        resp = test_client.post(
            _url(cid, "/cheques"),
            json={
                "bank_account_id": account["id"],
                "cheque_number": "CHQ-API-001",
                "payee_name": "Acme Supplies",
                "cheque_date": gl["today"].isoformat(),
                "amount": "150.00",
            },
            headers=_auth(token),
        )
        assert resp.status_code == 201, resp.text
        cheque = resp.json()["data"]
        assert cheque["status"] == "ISSUED"

        resp = test_client.get(_url(cid, "/cheques"), headers=_auth(token))
        assert resp.status_code == 200
        assert len(resp.json()["data"]) == 1

        resp = test_client.post(
            _url(cid, f"/cheques/{cheque['id']}/status"),
            json={"status": "CANCELLED", "cancel_reason": "Issued in error"},
            headers=_auth(token),
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["data"]["status"] == "CANCELLED"

        resp = test_client.get(
            _url(cid, "/cheques?status=CANCELLED"), headers=_auth(token)
        )
        assert resp.status_code == 200
        assert len(resp.json()["data"]) == 1


class TestCrossTenantIsolation:
    def test_bank_account_not_visible_across_tenants(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        token = _user_token(test_client, db_session, "bank_tenant@example.com")
        cid_a = str(_create_company(test_client, token))
        cid_b = str(_create_company(test_client, token))
        gl = _setup_gl(db_session, uuid.UUID(cid_a))
        account = _create_bank_account(test_client, token, cid_a, gl)

        resp = test_client.get(
            _url(cid_b, f"/bank-accounts/{account['id']}"), headers=_auth(token)
        )
        assert resp.status_code == 404
