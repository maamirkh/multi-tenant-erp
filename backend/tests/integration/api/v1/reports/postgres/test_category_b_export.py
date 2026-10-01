"""T211 — Category B end-to-end for the one real remaining case,
``installments.due_overdue``/``installments.aging`` (bounded by the
enforced ``_DUE_STATE_POPULATION_BOUND`` hard cap — T196 unit-verifies the
cap is what each fetch passes):

- within limit → the export's row set matches the online scope exactly;
- over the configured limit → ``EXPORT_TOO_LARGE`` before any file is
  generated (no attachment, no audit row);
- Case B (Installments disabled, existing contract) → the two allow-listed
  keys remain exportable, exactly as they remain viewable.

Real Postgres: ``build_active_contract_with_schedule`` depends on
Postgres-only server defaults (the same requirement T142/T153 have).
"""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from modules.installments.repositories.feature_flag import (
    InstallmentsFeatureFlagRepository,
)
from modules.installments.services.feature_flag_service import (
    InstallmentsFeatureFlagService,
)
from modules.reports import constants
from modules.reports.repositories.reports_audit_repository import (
    ReportsAuditRepository,
)
from tests.integration.api.v1.installments.conftest import (
    build_active_contract_with_schedule,
)
from tests.integration.api.v1.reports.conftest import (
    auth_header,
    export_url,
    parse_csv,
    reports_url,
    setup_company,
)

_CATEGORY_B_KEYS = ("installments.due_overdue", "installments.aging")


def _cell(value: object) -> str:
    return "" if value is None else str(value)


def _online_rows(
    client: TestClient, company_id: uuid.UUID, key: str, headers: dict[str, str]
) -> tuple[list[str], list[list[str]]]:
    fields: list[str] = []
    rows: list[list[str]] = []
    page = 1
    while True:
        resp = client.get(
            reports_url(company_id, f"/{key}") + f"?page={page}&page_size=2",
            headers=headers,
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        for item in data["items"]:
            fields = fields or list(item.keys())
            rows.append([_cell(item[f]) for f in fields])
        if page >= data["pages"]:
            return fields, rows
        page += 1


def _enable_installments(db: Session, company_id: uuid.UUID) -> None:
    InstallmentsFeatureFlagService(
        flag_repo=InstallmentsFeatureFlagRepository(db)
    ).enable(company_id)
    db.commit()


def test_within_limit_matches_online_scope(
    test_client: TestClient, db_session: Session
) -> None:
    token, company_id = setup_company(db_session, test_client)
    _enable_installments(db_session, company_id)
    build_active_contract_with_schedule(
        db_session, company_id=company_id, installment_count=5
    )
    headers = auth_header(token)

    populated = 0
    for key in _CATEGORY_B_KEYS:
        fields, online = _online_rows(test_client, company_id, key, headers)
        resp = test_client.get(export_url(company_id, key, "csv"), headers=headers)
        assert resp.status_code == 200, f"{key}: {resp.text}"
        exported = parse_csv(resp.content)
        if online:
            populated += 1
            assert exported[0] == fields, key
        assert sorted(exported[1:]) == sorted(online), key
    assert populated >= 1, "fixture produced no due/aging rows to compare"


def test_over_limit_rejected_before_file_generation(
    test_client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    token, company_id = setup_company(db_session, test_client)
    _enable_installments(db_session, company_id)
    build_active_contract_with_schedule(
        db_session, company_id=company_id, installment_count=5
    )
    headers = auth_header(token)
    _fields, aging_rows = _online_rows(
        test_client, company_id, "installments.aging", headers
    )
    assert len(aging_rows) >= 2

    monkeypatch.setattr(constants, "EXPORT_ROW_LIMIT_CSV", len(aging_rows) - 1)
    resp = test_client.get(
        export_url(company_id, "installments.aging", "csv"), headers=headers
    )

    assert resp.status_code == 422, resp.text
    assert resp.json()["error"]["code"] == "EXPORT_TOO_LARGE"
    assert "content-disposition" not in resp.headers
    assert ReportsAuditRepository(db_session).list_for_company(company_id) == []


def test_case_b_allowlisted_keys_remain_exportable(
    test_client: TestClient, db_session: Session
) -> None:
    token, company_id = setup_company(db_session, test_client)
    # Installments left disabled, but a serviceable contract exists (Case B).
    build_active_contract_with_schedule(db_session, company_id=company_id)
    headers = auth_header(token)

    for key in _CATEGORY_B_KEYS:
        resp = test_client.get(export_url(company_id, key, "xlsx"), headers=headers)
        assert resp.status_code == 200, f"{key}: {resp.text}"
    assert len(ReportsAuditRepository(db_session).list_for_company(company_id)) == 2
