"""AdjustmentRepository — data-access layer for inventory_adjustments.

Design contracts:
  - All writes go through the service layer; repository is data-access only.
  - Optimistic locking on status transitions: update WHERE version = expected_version.
  - update_status raises ConflictError if rowcount = 0 (version mismatch).

Spec ref: specs/005-inventory-management/spec.md §15 / FR-IO-012
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from core.repositories.base import BaseRepository
from modules.inventory.exceptions import (
    InvalidAdjustmentStateTransitionError,
)
from modules.inventory.models.adjustment import InventoryAdjustment


class AdjustmentRepository(BaseRepository[InventoryAdjustment]):
    """CRUD repository for inventory adjustments with optimistic lock support."""

    def __init__(self, db: Session) -> None:
        super().__init__(db=db, model=InventoryAdjustment)

    # ------------------------------------------------------------------
    # List / filter
    # ------------------------------------------------------------------

    def list_for_company(
        self,
        *,
        company_id: UUID,
        status: str | None = None,
        product_id: UUID | None = None,
        warehouse_id: UUID | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[InventoryAdjustment]:
        """Return adjustments for a company with optional filters."""
        stmt = (
            select(InventoryAdjustment)
            .where(InventoryAdjustment.company_id == company_id)
            .where(InventoryAdjustment.is_deleted == False)  # noqa: E712
            .order_by(InventoryAdjustment.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        if status:
            stmt = stmt.where(InventoryAdjustment.status == status)
        if product_id:
            stmt = stmt.where(InventoryAdjustment.product_id == str(product_id))
        if warehouse_id:
            stmt = stmt.where(InventoryAdjustment.warehouse_id == str(warehouse_id))
        return list(self.db.execute(stmt).scalars().all())

    # ------------------------------------------------------------------
    # Optimistic lock update
    # ------------------------------------------------------------------

    def update_status(
        self,
        *,
        adjustment_id: UUID,
        company_id: UUID,
        expected_version: int,
        new_status: str,
        **extra_fields: object,
    ) -> InventoryAdjustment:
        """Transition status using optimistic locking.

        Executes:
          UPDATE inventory_adjustments
          SET status = :new_status, version = :expected_version + 1, **extra_fields
          WHERE id = :adjustment_id
            AND company_id = :company_id
            AND version = :expected_version
            AND is_deleted = false

        Raises:
          AdjustmentNotFoundError: if no row matched (either not found or version conflict).
        """
        values: dict[str, object] = {
            "status": new_status,
            "version": expected_version + 1,
            **extra_fields,
        }
        stmt = (
            update(InventoryAdjustment)
            .where(InventoryAdjustment.id == adjustment_id)
            .where(InventoryAdjustment.company_id == company_id)
            .where(InventoryAdjustment.version == expected_version)
            .where(InventoryAdjustment.is_deleted == False)  # noqa: E712
            .values(**values)
            .returning(InventoryAdjustment)
        )
        result = self.db.execute(stmt).scalars().one_or_none()
        if result is None:
            raise InvalidAdjustmentStateTransitionError(
                "Adjustment not found, already modified, or concurrent update conflict."
            )
        return result
