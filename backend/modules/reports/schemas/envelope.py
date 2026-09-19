"""HTTP-facing envelope wrappers for ``GET /reports/{report_key}`` (T132,
plan.md §9 step 8, FR-RPT-310/311).

FR-RPT-310 requires reusing ``core/schemas/{response,pagination}.py``
**verbatim** — neither ``StandardResponse``/``PaginatedResponse`` nor
Reports' own ``CursorPage`` (T051) is ever modified. FR-RPT-311 requires
``ReportEnvelopeMeta`` (report_key, applied filters, resolved period,
freshness, drill-down refs, comparison) present in *every* report
response, including list-shaped ones — which ``PaginatedData``/
``CursorPage``'s existing, unmodified shapes have no room for.

These three thin, Reports-owned wrapper types resolve that: each embeds
the relevant *unmodified* core/Reports pagination shape as ``data`` and
adds a sibling ``report_meta: ReportEnvelopeMeta`` field alongside the
platform's own ``message``/``meta: ResponseMeta`` — reusing every
existing shape verbatim, never redefining one.

Every generic payload field is wrapped in ``SerializeAsAny`` —
the router (T132) always parametrizes these with the common bound
(``BaseModel``, since the real row/aggregate schema for a given
``report_key`` is only known at runtime, exactly like
``ADAPTER_REGISTRY``'s own typing, plan.md §10.1). Pydantic v2, by
default, serializes a field using its *declared* type's schema, not the
runtime instance's — so an un-wrapped ``AggregateT`` bound to bare
``BaseModel`` would silently serialize every real payload as ``{}``
(caught by ``test_http_trial_balance_equivalence.py`` actually
inspecting non-empty response bodies, where every *other* Phase-3 test
against a fresh, dataless company never has a non-empty payload to
expose it). ``SerializeAsAny`` opts back into "serialize the actual
runtime type" — the correct behavior here, matching every other
closed-union pattern in this Epic.
"""

from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, SerializeAsAny

from core.schemas.pagination import PaginatedData
from core.schemas.response import ResponseMeta
from modules.reports.schemas.common import ReportEnvelopeMeta
from modules.reports.schemas.pagination import CursorPage

AggregateT = TypeVar("AggregateT", bound=BaseModel)
RowT = TypeVar("RowT", bound=BaseModel)


class ReportStandardResponse(BaseModel, Generic[AggregateT]):  # noqa: UP046
    model_config = ConfigDict(from_attributes=True)

    data: SerializeAsAny[AggregateT]
    report_meta: ReportEnvelopeMeta
    message: str
    meta: ResponseMeta


class ReportPaginatedResponse(BaseModel, Generic[RowT]):  # noqa: UP046
    model_config = ConfigDict(from_attributes=True)

    data: PaginatedData[SerializeAsAny[RowT]]
    report_meta: ReportEnvelopeMeta
    message: str
    meta: ResponseMeta


class ReportCursorResponse(BaseModel, Generic[RowT]):  # noqa: UP046
    model_config = ConfigDict(from_attributes=True)

    data: CursorPage[SerializeAsAny[RowT]]
    report_meta: ReportEnvelopeMeta
    message: str
    meta: ResponseMeta
