"""API integration tests for AI ERP Readiness endpoints — Phase 17 (T309).

Tests:
  - GET /events/stream, GET /ai/pl-history, GET /ai/cashflow-history,
    POST /ai/anomaly-report all return 403 FEATURE_DISABLED when
    ``accounting.ai.enabled`` is disabled (the default) for the company
  - All four return 200/201 with real data once the flag is enabled
  - Anomaly report: 404 for a journal entry that does not exist
  - 401 enforcement
  - Cross-tenant isolation for the anomaly-report endpoint

Spec ref: specs/008-accounting-finance/tasks.md T309
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from modules.accounting.dependencies import build_posting_engine
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
    suffix = uuid.uuid4().hex[:8]
    resp = client.post(
        "/api/v1/companies",
        json={
            "legal_name": f"AI Readiness Test Co {suffix}",
            "email": f"contact-{suffix}@ai-readiness-test.example.com",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201, resp.text
    return uuid.UUID(resp.json()["data"]["id"])


def _enable_ai_flag(test_client: TestClient, token: str, cid: str) -> None:
    resp = test_client.put(
        _url(cid, "/feature-flags/accounting.ai.enabled"),
        json={"is_enabled": True},
        headers=_auth(token),
    )
    assert resp.status_code == 200, resp.text


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
    cash = account_repo.create(
        Account(
            company_id=company_id,
            account_code="1000",
            account_name="Cash",
            account_type="ASSET",
            is_cash_account=True,
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
    expense = account_repo.create(
        Account(
            company_id=company_id,
            account_code="5000",
            account_name="Expense",
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
        AccountingConfiguration(company_id=company_id, base_currency_code="USD")
    )

    posting_engine = build_posting_engine(db_session)
    revenue_result = posting_engine.post_direct(
        company_id=company_id,
        journal_type="STANDARD",
        posting_source="MANUAL",
        posting_date=today,
        lines=[
            {
                "account_id": cash.id,
                "debit_amount": Decimal("1000.00"),
                "credit_amount": Decimal("0"),
            },
            {
                "account_id": revenue.id,
                "debit_amount": Decimal("0"),
                "credit_amount": Decimal("1000.00"),
            },
        ],
        currency_code="USD",
        reference="AI-READINESS-REF-001",
    )
    posting_engine.post_direct(
        company_id=company_id,
        journal_type="STANDARD",
        posting_source="MANUAL",
        posting_date=today,
        lines=[
            {
                "account_id": expense.id,
                "debit_amount": Decimal("300.00"),
                "credit_amount": Decimal("0"),
            },
            {
                "account_id": cash.id,
                "debit_amount": Decimal("0"),
                "credit_amount": Decimal("300.00"),
            },
        ],
        currency_code="USD",
    )

    return {
        "cash": cash,
        "revenue": revenue,
        "expense": expense,
        "period": period,
        "today": today,
        "posted_journal_entry_id": revenue_result.journal_entry_id,
    }


_ALL_AI_ENDPOINTS: list[tuple[str, str]] = [
    ("GET", "/events/stream"),
    ("GET", "/ai/pl-history?periods=1"),
    ("GET", "/ai/cashflow-history?periods=1"),
]


class TestUnauthenticated:
    def test_ai_endpoints_require_auth(self, test_client: TestClient) -> None:
        cid = str(uuid.uuid4())
        for method, path in _ALL_AI_ENDPOINTS:
            resp = test_client.request(method, _url(cid, path))
            assert resp.status_code == 401, path
        resp = test_client.post(
            _url(cid, "/ai/anomaly-report"),
            json={"journal_entry_ids": [str(uuid.uuid4())]},
        )
        assert resp.status_code == 401


class TestFeatureFlagGating:
    def test_all_endpoints_403_when_flag_disabled(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        token = _user_token(test_client, db_session, "ai_flag_disabled@example.com")
        cid = str(_create_company(test_client, token))
        gl = _setup_gl(db_session, uuid.UUID(cid))

        for method, path in _ALL_AI_ENDPOINTS:
            resp = test_client.request(method, _url(cid, path), headers=_auth(token))
            assert resp.status_code == 403, path
            assert resp.json()["error"]["code"] == "FEATURE_DISABLED"

        resp = test_client.post(
            _url(cid, "/ai/anomaly-report"),
            json={"journal_entry_ids": [str(gl["posted_journal_entry_id"])]},
            headers=_auth(token),
        )
        assert resp.status_code == 403
        assert resp.json()["error"]["code"] == "FEATURE_DISABLED"

    def test_all_endpoints_200_when_flag_enabled(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        token = _user_token(test_client, db_session, "ai_flag_enabled@example.com")
        cid = str(_create_company(test_client, token))
        gl = _setup_gl(db_session, uuid.UUID(cid))
        _enable_ai_flag(test_client, token, cid)

        for method, path in _ALL_AI_ENDPOINTS:
            resp = test_client.request(method, _url(cid, path), headers=_auth(token))
            assert resp.status_code == 200, (path, resp.text)
            assert resp.json()["data"] is not None

        resp = test_client.post(
            _url(cid, "/ai/anomaly-report"),
            json={"journal_entry_ids": [str(gl["posted_journal_entry_id"])]},
            headers=_auth(token),
        )
        assert resp.status_code == 201, resp.text


class TestGLEventStream:
    def test_stream_includes_posted_entry_with_ml_fields(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        token = _user_token(test_client, db_session, "ai_stream@example.com")
        cid = str(_create_company(test_client, token))
        gl = _setup_gl(db_session, uuid.UUID(cid))
        _enable_ai_flag(test_client, token, cid)

        resp = test_client.get(_url(cid, "/events/stream"), headers=_auth(token))
        assert resp.status_code == 200, resp.text
        rows = resp.json()["data"]
        assert len(rows) == 2
        row = next(
            r
            for r in rows
            if r["journal_entry_id"] == str(gl["posted_journal_entry_id"])
        )
        assert row["journal_type"] == "STANDARD"
        assert row["posting_source"] == "MANUAL"
        assert row["reference"] == "AI-READINESS-REF-001"
        assert row["total_debit_base"] == "1000.000000"
        assert row["total_credit_base"] == "1000.000000"

    def test_stream_from_filter_excludes_earlier_entries(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        token = _user_token(test_client, db_session, "ai_stream_from@example.com")
        cid = str(_create_company(test_client, token))
        _setup_gl(db_session, uuid.UUID(cid))
        _enable_ai_flag(test_client, token, cid)

        future_date = date(date.today().year + 1, 1, 1)
        resp = test_client.get(
            _url(cid, f"/events/stream?from={future_date.isoformat()}"),
            headers=_auth(token),
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["data"] == []


class TestPLAndCashFlowHistory:
    def test_pl_history_reflects_posted_activity(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        token = _user_token(test_client, db_session, "ai_pl_history@example.com")
        cid = str(_create_company(test_client, token))
        _setup_gl(db_session, uuid.UUID(cid))
        _enable_ai_flag(test_client, token, cid)

        resp = test_client.get(
            _url(cid, "/ai/pl-history?periods=1"), headers=_auth(token)
        )
        assert resp.status_code == 200, resp.text
        periods = resp.json()["data"]
        assert len(periods) == 1
        assert periods[0]["total_revenue"] == "1000.000000"
        assert periods[0]["total_expense"] == "300.000000"
        assert periods[0]["net_income"] == "700.000000"

    def test_cashflow_history_reflects_posted_activity(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        token = _user_token(test_client, db_session, "ai_cashflow_history@example.com")
        cid = str(_create_company(test_client, token))
        _setup_gl(db_session, uuid.UUID(cid))
        _enable_ai_flag(test_client, token, cid)

        resp = test_client.get(
            _url(cid, "/ai/cashflow-history?periods=1"), headers=_auth(token)
        )
        assert resp.status_code == 200, resp.text
        periods = resp.json()["data"]
        assert len(periods) == 1
        assert periods[0]["net_income"] == "700.000000"
        assert periods[0]["net_change_in_cash"] == "700.000000"


class TestAnomalyReport:
    def test_flag_posted_entry_and_reject_unknown_entry(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        token = _user_token(test_client, db_session, "ai_anomaly@example.com")
        cid = str(_create_company(test_client, token))
        gl = _setup_gl(db_session, uuid.UUID(cid))
        _enable_ai_flag(test_client, token, cid)

        resp = test_client.post(
            _url(cid, "/ai/anomaly-report"),
            json={
                "journal_entry_ids": [str(gl["posted_journal_entry_id"])],
                "reason": "Unusual amount vs 90-day account average",
            },
            headers=_auth(token),
        )
        assert resp.status_code == 201, resp.text
        flags = resp.json()["data"]
        assert len(flags) == 1
        assert flags[0]["journal_entry_id"] == str(gl["posted_journal_entry_id"])
        assert flags[0]["status"] == "OPEN"
        assert flags[0]["reason"] == "Unusual amount vs 90-day account average"

        resp = test_client.post(
            _url(cid, "/ai/anomaly-report"),
            json={"journal_entry_ids": [str(uuid.uuid4())]},
            headers=_auth(token),
        )
        assert resp.status_code == 404


class TestCrossTenantIsolation:
    def test_anomaly_report_rejects_cross_tenant_journal_entry(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        token = _user_token(test_client, db_session, "ai_tenant@example.com")
        cid_a = str(_create_company(test_client, token))
        cid_b = str(_create_company(test_client, token))
        gl_a = _setup_gl(db_session, uuid.UUID(cid_a))
        _enable_ai_flag(test_client, token, cid_b)

        resp = test_client.post(
            _url(cid_b, "/ai/anomaly-report"),
            json={"journal_entry_ids": [str(gl_a["posted_journal_entry_id"])]},
            headers=_auth(token),
        )
        assert resp.status_code == 404
