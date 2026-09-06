"""TransferRepository — data-access layer for stock transfers.

Design contracts:
  - All writes go through the service layer; repository is data-access only.
  - Optimistic locking on status transitions: update WHERE version = expected_version.
  - Lines are loaded eagerly when fetching a transfer by ID to avoid N+1 queries.

Spec ref: specs/005-inventory-management/spec.md §16 / FR-IO-013
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.orm import Session, joinedload

from core.repositories.base import BaseRepository
from modules.inventory.exceptions import (
    InvalidTransferStateTransitionError,
)
from modules.inventory.models.transfer import StockTransfer, StockTransferLine


class TransferRepository(BaseRepository[StockTransfer]):
    """CRUD repository for stock transfers with optimistic lock support."""

    def __init__(self, db: Session) -> None:
        super().__init__(db=db, model=StockTransfer)

    # ------------------------------------------------------------------
    # Get by ID (with lines eagerly loaded)
    # ------------------------------------------------------------------

    def get_by_id_with_lines(
        self,
        *,
        transfer_id: UUID,
        company_id: UUID,
    ) -> StockTransfer | None:
        """Return a transfer with its lines loaded, or None if not found."""
        stmt = (
            select(StockTransfer)
            .options(joinedload(StockTransfer.lines))
            .where(StockTransfer.id == transfer_id)
            .where(StockTransfer.company_id == company_id)
            .where(StockTransfer.is_deleted == False)  # noqa: E712
        )
        return self.db.execute(stmt).unique().scalars().one_or_none()

    # ------------------------------------------------------------------
    # List / filter
    # ------------------------------------------------------------------

    def list_for_company(
        self,
        *,
        company_id: UUID,
        status: str | None = None,
        source_warehouse_id: UUID | None = None,
        destination_warehouse_id: UUID | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[StockTransfer]:
        """Return transfers for a company with optional filters."""
        stmt = (
            select(StockTransfer)
            .where(StockTransfer.company_id == company_id)
            .where(StockTransfer.is_deleted == False)  # noqa: E712
            .order_by(StockTransfer.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        if status:
            stmt = stmt.where(StockTransfer.status == status)
        if source_warehouse_id:
            stmt = stmt.where(
                StockTransfer.source_warehouse_id == str(source_warehouse_id)
            )
        if destination_warehouse_id:
            stmt = stmt.where(
                StockTransfer.destination_warehouse_id == str(destination_warehouse_id)
            )
        return list(self.db.execute(stmt).scalars().all())

    # ------------------------------------------------------------------
    # Optimistic lock update
    # ------------------------------------------------------------------

    def update_status(
        self,
        *,
        transfer_id: UUID,
        company_id: UUID,
        expected_version: int,
        new_status: str,
        **extra_fields: object,
    ) -> StockTransfer:
        """Transition status using optimistic locking.

        Raises:
          InvalidTransferStateTransitionError: if no row matched (version conflict
          or transfer not found).
        """
        values: dict[str, object] = {
            "status": new_status,
            "version": expected_version + 1,
            **extra_fields,
        }
        stmt = (
            update(StockTransfer)
            .where(StockTransfer.id == transfer_id)
            .where(StockTransfer.company_id == company_id)
            .where(StockTransfer.version == expected_version)
            .where(StockTransfer.is_deleted == False)  # noqa: E712
            .values(**values)
            .returning(StockTransfer)
        )
        result = self.db.execute(stmt).scalars().one_or_none()
        if result is None:
            raise InvalidTransferStateTransitionError(
                "Transfer not found, already modified, or concurrent update conflict."
            )
        return result

    # ------------------------------------------------------------------
    # Line helpers
    # ------------------------------------------------------------------

    def add_line(self, line: StockTransferLine) -> None:
        """Persist a transfer line."""
        self.db.add(line)

    def get_lines(
        self,
        *,
        transfer_id: UUID,
        company_id: UUID,
    ) -> list[StockTransferLine]:
        """Return all active lines for a transfer."""
        stmt = (
            select(StockTransferLine)
            .where(StockTransferLine.transfer_id == str(transfer_id))
            .where(StockTransferLine.company_id == company_id)
            .where(StockTransferLine.is_deleted == False)  # noqa: E712
        )
        return list(self.db.execute(stmt).scalars().all())

    def update_line(
        self,
        *,
        line_id: UUID,
        **fields: object,
    ) -> None:
        """Patch fields on a transfer line."""
        stmt = (
            update(StockTransferLine)
            .where(StockTransferLine.id == line_id)
            .values(**fields)
        )
        self.db.execute(stmt)
