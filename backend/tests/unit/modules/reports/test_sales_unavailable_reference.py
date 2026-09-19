"""T068 — Defensive product/customer display-name resolution for loose-UUID
references (FR-RPT-053): an unresolvable ``customer_id`` renders
``"[unavailable reference]"``, never raises."""

from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy.orm import Session

from modules.reports.schemas.sales import SalesByCustomerFilter, SalesByCustomerRow
from modules.reports.services.adapters.base import PaginatedReportResult
from modules.reports.services.adapters.sales_adapter import SalesAdapter
from modules.sales.models.invoice import SalesInvoice


def test_dangling_customer_id_renders_unavailable_reference(
    db_session: Session,
) -> None:
    company_id = uuid.uuid4()
    dangling_customer_id = str(uuid.uuid4())  # no matching Customer row exists
    db_session.add(
        SalesInvoice(
            company_id=company_id,
            invoice_number=f"INV-{uuid.uuid4().hex[:8]}",
            customer_id=dangling_customer_id,
            invoice_date="2026-01-15",
            due_date="2026-02-14",
            currency_code="USD",
            status="ISSUED",
            subtotal=Decimal("50.00"),
            discount_amount=Decimal("0"),
            tax_amount=Decimal("0"),
            charges_amount=Decimal("0"),
            total_amount=Decimal("50.00"),
            version=1,
        )
    )
    db_session.commit()

    adapter = SalesAdapter()
    result = adapter.run(
        db_session,
        company_id,
        "sales.by_customer",
        SalesByCustomerFilter(),
        page=1,
        page_size=20,
        sort=None,
        comparison=None,
    )
    assert isinstance(result, PaginatedReportResult)
    row = result.items[0]
    assert isinstance(row, SalesByCustomerRow)
    assert row.customer_name == "[unavailable reference]"


def test_null_customer_id_also_renders_unavailable_reference() -> None:
    from unittest.mock import MagicMock

    from modules.reports.services.adapters.sales_adapter import _resolve_customer_name

    assert _resolve_customer_name(MagicMock(), uuid.uuid4(), None) == (
        "[unavailable reference]"
    )
    assert _resolve_customer_name(MagicMock(), uuid.uuid4(), "not-a-uuid") == (
        "[unavailable reference]"
    )
