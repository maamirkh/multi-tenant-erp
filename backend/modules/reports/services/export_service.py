"""``ReportExportService`` — the one export path (plan.md §21, tasks.md
T187–T195).

Exact ordering inside ``export()`` (§21.8):

1. ``ReportExecutionService._authorize_and_validate(permission_kind=
   "export")`` — the **identical** preamble ``execute()`` runs (registry,
   domain entitlement incl. Installments Case A/B, RBAC, filters, sort),
   differing only in checking ``definition.export_permission``
   (FR-RPT-212/213). Then the requested format is checked against
   ``definition.export_formats``.
2. Bounded retrieval, by category (tasks.md's Final Export Category
   Matrix):

   - **A** (SQL-bounded list reports) / **B** (Installments
     ``due_overdue``/``aging``, hard-capped population): one
     ``count_export_rows()`` call; over the format's limit →
     ``ExportTooLargeError`` **before** ``iter_export_rows()`` is ever
     called; otherwise stream ``iter_export_rows()`` batches.
   - **B-cursor** (``accounting.gl``): no count. Stream cursor batches,
     tracking the cumulative count; the moment the ``limit+1``th row is
     observed, stop pulling pages and raise ``ExportTooLargeError``.
   - **D** (aggregates): one ``adapter.run()``, fixed shape serialized
     directly — no count/iterate seam is touched.
   - **PDF** (four Accounting statements): delegated to
     ``AccountingAdapter.export_pdf()`` → Accounting's own
     ``export_to_pdf()``.

3. Only after the file bytes are fully built: stage the audit row, commit.
   **Only if the commit succeeds** is the ``ExportResult`` returned. A
   commit failure discards the bytes and raises
   ``ExportAuditPersistenceError`` — there is no delivered export without
   a durable audit record.

Every dispatch goes through ``ADAPTER_REGISTRY`` *inside this service* —
the router never touches an adapter (T212).
"""

from __future__ import annotations

import logging
from collections.abc import Generator, Iterator, Mapping
from datetime import date, datetime
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import BaseModel
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from modules.reports import constants
from modules.reports.exceptions import (
    ExportAuditPersistenceError,
    ExportTooLargeError,
    FilterValidationError,
)
from modules.reports.registry.definitions import (
    ExportFormat,
    PaginationStyle,
    ReportDefinition,
)
from modules.reports.repositories.reports_audit_repository import (
    ReportsAuditRepository,
)
from modules.reports.schemas.export import ExportResult
from modules.reports.services.adapters.accounting_adapter import AccountingAdapter
from modules.reports.services.adapters.base import (
    ADAPTER_REGISTRY,
    AggregateReportResult,
    BaseReportResult,
    ReportAdapter,
)
from modules.reports.services.audit_service import ReportsAuditService
from modules.reports.services.execution_service import ReportExecutionService
from modules.reports.services.export_writers import (
    CsvExportWriter,
    TabularWriter,
    XlsxExportWriter,
)

logger = logging.getLogger(__name__)

_CONTENT_TYPES: Mapping[ExportFormat, str] = {
    ExportFormat.CSV: "text/csv; charset=utf-8",
    ExportFormat.XLSX: (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    ),
    ExportFormat.PDF: "application/pdf",
}

_AGGREGATE_HEADERS = ["field", "value"]


class ExportCategory(StrEnum):
    """tasks.md's Final Export Category Matrix, as a typed discriminator."""

    BOUNDED_SQL = "A"
    BOUNDED_POPULATION = "B"
    CURSOR_LIMIT_PLUS_ONE = "B-cursor"
    AGGREGATE = "D"


#: Category B's only members — bounded by the genuinely enforced
#: ``InstallmentReportingService._DUE_STATE_POPULATION_BOUND`` hard cap
#: (re-verified in T118), never by a "finite customer count" argument.
_BOUNDED_POPULATION_KEYS: frozenset[str] = frozenset(
    {"installments.due_overdue", "installments.aging"}
)


def export_category(definition: ReportDefinition) -> ExportCategory:
    if definition.pagination is PaginationStyle.CURSOR:
        return ExportCategory.CURSOR_LIMIT_PLUS_ONE
    if definition.pagination is PaginationStyle.NONE:
        return ExportCategory.AGGREGATE
    if definition.key in _BOUNDED_POPULATION_KEYS:
        return ExportCategory.BOUNDED_POPULATION
    return ExportCategory.BOUNDED_SQL


