"""Purchase report export service — Phase 9.

Provides CSV and Excel (xlsx) export for all 14 purchase reports.

Dependencies:
  - csv (stdlib)
  - openpyxl (already in backend/pyproject.toml via xlrd/openpyxl)

Task: T222
"""

from __future__ import annotations

import csv
import io
import logging
from typing import Any

logger = logging.getLogger(__name__)


class ReportExportService:
    """Convert report row-dicts to CSV or Excel byte streams."""

    # ------------------------------------------------------------------
    # CSV
    # ------------------------------------------------------------------

    @staticmethod
    def to_csv(rows: list[dict[str, Any]], *, report_name: str = "report") -> bytes:
        """Serialise a list of dicts to a UTF-8 CSV byte string.

        Returns an empty CSV with header-only when rows is empty.
        """
        if not rows:
            return b""

        output = io.StringIO()
        writer = csv.DictWriter(
            output, fieldnames=list(rows[0].keys()), lineterminator="\n"
        )
        writer.writeheader()
        writer.writerows(rows)
        return output.getvalue().encode("utf-8-sig")  # BOM for Excel compatibility

    # ------------------------------------------------------------------
    # Excel (xlsx)
    # ------------------------------------------------------------------

    @staticmethod
    def to_excel(rows: list[dict[str, Any]], *, sheet_name: str = "Report") -> bytes:
        """Serialise a list of dicts to an xlsx byte string.

        Uses openpyxl.  Raises ImportError when openpyxl is not installed.
        """
        try:
            import openpyxl
            from openpyxl.styles import Font, PatternFill
        except ImportError as exc:
            raise ImportError(
                "openpyxl is required for Excel export. "
                "Install it with: pip install openpyxl"
            ) from exc

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = sheet_name[:31]  # Excel tab name max 31 chars

        if not rows:
            output = io.BytesIO()
            wb.save(output)
            return output.getvalue()

        headers = list(rows[0].keys())

        # Header row with styling
        header_fill = PatternFill(
            start_color="2E5090", end_color="2E5090", fill_type="solid"
        )
        header_font = Font(color="FFFFFF", bold=True)
        for col_idx, header in enumerate(headers, start=1):
            cell = ws.cell(
                row=1, column=col_idx, value=header.replace("_", " ").title()
            )
            cell.fill = header_fill
            cell.font = header_font

        # Data rows
        for row_idx, row in enumerate(rows, start=2):
            for col_idx, key in enumerate(headers, start=1):
                ws.cell(
                    row=row_idx,
                    column=col_idx,
                    value=str(row[key]) if row[key] is not None else "",
                )

        # Auto-width columns
        for col in ws.columns:
            max_length = max((len(str(cell.value or "")) for cell in col), default=10)
            ws.column_dimensions[col[0].column_letter].width = min(max_length + 4, 50)

        output = io.BytesIO()
        wb.save(output)
        return output.getvalue()
