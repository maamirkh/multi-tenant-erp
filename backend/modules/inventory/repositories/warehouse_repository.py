"""WarehouseRepository and WarehouseLocationRepository — data access for warehouse entities.

Spec ref: specs/005-inventory-management/spec.md §16
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from core.repositories.base import BaseRepository
from modules.inventory.models.stock import StockPosition
from modules.inventory.models.warehouse import Warehouse, WarehouseLocation


class WarehouseRepository(BaseRepository[Warehouse]):
    """Data-access layer for ``inventory_warehouses`` table."""

    def __init__(self, db: Session) -> None:
        super().__init__(db=db, model=Warehouse)

    def get_by_code(self, company_id: UUID, code: str) -> Warehouse | None:
        """Return the warehouse with this code for the company, or None."""
        stmt = (
            select(Warehouse)
            .where(Warehouse.company_id == company_id)
            .where(Warehouse.code == code)
            .where(Warehouse.is_deleted == False)  # noqa: E712
        )
        return self.db.execute(stmt).scalars().one_or_none()

    def list_for_company(
        self,
        company_id: UUID,
        *,
        status: str | None = None,
    ) -> list[Warehouse]:
        """Return all non-deleted warehouses for a company, optionally filtered by status."""
        stmt = (
            select(Warehouse)
            .where(Warehouse.company_id == company_id)
            .where(Warehouse.is_deleted == False)  # noqa: E712
        )
        if status:
            stmt = stmt.where(Warehouse.status == status)
        stmt = stmt.order_by(Warehouse.name)
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


class WarehouseLocationRepository(BaseRepository[WarehouseLocation]):
    """Data-access layer for ``inventory_warehouse_locations`` table."""

    def __init__(self, db: Session) -> None:
        super().__init__(db=db, model=WarehouseLocation)

    def get_by_code(
        self,
        company_id: UUID,
        warehouse_id: UUID,
        location_code: str,
    ) -> WarehouseLocation | None:
        """Return location by code within a warehouse, or None."""
        stmt = (
            select(WarehouseLocation)
            .where(WarehouseLocation.company_id == company_id)
            .where(WarehouseLocation.warehouse_id == str(warehouse_id))
            .where(WarehouseLocation.location_code == location_code)
            .where(WarehouseLocation.is_deleted == False)  # noqa: E712
        )
        return self.db.execute(stmt).scalars().one_or_none()

    def list_for_warehouse(
        self,
        company_id: UUID,
        warehouse_id: UUID,
        *,
        active_only: bool = False,
    ) -> list[WarehouseLocation]:
        """Return all locations for a warehouse."""
        stmt = (
            select(WarehouseLocation)
            .where(WarehouseLocation.company_id == company_id)
            .where(WarehouseLocation.warehouse_id == str(warehouse_id))
            .where(WarehouseLocation.is_deleted == False)  # noqa: E712
        )
        if active_only:
            stmt = stmt.where(WarehouseLocation.is_active == True)  # noqa: E712
        stmt = stmt.order_by(WarehouseLocation.location_code)
        return list(self.db.execute(stmt).scalars().all())
