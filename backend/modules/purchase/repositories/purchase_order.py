"""Purchase Order repositories — Phase 5.

Repositories:
  PurchaseOrderRepository  — CRUD + multi-status / supplier / date / overdue queries
  POLineRepository         — CRUD + PO-scoped line queries
  POAdditionalChargeRepo   — CRUD + PO-scoped charge queries
  POAmendmentRepository    — append-only (INSERT only) amendment records

All enforce company_id isolation on every query.

Spec ref: specs/006-purchase-management/data-model.md §Purchase Order Aggregate
Tasks: T130, T131
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from modules.purchase.models.purchase_order import (
    POAdditionalCharge,
    POAmendment,
    POLine,
    PurchaseOrder,
)
from modules.purchase.repositories import BasePurchaseRepository


class PurchaseOrderRepository(BasePurchaseRepository[PurchaseOrder]):
    """Repository for PurchaseOrder aggregate root.

    All mutations enforce company_id isolation.
    Soft-delete is inherited from BasePurchaseRepository.
    """

    def __init__(self, db: Session) -> None:
        super().__init__(db=db, model=PurchaseOrder)

    # ------------------------------------------------------------------
    # List / search
    # ------------------------------------------------------------------

    def list_for_company(
        self,
        company_id: UUID,
        *,
        status: str | None = None,
        statuses: list[str] | None = None,
        supplier_id: str | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> list[PurchaseOrder]:
        """Return POs for a company with optional filters."""
        stmt = (
            select(PurchaseOrder)
            .where(PurchaseOrder.company_id == company_id)
            .where(PurchaseOrder.is_deleted == False)  # noqa: E712
            .order_by(PurchaseOrder.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        if status:
            stmt = stmt.where(PurchaseOrder.status == status)
        if statuses:
            stmt = stmt.where(PurchaseOrder.status.in_(statuses))
        if supplier_id:
            stmt = stmt.where(PurchaseOrder.supplier_id == supplier_id)
        if date_from:
            stmt = stmt.where(PurchaseOrder.expected_delivery_date >= date_from)
        if date_to:
            stmt = stmt.where(PurchaseOrder.expected_delivery_date <= date_to)
        return list(self.db.execute(stmt).scalars().all())

    def count_for_company(
        self,
        company_id: UUID,
        *,
        status: str | None = None,
        statuses: list[str] | None = None,
        supplier_id: str | None = None,
    ) -> int:
        """Return total count for pagination metadata."""
        stmt = (
            select(func.count())
            .select_from(PurchaseOrder)
            .where(PurchaseOrder.company_id == company_id)
            .where(PurchaseOrder.is_deleted == False)  # noqa: E712
        )
        if status:
            stmt = stmt.where(PurchaseOrder.status == status)
        if statuses:
            stmt = stmt.where(PurchaseOrder.status.in_(statuses))
        if supplier_id:
            stmt = stmt.where(PurchaseOrder.supplier_id == supplier_id)
        return self.db.execute(stmt).scalar_one()

    def get_by_po_number(
        self, po_number: str, company_id: UUID
    ) -> PurchaseOrder | None:
        """Lookup by PO number within a company."""
        stmt = (
            select(PurchaseOrder)
            .where(PurchaseOrder.company_id == company_id)
            .where(PurchaseOrder.po_number == po_number)
            .where(PurchaseOrder.is_deleted == False)  # noqa: E712
        )
        return self.db.execute(stmt).scalars().first()

    # ------------------------------------------------------------------
    # Status mutations
    # ------------------------------------------------------------------

    def update_status(self, po_id: UUID, company_id: UUID, new_status: str) -> None:
        """Atomically update status + bump version (optimistic lock)."""
        stmt = (
            update(PurchaseOrder)
            .where(PurchaseOrder.id == po_id)
            .where(PurchaseOrder.company_id == company_id)
            .where(PurchaseOrder.is_deleted == False)  # noqa: E712
            .values(status=new_status, version=PurchaseOrder.version + 1)
        )
        self.db.execute(stmt)

    # ------------------------------------------------------------------
    # Totals
    # ------------------------------------------------------------------

    def update_totals(
        self,
        po_id: UUID,
        company_id: UUID,
        *,
        subtotal: Decimal,
        total_charges: Decimal,
        total_discounts: Decimal,
        tax_amount: Decimal,
        total: Decimal,
    ) -> None:
        """Persist recomputed PO totals."""
        stmt = (
            update(PurchaseOrder)
            .where(PurchaseOrder.id == po_id)
            .where(PurchaseOrder.company_id == company_id)
            .where(PurchaseOrder.is_deleted == False)  # noqa: E712
            .values(
                subtotal=subtotal,
                total_charges=total_charges,
                total_discounts=total_discounts,
                tax_amount=tax_amount,
                total=total,
            )
        )
        self.db.execute(stmt)

    # ------------------------------------------------------------------
    # Overdue detection  (T130)
    # ------------------------------------------------------------------

    def get_overdue_pos(self, company_id: UUID) -> list[PurchaseOrder]:
        """Return POs in APPROVED/PARTIALLY_RECEIVED with expected_delivery_date < today."""
        today = date.today()
        stmt = (
            select(PurchaseOrder)
            .where(PurchaseOrder.company_id == company_id)
            .where(PurchaseOrder.is_deleted == False)  # noqa: E712
            .where(PurchaseOrder.status.in_(["APPROVED", "PARTIALLY_RECEIVED"]))
            .where(PurchaseOrder.expected_delivery_date < today)
            .order_by(PurchaseOrder.expected_delivery_date.asc())
        )
        return list(self.db.execute(stmt).scalars().all())

    # ------------------------------------------------------------------
    # Open PO value by supplier (for credit limit check)
    # ------------------------------------------------------------------

    def get_open_po_total_for_supplier(
        self, supplier_id: str, company_id: UUID
    ) -> Decimal:
        """Sum total of all open POs for a supplier (for credit limit evaluation)."""
        stmt = (
            select(func.coalesce(func.sum(PurchaseOrder.total), 0))
            .where(PurchaseOrder.company_id == company_id)
            .where(PurchaseOrder.supplier_id == supplier_id)
            .where(PurchaseOrder.is_deleted == False)  # noqa: E712
            .where(
                PurchaseOrder.status.in_(
                    [
                        "PENDING_APPROVAL",
                        "APPROVED",
                        "PARTIALLY_RECEIVED",
                    ]
                )
            )
        )
        result = self.db.execute(stmt).scalar_one()
        return Decimal(str(result))


class POLineRepository(BasePurchaseRepository[POLine]):
    """Repository for POLine."""

    def __init__(self, db: Session) -> None:
        super().__init__(db=db, model=POLine)

    def list_for_po(self, po_id: UUID, company_id: UUID) -> list[POLine]:
        """Return all active lines for a PO, ordered by line_number."""
        stmt = (
            select(POLine)
            .where(POLine.company_id == company_id)
            .where(POLine.po_id == str(po_id))
            .where(POLine.is_deleted == False)  # noqa: E712
            .order_by(POLine.line_number.asc())
        )
        return list(self.db.execute(stmt).scalars().all())

    def get_max_line_number(self, po_id: UUID, company_id: UUID) -> int:
        """Return the current maximum line_number, or 0 if no lines."""
        stmt = (
            select(func.coalesce(func.max(POLine.line_number), 0))
            .where(POLine.company_id == company_id)
            .where(POLine.po_id == str(po_id))
            .where(POLine.is_deleted == False)  # noqa: E712
        )
        return int(self.db.execute(stmt).scalar_one())

    def update_received_qty(
        self,
        line_id: UUID,
        company_id: UUID,
        quantity_received: Decimal,
        quantity_rejected: Decimal,
        open_quantity: Decimal,
    ) -> None:
        """Update received/rejected/open quantities after GR confirmation."""
        stmt = (
            update(POLine)
            .where(POLine.id == line_id)
            .where(POLine.company_id == company_id)
            .values(
                quantity_received=quantity_received,
                quantity_rejected=quantity_rejected,
                open_quantity=open_quantity,
            )
        )
        self.db.execute(stmt)

    def delete_all_for_po(self, po_id: UUID, company_id: UUID) -> None:
        """Soft-delete all lines for a PO (used on PO cancellation)."""
        stmt = (
            update(POLine)
            .where(POLine.po_id == str(po_id))
            .where(POLine.company_id == company_id)
            .where(POLine.is_deleted == False)  # noqa: E712
            .values(is_deleted=True)
        )
        self.db.execute(stmt)


class POAdditionalChargeRepository(BasePurchaseRepository[POAdditionalCharge]):
    """Repository for POAdditionalCharge."""

    def __init__(self, db: Session) -> None:
        super().__init__(db=db, model=POAdditionalCharge)

    def list_for_po(self, po_id: UUID, company_id: UUID) -> list[POAdditionalCharge]:
        stmt = (
            select(POAdditionalCharge)
            .where(POAdditionalCharge.company_id == company_id)
            .where(POAdditionalCharge.po_id == str(po_id))
            .where(POAdditionalCharge.is_deleted == False)  # noqa: E712
        )
        return list(self.db.execute(stmt).scalars().all())


class POAmendmentRepository(BasePurchaseRepository[POAmendment]):
    """Repository for POAmendment (append-only — no update/delete methods).

    Invariant: Only INSERT is permitted. This repository intentionally
    omits update() and soft_delete() to enforce immutability of amendment records.
    """

    def __init__(self, db: Session) -> None:
        super().__init__(db=db, model=POAmendment)

    def list_for_po(self, po_id: UUID, company_id: UUID) -> list[POAmendment]:
        stmt = (
            select(POAmendment)
            .where(POAmendment.company_id == company_id)
            .where(POAmendment.po_id == str(po_id))
            .order_by(POAmendment.amendment_number.asc())
        )
        return list(self.db.execute(stmt).scalars().all())

    def get_max_amendment_number(self, po_id: UUID, company_id: UUID) -> int:
        """Return the current maximum amendment_number, or 0 if none."""
        stmt = (
            select(func.coalesce(func.max(POAmendment.amendment_number), 0))
            .where(POAmendment.company_id == company_id)
            .where(POAmendment.po_id == str(po_id))
        )
        return int(self.db.execute(stmt).scalar_one())
