"""End-to-end smoke test — Phase 18 (T316).

Exercises the full literal sequence tasks.md T316 specifies: create company
-> configure accounting -> set up COA from the Retail template -> create
fiscal year -> post manual journal -> verify GL -> post sales invoice event
-> verify AR -> process payment -> verify zero balance -> generate balance
sheet -> verify the accounting equation holds.

Unlike the narrower Phase 16 E2E tests (test_e2e_sales_to_cash.py, etc.),
this is the single continuous "does the whole module work end to end for a
brand-new company, using nothing but its own APIs to configure itself"
check — the exact kind of test spec.md §65.10 calls a fully-tested
"migration"/onboarding path.

Spec ref: specs/008-accounting-finance/tasks.md T316
"""

from __future__ import annotations

import uuid
from datetime import date, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

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


def _account_id_by_code(
    test_client: TestClient, token: str, cid: str, code: str
) -> str:
    resp = test_client.get(_url(cid, "/accounts"), headers=_auth(token))
    assert resp.status_code == 200, resp.text
    accounts = {a["account_code"]: a["id"] for a in resp.json()["data"]}
    assert code in accounts, f"account code {code} not found in COA: {sorted(accounts)}"
    return str(accounts[code])


class _NoCloseSession:
    """See test_e2e_sales_to_cash.py's identical helper — lets the live
    Sales-invoice-posted handler's ``finally: db.close()`` run against the
    test's rollback-scoped ``db_session`` without tearing it down early."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def __getattr__(self, name: str) -> object:
        return getattr(self._session, name)

    def close(self) -> None:
        pass


class TestFullLifecycleSmoke:
    def test_company_onboarding_through_balance_sheet(
        self,
        test_client: TestClient,
        db_session: Session,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # --- Step 1: create company ---
        user, pw = create_test_user(
            db_session, email="smoke_full_lifecycle@example.com"
        )
        token = _login(test_client, user.email, pw)
        suffix = uuid.uuid4().hex[:8]
        resp = test_client.post(
            "/api/v1/companies",
            json={
                "legal_name": f"Smoke Test Retail Co {suffix}",
                "email": f"contact-{suffix}@smoke-test.example.com",
            },
            headers=_auth(token),
        )
        assert resp.status_code == 201, resp.text
        cid = resp.json()["data"]["id"]

        # --- Step 2: configure accounting (base currency) ---
        resp = test_client.put(
            _url(cid, "/configuration"),
            json={"base_currency_code": "USD"},
            headers=_auth(token),
        )
        assert resp.status_code == 200, resp.text

        # --- Step 3: set up COA from the Retail template ---
        resp = test_client.post(
            _url(cid, "/coa-templates/apply"),
            json={"template_key": "RETAIL"},
            headers=_auth(token),
        )
        assert resp.status_code == 200, resp.text

        cash_id = _account_id_by_code(test_client, token, cid, "1000")
        ar_id = _account_id_by_code(test_client, token, cid, "1100")
        equity_id = _account_id_by_code(test_client, token, cid, "3000")
        revenue_id = _account_id_by_code(test_client, token, cid, "4000")

        for role, account_id in (
            ("default_ar_account_id", ar_id),
            ("default_revenue_account_id", revenue_id),
        ):
            resp = test_client.put(
                _url(cid, "/system-accounts"),
                json={"role": role, "account_id": account_id},
                headers=_auth(token),
            )
            assert resp.status_code == 200, resp.text

        # --- Step 4: create fiscal year ---
        today = date.today()
        resp = test_client.post(
            _url(cid, "/fiscal-years"),
            json={
                "fiscal_year_name": f"FY-SMOKE-{suffix}",
                "start_date": date(today.year, 1, 1).isoformat(),
                "end_date": date(today.year, 12, 31).isoformat(),
                "base_currency_code": "USD",
            },
            headers=_auth(token),
        )
        assert resp.status_code == 201, resp.text

        # --- Step 5: post a manual journal (owner's capital injection) ---
        resp = test_client.post(
            _url(cid, "/journals"),
            json={
                "journal_type": "STANDARD",
                "posting_source": "MANUAL",
                "posting_date": today.isoformat(),
                "currency_code": "USD",
                "reference": "SMOKE-CAPITAL-001",
                "lines": [
                    {
                        "account_id": cash_id,
                        "debit_amount": "20000.00",
                        "credit_amount": "0",
                    },
                    {
                        "account_id": equity_id,
                        "debit_amount": "0",
                        "credit_amount": "20000.00",
                    },
                ],
            },
            headers=_auth(token),
        )
        assert resp.status_code == 201, resp.text
        journal_id = resp.json()["data"]["id"]
        resp = test_client.post(
            _url(cid, f"/journals/{journal_id}/post"), headers=_auth(token)
        )
        assert resp.status_code == 200, resp.text

        # --- Step 6: verify GL ---
        resp = test_client.get(_url(cid, "/reports/gl"), headers=_auth(token))
        assert resp.status_code == 200, resp.text
        gl_rows = resp.json()["data"]
        assert any(
            r["account_id"] == cash_id and r["debit_amount"] == "20000.000000"
            for r in gl_rows
        )
        assert any(
            r["account_id"] == equity_id and r["credit_amount"] == "20000.000000"
            for r in gl_rows
        )

        # --- Step 7: post a real sales.invoice.issued event ---
        from modules.accounting.handlers import integration_handlers as handlers_module
        from modules.sales.events import get_event_bus as get_sales_event_bus
        from modules.sales.events.invoice_events import InvoiceIssued

        get_sales_event_bus().clear_handlers()
        monkeypatch.setattr(
            handlers_module, "SessionLocal", lambda: _NoCloseSession(db_session)
        )
        handlers_module.register_integration_handlers()

        customer_id = uuid.uuid4()
        invoice_id = uuid.uuid4()
        get_sales_event_bus().publish(
            InvoiceIssued(
                aggregate_id=invoice_id,
                company_id=uuid.UUID(cid),
                invoice_id=invoice_id,
                invoice_number="SMOKE-INV-001",
                customer_id=str(customer_id),
                due_date=(today + timedelta(days=30)).isoformat(),
                total_amount="1500.00",
                currency_code="USD",
                issued_by=str(uuid.uuid4()),
            )
        )

        # --- Step 8: verify AR ---
        resp = test_client.get(
            _url(cid, f"/ar/customer-ledger/{customer_id}"), headers=_auth(token)
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["data"]["total_outstanding_base"] == "1500.000000"

        # --- Step 9: process payment ---
        resp = test_client.post(
            _url(cid, "/cash-accounts"),
            json={
                "account_name": "Petty Cash",
                "currency_code": "USD",
                "gl_account_id": cash_id,
            },
            headers=_auth(token),
        )
        assert resp.status_code == 201, resp.text
        cash_account_id = resp.json()["data"]["id"]

        resp = test_client.post(
            _url(cid, "/payments/customer"),
            json={
                "customer_id": str(customer_id),
                "payment_method": "CASH",
                "payment_date": today.isoformat(),
                "amount": "1500.00",
                "currency_code": "USD",
                "cash_account_id": cash_account_id,
            },
            headers=_auth(token),
        )
        assert resp.status_code == 201, resp.text
        payment = resp.json()["data"]

        from modules.accounting.repositories.ar import ARTransactionRepository

        ar_transaction = ARTransactionRepository(db_session).find_by_source_document(
            company_id=uuid.UUID(cid),
            source_document_type="SalesInvoice",
            source_document_id=invoice_id,
        )
        assert ar_transaction is not None
        resp = test_client.post(
            _url(cid, f"/payments/{payment['id']}/allocate"),
            json={
                "allocation_lines": [
                    {
                        "transaction_id": str(ar_transaction.id),
                        "amount_foreign": "1500.00",
                    }
                ]
            },
            headers=_auth(token),
        )
        assert resp.status_code == 201, resp.text

        # --- Step 10: verify zero AR balance ---
        resp = test_client.get(
            _url(cid, f"/ar/customer-ledger/{customer_id}"), headers=_auth(token)
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["data"]["total_outstanding_base"] == "0.000000"

        # --- Step 11: generate balance sheet, verify the equation holds ---
        resp = test_client.get(
            _url(cid, f"/reports/balance-sheet?as_of_date={today.isoformat()}"),
            headers=_auth(token),
        )
        assert resp.status_code == 200, resp.text
        bs = resp.json()["data"]
        assert bs["is_balanced"] is True
        total_assets = Decimal(bs["total_assets"])
        total_liabilities = Decimal(bs["total_liabilities"])
        total_equity = Decimal(bs["total_equity"])
        assert total_assets == total_liabilities + total_equity
        # Cash 20000 (capital) + Cash 1500 (payment received) - AR 0 = 21500 total assets.
        assert total_assets == Decimal("21500.00")
