"""Repositories for inventory alerts and reorder rules — Phase 8.

Provides:
  - ReorderRuleRepository
  - LowStockAlertRepository
  - ReorderSuggestionRepository

Design contracts:
  - All writes go through the service layer; repositories are data-access only.
  - Deduplication is enforced at DB level (partial unique index) and also
    checked in LowStockAlertRepository.get_open_alert to avoid a write attempt.

Spec ref: specs/005-inventory-management/spec.md §15 / FR-IO-016
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from core.repositories.base import BaseRepository
from modules.inventory.models.alerts import (
    LowStockAlert,
    ReorderRule,
    ReorderSuggestion,
)


class ReorderRuleRepository(BaseRepository[ReorderRule]):
    """CRUD for per-product/warehouse reorder rules."""

    def __init__(self, db: Session) -> None:
        super().__init__(db=db, model=ReorderRule)

    def get_for_product(
        self,
        *,
        company_id: UUID,
        product_id: UUID,
        warehouse_id: UUID | None = None,
        variant_id: UUID | None = None,
        active_only: bool = True,
    ) -> list[ReorderRule]:
        """Return rules matching the given product, optionally warehouse-specific.

        Warehouse-specific rules are returned before global (NULL warehouse) rules.
        """
        stmt = (
            select(ReorderRule)
            .where(ReorderRule.company_id == company_id)
            .where(ReorderRule.product_id == str(product_id))
            .where(ReorderRule.is_deleted == False)  # noqa: E712
        )
        if active_only:
            stmt = stmt.where(ReorderRule.is_active == True)  # noqa: E712
        if variant_id is not None:
            stmt = stmt.where(ReorderRule.variant_id == str(variant_id))
        if warehouse_id is not None:
            # Match warehouse-specific rules OR global (NULL) rules
            from sqlalchemy import or_

            stmt = stmt.where(
                or_(
                    ReorderRule.warehouse_id == str(warehouse_id),
                    ReorderRule.warehouse_id.is_(None),
                )
            )
        # Warehouse-specific rules first (non-null warehouse_id)
        stmt = stmt.order_by(
            ReorderRule.warehouse_id.is_(None),  # NULLs last
        )
        return list(self.db.execute(stmt).scalars().all())

    def list_for_company(
        self,
        *,
        company_id: UUID,
        active_only: bool = False,
        limit: int = 200,
        offset: int = 0,
    ) -> list[ReorderRule]:
        stmt = (
            select(ReorderRule)
            .where(ReorderRule.company_id == company_id)
            .where(ReorderRule.is_deleted == False)  # noqa: E712
            .order_by(ReorderRule.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        if active_only:
            stmt = stmt.where(ReorderRule.is_active == True)  # noqa: E712
        return list(self.db.execute(stmt).scalars().all())


class LowStockAlertRepository(BaseRepository[LowStockAlert]):
    """CRUD and alert-lifecycle queries for LowStockAlert."""

    def __init__(self, db: Session) -> None:
        super().__init__(db=db, model=LowStockAlert)

    def get_open_alert(
        self,
        *,
        company_id: UUID,
        product_id: UUID,
        warehouse_id: UUID,
        alert_type: str,
    ) -> LowStockAlert | None:
        """Return the single OPEN alert for this product × warehouse × type, or None."""
        stmt = (
            select(LowStockAlert)
            .where(LowStockAlert.company_id == company_id)
            .where(LowStockAlert.product_id == str(product_id))
            .where(LowStockAlert.warehouse_id == str(warehouse_id))
            .where(LowStockAlert.alert_type == alert_type)
            .where(LowStockAlert.status == "OPEN")
            .where(LowStockAlert.is_deleted == False)  # noqa: E712
        )
        return self.db.execute(stmt).scalars().one_or_none()

    def list_for_company(
        self,
        *,
        company_id: UUID,
        status: str | None = None,
        alert_type: str | None = None,
        product_id: UUID | None = None,
        warehouse_id: UUID | None = None,
        limit: int = 200,
        offset: int = 0,
    ) -> list[LowStockAlert]:
        """Return alerts with optional filters."""
        stmt = (
            select(LowStockAlert)
            .where(LowStockAlert.company_id == company_id)
            .where(LowStockAlert.is_deleted == False)  # noqa: E712
            .order_by(LowStockAlert.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        if status:
            stmt = stmt.where(LowStockAlert.status == status)
        if alert_type:
            stmt = stmt.where(LowStockAlert.alert_type == alert_type)
        if product_id:
            stmt = stmt.where(LowStockAlert.product_id == str(product_id))
        if warehouse_id:
            stmt = stmt.where(LowStockAlert.warehouse_id == str(warehouse_id))
        return list(self.db.execute(stmt).scalars().all())

    def get_all_open_for_position(
        self,
        *,
        company_id: UUID,
        product_id: UUID,
        warehouse_id: UUID,
    ) -> list[LowStockAlert]:
        """Return all OPEN alerts for this product × warehouse (all types)."""
        stmt = (
            select(LowStockAlert)
            .where(LowStockAlert.company_id == company_id)
            .where(LowStockAlert.product_id == str(product_id))
            .where(LowStockAlert.warehouse_id == str(warehouse_id))
            .where(LowStockAlert.status == "OPEN")
            .where(LowStockAlert.is_deleted == False)  # noqa: E712
        )
        return list(self.db.execute(stmt).scalars().all())


class ReorderSuggestionRepository(BaseRepository[ReorderSuggestion]):
    """CRUD for reorder suggestions."""

    def __init__(self, db: Session) -> None:
        super().__init__(db=db, model=ReorderSuggestion)

    def list_for_company(
        self,
        *,
        company_id: UUID,
        status: str | None = None,
        product_id: UUID | None = None,
        limit: int = 200,
        offset: int = 0,
    ) -> list[ReorderSuggestion]:
        stmt = (
            select(ReorderSuggestion)
            .where(ReorderSuggestion.company_id == company_id)
            .where(ReorderSuggestion.is_deleted == False)  # noqa: E712
            .order_by(ReorderSuggestion.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        if status:
            stmt = stmt.where(ReorderSuggestion.status == status)
        if product_id:
            stmt = stmt.where(ReorderSuggestion.product_id == str(product_id))
        return list(self.db.execute(stmt).scalars().all())
