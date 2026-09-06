"""Repositories for the Supplier aggregate — Phase 1.

Covers:
  - SupplierRepository        — Supplier CRUD + FTS search + filters
  - SupplierContactRepository — SupplierContact CRUD
  - SupplierAddressRepository — SupplierAddress CRUD

All repositories enforce company_id isolation via BasePurchaseRepository.

FTS search: uses PostgreSQL tsvector when available; falls back to ILIKE
for SQLite (tests).

Spec ref: specs/006-purchase-management/data-model.md §Supplier Aggregate
Task: T034, T035
"""

from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from modules.purchase.models.supplier import Supplier, SupplierAddress, SupplierContact
from modules.purchase.repositories import BasePurchaseRepository

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
# Supplier Repository
# ---------------------------------------------------------------------------


class SupplierRepository(BasePurchaseRepository[Supplier]):
    """Data-access layer for the ``suppliers`` table.

    Key queries:
      - ``get_by_code``  — lookup by (company_id, supplier_code)
      - ``search``       — FTS + status/category filters + pagination
      - ``get_active``   — all ACTIVE suppliers for a company
    """

    def __init__(self, db: Session) -> None:
        super().__init__(db=db, model=Supplier)

    def get_by_code(self, company_id: UUID, supplier_code: str) -> Supplier | None:
        """Return the supplier with the given code for this company, or None."""
        stmt = (
            select(Supplier)
            .where(Supplier.company_id == company_id)
            .where(Supplier.supplier_code == supplier_code.upper())
            .where(Supplier.is_deleted == False)  # noqa: E712
        )
        return self.db.execute(stmt).scalars().one_or_none()

    def get_active(self, company_id: UUID) -> list[Supplier]:
        """Return all ACTIVE suppliers for a company."""
        stmt = (
            select(Supplier)
            .where(Supplier.company_id == company_id)
            .where(Supplier.status == "ACTIVE")
            .where(Supplier.is_deleted == False)  # noqa: E712
            .order_by(Supplier.legal_name)
        )
        return list(self.db.execute(stmt).scalars().all())

    def search(
        self,
        company_id: UUID,
        query: str | None = None,
        status: str | None = None,
        category_id: UUID | None = None,
        supplier_type: str | None = None,
        is_preferred: bool | None = None,
        skip: int = 0,
        limit: int = 20,
    ) -> tuple[list[Supplier], int]:
        """Search suppliers with FTS / ILIKE, filters, and pagination.

        Returns (items, total_count).
        """
        base_filter = [
            Supplier.company_id == company_id,
            Supplier.is_deleted == False,  # noqa: E712
        ]

        # Text search — FTS on PostgreSQL, ILIKE on SQLite
        text_filter = None
        if query:
            q = query.strip()
            if _dialect_name(self.db) == "postgresql":
                text_filter = Supplier.tsvector_search.op("@@")(
                    func.plainto_tsquery("english", q)
                )
            else:
                like = f"%{q}%"
                text_filter = or_(
                    Supplier.legal_name.ilike(like),
                    Supplier.supplier_code.ilike(like),
                    Supplier.trading_name.ilike(like),
                    Supplier.vendor_code.ilike(like),
                )

        filters = list(base_filter)
        if text_filter is not None:
            filters.append(text_filter)
        if status:
            filters.append(Supplier.status == status)
        if category_id:
            filters.append(Supplier.category_id == str(category_id))
        if supplier_type:
            filters.append(Supplier.supplier_type == supplier_type.upper())
        if is_preferred is not None:
            filters.append(Supplier.is_preferred == is_preferred)

        count_stmt = select(func.count()).select_from(Supplier).where(*filters)
        total = self.db.execute(count_stmt).scalar_one()

        items_stmt = (
            select(Supplier)
            .where(*filters)
            .order_by(Supplier.legal_name)
            .offset(skip)
            .limit(limit)
        )
        items = list(self.db.execute(items_stmt).scalars().all())

        return items, total

    def count_by_status(self, company_id: UUID, status: str) -> int:
        """Return the number of suppliers in the given status for a company."""
        stmt = (
            select(func.count())
            .select_from(Supplier)
            .where(Supplier.company_id == company_id)
            .where(Supplier.status == status)
            .where(Supplier.is_deleted == False)  # noqa: E712
        )
        return self.db.execute(stmt).scalar_one()


