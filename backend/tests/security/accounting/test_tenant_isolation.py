"""Tenant isolation tests — accounting module — Phase 14 T284.

Verifies zero cross-company data leakage for the accounting module:
  - Company A's journals are not visible via Company B's journal list.
  - Company A's journal is not reachable via Company B's company_id path
    (a genuine member of B, who is NOT a member of A, gets 403 at the
    router-level membership gate — see ``get_current_company_member`` wired
    for the whole ``/companies/{company_id}/accounting`` prefix in
    ``api/v1/router.py``; the request never even reaches the journal
    lookup, so it never becomes a 404).
  - Company A's audit trail is not accessible via Company B's credentials.
  - Company A's customer ledger report is not accessible via Company B's
    credentials — even though the requesting user is a genuine owner (full
    accounting permissions) of Company B.

Two independent companies (A and B) are created, each owned by a distinct
real user. Company A populates data. Company B's owner — who has full
accounting permissions *in Company B* — must not be able to see any of
Company A's data.

Task: T284
Spec ref: specs/008-accounting-finance/tasks.md T284
"""

from __future__ import annotations

import uuid
from datetime import date
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from core.utils.datetime import utcnow
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

_TEST_PASSWORD = "TenantIso@12345"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


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
    user, pw = create_test_user(db_session, email=email, password=_TEST_PASSWORD)
    return _login(test_client, user.email, pw)


def _create_company(client: TestClient, token: str) -> uuid.UUID:
    """Create a real company (via the API) so the caller becomes its owner
    and active member — required now that company-scoped routes enforce
    membership (see api/v1/router.py's get_current_company_member gate)."""
    suffix = uuid.uuid4().hex[:8]
    resp = client.post(
        "/api/v1/companies",
        json={
            "legal_name": f"Tenant Iso Acct Co {suffix}",
            "email": f"contact-{suffix}@tenant-iso-acct.example.com",
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
    today = utcnow().date()
    fiscal_service.create_fiscal_year(
        company_id,
        f"FY-{uuid.uuid4().hex[:8]}",
        date(today.year, 1, 1),
        date(today.year, 12, 31),
        "USD",
    )
    return {"ar": str(ar.id), "revenue": str(revenue.id), "today": today.isoformat()}


def _posting_body(
    ar_id: str, revenue_id: str, posting_date: str, amount: str = "500.00"
) -> dict[str, Any]:
    return {
        "journal_type": "STANDARD",
        "posting_source": "MANUAL",
        "posting_date": posting_date,
        "currency_code": "USD",
        "lines": [
            {"account_id": ar_id, "debit_amount": amount, "credit_amount": "0"},
            {"account_id": revenue_id, "debit_amount": "0", "credit_amount": amount},
        ],
    }


def two_companies_with_journal_in_a(
    test_client: TestClient, db_session: Session
) -> tuple[str, str, str, str, str]:
    """Returns (cid_a, token_a, journal_id_in_a, cid_b, token_b)."""
    token_a = _user_token(
        test_client, db_session, f"tia-{uuid.uuid4().hex[:8]}@example.com"
    )
    cid_a = _create_company(test_client, token_a)
    cid_a_str = str(cid_a)
    gl_a = _setup_gl(db_session, cid_a)
    resp = test_client.post(
        _url(cid_a_str, "/journals"),
        json=_posting_body(gl_a["ar"], gl_a["revenue"], gl_a["today"]),
        headers=_auth(token_a),
    )
    assert resp.status_code == 201, resp.text
    journal_id = resp.json()["data"]["id"]

    token_b = _user_token(
        test_client, db_session, f"tib-{uuid.uuid4().hex[:8]}@example.com"
    )
    cid_b = _create_company(test_client, token_b)
    cid_b_str = str(cid_b)

    return cid_a_str, token_a, journal_id, cid_b_str, token_b


# ---------------------------------------------------------------------------
# Journal isolation
# ---------------------------------------------------------------------------


class TestJournalTenantIsolation:
    def test_company_b_journal_list_does_not_show_company_a_journals(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        _cid_a, _token_a, _journal_id, cid_b, token_b = two_companies_with_journal_in_a(
            test_client, db_session
        )
        resp = test_client.get(_url(cid_b, "/journals"), headers=_auth(token_b))
        assert resp.status_code == 200
        items = resp.json()["data"]
        assert items == [], f"Company B saw Company A's journals: {items}"

    def test_company_b_owner_cannot_fetch_company_a_journal_via_b_path(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """Company B's owner is not a member of Company A. Requesting
        Company A's journal through Company A's own company_id path is
        rejected at the router-level membership gate (403) — Company B's
        owner simply isn't an active member of Company A, regardless of
        which journal_id they pass."""
        cid_a, _token_a, journal_id, _cid_b, token_b = two_companies_with_journal_in_a(
            test_client, db_session
        )
        resp = test_client.get(
            _url(cid_a, f"/journals/{journal_id}"), headers=_auth(token_b)
        )
        assert resp.status_code == 403, resp.text

    def test_company_b_owner_gets_not_found_for_as_journal_id_under_b_scope(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """If Company B's owner instead scopes the request to their OWN
        company (which they legitimately access) but supplies Company A's
        journal_id, the journal lookup is scoped by company_id and finds
        nothing — 404, not a cross-tenant leak."""
        _cid_a, _token_a, journal_id, cid_b, token_b = two_companies_with_journal_in_a(
            test_client, db_session
        )
        resp = test_client.get(
            _url(cid_b, f"/journals/{journal_id}"), headers=_auth(token_b)
        )
        assert resp.status_code == 404, resp.text


# ---------------------------------------------------------------------------
# Audit log isolation
# ---------------------------------------------------------------------------


class TestAuditLogTenantIsolation:
    def test_company_b_owner_cannot_view_company_a_audit_log(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        cid_a, _token_a, _journal_id, _cid_b, token_b = two_companies_with_journal_in_a(
            test_client, db_session
        )
        # token_b's user is a genuine, fully-permissioned owner — but only of
        # Company B. Requesting Company A's audit log must be rejected at
        # the membership gate before accounting.audit.view is even checked.
        resp = test_client.get(_url(cid_a, "/audit-log"), headers=_auth(token_b))
        assert resp.status_code == 403, resp.text

    def test_company_b_owner_cannot_export_company_a_audit_log(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        cid_a, _token_a, _journal_id, _cid_b, token_b = two_companies_with_journal_in_a(
            test_client, db_session
        )
        resp = test_client.get(_url(cid_a, "/audit-log/export"), headers=_auth(token_b))
        assert resp.status_code == 403, resp.text


# ---------------------------------------------------------------------------
# Customer ledger isolation
# ---------------------------------------------------------------------------


class TestCustomerLedgerTenantIsolation:
    def test_company_b_owner_cannot_view_company_a_customer_ledger(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        cid_a, _token_a, _journal_id, _cid_b, token_b = two_companies_with_journal_in_a(
            test_client, db_session
        )
        customer_id = str(uuid.uuid4())
        resp = test_client.get(
            _url(cid_a, f"/reports/customer-ledger/{customer_id}"),
            params={"from_date": "2020-01-01", "to_date": "2030-12-31"},
            headers=_auth(token_b),
        )
        assert resp.status_code == 403, resp.text
