"""T133 — Integration test: correct envelope shape per report kind for
all 43 real ``ADAPTER``-kind "Now" keys (parametrized), ``report_meta``
present and correct.

**Scoped to ``execution_kind == ADAPTER`` only** (corrected, Phase 4):
composite reports (``exec.dashboard``, registered T151; eventually
``crossmodule.customer_360``, Phase 5) are deliberately unreachable via
this generic ``GET /{report_key}`` path (T126) — they correctly 404,
identical to an unregistered/``DEFERRED`` key, already asserted at the
service layer by ``test_authorize_and_validate.py``. Including them here
against the (200 | 409 | 422) assertion this file's parametrization was
built for would misclassify their correct 404 as a failure; this is a
generic-execution-path test, not a full registry sweep.

Each of the 43 keys is called with an **empty** filter payload. Many
Accounting/Purchase/etc. filter schemas declare required fields (e.g.
``TrialBalanceFilter.period_id``, ``BankCashBookFilter.account_id``) that
only resolve against real fixture rows this test deliberately does not
construct (43 domain-specific fixtures is out of this test's scope) — an
empty payload against those legitimately 422s via
``FilterValidationError``, exercised and asserted as a real, correctly-
mapped outcome, not a crash. What this test proves for **every** one of
the 43 keys: the request never 500s, and whenever it succeeds (200), the
envelope shape matches its declared ``pagination`` style exactly, with
``report_meta`` (report_key/period/freshness/drill_down) present and
correct. Three keys needing no fixture data at all
(``accounting.gl``/``purchase.kpis``/``purchase.summary``) additionally
prove the concrete 200 path for each of the three shape families
(cursor/aggregate/paginated).
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

import modules.reports.registry.load_all  # noqa: F401 — triggers full catalog registration
from modules.reports.registry.definitions import (
    REPORT_REGISTRY,
    PaginationStyle,
    ReportDefinition,
    ReportExecutionKind,
    ReportStatus,
)
from tests.integration.api.v1.reports.conftest import (
    enable_crm_and_installments,
    reports_url,
    setup_company,
)


def _now_definitions() -> list[ReportDefinition]:
    return [
        d
        for d in REPORT_REGISTRY.values()
        if d.status is ReportStatus.NOW
        and d.execution_kind is ReportExecutionKind.ADAPTER
    ]


@pytest.fixture
def _company(test_client: TestClient, db_session: Session) -> tuple[str, str]:
    token, company_id = setup_company(db_session, test_client)
    enable_crm_and_installments(db_session, company_id)
    return token, str(company_id)


@pytest.mark.parametrize("definition", _now_definitions(), ids=lambda d: d.key)
def test_every_now_key_never_500s_and_has_correct_envelope_when_200(
    definition: ReportDefinition,
    test_client: TestClient,
    _company: tuple[str, str],
) -> None:
    token, company_id = _company
    resp = test_client.get(
        reports_url(company_id, f"/{definition.key}"),
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code != 500, resp.text
    if resp.status_code != 200:
        # A required filter field this test didn't supply — a real,
        # correctly-classified outcome, not a crash.
        assert resp.status_code in (409, 422), resp.text
        return

    body = resp.json()
    assert "data" in body
    assert "report_meta" in body
    assert "message" in body
    assert "meta" in body
    report_meta = body["report_meta"]
    assert report_meta["report_key"] == definition.key
    assert "period" in report_meta
    assert "freshness" in report_meta
    assert "drill_down" in report_meta

    if definition.pagination is PaginationStyle.OFFSET:
        assert set(body["data"].keys()) >= {
            "items",
            "total",
            "page",
            "page_size",
            "pages",
        }
    elif definition.pagination is PaginationStyle.CURSOR:
        assert set(body["data"].keys()) >= {"items", "has_more", "next_cursor"}
    else:
        assert isinstance(body["data"], dict)


def test_accounting_gl_cursor_shape_succeeds_with_empty_filters(
    test_client: TestClient, _company: tuple[str, str]
) -> None:
    token, company_id = _company
    resp = test_client.get(
        reports_url(company_id, "/accounting.gl"),
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert "items" in data and "has_more" in data and "next_cursor" in data


def test_purchase_kpis_aggregate_shape_succeeds_with_empty_filters(
    test_client: TestClient, _company: tuple[str, str]
) -> None:
    token, company_id = _company
    resp = test_client.get(
        reports_url(company_id, "/purchase.kpis"),
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert isinstance(body["data"], dict)
    assert body["report_meta"]["report_key"] == "purchase.kpis"


def test_purchase_summary_paginated_shape_succeeds_with_empty_filters(
    test_client: TestClient, _company: tuple[str, str]
) -> None:
    token, company_id = _company
    resp = test_client.get(
        reports_url(company_id, "/purchase.summary"),
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["items"] == []
    assert data["total"] == 0
    assert data["page"] == 1
    assert data["page_size"] == 20
    assert data["pages"] == 0
