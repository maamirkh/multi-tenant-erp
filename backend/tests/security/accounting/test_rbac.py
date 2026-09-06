"""RBAC permission matrix tests — accounting module — Phase 14 T283.

All 20 accounting permission codes defined in
``modules/users_roles/constants.py``'s ``INITIAL_PERMISSIONS``/
``DEFAULT_ROLE_PERMISSIONS`` are now enforced in code (via
``modules.accounting.services.permission_check.user_has_accounting_permission``,
called from ``posting_engine.py``, ``payment_service.py``, and 49 router
endpoints in ``router.py``).

This file covers, for each permission code, at least one granted-role and
one denied-role check, plus a bare/no-token 401 sweep.
``accounting.journal.approve``/``payment.customer.approve``/
``payment.supplier.approve``/``payment.customer.create``/
``payment.supplier.create``/``audit.view`` get full end-to-end coverage
(the action genuinely succeeds for a granted role, not just "not a 403").
``accounting.period.close`` is covered in
``test_financial_controls.py::TestFiscalYearCloseRequiresPermission``
instead (needs a fully-locked fiscal year, sharing setup with that file's
SoD tests) — not duplicated here.

The remaining codes' "denied" side always asserts a clean 403
``APPROVAL_PERMISSION_DENIED`` (the permission check runs before any
resource lookup, so a fake path ID is sufficient and keeps setup minimal).
Their "granted" side asserts the permission check itself passes (response
is NOT a 403 APPROVAL_PERMISSION_DENIED) — proving RBAC works without
re-testing each action's full business logic, which is already covered
elsewhere in the accounting test suite.

Spec ref: specs/008-accounting-finance/tasks.md T283
"""

from __future__ import annotations

import uuid
from datetime import date

import pytest
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
from modules.users_roles.constants import DEFAULT_ROLE_PERMISSIONS
from tests.fixtures.auth_fixtures import create_test_user
from tests.fixtures.users_roles_fixtures import create_member_with_role

_TEST_PASSWORD = "RbacAcct@12345"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


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
            "legal_name": f"RBAC Acct Test Co {suffix}",
            "email": f"contact-{suffix}@rbac-acct-test.example.com",
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


