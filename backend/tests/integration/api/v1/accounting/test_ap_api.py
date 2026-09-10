"""API integration tests for Accounts Payable endpoints — Phase 7.

Tests (tasks.md T174):
  - GET supplier-ledger, GET aging, GET supplier-statement
  - POST bills, POST credit-notes (manual entry, T163/T164)
  - POST reconcile-statement
  - GET payments/{id}/remittance-advice
  - 401 enforcement
  - Cross-tenant isolation

Spec ref: specs/008-accounting-finance/tasks.md T174
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from modules.accounting.dependencies import build_ap_service
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
            "legal_name": f"AP Test Co {suffix}",
            "email": f"contact-{suffix}@ap-test.example.com",
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
    ap = account_repo.create(
        Account(
            company_id=company_id,
            account_code="2100",
            account_name="AP",
            account_type="LIABILITY",
        )
    )
    expense = account_repo.create(
        Account(
            company_id=company_id,
            account_code="5000",
            account_name="Expense",
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
            default_ap_account_id=ap.id,
            default_expense_account_id=expense.id,
        )
    )
    return {"ap": ap, "expense": expense, "today": today}


def _seed_bill(
    db_session: Session,
    company_id: uuid.UUID,
    gl: dict[str, Any],
    supplier_id: uuid.UUID,
) -> dict[str, Any]:
    ap_service = build_ap_service(db_session)
    transaction, _ = ap_service.record_supplier_bill(
        company_id=company_id,
        supplier_id=supplier_id,
        bill_id=uuid.uuid4(),
        bill_number="BILL-API-001",
        total_amount=Decimal("100"),
        currency_code="USD",
        transaction_date=gl["today"],
        due_date=gl["today"],
        actor_id=None,
    )
    db_session.commit()
    return {"transaction_id": str(transaction.id)}


class TestUnauthenticated:
    def test_ap_endpoints_require_auth(self, test_client: TestClient) -> None:
        resp = test_client.get(
            _url(str(uuid.uuid4()), f"/ap/supplier-ledger/{uuid.uuid4()}")
        )
        assert resp.status_code == 401


class TestSupplierLedgerEndpoint:
    def test_get_supplier_ledger(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        token = _user_token(test_client, db_session, "ap_ledger@example.com")
        cid = _create_company(test_client, token)
        supplier_id = uuid.uuid4()
        gl = _setup_gl(db_session, cid)
        _seed_bill(db_session, cid, gl, supplier_id)

        resp = test_client.get(
            _url(str(cid), f"/ap/supplier-ledger/{supplier_id}"), headers=_auth(token)
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert data["total_outstanding_base"] == "100.000000"

    def test_get_supplier_ledger_not_found(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        token = _user_token(test_client, db_session, "ap_ledger_404@example.com")
        cid = _create_company(test_client, token)
        resp = test_client.get(
            _url(str(cid), f"/ap/supplier-ledger/{uuid.uuid4()}"), headers=_auth(token)
        )
        assert resp.status_code == 404


class TestAgingEndpoint:
    def test_get_aging_report(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        token = _user_token(test_client, db_session, "ap_aging@example.com")
        cid = _create_company(test_client, token)
        supplier_id = uuid.uuid4()
        gl = _setup_gl(db_session, cid)
        _seed_bill(db_session, cid, gl, supplier_id)

        resp = test_client.get(
            _url(str(cid), f"/ap/aging?as_of_date={gl['today'].isoformat()}"),
            headers=_auth(token),
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert len(data["rows"]) == 1
        assert data["rows"][0]["current"] == "100.000000"
        assert data["totals"]["total"] == "100.000000"


class TestSupplierStatementEndpoint:
    def test_get_supplier_statement(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        token = _user_token(test_client, db_session, "ap_statement@example.com")
        cid = _create_company(test_client, token)
        supplier_id = uuid.uuid4()
        gl = _setup_gl(db_session, cid)
        _seed_bill(db_session, cid, gl, supplier_id)

        resp = test_client.get(
            _url(
                str(cid),
                f"/ap/supplier-statement/{supplier_id}"
                f"?from_date={gl['today'].isoformat()}&to_date={gl['today'].isoformat()}",
            ),
            headers=_auth(token),
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert len(data["transactions"]) == 1
        assert data["closing_balance"] == "100.000000"


class TestBillAndCreditNoteEndpoints:
    def test_create_bill(self, test_client: TestClient, db_session: Session) -> None:
        token = _user_token(test_client, db_session, "ap_bill_create@example.com")
        cid = _create_company(test_client, token)
        supplier_id = uuid.uuid4()
        gl = _setup_gl(db_session, cid)

        resp = test_client.post(
            _url(str(cid), "/ap/bills"),
            json={
                "supplier_id": str(supplier_id),
                "bill_number": "BILL-2001",
                "total_amount": "250.00",
                "currency_code": "USD",
                "transaction_date": gl["today"].isoformat(),
                "due_date": gl["today"].isoformat(),
            },
            headers=_auth(token),
        )
        assert resp.status_code == 201, resp.text
        data = resp.json()["data"]
        assert data["status"] == "OPEN"
        assert data["outstanding_amount"] == "250.000000"

    def test_create_credit_note_against_bill(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        token = _user_token(test_client, db_session, "ap_creditnote_create@example.com")
        cid = _create_company(test_client, token)
        supplier_id = uuid.uuid4()
        gl = _setup_gl(db_session, cid)

        bill_resp = test_client.post(
            _url(str(cid), "/ap/bills"),
            json={
                "supplier_id": str(supplier_id),
                "bill_number": "BILL-2002",
                "total_amount": "300.00",
                "currency_code": "USD",
                "transaction_date": gl["today"].isoformat(),
            },
            headers=_auth(token),
        )
        bill_id = bill_resp.json()["data"]["source_document_id"]

        resp = test_client.post(
            _url(str(cid), "/ap/credit-notes"),
            json={
                "supplier_id": str(supplier_id),
                "bill_id": bill_id,
                "bill_number": "BILL-2002",
                "credit_amount": "100.00",
                "transaction_date": gl["today"].isoformat(),
            },
            headers=_auth(token),
        )
        assert resp.status_code == 201, resp.text
        data = resp.json()["data"]
        assert data["transaction_type"] == "CREDIT_NOTE"
        assert data["outstanding_amount"] == "-100.000000"


class TestReconcileStatementEndpoint:
    def test_reconcile_statement_matches_bill(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        token = _user_token(test_client, db_session, "ap_reconcile@example.com")
        cid = _create_company(test_client, token)
        supplier_id = uuid.uuid4()
        gl = _setup_gl(db_session, cid)
        _seed_bill(db_session, cid, gl, supplier_id)

        resp = test_client.post(
            _url(str(cid), "/ap/reconcile-statement"),
            json={
                "supplier_id": str(supplier_id),
                "statement_date": gl["today"].isoformat(),
                "statement_total": "100.00",
                "statement_lines": [{"reference": "STMT-1", "amount": "100.00"}],
            },
            headers=_auth(token),
        )
        assert resp.status_code == 201, resp.text
        data = resp.json()["data"]
        assert data["status"] == "COMPLETED"
        assert len(data["items"]) == 1
        assert data["items"][0]["match_status"] == "MATCHED"


class TestRemittanceAdviceEndpoint:
    def test_remittance_advice_empty_until_payment_allocations_exist(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        token = _user_token(test_client, db_session, "ap_remittance@example.com")
        cid = _create_company(test_client, token)
        _setup_gl(db_session, cid)
        payment_id = uuid.uuid4()

        resp = test_client.get(
            _url(str(cid), f"/ap/payments/{payment_id}/remittance-advice"),
            headers=_auth(token),
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert data["lines"] == []
        assert data["total_paid"] == "0"


class TestCrossTenantIsolation:
    def test_supplier_ledger_not_visible_across_tenants(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        token = _user_token(test_client, db_session, "ap_tenant@example.com")
        cid_a = _create_company(test_client, token)
        cid_b = _create_company(test_client, token)
        supplier_id = uuid.uuid4()
        gl = _setup_gl(db_session, cid_a)
        _seed_bill(db_session, cid_a, gl, supplier_id)

        resp = test_client.get(
            _url(str(cid_b), f"/ap/supplier-ledger/{supplier_id}"), headers=_auth(token)
        )
        assert resp.status_code == 404
