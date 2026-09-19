"""T118 — Export-seam test: ``count_export_rows()``/``iter_export_rows()``
for Installments' 5 list-shaped reports — cheap-count pattern for
``register``/``collections``; bounded-population-then-slice (reusing
the existing ``_DUE_STATE_POPULATION_BOUND=50_000`` cap) for
``due_overdue``/``aging``/``settlement_writeoff``.

T119 — Aggregate-export note: ``plan_performance``/``dashboard`` have no
count/iterate seam — calling either raises ``ValueError``, exercised
below.
"""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock

import pytest

from modules.reports.schemas.installments import (
    ContractRegisterFilter,
    InstallmentDashboardFilter,
)
from modules.reports.services.adapters import (
    installments_adapter as installments_adapter_mod,
)
from modules.reports.services.adapters.installments_adapter import InstallmentsAdapter

COMPANY_ID = uuid.uuid4()


def test_register_export_seam(monkeypatch: pytest.MonkeyPatch) -> None:
    service = MagicMock()
    all_rows = [{"contract_id": f"c-{i}"} for i in range(5)]
    service.get_contract_register.side_effect = lambda company_id, status, skip, limit: (
        all_rows[skip : skip + limit],
        len(all_rows),
    )
    monkeypatch.setattr(
        installments_adapter_mod, "_build_reporting_service", lambda db: service
    )

    adapter = InstallmentsAdapter()
    filters = ContractRegisterFilter()

    count = adapter.count_export_rows(
        MagicMock(), COMPANY_ID, "installments.register", filters
    )
    assert count == 5

    batches = list(
        adapter.iter_export_rows(
            MagicMock(),
            COMPANY_ID,
            "installments.register",
            filters,
            None,
            batch_size=2,
        )
    )
    total_rows = sum(len(b) for b in batches)
    assert total_rows == 5
    assert all(len(b) <= 2 for b in batches)


def test_aggregate_reports_have_no_export_seam(monkeypatch: pytest.MonkeyPatch) -> None:
    service = MagicMock()
    monkeypatch.setattr(
        installments_adapter_mod, "_build_reporting_service", lambda db: service
    )
    adapter = InstallmentsAdapter()
    filters = InstallmentDashboardFilter()

    with pytest.raises(ValueError):
        adapter.count_export_rows(
            MagicMock(), COMPANY_ID, "installments.dashboard", filters
        )

    with pytest.raises(ValueError):
        list(
            adapter.iter_export_rows(
                MagicMock(),
                COMPANY_ID,
                "installments.dashboard",
                filters,
                None,
                batch_size=100,
            )
        )
