"""API integration tests for Chart of Accounts (Phase 2) endpoints.

Tests:
  - Account CRUD lifecycle (create, get, update, deactivate, activate)
  - COA tree endpoint (?tree=true)
  - Duplicate account code returns 409
  - Non-existent account returns 404
  - Account groups CRUD
  - System account configuration (valid + type-mismatch)
  - COA templates listing and application
  - Bulk import (success + row-level failure reporting)
  - Cross-tenant isolation
  - 401 enforcement on all endpoints

Spec ref: specs/008-accounting-finance/tasks.md T066
"""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

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
            "legal_name": f"COA Test Co {suffix}",
            "email": f"contact-{suffix}@coa-test.example.com",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201, resp.text
    return uuid.UUID(resp.json()["data"]["id"])


class TestUnauthenticated:
    def test_accounts_requires_auth(self, test_client: TestClient) -> None:
        resp = test_client.get(_url(str(uuid.uuid4()), "/accounts"))
        assert resp.status_code == 401

    def test_account_groups_requires_auth(self, test_client: TestClient) -> None:
        resp = test_client.get(_url(str(uuid.uuid4()), "/account-groups"))
        assert resp.status_code == 401

    def test_system_accounts_requires_auth(self, test_client: TestClient) -> None:
        resp = test_client.get(_url(str(uuid.uuid4()), "/system-accounts"))
        assert resp.status_code == 401

    def test_coa_templates_requires_auth(self, test_client: TestClient) -> None:
        resp = test_client.get(_url(str(uuid.uuid4()), "/coa-templates"))
        assert resp.status_code == 401


