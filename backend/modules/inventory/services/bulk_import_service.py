"""BulkImportService — synchronous CSV product import.

Accepts an uploaded CSV file, processes rows synchronously (suitable for files
up to ~500 rows), records results in an ImportJob, and returns the job record.

CSV format expected:
  product_code,name,product_type,base_uom_code,description,cost_price,
  category_code,brand_code,hs_code,country_of_origin,lead_time_days,
  min_order_qty,max_order_qty,is_serialized,is_batch_tracked

Spec ref: specs/005-inventory-management/spec.md §35
"""

from __future__ import annotations

import csv
import io
import logging
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from modules.inventory.models.product_enrichment import ImportJob
from modules.inventory.models.uom import UOM
from modules.inventory.repositories.product_enrichment_repository import (
    ImportJobRepository,
)
from modules.inventory.repositories.product_repository import ProductRepository
from modules.inventory.services.product_service import _VALID_TYPES, ProductService

logger = logging.getLogger(__name__)

# CSV columns expected in header row
_REQUIRED_COLS = {"product_code", "name", "base_uom_code"}
_ALL_COLS = {
    "product_code",
    "name",
    "product_type",
    "base_uom_code",
    "description",
    "cost_price",
    "category_code",
    "brand_code",
    "hs_code",
    "country_of_origin",
    "lead_time_days",
    "min_order_qty",
    "max_order_qty",
    "is_serialized",
    "is_batch_tracked",
}


def _parse_bool(val: str) -> bool:
    return val.strip().lower() in ("1", "true", "yes")


def _parse_float_or_none(val: str) -> float | None:
    v = val.strip()
    if not v:
        return None
    try:
        return float(v)
    except ValueError:
        return None


def _parse_int_or_none(val: str) -> int | None:
    v = val.strip()
    if not v:
        return None
    try:
        return int(v)
    except ValueError:
        return None


