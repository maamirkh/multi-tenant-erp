"""Customer export service — Phase 1.

Supports CSV export of customers with:
  - Company-scoped tenant isolation
  - Optional status filter
  - Streaming-safe output (all data in memory for now; streaming in future)

Spec ref: specs/007-sales-management/spec.md §38 Import & Export
Task: T044
"""

from __future__ import annotations

import csv
import io
import logging
from uuid import UUID

from sqlalchemy.orm import Session

from modules.sales.repositories.customer import CustomerRepository

logger = logging.getLogger(__name__)

_EXPORT_COLUMNS = [
    "customer_code",
    "legal_name",
    "trading_name",
    "customer_type",
    "status",
    "credit_status",
    "credit_limit",
    "currency_code",
    "rating",
    "tax_registration_number",
    "tax_exempt",
    "website",
    "industry",
    "annual_revenue_range",
    "created_at",
]


class CustomerExportService:
    """Export customers for a company to CSV format."""

    def __init__(self, db: Session, customer_repo: CustomerRepository) -> None:
        self.db = db
        self._repo = customer_repo

    def export_csv(
        self,
        company_id: UUID,
        status: str | None = None,
    ) -> bytes:
        """Export all customers (optionally filtered by status) to CSV bytes.

        Returns UTF-8 encoded CSV with BOM for Excel compatibility.
        """
        items, total = self._repo.search(
            company_id=company_id,
            status=status,
            skip=0,
            limit=100_000,
        )

        output = io.StringIO()
        writer = csv.DictWriter(
            output,
            fieldnames=_EXPORT_COLUMNS,
            extrasaction="ignore",
            lineterminator="\r\n",
        )
        writer.writeheader()

        for customer in items:
            writer.writerow(
                {
                    "customer_code": customer.customer_code,
                    "legal_name": customer.legal_name,
                    "trading_name": customer.trading_name or "",
                    "customer_type": customer.customer_type,
                    "status": customer.status,
                    "credit_status": customer.credit_status,
                    "credit_limit": str(customer.credit_limit),
                    "currency_code": customer.currency_code,
                    "rating": customer.rating or "",
                    "tax_registration_number": customer.tax_registration_number or "",
                    "tax_exempt": "true" if customer.tax_exempt else "false",
                    "website": customer.website or "",
                    "industry": customer.industry or "",
                    "annual_revenue_range": customer.annual_revenue_range or "",
                    "created_at": (
                        customer.created_at.isoformat() if customer.created_at else ""
                    ),
                }
            )

        logger.info(
            "customer.export company=%s rows=%d status=%s",
            company_id,
            total,
            status,
        )
        # Return UTF-8 with BOM for Excel
        return ("\ufeff" + output.getvalue()).encode("utf-8")
