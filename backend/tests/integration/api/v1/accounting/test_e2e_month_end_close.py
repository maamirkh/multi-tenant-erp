"""End-to-end integration test: month-end close workflow — Phase 16 (T298).

Post journals -> bank reconcile -> lock period -> generate statements ->
verify all pass, plus confirms period lock blocks new postings to the
locked period (spec.md §16.4/§16.5; PostingEngine Step 3).

Spec ref: specs/008-accounting-finance/tasks.md T298
"""

from __future__ import annotations

import uuid
from datetime import date

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

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
            "legal_name": f"Close Test Co {suffix}",
            "email": f"contact-{suffix}@close-test.example.com",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201, resp.text
    return uuid.UUID(resp.json()["data"]["id"])


class TestMonthEndCloseE2E:
    def test_post_reconcile_lock_report_workflow(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        token = _user_token(test_client, db_session, "close_full@example.com")
        cid = _create_company(test_client, token)
        cid_str = str(cid)

        account_repo = AccountRepository(db_session)
        bank_gl = account_repo.create(
            Account(
                company_id=cid,
                account_code="1000",
                account_name="Bank",
                account_type="ASSET",
            )
        )
        revenue = account_repo.create(
            Account(
                company_id=cid,
                account_code="4000",
                account_name="Revenue",
                account_type="REVENUE",
            )
        )
        expense = account_repo.create(
            Account(
                company_id=cid,
                account_code="5000",
                account_name="Expense",
                account_type="EXPENSE",
            )
        )
        accrued_liability = account_repo.create(
            Account(
                company_id=cid,
                account_code="2100",
                account_name="Accrued Liability",
                account_type="LIABILITY",
            )
        )

        fiscal_service = FiscalCalendarService(
            db=db_session,
            year_repo=FiscalYearRepository(db_session),
            period_repo=FiscalPeriodRepository(db_session),
            opening_balance_repo=OpeningBalanceRepository(db_session),
            audit_service=AuditLogService(
                db=db_session, audit_repo=AccountingAuditLogRepository(db_session)
            ),
        )
        today = date.today()
        fiscal_year = fiscal_service.create_fiscal_year(
            cid,
            f"FY-{uuid.uuid4().hex[:8]}",
            date(today.year, 1, 1),
            date(today.year, 12, 31),
            "USD",
        )
        current_period = next(
            p
            for p in fiscal_service.list_periods(cid, fiscal_year.id)
            if p.start_date <= today <= p.end_date
        )

        AccountingConfigurationRepository(db_session).create(
            AccountingConfiguration(company_id=cid, base_currency_code="USD")
        )

        bank_account = BankAccountRepository(db_session).create(
            BankAccount(
                company_id=cid,
                bank_name="Main Current Account",
                account_number="ACC-CLOSE-0001",
                currency_code="USD",
                gl_account_id=bank_gl.id,
            )
        )

        # --- Step 1: post journals ---
        # 1a. Bank deposit — a real revenue receipt into the bank account,
        # which is also what bank reconciliation will match against.
        resp = test_client.post(
            _url(cid_str, f"/bank-accounts/{bank_account.id}/deposit"),
            json={
                "total_amount": "5000.00",
                "contra_account_id": str(revenue.id),
                "deposit_date": today.isoformat(),
            },
            headers=_auth(token),
        )
        assert resp.status_code == 201, resp.text

        # 1b. A manual journal unrelated to the bank account (DR Expense /
        # CR Accrued Liability) — exercises the ordinary create->post path.
        resp = test_client.post(
            _url(cid_str, "/journals"),
            json={
                "journal_type": "STANDARD",
                "posting_source": "MANUAL",
                "posting_date": today.isoformat(),
                "currency_code": "USD",
                "lines": [
                    {
                        "account_id": str(expense.id),
                        "debit_amount": "1200.00",
                        "credit_amount": "0",
                    },
                    {
                        "account_id": str(accrued_liability.id),
                        "debit_amount": "0",
                        "credit_amount": "1200.00",
                    },
                ],
            },
            headers=_auth(token),
        )
        assert resp.status_code == 201, resp.text
        journal_id = resp.json()["data"]["id"]
        resp = test_client.post(
            _url(cid_str, f"/journals/{journal_id}/post"), headers=_auth(token)
        )
        assert resp.status_code == 200, resp.text

        # --- Step 2: bank reconcile ---
        resp = test_client.post(
            _url(cid_str, f"/bank-accounts/{bank_account.id}/reconciliations"),
            json={
                "statement_date": today.isoformat(),
                "statement_closing_balance": "5000.00",
            },
            headers=_auth(token),
        )
        assert resp.status_code == 201, resp.text
        reconciliation_id = resp.json()["data"]["id"]

        resp = test_client.post(
            _url(
                cid_str,
                f"/bank-accounts/{bank_account.id}/reconciliations/{reconciliation_id}/import-statement",
            ),
            json={
                "lines": [{"statement_date": today.isoformat(), "amount": "5000.00"}]
            },
            headers=_auth(token),
        )
        assert resp.status_code == 201, resp.text

        resp = test_client.post(
            _url(
                cid_str,
                f"/bank-accounts/{bank_account.id}/reconciliations/{reconciliation_id}/auto-match",
            ),
            headers=_auth(token),
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["data"]["matched_count"] == 1

        resp = test_client.post(
            _url(
                cid_str,
                f"/bank-accounts/{bank_account.id}/reconciliations/{reconciliation_id}/complete",
            ),
            headers=_auth(token),
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["data"]["status"] == "COMPLETED"
        assert resp.json()["data"]["difference"] == "0.000000"

        resp = test_client.post(
            _url(
                cid_str,
                f"/bank-accounts/{bank_account.id}/reconciliations/{reconciliation_id}/lock",
            ),
            headers=_auth(token),
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["data"]["status"] == "LOCKED"

        # --- Step 3: lock the fiscal period ---
        resp = test_client.post(
            _url(
                cid_str,
                f"/fiscal-years/{fiscal_year.id}/periods/{current_period.id}/lock",
            ),
            json={"lock_reason": "Month-end close"},
            headers=_auth(token),
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["data"]["status"] == "LOCKED"

        # A new journal DRAFT may still be created (only balance-checked),
        # but attempting to POST it into the now-locked period must be
        # rejected — PostingEngine Step 3 (spec.md §14).
        resp = test_client.post(
            _url(cid_str, "/journals"),
            json={
                "journal_type": "STANDARD",
                "posting_source": "MANUAL",
                "posting_date": today.isoformat(),
                "currency_code": "USD",
                "lines": [
                    {
                        "account_id": str(expense.id),
                        "debit_amount": "50.00",
                        "credit_amount": "0",
                    },
                    {
                        "account_id": str(accrued_liability.id),
                        "debit_amount": "0",
                        "credit_amount": "50.00",
                    },
                ],
            },
            headers=_auth(token),
        )
        assert resp.status_code == 201, resp.text
        blocked_journal_id = resp.json()["data"]["id"]
        resp = test_client.post(
            _url(cid_str, f"/journals/{blocked_journal_id}/post"), headers=_auth(token)
        )
        assert resp.status_code == 422, resp.text

        # --- Step 4: generate statements — all must pass ---
        resp = test_client.get(
            _url(cid_str, f"/reports/trial-balance?period_id={current_period.id}"),
            headers=_auth(token),
        )
        assert resp.status_code == 200, resp.text
        tb = resp.json()["data"]
        assert tb["total_debit"] == tb["total_credit"]
        assert tb["is_balanced"] is True

        resp = test_client.get(
            _url(cid_str, f"/reports/balance-sheet?as_of_date={today.isoformat()}"),
            headers=_auth(token),
        )
        assert resp.status_code == 200, resp.text
        bs = resp.json()["data"]
        assert bs["is_balanced"] is True

        resp = test_client.get(
            _url(
                cid_str,
                f"/reports/profit-loss?period_from={today.isoformat()}&period_to={today.isoformat()}",
            ),
            headers=_auth(token),
        )
        assert resp.status_code == 200, resp.text
        pl = resp.json()["data"]
        # Revenue 5000 - Expense 1200 = 3800 net income.
        assert pl["net_income"] == "3800.000000"
