"""T018 — ``BaseReportResult`` subtypes construct and discriminate
correctly."""

from __future__ import annotations

import inspect

from pydantic import BaseModel

from modules.reports.schemas.common import (
    FreshnessClassification,
    PeriodResolution,
    ReportEnvelopeMeta,
)
from modules.reports.services.adapters.base import (
    AggregateReportResult,
    BaseReportResult,
    CursorReportResult,
    PaginatedReportResult,
    ReportAdapter,
)


class _Row(BaseModel):
    label: str


class _Aggregate(BaseModel):
    total: int


def _meta() -> ReportEnvelopeMeta:
    return ReportEnvelopeMeta(
        report_key="test.fixture",
        applied_filters={},
        period=PeriodResolution(
            start="2026-01-01T00:00:00+00:00",
            end="2026-02-01T00:00:00+00:00",
            timezone="UTC",
        ),
        freshness=FreshnessClassification.TRANSACTIONAL_LIVE,
    )


def test_aggregate_report_result_constructs_and_isinstance() -> None:
    result = AggregateReportResult[_Aggregate](meta=_meta(), data=_Aggregate(total=5))
    assert isinstance(result, BaseReportResult)
    assert result.data.total == 5


def test_paginated_report_result_constructs_and_isinstance() -> None:
    result = PaginatedReportResult[_Row](meta=_meta(), items=[_Row(label="a")], total=1)
    assert isinstance(result, BaseReportResult)
    assert result.total == 1
    assert result.items[0].label == "a"


def test_cursor_report_result_constructs_and_isinstance() -> None:
    result = CursorReportResult[_Row](
        meta=_meta(), items=[_Row(label="a")], has_more=True, next_cursor="abc"
    )
    assert isinstance(result, BaseReportResult)
    assert result.has_more is True
    assert result.next_cursor == "abc"


def test_report_adapter_protocol_has_no_any_in_signatures() -> None:
    """Static guard: no method on ``ReportAdapter`` accepts or returns
    ``Any`` (plan.md §10.1 zone 3 — the orchestration boundary must be
    fully typed)."""
    for name, member in inspect.getmembers(ReportAdapter):
        if name.startswith("_"):
            continue
        if not callable(member):
            continue
        signature = inspect.signature(member)
        for param in signature.parameters.values():
            if param.name == "self":
                continue
            assert param.annotation is not None
            assert "Any" not in str(param.annotation)
        assert "Any" not in str(signature.return_annotation)