def row_limit_for(export_format: ExportFormat) -> int:
    """XLSX is independently lower than CSV (plan.md §21.4) — read at call
    time, so a limit tuned in ``constants`` (T214) always applies."""
    if export_format is ExportFormat.XLSX:
        return constants.EXPORT_ROW_LIMIT_XLSX
    return constants.EXPORT_ROW_LIMIT_CSV


def build_filename(
    report_key: str, filters: BaseModel, export_format: ExportFormat
) -> str:
    """``report_key`` (registry-controlled) + the filter scope's typed
    date values + extension — never an unescaped user string
    (FR-RPT-215). E.g. ``sales-summary_2026-08-01_2026-08-31.csv``."""
    parts = [report_key.replace(".", "-")]
    for field_name in type(filters).model_fields:
        value = getattr(filters, field_name)
        if isinstance(value, datetime):
            parts.append(value.date().isoformat())
        elif isinstance(value, date):
            parts.append(value.isoformat())
    return f"{'_'.join(parts)}.{export_format.value}"


def _flatten(prefix: str, value: object, out: list[tuple[str, object]]) -> None:
    if isinstance(value, dict):
        for key, nested in value.items():
            _flatten(f"{prefix}.{key}" if prefix else str(key), nested, out)
    elif isinstance(value, list):
        if not value:
            out.append((prefix, None))
        for index, nested in enumerate(value):
            _flatten(f"{prefix}.{index}", nested, out)
    else:
        out.append((prefix, value))


def _new_writer(export_format: ExportFormat, report_key: str) -> TabularWriter:
    if export_format is ExportFormat.XLSX:
        return XlsxExportWriter(sheet_title=report_key)
    return CsvExportWriter()


