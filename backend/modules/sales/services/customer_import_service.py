"""Customer bulk import service — Phase 1 (enhanced in Phase 9).

Supports CSV import of customers with:
  - Row-level validation
  - 500-row batch writes
  - Duplicate detection (customer_code)
  - Category/group/payment-term code resolution
  - Detailed per-row error reporting (errors list)
  - Per-row warnings for non-fatal issues (warnings list)
  - Full validation report: total_rows, imported, skipped, errors, warnings

Feature flag: sales.customer_bulk_import must be enabled.

Spec ref: specs/007-sales-management/spec.md §38 Import & Export
Task: T043, T226
"""

from __future__ import annotations

import csv
import io
import logging
from decimal import Decimal, InvalidOperation
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from modules.sales.models.customer import Customer
from modules.sales.repositories.customer import CustomerRepository
from modules.sales.repositories.master import (
    CustomerCategoryRepository,
    CustomerGroupRepository,
    SalesPaymentTermRepository,
)
from modules.sales.services.customer_service import CustomerService

logger = logging.getLogger(__name__)

BATCH_SIZE = 500

_REQUIRED_COLUMNS = {"customer_code", "legal_name", "category_code"}

_VALID_CUSTOMER_TYPES = {"INDIVIDUAL", "COMPANY", "GOVERNMENT", "INTERNAL"}


