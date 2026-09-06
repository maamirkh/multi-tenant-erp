"""API integration tests for Payment Processing endpoints — Phase 10.

Tests (tasks.md T223):
  - GET/POST customer & supplier payments
  - POST allocate
  - POST cancel
  - POST refund
  - GET unallocated
  - GET wht-certificate
  - 401 enforcement
  - Cross-tenant isolation

Spec ref: specs/008-accounting-finance/tasks.md T223
"""

from __future__ import annotations

import uuid
from datetime import date

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from modules.accounting.models.banking import BankAccount
from modules.accounting.models.coa import Account
from modules.accounting.repositories.banking import BankAccountRepository
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
            "legal_name": f"Payment Test Co {suffix}",
            "email": f"contact-{suffix}@payment-test.example.com",
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
    ap = account_repo.create(
        Account(
            company_id=company_id,
            account_code="2000",
            account_name="AP",
            account_type="LIABILITY",
        )
    )
    wht_payable = account_repo.create(
        Account(
            company_id=company_id,
            account_code="2100",
            account_name="WHT Payable",
            account_type="LIABILITY",
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
    bank = BankAccountRepository(db_session).create(
        BankAccount(
            company_id=company_id,
            bank_name="Test Bank",
            account_number="ACC-API-0001",
            currency_code="USD",
            gl_account_id=bank_gl.id,
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
        "ar": ar,
        "ap": ap,
        "wht_payable": wht_payable,
        "bank": bank,
        "today": today,
    }


def _configure_accounts(
    test_client: TestClient, token: str, cid: str, gl: dict
) -> None:
    for role, account in (
        ("default_ar_account_id", gl["ar"]),
        ("default_ap_account_id", gl["ap"]),
    ):
        resp = test_client.put(
            _url(cid, "/system-accounts"),
            json={"role": role, "account_id": str(account.id)},
            headers=_auth(token),
        )
        assert resp.status_code == 200, resp.text


class TestUnauthenticated:
    def test_payments_require_auth(self, test_client: TestClient) -> None:
        resp = test_client.get(
            _url(str(uuid.uuid4()), f"/payments/customer?customer_id={uuid.uuid4()}")
        )
        assert resp.status_code == 401


class TestCustomerPayment:
    def test_create_list_allocate_customer_payment(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        token = _user_token(test_client, db_session, "pay_customer@example.com")
        cid = str(_create_company(test_client, token))
        gl = _setup_gl(db_session, uuid.UUID(cid))
        _configure_accounts(test_client, token, cid, gl)
        customer_id = str(uuid.uuid4())

        resp = test_client.post(
            _url(cid, "/payments/customer"),
            json={
                "customer_id": customer_id,
                "payment_method": "BANK_TRANSFER",
                "payment_date": gl["today"].isoformat(),
                "amount": "500.00",
                "currency_code": "USD",
                "bank_account_id": str(gl["bank"].id),
            },
            headers=_auth(token),
        )
        assert resp.status_code == 201, resp.text
        payment = resp.json()["data"]
        assert payment["status"] == "POSTED"
        assert payment["amount_base"] == "500.000000"

        resp = test_client.get(
            _url(cid, f"/payments/customer?customer_id={customer_id}"),
            headers=_auth(token),
        )
        assert resp.status_code == 200
        assert len(resp.json()["data"]) == 1

        resp = test_client.post(
            _url(cid, "/journals"),
            json={
                "journal_type": "STANDARD",
                "posting_source": "MANUAL",
                "posting_date": gl["today"].isoformat(),
                "currency_code": "USD",
                "lines": [
                    {
                        "account_id": str(gl["ar"].id),
                        "debit_amount": "500.00",
                        "credit_amount": "0",
                    },
                    {
                        "account_id": str(gl["bank"].gl_account_id),
                        "debit_amount": "0",
                        "credit_amount": "500.00",
                    },
                ],
            },
            headers=_auth(token),
        )
        assert resp.status_code == 201, resp.text

        # No invoice exists in this API test — allocating against a fabricated
        # id must 404, proving the endpoint round-trips through the real
        # ARTransaction lookup rather than trusting the client blindly.
        resp = test_client.post(
            _url(cid, f"/payments/{payment['id']}/allocate"),
            json={
                "allocation_lines": [
                    {"transaction_id": str(uuid.uuid4()), "amount_foreign": "500.00"}
                ]
            },
            headers=_auth(token),
        )
        assert resp.status_code == 404

    def test_unallocated_payments_lists_posted_payment(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        token = _user_token(test_client, db_session, "pay_unalloc@example.com")
        cid = str(_create_company(test_client, token))
        gl = _setup_gl(db_session, uuid.UUID(cid))
        _configure_accounts(test_client, token, cid, gl)

        resp = test_client.post(
            _url(cid, "/payments/customer"),
            json={
                "customer_id": str(uuid.uuid4()),
                "payment_method": "BANK_TRANSFER",
                "payment_date": gl["today"].isoformat(),
                "amount": "250.00",
                "currency_code": "USD",
                "bank_account_id": str(gl["bank"].id),
            },
            headers=_auth(token),
        )
        assert resp.status_code == 201, resp.text

        resp = test_client.get(_url(cid, "/payments/unallocated"), headers=_auth(token))
        assert resp.status_code == 200
        assert len(resp.json()["data"]) == 1

    def test_cancel_payment(self, test_client: TestClient, db_session: Session) -> None:
        token = _user_token(test_client, db_session, "pay_cancel@example.com")
        cid = str(_create_company(test_client, token))
        gl = _setup_gl(db_session, uuid.UUID(cid))
        _configure_accounts(test_client, token, cid, gl)

        resp = test_client.post(
            _url(cid, "/payments/customer"),
            json={
                "customer_id": str(uuid.uuid4()),
                "payment_method": "CASH",
                "payment_date": gl["today"].isoformat(),
                "amount": "100.00",
                "currency_code": "USD",
                "bank_account_id": str(gl["bank"].id),
            },
            headers=_auth(token),
        )
        payment_id = resp.json()["data"]["id"]

        resp = test_client.post(
            _url(cid, f"/payments/{payment_id}/cancel"),
            json={"reason": "Entered in error"},
            headers=_auth(token),
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["data"]["status"] == "CANCELLED"

    def test_refund_payment(self, test_client: TestClient, db_session: Session) -> None:
        token = _user_token(test_client, db_session, "pay_refund@example.com")
        cid = str(_create_company(test_client, token))
        gl = _setup_gl(db_session, uuid.UUID(cid))
        _configure_accounts(test_client, token, cid, gl)

        resp = test_client.post(
            _url(cid, "/payments/customer"),
            json={
                "customer_id": str(uuid.uuid4()),
                "payment_method": "BANK_TRANSFER",
                "payment_date": gl["today"].isoformat(),
                "amount": "300.00",
                "currency_code": "USD",
                "bank_account_id": str(gl["bank"].id),
            },
            headers=_auth(token),
        )
        payment_id = resp.json()["data"]["id"]

        resp = test_client.post(
            _url(cid, f"/payments/{payment_id}/refund"),
            json={
                "refund_date": gl["today"].isoformat(),
                "amount": "300.00",
                "reason": "Customer requested refund",
                "bank_account_id": str(gl["bank"].id),
            },
            headers=_auth(token),
        )
        assert resp.status_code == 201, resp.text
        assert resp.json()["data"]["amount"] == "300.000000"


class TestSupplierPaymentAndWHT:
    def test_create_supplier_payment_with_wht_and_get_certificate(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        token = _user_token(test_client, db_session, "pay_supplier_wht@example.com")
        cid = str(_create_company(test_client, token))
        gl = _setup_gl(db_session, uuid.UUID(cid))
        _configure_accounts(test_client, token, cid, gl)

        resp = test_client.put(
            _url(cid, "/feature-flags/accounting.taxwithholding.enabled"),
            json={"is_enabled": True},
            headers=_auth(token),
        )
        assert resp.status_code == 200, resp.text

        resp = test_client.post(
            _url(cid, "/payments/supplier"),
            json={
                "supplier_id": str(uuid.uuid4()),
                "payment_method": "BANK_TRANSFER",
                "payment_date": gl["today"].isoformat(),
                "amount": "1000.00",
                "currency_code": "USD",
                "bank_account_id": str(gl["bank"].id),
                "wht_amount": "100.00",
                "wht_payable_account_id": str(gl["wht_payable"].id),
            },
            headers=_auth(token),
        )
        assert resp.status_code == 201, resp.text
        payment = resp.json()["data"]
        assert payment["wht_amount"] == "100.000000"

        resp = test_client.get(
            _url(cid, f"/payments/{payment['id']}/wht-certificate"),
            headers=_auth(token),
        )
        assert resp.status_code == 200, resp.text
        certificate = resp.json()["data"]
        assert certificate["gross_amount"] == "1000.000000"
        assert certificate["net_amount"] == "900.000000"

    def test_supplier_payment_list(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        token = _user_token(test_client, db_session, "pay_supplier_list@example.com")
        cid = str(_create_company(test_client, token))
        gl = _setup_gl(db_session, uuid.UUID(cid))
        _configure_accounts(test_client, token, cid, gl)
        supplier_id = str(uuid.uuid4())

        resp = test_client.post(
            _url(cid, "/payments/supplier"),
            json={
                "supplier_id": supplier_id,
                "payment_method": "BANK_TRANSFER",
                "payment_date": gl["today"].isoformat(),
                "amount": "400.00",
                "currency_code": "USD",
                "bank_account_id": str(gl["bank"].id),
            },
            headers=_auth(token),
        )
        assert resp.status_code == 201, resp.text

        resp = test_client.get(
            _url(cid, f"/payments/supplier?supplier_id={supplier_id}"),
            headers=_auth(token),
        )
        assert resp.status_code == 200
        assert len(resp.json()["data"]) == 1


class TestCrossTenantIsolation:
    def test_payment_not_visible_across_tenants(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        token = _user_token(test_client, db_session, "pay_tenant@example.com")
        cid_a = str(_create_company(test_client, token))
        cid_b = str(_create_company(test_client, token))
        gl = _setup_gl(db_session, uuid.UUID(cid_a))
        _configure_accounts(test_client, token, cid_a, gl)

        resp = test_client.post(
            _url(cid_a, "/payments/customer"),
            json={
                "customer_id": str(uuid.uuid4()),
                "payment_method": "BANK_TRANSFER",
                "payment_date": gl["today"].isoformat(),
                "amount": "150.00",
                "currency_code": "USD",
                "bank_account_id": str(gl["bank"].id),
            },
            headers=_auth(token),
        )
        payment_id = resp.json()["data"]["id"]

        resp = test_client.post(
            _url(cid_b, f"/payments/{payment_id}/cancel"),
            json={"reason": "cross tenant attempt"},
            headers=_auth(token),
        )
        assert resp.status_code == 404
