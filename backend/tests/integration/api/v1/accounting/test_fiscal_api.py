"""API integration tests for Fiscal Calendar (Phase 3) endpoints.

Tests:
  - Fiscal year CRUD (create, list, get, update)
  - Period listing, lock, unlock (mandatory reason enforced)
  - Opening balance setup (balanced passes, imbalanced returns 422)
  - Year-end close (blocked until all periods locked, then succeeds)
  - Cross-tenant isolation
  - 401 enforcement

Spec ref: specs/008-accounting-finance/tasks.md T087
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

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
    """Create a real company (via the API) so the caller becomes its owner
    and active member — required now that company-scoped routes enforce
    membership (see api/v1/router.py's get_current_company_member gate)."""
    suffix = uuid.uuid4().hex[:8]
    resp = client.post(
        "/api/v1/companies",
        json={
            "legal_name": f"Fiscal Test Co {suffix}",
            "email": f"contact-{suffix}@fiscal-test.example.com",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201, resp.text
    return uuid.UUID(resp.json()["data"]["id"])


def _create_fiscal_year(
    test_client: TestClient, cid: str, token: str, name: str, start: str, end: str
) -> dict[str, Any]:
    resp = test_client.post(
        _url(cid, "/fiscal-years"),
        json={
            "fiscal_year_name": name,
            "start_date": start,
            "end_date": end,
            "base_currency_code": "USD",
        },
        headers=_auth(token),
    )
    assert resp.status_code == 201, resp.text
    return dict(resp.json()["data"])


class TestUnauthenticated:
    def test_fiscal_years_requires_auth(self, test_client: TestClient) -> None:
        resp = test_client.get(_url(str(uuid.uuid4()), "/fiscal-years"))
        assert resp.status_code == 401


class TestFiscalYearCRUD:
    def test_create_generates_twelve_periods(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        token = _user_token(test_client, db_session, "fiscal_create@example.com")
        cid = str(_create_company(test_client, token))
        year = _create_fiscal_year(
            test_client, cid, token, "FY2050", "2050-01-01", "2050-12-31"
        )
        assert year["status"] == "OPEN"

        resp = test_client.get(
            _url(cid, f"/fiscal-years/{year['id']}/periods"), headers=_auth(token)
        )
        assert resp.status_code == 200
        periods = resp.json()["data"]
        assert len(periods) == 12
        assert all(p["status"] == "OPEN" for p in periods)

    def test_duplicate_fiscal_year_name_rejected(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        token = _user_token(test_client, db_session, "fiscal_dup@example.com")
        cid = str(_create_company(test_client, token))
        _create_fiscal_year(
            test_client, cid, token, "FY2051", "2051-01-01", "2051-12-31"
        )
        resp = test_client.post(
            _url(cid, "/fiscal-years"),
            json={
                "fiscal_year_name": "FY2051",
                "start_date": "2051-01-01",
                "end_date": "2051-12-31",
                "base_currency_code": "USD",
            },
            headers=_auth(token),
        )
        assert resp.status_code == 409

    def test_get_and_update_fiscal_year(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        token = _user_token(test_client, db_session, "fiscal_update@example.com")
        cid = str(_create_company(test_client, token))
        year = _create_fiscal_year(
            test_client, cid, token, "FY2052", "2052-01-01", "2052-12-31"
        )
        resp = test_client.get(
            _url(cid, f"/fiscal-years/{year['id']}"), headers=_auth(token)
        )
        assert resp.status_code == 200

        resp = test_client.put(
            _url(cid, f"/fiscal-years/{year['id']}"),
            json={"is_current": True},
            headers=_auth(token),
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["is_current"] is True

    def test_cross_tenant_isolation(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        token = _user_token(test_client, db_session, "fiscal_tenant@example.com")
        cid_a = str(_create_company(test_client, token))
        cid_b = str(_create_company(test_client, token))
        year = _create_fiscal_year(
            test_client, cid_a, token, "FY2053", "2053-01-01", "2053-12-31"
        )
        resp = test_client.get(
            _url(cid_b, f"/fiscal-years/{year['id']}"), headers=_auth(token)
        )
        assert resp.status_code == 404


class TestPeriodLockUnlock:
    def test_lock_then_unlock(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        token = _user_token(test_client, db_session, "fiscal_lock@example.com")
        cid = str(_create_company(test_client, token))
        year = _create_fiscal_year(
            test_client, cid, token, "FY2054", "2054-01-01", "2054-12-31"
        )
        periods = test_client.get(
            _url(cid, f"/fiscal-years/{year['id']}/periods"), headers=_auth(token)
        ).json()["data"]
        period_id = periods[0]["id"]

        resp = test_client.post(
            _url(cid, f"/fiscal-years/{year['id']}/periods/{period_id}/lock"),
            json={"lock_reason": "Month-end close"},
            headers=_auth(token),
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["status"] == "LOCKED"

        resp = test_client.post(
            _url(cid, f"/fiscal-years/{year['id']}/periods/{period_id}/unlock"),
            json={"reason": "Missing invoice discovered"},
            headers=_auth(token),
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["status"] == "OPEN"

    def test_unlock_without_reason_rejected(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        token = _user_token(test_client, db_session, "fiscal_lock2@example.com")
        cid = str(_create_company(test_client, token))
        year = _create_fiscal_year(
            test_client, cid, token, "FY2055", "2055-01-01", "2055-12-31"
        )
        periods = test_client.get(
            _url(cid, f"/fiscal-years/{year['id']}/periods"), headers=_auth(token)
        ).json()["data"]
        period_id = periods[0]["id"]

        resp = test_client.post(
            _url(cid, f"/fiscal-years/{year['id']}/periods/{period_id}/unlock"),
            json={"reason": ""},
            headers=_auth(token),
        )
        assert resp.status_code == 422


class TestOpeningBalances:
    def test_balanced_opening_balances_accepted(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        token = _user_token(test_client, db_session, "fiscal_ob@example.com")
        cid = str(_create_company(test_client, token))
        year = _create_fiscal_year(
            test_client, cid, token, "FY2056", "2056-01-01", "2056-12-31"
        )
        resp = test_client.post(
            _url(cid, f"/fiscal-years/{year['id']}/opening-balances"),
            json={
                "lines": [
                    {"account_id": str(uuid.uuid4()), "debit_amount": "1000.00"},
                    {"account_id": str(uuid.uuid4()), "credit_amount": "1000.00"},
                ]
            },
            headers=_auth(token),
        )
        assert resp.status_code == 201, resp.text
        assert len(resp.json()["data"]) == 2

    def test_imbalanced_opening_balances_returns_422(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        token = _user_token(test_client, db_session, "fiscal_ob2@example.com")
        cid = str(_create_company(test_client, token))
        year = _create_fiscal_year(
            test_client, cid, token, "FY2057", "2057-01-01", "2057-12-31"
        )
        resp = test_client.post(
            _url(cid, f"/fiscal-years/{year['id']}/opening-balances"),
            json={
                "lines": [{"account_id": str(uuid.uuid4()), "debit_amount": "500.00"}]
            },
            headers=_auth(token),
        )
        assert resp.status_code == 422


class TestYearEndClose:
    def test_blocked_until_all_periods_locked(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        token = _user_token(test_client, db_session, "fiscal_close@example.com")
        cid = str(_create_company(test_client, token))
        year = _create_fiscal_year(
            test_client, cid, token, "FY2058", "2058-01-01", "2058-12-31"
        )
        resp = test_client.post(
            _url(cid, f"/fiscal-years/{year['id']}/year-end-close"),
            json={},
            headers=_auth(token),
        )
        assert resp.status_code == 422

    def test_succeeds_after_all_periods_locked(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        token = _user_token(test_client, db_session, "fiscal_close2@example.com")
        cid = str(_create_company(test_client, token))
        year = _create_fiscal_year(
            test_client, cid, token, "FY2059", "2059-01-01", "2059-12-31"
        )
        periods = test_client.get(
            _url(cid, f"/fiscal-years/{year['id']}/periods"), headers=_auth(token)
        ).json()["data"]
        for period in periods:
            resp = test_client.post(
                _url(cid, f"/fiscal-years/{year['id']}/periods/{period['id']}/lock"),
                json={"lock_reason": "close"},
                headers=_auth(token),
            )
            assert resp.status_code == 200

        resp = test_client.post(
            _url(cid, f"/fiscal-years/{year['id']}/year-end-close"),
            json={},
            headers=_auth(token),
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["status"] == "CLOSED"