class ReportExportService:
    """Stateless apart from the shared ``ReportExecutionService`` whose
    authorization preamble it reuses."""

    def __init__(self, execution_service: ReportExecutionService | None = None) -> None:
        self._execution_service = execution_service or ReportExecutionService()

    def export(
        self,
        db: Session,
        *,
        company_id: UUID,
        user_id: UUID | None,
        report_key: str,
        raw_filters: Mapping[str, object],
        sort: str | None,
        export_format: ExportFormat,
        user_roles: list[str] | None = None,
    ) -> ExportResult:
        # Step 1 — the identical authorization/validation path execute()
        # uses; only the permission kind differs (T187).
        definition, filters, _is_servicing_continuity = (
            self._execution_service._authorize_and_validate(  # noqa: SLF001 — the sanctioned shared preamble (plan.md §21.1)
                db,
                company_id=company_id,
                user_id=user_id,
                report_key=report_key,
                raw_filters=raw_filters,
                sort=sort,
                permission_kind="export",
                user_roles=user_roles,
            )
        )
        if export_format not in definition.export_formats:
            raise FilterValidationError(
                report_key,
                f"export format '{export_format.value}' is not supported "
                "for this report",
            )

        # Step 2 — bounded retrieval + file generation.
        adapter = ADAPTER_REGISTRY[definition.domain]
        content, row_count = self._generate(
            db, adapter, company_id, definition, filters, sort, export_format
        )

        # Step 3 — durable audit before delivery (T195).
        self._commit_audit(
            db,
            company_id=company_id,
            user_id=user_id,
            report_key=definition.key,
            filters=filters,
            export_format=export_format,
            row_count=row_count,
        )
        logger.info(
            "Report exported: report_key=%s company=%s format=%s rows=%s",
            definition.key,
            company_id,
            export_format.value,
            row_count,
        )
        return ExportResult(
            content=content,
            filename=build_filename(definition.key, filters, export_format),
            content_type=_CONTENT_TYPES[export_format],
            row_count=row_count,
        )

    # ------------------------------------------------------------------
    # Step 2 — generation per category
    # ------------------------------------------------------------------

    def _generate(
        self,
        db: Session,
        adapter: ReportAdapter[BaseReportResult],
        company_id: UUID,
        definition: ReportDefinition,
        filters: BaseModel,
        sort: str | None,
        export_format: ExportFormat,
    ) -> tuple[bytes, int | None]:
        if export_format is ExportFormat.PDF:
            return self._export_pdf(db, adapter, company_id, definition, filters)

        category = export_category(definition)
        writer = _new_writer(export_format, definition.key)
        if category is ExportCategory.AGGREGATE:
            row_count = self._write_aggregate(
                db, adapter, company_id, definition, filters, writer
            )
            return writer.finish(), row_count

        limit = row_limit_for(export_format)
        if category is not ExportCategory.CURSOR_LIMIT_PLUS_ONE:
            # Categories A and B — count first, reject before any batch
            # retrieval (T188/T189).
            count = adapter.count_export_rows(db, company_id, definition.key, filters)
            if count > limit:
                raise ExportTooLargeError(definition.key, count, limit)

        batches = adapter.iter_export_rows(
            db,
            company_id,
            definition.key,
            filters,
            sort,
            constants.EXPORT_BATCH_SIZE,
        )
        row_count = self._write_batches(adapter, definition.key, batches, writer, limit)
        return writer.finish(), row_count

    def _write_batches(
        self,
        adapter: ReportAdapter[BaseReportResult],
        report_key: str,
        batches: Iterator[list[BaseModel]],
        writer: TabularWriter,
        limit: int,
    ) -> int:
        """Streams batches into *writer*, tracking the cumulative row
        count. For GL this *is* the limit+1 detection (T190): the check
        runs as each batch arrives, before the next cursor page is
        pulled, and the adapter's generator is closed so no
        further page is ever requested. For A/B it is a defence-in-depth
        guard against rows appearing between count and iterate."""
        headers: list[str] | None = None
        written = 0
        try:
            for batch in batches:
                written += len(batch)
                if written > limit:
                    raise ExportTooLargeError(report_key, written, limit)
                for row in batch:
                    values = row.model_dump(mode="python")
                    if headers is None:
                        headers = list(values)
                        writer.write_header(headers)
                    writer.write_row([values.get(h) for h in headers])
        finally:
            if isinstance(batches, Generator):
                batches.close()
        if headers is None:
            # Zero rows — still a valid file with the row schema's own
            # headers (FR-RPT-219).
            row_model = adapter.export_row_model(report_key)
            writer.write_header(list(row_model.model_fields))
        return written

    def _write_aggregate(
        self,
        db: Session,
        adapter: ReportAdapter[BaseReportResult],
        company_id: UUID,
        definition: ReportDefinition,
        filters: BaseModel,
        writer: TabularWriter,
    ) -> int:
        """Category D (T191): one ``run()``, the fixed aggregate shape
        flattened to ``field``/``value`` rows — nested sections become
        dotted paths (``sections.0.lines.2.amount``)."""
        result = adapter.run(db, company_id, definition.key, filters, 1, 1, None, None)
        assert isinstance(result, AggregateReportResult)
        flattened: list[tuple[str, object]] = []
        _flatten("", result.data.model_dump(mode="python"), flattened)
        writer.write_header(list(_AGGREGATE_HEADERS))
        for path, value in flattened:
            writer.write_row([path, value])
        return len(flattened)

    def _export_pdf(
        self,
        db: Session,
        adapter: ReportAdapter[BaseReportResult],
        company_id: UUID,
        definition: ReportDefinition,
        filters: BaseModel,
    ) -> tuple[bytes, int | None]:
        """T194 — only Accounting's statements list PDF in
        ``export_formats`` (already enforced in step 1); delegate to
        Accounting's own ``export_to_pdf()`` via the adapter."""
        if not isinstance(adapter, AccountingAdapter):
            raise FilterValidationError(
                definition.key, "export format 'pdf' is not supported for this report"
            )
        return adapter.export_pdf(db, company_id, definition.key, filters), None

    # ------------------------------------------------------------------
    # Step 3 — audit durability
    # ------------------------------------------------------------------

    def _commit_audit(
        self,
        db: Session,
        *,
        company_id: UUID,
        user_id: UUID | None,
        report_key: str,
        filters: BaseModel,
        export_format: ExportFormat,
        row_count: int | None,
    ) -> None:
        try:
            ReportsAuditService(ReportsAuditRepository(db)).record(
                company_id=company_id,
                entity_type="ReportExport",
                entity_id=uuid4(),
                action="EXPORTED",
                actor_id=user_id,
                report_key=report_key,
                filter_scope=filters.model_dump(mode="json"),
                export_format=export_format.value.upper(),
                row_count=row_count,
            )
            db.commit()
        except SQLAlchemyError as exc:
            db.rollback()
            logger.error(
                "Report export audit commit failed — export not delivered: "
                "report_key=%s company=%s",
                report_key,
                company_id,
            )
            raise ExportAuditPersistenceError(report_key) from exc
