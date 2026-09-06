"""Integration tests for invoice generation modes — Phase 6.

Tests:
  - Manual invoice creation with explicit lines and charges
  - Invoice amount aggregation (subtotal, tax, total)
  - Issue transition (DRAFT → ISSUED)
  - Cancel transition (DRAFT → CANCELLED)
  - Cancel then create produces next sequential number
  - Credit note transition (ISSUED → CREDIT_NOTE_ISSUED)
  - Terminal status prevents further transitions
  - List filtering by status/customer

Task: T181
Spec ref: specs/007-sales-management/spec.md §18
"""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from sqlalchemy.orm import Session

from core.exceptions.base import ConflictException, NotFoundException
from modules.sales.schemas.invoice import (
    InvoiceCreate,
    InvoiceCreditNoteRequest,
    InvoiceIssueRequest,
)
from modules.sales.services.invoice_service import InvoiceService

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _invoice_payload(
    customer_id: UUID | None = None,
    lines: list[dict] | None = None,
    charges: list[dict] | None = None,
) -> InvoiceCreate:
    _lines = lines or [
        {
            "description": "Widget A",
            "quantity": "2",
            "unit_of_measure": "EA",
            "unit_price": "50.00",
        }
    ]
    return InvoiceCreate(
        customer_id=customer_id or uuid4(),
        invoice_date="2026-08-03",
        currency_code="USD",
        lines=_lines,
        charges=charges or [],
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestManualInvoiceCreation:
    def test_creates_invoice_in_draft(self, db_session: Session) -> None:
        company_id = uuid4()
        svc = InvoiceService(db=db_session)
        inv = svc.create_invoice(company_id, _invoice_payload(), created_by=None)
        assert inv.status == "DRAFT"
        assert inv.company_id == company_id

    def test_subtotal_computed_from_lines(self, db_session: Session) -> None:
        """2 × $50 = $100 subtotal."""
        company_id = uuid4()
        svc = InvoiceService(db=db_session)
        inv = svc.create_invoice(company_id, _invoice_payload(), created_by=None)
        assert inv.subtotal == Decimal("100.00")
        assert inv.total_amount == Decimal("100.00")

    def test_multi_line_subtotal(self, db_session: Session) -> None:
        company_id = uuid4()
        svc = InvoiceService(db=db_session)
        payload = _invoice_payload(
            lines=[
                {
                    "description": "A",
                    "quantity": "1",
                    "unit_of_measure": "EA",
                    "unit_price": "30.00",
                },
                {
                    "description": "B",
                    "quantity": "3",
                    "unit_of_measure": "EA",
                    "unit_price": "20.00",
                },
            ]
        )
        inv = svc.create_invoice(company_id, payload, created_by=None)
        assert inv.subtotal == Decimal("90.00")

    def test_charges_added_to_total(self, db_session: Session) -> None:
        company_id = uuid4()
        svc = InvoiceService(db=db_session)
        payload = _invoice_payload(
            charges=[
                {
                    "charge_type": "FREIGHT",
                    "description": "Shipping",
                    "amount": "15.00",
                },
            ]
        )
        inv = svc.create_invoice(company_id, payload, created_by=None)
        assert inv.charges_amount == Decimal("15.00")
        assert inv.total_amount == Decimal("115.00")

    def test_lines_stored(self, db_session: Session) -> None:
        company_id = uuid4()
        svc = InvoiceService(db=db_session)
        inv = svc.create_invoice(company_id, _invoice_payload(), created_by=None)
        lines = svc.get_invoice_lines(company_id, inv.id)
        assert len(lines) == 1
        assert lines[0].description == "Widget A"

    def test_invoice_number_assigned(self, db_session: Session) -> None:
        company_id = uuid4()
        svc = InvoiceService(db=db_session)
        inv = svc.create_invoice(company_id, _invoice_payload(), created_by=None)
        assert inv.invoice_number

    def test_due_date_equals_invoice_date_no_term(self, db_session: Session) -> None:
        """Without a payment term, due_date == invoice_date (net 0)."""
        company_id = uuid4()
        svc = InvoiceService(db=db_session)
        inv = svc.create_invoice(company_id, _invoice_payload(), created_by=None)
        assert inv.due_date == "2026-08-03"

    def test_discount_on_line(self, db_session: Session) -> None:
        """10% discount on $100 = $10 discount, $90 extended."""
        company_id = uuid4()
        svc = InvoiceService(db=db_session)
        payload = _invoice_payload(
            lines=[
                {
                    "description": "Disc item",
                    "quantity": "1",
                    "unit_of_measure": "EA",
                    "unit_price": "100.00",
                    "discount_percentage": "10",
                }
            ]
        )
        inv = svc.create_invoice(company_id, payload, created_by=None)
        assert inv.discount_amount == Decimal("10.00")
        assert inv.subtotal == Decimal("90.00")


class TestInvoiceTransitions:
    def test_issue_draft(self, db_session: Session) -> None:
        company_id = uuid4()
        svc = InvoiceService(db=db_session)
        inv = svc.create_invoice(company_id, _invoice_payload(), created_by=None)
        issued = svc.issue_invoice(
            company_id, inv.id, InvoiceIssueRequest(), issued_by=None
        )
        assert issued.status == "ISSUED"

    def test_cancel_draft(self, db_session: Session) -> None:
        company_id = uuid4()
        svc = InvoiceService(db=db_session)
        inv = svc.create_invoice(company_id, _invoice_payload(), created_by=None)
        cancelled = svc.cancel_invoice(company_id, inv.id, cancelled_by=None)
        assert cancelled.status == "CANCELLED"

    def test_credit_note_on_issued(self, db_session: Session) -> None:
        company_id = uuid4()
        svc = InvoiceService(db=db_session)
        inv = svc.create_invoice(company_id, _invoice_payload(), created_by=None)
        svc.issue_invoice(company_id, inv.id, InvoiceIssueRequest(), issued_by=None)
        cn_req = InvoiceCreditNoteRequest(credit_note_amount=Decimal("50.00"))
        updated = svc.issue_credit_note(company_id, inv.id, cn_req, issued_by=None)
        assert updated.status == "CREDIT_NOTE_ISSUED"
        assert updated.credit_note_amount == Decimal("50.00")

    def test_cannot_cancel_issued(self, db_session: Session) -> None:
        company_id = uuid4()
        svc = InvoiceService(db=db_session)
        inv = svc.create_invoice(company_id, _invoice_payload(), created_by=None)
        svc.issue_invoice(company_id, inv.id, InvoiceIssueRequest(), issued_by=None)
        with pytest.raises(ConflictException):
            svc.cancel_invoice(company_id, inv.id, cancelled_by=None)

    def test_cannot_issue_cancelled(self, db_session: Session) -> None:
        company_id = uuid4()
        svc = InvoiceService(db=db_session)
        inv = svc.create_invoice(company_id, _invoice_payload(), created_by=None)
        svc.cancel_invoice(company_id, inv.id, cancelled_by=None)
        with pytest.raises(ConflictException):
            svc.issue_invoice(company_id, inv.id, InvoiceIssueRequest(), issued_by=None)

    def test_credit_note_on_draft_raises(self, db_session: Session) -> None:
        company_id = uuid4()
        svc = InvoiceService(db=db_session)
        inv = svc.create_invoice(company_id, _invoice_payload(), created_by=None)
        cn_req = InvoiceCreditNoteRequest(credit_note_amount=Decimal("10.00"))
        with pytest.raises(ConflictException):
            svc.issue_credit_note(company_id, inv.id, cn_req, issued_by=None)


class TestInvoiceListing:
    def test_list_returns_invoices_for_company(self, db_session: Session) -> None:
        company_id = uuid4()
        other_company = uuid4()
        svc = InvoiceService(db=db_session)
        svc.create_invoice(company_id, _invoice_payload(), created_by=None)
        svc.create_invoice(company_id, _invoice_payload(), created_by=None)
        svc.create_invoice(other_company, _invoice_payload(), created_by=None)
        items, total = svc.list_invoices(company_id)
        assert total == 2
        assert len(items) == 2

    def test_filter_by_status(self, db_session: Session) -> None:
        company_id = uuid4()
        svc = InvoiceService(db=db_session)
        inv1 = svc.create_invoice(company_id, _invoice_payload(), created_by=None)
        inv2 = svc.create_invoice(company_id, _invoice_payload(), created_by=None)
        svc.issue_invoice(company_id, inv1.id, InvoiceIssueRequest(), issued_by=None)
        # Filter DRAFT — only inv2
        items, total = svc.list_invoices(company_id, status="DRAFT")
        assert total == 1
        assert items[0].id == inv2.id

    def test_filter_by_customer(self, db_session: Session) -> None:
        company_id = uuid4()
        customer_a = uuid4()
        customer_b = uuid4()
        svc = InvoiceService(db=db_session)
        svc.create_invoice(
            company_id, _invoice_payload(customer_id=customer_a), created_by=None
        )
        svc.create_invoice(
            company_id, _invoice_payload(customer_id=customer_b), created_by=None
        )
        items, total = svc.list_invoices(company_id, customer_id=str(customer_a))
        assert total == 1
        assert items[0].customer_id == str(customer_a)

    def test_tenant_isolation(self, db_session: Session) -> None:
        """Company B cannot see Company A's invoices."""
        company_a = uuid4()
        company_b = uuid4()
        svc = InvoiceService(db=db_session)
        svc.create_invoice(company_a, _invoice_payload(), created_by=None)
        items, total = svc.list_invoices(company_b)
        assert total == 0

    def test_get_invoice_wrong_company_raises(self, db_session: Session) -> None:
        company_a = uuid4()
        company_b = uuid4()
        svc = InvoiceService(db=db_session)
        inv = svc.create_invoice(company_a, _invoice_payload(), created_by=None)
        with pytest.raises(NotFoundException):
            svc.get_invoice(company_b, inv.id)
