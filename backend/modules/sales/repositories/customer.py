"""Repositories for the Customer aggregate — Phase 1.

Covers:
  - CustomerRepository        — Customer CRUD + FTS search + filters
  - CustomerContactRepository — CustomerContact CRUD
  - CustomerAddressRepository — CustomerAddress CRUD
  - CustomerBankDetailRepository — CustomerBankDetail CRUD
  - CustomerNoteRepository    — CustomerNote append-only

All repositories enforce company_id isolation via BaseSalesRepository.

FTS search: uses PostgreSQL tsvector when available; falls back to ILIKE
for SQLite (tests).

Spec ref: specs/007-sales-management/data-model.md §Customer Aggregate
Task: T039, T040
"""

from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy import ColumnElement, func, or_, select
from sqlalchemy.orm import Session

from modules.sales.models.customer import (
    Customer,
    CustomerAddress,
    CustomerBankDetail,
    CustomerContact,
    CustomerNote,
)
from modules.sales.repositories import BaseSalesRepository

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helper — dialect detection
# ---------------------------------------------------------------------------


def _dialect_name(db: Session) -> str:
    """Return the DB dialect name for the current session."""
    try:
        bind = db.get_bind()
        return bind.dialect.name
    except Exception:
        return "sqlite"


# ---------------------------------------------------------------------------
# Customer Repository
# ---------------------------------------------------------------------------


class CustomerRepository(BaseSalesRepository[Customer]):
    """Data-access layer for the ``customers`` table.

    Key queries:
      - ``get_by_code``  — lookup by (company_id, customer_code)
      - ``search``       — FTS + status/type/category filters + pagination
      - ``get_active``   — all ACTIVE customers for a company
    """

    def __init__(self, db: Session) -> None:
        super().__init__(db=db, model=Customer)

    def get_by_code(self, company_id: UUID, customer_code: str) -> Customer | None:
        """Return the customer with the given code for this company, or None."""
        stmt = (
            select(Customer)
            .where(Customer.company_id == company_id)
            .where(Customer.customer_code == customer_code.upper())
            .where(Customer.is_deleted == False)  # noqa: E712
        )
        return self.db.execute(stmt).scalars().one_or_none()

    def get_active(self, company_id: UUID) -> list[Customer]:
        """Return all ACTIVE customers for a company."""
        stmt = (
            select(Customer)
            .where(Customer.company_id == company_id)
            .where(Customer.status == "ACTIVE")
            .where(Customer.is_deleted == False)  # noqa: E712
            .order_by(Customer.legal_name)
        )
        return list(self.db.execute(stmt).scalars().all())

    def search(
        self,
        company_id: UUID,
        query: str | None = None,
        status: str | None = None,
        customer_type: str | None = None,
        category_id: UUID | None = None,
        group_id: UUID | None = None,
        skip: int = 0,
        limit: int = 20,
    ) -> tuple[list[Customer], int]:
        """Search customers with FTS / ILIKE, filters, and pagination.

        Returns (items, total_count).
        """
        base_filter = [
            Customer.company_id == company_id,
            Customer.is_deleted == False,  # noqa: E712
        ]

        # Text search — FTS on PostgreSQL, ILIKE on SQLite
        text_filter: ColumnElement[bool] | None = None
        if query:
            q = query.strip()
            if _dialect_name(self.db) == "postgresql":
                text_filter = Customer.tsvector_search.op("@@")(
                    func.plainto_tsquery("english", q)
                )
            else:
                like = f"%{q}%"
                text_filter = or_(
                    Customer.legal_name.ilike(like),
                    Customer.customer_code.ilike(like),
                    Customer.trading_name.ilike(like),
                )

        filters = list(base_filter)
        if text_filter is not None:
            filters.append(text_filter)
        if status:
            filters.append(Customer.status == status.upper())
        if customer_type:
            filters.append(Customer.customer_type == customer_type.upper())
        if category_id:
            filters.append(Customer.category_id == str(category_id))
        if group_id:
            filters.append(Customer.group_id == str(group_id))

        count_stmt = select(func.count()).select_from(Customer).where(*filters)
        total = self.db.execute(count_stmt).scalar_one()

        items_stmt = (
            select(Customer)
            .where(*filters)
            .order_by(Customer.legal_name)
            .offset(skip)
            .limit(limit)
        )
        items = list(self.db.execute(items_stmt).scalars().all())

        return items, total

    def count_by_status(self, company_id: UUID, status: str) -> int:
        """Return the number of customers in the given status for a company."""
        stmt = (
            select(func.count())
            .select_from(Customer)
            .where(Customer.company_id == company_id)
            .where(Customer.status == status)
            .where(Customer.is_deleted == False)  # noqa: E712
        )
        return self.db.execute(stmt).scalar_one()

    def update_tsvector(
        self,
        db: Session,
        customer: Customer,
    ) -> None:
        """Update the tsvector_search column on PostgreSQL.

        On SQLite (tests) this is a no-op.
        """
        if _dialect_name(db) != "postgresql":
            return

        # Build the tsvector from key text columns
        from sqlalchemy import text

        db.execute(
            text(
                "UPDATE customers SET tsvector_search = "
                "to_tsvector('english', "
                "  coalesce(legal_name, '') || ' ' || "
                "  coalesce(trading_name, '') || ' ' || "
                "  coalesce(customer_code, '') "
                ") WHERE id = :cid"
            ),
            {"cid": str(customer.id)},
        )


