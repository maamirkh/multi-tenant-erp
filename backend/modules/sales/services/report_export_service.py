"""Report Export Service — Phase 8.

Converts ReportResponse rows to CSV or Excel (xlsx) bytes.

Supports:
  - ExportFormat.CSV   → UTF-8 CSV bytes via csv module (no extra deps)
  - ExportFormat.EXCEL → xlsx bytes via openpyxl

Task: T212
Spec ref: specs/007-sales-management/spec.md §35
"""

from __future__ import annotations

import csv
import io
import logging
from typing import Any

from modules.sales.schemas.reports import ExportFormat, ReportResponse

log = logging.getLogger(__name__)


class ReportExportService:
    """Convert a ReportResponse to bytes for file download."""

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def export(
        self, report: ReportResponse, fmt: ExportFormat
    ) -> tuple[bytes, str, str]:
        """Export *report* rows to the requested format.

        Returns:
            (file_bytes, filename, content_type)
        """
        if fmt == ExportFormat.CSV:
            return self._to_csv(report)
        return self._to_excel(report)

    # ------------------------------------------------------------------
    # CSV
    # ------------------------------------------------------------------

    def _to_csv(self, report: ReportResponse) -> tuple[bytes, str, str]:
        buf = io.StringIO()
        if not report.rows:
            buf.write("")
        else:
            headers = list(report.rows[0].keys())
            writer = csv.DictWriter(buf, fieldnames=headers, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(report.rows)
        filename = f"{report.report_type}_{report.company_id[:8]}.csv"
        return buf.getvalue().encode("utf-8"), filename, "text/csv; charset=utf-8"

    # ------------------------------------------------------------------
    # Excel
    # ------------------------------------------------------------------

    def _to_excel(self, report: ReportResponse) -> tuple[bytes, str, str]:
        try:
            import openpyxl
            from openpyxl.styles import Font, PatternFill
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError(
                "openpyxl is required for Excel export. "
                "Install it with: pip install openpyxl"
            ) from exc

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = report.report_type[:31]  # Excel sheet name max 31 chars

        if report.rows:
            headers = list(report.rows[0].keys())

            # Header row — bold + light blue fill
            header_fill = PatternFill(
                start_color="4472C4", end_color="4472C4", fill_type="solid"
            )
            header_font = Font(bold=True, color="FFFFFF")
            for col_idx, header in enumerate(headers, start=1):
                cell = ws.cell(row=1, column=col_idx, value=header)
                cell.fill = header_fill
                cell.font = header_font

            # Data rows
            for row_idx, row_data in enumerate(report.rows, start=2):
                for col_idx, key in enumerate(headers, start=1):
                    ws.cell(
                        row=row_idx,
                        column=col_idx,
                        value=_excel_value(row_data.get(key)),
                    )

            # Auto-fit column widths (approximate)
            for col in ws.columns:
                max_len = max(
                    (
                        len(str(cell.value)) if cell.value is not None else 0
                        for cell in col
                    ),
                    default=10,
                )
                ws.column_dimensions[col[0].column_letter].width = min(max_len + 2, 50)

        buf = io.BytesIO()
        wb.save(buf)
        filename = f"{report.report_type}_{report.company_id[:8]}.xlsx"
        content_type = (
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        return buf.getvalue(), filename, content_type


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _excel_value(v: Any) -> Any:
    """Convert report cell value to a type Excel can natively handle."""
    if v is None:
        return None
    if isinstance(v, bool):
        return v
    try:
        from decimal import Decimal

        if isinstance(v, Decimal):
            return float(v)
    except Exception:
        pass
    return str(v) if not isinstance(v, int | float) else v
