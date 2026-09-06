"""Sales Invoice repositories — Phase 6.

Repositories:
  SalesInvoiceRepository — CRUD + customer/status/date filters
  InvoiceLineRepository  — CRUD + invoice filter
  InvoiceChargeRepository — CRUD + invoice filter

All queries enforce company_id isolation (tenant safety).

Spec ref: specs/007-sales-management/plan.md §Repository Layer
Task: T170
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from modules.sales.models.invoice import InvoiceCharge, InvoiceLine, SalesInvoice


class SalesInvoiceRepository:
    """Repository for SalesInvoice aggregate root."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def get_by_id_or_none(
        self,
        invoice_id: UUID,
        company_id: UUID,
    ) -> SalesInvoice | None:
        return (
            self._db.query(SalesInvoice)
            .filter(
                SalesInvoice.id == invoice_id,
                SalesInvoice.company_id == company_id,
                SalesInvoice.is_deleted.is_(False),
            )
            .first()
        )

    def get_by_number(
        self,
        company_id: UUID,
        invoice_number: str,
    ) -> SalesInvoice | None:
        return (
            self._db.query(SalesInvoice)
            .filter(
                SalesInvoice.company_id == company_id,
                SalesInvoice.invoice_number == invoice_number,
                SalesInvoice.is_deleted.is_(False),
            )
            .first()
        )

    def list_for_company(
        self,
        company_id: UUID,
        *,
        customer_id: str | None = None,
        status: str | None = None,
        order_id: str | None = None,
        delivery_note_id: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[SalesInvoice], int]:
        q = self._db.query(SalesInvoice).filter(
            SalesInvoice.company_id == company_id,
            SalesInvoice.is_deleted.is_(False),
        )
        if customer_id:
            q = q.filter(SalesInvoice.customer_id == customer_id)
        if status:
            q = q.filter(SalesInvoice.status == status)
        if order_id:
            q = q.filter(SalesInvoice.order_id == order_id)
        if delivery_note_id:
            q = q.filter(SalesInvoice.delivery_note_id == delivery_note_id)
        if date_from:
            q = q.filter(SalesInvoice.invoice_date >= date_from)
        if date_to:
            q = q.filter(SalesInvoice.invoice_date <= date_to)

        total = q.count()
        items = (
            q.order_by(SalesInvoice.invoice_number.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )
        return items, total


class InvoiceLineRepository:
    """Repository for InvoiceLine owned entities."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def list_for_invoice(
        self,
        company_id: UUID,
        invoice_id: UUID,
    ) -> list[InvoiceLine]:
        return (
            self._db.query(InvoiceLine)
            .filter(
                InvoiceLine.company_id == company_id,
                InvoiceLine.invoice_id == str(invoice_id),
                InvoiceLine.is_deleted.is_(False),
            )
            .order_by(InvoiceLine.line_number)
            .all()
        )

    def get_by_id_or_none(
        self,
        line_id: UUID,
        company_id: UUID,
    ) -> InvoiceLine | None:
        return (
            self._db.query(InvoiceLine)
            .filter(
                InvoiceLine.id == line_id,
                InvoiceLine.company_id == company_id,
                InvoiceLine.is_deleted.is_(False),
            )
            .first()
        )


class InvoiceChargeRepository:
    """Repository for InvoiceCharge owned entities."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def list_for_invoice(
        self,
        company_id: UUID,
        invoice_id: UUID,
    ) -> list[InvoiceCharge]:
        return (
            self._db.query(InvoiceCharge)
            .filter(
                InvoiceCharge.company_id == company_id,
                InvoiceCharge.invoice_id == str(invoice_id),
                InvoiceCharge.is_deleted.is_(False),
            )
            .all()
        )
