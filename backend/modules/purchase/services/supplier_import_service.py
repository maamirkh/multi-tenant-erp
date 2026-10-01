"""Supplier bulk import service — Phase 1.

Supports CSV/Excel imports of up to 10,000 supplier rows.

Processing:
  1. Parse rows from CSV bytes (or pre-parsed list[Any] of dicts)
  2. Validate each row (schema + business rules)
  3. Skip rows with errors (collect per-row error list[Any])
  4. Create valid suppliers via SupplierService
  5. Return BulkImportResult with totals and row-level errors

Error handling:
  - Row-level errors do NOT stop the import; all valid rows are processed.
  - Duplicate supplier_code in the same batch → skip with error.
  - Duplicate supplier_code already in DB → skip with error.

Spec ref: specs/006-purchase-management/spec.md §37 Import & Export
Task: T041
"""

from __future__ import annotations

import csv
import io
import logging
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from core.exceptions.base import ConflictException
from modules.purchase.repositories.supplier import (
    SupplierRepository,
)
from modules.purchase.schemas.supplier import (
    BulkImportResult,
    SupplierImportRowError,
)
from modules.purchase.services.supplier_service import SupplierService

logger = logging.getLogger(__name__)

MAX_IMPORT_ROWS = 10_000
REQUIRED_COLUMNS = {"supplier_code", "legal_name"}
VALID_SUPPLIER_TYPES = {"GOODS", "SERVICES", "BOTH"}


class SupplierImportService:
    """Processes a CSV/Excel supplier import file and creates suppliers in bulk."""

    def __init__(
        self,
        db: Session,
        supplier_service: SupplierService,
        supplier_repo: SupplierRepository,
    ) -> None:
        self.db = db
        self._svc = supplier_service
        self._repo = supplier_repo

    def import_from_csv(
        self,
        company_id: UUID,
        csv_bytes: bytes,
        actor_id: UUID | None = None,
    ) -> BulkImportResult:
        """Import suppliers from CSV bytes.

        Args:
            company_id: Company scope for all imported suppliers.
            csv_bytes:  Raw CSV file content (UTF-8 or latin-1 encoded).
            actor_id:   The user performing the import (for audit trail).

        Returns:
            BulkImportResult with counts and per-row errors.
        """
        try:
            text = csv_bytes.decode("utf-8-sig")  # strip BOM
        except UnicodeDecodeError:
            text = csv_bytes.decode("latin-1", errors="replace")

        reader = csv.DictReader(io.StringIO(text))
        rows = list[Any](reader)
        return self._process_rows(company_id=company_id, rows=rows, actor_id=actor_id)

    def import_from_rows(
        self,
        company_id: UUID,
        rows: list[dict[str, Any]],
        actor_id: UUID | None = None,
    ) -> BulkImportResult:
        """Import suppliers from a pre-parsed list[Any] of dicts.

        Used by tests and Excel parsers.
        """
        return self._process_rows(company_id=company_id, rows=rows, actor_id=actor_id)

    # -----------------------------------------------------------------------
    # Internal processing
    # -----------------------------------------------------------------------

    def _process_rows(
        self,
        company_id: UUID,
        rows: list[dict[str, Any]],
        actor_id: UUID | None,
    ) -> BulkImportResult:
        total_rows = len(rows)
        if total_rows > MAX_IMPORT_ROWS:
            rows = rows[:MAX_IMPORT_ROWS]
            logger.warning(
                "Import truncated to %d rows (company_id=%s)",
                MAX_IMPORT_ROWS,
                company_id,
            )

        created = 0
        skipped = 0
        failed = 0
        errors: list[SupplierImportRowError] = []
        seen_codes: set[str] = set()

        for row_num, raw_row in enumerate(
            rows, start=2
        ):  # 2 = first data row (1 is header)
            row_errors: list[str] = []
            row = {
                k.strip().lower(): (v.strip() if isinstance(v, str) else v)
                for k, v in raw_row.items()
            }

            # --- Required field validation ---
            supplier_code = row.get("supplier_code", "").upper()
            legal_name = row.get("legal_name", "")

            if not supplier_code:
                row_errors.append("supplier_code is required")
            if not legal_name:
                row_errors.append("legal_name is required")

            if row_errors:
                errors.append(
                    SupplierImportRowError(
                        row_number=row_num,
                        supplier_code=supplier_code or None,
                        errors=row_errors,
                    )
                )
                failed += 1
                continue

            # --- Duplicate within batch ---
            if supplier_code in seen_codes:
                errors.append(
                    SupplierImportRowError(
                        row_number=row_num,
                        supplier_code=supplier_code,
                        errors=[
                            f"Duplicate supplier_code '{supplier_code}' in import batch"
                        ],
                    )
                )
                skipped += 1
                continue
            seen_codes.add(supplier_code)

            # --- Optional field validation ---
            supplier_type = row.get("supplier_type", "GOODS").upper()
            if supplier_type not in VALID_SUPPLIER_TYPES:
                row_errors.append(
                    f"supplier_type must be one of {sorted(VALID_SUPPLIER_TYPES)}"
                )

            lead_time_raw = row.get("lead_time_days", "")
            lead_time_days: int | None = None
            if lead_time_raw:
                try:
                    lead_time_days = int(lead_time_raw)
                    if lead_time_days < 0:
                        row_errors.append("lead_time_days must be >= 0")
                        lead_time_days = None
                except ValueError:
                    row_errors.append("lead_time_days must be an integer")

            if row_errors:
                errors.append(
                    SupplierImportRowError(
                        row_number=row_num,
                        supplier_code=supplier_code,
                        errors=row_errors,
                    )
                )
                failed += 1
                continue

            # --- Create supplier ---
            try:
                self._svc.create(
                    company_id=company_id,
                    supplier_code=supplier_code,
                    legal_name=legal_name,
                    supplier_type=supplier_type,
                    trading_name=row.get("trading_name") or None,
                    currency_code=(row.get("currency_code") or "USD").upper(),
                    website=row.get("website") or None,
                    notes=row.get("notes") or None,
                    lead_time_days=lead_time_days,
                    tax_registration_number=row.get("tax_registration_number") or None,
                    actor_id=actor_id,
                )
                created += 1
            except ConflictException:
                errors.append(
                    SupplierImportRowError(
                        row_number=row_num,
                        supplier_code=supplier_code,
                        errors=[f"Supplier code '{supplier_code}' already exists"],
                    )
                )
                skipped += 1
            except Exception as exc:
                logger.warning(
                    "Import row %d failed (code=%s): %s", row_num, supplier_code, exc
                )
                errors.append(
                    SupplierImportRowError(
                        row_number=row_num,
                        supplier_code=supplier_code,
                        errors=[str(exc)],
                    )
                )
                failed += 1

        return BulkImportResult(
            total_rows=total_rows,
            created=created,
            skipped=skipped,
            failed=failed,
            errors=errors,
        )