class CustomerImportService:
    """Bulk import customers from CSV data.

    Usage:
        result = service.import_csv(company_id, csv_bytes, created_by)
        # result.imported = number successfully imported
        # result.errors = list of {row, field, message}
    """

    def __init__(
        self,
        db: Session,
        customer_service: CustomerService,
        customer_repo: CustomerRepository,
        category_repo: CustomerCategoryRepository,
        group_repo: CustomerGroupRepository,
        payment_term_repo: SalesPaymentTermRepository,
    ) -> None:
        self.db = db
        self._customer_service = customer_service
        self._customer_repo = customer_repo
        self._category_repo = category_repo
        self._group_repo = group_repo
        self._payment_term_repo = payment_term_repo

    def import_csv(
        self,
        company_id: UUID,
        csv_bytes: bytes,
        created_by: UUID | None = None,
    ) -> dict[str, Any]:
        """Import customers from CSV bytes.

        Returns a dict[str, Any] with: total_rows, imported, skipped, errors.
        """
        text = csv_bytes.decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(text))

        if reader.fieldnames is None:
            return {
                "total_rows": 0,
                "imported": 0,
                "skipped": 0,
                "errors": [{"row": 0, "field": "file", "message": "Empty CSV file"}],
            }

        headers = {h.strip().lower() for h in reader.fieldnames}
        missing = _REQUIRED_COLUMNS - headers
        if missing:
            return {
                "total_rows": 0,
                "imported": 0,
                "skipped": 0,
                "errors": [
                    {
                        "row": 0,
                        "field": "header",
                        "message": f"Missing required columns: {', '.join(missing)}",
                    }
                ],
            }

        imported = 0
        skipped = 0
        errors: list[dict[str, Any]] = []
        warnings: list[dict[str, Any]] = []
        batch: list[Customer] = []
        total_rows = 0

        for row_num, row in enumerate(reader, start=2):
            total_rows += 1
            row_errors = self._validate_row(row, row_num, company_id)
            if row_errors:
                errors.extend(row_errors)
                skipped += 1
                continue

            customer_code = row.get("customer_code", "").strip().upper()

            # Duplicate check
            if self._customer_repo.get_by_code(
                company_id=company_id, customer_code=customer_code
            ):
                errors.append(
                    {
                        "row": row_num,
                        "field": "customer_code",
                        "message": f"Customer code '{customer_code}' already exists",
                    }
                )
                skipped += 1
                continue

            # Resolve category
            category_code = row.get("category_code", "").strip().upper()
            category = self._category_repo.get_by_code(
                company_id=company_id, code=category_code
            )
            if category is None:
                errors.append(
                    {
                        "row": row_num,
                        "field": "category_code",
                        "message": f"Category code '{category_code}' not found",
                    }
                )
                skipped += 1
                continue

            # Resolve optional group
            group_id = None
            group_code = row.get("group_code", "").strip().upper()
            if group_code:
                group = self._group_repo.get_by_code(
                    company_id=company_id, code=group_code
                )
                if group is None:
                    errors.append(
                        {
                            "row": row_num,
                            "field": "group_code",
                            "message": f"Group code '{group_code}' not found",
                        }
                    )
                    skipped += 1
                    continue
                group_id = group.id

            # Resolve optional payment term
            payment_term_id = None
            term_code = row.get("payment_term_code", "").strip().upper()
            if term_code:
                term = self._payment_term_repo.get_by_code(
                    company_id=company_id, code=term_code
                )
                if term is None:
                    errors.append(
                        {
                            "row": row_num,
                            "field": "payment_term_code",
                            "message": f"Payment term '{term_code}' not found",
                        }
                    )
                    skipped += 1
                    continue
                payment_term_id = term.id

            # Parse credit limit — warn if missing or zero
            credit_limit = Decimal("0")
            raw_limit = row.get("credit_limit", "").strip()
            if not raw_limit:
                warnings.append(
                    {
                        "row": row_num,
                        "field": "credit_limit",
                        "message": "credit_limit not specified; defaulting to 0",
                    }
                )
            else:
                try:
                    credit_limit = Decimal(raw_limit)
                    if credit_limit < 0:
                        warnings.append(
                            {
                                "row": row_num,
                                "field": "credit_limit",
                                "message": f"credit_limit '{raw_limit}' is negative; using 0",
                            }
                        )
                        credit_limit = Decimal("0")
                except InvalidOperation:
                    warnings.append(
                        {
                            "row": row_num,
                            "field": "credit_limit",
                            "message": f"credit_limit '{raw_limit}' is not a valid number; defaulting to 0",
                        }
                    )
                    credit_limit = Decimal("0")

            # Validate and default customer_type — warn if invalid
            customer_type = row.get("customer_type", "").strip().upper()
            if not customer_type:
                customer_type = "COMPANY"
                warnings.append(
                    {
                        "row": row_num,
                        "field": "customer_type",
                        "message": "customer_type not specified; defaulting to COMPANY",
                    }
                )
            elif customer_type not in _VALID_CUSTOMER_TYPES:
                warnings.append(
                    {
                        "row": row_num,
                        "field": "customer_type",
                        "message": (
                            f"customer_type '{customer_type}' is invalid; "
                            f"must be one of {sorted(_VALID_CUSTOMER_TYPES)}; defaulting to COMPANY"
                        ),
                    }
                )
                customer_type = "COMPANY"

            # Validate currency code — warn if not 3 uppercase letters
            currency_code = row.get("currency_code", "").strip().upper() or "USD"
            if len(currency_code) != 3:
                warnings.append(
                    {
                        "row": row_num,
                        "field": "currency_code",
                        "message": f"currency_code '{currency_code}' looks invalid; using as-is",
                    }
                )

            customer = Customer(
                company_id=company_id,
                customer_code=customer_code,
                legal_name=row.get("legal_name", "").strip(),
                trading_name=row.get("trading_name", "").strip() or None,
                customer_type=customer_type,
                category_id=str(category.id),
                group_id=str(group_id) if group_id else None,
                payment_term_id=str(payment_term_id) if payment_term_id else None,
                credit_limit=credit_limit,
                credit_status="GOOD",
                currency_code=currency_code,
                tax_registration_number=(
                    row.get("tax_registration_number", "").strip() or None
                ),
                status="DRAFT",
                version=1,
                created_by=created_by,
            )
            batch.append(customer)

            if len(batch) >= BATCH_SIZE:
                self._flush_batch(batch)
                imported += len(batch)
                batch = []

        if batch:
            self._flush_batch(batch)
            imported += len(batch)

        return {
            "total_rows": total_rows,
            "imported": imported,
            "skipped": skipped,
            "errors": errors,
            "warnings": warnings,
            "success_count": imported,
            "error_count": len(errors),
            "warning_count": len(warnings),
        }

    def _flush_batch(self, customers: list[Customer]) -> None:
        """Write a batch of customers to the database."""
        for customer in customers:
            self.db.add(customer)
        self.db.flush()
        # Missing-commit defect fixed during pre-Epic-9 hardening audit
        # (2026-08-14) — see inventory/services/warehouse_service.py::
        # create_warehouse's comment for the full root-cause explanation.
        self.db.commit()

    def _validate_row(
        self, row: dict[str, Any], row_num: int, company_id: UUID
    ) -> list[dict[str, Any]]:
        """Validate a single CSV row. Returns list of error dicts."""
        errors = []

        code = row.get("customer_code", "").strip()
        if not code:
            errors.append(
                {
                    "row": row_num,
                    "field": "customer_code",
                    "message": "customer_code is required",
                }
            )

        legal_name = row.get("legal_name", "").strip()
        if not legal_name:
            errors.append(
                {
                    "row": row_num,
                    "field": "legal_name",
                    "message": "legal_name is required",
                }
            )

        category_code = row.get("category_code", "").strip()
        if not category_code:
            errors.append(
                {
                    "row": row_num,
                    "field": "category_code",
                    "message": "category_code is required",
                }
            )

        return errors
