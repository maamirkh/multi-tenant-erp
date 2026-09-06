"""Stock repositories — StockPositionRepository, StockMovementRepository, SnapshotRepository.

Design contracts:
  - StockMovementRepository: INSERT ONLY — no update/delete methods exist
  - StockPositionRepository: upsert pattern (select-then-update or insert)
  - SnapshotRepository: insert header + bulk insert lines

Spec ref: specs/005-inventory-management/spec.md §15
"""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from core.repositories.base import BaseRepository
from modules.inventory.models.stock import (
    InventorySnapshot,
    InventorySnapshotLine,
    StockMovement,
    StockPosition,
)

# =============================================================================
# StockPositionRepository
# =============================================================================


class StockPositionRepository(BaseRepository[StockPosition]):
    """Data-access layer for inventory_stock_positions.

    Provides upsert semantics: get_or_create a position, then modify in-place.
    """

    def __init__(self, db: Session) -> None:
        super().__init__(db=db, model=StockPosition)

    def get_by_product_warehouse(
        self,
        *,
        company_id: UUID,
        product_id: UUID,
        warehouse_id: UUID,
        variant_id: UUID | None = None,
    ) -> StockPosition | None:
        """Return the stock position for a product+warehouse, or None."""
        stmt = (
            select(StockPosition)
            .where(StockPosition.company_id == company_id)
            .where(StockPosition.product_id == str(product_id))
            .where(StockPosition.warehouse_id == str(warehouse_id))
            .where(StockPosition.is_deleted == False)  # noqa: E712
        )
        if variant_id is not None:
            stmt = stmt.where(StockPosition.variant_id == str(variant_id))
        else:
            stmt = stmt.where(StockPosition.variant_id == None)  # noqa: E711
        return self.db.execute(stmt).scalars().one_or_none()

    def get_or_create(
        self,
        *,
        company_id: UUID,
        product_id: UUID,
        warehouse_id: UUID,
        variant_id: UUID | None = None,
    ) -> tuple[StockPosition, bool]:
        """Return (position, created).

        If no position exists, creates one with zero quantities.
        """
        pos = self.get_by_product_warehouse(
            company_id=company_id,
            product_id=product_id,
            warehouse_id=warehouse_id,
            variant_id=variant_id,
        )
        if pos is not None:
            return pos, False

        pos = StockPosition(
            id=uuid4(),
            company_id=company_id,
            product_id=str(product_id),
            warehouse_id=str(warehouse_id),
            variant_id=str(variant_id) if variant_id else None,
            qty_on_hand=Decimal("0"),
            qty_reserved=Decimal("0"),
            qty_damaged=Decimal("0"),
        )
        self.db.add(pos)
        self.db.flush()
        return pos, True

    def list_by_warehouse(
        self,
        company_id: UUID,
        warehouse_id: UUID,
    ) -> list[StockPosition]:
        """Return all non-deleted positions for a warehouse."""
        stmt = (
            select(StockPosition)
            .where(StockPosition.company_id == company_id)
            .where(StockPosition.warehouse_id == str(warehouse_id))
            .where(StockPosition.is_deleted == False)  # noqa: E712
            .order_by(StockPosition.product_id)
        )
        return list(self.db.execute(stmt).scalars().all())

    def list_by_product(
        self,
        company_id: UUID,
        product_id: UUID,
    ) -> list[StockPosition]:
        """Return all non-deleted positions for a product across warehouses."""
        stmt = (
            select(StockPosition)
            .where(StockPosition.company_id == company_id)
            .where(StockPosition.product_id == str(product_id))
            .where(StockPosition.is_deleted == False)  # noqa: E712
        )
        return list(self.db.execute(stmt).scalars().all())

    def list_for_company(self, company_id: UUID) -> list[StockPosition]:
        """Return all non-deleted positions for the company."""
        stmt = (
            select(StockPosition)
            .where(StockPosition.company_id == company_id)
            .where(StockPosition.is_deleted == False)  # noqa: E712
        )
        return list(self.db.execute(stmt).scalars().all())

    def has_stock(self, company_id: UUID, warehouse_id: UUID) -> bool:
        """Return True if the warehouse has any non-zero qty_on_hand position."""
        stmt = (
            select(StockPosition.id)
            .where(StockPosition.company_id == company_id)
            .where(StockPosition.warehouse_id == str(warehouse_id))
            .where(StockPosition.is_deleted == False)  # noqa: E712
            .where(StockPosition.qty_on_hand > 0)
            .limit(1)
        )
        return self.db.execute(stmt).scalars().one_or_none() is not None


