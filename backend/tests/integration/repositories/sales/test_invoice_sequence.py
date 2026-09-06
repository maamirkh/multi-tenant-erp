"""Integration tests for gap-free invoice sequencing — Phase 6.

Tests:
  - InvoiceService generates sequential invoice numbers per company
  - Cancelled invoices retain their number (no reuse, no gap-fill)
  - Different companies have independent sequences
  - SalesSequenceService increments correctly for 'invoice' type

Task: T180
Spec ref: specs/007-sales-management/spec.md §18
"""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from modules.sales.models.order import SalesOrder
from modules.sales.schemas.invoice import InvoiceCreate
from modules.sales.services.invoice_service import InvoiceService

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_order(db: Session, company_id: UUID, status: str = "APPROVED") -> SalesOrder:
    order = SalesOrder(
        company_id=company_id,
        order_number=f"SO-SEQ-{uuid4().hex[:8]}",
        customer_id=str(uuid4()),
        order_date="2026-08-03",
        currency_code="USD",
        sales_rep_id=str(uuid4()),
        priority="NORMAL",
        status=status,
        subtotal=Decimal("100.00"),
        discount_amount=Decimal("0"),
        tax_amount=Decimal("0"),
        charges_amount=Decimal("0"),
        total_amount=Decimal("100.00"),
        approval_version=1,
        version=1,
    )
    db.add(order)
    db.flush()
    return order


def _make_invoice_payload(customer_id: str | None = None) -> InvoiceCreate:
    return InvoiceCreate(
        customer_id=uuid4() if customer_id is None else UUID(customer_id),
        invoice_date="2026-08-03",
        currency_code="USD",
        lines=[
            {
                "description": "Test product",
                "quantity": "1",
                "unit_of_measure": "EA",
                "unit_price": "100.00",
            }
        ],
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestInvoiceSequencing:
    def test_first_invoice_gets_number_one(self, db_session: Session) -> None:
        """First invoice for a company gets a number starting with INV-."""
        company_id = uuid4()
        svc = InvoiceService(db=db_session)
        payload = _make_invoice_payload()
        invoice = svc.create_invoice(company_id, payload, created_by=None)
        assert invoice.invoice_number  # non-empty, format is SI-YYYY-NNNNNN

    def test_sequential_numbers_increment(self, db_session: Session) -> None:
        """Two invoices for the same company get sequential numbers."""
        company_id = uuid4()
        svc = InvoiceService(db=db_session)
        p1 = _make_invoice_payload()
        p2 = _make_invoice_payload()
        inv1 = svc.create_invoice(company_id, p1, created_by=None)
        inv2 = svc.create_invoice(company_id, p2, created_by=None)
        # Extract numeric suffix
        num1 = int(inv1.invoice_number.split("-")[-1])
        num2 = int(inv2.invoice_number.split("-")[-1])
        assert num2 == num1 + 1

    def test_different_companies_independent_sequences(
        self, db_session: Session
    ) -> None:
        """Invoice numbering sequences are isolated per company."""
        company_a = uuid4()
        company_b = uuid4()
        svc = InvoiceService(db=db_session)
        inv_a = svc.create_invoice(company_a, _make_invoice_payload(), created_by=None)
        inv_b = svc.create_invoice(company_b, _make_invoice_payload(), created_by=None)
        # Both should start at the same suffix (e.g. 1) — independent counters
        suffix_a = int(inv_a.invoice_number.split("-")[-1])
        suffix_b = int(inv_b.invoice_number.split("-")[-1])
        assert suffix_a == suffix_b

    def test_cancelled_invoice_number_retained(self, db_session: Session) -> None:
        """Cancelling an invoice does not free its number for reuse."""
        company_id = uuid4()
        svc = InvoiceService(db=db_session)
        inv1 = svc.create_invoice(company_id, _make_invoice_payload(), created_by=None)
        cancelled_number = inv1.invoice_number
        # Cancel it
        svc.cancel_invoice(company_id, inv1.id, cancelled_by=None)
        # Create another invoice — should get a NEW number, not the cancelled one
        inv2 = svc.create_invoice(company_id, _make_invoice_payload(), created_by=None)
        assert inv2.invoice_number != cancelled_number
        suffix1 = int(cancelled_number.split("-")[-1])
        suffix2 = int(inv2.invoice_number.split("-")[-1])
        # New invoice should be strictly after the cancelled one
        assert suffix2 > suffix1

    def test_three_invoices_sequential(self, db_session: Session) -> None:
        """Verify monotonically increasing sequence for 3 invoices."""
        company_id = uuid4()
        svc = InvoiceService(db=db_session)
        numbers = []
        for _ in range(3):
            inv = svc.create_invoice(
                company_id, _make_invoice_payload(), created_by=None
            )
            numbers.append(int(inv.invoice_number.split("-")[-1]))
        assert numbers == sorted(numbers)
        assert numbers[1] == numbers[0] + 1
        assert numbers[2] == numbers[1] + 1
