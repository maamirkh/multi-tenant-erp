"""Export request/result contracts (plan.md §21, tasks.md T186).

``ExportRequest`` is the validated shape of ``GET /{report_key}/export``'s
own query parameters (``filters[...]`` travel separately, as the same raw
deepObject dict the online route uses, so both paths validate filters
through the identical ``_authorize_and_validate()`` step).

``ExportResult`` is internal — never serialized to JSON. The router turns
it into a file ``Response`` only after ``ReportExportService`` has
durably committed the export's audit row (§21.8).
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from modules.reports.registry.definitions import ExportFormat


class ExportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    format: ExportFormat
    sort: str | None = None


class ExportResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    content: bytes
    filename: str
    content_type: str
    row_count: int | None
    """Data rows written (list/aggregate exports); ``None`` for PDF, whose
    row structure is owned by Accounting's own template."""
