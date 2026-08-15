"""End-to-end integration test: full Sales-to-Cash workflow — Phase 16 (T295).

Drives the real, live cross-module path documented in
``modules/accounting/handlers/integration_handlers.py``:
``sales.invoice.issued`` (published on Sales's own event bus) ->
``handle_sales_invoice_posted`` -> ``AccountsReceivableService.
record_sales_invoice()`` -> DR AR / CR Revenue posted to the GL and an
OPEN ``ARTransaction`` created, atomically -> customer payment recorded via
``POST /payments/customer`` -> allocated against the invoice via
``POST /payments/{id}/allocate`` -> AR outstanding verified at zero ->
GL verified via ``AccountsReceivableService.reconcile_ar_control_account()``.

This closes a gap flagged during Phase 16 research: no existing Phase 6/10
test exercises the full invoice -> payment -> allocate -> zero-balance path
against a REAL seeded AR transaction created via the live event bus (Phase
6/10's own tests either bypass the event bus entirely — calling
``ar_service.record_sales_invoice()`` directly — or allocate against a
fabricated transaction id that 404s by design).

Two test-only workarounds are required to exercise the real event path
under the SQLite in-memory test harness (neither touches production code):

1. ``modules.sales.events.get_event_bus()`` returns a process-wide module
   singleton. ``register_integration_handlers()`` runs on every
   ``test_client`` fixture instantiation (via ``main.py``'s lifespan) and
   only ever *appends* subscriptions — never clears them. Left alone, a
   test running later in the same pytest session would see its published
   event dispatch to N accumulated duplicate handler registrations from
   earlier tests. We call ``clear_handlers()`` then ``register_integration_
   handlers()`` once at the top of this test to guarantee exactly one
   subscription regardless of execution order.

2. ``handle_sales_invoice_posted`` opens its own ``SessionLocal()`` (real
   production pattern — event handlers run outside any request's DI scope,
   so they cannot receive the test's overridden ``get_db``). ``SessionLocal``
   is bound to the dummy/unreachable ``DATABASE_URL`` conftest.py sets for
   module-import purposes only — a real connection attempt would fail
   silently (swallowed by ``SalesEventBus.publish()``'s own try/except) and
   the AR transaction would simply never appear. We monkeypatch
   ``SessionLocal`` inside the handler module to return the test's own
   ``db_session`` (wrapped so the handler's ``finally: db.close()`` doesn't
   tear down the shared test session), so the handler observes the exact
   same in-memory database this test set up.

Spec ref: specs/008-accounting-finance/tasks.md T295
"""

from __future__ import annotations

import uuid
from datetime import date, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from modules.accounting.dependencies import build_ar_service
from modules.accounting.models.banking import BankAccount
from modules.accounting.models.coa import Account
from modules.accounting.models.foundation import AccountingConfiguration
from modules.accounting.repositories.ar import ARTransactionRepository
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
    return resp.json()["data"]["access_token"]


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
            "legal_name": f"S2C Test Co {suffix}",
            "email": f"contact-{suffix}@s2c-test.example.com",
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
            account_number="ACC-S2C-0001",
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
            default_ar_account_id=ar.id,
            default_revenue_account_id=revenue.id,
        )
    )
    return {
        "ar": ar,
        "revenue": revenue,
        "bank_gl": bank_gl,
        "bank_account": bank_account,
        "today": today,
    }