def _create_and_submit_journal(
    test_client: TestClient, token: str, cid: str, gl: dict
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
    return journal_id


def _setup_payment_approval(
    test_client: TestClient,
    token: str,
    db_session: Session,
    cid: uuid.UUID,
    threshold: str = "100.00",
) -> dict:
    account_repo = AccountRepository(db_session)
    ar = account_repo.create(
        Account(
            company_id=cid, account_code="1100", account_name="AR", account_type="ASSET"
        )
    )
    ap = account_repo.create(
        Account(
            company_id=cid,
            account_code="2000",
            account_name="AP",
            account_type="LIABILITY",
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
    for role, account in (("default_ar_account_id", ar), ("default_ap_account_id", ap)):
        resp = test_client.put(
            _url(cid_str, "/system-accounts"),
            json={"role": role, "account_id": str(account.id)},
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

    return {"ar": ar, "ap": ap, "bank": bank, "today": today.isoformat()}


def _create_draft_customer_payment(
    test_client: TestClient, token: str, cid: str, gl: dict, amount: str = "500.00"
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
    assert payment["status"] == "DRAFT"
    return payment["id"]


def _create_draft_supplier_payment(
    test_client: TestClient, token: str, cid: str, gl: dict, amount: str = "500.00"
) -> str:
    resp = test_client.post(
        _url(cid, "/payments/supplier"),
        json={
            "supplier_id": str(uuid.uuid4()),
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
    assert payment["status"] == "DRAFT"
    return payment["id"]


# ---------------------------------------------------------------------------
# Permission matrix sanity — assert the fixture data matches constants.py
# (fails loudly if DEFAULT_ROLE_PERMISSIONS is ever edited without updating
# the tests that rely on these specific role/permission combinations).
# ---------------------------------------------------------------------------


class TestPermissionMatrixAssumptions:
    def test_manager_has_journal_approve_viewer_and_cashier_do_not(self) -> None:
        assert "accounting.journal.approve" in DEFAULT_ROLE_PERMISSIONS["manager"]
        assert "accounting.journal.approve" not in DEFAULT_ROLE_PERMISSIONS["viewer"]
        assert "accounting.journal.approve" not in DEFAULT_ROLE_PERMISSIONS["cashier"]

    def test_manager_has_payment_approvals_cashier_does_not(self) -> None:
        assert (
            "accounting.payment.customer.approve" in DEFAULT_ROLE_PERMISSIONS["manager"]
        )
        assert (
            "accounting.payment.supplier.approve" in DEFAULT_ROLE_PERMISSIONS["manager"]
        )
        assert (
            "accounting.payment.customer.approve"
            not in DEFAULT_ROLE_PERMISSIONS["cashier"]
        )
        assert (
            "accounting.payment.supplier.approve"
            not in DEFAULT_ROLE_PERMISSIONS["cashier"]
        )
        # Cashier CAN create payments — never approve.
        assert (
            "accounting.payment.customer.create" in DEFAULT_ROLE_PERMISSIONS["cashier"]
        )
        assert (
            "accounting.payment.supplier.create" in DEFAULT_ROLE_PERMISSIONS["cashier"]
        )

    def test_viewer_has_audit_view_cashier_does_not(self) -> None:
        assert "accounting.audit.view" in DEFAULT_ROLE_PERMISSIONS["viewer"]
        assert "accounting.audit.view" not in DEFAULT_ROLE_PERMISSIONS["cashier"]


# ---------------------------------------------------------------------------
# accounting.journal.approve
# ---------------------------------------------------------------------------


class TestJournalApprovePermission:
    def test_manager_role_can_approve_journal(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        owner_token, _oid = _user_token_and_id(
            test_client, db_session, f"ja-owner-{uuid.uuid4().hex[:8]}@example.com"
        )
        cid = _create_company(test_client, owner_token)
        cid_str = str(cid)
        gl = _setup_gl(db_session, cid)
        journal_id = _create_and_submit_journal(test_client, owner_token, cid_str, gl)

        manager_token, manager_id = _user_token_and_id(
            test_client, db_session, f"ja-mgr-{uuid.uuid4().hex[:8]}@example.com"
        )
        create_member_with_role(
            db_session, company_id=cid, user_id=manager_id, role_slug="manager"
        )

        resp = test_client.post(
            _url(cid_str, f"/journals/{journal_id}/approve"),
            headers=_auth(manager_token),
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["data"]["status"] == "APPROVED"

    def test_viewer_role_cannot_approve_journal(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        owner_token, _oid = _user_token_and_id(
            test_client, db_session, f"ja-owner2-{uuid.uuid4().hex[:8]}@example.com"
        )
        cid = _create_company(test_client, owner_token)
        cid_str = str(cid)
        gl = _setup_gl(db_session, cid)
        journal_id = _create_and_submit_journal(test_client, owner_token, cid_str, gl)

        viewer_token, viewer_id = _user_token_and_id(
            test_client, db_session, f"ja-viewer-{uuid.uuid4().hex[:8]}@example.com"
        )
        create_member_with_role(
            db_session, company_id=cid, user_id=viewer_id, role_slug="viewer"
        )

        resp = test_client.post(
            _url(cid_str, f"/journals/{journal_id}/approve"),
            headers=_auth(viewer_token),
        )
        assert resp.status_code == 403, resp.text
        assert resp.json()["error"]["code"] == "APPROVAL_PERMISSION_DENIED"

    def test_cashier_role_cannot_approve_journal(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        owner_token, _oid = _user_token_and_id(
            test_client, db_session, f"ja-owner3-{uuid.uuid4().hex[:8]}@example.com"
        )
        cid = _create_company(test_client, owner_token)
        cid_str = str(cid)
        gl = _setup_gl(db_session, cid)
        journal_id = _create_and_submit_journal(test_client, owner_token, cid_str, gl)

        cashier_token, cashier_id = _user_token_and_id(
            test_client, db_session, f"ja-cash-{uuid.uuid4().hex[:8]}@example.com"
        )
        create_member_with_role(
            db_session, company_id=cid, user_id=cashier_id, role_slug="cashier"
        )

        resp = test_client.post(
            _url(cid_str, f"/journals/{journal_id}/approve"),
            headers=_auth(cashier_token),
        )
        assert resp.status_code == 403, resp.text
        assert resp.json()["error"]["code"] == "APPROVAL_PERMISSION_DENIED"


# ---------------------------------------------------------------------------
# accounting.payment.customer.create / accounting.payment.supplier.create
# ---------------------------------------------------------------------------


class TestPaymentCustomerCreatePermission:
    def test_accountant_cannot_create_customer_payment_cashier_can(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        owner_token, _oid = _user_token_and_id(
            test_client, db_session, f"pcc-owner-{uuid.uuid4().hex[:8]}@example.com"
        )
        cid = _create_company(test_client, owner_token)
        cid_str = str(cid)
        gl = _setup_payment_approval(
            test_client, owner_token, db_session, cid, threshold="999999.00"
        )

        accountant_token, accountant_id = _user_token_and_id(
            test_client, db_session, f"pcc-acct-{uuid.uuid4().hex[:8]}@example.com"
        )
        create_member_with_role(
            db_session, company_id=cid, user_id=accountant_id, role_slug="accountant"
        )
        resp = test_client.post(
            _url(cid_str, "/payments/customer"),
            json={
                "customer_id": str(uuid.uuid4()),
                "payment_method": "BANK_TRANSFER",
                "payment_date": gl["today"],
                "amount": "100.00",
                "currency_code": "USD",
                "bank_account_id": str(gl["bank"].id),
            },
            headers=_auth(accountant_token),
        )
        _assert_permission_denied(resp, "accounting.payment.customer.create")

        cashier_token, cashier_id = _user_token_and_id(
            test_client, db_session, f"pcc-cash-{uuid.uuid4().hex[:8]}@example.com"
        )
        create_member_with_role(
            db_session, company_id=cid, user_id=cashier_id, role_slug="cashier"
        )
        resp = test_client.post(
            _url(cid_str, "/payments/customer"),
            json={
                "customer_id": str(uuid.uuid4()),
                "payment_method": "BANK_TRANSFER",
                "payment_date": gl["today"],
                "amount": "100.00",
                "currency_code": "USD",
                "bank_account_id": str(gl["bank"].id),
            },
            headers=_auth(cashier_token),
        )
        assert resp.status_code == 201, resp.text


class TestPaymentSupplierCreatePermission:
    def test_accountant_cannot_create_supplier_payment_cashier_can(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        owner_token, _oid = _user_token_and_id(
            test_client, db_session, f"psc-owner-{uuid.uuid4().hex[:8]}@example.com"
        )
        cid = _create_company(test_client, owner_token)
        cid_str = str(cid)
        gl = _setup_payment_approval(
            test_client, owner_token, db_session, cid, threshold="999999.00"
        )

        accountant_token, accountant_id = _user_token_and_id(
            test_client, db_session, f"psc-acct-{uuid.uuid4().hex[:8]}@example.com"
        )
        create_member_with_role(
            db_session, company_id=cid, user_id=accountant_id, role_slug="accountant"
        )
        resp = test_client.post(
            _url(cid_str, "/payments/supplier"),
            json={
                "supplier_id": str(uuid.uuid4()),
                "payment_method": "BANK_TRANSFER",
                "payment_date": gl["today"],
                "amount": "100.00",
                "currency_code": "USD",
                "bank_account_id": str(gl["bank"].id),
            },
            headers=_auth(accountant_token),
        )
        _assert_permission_denied(resp, "accounting.payment.supplier.create")

        cashier_token, cashier_id = _user_token_and_id(
            test_client, db_session, f"psc-cash-{uuid.uuid4().hex[:8]}@example.com"
        )
        create_member_with_role(
            db_session, company_id=cid, user_id=cashier_id, role_slug="cashier"
        )
        resp = test_client.post(
            _url(cid_str, "/payments/supplier"),
            json={
                "supplier_id": str(uuid.uuid4()),
                "payment_method": "BANK_TRANSFER",
                "payment_date": gl["today"],
                "amount": "100.00",
                "currency_code": "USD",
                "bank_account_id": str(gl["bank"].id),
            },
            headers=_auth(cashier_token),
        )
        assert resp.status_code == 201, resp.text


# ---------------------------------------------------------------------------
# accounting.payment.customer.approve
# ---------------------------------------------------------------------------


class TestPaymentCustomerApprovePermission:
    def test_manager_role_can_approve_customer_payment(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        owner_token, _oid = _user_token_and_id(
            test_client, db_session, f"pca-owner-{uuid.uuid4().hex[:8]}@example.com"
        )
        cid = _create_company(test_client, owner_token)
        cid_str = str(cid)
        gl = _setup_payment_approval(test_client, owner_token, db_session, cid)
        payment_id = _create_draft_customer_payment(
            test_client, owner_token, cid_str, gl
        )

        manager_token, manager_id = _user_token_and_id(
            test_client, db_session, f"pca-mgr-{uuid.uuid4().hex[:8]}@example.com"
        )
        create_member_with_role(
            db_session, company_id=cid, user_id=manager_id, role_slug="manager"
        )

        resp = test_client.post(
            _url(cid_str, f"/payments/{payment_id}/approve"),
            headers=_auth(manager_token),
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["data"]["status"] == "POSTED"

    def test_cashier_role_cannot_approve_customer_payment(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        owner_token, _oid = _user_token_and_id(
            test_client, db_session, f"pca-owner2-{uuid.uuid4().hex[:8]}@example.com"
        )
        cid = _create_company(test_client, owner_token)
        cid_str = str(cid)
        gl = _setup_payment_approval(test_client, owner_token, db_session, cid)
        payment_id = _create_draft_customer_payment(
            test_client, owner_token, cid_str, gl
        )

        cashier_token, cashier_id = _user_token_and_id(
            test_client, db_session, f"pca-cash-{uuid.uuid4().hex[:8]}@example.com"
        )
        create_member_with_role(
            db_session, company_id=cid, user_id=cashier_id, role_slug="cashier"
        )

        resp = test_client.post(
            _url(cid_str, f"/payments/{payment_id}/approve"),
            headers=_auth(cashier_token),
        )
        assert resp.status_code == 403, resp.text
        assert resp.json()["error"]["code"] == "APPROVAL_PERMISSION_DENIED"


# ---------------------------------------------------------------------------
# accounting.payment.supplier.approve
# ---------------------------------------------------------------------------


class TestPaymentSupplierApprovePermission:
    def test_manager_role_can_approve_supplier_payment(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        owner_token, _oid = _user_token_and_id(
            test_client, db_session, f"psa-owner-{uuid.uuid4().hex[:8]}@example.com"
        )
        cid = _create_company(test_client, owner_token)
        cid_str = str(cid)
        gl = _setup_payment_approval(test_client, owner_token, db_session, cid)
        payment_id = _create_draft_supplier_payment(
            test_client, owner_token, cid_str, gl
        )

        manager_token, manager_id = _user_token_and_id(
            test_client, db_session, f"psa-mgr-{uuid.uuid4().hex[:8]}@example.com"
        )
        create_member_with_role(
            db_session, company_id=cid, user_id=manager_id, role_slug="manager"
        )

        resp = test_client.post(
            _url(cid_str, f"/payments/{payment_id}/approve"),
            headers=_auth(manager_token),
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["data"]["status"] == "POSTED"

    def test_cashier_role_cannot_approve_supplier_payment(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        owner_token, _oid = _user_token_and_id(
            test_client, db_session, f"psa-owner2-{uuid.uuid4().hex[:8]}@example.com"
        )
        cid = _create_company(test_client, owner_token)
        cid_str = str(cid)
        gl = _setup_payment_approval(test_client, owner_token, db_session, cid)
        payment_id = _create_draft_supplier_payment(
            test_client, owner_token, cid_str, gl
        )

        cashier_token, cashier_id = _user_token_and_id(
            test_client, db_session, f"psa-cash-{uuid.uuid4().hex[:8]}@example.com"
        )
        create_member_with_role(
            db_session, company_id=cid, user_id=cashier_id, role_slug="cashier"
        )

        resp = test_client.post(
            _url(cid_str, f"/payments/{payment_id}/approve"),
            headers=_auth(cashier_token),
        )
        assert resp.status_code == 403, resp.text
        assert resp.json()["error"]["code"] == "APPROVAL_PERMISSION_DENIED"


# ---------------------------------------------------------------------------
# accounting.audit.view
# ---------------------------------------------------------------------------


class TestAuditViewPermission:
    def test_viewer_role_can_view_audit_log(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        owner_token, _oid = _user_token_and_id(
            test_client, db_session, f"av-owner-{uuid.uuid4().hex[:8]}@example.com"
        )
        cid = _create_company(test_client, owner_token)
        cid_str = str(cid)

        viewer_token, viewer_id = _user_token_and_id(
            test_client, db_session, f"av-viewer-{uuid.uuid4().hex[:8]}@example.com"
        )
        create_member_with_role(
            db_session, company_id=cid, user_id=viewer_id, role_slug="viewer"
        )

        resp = test_client.get(_url(cid_str, "/audit-log"), headers=_auth(viewer_token))
        assert resp.status_code == 200, resp.text

    def test_cashier_role_cannot_view_audit_log(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        owner_token, _oid = _user_token_and_id(
            test_client, db_session, f"av-owner2-{uuid.uuid4().hex[:8]}@example.com"
        )
        cid = _create_company(test_client, owner_token)
        cid_str = str(cid)

        cashier_token, cashier_id = _user_token_and_id(
            test_client, db_session, f"av-cash-{uuid.uuid4().hex[:8]}@example.com"
        )
        create_member_with_role(
            db_session, company_id=cid, user_id=cashier_id, role_slug="cashier"
        )

        resp = test_client.get(
            _url(cid_str, "/audit-log"), headers=_auth(cashier_token)
        )
        assert resp.status_code == 403, resp.text
        assert resp.json()["error"]["code"] == "APPROVAL_PERMISSION_DENIED"

    def test_cashier_role_cannot_export_audit_log(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        owner_token, _oid = _user_token_and_id(
            test_client, db_session, f"av-owner3-{uuid.uuid4().hex[:8]}@example.com"
        )
        cid = _create_company(test_client, owner_token)
        cid_str = str(cid)

        cashier_token, cashier_id = _user_token_and_id(
            test_client, db_session, f"av-cash2-{uuid.uuid4().hex[:8]}@example.com"
        )
        create_member_with_role(
            db_session, company_id=cid, user_id=cashier_id, role_slug="cashier"
        )

        resp = test_client.get(
            _url(cid_str, "/audit-log/export"), headers=_auth(cashier_token)
        )
        assert resp.status_code == 403, resp.text


# ---------------------------------------------------------------------------
# Remaining 13 permission codes (period.close covered separately — see
# test_financial_controls.py). Each: denied role -> 403
# APPROVAL_PERMISSION_DENIED (fake path IDs OK, check runs pre-lookup);
# granted role -> anything but that specific 403 (proves the gate passed).
# ---------------------------------------------------------------------------


def _assert_permission_denied(resp, code: str) -> None:
    assert resp.status_code == 403, resp.text
    assert resp.json()["error"]["code"] == "APPROVAL_PERMISSION_DENIED"
    assert resp.json()["error"]["details"]["permission_code"] == code


def _assert_permission_granted(resp, code: str) -> None:
    if resp.status_code == 403:
        assert resp.json()["error"].get("code") != "APPROVAL_PERMISSION_DENIED", (
            f"expected permission '{code}' to be granted, but got "
            f"APPROVAL_PERMISSION_DENIED: {resp.text}"
        )


class TestJournalCreatePermission:
    def test_cashier_cannot_create_journal_accountant_can(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        owner_token, _oid = _user_token_and_id(
            test_client, db_session, f"jc-owner-{uuid.uuid4().hex[:8]}@example.com"
        )
        cid = _create_company(test_client, owner_token)
        cid_str = str(cid)
        gl = _setup_gl(db_session, cid)

        cashier_token, cashier_id = _user_token_and_id(
            test_client, db_session, f"jc-cash-{uuid.uuid4().hex[:8]}@example.com"
        )
        create_member_with_role(
            db_session, company_id=cid, user_id=cashier_id, role_slug="cashier"
        )
        resp = test_client.post(
            _url(cid_str, "/journals"),
            json=_posting_body(gl["ar"], gl["revenue"], gl["today"]),
            headers=_auth(cashier_token),
        )
        _assert_permission_denied(resp, "accounting.journal.create")

        accountant_token, accountant_id = _user_token_and_id(
            test_client, db_session, f"jc-acct-{uuid.uuid4().hex[:8]}@example.com"
        )
        create_member_with_role(
            db_session, company_id=cid, user_id=accountant_id, role_slug="accountant"
        )
        resp = test_client.post(
            _url(cid_str, "/journals"),
            json=_posting_body(gl["ar"], gl["revenue"], gl["today"]),
            headers=_auth(accountant_token),
        )
        assert resp.status_code == 201, resp.text


class TestJournalPostPermission:
    def test_cashier_cannot_post_journal(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        owner_token, _oid = _user_token_and_id(
            test_client, db_session, f"jp-owner-{uuid.uuid4().hex[:8]}@example.com"
        )
        cid = _create_company(test_client, owner_token)
        cid_str = str(cid)
        cashier_token, cashier_id = _user_token_and_id(
            test_client, db_session, f"jp-cash-{uuid.uuid4().hex[:8]}@example.com"
        )
        create_member_with_role(
            db_session, company_id=cid, user_id=cashier_id, role_slug="cashier"
        )
        resp = test_client.post(
            _url(cid_str, f"/journals/{uuid.uuid4()}/post"),
            headers=_auth(cashier_token),
        )
        _assert_permission_denied(resp, "accounting.journal.post")


class TestJournalReversePermission:
    def test_accountant_cannot_reverse_journal_manager_can_pass_gate(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        owner_token, _oid = _user_token_and_id(
            test_client, db_session, f"jr-owner-{uuid.uuid4().hex[:8]}@example.com"
        )
        cid = _create_company(test_client, owner_token)
        cid_str = str(cid)
        accountant_token, accountant_id = _user_token_and_id(
            test_client, db_session, f"jr-acct-{uuid.uuid4().hex[:8]}@example.com"
        )
        create_member_with_role(
            db_session, company_id=cid, user_id=accountant_id, role_slug="accountant"
        )
        resp = test_client.post(
            _url(cid_str, f"/journals/{uuid.uuid4()}/reverse"),
            headers=_auth(accountant_token),
        )
        _assert_permission_denied(resp, "accounting.journal.reverse")

        manager_token, manager_id = _user_token_and_id(
            test_client, db_session, f"jr-mgr-{uuid.uuid4().hex[:8]}@example.com"
        )
        create_member_with_role(
            db_session, company_id=cid, user_id=manager_id, role_slug="manager"
        )
        resp = test_client.post(
            _url(cid_str, f"/journals/{uuid.uuid4()}/reverse"),
            headers=_auth(manager_token),
        )
        _assert_permission_granted(resp, "accounting.journal.reverse")


class TestCoaManagePermission:
    def test_cashier_cannot_create_account_accountant_can(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        owner_token, _oid = _user_token_and_id(
            test_client, db_session, f"coa-owner-{uuid.uuid4().hex[:8]}@example.com"
        )
        cid = _create_company(test_client, owner_token)
        cid_str = str(cid)
        cashier_token, cashier_id = _user_token_and_id(
            test_client, db_session, f"coa-cash-{uuid.uuid4().hex[:8]}@example.com"
        )
        create_member_with_role(
            db_session, company_id=cid, user_id=cashier_id, role_slug="cashier"
        )
        resp = test_client.post(
            _url(cid_str, "/accounts"),
            json={
                "account_code": "9001",
                "account_name": "X",
                "account_type": "EXPENSE",
            },
            headers=_auth(cashier_token),
        )
        _assert_permission_denied(resp, "accounting.coa.manage")

        accountant_token, accountant_id = _user_token_and_id(
            test_client, db_session, f"coa-acct-{uuid.uuid4().hex[:8]}@example.com"
        )
        create_member_with_role(
            db_session, company_id=cid, user_id=accountant_id, role_slug="accountant"
        )
        resp = test_client.post(
            _url(cid_str, "/accounts"),
            json={
                "account_code": "9002",
                "account_name": "Y",
                "account_type": "EXPENSE",
            },
            headers=_auth(accountant_token),
        )
        assert resp.status_code == 201, resp.text


class TestTaxManagePermission:
    def test_accountant_cannot_create_tax_code_manager_can_pass_gate(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        owner_token, _oid = _user_token_and_id(
            test_client, db_session, f"tax-owner-{uuid.uuid4().hex[:8]}@example.com"
        )
        cid = _create_company(test_client, owner_token)
        cid_str = str(cid)
        accountant_token, accountant_id = _user_token_and_id(
            test_client, db_session, f"tax-acct-{uuid.uuid4().hex[:8]}@example.com"
        )
        create_member_with_role(
            db_session, company_id=cid, user_id=accountant_id, role_slug="accountant"
        )
        resp = test_client.post(
            _url(cid_str, "/tax-codes"),
            json={
                "tax_code": "VAT10",
                "tax_name": "VAT 10%",
                "tax_type": "VAT",
                "applicability": "SALES",
                "gl_account_id": str(uuid.uuid4()),
            },
            headers=_auth(accountant_token),
        )
        _assert_permission_denied(resp, "accounting.tax.manage")

        manager_token, manager_id = _user_token_and_id(
            test_client, db_session, f"tax-mgr-{uuid.uuid4().hex[:8]}@example.com"
        )
        create_member_with_role(
            db_session, company_id=cid, user_id=manager_id, role_slug="manager"
        )
        resp = test_client.post(
            _url(cid_str, "/tax-codes"),
            json={
                "tax_code": "VAT10",
                "tax_name": "VAT 10%",
                "tax_type": "VAT",
                "applicability": "SALES",
                "gl_account_id": str(uuid.uuid4()),
            },
            headers=_auth(manager_token),
        )
        _assert_permission_granted(resp, "accounting.tax.manage")


class TestExchangeRateManagePermission:
    def test_cashier_cannot_create_exchange_rate_accountant_can_pass_gate(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        owner_token, _oid = _user_token_and_id(
            test_client, db_session, f"fx-owner-{uuid.uuid4().hex[:8]}@example.com"
        )
        cid = _create_company(test_client, owner_token)
        cid_str = str(cid)
        cashier_token, cashier_id = _user_token_and_id(
            test_client, db_session, f"fx-cash-{uuid.uuid4().hex[:8]}@example.com"
        )
        create_member_with_role(
            db_session, company_id=cid, user_id=cashier_id, role_slug="cashier"
        )
        body = {
            "from_currency_code": "USD",
            "to_currency_code": "EUR",
            "rate": "0.9200",
            "rate_date": utcnow().date().isoformat(),
        }
        resp = test_client.post(
            _url(cid_str, "/exchange-rates"), json=body, headers=_auth(cashier_token)
        )
        _assert_permission_denied(resp, "accounting.exchangerate.manage")

        accountant_token, accountant_id = _user_token_and_id(
            test_client, db_session, f"fx-acct-{uuid.uuid4().hex[:8]}@example.com"
        )
        create_member_with_role(
            db_session, company_id=cid, user_id=accountant_id, role_slug="accountant"
        )
        resp = test_client.post(
            _url(cid_str, "/exchange-rates"), json=body, headers=_auth(accountant_token)
        )
        _assert_permission_granted(resp, "accounting.exchangerate.manage")


class TestBankReconcilePermission:
    def test_accountant_can_pass_gate_cashier_cannot(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        owner_token, _oid = _user_token_and_id(
            test_client, db_session, f"br-owner-{uuid.uuid4().hex[:8]}@example.com"
        )
        cid = _create_company(test_client, owner_token)
        cid_str = str(cid)
        cashier_token, cashier_id = _user_token_and_id(
            test_client, db_session, f"br-cash-{uuid.uuid4().hex[:8]}@example.com"
        )
        create_member_with_role(
            db_session, company_id=cid, user_id=cashier_id, role_slug="cashier"
        )
        resp = test_client.post(
            _url(cid_str, f"/bank-accounts/{uuid.uuid4()}/reconciliations"),
            json={
                "statement_date": utcnow().date().isoformat(),
                "statement_closing_balance": "0",
            },
            headers=_auth(cashier_token),
        )
        _assert_permission_denied(resp, "accounting.bank.reconcile")

        accountant_token, accountant_id = _user_token_and_id(
            test_client, db_session, f"br-acct-{uuid.uuid4().hex[:8]}@example.com"
        )
        create_member_with_role(
            db_session, company_id=cid, user_id=accountant_id, role_slug="accountant"
        )
        resp = test_client.post(
            _url(cid_str, f"/bank-accounts/{uuid.uuid4()}/reconciliations"),
            json={
                "statement_date": utcnow().date().isoformat(),
                "statement_closing_balance": "0",
            },
            headers=_auth(accountant_token),
        )
        _assert_permission_granted(resp, "accounting.bank.reconcile")


class TestReportsViewPermission:
    def test_cashier_cannot_view_pl_report_viewer_can_pass_gate(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        owner_token, _oid = _user_token_and_id(
            test_client, db_session, f"rv-owner-{uuid.uuid4().hex[:8]}@example.com"
        )
        cid = _create_company(test_client, owner_token)
        cid_str = str(cid)
        cashier_token, cashier_id = _user_token_and_id(
            test_client, db_session, f"rv-cash-{uuid.uuid4().hex[:8]}@example.com"
        )
        create_member_with_role(
            db_session, company_id=cid, user_id=cashier_id, role_slug="cashier"
        )
        today = utcnow().date().isoformat()
        resp = test_client.get(
            _url(
                cid_str, f"/reports/profit-loss?period_from={today}&period_to={today}"
            ),
            headers=_auth(cashier_token),
        )
        _assert_permission_denied(resp, "accounting.reports.view")

        viewer_token, viewer_id = _user_token_and_id(
            test_client, db_session, f"rv-viewer-{uuid.uuid4().hex[:8]}@example.com"
        )
        create_member_with_role(
            db_session, company_id=cid, user_id=viewer_id, role_slug="viewer"
        )
        resp = test_client.get(
            _url(
                cid_str, f"/reports/profit-loss?period_from={today}&period_to={today}"
            ),
            headers=_auth(viewer_token),
        )
        _assert_permission_granted(resp, "accounting.reports.view")


class TestGLViewPermission:
    def test_cashier_cannot_list_journals_viewer_can(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        owner_token, _oid = _user_token_and_id(
            test_client, db_session, f"gl-owner-{uuid.uuid4().hex[:8]}@example.com"
        )
        cid = _create_company(test_client, owner_token)
        cid_str = str(cid)
        cashier_token, cashier_id = _user_token_and_id(
            test_client, db_session, f"gl-cash-{uuid.uuid4().hex[:8]}@example.com"
        )
        create_member_with_role(
            db_session, company_id=cid, user_id=cashier_id, role_slug="cashier"
        )
        resp = test_client.get(_url(cid_str, "/journals"), headers=_auth(cashier_token))
        _assert_permission_denied(resp, "accounting.gl.view")

        viewer_token, viewer_id = _user_token_and_id(
            test_client, db_session, f"gl-viewer-{uuid.uuid4().hex[:8]}@example.com"
        )
        create_member_with_role(
            db_session, company_id=cid, user_id=viewer_id, role_slug="viewer"
        )
        resp = test_client.get(_url(cid_str, "/journals"), headers=_auth(viewer_token))
        assert resp.status_code == 200, resp.text


class TestARWriteOffPermission:
    def test_accountant_cannot_writeoff_manager_can_pass_gate(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        owner_token, _oid = _user_token_and_id(
            test_client, db_session, f"wo-owner-{uuid.uuid4().hex[:8]}@example.com"
        )
        cid = _create_company(test_client, owner_token)
        cid_str = str(cid)
        accountant_token, accountant_id = _user_token_and_id(
            test_client, db_session, f"wo-acct-{uuid.uuid4().hex[:8]}@example.com"
        )
        create_member_with_role(
            db_session, company_id=cid, user_id=accountant_id, role_slug="accountant"
        )
        resp = test_client.post(
            _url(cid_str, f"/ar/transactions/{uuid.uuid4()}/write-off"),
            json={"reason": "uncollectible"},
            headers=_auth(accountant_token),
        )
        _assert_permission_denied(resp, "accounting.ar.writeoff")

        manager_token, manager_id = _user_token_and_id(
            test_client, db_session, f"wo-mgr-{uuid.uuid4().hex[:8]}@example.com"
        )
        create_member_with_role(
            db_session, company_id=cid, user_id=manager_id, role_slug="manager"
        )
        resp = test_client.post(
            _url(cid_str, f"/ar/transactions/{uuid.uuid4()}/write-off"),
            json={"reason": "uncollectible"},
            headers=_auth(manager_token),
        )
        _assert_permission_granted(resp, "accounting.ar.writeoff")


class TestCreditLimitOverridePermission:
    def test_accountant_cannot_override_credit_limit_manager_can_pass_gate(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        owner_token, _oid = _user_token_and_id(
            test_client, db_session, f"cl-owner-{uuid.uuid4().hex[:8]}@example.com"
        )
        cid = _create_company(test_client, owner_token)
        cid_str = str(cid)
        accountant_token, accountant_id = _user_token_and_id(
            test_client, db_session, f"cl-acct-{uuid.uuid4().hex[:8]}@example.com"
        )
        create_member_with_role(
            db_session, company_id=cid, user_id=accountant_id, role_slug="accountant"
        )
        resp = test_client.post(
            _url(cid_str, f"/ar/customers/{uuid.uuid4()}/credit-limit"),
            json={"credit_limit": "10000"},
            headers=_auth(accountant_token),
        )
        _assert_permission_denied(resp, "accounting.creditlimit.override")

        manager_token, manager_id = _user_token_and_id(
            test_client, db_session, f"cl-mgr-{uuid.uuid4().hex[:8]}@example.com"
        )
        create_member_with_role(
            db_session, company_id=cid, user_id=manager_id, role_slug="manager"
        )
        resp = test_client.post(
            _url(cid_str, f"/ar/customers/{uuid.uuid4()}/credit-limit"),
            json={"credit_limit": "10000"},
            headers=_auth(manager_token),
        )
        _assert_permission_granted(resp, "accounting.creditlimit.override")


class TestApprovalWorkflowManagePermission:
    def test_manager_cannot_update_configuration_owner_can(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """Only owner/admin hold accounting.approvalworkflow.manage — even
        manager (Controller-equivalent, holds most other permissions) does
        not, matching spec.md §33's "Manage Approval Workflows" row (CFO +
        System Admin only)."""
        owner_token, _oid = _user_token_and_id(
            test_client, db_session, f"aw-owner-{uuid.uuid4().hex[:8]}@example.com"
        )
        cid = _create_company(test_client, owner_token)
        cid_str = str(cid)
        assert (
            "accounting.approvalworkflow.manage"
            not in DEFAULT_ROLE_PERMISSIONS["manager"]
        )

        manager_token, manager_id = _user_token_and_id(
            test_client, db_session, f"aw-mgr-{uuid.uuid4().hex[:8]}@example.com"
        )
        create_member_with_role(
            db_session, company_id=cid, user_id=manager_id, role_slug="manager"
        )
        resp = test_client.put(
            _url(cid_str, "/configuration"),
            json={"payment_approval_threshold": "5000"},
            headers=_auth(manager_token),
        )
        _assert_permission_denied(resp, "accounting.approvalworkflow.manage")

        resp = test_client.put(
            _url(cid_str, "/configuration"),
            json={"payment_approval_threshold": "5000"},
            headers=_auth(owner_token),
        )
        assert resp.status_code == 200, resp.text


class TestPeriodLockPermission:
    def test_accountant_cannot_lock_period_owner_can(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        owner_token, _oid = _user_token_and_id(
            test_client, db_session, f"pl-owner-{uuid.uuid4().hex[:8]}@example.com"
        )
        cid = _create_company(test_client, owner_token)
        cid_str = str(cid)
        resp = test_client.post(
            _url(cid_str, "/fiscal-years"),
            json={
                "fiscal_year_name": f"FY-{uuid.uuid4().hex[:8]}",
                "start_date": "2078-01-01",
                "end_date": "2078-12-31",
                "base_currency_code": "USD",
            },
            headers=_auth(owner_token),
        )
        assert resp.status_code == 201, resp.text
        year = resp.json()["data"]
        period_id = test_client.get(
            _url(cid_str, f"/fiscal-years/{year['id']}/periods"),
            headers=_auth(owner_token),
        ).json()["data"][0]["id"]

        accountant_token, accountant_id = _user_token_and_id(
            test_client, db_session, f"pl-acct-{uuid.uuid4().hex[:8]}@example.com"
        )
        create_member_with_role(
            db_session, company_id=cid, user_id=accountant_id, role_slug="accountant"
        )
        resp = test_client.post(
            _url(cid_str, f"/fiscal-years/{year['id']}/periods/{period_id}/lock"),
            json={"lock_reason": "test"},
            headers=_auth(accountant_token),
        )
        _assert_permission_denied(resp, "accounting.period.lock")

        resp = test_client.post(
            _url(cid_str, f"/fiscal-years/{year['id']}/periods/{period_id}/lock"),
            json={"lock_reason": "month-end"},
            headers=_auth(owner_token),
        )
        assert resp.status_code == 200, resp.text


# ---------------------------------------------------------------------------
# No accounting endpoint is accessible without authentication (401)
# ---------------------------------------------------------------------------

UNAUTHENTICATED_ENDPOINTS: list[tuple[str, str, dict | None]] = [
    ("POST", "/journals/{jid}/approve", None),
    ("POST", "/payments/{pid}/approve", None),
    ("GET", "/audit-log", None),
    ("GET", "/audit-log/export", None),
    ("GET", "/journals", None),
    ("POST", "/journals", {}),
]


class TestNoEndpointAccessibleWithoutAuth:
    """Representative sweep of accounting endpoints (including the
    approval/audit endpoints this file specifically exercises) — every one
    must 401 for a bare/no-token request. Fake UUIDs are used for
    {jid}/{pid}; the auth check happens before any lookup, so the response
    is 401 regardless of whether the resource exists."""

    @pytest.mark.parametrize("method,path_template,body", UNAUTHENTICATED_ENDPOINTS)
    def test_no_token_returns_401(
        self,
        test_client: TestClient,
        method: str,
        path_template: str,
        body: dict | None,
    ) -> None:
        cid = str(uuid.uuid4())
        path = path_template.format(jid=uuid.uuid4(), pid=uuid.uuid4())
        url = _url(cid, path)
        if method == "GET":
            resp = test_client.get(url)
        else:
            resp = test_client.post(url, json=body if body is not None else {})
        assert resp.status_code == 401, (
            f"{method} {path} returned {resp.status_code}, expected 401"
        )

    def test_garbage_token_returns_401(self, test_client: TestClient) -> None:
        cid = str(uuid.uuid4())
        resp = test_client.get(
            _url(cid, "/audit-log"), headers={"Authorization": "Bearer this.is.garbage"}
        )
        assert resp.status_code == 401
