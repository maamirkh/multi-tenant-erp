"""API integration tests for General Ledger / journal endpoints — Phase 4.

Tests:
  - Full DRAFT -> SUBMIT -> APPROVE -> POST lifecycle
  - Rejection
  - Reversal
  - GL report filters
  - Cross-tenant isolation
  - 401 enforcement

Spec ref: specs/008-accounting-finance/tasks.md T112
"""

from __future__ import annotations

import uuid

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
from tests.fixtures.users_roles_fixtures import grant_permission_to_user


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


def _user_token_and_id(
    test_client: TestClient, db_session: Session, email: str
) -> tuple[str, uuid.UUID]:
    user, pw = create_test_user(db_session, email=email)
    return _login(test_client, user.email, pw), user.id


def _create_company(client: TestClient, token: str) -> uuid.UUID:
    """Create a real company (via the API) so the caller becomes its owner
    and active member — required now that company-scoped routes enforce
    membership (see api/v1/router.py's get_current_company_member gate)."""
    suffix = uuid.uuid4().hex[:8]
    resp = client.post(
        "/api/v1/companies",
        json={
            "legal_name": f"Journal Test Co {suffix}",
            "email": f"contact-{suffix}@journal-test.example.com",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201, resp.text
    return uuid.UUID(resp.json()["data"]["id"])


def _add_member(db_session: Session, company_id: uuid.UUID, user_id: uuid.UUID) -> None:
    """Grant an additional real user an active membership in ``company_id``,
    with the ``accounting.journal.approve`` SoD permission (tasks.md T276).

    Needed for tests where a second, distinct user (e.g. a journal approver)
    must act within the same company — the router-level membership gate
    requires an active company_members row for every company-scoped call,
    and PostingEngine.approve() additionally requires this specific
    permission on top of that.
    """
    grant_permission_to_user(
        db_session,
        company_id=company_id,
        user_id=user_id,
        permission_code="accounting.journal.approve",
        role_slug=f"approver-{uuid.uuid4().hex[:8]}",
    )


def _setup_gl(db_session: Session, company_id: uuid.UUID) -> dict:
    """Create AR/Revenue accounts and a fiscal year covering today, directly via the DB."""
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
    from datetime import date

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
) -> dict:
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


class TestUnauthenticated:
    def test_journals_requires_auth(self, test_client: TestClient) -> None:
        resp = test_client.get(_url(str(uuid.uuid4()), "/journals"))
        assert resp.status_code == 401

    def test_gl_report_requires_auth(self, test_client: TestClient) -> None:
        resp = test_client.get(_url(str(uuid.uuid4()), "/reports/gl"))
        assert resp.status_code == 401


class TestFullLifecycle:
    def test_draft_submit_approve_post(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        token = _user_token(test_client, db_session, "journal_lifecycle@example.com")
        cid = _create_company(test_client, token)
        gl = _setup_gl(db_session, cid)
        cid_str = str(cid)

        resp = test_client.post(
            _url(cid_str, "/journals"),
            json=_posting_body(gl["ar"], gl["revenue"], gl["today"]),
            headers=_auth(token),
        )
        assert resp.status_code == 201, resp.text
        journal = resp.json()["data"]
        assert journal["status"] == "DRAFT"
        assert len(journal["lines"]) == 2
        journal_id = journal["id"]

        resp = test_client.post(
            _url(cid_str, f"/journals/{journal_id}/submit"), headers=_auth(token)
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["status"] == "SUBMITTED"

        approver_token, approver_id = _user_token_and_id(
            test_client, db_session, "journal_lifecycle_approver@example.com"
        )
        _add_member(db_session, cid, approver_id)
        resp = test_client.post(
            _url(cid_str, f"/journals/{journal_id}/approve"),
            headers=_auth(approver_token),
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["status"] == "APPROVED"

        resp = test_client.post(
            _url(cid_str, f"/journals/{journal_id}/post"), headers=_auth(token)
        )
        assert resp.status_code == 200, resp.text
        result = resp.json()["data"]
        assert result["journal_number"] is not None

        resp = test_client.get(
            _url(cid_str, f"/journals/{journal_id}"), headers=_auth(token)
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["status"] == "POSTED"

    def test_unbalanced_create_returns_422(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        token = _user_token(test_client, db_session, "journal_unbalanced@example.com")
        cid = _create_company(test_client, token)
        gl = _setup_gl(db_session, cid)
        body = _posting_body(gl["ar"], gl["revenue"], gl["today"])
        body["lines"][1]["credit_amount"] = "1.00"
        resp = test_client.post(
            _url(str(cid), "/journals"), json=body, headers=_auth(token)
        )
        assert resp.status_code == 422
        assert "balance" in resp.json()["error"]["message"].lower()

    def test_direct_draft_to_post_below_threshold(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        token = _user_token(test_client, db_session, "journal_direct@example.com")
        cid = _create_company(test_client, token)
        gl = _setup_gl(db_session, cid)
        cid_str = str(cid)

        resp = test_client.post(
            _url(cid_str, "/journals"),
            json=_posting_body(gl["ar"], gl["revenue"], gl["today"]),
            headers=_auth(token),
        )
        journal_id = resp.json()["data"]["id"]

        resp = test_client.post(
            _url(cid_str, f"/journals/{journal_id}/post"), headers=_auth(token)
        )
        assert resp.status_code == 200, resp.text


class TestRejection:
    def test_submit_then_reject(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        token = _user_token(test_client, db_session, "journal_reject@example.com")
        cid = _create_company(test_client, token)
        gl = _setup_gl(db_session, cid)
        cid_str = str(cid)

        resp = test_client.post(
            _url(cid_str, "/journals"),
            json=_posting_body(gl["ar"], gl["revenue"], gl["today"]),
            headers=_auth(token),
        )
        journal_id = resp.json()["data"]["id"]
        test_client.post(
            _url(cid_str, f"/journals/{journal_id}/submit"), headers=_auth(token)
        )

        resp = test_client.post(
            _url(cid_str, f"/journals/{journal_id}/reject"),
            json={"rejection_reason": "Wrong account coding"},
            headers=_auth(token),
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["status"] == "REJECTED"

        # A rejected entry can never be posted.
        resp = test_client.post(
            _url(cid_str, f"/journals/{journal_id}/post"), headers=_auth(token)
        )
        assert resp.status_code == 422


class TestRejectRBAC:
    def test_reject_blocked_without_journal_approve_permission(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """Regression test — pre-Epic-9 hardening audit (2026-08-15).

        ``PostingEngine.reject()`` had no permission check at all — the
        mirror-image ``approve()`` decision on the same SUBMITTED entry
        requires ``accounting.journal.approve``, but reject was callable by
        any company member. This test creates a second, distinct user who
        is a company member but was never granted that permission, and
        asserts they are blocked (403) from rejecting a submitted journal
        that the owner created and submitted.
        """
        owner_token, owner_id = _user_token_and_id(
            test_client, db_session, "reject_rbac_owner@example.com"
        )
        cid = _create_company(test_client, owner_token)
        gl = _setup_gl(db_session, cid)
        cid_str = str(cid)

        resp = test_client.post(
            _url(cid_str, "/journals"),
            json=_posting_body(gl["ar"], gl["revenue"], gl["today"]),
            headers=_auth(owner_token),
        )
        journal_id = resp.json()["data"]["id"]
        test_client.post(
            _url(cid_str, f"/journals/{journal_id}/submit"), headers=_auth(owner_token)
        )

        # A second user, a real active company member with NO
        # accounting.journal.approve grant.
        no_perm_token, no_perm_id = _user_token_and_id(
            test_client, db_session, "reject_rbac_noperm@example.com"
        )
        grant_permission_to_user(
            db_session,
            company_id=cid,
            user_id=no_perm_id,
            permission_code="accounting.gl.view",
            role_slug=f"viewer-{uuid.uuid4().hex[:8]}",
        )

        resp = test_client.post(
            _url(cid_str, f"/journals/{journal_id}/reject"),
            json={"rejection_reason": "Should be blocked"},
            headers=_auth(no_perm_token),
        )
        assert resp.status_code == 403, resp.text

        # Control: the owner (who does have accounting.journal.approve via
        # the default owner role) can still reject the same entry — proves
        # this is a targeted permission gate, not a blanket regression.
        resp = test_client.post(
            _url(cid_str, f"/journals/{journal_id}/reject"),
            json={"rejection_reason": "Wrong account coding"},
            headers=_auth(owner_token),
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["data"]["status"] == "REJECTED"


class TestReversal:
    def test_reverse_a_posted_entry(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        token = _user_token(test_client, db_session, "journal_reverse@example.com")
        cid = _create_company(test_client, token)
        gl = _setup_gl(db_session, cid)
        cid_str = str(cid)

        resp = test_client.post(
            _url(cid_str, "/journals"),
            json=_posting_body(gl["ar"], gl["revenue"], gl["today"]),
            headers=_auth(token),
        )
        journal_id = resp.json()["data"]["id"]
        test_client.post(
            _url(cid_str, f"/journals/{journal_id}/post"), headers=_auth(token)
        )

        resp = test_client.post(
            _url(cid_str, f"/journals/{journal_id}/reverse"),
            json={"reason": "duplicate entry"},
            headers=_auth(token),
        )
        assert resp.status_code == 200, resp.text
        reversal = resp.json()["data"]
        assert reversal["is_reversal"] is True
        assert reversal["reversal_of_journal_id"] == journal_id

        resp = test_client.get(
            _url(cid_str, f"/journals/{journal_id}"), headers=_auth(token)
        )
        assert resp.json()["data"]["status"] == "REVERSED"

    def test_cannot_reverse_a_draft(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        token = _user_token(
            test_client, db_session, "journal_reverse_draft@example.com"
        )
        cid = _create_company(test_client, token)
        gl = _setup_gl(db_session, cid)
        cid_str = str(cid)

        resp = test_client.post(
            _url(cid_str, "/journals"),
            json=_posting_body(gl["ar"], gl["revenue"], gl["today"]),
            headers=_auth(token),
        )
        journal_id = resp.json()["data"]["id"]

        resp = test_client.post(
            _url(cid_str, f"/journals/{journal_id}/reverse"),
            json={},
            headers=_auth(token),
        )
        assert resp.status_code == 422


class TestGLReportAndCrossTenantIsolation:
    def test_gl_report_returns_only_posted_lines(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        token = _user_token(test_client, db_session, "journal_gl_report@example.com")
        cid = _create_company(test_client, token)
        gl = _setup_gl(db_session, cid)
        cid_str = str(cid)

        resp = test_client.post(
            _url(cid_str, "/journals"),
            json=_posting_body(gl["ar"], gl["revenue"], gl["today"]),
            headers=_auth(token),
        )
        journal_id = resp.json()["data"]["id"]
        test_client.post(
            _url(cid_str, f"/journals/{journal_id}/post"), headers=_auth(token)
        )

        # A second, never-posted draft should NOT appear in the GL report.
        test_client.post(
            _url(cid_str, "/journals"),
            json=_posting_body(gl["ar"], gl["revenue"], gl["today"], amount="999.00"),
            headers=_auth(token),
        )

        resp = test_client.get(
            _url(cid_str, "/reports/gl"),
            params={"account_id": gl["ar"]},
            headers=_auth(token),
        )
        assert resp.status_code == 200
        rows = resp.json()["data"]
        assert len(rows) == 1
        assert rows[0]["debit_amount"] == "500.000000"

    def test_cross_tenant_isolation(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        token = _user_token(test_client, db_session, "journal_tenant@example.com")
        cid_a = _create_company(test_client, token)
        cid_b = _create_company(test_client, token)
        gl = _setup_gl(db_session, cid_a)

        resp = test_client.post(
            _url(str(cid_a), "/journals"),
            json=_posting_body(gl["ar"], gl["revenue"], gl["today"]),
            headers=_auth(token),
        )
        journal_id = resp.json()["data"]["id"]

        resp = test_client.get(
            _url(str(cid_b), f"/journals/{journal_id}"), headers=_auth(token)
        )
        assert resp.status_code == 404
