"""Financial controls security tests — Phase 14 T282.

Covers Segregation-of-Duties (SoD) enforcement for the accounting module:
  - Self-approval blocked (creator == approver) for both journal and
    payment approval.
  - Role-based approval permission enforcement (Accountant cannot approve
    a journal they did not create either, since they lack
    ``accounting.journal.approve``).
  - Cross-tenant: a user who is only a member of Company A cannot approve
    a journal that lives in Company B — rejected at the company-membership
    gate (``get_current_company_member``, wired as a router-level
    dependency for the whole ``/companies/{company_id}/accounting`` prefix
    in ``api/v1/router.py``) before SoD/permission checks ever run.

IMPORTANT — discrepancy found vs. the original task description (see
final report to the user for a full write-up):

1. ``SelfApprovalNotAllowedError`` (posting_engine.py / payment_service.py)
   is defined with ``http_status=422`` (modules/accounting/exceptions.py),
   NOT 403. The task description assumed 403 for self-approval; the actual,
   verified behavior is 422. Tests below assert 422 to match reality.

(A second discrepancy — period-lock/unlock/year-end-close having no RBAC
check at all — was found during this same review and has since been FIXED
directly in modules/accounting/router.py (lock_fiscal_period,
unlock_fiscal_period, year_end_close now call
``user_has_accounting_permission`` for ``accounting.period.lock`` /
``accounting.period.close``, matching journal/payment approval and
audit-log viewing). ``TestFiscalYearCloseRequiresPermission`` below asserts
the corrected, enforced behavior.)

Spec ref: specs/008-accounting-finance/tasks.md T276, T282
"""

from __future__ import annotations

import uuid
from datetime import date
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from core.utils.datetime import utcnow
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
from tests.fixtures.users_roles_fixtures import (
    create_member_with_role,
    grant_permission_to_user,
)

_TEST_PASSWORD = "FinCtl@12345"


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


def _user_token_and_id(
    test_client: TestClient, db_session: Session, email: str
) -> tuple[str, uuid.UUID]:
    user, pw = create_test_user(db_session, email=email, password=_TEST_PASSWORD)
    return _login(test_client, user.email, pw), user.id


