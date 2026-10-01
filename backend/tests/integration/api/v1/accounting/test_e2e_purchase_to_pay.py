"""End-to-end integration test: full Purchase-to-Pay workflow — Phase 16 (T296).

Confirmed during Phase 0/7 (quickstart.md "Phase 0 Verification Findings",
``modules/accounting/services/ap_service.py`` module docstring): Purchase
(Epic 6) has no Bill/Invoice/AP entity or `purchase.bill.posted` event at
all (spec 006 §60.2 explicitly defers Invoice Processing/Three-Way Matching/
Accounts Payable to Epic 8's own future scope). There is therefore no event
to publish here, unlike T295's Sales-to-Cash flow — the "Purchase -> Bill"
half of this workflow is Accounting's own bill-capture endpoint
(``POST /ap/bills``, built directly on ``AccountsPayableService.
record_supplier_bill()``), the already-resolved substitute for a live
Purchase event per ADR-0004/quickstart.md.

Flow under test: bill captured (DR Expense / CR AP + OPEN APTransaction,
atomically) -> supplier payment recorded (DR AP / CR Bank) -> allocated
against the bill -> AP outstanding verified at zero -> GL control account
reconciled via ``AccountsPayableService.reconcile_ap_control_account()``.

Spec ref: specs/008-accounting-finance/tasks.md T296
"""

from __future__ import annotations

import uuid
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from modules.accounting.dependencies import build_ap_service
from modules.accounting.models.banking import BankAccount
from modules.accounting.models.coa import Account
from modules.accounting.models.foundation import AccountingConfiguration
from modules.accounting.repositories.banking import BankAccountRepository
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
    suffix = uuid.uuid4().hex[:8]
    resp = client.post(
        "/api/v1/companies",
        json={
            "legal_name": f"P2P Test Co {suffix}",
            "email": f"contact-{suffix}@p2p-test.example.com",
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
            account_code="2000",
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
    bank_gl = account_repo.create(
        Account(
            company_id=company_id,
            account_code="1000",
            account_name="Bank",
            account_type="ASSET",
        )
    )
    bank_account = BankAccountRepository(db_session).create(
        BankAccount(
            company_id=company_id,
            bank_name="Test Bank",
            account_number="ACC-P2P-0001",
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
    AccountingConfigurationRepository(db_session).create(
        AccountingConfiguration(
            company_id=company_id,
            base_currency_code="USD",
            default_ap_account_id=ap.id,
            default_expense_account_id=expense.id,
        )
    )
    return {
        "ap": ap,
        "expense": expense,
        "bank_gl": bank_gl,
        "bank_account": bank_account,
        "today": today,
    }


class TestPurchaseToPayE2E:
    def test_bill_to_zero_balance_full_flow(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        token = _user_token(test_client, db_session, "p2p_full@example.com")
        cid = _create_company(test_client, token)
        gl = _setup_gl(db_session, cid)
        supplier_id = uuid.uuid4()

        # --- Step 1: bill captured (Accounting-native AP entry point) ---
        resp = test_client.post(
            _url(str(cid), "/ap/bills"),
            json={
                "supplier_id": str(supplier_id),
                "bill_number": "BILL-P2P-001",
                "total_amount": "750.00",
                "currency_code": "USD",
                "transaction_date": gl["today"].isoformat(),
                "due_date": (gl["today"] + timedelta(days=30)).isoformat(),
            },
            headers=_auth(token),
        )
        assert resp.status_code == 201, resp.text
        bill = resp.json()["data"]
        assert bill["status"] == "OPEN"
        assert bill["outstanding_amount"] == "750.000000"
        ap_transaction_id = bill["id"]

        # --- Step 2: AP subsidiary ledger reflects the bill ---
        resp = test_client.get(
            _url(str(cid), f"/ap/supplier-ledger/{supplier_id}"), headers=_auth(token)
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["data"]["total_outstanding_base"] == "750.000000"

        ap_service = build_ap_service(db_session)
        assert ap_service.reconcile_ap_control_account(cid) == Decimal("750")

        # --- Step 3: supplier payment recorded (DR AP / CR Bank) ---
        resp = test_client.post(
            _url(str(cid), "/payments/supplier"),
            json={
                "supplier_id": str(supplier_id),
                "payment_method": "BANK_TRANSFER",
                "payment_date": gl["today"].isoformat(),
                "amount": "750.00",
                "currency_code": "USD",
                "bank_account_id": str(gl["bank_account"].id),
            },
            headers=_auth(token),
        )
        assert resp.status_code == 201, resp.text
        payment = resp.json()["data"]
        assert payment["status"] == "POSTED"

        # --- Step 4: allocate the payment against the real bill ---
        resp = test_client.post(
            _url(str(cid), f"/payments/{payment['id']}/allocate"),
            json={
                "allocation_lines": [
                    {"transaction_id": ap_transaction_id, "amount_foreign": "750.00"}
                ]
            },
            headers=_auth(token),
        )
        assert resp.status_code == 201, resp.text

        # --- Step 5: AP outstanding is zero, GL control account reconciles ---
        resp = test_client.get(
            _url(str(cid), f"/ap/supplier-ledger/{supplier_id}"), headers=_auth(token)
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["data"]["total_outstanding_base"] == "0.000000"

        assert ap_service.reconcile_ap_control_account(cid) == Decimal("0")

    def test_credit_note_reduces_outstanding_payable(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        token = _user_token(test_client, db_session, "p2p_creditnote@example.com")
        cid = _create_company(test_client, token)
        gl = _setup_gl(db_session, cid)
        supplier_id = uuid.uuid4()

        resp = test_client.post(
            _url(str(cid), "/ap/bills"),
            json={
                "supplier_id": str(supplier_id),
                "bill_number": "BILL-P2P-002",
                "total_amount": "400.00",
                "currency_code": "USD",
                "transaction_date": gl["today"].isoformat(),
            },
            headers=_auth(token),
        )
        assert resp.status_code == 201, resp.text
        bill_id = resp.json()["data"]["source_document_id"]

        resp = test_client.post(
            _url(str(cid), "/ap/credit-notes"),
            json={
                "supplier_id": str(supplier_id),
                "bill_id": bill_id,
                "bill_number": "BILL-P2P-002",
                "credit_amount": "150.00",
                "transaction_date": gl["today"].isoformat(),
            },
            headers=_auth(token),
        )
        assert resp.status_code == 201, resp.text

        resp = test_client.get(
            _url(str(cid), f"/ap/supplier-ledger/{supplier_id}"), headers=_auth(token)
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["data"]["total_outstanding_base"] == "250.000000"

        ap_service = build_ap_service(db_session)
        assert ap_service.reconcile_ap_control_account(cid) == Decimal("250")
