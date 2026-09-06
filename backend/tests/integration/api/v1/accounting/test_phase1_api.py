"""API integration tests for Accounting Phase 1 endpoints.

Tests:
  - Health endpoint (200 + 401 enforcement)
  - Feature flags (list, enable, disable, unknown-flag 400)
  - Accounting Configuration (get auto-creates default, update, singleton)
  - Currency (list, create, duplicate 409)
  - Exchange Rate (create, list, filter by period)
  - Cross-tenant isolation for company-scoped resources

All tests use the FastAPI TestClient with SQLite in-memory database.

Spec ref: specs/008-accounting-finance/tasks.md T048
"""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.fixtures.auth_fixtures import create_test_user

# ---------------------------------------------------------------------------
# Helper utilities
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


def _create_company(client: TestClient, token: str) -> uuid.UUID:
    """Create a real company (via the API) so the caller becomes its owner
    and active member — required now that company-scoped routes enforce
    membership (see api/v1/router.py's get_current_company_member gate)."""
    suffix = uuid.uuid4().hex[:8]
    resp = client.post(
        "/api/v1/companies",
        json={
            "legal_name": f"Phase1 Test Co {suffix}",
            "email": f"contact-{suffix}@phase1-test.example.com",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201, resp.text
    return uuid.UUID(resp.json()["data"]["id"])


# ---------------------------------------------------------------------------
# Unauthenticated access (401 enforcement)
# ---------------------------------------------------------------------------


class TestUnauthenticated:
    """All accounting routes must reject unauthenticated requests with 401."""

    def test_health_requires_auth(self, test_client: TestClient) -> None:
        resp = test_client.get(_url(str(uuid.uuid4()), "/health"))
        assert resp.status_code == 401

    def test_feature_flags_requires_auth(self, test_client: TestClient) -> None:
        resp = test_client.get(_url(str(uuid.uuid4()), "/feature-flags"))
        assert resp.status_code == 401

    def test_configuration_requires_auth(self, test_client: TestClient) -> None:
        resp = test_client.get(_url(str(uuid.uuid4()), "/configuration"))
        assert resp.status_code == 401

    def test_currencies_requires_auth(self, test_client: TestClient) -> None:
        resp = test_client.get(_url(str(uuid.uuid4()), "/currencies"))
        assert resp.status_code == 401

    def test_exchange_rates_requires_auth(self, test_client: TestClient) -> None:
        resp = test_client.get(_url(str(uuid.uuid4()), "/exchange-rates"))
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Health endpoint
# ---------------------------------------------------------------------------


class TestHealthEndpoint:
    def test_health_returns_200(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, pw = create_test_user(db_session, email="acct_health_ok@example.com")
        token = _login(test_client, user.email, pw)
        cid = str(_create_company(test_client, token))

        resp = test_client.get(_url(cid, "/health"), headers=_auth(token))
        assert resp.status_code == 200
        body = resp.json()["data"]
        assert body["status"] == "healthy"
        assert body["module"] == "accounting"


# ---------------------------------------------------------------------------
# Feature flags
# ---------------------------------------------------------------------------


class TestFeatureFlags:
    def test_list_feature_flags_returns_8(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, pw = create_test_user(db_session, email="acct_ff_list@example.com")
        token = _login(test_client, user.email, pw)
        cid = str(_create_company(test_client, token))

        resp = test_client.get(_url(cid, "/feature-flags"), headers=_auth(token))
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert len(data) == 8

    def test_list_contains_bankreconciliation_flag_default_true(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, pw = create_test_user(db_session, email="acct_ff_get@example.com")
        token = _login(test_client, user.email, pw)
        cid = str(_create_company(test_client, token))

        resp = test_client.get(_url(cid, "/feature-flags"), headers=_auth(token))
        flags = {f["flag_key"]: f for f in resp.json()["data"]}
        assert flags["accounting.bankreconciliation.enabled"]["is_enabled"] is True
        assert flags["accounting.multicurrency.enabled"]["is_enabled"] is False

    def test_put_unknown_flag_returns_400(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, pw = create_test_user(db_session, email="acct_ff_400@example.com")
        token = _login(test_client, user.email, pw)
        cid = str(_create_company(test_client, token))

        resp = test_client.put(
            _url(cid, "/feature-flags/accounting.nonexistent_flag"),
            json={"is_enabled": True},
            headers=_auth(token),
        )
        assert resp.status_code == 400

    def test_enable_and_disable_flag(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, pw = create_test_user(db_session, email="acct_ff_toggle@example.com")
        token = _login(test_client, user.email, pw)
        cid = str(_create_company(test_client, token))

        resp = test_client.put(
            _url(cid, "/feature-flags/accounting.multicurrency.enabled"),
            json={"is_enabled": True},
            headers=_auth(token),
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["is_enabled"] is True

        resp = test_client.put(
            _url(cid, "/feature-flags/accounting.multicurrency.enabled"),
            json={"is_enabled": False},
            headers=_auth(token),
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["is_enabled"] is False


# ---------------------------------------------------------------------------
# Accounting Configuration
# ---------------------------------------------------------------------------


class TestAccountingConfiguration:
    def test_get_auto_creates_default(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, pw = create_test_user(db_session, email="acct_cfg_get@example.com")
        token = _login(test_client, user.email, pw)
        cid = str(_create_company(test_client, token))

        resp = test_client.get(_url(cid, "/configuration"), headers=_auth(token))
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["base_currency_code"] == "USD"
        assert data["credit_warning_threshold_pct"] == "80.00"

    def test_update_configuration(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, pw = create_test_user(db_session, email="acct_cfg_upd@example.com")
        token = _login(test_client, user.email, pw)
        cid = str(_create_company(test_client, token))

        resp = test_client.put(
            _url(cid, "/configuration"),
            json={"base_currency_code": "EUR", "cheque_stale_days": 90},
            headers=_auth(token),
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["base_currency_code"] == "EUR"
        assert data["cheque_stale_days"] == 90

    def test_configuration_singleton_per_company(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, pw = create_test_user(db_session, email="acct_cfg_sing@example.com")
        token = _login(test_client, user.email, pw)
        cid = str(_create_company(test_client, token))

        resp1 = test_client.get(_url(cid, "/configuration"), headers=_auth(token))
        resp2 = test_client.get(_url(cid, "/configuration"), headers=_auth(token))
        assert resp1.json()["data"]["id"] == resp2.json()["data"]["id"]

    def test_configuration_tenant_isolation(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, pw = create_test_user(db_session, email="acct_cfg_iso@example.com")
        token = _login(test_client, user.email, pw)
        company_a = str(_create_company(test_client, token))
        company_b = str(_create_company(test_client, token))

        test_client.put(
            _url(company_a, "/configuration"),
            json={"base_currency_code": "GBP"},
            headers=_auth(token),
        )
        resp_b = test_client.get(
            _url(company_b, "/configuration"), headers=_auth(token)
        )
        assert resp_b.json()["data"]["base_currency_code"] == "USD"


# ---------------------------------------------------------------------------
# Currencies
# ---------------------------------------------------------------------------


class TestCurrencies:
    def test_list_currencies_includes_seed_data_shape(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, pw = create_test_user(db_session, email="acct_cur_list@example.com")
        token = _login(test_client, user.email, pw)
        cid = str(_create_company(test_client, token))

        resp = test_client.get(_url(cid, "/currencies"), headers=_auth(token))
        assert resp.status_code == 200
        assert isinstance(resp.json()["data"], list)

    def test_create_currency_returns_201(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, pw = create_test_user(db_session, email="acct_cur_create@example.com")
        token = _login(test_client, user.email, pw)
        cid = str(_create_company(test_client, token))
        code = f"T{uuid.uuid4().hex[:2].upper()}"

        resp = test_client.post(
            _url(cid, "/currencies"),
            json={
                "iso_code": code,
                "name": "Test Currency",
                "symbol": "T$",
                "decimal_places": 2,
            },
            headers=_auth(token),
        )
        assert resp.status_code == 201
        assert resp.json()["data"]["iso_code"] == code

    def test_create_duplicate_currency_returns_409(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, pw = create_test_user(db_session, email="acct_cur_dup@example.com")
        token = _login(test_client, user.email, pw)
        cid = str(_create_company(test_client, token))
        code = f"D{uuid.uuid4().hex[:2].upper()}"
        payload = {"iso_code": code, "name": "Dup", "symbol": "D$"}

        test_client.post(_url(cid, "/currencies"), json=payload, headers=_auth(token))
        resp = test_client.post(
            _url(cid, "/currencies"), json=payload, headers=_auth(token)
        )
        assert resp.status_code == 409


# ---------------------------------------------------------------------------
# Exchange Rates
# ---------------------------------------------------------------------------


class TestExchangeRates:
    def test_create_exchange_rate_returns_201(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, pw = create_test_user(db_session, email="acct_fx_create@example.com")
        token = _login(test_client, user.email, pw)
        cid = str(_create_company(test_client, token))

        resp = test_client.post(
            _url(cid, "/exchange-rates"),
            json={
                "from_currency_code": "USD",
                "to_currency_code": "EUR",
                "rate_date": "2026-08-05",
                "rate": "0.9200",
                "rate_type": "SPOT",
            },
            headers=_auth(token),
        )
        assert resp.status_code == 201
        data = resp.json()["data"]
        assert data["from_currency_code"] == "USD"
        assert data["rate"] == "0.9200000000"

    def test_list_exchange_rates(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, pw = create_test_user(db_session, email="acct_fx_list@example.com")
        token = _login(test_client, user.email, pw)
        cid = str(_create_company(test_client, token))

        test_client.post(
            _url(cid, "/exchange-rates"),
            json={
                "from_currency_code": "USD",
                "to_currency_code": "PKR",
                "rate_date": "2026-08-05",
                "rate": "278.50",
            },
            headers=_auth(token),
        )
        resp = test_client.get(_url(cid, "/exchange-rates"), headers=_auth(token))
        assert resp.status_code == 200
        assert len(resp.json()["data"]) >= 1

    def test_invalid_rate_type_returns_422(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, pw = create_test_user(db_session, email="acct_fx_422@example.com")
        token = _login(test_client, user.email, pw)
        cid = str(_create_company(test_client, token))

        resp = test_client.post(
            _url(cid, "/exchange-rates"),
            json={
                "from_currency_code": "USD",
                "to_currency_code": "EUR",
                "rate_date": "2026-08-05",
                "rate": "0.92",
                "rate_type": "BOGUS",
            },
            headers=_auth(token),
        )
        assert resp.status_code == 422

    def test_negative_rate_returns_422(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, pw = create_test_user(db_session, email="acct_fx_neg@example.com")
        token = _login(test_client, user.email, pw)
        cid = str(_create_company(test_client, token))

        resp = test_client.post(
            _url(cid, "/exchange-rates"),
            json={
                "from_currency_code": "USD",
                "to_currency_code": "EUR",
                "rate_date": "2026-08-05",
                "rate": "-1.0",
            },
            headers=_auth(token),
        )
        assert resp.status_code == 422

    def test_exchange_rate_tenant_isolation(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, pw = create_test_user(db_session, email="acct_fx_iso@example.com")
        token = _login(test_client, user.email, pw)
        company_a = str(_create_company(test_client, token))
        company_b = str(_create_company(test_client, token))

        test_client.post(
            _url(company_a, "/exchange-rates"),
            json={
                "from_currency_code": "USD",
                "to_currency_code": "JPY",
                "rate_date": "2026-08-05",
                "rate": "148.00",
            },
            headers=_auth(token),
        )
        resp_b = test_client.get(
            _url(company_b, "/exchange-rates"), headers=_auth(token)
        )
        assert resp_b.status_code == 200
        assert resp_b.json()["data"] == []