# ---------------------------------------------------------------------------
# CustomerContact Repository
# ---------------------------------------------------------------------------


class CustomerContactRepository(BaseSalesRepository[CustomerContact]):
    """Data-access layer for the ``customer_contacts`` table."""

    def __init__(self, db: Session) -> None:
        super().__init__(db=db, model=CustomerContact)

    def get_for_customer(
        self, company_id: UUID, customer_id: UUID
    ) -> list[CustomerContact]:
        """Return all active contacts for a customer."""
        stmt = (
            select(CustomerContact)
            .where(CustomerContact.company_id == company_id)
            .where(CustomerContact.customer_id == str(customer_id))
            .where(CustomerContact.is_deleted == False)  # noqa: E712
            .order_by(CustomerContact.is_primary.desc(), CustomerContact.contact_name)
        )
        return list(self.db.execute(stmt).scalars().all())

    def get_primary(
        self, company_id: UUID, customer_id: UUID
    ) -> CustomerContact | None:
        """Return the primary contact for a customer, or None."""
        stmt = (
            select(CustomerContact)
            .where(CustomerContact.company_id == company_id)
            .where(CustomerContact.customer_id == str(customer_id))
            .where(CustomerContact.is_primary == True)  # noqa: E712
            .where(CustomerContact.is_deleted == False)  # noqa: E712
        )
        return self.db.execute(stmt).scalars().one_or_none()

    def clear_primary(self, company_id: UUID, customer_id: UUID) -> None:
        """Set is_primary=False for all contacts of a customer."""
        contacts = self.get_for_customer(company_id=company_id, customer_id=customer_id)
        for c in contacts:
            if c.is_primary:
                c.is_primary = False
        self.db.flush()

    def count_for_customer(self, company_id: UUID, customer_id: UUID) -> int:
        """Return the number of active contacts for a customer."""
        stmt = (
            select(func.count())
            .select_from(CustomerContact)
            .where(CustomerContact.company_id == company_id)
            .where(CustomerContact.customer_id == str(customer_id))
            .where(CustomerContact.is_deleted == False)  # noqa: E712
        )
        return self.db.execute(stmt).scalar_one()


# ---------------------------------------------------------------------------
# CustomerAddress Repository
# ---------------------------------------------------------------------------


