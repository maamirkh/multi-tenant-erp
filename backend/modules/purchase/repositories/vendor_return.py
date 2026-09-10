"""Vendor Return (RMA) repositories — Phase 7.

Repositories:
  VendorReturnRepository  — CRUD + GR-linked / supplier / status queries
  ReturnLineRepository    — CRUD + RMA-scoped line queries

All enforce company_id isolation on every query.

Spec ref: specs/006-purchase-management/data-model.md §VendorReturn Aggregate
Task: T177
"""

from __future__ import annotations

from typing import Any, cast
from uuid import UUID

from sqlalchemy import CursorResult, func, select, update
from sqlalchemy.orm import Session

from modules.purchase.models.vendor_return import ReturnLine, VendorReturn
from modules.purchase.repositories import BasePurchaseRepository


class VendorReturnRepository(BasePurchaseRepository[VendorReturn]):
    """Repository for VendorReturn aggregate root."""

    def __init__(self, db: Session) -> None:
        super().__init__(db=db, model=VendorReturn)

    # ------------------------------------------------------------------
    # List / search
    # ------------------------------------------------------------------

    def list_for_company(
        self,
        company_id: UUID,
        *,
        status: str | None = None,
        gr_id: str | None = None,
        supplier_id: str | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> list[VendorReturn]:
        stmt = (
            select(VendorReturn)
            .where(VendorReturn.company_id == company_id)
            .where(VendorReturn.is_deleted == False)  # noqa: E712
            .order_by(VendorReturn.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        if status:
            stmt = stmt.where(VendorReturn.status == status)
        if gr_id:
            stmt = stmt.where(VendorReturn.gr_id == gr_id)
        if supplier_id:
            stmt = stmt.where(VendorReturn.supplier_id == supplier_id)
        return list(self.db.execute(stmt).scalars().all())

    def count_for_company(
        self,
        company_id: UUID,
        *,
        status: str | None = None,
        gr_id: str | None = None,
        supplier_id: str | None = None,
    ) -> int:
        stmt = (
            select(func.count(VendorReturn.id))
            .where(VendorReturn.company_id == company_id)
            .where(VendorReturn.is_deleted == False)  # noqa: E712
        )
        if status:
            stmt = stmt.where(VendorReturn.status == status)
        if gr_id:
            stmt = stmt.where(VendorReturn.gr_id == gr_id)
        if supplier_id:
            stmt = stmt.where(VendorReturn.supplier_id == supplier_id)
        return self.db.execute(stmt).scalar_one()

    def get_by_id_or_none(self, rma_id: UUID, company_id: UUID) -> VendorReturn | None:
        stmt = (
            select(VendorReturn)
            .where(VendorReturn.id == rma_id)
            .where(VendorReturn.company_id == company_id)
            .where(VendorReturn.is_deleted == False)  # noqa: E712
        )
        return self.db.execute(stmt).scalars().one_or_none()

    def update_status(self, rma_id: UUID, company_id: UUID, new_status: str) -> None:
        """Transition RMA to a new status."""
        stmt = (
            update(VendorReturn)
            .where(VendorReturn.id == rma_id)
            .where(VendorReturn.company_id == company_id)
            .values(status=new_status)
        )
        self.db.execute(stmt)
        self.db.flush()


class ReturnLineRepository(BasePurchaseRepository[ReturnLine]):
    """Repository for ReturnLine entities."""

    def __init__(self, db: Session) -> None:
        super().__init__(db=db, model=ReturnLine)

    def list_for_rma(self, rma_id: UUID, company_id: UUID) -> list[ReturnLine]:
        stmt = (
            select(ReturnLine)
            .where(ReturnLine.company_id == company_id)
            .where(ReturnLine.return_id == str(rma_id))
            .where(ReturnLine.is_deleted == False)  # noqa: E712
            .order_by(ReturnLine.created_at.asc())
        )
        return list(self.db.execute(stmt).scalars().all())

    def get_by_id_or_none(self, line_id: UUID, company_id: UUID) -> ReturnLine | None:
        stmt = (
            select(ReturnLine)
            .where(ReturnLine.id == line_id)
            .where(ReturnLine.company_id == company_id)
            .where(ReturnLine.is_deleted == False)  # noqa: E712
        )
        return self.db.execute(stmt).scalars().one_or_none()

    def delete_all_for_rma(self, rma_id: UUID, company_id: UUID) -> int:
        """Soft-delete all lines for a given RMA. Returns count deleted."""
        from core.utils.datetime import utcnow

        stmt = (
            update(ReturnLine)
            .where(ReturnLine.return_id == str(rma_id))
            .where(ReturnLine.company_id == company_id)
            .where(ReturnLine.is_deleted == False)  # noqa: E712
            .values(is_deleted=True, deleted_at=utcnow())
        )
        result = cast(CursorResult[Any], self.db.execute(stmt))
        self.db.flush()
        return result.rowcount
