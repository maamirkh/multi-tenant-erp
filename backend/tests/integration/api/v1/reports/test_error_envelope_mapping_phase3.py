"""T135 — Integration test: each of the 8 reachable-now error codes
triggered end-to-end via the real API (T134): ``REPORT_NOT_FOUND`` 404,
``REPORT_NOT_ENTITLED`` 403, ``REPORT_PERMISSION_DENIED`` 403,
``REPORT_INVALID_FILTER`` 422, ``REPORT_UNSUPPORTED_SORT`` 422,
``REPORT_UNAVAILABLE`` 409, ``SAVED_VIEW_NOT_FOUND`` 404,
``SAVED_VIEW_REPORT_RETIRED`` 410 — no internal detail leakage (every
body is the platform's standard ``ErrorResponse`` shape: ``code``/
``message``/``details`` only).

``REPORT_UNAVAILABLE`` has no organic trigger in any Phase 2 adapter yet
(``UnavailablePrerequisiteError`` is defined but never raised anywhere in
``modules/reports/services/adapters/*.py`` — confirmed by direct search).
Its test below verifies the exception->HTTP mapping itself (T134's actual
deliverable) via a monkeypatched adapter method, the same "prove the
wiring" approach the codebase already uses elsewhere — not an invented
business scenario in a settled Phase 2 file.
"""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

import modules.reports.registry.load_all  # noqa: F401 — triggers full catalog registration
from modules.reports.exceptions import UnavailablePrerequisiteError
from modules.reports.services import saved_view_service as saved_view_service_mod
from modules.users_roles.repositories.company_member_repository import (
    CompanyMemberRepository,
)
from modules.users_roles.repositories.role_permission_repository import (
    RolePermissionRepository,
)
from tests.integration.api.v1.reports.conftest import reports_url, setup_company


def _current_user_id(client: TestClient, token: str) -> uuid.UUID:
    resp = client.get("/api/v1/profile", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200, resp.text
    return uuid.UUID(resp.json()["data"]["id"])


def _assert_error_envelope(resp_json: dict[str, object], expected_code: str) -> None:
    assert "error" in resp_json
    error = resp_json["error"]
    assert isinstance(error, dict)
    assert error["code"] == expected_code
    assert "message" in error
    assert "details" in error
    # No internal leakage: no stack trace / traceback-shaped keys.
    assert "traceback" not in resp_json
    assert "traceback" not in error.get("details", {})


def test_report_not_found_404(test_client: TestClient, db_session: Session) -> None:
    token, company_id = setup_company(db_session, test_client)
    resp = test_client.get(
        reports_url(company_id, "/does.not.exist"),
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404, resp.text
    _assert_error_envelope(resp.json(), "REPORT_NOT_FOUND")


def test_report_not_entitled_403(test_client: TestClient, db_session: Session) -> None:
    """CRM defaults disabled; this company never enables it."""
    token, company_id = setup_company(db_session, test_client)
    resp = test_client.get(
        reports_url(company_id, "/crm.pipeline"),
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403, resp.text
    _assert_error_envelope(resp.json(), "REPORT_NOT_ENTITLED")


def test_report_permission_denied_403(
    test_client: TestClient, db_session: Session
) -> None:
    token, company_id = setup_company(db_session, test_client)
    user_id = _current_user_id(test_client, token)
    member = CompanyMemberRepository(db_session).get_by_user_id(
        user_id=user_id, company_id=company_id
    )
    assert member is not None
    role_permission_repo = RolePermissionRepository(db_session)
    current = role_permission_repo.get_permission_codes_for_role(member.role_id)
    role_permission_repo.bulk_set_permissions_for_role(
        member.role_id, current - {"reports.purchase.view"}
    )
    db_session.commit()

    resp = test_client.get(
        reports_url(company_id, "/purchase.summary"),
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403, resp.text
    _assert_error_envelope(resp.json(), "REPORT_PERMISSION_DENIED")


def test_report_invalid_filter_422(
    test_client: TestClient, db_session: Session
) -> None:
    token, company_id = setup_company(db_session, test_client)
    resp = test_client.get(
        reports_url(company_id, "/purchase.summary") + "?filters[not_a_real_field]=x",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422, resp.text
    _assert_error_envelope(resp.json(), "REPORT_INVALID_FILTER")


def test_report_unsupported_sort_422(
    test_client: TestClient, db_session: Session
) -> None:
    """Every Phase 2 catalog entry declares ``sortable_fields=()`` — any
    non-empty ``sort`` value is therefore always rejected."""
    token, company_id = setup_company(db_session, test_client)
    resp = test_client.get(
        reports_url(company_id, "/purchase.summary") + "?sort=not_sortable",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422, resp.text
    _assert_error_envelope(resp.json(), "REPORT_UNSUPPORTED_SORT")


def test_report_unavailable_409(
    test_client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    from modules.reports.services.adapters import (
        purchase_adapter as purchase_adapter_mod,
    )

    def _raise_unavailable(self: object, *args: object, **kwargs: object) -> object:
        raise UnavailablePrerequisiteError("purchase.summary", "no fixture configured")

    monkeypatch.setattr(purchase_adapter_mod.PurchaseAdapter, "run", _raise_unavailable)

    token, company_id = setup_company(db_session, test_client)
    resp = test_client.get(
        reports_url(company_id, "/purchase.summary"),
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 409, resp.text
    _assert_error_envelope(resp.json(), "REPORT_UNAVAILABLE")


def test_saved_view_not_found_404(test_client: TestClient, db_session: Session) -> None:
    token, company_id = setup_company(db_session, test_client)
    resp = test_client.get(
        reports_url(company_id, f"/saved-views/{uuid.uuid4()}"),
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404, resp.text
    _assert_error_envelope(resp.json(), "SAVED_VIEW_NOT_FOUND")


def test_saved_view_report_retired_410(
    test_client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    token, company_id = setup_company(db_session, test_client)

    resp = test_client.post(
        reports_url(company_id, "/saved-views"),
        json={
            "report_key": "purchase.summary",
            "name": "Retirement Test",
            "filter_config": {},
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201, resp.text
    view_id = resp.json()["data"]["id"]

    # Simulate the referenced report_key having been retired since save
    # time — a monkeypatched, empty registry view, scoped to this test
    # only (never mutates the real, shared REPORT_REGISTRY).
    monkeypatch.setattr(saved_view_service_mod, "REPORT_REGISTRY", {})

    resp = test_client.get(
        reports_url(company_id, f"/saved-views/{view_id}"),
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 410, resp.text
    _assert_error_envelope(resp.json(), "SAVED_VIEW_REPORT_RETIRED")
