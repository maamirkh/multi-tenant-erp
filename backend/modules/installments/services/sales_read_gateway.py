"""Read-only cross-module accessors into Sales.

Thin wrappers importing ``modules.sales.repositories.{invoice,customer}``
directly — read-only cross-module repository import, mirroring
``Customer360Service``'s exact precedent for ``CustomerRepository``
(plan.md §13). Never writes anything, anywhere.

Spec ref: specs/010-installments/plan.md §13 (Sales Integration).
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from modules.sales.models.customer import Customer
from modules.sales.models.invoice import SalesInvoice
from modules.sales.repositories.customer import CustomerRepository
from modules.sales.repositories.invoice import SalesInvoiceRepository


class SalesInvoiceReadGateway:
    """Read-only accessor for ``SalesInvoice`` rows."""

    def __init__(self, db: Session) -> None:
        self._repo = SalesInvoiceRepository(db)

    def get_invoice(
        self, company_id: UUID, sales_invoice_id: UUID
    ) -> SalesInvoice | None:
        return self._repo.get_by_id_or_none(sales_invoice_id, company_id)


class SalesCustomerReadGateway:
    """Read-only accessor for ``Customer`` rows."""

    def __init__(self, db: Session) -> None:
        self._repo = CustomerRepository(db)

    def get_customer(self, company_id: UUID, customer_id: UUID) -> Customer | None:
        return self._repo.get_by_id_or_none(customer_id, company_id)