class TestAccountCRUD:
    def test_create_account_returns_201(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        token = _user_token(test_client, db_session, "coa_create@example.com")
        cid = str(_create_company(test_client, token))
        resp = test_client.post(
            _url(cid, "/accounts"),
            json={
                "account_code": "1000",
                "account_name": "Cash",
                "account_type": "ASSET",
            },
            headers=_auth(token),
        )
        assert resp.status_code == 201
        data = resp.json()["data"]
        assert data["account_code"] == "1000"
        assert data["is_active"] is True

    def test_duplicate_code_returns_409(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        token = _user_token(test_client, db_session, "coa_dup@example.com")
        cid = str(_create_company(test_client, token))
        payload = {
            "account_code": "1000",
            "account_name": "Cash",
            "account_type": "ASSET",
        }
        test_client.post(_url(cid, "/accounts"), json=payload, headers=_auth(token))
        resp = test_client.post(
            _url(cid, "/accounts"), json=payload, headers=_auth(token)
        )
        assert resp.status_code == 409

    def test_get_account_by_id(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        token = _user_token(test_client, db_session, "coa_get@example.com")
        cid = str(_create_company(test_client, token))
        create_resp = test_client.post(
            _url(cid, "/accounts"),
            json={
                "account_code": "1000",
                "account_name": "Cash",
                "account_type": "ASSET",
            },
            headers=_auth(token),
        )
        account_id = create_resp.json()["data"]["id"]
        resp = test_client.get(
            _url(cid, f"/accounts/{account_id}"), headers=_auth(token)
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["account_code"] == "1000"

    def test_get_nonexistent_account_returns_404(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        token = _user_token(test_client, db_session, "coa_404@example.com")
        cid = str(_create_company(test_client, token))
        resp = test_client.get(
            _url(cid, f"/accounts/{uuid.uuid4()}"), headers=_auth(token)
        )
        assert resp.status_code == 404

    def test_update_account_name(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        token = _user_token(test_client, db_session, "coa_upd@example.com")
        cid = str(_create_company(test_client, token))
        create_resp = test_client.post(
            _url(cid, "/accounts"),
            json={
                "account_code": "1000",
                "account_name": "Cash",
                "account_type": "ASSET",
            },
            headers=_auth(token),
        )
        account_id = create_resp.json()["data"]["id"]
        resp = test_client.put(
            _url(cid, f"/accounts/{account_id}"),
            json={"account_name": "Petty Cash"},
            headers=_auth(token),
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["account_name"] == "Petty Cash"

    def test_deactivate_and_reactivate_account(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        token = _user_token(test_client, db_session, "coa_deact@example.com")
        cid = str(_create_company(test_client, token))
        create_resp = test_client.post(
            _url(cid, "/accounts"),
            json={
                "account_code": "1000",
                "account_name": "Cash",
                "account_type": "ASSET",
            },
            headers=_auth(token),
        )
        account_id = create_resp.json()["data"]["id"]

        deact_resp = test_client.delete(
            _url(cid, f"/accounts/{account_id}"), headers=_auth(token)
        )
        assert deact_resp.status_code == 200
        assert deact_resp.json()["data"]["is_active"] is False

        react_resp = test_client.post(
            _url(cid, f"/accounts/{account_id}/activate"), headers=_auth(token)
        )
        assert react_resp.status_code == 200
        assert react_resp.json()["data"]["is_active"] is True

    def test_deactivation_blocked_with_active_children_returns_422(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        token = _user_token(test_client, db_session, "coa_block@example.com")
        cid = str(_create_company(test_client, token))
        parent_resp = test_client.post(
            _url(cid, "/accounts"),
            json={
                "account_code": "1000",
                "account_name": "Assets",
                "account_type": "ASSET",
                "is_leaf": False,
            },
            headers=_auth(token),
        )
        parent_id = parent_resp.json()["data"]["id"]
        test_client.post(
            _url(cid, "/accounts"),
            json={
                "account_code": "1010",
                "account_name": "Cash",
                "account_type": "ASSET",
                "parent_account_id": parent_id,
            },
            headers=_auth(token),
        )
        resp = test_client.delete(
            _url(cid, f"/accounts/{parent_id}"), headers=_auth(token)
        )
        assert resp.status_code == 422

    def test_tenant_isolation(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        token = _user_token(test_client, db_session, "coa_iso@example.com")
        company_a = str(_create_company(test_client, token))
        company_b = str(_create_company(test_client, token))
        test_client.post(
            _url(company_a, "/accounts"),
            json={
                "account_code": "1000",
                "account_name": "A Cash",
                "account_type": "ASSET",
            },
            headers=_auth(token),
        )
        resp = test_client.get(_url(company_b, "/accounts"), headers=_auth(token))
        assert resp.status_code == 200
        codes = [a["account_code"] for a in resp.json()["data"]]
        assert "1000" not in codes


class TestCOATreeEndpoint:
    def test_tree_endpoint_returns_nested_structure(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        token = _user_token(test_client, db_session, "coa_tree@example.com")
        cid = str(_create_company(test_client, token))
        parent_resp = test_client.post(
            _url(cid, "/accounts"),
            json={
                "account_code": "1000",
                "account_name": "Assets",
                "account_type": "ASSET",
                "is_leaf": False,
            },
            headers=_auth(token),
        )
        parent_id = parent_resp.json()["data"]["id"]
        test_client.post(
            _url(cid, "/accounts"),
            json={
                "account_code": "1010",
                "account_name": "Cash",
                "account_type": "ASSET",
                "parent_account_id": parent_id,
            },
            headers=_auth(token),
        )
        resp = test_client.get(_url(cid, "/accounts?tree=true"), headers=_auth(token))
        assert resp.status_code == 200
        tree = resp.json()["data"]
        assert len(tree) == 1
        assert tree[0]["account_code"] == "1000"
        assert len(tree[0]["children"]) == 1
        assert tree[0]["children"][0]["account_code"] == "1010"


class TestAccountGroups:
    def test_create_and_list_account_groups(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        token = _user_token(test_client, db_session, "coa_grp@example.com")
        cid = str(_create_company(test_client, token))
        resp = test_client.post(
            _url(cid, "/account-groups"),
            json={
                "group_code": "CUR-AST",
                "group_name": "Current Assets",
                "account_type": "ASSET",
            },
            headers=_auth(token),
        )
        assert resp.status_code == 201

        list_resp = test_client.get(_url(cid, "/account-groups"), headers=_auth(token))
        assert list_resp.status_code == 200
        assert len(list_resp.json()["data"]) == 1


class TestSystemAccounts:
    def test_get_system_accounts_auto_creates_default(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        token = _user_token(test_client, db_session, "coa_sysget@example.com")
        cid = str(_create_company(test_client, token))
        resp = test_client.get(_url(cid, "/system-accounts"), headers=_auth(token))
        assert resp.status_code == 200
        assert resp.json()["data"]["default_ar_account_id"] is None

    def test_set_system_account_with_matching_type(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        token = _user_token(test_client, db_session, "coa_sysset@example.com")
        cid = str(_create_company(test_client, token))
        ar_resp = test_client.post(
            _url(cid, "/accounts"),
            json={
                "account_code": "1100",
                "account_name": "Accounts Receivable",
                "account_type": "ASSET",
            },
            headers=_auth(token),
        )
        ar_id = ar_resp.json()["data"]["id"]
        resp = test_client.put(
            _url(cid, "/system-accounts"),
            json={"role": "default_ar_account_id", "account_id": ar_id},
            headers=_auth(token),
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["default_ar_account_id"] == ar_id

    def test_set_system_account_type_mismatch_returns_422(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        token = _user_token(test_client, db_session, "coa_sysmismatch@example.com")
        cid = str(_create_company(test_client, token))
        expense_resp = test_client.post(
            _url(cid, "/accounts"),
            json={
                "account_code": "6000",
                "account_name": "Salaries",
                "account_type": "EXPENSE",
            },
            headers=_auth(token),
        )
        expense_id = expense_resp.json()["data"]["id"]
        resp = test_client.put(
            _url(cid, "/system-accounts"),
            json={"role": "default_ar_account_id", "account_id": expense_id},
            headers=_auth(token),
        )
        assert resp.status_code == 422


class TestCOATemplates:
    def test_list_templates_returns_6(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        token = _user_token(test_client, db_session, "coa_tmpl_list@example.com")
        cid = str(_create_company(test_client, token))
        resp = test_client.get(_url(cid, "/coa-templates"), headers=_auth(token))
        assert resp.status_code == 200
        assert len(resp.json()["data"]) == 6

    def test_apply_template_creates_accounts(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        token = _user_token(test_client, db_session, "coa_tmpl_apply@example.com")
        cid = str(_create_company(test_client, token))
        resp = test_client.post(
            _url(cid, "/coa-templates/apply"),
            json={"template_key": "GENERIC"},
            headers=_auth(token),
        )
        assert resp.status_code == 200
        assert len(resp.json()["data"]) > 0

        list_resp = test_client.get(_url(cid, "/accounts"), headers=_auth(token))
        assert len(list_resp.json()["data"]) == len(resp.json()["data"])

    def test_apply_unknown_template_returns_400(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        token = _user_token(test_client, db_session, "coa_tmpl_bad@example.com")
        cid = str(_create_company(test_client, token))
        resp = test_client.post(
            _url(cid, "/coa-templates/apply"),
            json={"template_key": "NOT_REAL"},
            headers=_auth(token),
        )
        assert resp.status_code == 422  # pydantic pattern validation rejects it


class TestBulkImport:
    def test_bulk_import_success_and_failure_rows(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        token = _user_token(test_client, db_session, "coa_bulk@example.com")
        cid = str(_create_company(test_client, token))
        # Pre-create an account whose code will collide with one import row.
        test_client.post(
            _url(cid, "/accounts"),
            json={
                "account_code": "1000",
                "account_name": "Existing",
                "account_type": "ASSET",
            },
            headers=_auth(token),
        )
        rows = [
            {"account_code": "1000", "account_name": "Dup", "account_type": "ASSET"},
            {
                "account_code": "1001",
                "account_name": "New Bank",
                "account_type": "ASSET",
            },
        ]
        resp = test_client.post(
            _url(cid, "/accounts/bulk-import"), json=rows, headers=_auth(token)
        )
        assert resp.status_code == 200
        results = resp.json()["data"]
        assert len(results) == 2
        by_code = {r["account_code"]: r for r in results}
        assert by_code["1000"]["success"] is False
        assert by_code["1001"]["success"] is True

    def test_export_returns_all_accounts(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        token = _user_token(test_client, db_session, "coa_export@example.com")
        cid = str(_create_company(test_client, token))
        test_client.post(
            _url(cid, "/accounts"),
            json={
                "account_code": "1000",
                "account_name": "Cash",
                "account_type": "ASSET",
            },
            headers=_auth(token),
        )
        resp = test_client.get(_url(cid, "/accounts/export"), headers=_auth(token))
        assert resp.status_code == 200
        assert len(resp.json()["data"]) == 1