def _create_company(client: TestClient, token: str) -> uuid.UUID:
    """Create a real company (via the API) so the caller becomes its owner
    and active member — required now that company-scoped routes enforce
    membership (see api/v1/router.py's get_current_company_member gate)."""
    suffix = uuid.uuid4().hex[:8]
    resp = client.post(
        "/api/v1/companies",
        json={
            "legal_name": f"FinCtl Test Co {suffix}",
            "email": f"contact-{suffix}@finctl-test.example.com",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201, resp.text
    return uuid.UUID(resp.json()["data"]["id"])


def _setup_gl(db_session: Session, company_id: uuid.UUID) -> dict[str, Any]:
    """Create AR/Revenue accounts and a fiscal year covering today."""
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


def _create_and_submit_journal(
    test_client: TestClient, token: str, cid: str, gl: dict[str, Any]
) -> str:
    resp = test_client.post(
        _url(cid, "/journals"),
        json=_posting_body(gl["ar"], gl["revenue"], gl["today"]),
        headers=_auth(token),
    )
    assert resp.status_code == 201, resp.text
    journal_id = resp.json()["data"]["id"]
    resp = test_client.post(
        _url(cid, f"/journals/{journal_id}/submit"), headers=_auth(token)
    )
    assert resp.status_code == 200, resp.text
    return str(journal_id)


def _setup_payment_approval(
    test_client: TestClient,
    token: str,
    db_session: Session,
    cid: uuid.UUID,
    threshold: str = "100.00",
) -> dict[str, Any]:
    """Configure GL accounts, a payment_approval_threshold, and enable the
    approval-workflow feature flag so that a payment above the threshold is
    created DRAFT (pending approval) rather than immediately POSTED."""
    account_repo = AccountRepository(db_session)
    ar = account_repo.create(
        Account(
            company_id=cid, account_code="1100", account_name="AR", account_type="ASSET"
        )
    )
    bank_gl = account_repo.create(
        Account(
            company_id=cid,
            account_code="1000",
            account_name="Bank",
            account_type="ASSET",
        )
    )
    bank = BankAccountRepository(db_session).create(
        BankAccount(
            company_id=cid,
            bank_name="Test Bank",
            account_number=f"ACC-{uuid.uuid4().hex[:8]}",
            currency_code="USD",
            gl_account_id=bank_gl.id,
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
    today = utcnow().date()
    fiscal_service.create_fiscal_year(
        cid,
        f"FY-{uuid.uuid4().hex[:8]}",
        date(today.year, 1, 1),
        date(today.year, 12, 31),
        "USD",
    )

    cid_str = str(cid)
    resp = test_client.put(
        _url(cid_str, "/system-accounts"),
        json={"role": "default_ar_account_id", "account_id": str(ar.id)},
        headers=_auth(token),
    )
    assert resp.status_code == 200, resp.text

    resp = test_client.put(
        _url(cid_str, "/configuration"),
        json={"payment_approval_threshold": threshold},
        headers=_auth(token),
    )
    assert resp.status_code == 200, resp.text

    resp = test_client.put(
        _url(cid_str, "/feature-flags/accounting.approvalworkflow.enabled"),
        json={"is_enabled": True},
        headers=_auth(token),
    )
    assert resp.status_code == 200, resp.text

    return {"ar": ar, "bank": bank, "today": today.isoformat()}


def _create_draft_customer_payment(
    test_client: TestClient,
    token: str,
    cid: str,
    gl: dict[str, Any],
    amount: str = "500.00",
) -> str:
    resp = test_client.post(
        _url(cid, "/payments/customer"),
        json={
            "customer_id": str(uuid.uuid4()),
            "payment_method": "BANK_TRANSFER",
            "payment_date": gl["today"],
            "amount": amount,
            "currency_code": "USD",
            "bank_account_id": str(gl["bank"].id),
        },
        headers=_auth(token),
    )
    assert resp.status_code == 201, resp.text
    payment = resp.json()["data"]
    assert payment["status"] == "DRAFT", (
        "Payment should be DRAFT (pending approval) given amount > threshold "
        f"and the approval-workflow flag enabled: {payment}"
    )
    return str(payment["id"])


# ---------------------------------------------------------------------------
# SoD: self-approval blocked — journal
# ---------------------------------------------------------------------------


class TestJournalSelfApprovalBlocked:
    def test_creator_cannot_approve_own_journal(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        token, _uid = _user_token_and_id(
            test_client, db_session, f"jsa-{uuid.uuid4().hex[:8]}@example.com"
        )
        cid = _create_company(test_client, token)
        cid_str = str(cid)
        gl = _setup_gl(db_session, cid)
        journal_id = _create_and_submit_journal(test_client, token, cid_str, gl)

        resp = test_client.post(
            _url(cid_str, f"/journals/{journal_id}/approve"), headers=_auth(token)
        )

        # ACTUAL behavior: SelfApprovalNotAllowedError carries http_status=422
        # (modules/accounting/exceptions.py), not 403 as originally assumed.
        assert resp.status_code == 422, resp.text
        assert resp.json()["error"]["code"] == "SELF_APPROVAL_NOT_ALLOWED"


# ---------------------------------------------------------------------------
# SoD: self-approval blocked — payment
# ---------------------------------------------------------------------------


class TestPaymentSelfApprovalBlocked:
    def test_creator_cannot_approve_own_payment(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        token, _uid = _user_token_and_id(
            test_client, db_session, f"psa-{uuid.uuid4().hex[:8]}@example.com"
        )
        cid = _create_company(test_client, token)
        cid_str = str(cid)
        gl = _setup_payment_approval(test_client, token, db_session, cid)
        payment_id = _create_draft_customer_payment(test_client, token, cid_str, gl)

        resp = test_client.post(
            _url(cid_str, f"/payments/{payment_id}/approve"), headers=_auth(token)
        )

        assert resp.status_code == 422, resp.text
        assert resp.json()["error"]["code"] == "SELF_APPROVAL_NOT_ALLOWED"


# ---------------------------------------------------------------------------
# RBAC gap: fiscal year close is NOT permission-gated (documented finding)
# ---------------------------------------------------------------------------


class TestFiscalYearCloseRequiresPermission:
    """Only owner/admin hold ``accounting.period.close`` in
    DEFAULT_ROLE_PERMISSIONS (CFO/System-Admin-equivalent, spec.md §33 —
    "Close Fiscal Year"). A manager (Controller-equivalent) lacks it and
    must be rejected with 403.
    """

    def test_manager_role_cannot_close_fiscal_year(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        owner_token, owner_id = _user_token_and_id(
            test_client, db_session, f"fyc-owner-{uuid.uuid4().hex[:8]}@example.com"
        )
        cid = _create_company(test_client, owner_token)
        cid_str = str(cid)

        # Fiscal year + lock every period (a prerequisite for year-end-close,
        # unrelated to the RBAC question being tested here).
        resp = test_client.post(
            _url(cid_str, "/fiscal-years"),
            json={
                "fiscal_year_name": f"FY-{uuid.uuid4().hex[:8]}",
                "start_date": "2077-01-01",
                "end_date": "2077-12-31",
                "base_currency_code": "USD",
            },
            headers=_auth(owner_token),
        )
        assert resp.status_code == 201, resp.text
        year = resp.json()["data"]

        periods = test_client.get(
            _url(cid_str, f"/fiscal-years/{year['id']}/periods"),
            headers=_auth(owner_token),
        ).json()["data"]
        for period in periods:
            resp = test_client.post(
                _url(
                    cid_str, f"/fiscal-years/{year['id']}/periods/{period['id']}/lock"
                ),
                json={"lock_reason": "period-end"},
                headers=_auth(owner_token),
            )
            assert resp.status_code == 200, resp.text

        # A "manager" role (Controller-equivalent per constants.py) does NOT
        # hold accounting.period.close — verify that via DEFAULT_ROLE_PERMISSIONS.
        from modules.users_roles.constants import DEFAULT_ROLE_PERMISSIONS

        assert "accounting.period.close" not in DEFAULT_ROLE_PERMISSIONS["manager"]

        manager_token, manager_id = _user_token_and_id(
            test_client, db_session, f"fyc-mgr-{uuid.uuid4().hex[:8]}@example.com"
        )
        create_member_with_role(
            db_session, company_id=cid, user_id=manager_id, role_slug="manager"
        )

        resp = test_client.post(
            _url(cid_str, f"/fiscal-years/{year['id']}/year-end-close"),
            json={},
            headers=_auth(manager_token),
        )

        assert resp.status_code == 403, resp.text
        assert resp.json()["error"]["code"] == "APPROVAL_PERMISSION_DENIED"

        # Confirm the owner (holds accounting.period.close) succeeds where
        # the manager was correctly blocked.
        resp = test_client.post(
            _url(cid_str, f"/fiscal-years/{year['id']}/year-end-close"),
            json={},
            headers=_auth(owner_token),
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["data"]["status"] == "CLOSED"


# ---------------------------------------------------------------------------
# Accountant role cannot approve journals (has journal.create/post, not approve)
# ---------------------------------------------------------------------------


class TestAccountantCannotApproveJournals:
    def test_accountant_approving_own_journal_blocked_by_self_approval_first(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """An accountant approving their OWN journal hits the self-approval
        check before the permission check even runs (posting_engine.approve()
        checks creator==approver first) — so this is 422, not 403."""
        owner_token, owner_id = _user_token_and_id(
            test_client, db_session, f"acct-own-{uuid.uuid4().hex[:8]}@example.com"
        )
        cid = _create_company(test_client, owner_token)
        cid_str = str(cid)

        accountant_token, accountant_id = _user_token_and_id(
            test_client, db_session, f"acct-self-{uuid.uuid4().hex[:8]}@example.com"
        )
        create_member_with_role(
            db_session, company_id=cid, user_id=accountant_id, role_slug="accountant"
        )
        gl = _setup_gl(db_session, cid)
        journal_id = _create_and_submit_journal(
            test_client, accountant_token, cid_str, gl
        )

        resp = test_client.post(
            _url(cid_str, f"/journals/{journal_id}/approve"),
            headers=_auth(accountant_token),
        )
        assert resp.status_code == 422, resp.text
        assert resp.json()["error"]["code"] == "SELF_APPROVAL_NOT_ALLOWED"

    def test_accountant_cannot_approve_someone_elses_journal(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """An accountant (not the creator) lacks accounting.journal.approve —
        must be 403 (ApprovalPermissionDeniedError)."""
        from modules.users_roles.constants import DEFAULT_ROLE_PERMISSIONS

        assert (
            "accounting.journal.approve" not in DEFAULT_ROLE_PERMISSIONS["accountant"]
        )

        owner_token, owner_id = _user_token_and_id(
            test_client, db_session, f"acct-cre-{uuid.uuid4().hex[:8]}@example.com"
        )
        cid = _create_company(test_client, owner_token)
        cid_str = str(cid)
        gl = _setup_gl(db_session, cid)
        journal_id = _create_and_submit_journal(test_client, owner_token, cid_str, gl)

        accountant_token, accountant_id = _user_token_and_id(
            test_client, db_session, f"acct-oth-{uuid.uuid4().hex[:8]}@example.com"
        )
        create_member_with_role(
            db_session, company_id=cid, user_id=accountant_id, role_slug="accountant"
        )

        resp = test_client.post(
            _url(cid_str, f"/journals/{journal_id}/approve"),
            headers=_auth(accountant_token),
        )
        assert resp.status_code == 403, resp.text
        assert resp.json()["error"]["code"] == "APPROVAL_PERMISSION_DENIED"


# ---------------------------------------------------------------------------
# Cross-tenant: SoD never reached — membership gate rejects first
# ---------------------------------------------------------------------------


class TestCrossTenantApprovalBlockedAtMembershipGate:
    def test_non_member_cannot_approve_journal_in_other_company(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        # Company B: owner creates + submits a journal.
        owner_b_token, _owner_b_id = _user_token_and_id(
            test_client, db_session, f"xt-ownerb-{uuid.uuid4().hex[:8]}@example.com"
        )
        cid_b = _create_company(test_client, owner_b_token)
        cid_b_str = str(cid_b)
        gl_b = _setup_gl(db_session, cid_b)
        journal_id = _create_and_submit_journal(
            test_client, owner_b_token, cid_b_str, gl_b
        )

        # A user who is a real, active member of Company A ONLY (granted
        # accounting.journal.approve there — irrelevant, wrong company).
        user_a_token, user_a_id = _user_token_and_id(
            test_client, db_session, f"xt-usera-{uuid.uuid4().hex[:8]}@example.com"
        )
        cid_a = _create_company(test_client, user_a_token)
        grant_permission_to_user(
            db_session,
            company_id=cid_a,
            user_id=user_a_id,
            permission_code="accounting.journal.approve",
            role_slug=f"xt-approver-{uuid.uuid4().hex[:8]}",
        )

        # user_a attempts to approve Company B's journal via Company B's URL —
        # user_a is not a member of B at all, so get_current_company_member
        # (router-level dependency for the whole accounting prefix) rejects
        # with 403 before SoD/permission logic in PostingEngine.approve() is
        # ever reached.
        resp = test_client.post(
            _url(cid_b_str, f"/journals/{journal_id}/approve"),
            headers=_auth(user_a_token),
        )
        assert resp.status_code == 403, resp.text