class CustomerAddressRepository(BaseSalesRepository[CustomerAddress]):
    """Data-access layer for the ``customer_addresses`` table."""

    def __init__(self, db: Session) -> None:
        super().__init__(db=db, model=CustomerAddress)

    def get_for_customer(
        self, company_id: UUID, customer_id: UUID
    ) -> list[CustomerAddress]:
        """Return all active addresses for a customer."""
        stmt = (
            select(CustomerAddress)
            .where(CustomerAddress.company_id == company_id)
            .where(CustomerAddress.customer_id == str(customer_id))
            .where(CustomerAddress.is_deleted == False)  # noqa: E712
            .order_by(
                CustomerAddress.address_type,
                CustomerAddress.is_default_billing.desc(),
            )
        )
        return list(self.db.execute(stmt).scalars().all())

    def get_default_billing(
        self, company_id: UUID, customer_id: UUID
    ) -> CustomerAddress | None:
        """Return the default billing address for a customer, or None."""
        stmt = (
            select(CustomerAddress)
            .where(CustomerAddress.company_id == company_id)
            .where(CustomerAddress.customer_id == str(customer_id))
            .where(CustomerAddress.is_default_billing == True)  # noqa: E712
            .where(CustomerAddress.is_deleted == False)  # noqa: E712
        )
        return self.db.execute(stmt).scalars().one_or_none()

    def get_default_shipping(
        self, company_id: UUID, customer_id: UUID
    ) -> CustomerAddress | None:
        """Return the default shipping address for a customer, or None."""
        stmt = (
            select(CustomerAddress)
            .where(CustomerAddress.company_id == company_id)
            .where(CustomerAddress.customer_id == str(customer_id))
            .where(CustomerAddress.is_default_shipping == True)  # noqa: E712
            .where(CustomerAddress.is_deleted == False)  # noqa: E712
        )
        return self.db.execute(stmt).scalars().one_or_none()

    def clear_default_billing(self, company_id: UUID, customer_id: UUID) -> None:
        """Clear is_default_billing from all addresses for a customer."""
        addresses = self.get_for_customer(
            company_id=company_id, customer_id=customer_id
        )
        for a in addresses:
            if a.is_default_billing:
                a.is_default_billing = False
        self.db.flush()

    def clear_default_shipping(self, company_id: UUID, customer_id: UUID) -> None:
        """Clear is_default_shipping from all addresses for a customer."""
        addresses = self.get_for_customer(
            company_id=company_id, customer_id=customer_id
        )
        for a in addresses:
            if a.is_default_shipping:
                a.is_default_shipping = False
        self.db.flush()

    def count_billing_addresses(self, company_id: UUID, customer_id: UUID) -> int:
        """Return the number of active billing (or BOTH) addresses for a customer."""
        stmt = (
            select(func.count())
            .select_from(CustomerAddress)
            .where(CustomerAddress.company_id == company_id)
            .where(CustomerAddress.customer_id == str(customer_id))
            .where(CustomerAddress.address_type.in_(["BILLING", "BOTH"]))
            .where(CustomerAddress.is_deleted == False)  # noqa: E712
        )
        return self.db.execute(stmt).scalar_one()


# ---------------------------------------------------------------------------
# CustomerBankDetail Repository
# ---------------------------------------------------------------------------


class CustomerBankDetailRepository(BaseSalesRepository[CustomerBankDetail]):
    """Data-access layer for the ``customer_bank_details`` table."""

    def __init__(self, db: Session) -> None:
        super().__init__(db=db, model=CustomerBankDetail)

    def get_for_customer(
        self, company_id: UUID, customer_id: UUID
    ) -> list[CustomerBankDetail]:
        """Return all active bank details for a customer."""
        stmt = (
            select(CustomerBankDetail)
            .where(CustomerBankDetail.company_id == company_id)
            .where(CustomerBankDetail.customer_id == str(customer_id))
            .where(CustomerBankDetail.is_deleted == False)  # noqa: E712
            .order_by(
                CustomerBankDetail.is_default.desc(),
                CustomerBankDetail.bank_name,
            )
        )
        return list(self.db.execute(stmt).scalars().all())

    def clear_default(self, company_id: UUID, customer_id: UUID) -> None:
        """Clear is_default from all bank details for a customer."""
        banks = self.get_for_customer(company_id=company_id, customer_id=customer_id)
        for b in banks:
            if b.is_default:
                b.is_default = False
        self.db.flush()


# ---------------------------------------------------------------------------
# CustomerNote Repository
# ---------------------------------------------------------------------------


class CustomerNoteRepository(BaseSalesRepository[CustomerNote]):
    """Data-access layer for the ``customer_notes`` table (append-only)."""

    def __init__(self, db: Session) -> None:
        super().__init__(db=db, model=CustomerNote)

    def get_for_customer(
        self, company_id: UUID, customer_id: UUID, skip: int = 0, limit: int = 50
    ) -> list[CustomerNote]:
        """Return notes for a customer, newest first."""
        stmt = (
            select(CustomerNote)
            .where(CustomerNote.company_id == company_id)
            .where(CustomerNote.customer_id == str(customer_id))
            .where(CustomerNote.is_deleted == False)  # noqa: E712
            .order_by(CustomerNote.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(self.db.execute(stmt).scalars().all())
