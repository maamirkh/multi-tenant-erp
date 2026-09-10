"""Goods Receipt repositories — Phase 6.

Repositories:
  GoodsReceiptRepository  — CRUD + PO-linked / supplier / status queries
  GRLineRepository        — CRUD + GR-scoped line queries

All enforce company_id isolation on every query.

Spec ref: specs/006-purchase-management/data-model.md §GoodsReceipt Aggregate
Task: T156
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any, cast
from uuid import UUID

from sqlalchemy import CursorResult, func, select, update
from sqlalchemy.orm import Session

from modules.purchase.models.goods_receipt import GoodsReceipt, GRLine
from modules.purchase.repositories import BasePurchaseRepository


class GoodsReceiptRepository(BasePurchaseRepository[GoodsReceipt]):
    """Repository for GoodsReceipt aggregate root."""

    def __init__(self, db: Session) -> None:
        super().__init__(db=db, model=GoodsReceipt)

    # ------------------------------------------------------------------
    # List / search
    # ------------------------------------------------------------------

    def list_for_company(
        self,
        company_id: UUID,
        *,
        status: str | None = None,
        po_id: str | None = None,
        supplier_id: str | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> list[GoodsReceipt]:
        stmt = (
            select(GoodsReceipt)
            .where(GoodsReceipt.company_id == company_id)
            .where(GoodsReceipt.is_deleted == False)  # noqa: E712
            .order_by(GoodsReceipt.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        if status:
            stmt = stmt.where(GoodsReceipt.status == status)
        if po_id:
            stmt = stmt.where(GoodsReceipt.po_id == po_id)
        if supplier_id:
            stmt = stmt.where(GoodsReceipt.supplier_id == supplier_id)
        return list(self.db.execute(stmt).scalars().all())

    def count_for_company(
        self,
        company_id: UUID,
        *,
        status: str | None = None,
        po_id: str | None = None,
        supplier_id: str | None = None,
    ) -> int:
        stmt = (
            select(func.count(GoodsReceipt.id))
            .where(GoodsReceipt.company_id == company_id)
            .where(GoodsReceipt.is_deleted == False)  # noqa: E712
        )
        if status:
            stmt = stmt.where(GoodsReceipt.status == status)
        if po_id:
            stmt = stmt.where(GoodsReceipt.po_id == po_id)
        if supplier_id:
            stmt = stmt.where(GoodsReceipt.supplier_id == supplier_id)
        return self.db.execute(stmt).scalar_one()

    def get_by_id_or_none(self, gr_id: UUID, company_id: UUID) -> GoodsReceipt | None:
        stmt = (
            select(GoodsReceipt)
            .where(GoodsReceipt.id == gr_id)
            .where(GoodsReceipt.company_id == company_id)
            .where(GoodsReceipt.is_deleted == False)  # noqa: E712
        )
        return self.db.execute(stmt).scalars().one_or_none()

    def update_status(self, gr_id: UUID, company_id: UUID, new_status: str) -> None:
        """Transition GR to a new status."""
        stmt = (
            update(GoodsReceipt)
            .where(GoodsReceipt.id == gr_id)
            .where(GoodsReceipt.company_id == company_id)
            .values(status=new_status)
        )
        self.db.execute(stmt)
        self.db.flush()

    def list_confirmed_for_po(
        self, po_id: UUID, company_id: UUID
    ) -> list[GoodsReceipt]:
        """Return all CONFIRMED GRs for a given PO."""
        stmt = (
            select(GoodsReceipt)
            .where(GoodsReceipt.company_id == company_id)
            .where(GoodsReceipt.po_id == str(po_id))
            .where(GoodsReceipt.status == "CONFIRMED")
            .where(GoodsReceipt.is_deleted == False)  # noqa: E712
            .order_by(GoodsReceipt.created_at.asc())
        )
        return list(self.db.execute(stmt).scalars().all())

    def has_confirmed_gr_for_po(self, po_id: UUID, company_id: UUID) -> bool:
        """Return True if at least one CONFIRMED GR exists for the given PO."""
        stmt = (
            select(func.count(GoodsReceipt.id))
            .where(GoodsReceipt.company_id == company_id)
            .where(GoodsReceipt.po_id == str(po_id))
            .where(GoodsReceipt.status == "CONFIRMED")
            .where(GoodsReceipt.is_deleted == False)  # noqa: E712
        )
        return self.db.execute(stmt).scalar_one() > 0


class GRLineRepository(BasePurchaseRepository[GRLine]):
    """Repository for GRLine entities."""

    def __init__(self, db: Session) -> None:
        super().__init__(db=db, model=GRLine)

    def list_for_gr(self, gr_id: UUID, company_id: UUID) -> list[GRLine]:
        stmt = (
            select(GRLine)
            .where(GRLine.company_id == company_id)
            .where(GRLine.gr_id == str(gr_id))
            .where(GRLine.is_deleted == False)  # noqa: E712
            .order_by(GRLine.created_at.asc())
        )
        return list(self.db.execute(stmt).scalars().all())

    def get_by_id_or_none(self, line_id: UUID, company_id: UUID) -> GRLine | None:
        stmt = (
            select(GRLine)
            .where(GRLine.id == line_id)
            .where(GRLine.company_id == company_id)
            .where(GRLine.is_deleted == False)  # noqa: E712
        )
        return self.db.execute(stmt).scalars().one_or_none()

    def get_received_qty_for_po_line(
        self,
        po_line_id: UUID,
        company_id: UUID,
        exclude_gr_id: UUID | None = None,
    ) -> Decimal:
        """Return total quantity_received across all CONFIRMED GRs for a PO line.

        Uses a two-phase approach for cross-dialect compatibility (PostgreSQL + SQLite tests):
          1. Fetch confirmed GR IDs as Python UUID objects
          2. Convert to str() format (same as stored in GRLine.gr_id) and run the sum query
        """
        # Phase 1: collect confirmed GR IDs for this company
        confirmed_gr_stmt = (
            select(GoodsReceipt.id)
            .where(GoodsReceipt.company_id == company_id)
            .where(GoodsReceipt.status == "CONFIRMED")
            .where(GoodsReceipt.is_deleted == False)  # noqa: E712
        )
        if exclude_gr_id is not None:
            confirmed_gr_stmt = confirmed_gr_stmt.where(
                GoodsReceipt.id != exclude_gr_id
            )

        confirmed_ids = self.db.execute(confirmed_gr_stmt).scalars().all()
        if not confirmed_ids:
            return Decimal("0")

        # Phase 2: sum GRLine.quantity_received for those GRs and the given PO line
        # GRLine.gr_id stores str(uuid) — same format as str(UUID object)
        confirmed_gr_id_strs = [str(gid) for gid in confirmed_ids]

        stmt = (
            select(func.coalesce(func.sum(GRLine.quantity_received), Decimal("0")))
            .where(GRLine.company_id == company_id)
            .where(GRLine.po_line_id == str(po_line_id))
            .where(GRLine.is_deleted == False)  # noqa: E712
            .where(GRLine.gr_id.in_(confirmed_gr_id_strs))
        )
        result = self.db.execute(stmt).scalar_one()
        return Decimal(str(result)) if result is not None else Decimal("0")

    def delete_all_for_gr(self, gr_id: UUID, company_id: UUID) -> int:
        """Soft-delete all lines for a given GR. Returns count deleted."""
        from core.utils.datetime import utcnow

        stmt = (
            update(GRLine)
            .where(GRLine.gr_id == str(gr_id))
            .where(GRLine.company_id == company_id)
            .where(GRLine.is_deleted == False)  # noqa: E712
            .values(is_deleted=True, deleted_at=utcnow())
        )
        result = cast(CursorResult[Any], self.db.execute(stmt))
        self.db.flush()
        return result.rowcount
