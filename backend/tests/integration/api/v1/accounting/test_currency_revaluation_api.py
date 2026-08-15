"""API integration tests for Currency Revaluation endpoints — Phase 12.

Tests (tasks.md T251):
  - POST /currency-revaluation runs a revaluation and returns the report
  - GET /currency-revaluation/history lists past runs
  - GET /currency-revaluation/{id}/report retrieves one run
  - 401 enforcement
  - Cross-tenant isolation
  - 404 for an unknown run id

Spec ref: specs/008-accounting-finance/tasks.md T251
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from modules.accounting.models.ar import ARTransaction, CustomerLedger
from modules.accounting.models.coa import Account
from modules.accounting.models.foundation import AccountingConfiguration
from modules.accounting.repositories.ar import (
    ARTransactionRepository,
    CustomerLedgerRepository,
)
from modules.accounting.repositories.coa import AccountRepository
from modules.accounting.repositories.fiscal import (
    FiscalPeriodRepository,
    FiscalYearRepository,
    OpeningBalanceRepository,
)
from modules.accounting.repositories.foundation import AccountingConfigurationRepository
from modules.accounting.repositories.gl import AccountingAuditLogRepository
from modules.accounting.services.audit_service import AuditLogService
from modules.accounting.services.currency_service import CurrencyService
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
            "legal_name": f"Reval Test Co {suffix}",
            "email": f"contact-{suffix}@reval-test.example.com",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201, resp.text
    return uuid.UUID(resp.json()["data"]["id"])


def _setup(db_session: Session, company_id: uuid.UUID) -> dict:
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
    exchange_gain = account_repo.create(
        Account(
            company_id=company_id,
            account_code="7100",
            account_name="Unrealized Exchange Gain",
            account_type="REVENUE",
        )
    )
    exchange_loss = account_repo.create(
        Account(
            company_id=company_id,
            account_code="8100",
            account_name="Unrealized Exchange Loss",
            account_type="EXPENSE",
        )
    )

    today = date.today()
    fiscal_year = fiscal_service.create_fiscal_year(
        company_id,
        f"FY-{uuid.uuid4().hex[:8]}",
        date(today.year, 1, 1),
        date(today.year, 12, 31),
        "USD",
    )
    period = next(
        p
        for p in fiscal_service.list_periods(company_id, fiscal_year.id)
        if p.start_date <= today <= p.end_date
    )

    AccountingConfigurationRepository(db_session).create(
        AccountingConfiguration(
            company_id=company_id,
            base_currency_code="USD",
            default_ar_account_id=ar.id,
            default_exchange_gain_account_id=exchange_gain.id,
            default_exchange_loss_account_id=exchange_loss.id,
        )
    )

    ledger = CustomerLedgerRepository(db_session).create(
        CustomerLedger(company_id=company_id, customer_id=uuid.uuid4())
    )
    ARTransactionRepository(db_session).create(
        ARTransaction(
            company_id=company_id,
            customer_ledger_id=ledger.id,
            transaction_type="INVOICE",
            transaction_date=today,
            currency_code="EUR",
            exchange_rate=Decimal("1.10"),
            amount_foreign=Decimal("1000.00"),
            amount_base=Decimal("1100.00"),
            outstanding_amount=Decimal("1100.00"),
            status="OPEN",
            invoice_number="INV-API-001",
        )
    )

    from modules.accounting.repositories.foundation import (
        CurrencyRepository,
        ExchangeRateRepository,
    )

    CurrencyService(
        db=db_session,
        currency_repo=CurrencyRepository(db_session),
        exchange_rate_repo=ExchangeRateRepository(db_session),
    ).set_exchange_rate(company_id, "EUR", "USD", today, Decimal("1.15"))

    return {"period": period, "today": today}


class TestUnauthenticated:
    def test_run_revaluation_requires_auth(self, test_client: TestClient) -> None:
        resp = test_client.post(
            _url(str(uuid.uuid4()), "/currency-revaluation"),
            json={
                "fiscal_period_id": str(uuid.uuid4()),
                "revaluation_date": "2026-01-31",
            },
        )
        assert resp.status_code == 401

    def test_history_requires_auth(self, test_client: TestClient) -> None:
        resp = test_client.get(_url(str(uuid.uuid4()), "/currency-revaluation/history"))
        assert resp.status_code == 401


class TestRunRevaluation:
    def test_run_revaluation_returns_gain_and_history_shows_it(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        token = _user_token(test_client, db_session, "reval_run@example.com")
        cid = str(_create_company(test_client, token))
        ctx = _setup(db_session, uuid.UUID(cid))

        resp = test_client.post(
            _url(cid, "/currency-revaluation"),
            json={
                "fiscal_period_id": str(ctx["period"].id),
                "revaluation_date": ctx["today"].isoformat(),
            },
            headers=_auth(token),
        )
        assert resp.status_code == 201, resp.text
        data = resp.json()["data"]
        assert data["total_unrealized_gain_base"] == "50.000000"
        assert data["journal_entry_id"] is not None
        assert len(data["lines"]) == 1
        run_id = data["id"]

        resp = test_client.get(
            _url(cid, "/currency-revaluation/history"), headers=_auth(token)
        )
        assert resp.status_code == 200
        assert len(resp.json()["data"]) == 1
        assert resp.json()["data"][0]["id"] == run_id

        resp = test_client.get(
            _url(cid, f"/currency-revaluation/{run_id}/report"), headers=_auth(token)
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["net_gain_loss_base"] == "50.000000"

    def test_unknown_period_returns_404(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        token = _user_token(test_client, db_session, "reval_404@example.com")
        cid = str(_create_company(test_client, token))
        resp = test_client.post(
            _url(cid, "/currency-revaluation"),
            json={
                "fiscal_period_id": str(uuid.uuid4()),
                "revaluation_date": "2026-01-31",
            },
            headers=_auth(token),
        )
        assert resp.status_code == 404

    def test_unknown_revaluation_report_returns_404(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        token = _user_token(test_client, db_session, "reval_report_404@example.com")
        cid = str(_create_company(test_client, token))
        resp = test_client.get(
            _url(cid, f"/currency-revaluation/{uuid.uuid4()}/report"),
            headers=_auth(token),
        )
        assert resp.status_code == 404


class TestCrossTenantIsolation:
    def test_revaluation_run_not_visible_across_tenants(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        token = _user_token(test_client, db_session, "reval_tenant@example.com")
        cid_a = str(_create_company(test_client, token))
        cid_b = str(_create_company(test_client, token))
        ctx = _setup(db_session, uuid.UUID(cid_a))

        resp = test_client.post(
            _url(cid_a, "/currency-revaluation"),
            json={
                "fiscal_period_id": str(ctx["period"].id),
                "revaluation_date": ctx["today"].isoformat(),
            },
            headers=_auth(token),
        )
        run_id = resp.json()["data"]["id"]

        resp = test_client.get(
            _url(cid_b, f"/currency-revaluation/{run_id}/report"), headers=_auth(token)
        )
        assert resp.status_code == 404
