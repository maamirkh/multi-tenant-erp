"""T143 — Deferred-key execution test: ``execute()`` for
``accounting.tax``/``accounting.cost_center_pl``/
``crossmodule.branch_performance`` raises ``ReportNotFoundError``
indistinguishable from an unregistered key."""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock

import pytest

import modules.reports.registry.load_all  # noqa: F401 — triggers full catalog registration
from modules.reports.exceptions import ReportNotFoundError
from modules.reports.services.execution_service import ReportExecutionService

_DEFERRED_KEYS = (
    "accounting.tax",
    "accounting.cost_center_pl",
    "crossmodule.branch_performance",
)


@pytest.mark.parametrize("report_key", _DEFERRED_KEYS)
def test_execute_raises_not_found_for_deferred_key(report_key: str) -> None:
    service = ReportExecutionService()
    with pytest.raises(ReportNotFoundError) as exc_info:
        service.execute(
            MagicMock(),
            company_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            report_key=report_key,
            raw_filters={},
            page=1,
            page_size=20,
            sort=None,
            comparison=None,
        )
    assert exc_info.value.code == "REPORT_NOT_FOUND"


def test_deferred_key_error_is_identical_to_unregistered_key_error() -> None:
    service = ReportExecutionService()

    with pytest.raises(ReportNotFoundError) as deferred_exc:
        service.execute(
            MagicMock(),
            company_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            report_key="accounting.tax",
            raw_filters={},
            page=1,
            page_size=20,
            sort=None,
            comparison=None,
        )
    with pytest.raises(ReportNotFoundError) as unregistered_exc:
        service.execute(
            MagicMock(),
            company_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            report_key="does.not.exist.at.all",
            raw_filters={},
            page=1,
            page_size=20,
            sort=None,
            comparison=None,
        )

    assert deferred_exc.value.code == unregistered_exc.value.code
    assert deferred_exc.value.http_status == unregistered_exc.value.http_status
