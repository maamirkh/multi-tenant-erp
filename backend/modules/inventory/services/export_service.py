"""ExportService — CSV and Excel export for inventory reports.

Converts any list-of-dicts report result into:
  - CSV  (in-memory, returned as bytes)
  - XLSX (in-memory via openpyxl, returned as bytes)

When a ``StorageClient`` is provided the file is uploaded to S3 and a
download URL is returned.  If storage is None the caller receives the raw
bytes (useful for streaming responses or tests).

Spec ref: specs/005-inventory-management/spec.md §35 (Import & Export)
"""

from __future__ import annotations

import csv
import io
import logging
from datetime import datetime
from decimal import Decimal
from typing import Any

import openpyxl
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter

from core.utils.datetime import utcnow

logger = logging.getLogger(__name__)


def _safe_str(value: Any) -> str:
    """Convert any value to a clean string for CSV/Excel cells."""
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, bool):
        return "Yes" if value else "No"
    return str(value)


class ExportService:
    """Converts report row dicts into downloadable CSV or XLSX files.

    Usage::

        svc = ExportService(storage=None)  # no upload → returns bytes
        csv_bytes, fname = svc.to_csv(rows, report_name="inventory_summary")
        xlsx_bytes, fname = svc.to_xlsx(rows, report_name="inventory_summary")
    """

    def __init__(self, storage: Any = None) -> None:
        """
        Args:
            storage: Optional ``StorageClient`` instance.  When provided,
                     ``export_and_upload`` stores the file and returns a URL.
        """
        self._storage = storage

    # -------------------------------------------------------------------------
    # CSV
    # -------------------------------------------------------------------------

    def to_csv(
        self, rows: list[dict[str, Any]], *, report_name: str = "report"
    ) -> tuple[bytes, str]:
        """Return (csv_bytes, filename)."""
        if not rows:
            file_name = f"{report_name}_{_ts()}.csv"
            return b"", file_name

        buf = io.StringIO()
        headers = list(rows[0].keys())
        writer = csv.DictWriter(buf, fieldnames=headers)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: _safe_str(v) for k, v in row.items()})

        file_name = f"{report_name}_{_ts()}.csv"
        return buf.getvalue().encode("utf-8-sig"), file_name

    # -------------------------------------------------------------------------
    # Excel
    # -------------------------------------------------------------------------

    def to_xlsx(
        self, rows: list[dict[str, Any]], *, report_name: str = "report"
    ) -> tuple[bytes, str]:
        """Return (xlsx_bytes, filename)."""
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = report_name[:31]  # Excel sheet name max 31 chars

        file_name = f"{report_name}_{_ts()}.xlsx"

        if not rows:
            buf = io.BytesIO()
            wb.save(buf)
            return buf.getvalue(), file_name

        headers = list(rows[0].keys())

        # Header row style
        header_fill = PatternFill(fill_type="solid", fgColor="1F4E79")
        header_font = Font(bold=True, color="FFFFFF")
        for col_idx, header in enumerate(headers, start=1):
            cell = ws.cell(
                row=1, column=col_idx, value=header.replace("_", " ").title()
            )
            cell.fill = header_fill
            cell.font = header_font

        # Data rows
        for row_idx, row in enumerate(rows, start=2):
            for col_idx, key in enumerate(headers, start=1):
                value = row.get(key)
                if isinstance(value, datetime):
                    ws.cell(row=row_idx, column=col_idx, value=value)
                elif isinstance(value, Decimal):
                    ws.cell(row=row_idx, column=col_idx, value=float(value))
                elif isinstance(value, bool):
                    ws.cell(row=row_idx, column=col_idx, value="Yes" if value else "No")
                else:
                    ws.cell(row=row_idx, column=col_idx, value=value)

        # Auto-fit columns (approximate)
        for col_idx, header in enumerate(headers, start=1):
            col_letter = get_column_letter(col_idx)
            max_len = max(
                len(header),
                *(
                    len(_safe_str(rows[i].get(header, "")))
                    for i in range(min(len(rows), 50))  # sample first 50 rows
                ),
            )
            ws.column_dimensions[col_letter].width = min(max_len + 2, 40)

        buf = io.BytesIO()
        wb.save(buf)
        return buf.getvalue(), file_name

    # -------------------------------------------------------------------------
    # Upload to S3
    # -------------------------------------------------------------------------

    def export_and_upload(
        self,
        rows: list[dict[str, Any]],
        *,
        report_name: str = "report",
        fmt: str = "csv",
        company_id: str = "unknown",
    ) -> dict[str, Any]:
        """Export rows to CSV or XLSX, upload to S3, return metadata dict.

        Returns:
            dict with keys: download_url, file_name, format, row_count
        """
        if fmt == "xlsx":
            data, file_name = self.to_xlsx(rows, report_name=report_name)
        else:
            data, file_name = self.to_csv(rows, report_name=report_name)

        key = f"exports/{company_id}/{file_name}"
        download_url = ""

        if self._storage is not None:
            try:
                buf = io.BytesIO(data)
                download_url = self._storage.upload(buf, key)
            except Exception:
                logger.warning("S3 upload failed for %s — returning empty URL", key)
        else:
            # No storage client: return placeholder URL for test/dev
            download_url = f"/dev/exports/{file_name}"

        return {
            "download_url": download_url,
            "file_name": file_name,
            "format": fmt,
            "row_count": len(rows),
        }


def _ts() -> str:
    """Compact UTC timestamp for file naming."""
    return utcnow().strftime("%Y%m%d_%H%M%S")
