"""T072 — Export-seam test: ``count_export_rows()``/``iter_export_rows()``
for Sales' list-shaped reports — cheap-count pattern, pages until
exhausted."""

from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy.orm import Session

from modules.reports.schemas.sales import SalesByCustomerFilter
from modules.reports.services.adapters.sales_adapter import SalesAdapter
from modules.sales.models.invoice import SalesInvoice


def test_sales_by_customer_export_seam(db_session: Session) -> None:
    company_id = uuid.uuid4()
    for i in range(5):
        db_session.add(
            SalesInvoice(
                company_id=company_id,
                invoice_number=f"INV-{uuid.uuid4().hex[:8]}",
                customer_id=str(uuid.uuid4()),
                invoice_date="2026-01-15",
                due_date="2026-02-14",
                currency_code="USD",
                status="ISSUED",
                subtotal=Decimal(f"{100 + i}.00"),
                discount_amount=Decimal("0"),
                tax_amount=Decimal("0"),
                charges_amount=Decimal("0"),
                total_amount=Decimal(f"{100 + i}.00"),
                version=1,
            )
        )
    db_session.commit()

    adapter = SalesAdapter()
    filters = SalesByCustomerFilter()

    count = adapter.count_export_rows(
        db_session, company_id, "sales.by_customer", filters
    )
    assert count == 5

    batches = list(
        adapter.iter_export_rows(
            db_session, company_id, "sales.by_customer", filters, None, batch_size=2
        )
    )
    total_rows = sum(len(b) for b in batches)
    assert total_rows == 5
    assert all(len(b) <= 2 for b in batches)
