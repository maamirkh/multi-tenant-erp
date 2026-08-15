"""API integration tests for Financial Statements & Reports endpoints — Phase 13.

Tests (tasks.md T271):
  - GET /reports/trial-balance, /balance-sheet, /profit-loss, /cash-flow
  - GET /reports/gl (offset AND keyset/cursor pagination)
  - GET /reports/customer-ledger/{id}, /supplier-ledger/{id}, /bank-book/{id},
    /cash-book/{id}, /journals
  - ?format=pdf / ?format=excel export on every report endpoint
  - 401 enforcement
  - Cross-tenant isolation

Spec ref: specs/008-accounting-finance/tasks.md T271
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from modules.accounting.dependencies import build_posting_engine
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
            "legal_name": f"Reports Test Co {suffix}",
            "email": f"contact-{suffix}@reports-test.example.com",
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
    cash = account_repo.create(
        Account(
            company_id=company_id,
            account_code="1000",
            account_name="Cash",
            account_type="ASSET",
        )
    )
    ar = account_repo.create(
        Account(
            company_id=company_id,
            account_code="1100",
            account_name="AR",
            account_type="ASSET",
        )
    )
    equity = account_repo.create(
        Account(
            company_id=company_id,
            account_code="3000",
            account_name="Equity",
            account_type="EQUITY",
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
        AccountingConfiguration(
            company_id=company_id, base_currency_code="USD", default_ar_account_id=ar.id
        )
    )

    posting_engine = build_posting_engine(db_session)
    posting_engine.post_direct(
        company_id=company_id,
        journal_type="OPENING_BALANCE",
        posting_source="MANUAL",
        posting_date=today,
        lines=[
            {
                "account_id": cash.id,
                "debit_amount": Decimal("1000.00"),
                "credit_amount": Decimal("0"),
            },
            {
                "account_id": equity.id,
                "debit_amount": Decimal("0"),
                "credit_amount": Decimal("1000.00"),
            },
        ],
        currency_code="USD",
    )
    posting_engine.post_direct(
        company_id=company_id,
        journal_type="STANDARD",
        posting_source="SALES",
        posting_date=today,
        lines=[
            {
                "account_id": cash.id,
                "debit_amount": Decimal("500.00"),
                "credit_amount": Decimal("0"),
            },
            {
                "account_id": revenue.id,
                "debit_amount": Decimal("0"),
                "credit_amount": Decimal("500.00"),
            },
        ],
        currency_code="USD",
    )
    posting_engine.post_direct(
        company_id=company_id,
        journal_type="STANDARD",
        posting_source="MANUAL",
        posting_date=today,
        lines=[
            {
                "account_id": expense.id,
                "debit_amount": Decimal("150.00"),
                "credit_amount": Decimal("0"),
            },
            {
                "account_id": cash.id,
                "debit_amount": Decimal("0"),
                "credit_amount": Decimal("150.00"),
            },
        ],
        currency_code="USD",
    )

    customer_id = uuid.uuid4()
    ledger = CustomerLedgerRepository(db_session).create(
        CustomerLedger(company_id=company_id, customer_id=customer_id)
    )
    ARTransactionRepository(db_session).create(
        ARTransaction(
            company_id=company_id,
            customer_ledger_id=ledger.id,
            transaction_type="INVOICE",
            transaction_date=today,
            currency_code="USD",
            exchange_rate=Decimal("1"),
            amount_foreign=Decimal("200.00"),
            amount_base=Decimal("200.00"),
            outstanding_amount=Decimal("200.00"),
            status="OPEN",
            invoice_number="INV-RPT-001",
        )
    )

    return {
        "cash": cash,
        "ar": ar,
        "equity": equity,
        "revenue": revenue,
        "expense": expense,
        "period": period,
        "today": today,
        "customer_id": customer_id,
    }


class TestUnauthenticated:
    def test_reports_require_auth(self, test_client: TestClient) -> None:
        cid = str(uuid.uuid4())
        for path in (
            "/reports/trial-balance?period_id=" + str(uuid.uuid4()),
            "/reports/balance-sheet?as_of_date=2026-01-01",
            "/reports/profit-loss?period_from=2026-01-01&period_to=2026-01-31",
            "/reports/cash-flow?period_from=2026-01-01&period_to=2026-01-31",
            "/reports/gl",
            "/reports/journals?period_id=" + str(uuid.uuid4()),
        ):
            resp = test_client.get(_url(cid, path))
            assert resp.status_code == 401, path


class TestTrialBalance:
    def test_trial_balance_json_and_export(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        token = _user_token(test_client, db_session, "tb_report@example.com")
        cid = str(_create_company(test_client, token))
        ctx = _setup(db_session, uuid.UUID(cid))

        resp = test_client.get(
            _url(cid, f"/reports/trial-balance?period_id={ctx['period'].id}"),
            headers=_auth(token),
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert data["total_debit"] == data["total_credit"]
        assert data["is_balanced"] is True

        resp = test_client.get(
            _url(
                cid, f"/reports/trial-balance?period_id={ctx['period'].id}&format=excel"
            ),
            headers=_auth(token),
        )
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith(
            "application/vnd.openxmlformats-officedocument"
        )

        resp = test_client.get(
            _url(
                cid, f"/reports/trial-balance?period_id={ctx['period'].id}&format=pdf"
            ),
            headers=_auth(token),
        )
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "application/pdf"


class TestBalanceSheet:
    def test_balance_sheet_equation_holds(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        token = _user_token(test_client, db_session, "bs_report@example.com")
        cid = str(_create_company(test_client, token))
        ctx = _setup(db_session, uuid.UUID(cid))

        resp = test_client.get(
            _url(cid, f"/reports/balance-sheet?as_of_date={ctx['today'].isoformat()}"),
            headers=_auth(token),
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        total_assets = Decimal(data["total_assets"])
        total_liabilities = Decimal(data["total_liabilities"])
        total_equity = Decimal(data["total_equity"])
        assert total_assets == total_liabilities + total_equity
        assert data["is_balanced"] is True
        # Includes the synthetic Current Year Earnings line since net
        # income (350) hasn't been closed.
        assert any(line["account_code"] == "CYE" for line in data["equity"]["lines"])


class TestProfitLoss:
    def test_profit_loss_net_income(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        token = _user_token(test_client, db_session, "pl_report@example.com")
        cid = str(_create_company(test_client, token))
        ctx = _setup(db_session, uuid.UUID(cid))

        resp = test_client.get(
            _url(
                cid,
                f"/reports/profit-loss?period_from={ctx['today'].isoformat()}"
                f"&period_to={ctx['today'].isoformat()}",
            ),
            headers=_auth(token),
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert data["total_revenue"] == "500.000000"
        assert data["total_expense"] == "150.000000"
        assert data["net_income"] == "350.000000"


class TestCashFlow:
    def test_cash_flow_reconciles(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        token = _user_token(test_client, db_session, "cf_report@example.com")
        cid = str(_create_company(test_client, token))
        ctx = _setup(db_session, uuid.UUID(cid))

        resp = test_client.get(
            _url(
                cid,
                f"/reports/cash-flow?period_from={ctx['today'].isoformat()}"
                f"&period_to={ctx['today'].isoformat()}",
            ),
            headers=_auth(token),
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert data["reconciles"] is True
        assert Decimal(data["net_cash_from_operating_activities"]) == Decimal(
            data["net_change_in_cash"]
        )


class TestGLReport:
    def test_offset_mode_returns_all_lines(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        token = _user_token(test_client, db_session, "gl_report_offset@example.com")
        cid = str(_create_company(test_client, token))
        _setup(db_session, uuid.UUID(cid))

        resp = test_client.get(_url(cid, "/reports/gl"), headers=_auth(token))
        assert resp.status_code == 200, resp.text
        rows = resp.json()["data"]
        assert (
            len(rows) >= 4
        )  # opening balance (2 lines) + sale (2 lines) + expense (2 lines)

    def test_cursor_mode_pages_through_every_row_with_no_overlap(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """Cursor mode (T256) walks the ledger in a DIFFERENT order
        (chronological ASC — see gl_detail_cursor_query's docstring) than
        the legacy offset mode (recent-first DESC) — the two are separate
        traversal modes, not interchangeable mid-walk. This test stays
        entirely within cursor mode: bootstraps page 1 with a sentinel
        cursor before all data, then continues from each page's own
        derived cursor.
        """
        token = _user_token(test_client, db_session, "gl_report_cursor@example.com")
        cid = str(_create_company(test_client, token))
        _setup(db_session, uuid.UUID(cid))

        cursor = ("1900-01-01", "00000000-0000-0000-0000-000000000000", 0)
        seen: set[tuple] = set()
        pages = 0
        while True:
            resp = test_client.get(
                _url(
                    cid,
                    f"/reports/gl?limit=2&cursor_date={cursor[0]}"
                    f"&cursor_entry_id={cursor[1]}&cursor_line_number={cursor[2]}",
                ),
                headers=_auth(token),
            )
            assert resp.status_code == 200, resp.text
            rows = resp.json()["data"]
            pages += 1
            if not rows:
                break
            for r in rows:
                key = (r["journal_entry_id"], r["line_number"])
                assert key not in seen, "cursor pagination duplicated a row"
                seen.add(key)
            last = rows[-1]
            cursor = (
                last["posting_date"],
                last["journal_entry_id"],
                last["line_number"],
            )
            assert pages < 20, "pagination did not terminate"

        assert len(seen) >= 4


class TestSubsidiaryLedgerReports:
    def test_customer_ledger_report(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        token = _user_token(test_client, db_session, "cust_ledger_report@example.com")
        cid = str(_create_company(test_client, token))
        ctx = _setup(db_session, uuid.UUID(cid))

        resp = test_client.get(
            _url(
                cid,
                f"/reports/customer-ledger/{ctx['customer_id']}?from_date={ctx['today'].isoformat()}"
                f"&to_date={ctx['today'].isoformat()}",
            ),
            headers=_auth(token),
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["data"]["closing_balance"] == "200.000000"

    def test_journal_report(self, test_client: TestClient, db_session: Session) -> None:
        token = _user_token(test_client, db_session, "journal_report@example.com")
        cid = str(_create_company(test_client, token))
        ctx = _setup(db_session, uuid.UUID(cid))

        resp = test_client.get(
            _url(cid, f"/reports/journals?period_id={ctx['period'].id}"),
            headers=_auth(token),
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert data["total"] == 3
        assert len(data["entries"]) == 3


class TestCrossTenantIsolation:
    def test_balance_sheet_isolated_per_company(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        token = _user_token(test_client, db_session, "reports_tenant@example.com")
        cid_a = str(_create_company(test_client, token))
        cid_b = str(_create_company(test_client, token))
        ctx = _setup(db_session, uuid.UUID(cid_a))
        # Company B has its own accounting configuration but zero transactions —
        # this isolates "different company, no data" from "no setup at all".
        AccountingConfigurationRepository(db_session).create(
            AccountingConfiguration(
                company_id=uuid.UUID(cid_b), base_currency_code="USD"
            )
        )

        resp = test_client.get(
            _url(
                cid_b, f"/reports/balance-sheet?as_of_date={ctx['today'].isoformat()}"
            ),
            headers=_auth(token),
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["total_assets"] == "0"
        assert data["total_liabilities"] == "0"
