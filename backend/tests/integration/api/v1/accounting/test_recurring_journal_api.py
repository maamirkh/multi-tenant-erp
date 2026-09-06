"""API integration tests for Recurring Journal Template endpoints — Phase 5.

Tests (tasks.md T131):
  - CRUD (create, list, get detail, update)
  - Activate / deactivate
  - Execution history
  - Batch posting endpoint (T122)
  - Cross-tenant isolation
  - 401 enforcement

Spec ref: specs/008-accounting-finance/tasks.md T131
"""

from __future__ import annotations

import uuid
from datetime import date

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
            "legal_name": f"Recurring Test Co {suffix}",
            "email": f"contact-{suffix}@recurring-test.example.com",
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
    rent = account_repo.create(
        Account(
            company_id=company_id,
            account_code="6100",
            account_name="Rent",
            account_type="EXPENSE",
        )
    )
    cash = account_repo.create(
        Account(
            company_id=company_id,
            account_code="1000",
            account_name="Cash",
            account_type="ASSET",
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
    return {"rent": str(rent.id), "cash": str(cash.id), "today": today.isoformat()}


def _template_body(gl: dict, **overrides) -> dict:
    body = {
        "template_name": "Monthly Rent",
        "frequency": "MONTHLY",
        "start_date": gl["today"],
        "auto_post": True,
        "currency_code": "USD",
        "lines": [
            {"account_id": gl["rent"], "debit_amount": "1500.00", "credit_amount": "0"},
            {"account_id": gl["cash"], "debit_amount": "0", "credit_amount": "1500.00"},
        ],
    }
    body.update(overrides)
    return body


class TestUnauthenticated:
    def test_recurring_journals_requires_auth(self, test_client: TestClient) -> None:
        resp = test_client.get(_url(str(uuid.uuid4()), "/recurring-journals"))
        assert resp.status_code == 401


class TestRecurringTemplateCRUD:
    def test_create_and_get_detail(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        token = _user_token(test_client, db_session, "recurring_create@example.com")
        cid = str(_create_company(test_client, token))
        gl = _setup_gl(db_session, uuid.UUID(cid))

        resp = test_client.post(
            _url(cid, "/recurring-journals"),
            json=_template_body(gl),
            headers=_auth(token),
        )
        assert resp.status_code == 201, resp.text
        template = resp.json()["data"]
        assert template["is_active"] is True
        assert len(template["lines"]) == 2
        template_id = template["id"]

        resp = test_client.get(
            _url(cid, f"/recurring-journals/{template_id}"), headers=_auth(token)
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["template_name"] == "Monthly Rent"

    def test_list_templates(self, test_client: TestClient, db_session: Session) -> None:
        token = _user_token(test_client, db_session, "recurring_list@example.com")
        cid = str(_create_company(test_client, token))
        gl = _setup_gl(db_session, uuid.UUID(cid))
        test_client.post(
            _url(cid, "/recurring-journals"),
            json=_template_body(gl),
            headers=_auth(token),
        )

        resp = test_client.get(_url(cid, "/recurring-journals"), headers=_auth(token))
        assert resp.status_code == 200
        assert len(resp.json()["data"]) == 1

    def test_update_template(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        token = _user_token(test_client, db_session, "recurring_update@example.com")
        cid = str(_create_company(test_client, token))
        gl = _setup_gl(db_session, uuid.UUID(cid))
        created = test_client.post(
            _url(cid, "/recurring-journals"),
            json=_template_body(gl),
            headers=_auth(token),
        ).json()["data"]

        resp = test_client.put(
            _url(cid, f"/recurring-journals/{created['id']}"),
            json={"template_name": "Renamed Template"},
            headers=_auth(token),
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["template_name"] == "Renamed Template"

    def test_unbalanced_template_returns_422(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        token = _user_token(test_client, db_session, "recurring_unbalanced@example.com")
        cid = str(_create_company(test_client, token))
        gl = _setup_gl(db_session, uuid.UUID(cid))
        body = _template_body(gl)
        body["lines"][1]["credit_amount"] = "1.00"
        resp = test_client.post(
            _url(cid, "/recurring-journals"), json=body, headers=_auth(token)
        )
        assert resp.status_code == 422

    def test_cross_tenant_isolation(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        token = _user_token(test_client, db_session, "recurring_tenant@example.com")
        cid_a = str(_create_company(test_client, token))
        cid_b = str(_create_company(test_client, token))
        gl = _setup_gl(db_session, uuid.UUID(cid_a))
        created = test_client.post(
            _url(cid_a, "/recurring-journals"),
            json=_template_body(gl),
            headers=_auth(token),
        ).json()["data"]

        resp = test_client.get(
            _url(cid_b, f"/recurring-journals/{created['id']}"), headers=_auth(token)
        )
        assert resp.status_code == 404


class TestActivateDeactivate:
    def test_deactivate_then_activate(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        token = _user_token(test_client, db_session, "recurring_toggle@example.com")
        cid = str(_create_company(test_client, token))
        gl = _setup_gl(db_session, uuid.UUID(cid))
        created = test_client.post(
            _url(cid, "/recurring-journals"),
            json=_template_body(gl),
            headers=_auth(token),
        ).json()["data"]

        resp = test_client.post(
            _url(cid, f"/recurring-journals/{created['id']}/deactivate"),
            headers=_auth(token),
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["is_active"] is False

        resp = test_client.post(
            _url(cid, f"/recurring-journals/{created['id']}/activate"),
            headers=_auth(token),
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["is_active"] is True


class TestExecutionHistory:
    def test_history_starts_empty(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        token = _user_token(test_client, db_session, "recurring_history@example.com")
        cid = str(_create_company(test_client, token))
        gl = _setup_gl(db_session, uuid.UUID(cid))
        created = test_client.post(
            _url(cid, "/recurring-journals"),
            json=_template_body(gl),
            headers=_auth(token),
        ).json()["data"]

        resp = test_client.get(
            _url(cid, f"/recurring-journals/{created['id']}/history"),
            headers=_auth(token),
        )
        assert resp.status_code == 200
        assert resp.json()["data"] == []


class TestBatchPosting:
    def test_batch_post_two_drafts(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        token = _user_token(test_client, db_session, "batch_post@example.com")
        cid = str(_create_company(test_client, token))
        gl = _setup_gl(db_session, uuid.UUID(cid))

        journal_ids = []
        for _ in range(2):
            resp = test_client.post(
                _url(cid, "/journals"),
                json={
                    "journal_type": "STANDARD",
                    "posting_source": "MANUAL",
                    "posting_date": gl["today"],
                    "currency_code": "USD",
                    "lines": [
                        {
                            "account_id": gl["rent"],
                            "debit_amount": "10.00",
                            "credit_amount": "0",
                        },
                        {
                            "account_id": gl["cash"],
                            "debit_amount": "0",
                            "credit_amount": "10.00",
                        },
                    ],
                },
                headers=_auth(token),
            )
            journal_ids.append(resp.json()["data"]["id"])

        resp = test_client.post(
            _url(cid, "/journals/batch-post"),
            json={"journal_entry_ids": journal_ids},
            headers=_auth(token),
        )
        assert resp.status_code == 200, resp.text
        results = resp.json()["data"]["results"]
        assert len(results) == 2