# ---------------------------------------------------------------------------
# SupplierContact Repository
# ---------------------------------------------------------------------------


class SupplierContactRepository(BasePurchaseRepository[SupplierContact]):
    """Data-access layer for the ``supplier_contacts`` table."""

    def __init__(self, db: Session) -> None:
        super().__init__(db=db, model=SupplierContact)

    def get_for_supplier(
        self, company_id: UUID, supplier_id: UUID
    ) -> list[SupplierContact]:
        """Return all active contacts for a supplier."""
        stmt = (
            select(SupplierContact)
            .where(SupplierContact.company_id == company_id)
            .where(SupplierContact.supplier_id == str(supplier_id))
            .where(SupplierContact.is_deleted == False)  # noqa: E712
            .order_by(SupplierContact.is_primary.desc(), SupplierContact.last_name)
        )
        return list(self.db.execute(stmt).scalars().all())

    def get_primary(
        self, company_id: UUID, supplier_id: UUID
    ) -> SupplierContact | None:
        """Return the primary contact for a supplier, or None."""
        stmt = (
            select(SupplierContact)
            .where(SupplierContact.company_id == company_id)
            .where(SupplierContact.supplier_id == str(supplier_id))
            .where(SupplierContact.is_primary == True)  # noqa: E712
            .where(SupplierContact.is_deleted == False)  # noqa: E712
        )
        return self.db.execute(stmt).scalars().one_or_none()

    def clear_primary(self, company_id: UUID, supplier_id: UUID) -> None:
        """Set is_primary=False for all contacts of a supplier."""
        contacts = self.get_for_supplier(company_id=company_id, supplier_id=supplier_id)
        for c in contacts:
            if c.is_primary:
                c.is_primary = False
        self.db.flush()


# ---------------------------------------------------------------------------
# SupplierAddress Repository
# ---------------------------------------------------------------------------


class SupplierAddressRepository(BasePurchaseRepository[SupplierAddress]):
    """Data-access layer for the ``supplier_addresses`` table."""

    def __init__(self, db: Session) -> None:
        super().__init__(db=db, model=SupplierAddress)

    def get_for_supplier(
        self, company_id: UUID, supplier_id: UUID
    ) -> list[SupplierAddress]:
        """Return all active addresses for a supplier."""
        stmt = (
            select(SupplierAddress)
            .where(SupplierAddress.company_id == company_id)
            .where(SupplierAddress.supplier_id == str(supplier_id))
            .where(SupplierAddress.is_deleted == False)  # noqa: E712
            .order_by(SupplierAddress.address_type, SupplierAddress.is_default.desc())
        )
        return list(self.db.execute(stmt).scalars().all())

    def get_default(
        self, company_id: UUID, supplier_id: UUID, address_type: str
    ) -> SupplierAddress | None:
        """Return the default address for a supplier and type, or None."""
        stmt = (
            select(SupplierAddress)
            .where(SupplierAddress.company_id == company_id)
            .where(SupplierAddress.supplier_id == str(supplier_id))
            .where(SupplierAddress.address_type == address_type)
            .where(SupplierAddress.is_default == True)  # noqa: E712
            .where(SupplierAddress.is_deleted == False)  # noqa: E712
        )
        return self.db.execute(stmt).scalars().one_or_none()

    def clear_default(
        self, company_id: UUID, supplier_id: UUID, address_type: str
    ) -> None:
        """Set is_default=False for all addresses of a supplier and type."""
        stmt = (
            select(SupplierAddress)
            .where(SupplierAddress.company_id == company_id)
            .where(SupplierAddress.supplier_id == str(supplier_id))
            .where(SupplierAddress.address_type == address_type)
            .where(SupplierAddress.is_deleted == False)  # noqa: E712
        )
        addresses = list(self.db.execute(stmt).scalars().all())
        for a in addresses:
            if a.is_default:
                a.is_default = False
        self.db.flush()
