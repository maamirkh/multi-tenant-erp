"""Typed report result hierarchy + the ``ReportAdapter`` Protocol
(plan.md §10.1) — the one place in Reports' own code where `Any` may
appear (only as a *local* variable inside a concrete adapter's
translation step, never as a parameter/return type here).

``ADAPTER_REGISTRY``/``COMPOSITE_REPORT_HANDLERS`` are declared here, both
empty at Phase 0, and populated incrementally: ``ADAPTER_REGISTRY`` once
per domain in Phase 2; ``COMPOSITE_REPORT_HANDLERS`` exactly twice, in
Phases 4 and 5 (T033).
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from typing import Generic, Protocol, TypeVar
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy.orm import Session

from modules.reports.registry.definitions import ReportDomain
from modules.reports.schemas.common import ComparisonRequest, ReportEnvelopeMeta

AggregateT = TypeVar("AggregateT", bound=BaseModel)
RowT = TypeVar("RowT", bound=BaseModel)


class BaseReportResult(BaseModel):
    """Common base every concrete report result subtypes."""

    meta: ReportEnvelopeMeta


class AggregateReportResult(BaseReportResult, Generic[AggregateT]):  # noqa: UP046
    """Statement/KPI-dashboard-shaped results — ``pagination == NONE``."""

    data: AggregateT


class PaginatedReportResult(BaseReportResult, Generic[RowT]):  # noqa: UP046
    """Offset-paginated list report results."""

    items: list[RowT]
    total: int


class CursorReportResult(BaseReportResult, Generic[RowT]):  # noqa: UP046
    """Cursor-paginated list report results (``accounting.gl`` only)."""

    items: list[RowT]
    has_more: bool
    next_cursor: str | None


ReportResultT_co = TypeVar("ReportResultT_co", bound=BaseReportResult, covariant=True)


class ReportAdapter(Protocol[ReportResultT_co]):
    """Every concrete domain adapter (Phase 2) implements this Protocol.
    No method signature here may accept or return ``Any`` (plan.md §10.1
    zone 3).

    **Correction (discovered during Phase 2 implementation)**: plan.md
    §10.1/§9's original signatures omitted both ``company_id`` and ``db``
    entirely — an adapter instance is a single, module-level,
    request-agnostic object registered once in ``ADAPTER_REGISTRY``
    (populated at import time, before any request/session/tenant
    context exists), so neither tenant scoping nor the database session
    can be bound at construction time; both must be threaded through on
    every call. Every concrete adapter is therefore **stateless** —
    holding no pre-built service instances — and builds the specific
    per-module service it needs, fresh, inside each call, from the
    module's own existing ``build_<x>_service(db)`` factory functions
    (the same plain, ``Depends()``-free factories every module's own
    ``dependencies.py`` already exposes). This is the smallest possible
    fix to two genuine gaps, not a redesign."""

    def run(
        self,
        db: Session,
        company_id: UUID,
        report_key: str,
        filters: BaseModel,
        page: int,
        page_size: int,
        sort: str | None,
        comparison: ComparisonRequest | None,
    ) -> ReportResultT_co: ...

    def count_export_rows(
        self, db: Session, company_id: UUID, report_key: str, filters: BaseModel
    ) -> int: ...

    def iter_export_rows(
        self,
        db: Session,
        company_id: UUID,
        report_key: str,
        filters: BaseModel,
        sort: str | None,
        batch_size: int,
    ) -> Iterator[list[BaseModel]]: ...


# One adapter per ``ReportDomain`` — populated incrementally through
# Phase 2 as each domain's adapter is implemented. Empty and importable
# from Phase 0 onward so nothing downstream ever forward-references its
# creation.
ADAPTER_REGISTRY: dict[ReportDomain, ReportAdapter[BaseReportResult]] = {}

# Keyed by ``report_key`` (not domain) — populated exactly twice, in
# Phase 4 (``exec.dashboard``) and Phase 5 (``crossmodule.customer_360``).
# Lets the registry-consistency test (T032) verify, by identity, that a
# COMPOSITE report's registered handler is the exact same callable its
# dedicated route actually calls.
COMPOSITE_REPORT_HANDLERS: dict[str, Callable[..., BaseModel]] = {}
