"""Saved Report View request/response schemas (spec §29, plan.md §15).

The actual per-field rejection of an unregistered filter key happens by
round-tripping the raw ``filter_config`` payload through the *target
report's own* ``ReportDefinition.supported_filters(**payload)`` model at
save/update time (every such model already declares ``extra="forbid"``) —
never by ``FilterConfigV1`` alone, since ``filter_config``'s real shape is
entirely report-specific and cannot be fixed generically. ``FilterConfigV1``
is the named, versioned envelope marker `schema_version` refers to (v1
has no base-level fields of its own — a future v2 could add one without
breaking storage, plan.md §15).
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from modules.reports.schemas.common import JsonValue


class FilterConfigV1(BaseModel):
    """Version-1 saved-view filter-storage envelope marker."""

    model_config = ConfigDict(extra="forbid")


class SavedReportViewCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    report_key: str
    name: str
    filter_config: dict[str, JsonValue]
    grouping: list[str] | None = None
    sorting: str | None = None
    visible_columns: list[str] | None = None
    date_preset: str | None = None


class SavedReportViewUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    report_key: str | None = None
    name: str | None = None
    filter_config: dict[str, JsonValue] | None = None
    grouping: list[str] | None = None
    sorting: str | None = None
    visible_columns: list[str] | None = None
    date_preset: str | None = None


class SavedReportViewRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    report_key: str
    name: str
    schema_version: int
    filter_config: dict[str, JsonValue]
    grouping: list[str] | None
    sorting: str | None
    visible_columns: list[str] | None
    date_preset: str | None
    created_at: datetime
    updated_at: datetime