class BulkImportService:
    """Processes CSV product imports synchronously."""

    def __init__(
        self,
        db: Session,
        product_repo: ProductRepository,
        job_repo: ImportJobRepository,
        product_service: ProductService,
    ) -> None:
        self.db = db
        self._product_repo = product_repo
        self._job_repo = job_repo
        self._product_service = product_service

    def _lookup_uom_id(self, company_id: UUID, code: str) -> UUID | None:
        """Find UOM by code for the company."""
        from sqlalchemy import func

        uom = (
            self.db.execute(
                select(UOM)
                .where(UOM.company_id == company_id)
                .where(func.upper(UOM.code) == code.strip().upper())
                .where(UOM.is_deleted == False)  # noqa: E712
            )
            .scalars()
            .one_or_none()
        )
        return uom.id if uom else None

    def import_csv(
        self,
        company_id: UUID,
        file_name: str,
        content: bytes,
        actor_id: UUID | None = None,
    ) -> ImportJob:
        """Parse the CSV bytes, process each row, and return the completed ImportJob."""
        job = self._job_repo.create(
            company_id=company_id,
            file_name=file_name,
            created_by=actor_id,
        )
        self._job_repo.update_status(job, "PROCESSING")
        self.db.commit()

        try:
            text = content.decode("utf-8-sig").strip()
            reader = csv.DictReader(io.StringIO(text))
            rows = list(reader)
        except Exception as e:
            self._job_repo.update_status(
                job, "FAILED", error_message=f"Could not parse CSV: {e}"
            )
            self.db.commit()
            return job

        # Validate header
        if not rows:
            self._job_repo.update_status(
                job, "COMPLETED", processed_rows=0, failed_rows=0
            )
            self.db.commit()
            return job

        headers = set(reader.fieldnames or [])
        missing = _REQUIRED_COLS - headers
        if missing:
            self._job_repo.update_status(
                job,
                "FAILED",
                error_message=f"Missing required CSV columns: {sorted(missing)}",
            )
            self.db.commit()
            return job

        job.total_rows = len(rows)
        self.db.flush()

        processed = 0
        failed = 0
        error_rows: list[dict] = []

        for row_num, row in enumerate(rows, start=2):  # 2 = data starts at line 2
            code = row.get("product_code", "").strip().upper()
            name = row.get("name", "").strip()
            uom_code = row.get("base_uom_code", "").strip()
            product_type = (
                row.get("product_type", "STANDARD").strip().upper() or "STANDARD"
            )

            row_errors: list[str] = []

            if not code:
                row_errors.append("product_code is required")
            if not name:
                row_errors.append("name is required")
            if not uom_code:
                row_errors.append("base_uom_code is required")
            if product_type not in _VALID_TYPES:
                row_errors.append(f"product_type must be one of {sorted(_VALID_TYPES)}")

            if row_errors:
                failed += 1
                error_rows.append(
                    {"row_number": row_num, "product_code": code, "errors": row_errors}
                )
                continue

            # Check for duplicate SKU
            if self._product_repo.get_by_code(company_id=company_id, product_code=code):
                failed += 1
                error_rows.append(
                    {
                        "row_number": row_num,
                        "product_code": code,
                        "errors": [f"Product with code '{code}' already exists"],
                    }
                )
                continue

            # Resolve UOM
            uom_id = self._lookup_uom_id(company_id, uom_code)
            if not uom_id:
                failed += 1
                error_rows.append(
                    {
                        "row_number": row_num,
                        "product_code": code,
                        "errors": [f"UOM with code '{uom_code}' not found"],
                    }
                )
                continue

            # Build create kwargs
            create_kwargs: dict = {
                "company_id": company_id,
                "product_code": code,
                "name": name,
                "product_type": product_type,
                "base_uom_id": uom_id,
                "created_by": actor_id,
            }

            if row.get("description"):
                create_kwargs["description"] = row["description"].strip()
            if row.get("hs_code"):
                create_kwargs["hs_code"] = row["hs_code"].strip()
            if row.get("country_of_origin"):
                create_kwargs["country_of_origin"] = row["country_of_origin"].strip()
            if row.get("lead_time_days"):
                create_kwargs["lead_time_days"] = _parse_int_or_none(
                    row["lead_time_days"]
                )
            if row.get("cost_price"):
                create_kwargs["cost_price"] = _parse_float_or_none(row["cost_price"])
            if row.get("min_order_qty"):
                create_kwargs["min_order_qty"] = _parse_float_or_none(
                    row["min_order_qty"]
                )
            if row.get("max_order_qty"):
                create_kwargs["max_order_qty"] = _parse_float_or_none(
                    row["max_order_qty"]
                )
            if row.get("is_serialized"):
                create_kwargs["is_serialized"] = _parse_bool(row["is_serialized"])
            if row.get("is_batch_tracked"):
                create_kwargs["is_batch_tracked"] = _parse_bool(row["is_batch_tracked"])

            try:
                self._product_service.create_product(**create_kwargs)
                processed += 1
            except Exception as exc:
                failed += 1
                error_rows.append(
                    {
                        "row_number": row_num,
                        "product_code": code,
                        "errors": [str(exc)],
                    }
                )

        final_status = "COMPLETED" if failed == 0 else "FAILED_WITH_ERRORS"
        self._job_repo.update_status(
            job,
            status=final_status,
            processed_rows=processed,
            failed_rows=failed,
            error_rows=error_rows if error_rows else None,
        )
        self.db.commit()
        logger.info(
            "Import job %s complete: %d processed, %d failed", job.id, processed, failed
        )
        return job

    def export_csv(self, company_id: UUID) -> bytes:
        """Export all active products for the company as CSV bytes."""

        from modules.inventory.models.product import Product

        products = list(
            self.db.execute(
                select(Product)
                .where(Product.company_id == company_id)
                .where(Product.is_deleted == False)  # noqa: E712
                .order_by(Product.product_code)
            )
            .scalars()
            .all()
        )

        output = io.StringIO()
        fieldnames = [
            "product_code",
            "name",
            "product_type",
            "status",
            "description",
            "short_description",
            "base_uom_id",
            "category_id",
            "brand_id",
            "hs_code",
            "country_of_origin",
            "lead_time_days",
            "min_order_qty",
            "max_order_qty",
            "reorder_point",
            "weight_kg",
            "width_cm",
            "height_cm",
            "depth_cm",
            "is_serialized",
            "is_batch_tracked",
            "cost_price",
        ]
        writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for p in products:
            writer.writerow(
                {
                    "product_code": p.product_code,
                    "name": p.name,
                    "product_type": p.product_type,
                    "status": p.status,
                    "description": p.description or "",
                    "short_description": p.short_description or "",
                    "base_uom_id": p.base_uom_id,
                    "category_id": p.category_id or "",
                    "brand_id": p.brand_id or "",
                    "hs_code": p.hs_code or "",
                    "country_of_origin": p.country_of_origin or "",
                    "lead_time_days": p.lead_time_days or "",
                    "min_order_qty": p.min_order_qty or "",
                    "max_order_qty": p.max_order_qty or "",
                    "reorder_point": p.reorder_point or "",
                    "weight_kg": p.weight_kg or "",
                    "width_cm": p.width_cm or "",
                    "height_cm": p.height_cm or "",
                    "depth_cm": p.depth_cm or "",
                    "is_serialized": p.is_serialized,
                    "is_batch_tracked": p.is_batch_tracked,
                    "cost_price": p.cost_price or "",
                }
            )
        return output.getvalue().encode("utf-8")