# =============================================================================
# StockMovementRepository — INSERT ONLY
# =============================================================================


class StockMovementRepository:
    """INSERT-only repository for inventory_stock_movements.

    CRITICAL: This repository intentionally has NO update() or delete() methods.
    The stock ledger is immutable by design.
    """

    def __init__(self, db: Session) -> None:
        self._db = db

    def append(self, movement: StockMovement) -> StockMovement:
        """Insert a new movement record. Never updates existing records."""
        self._db.add(movement)
        self._db.flush()
        return movement

    def list_by_product_warehouse(
        self,
        *,
        company_id: UUID,
        product_id: UUID | None = None,
        warehouse_id: UUID | None = None,
        movement_type: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[StockMovement]:
        """Return movements filtered by product/warehouse/type. Ordered newest first."""
        stmt = (
            select(StockMovement)
            .where(StockMovement.company_id == company_id)
            .where(StockMovement.is_deleted == False)  # noqa: E712
        )
        if product_id is not None:
            stmt = stmt.where(StockMovement.product_id == str(product_id))
        if warehouse_id is not None:
            stmt = stmt.where(StockMovement.warehouse_id == str(warehouse_id))
        if movement_type is not None:
            stmt = stmt.where(StockMovement.movement_type == movement_type)
        stmt = (
            stmt.order_by(StockMovement.performed_at.desc()).limit(limit).offset(offset)
        )
        return list(self._db.execute(stmt).scalars().all())

    def count(
        self,
        *,
        company_id: UUID,
        product_id: UUID | None = None,
        warehouse_id: UUID | None = None,
    ) -> int:
        from sqlalchemy import func

        stmt = (
            select(func.count(StockMovement.id))
            .where(StockMovement.company_id == company_id)
            .where(StockMovement.is_deleted == False)  # noqa: E712
        )
        if product_id is not None:
            stmt = stmt.where(StockMovement.product_id == str(product_id))
        if warehouse_id is not None:
            stmt = stmt.where(StockMovement.warehouse_id == str(warehouse_id))
        return self._db.execute(stmt).scalar_one()


# =============================================================================
# SnapshotRepository
# =============================================================================


class SnapshotRepository(BaseRepository[InventorySnapshot]):
    """Data-access layer for inventory_snapshots and inventory_snapshot_lines."""

    def __init__(self, db: Session) -> None:
        super().__init__(db=db, model=InventorySnapshot)

    def list_for_company(self, company_id: UUID) -> list[InventorySnapshot]:
        stmt = (
            select(InventorySnapshot)
            .where(InventorySnapshot.company_id == company_id)
            .where(InventorySnapshot.is_deleted == False)  # noqa: E712
            .order_by(InventorySnapshot.created_at.desc())
        )
        return list(self.db.execute(stmt).scalars().all())

    def list_lines(
        self, company_id: UUID, snapshot_id: UUID
    ) -> list[InventorySnapshotLine]:
        stmt = (
            select(InventorySnapshotLine)
            .where(InventorySnapshotLine.company_id == company_id)
            .where(InventorySnapshotLine.snapshot_id == str(snapshot_id))
        )
        return list(self.db.execute(stmt).scalars().all())
