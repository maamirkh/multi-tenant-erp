"""CSV/XLSX export writers (plan.md §21.3/§21.4, tasks.md T192/T193).

Both writers consume the same header + row stream ``ReportExportService``
produces batch-by-batch — neither ever receives the full result set as
one list. Every **text** cell passes through ``sanitize_cell()`` (T028)
before it is written (FR-RPT-216).

Typed numeric/date/UUID/bool cells are rendered from their typed value
and are deliberately *not* routed through ``sanitize_cell()``: none of
those types can carry a formula, and the sanitizer's ``-`` prefix rule
would otherwise turn every negative financial amount (an AR credit, a GL
credit line) into the text ``'-125.00`` — silently corrupting the
exported figure. This is exactly the contract ``sanitize_cell()``'s own
docstring states ("non-string-shaped values are returned unmodified by
the caller"). Anything free-text-shaped — ``str``, enum values, nested
``list``/``dict`` payloads serialized to JSON — is always sanitized.
"""

from __future__ import annotations

import csv
import io
import json
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Protocol
from uuid import UUID

from openpyxl import Workbook

from modules.reports.services.csv_sanitizer import sanitize_cell

type XlsxCell = str | int | Decimal | float | None


def _text_cell(value: object) -> str:
    """Stringify a free-text-shaped value and neutralize any formula
    prefix. Nested structures are JSON-encoded first, so a formula
    hidden inside a nested value is sanitized too."""
    if isinstance(value, Enum):
        return sanitize_cell(str(value.value))
    if isinstance(value, str):
        return sanitize_cell(value)
    return sanitize_cell(json.dumps(value, default=str, sort_keys=True))


def _temporal_text(value: date | datetime) -> str:
    return value.isoformat()


def to_csv_cell(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int | Decimal | float):
        return str(value)
    if isinstance(value, date | datetime):
        return _temporal_text(value)
    if isinstance(value, UUID):
        return str(value)
    return _text_cell(value)


def to_xlsx_cell(value: object) -> XlsxCell:
    """Numbers stay native (Excel sums them correctly); dates are written
    as ISO text — openpyxl rejects timezone-aware datetimes outright, and
    report timestamps are always timezone-aware UTC instants."""
    if value is None:
        return None
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int | Decimal | float):
        return value
    if isinstance(value, date | datetime):
        return _temporal_text(value)
    if isinstance(value, UUID):
        return str(value)
    return _text_cell(value)


class TabularWriter(Protocol):
    def write_header(self, headers: list[str]) -> None: ...

    def write_row(self, values: list[object]) -> None: ...

    def finish(self) -> bytes: ...


class CsvExportWriter:
    """``csv.writer`` over an in-memory text buffer (plan.md §21.3 — the
    repo's established export contract returns final ``bytes``; database
    retrieval stays bounded per batch regardless)."""

    def __init__(self) -> None:
        self._buffer = io.StringIO()
        self._writer = csv.writer(self._buffer)

    def write_header(self, headers: list[str]) -> None:
        self._writer.writerow([_text_cell(h) for h in headers])

    def write_row(self, values: list[object]) -> None:
        self._writer.writerow([to_csv_cell(v) for v in values])

    def finish(self) -> bytes:
        # UTF-8 BOM so Excel opens non-ASCII customer/product names
        # correctly; every other CSV consumer ignores it.
        return ("﻿" + self._buffer.getvalue()).encode("utf-8")


class XlsxExportWriter:
    """openpyxl ``write_only=True`` streaming workbook (plan.md §21.4) —
    rows are appended as they arrive and never re-read, so the workbook's
    object graph is not held for the whole sheet."""

    def __init__(self, sheet_title: str) -> None:
        self._workbook = Workbook(write_only=True)
        self._sheet = self._workbook.create_sheet(title=sheet_title[:31])

    def write_header(self, headers: list[str]) -> None:
        self._sheet.append([_text_cell(h) for h in headers])

    def write_row(self, values: list[object]) -> None:
        self._sheet.append([to_xlsx_cell(v) for v in values])

    def finish(self) -> bytes:
        buffer = io.BytesIO()
        self._workbook.save(buffer)
        return buffer.getvalue()