class _NoCloseSession:
    """Delegates everything to a shared Session except ``close()``, which is
    a no-op — lets a production ``finally: db.close()`` run against the
    test's rollback-scoped ``db_session`` without tearing it down early."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def __getattr__(self, name: str) -> object:
        return getattr(self._session, name)

    def close(self) -> None:
        pass


def _wire_live_sales_invoice_handler(
    monkeypatch: pytest.MonkeyPatch, db_session: Session
) -> None:
    """Guarantee exactly one live subscription on Sales's real event bus,
    and make its handler observe this test's own in-memory DB (see module
    docstring, points 1 and 2)."""
    from modules.accounting.handlers import integration_handlers as handlers_module
    from modules.sales.events import get_event_bus as get_sales_event_bus

    get_sales_event_bus().clear_handlers()
    monkeypatch.setattr(
        handlers_module, "SessionLocal", lambda: _NoCloseSession(db_session)
    )
    handlers_module.register_integration_handlers()


class TestSalesToCashE2E:
    def test_invoice_to_zero_balance_full_flow(
        self,
        test_client: TestClient,
        db_session: Session,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        token = _user_token(test_client, db_session, "s2c_full@example.com")
        cid = _create_company(test_client, token)
        gl = _setup_gl(db_session, cid)
        _wire_live_sales_invoice_handler(monkeypatch, db_session)

        # --- Step 1: Sales publishes a real sales.invoice.issued event ---
        from modules.sales.events import get_event_bus as get_sales_event_bus
        from modules.sales.events.invoice_events import InvoiceIssued

        customer_id = uuid.uuid4()
        invoice_id = uuid.uuid4()
        due_date = gl["today"] + timedelta(days=30)
        get_sales_event_bus().publish(
            InvoiceIssued(
                aggregate_id=invoice_id,
                company_id=cid,
                invoice_id=invoice_id,
                invoice_number="INV-S2C-001",
                customer_id=str(customer_id),
                due_date=due_date.isoformat(),
                total_amount="1000.00",
                currency_code="USD",
                issued_by=str(uuid.uuid4()),
            )
        )

        # --- Step 2: AR was created and posted to the GL ---
        resp = test_client.get(
            _url(str(cid), f"/ar/customer-ledger/{customer_id}"), headers=_auth(token)
        )
        assert resp.status_code == 200, resp.text
        ledger = resp.json()["data"]
        assert ledger["total_outstanding_base"] == "1000.000000"
        assert ledger["credit_status"] == "GOOD"

        ar_service = build_ar_service(db_session, with_sales_sync=False)
        assert ar_service.reconcile_ar_control_account(cid) == Decimal("1000")

        # --- Step 3: customer payment recorded (DR Bank / CR AR) ---
        resp = test_client.post(
            _url(str(cid), "/payments/customer"),
            json={
                "customer_id": str(customer_id),
                "payment_method": "BANK_TRANSFER",
                "payment_date": gl["today"].isoformat(),
                "amount": "1000.00",
                "currency_code": "USD",
                "bank_account_id": str(gl["bank_account"].id),
            },
            headers=_auth(token),
        )
        assert resp.status_code == 201, resp.text
        payment = resp.json()["data"]
        assert payment["status"] == "POSTED"

        # --- Step 4: allocate the payment against the real invoice ---
        ar_transaction = ARTransactionRepository(db_session).find_by_source_document(
            company_id=cid,
            source_document_type="SalesInvoice",
            source_document_id=invoice_id,
        )
        assert ar_transaction is not None
        assert ar_transaction.outstanding_amount == Decimal("1000")

        resp = test_client.post(
            _url(str(cid), f"/payments/{payment['id']}/allocate"),
            json={
                "allocation_lines": [
                    {
                        "transaction_id": str(ar_transaction.id),
                        "amount_foreign": "1000.00",
                    }
                ]
            },
            headers=_auth(token),
        )
        assert resp.status_code == 201, resp.text

        # --- Step 5: AR outstanding is zero, GL control account reconciles ---
        resp = test_client.get(
            _url(str(cid), f"/ar/customer-ledger/{customer_id}"), headers=_auth(token)
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["data"]["total_outstanding_base"] == "0.000000"

        db_session.refresh(ar_transaction)
        assert ar_transaction.outstanding_amount == Decimal("0")
        assert ar_transaction.status == "PAID"

        assert ar_service.reconcile_ar_control_account(cid) == Decimal("0")

    def test_unconfigured_company_invoice_silently_fails_to_post(
        self,
        test_client: TestClient,
        db_session: Session,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Documents the failure semantics noted in integration_handlers.py:
        if default AR/Revenue accounts aren't configured, the handler raises
        internally but ``SalesEventBus.publish()`` swallows it — Sales's own
        flow is unaffected, and no ARTransaction/GL entry is ever created."""
        token = _user_token(test_client, db_session, "s2c_unconfigured@example.com")
        cid = _create_company(test_client, token)
        # No _setup_gl() call — accounting configuration intentionally absent.
        _wire_live_sales_invoice_handler(monkeypatch, db_session)

        from modules.sales.events import get_event_bus as get_sales_event_bus
        from modules.sales.events.invoice_events import InvoiceIssued

        customer_id = uuid.uuid4()
        invoice_id = uuid.uuid4()
        get_sales_event_bus().publish(
            InvoiceIssued(
                aggregate_id=invoice_id,
                company_id=cid,
                invoice_id=invoice_id,
                invoice_number="INV-S2C-002",
                customer_id=str(customer_id),
                due_date=(date.today() + timedelta(days=30)).isoformat(),
                total_amount="500.00",
                currency_code="USD",
                issued_by=str(uuid.uuid4()),
            )
        )

        resp = test_client.get(
            _url(str(cid), f"/ar/customer-ledger/{customer_id}"), headers=_auth(token)
        )
        assert resp.status_code == 404
