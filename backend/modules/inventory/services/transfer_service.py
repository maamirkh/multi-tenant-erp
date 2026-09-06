"""TransferService — inter-warehouse stock transfer workflow.

Workflow:
  create_transfer   → DRAFT        (validates warehouses, creates header + lines)
  dispatch_transfer → IN_TRANSIT   (TRANSFER_OUT at source per line)
  receive_transfer  → COMPLETED    (TRANSFER_IN at destination per line)
  cancel_transfer   → CANCELLED
    - from DRAFT:      no stock change
    - from IN_TRANSIT: reversal TRANSFER_IN at source per line

Reservation:
  reserve_stock    — increments qty_reserved on StockPosition
  release_stock    — decrements qty_reserved on StockPosition

Business invariants enforced here:
  - source_warehouse_id ≠ destination_warehouse_id
  - at least one line required
  - quantity per line must be positive
  - both warehouses must be ACTIVE
  - STRICT negative stock policy on TRANSFER_OUT (available_qty ≥ requested)
  - optimistic lock prevents concurrent state transitions

Spec ref: specs/005-inventory-management/spec.md §16 / FR-IO-013
"""

from __future__ import annotations

import logging
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from core.utils.datetime import utcnow
from modules.inventory.domain_events import (
    StockTransferCancelled,
    StockTransferDispatched,
    StockTransferInitiated,
    StockTransferReceived,
)
from modules.inventory.events import get_event_bus
from modules.inventory.exceptions import (
    InsufficientStockError,
    InvalidStockQuantityError,
    InvalidTransferError,
    InvalidTransferStateTransitionError,
    TransferNotFoundError,
    WarehouseNotFoundError,
)
from modules.inventory.models.transfer import StockTransfer, StockTransferLine
from modules.inventory.repositories.stock_repository import StockPositionRepository
from modules.inventory.repositories.transfer_repository import TransferRepository
from modules.inventory.repositories.warehouse_repository import WarehouseRepository
from modules.inventory.services.stock_service import StockLedgerService

logger = logging.getLogger(__name__)

_VALID_FROM_STATUSES: dict[str, set[str]] = {
    "dispatch": {"DRAFT"},
    "receive": {"IN_TRANSIT"},
    "cancel": {"DRAFT", "IN_TRANSIT"},
}


class TransferService:
    """Orchestrates the full stock transfer lifecycle.

    All public methods flush but do NOT commit — the FastAPI dependency
    (via the session context manager) owns the transaction boundary.
    """

    def __init__(
        self,
        db: Session,
        transfer_repo: TransferRepository,
        stock_ledger: StockLedgerService,
        position_repo: StockPositionRepository,
        warehouse_repo: WarehouseRepository,
    ) -> None:
        self._db = db
        self._transfer_repo = transfer_repo
        self._ledger = stock_ledger
        self._pos_repo = position_repo
        self._wh_repo = warehouse_repo

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _require_active_warehouse(
        self, *, company_id: UUID, warehouse_id: UUID
    ) -> None:
        wh = self._wh_repo.get_by_id_or_none(id=warehouse_id, company_id=company_id)
        if wh is None or wh.is_deleted or wh.status != "ACTIVE":
            raise WarehouseNotFoundError(
                f"Warehouse {warehouse_id} not found or not active."
            )

    def _require_transfer(
        self, *, company_id: UUID, transfer_id: UUID
    ) -> StockTransfer:
        transfer = self._transfer_repo.get_by_id_with_lines(
            transfer_id=transfer_id, company_id=company_id
        )
        if transfer is None:
            raise TransferNotFoundError(f"Transfer {transfer_id} not found.")
        return transfer

    # ------------------------------------------------------------------
    # Create (T196)
    # ------------------------------------------------------------------

    def create_transfer(
        self,
        *,
        company_id: UUID,
        source_warehouse_id: UUID,
        destination_warehouse_id: UUID,
        lines: list[dict],
        notes: str | None = None,
        reference_no: str | None = None,
        actor_id: UUID | None = None,
    ) -> StockTransfer:
        """Create a DRAFT transfer with one or more product lines.

        Args:
            lines: list of dicts with keys: product_id, quantity,
                   and optionally variant_id, unit_cost, currency_code.

        Raises:
            InvalidTransferError: if source == destination.
            WarehouseNotFoundError: if either warehouse is not ACTIVE.
            InvalidStockQuantityError: if any line quantity ≤ 0.
            ValueError: if lines list is empty.
        """
        if source_warehouse_id == destination_warehouse_id:
            raise InvalidTransferError()

        if not lines:
            raise ValueError("At least one transfer line is required.")

        self._require_active_warehouse(
            company_id=company_id, warehouse_id=source_warehouse_id
        )
        self._require_active_warehouse(
            company_id=company_id, warehouse_id=destination_warehouse_id
        )

        for line in lines:
            qty = Decimal(str(line["quantity"]))
            if qty <= 0:
                raise InvalidStockQuantityError(
                    "Transfer line quantity must be positive."
                )

        transfer = StockTransfer(
            id=uuid4(),
            company_id=company_id,
            source_warehouse_id=str(source_warehouse_id),
            destination_warehouse_id=str(destination_warehouse_id),
            status="DRAFT",
            version=1,
            notes=notes,
            reference_no=reference_no,
            created_by=actor_id,
        )
        self._db.add(transfer)
        self._db.flush()  # get transfer.id

        for line in lines:
            tl = StockTransferLine(
                id=uuid4(),
                company_id=company_id,
                transfer_id=str(transfer.id),
                product_id=str(line["product_id"]),
                variant_id=str(line["variant_id"]) if line.get("variant_id") else None,
                quantity=Decimal(str(line["quantity"])),
                unit_cost=(
                    Decimal(str(line["unit_cost"])) if line.get("unit_cost") else None
                ),
                currency_code=line.get("currency_code"),
                created_by=actor_id,
            )
            self._db.add(tl)

        self._db.flush()
        # Missing-commit defect fixed during pre-Epic-9 hardening audit
        # (2026-08-14) — see warehouse_service.py::create_warehouse's comment
        # for the full root-cause explanation.
        self._db.commit()
        get_event_bus().publish(
            StockTransferInitiated(
                aggregate_id=transfer.id,
                company_id=company_id,
                transfer_id=str(transfer.id),
                from_warehouse_id=str(source_warehouse_id),
                to_warehouse_id=str(destination_warehouse_id),
            )
        )
        logger.info(
            "Transfer created: company=%s src=%s dst=%s lines=%d",
            company_id,
            source_warehouse_id,
            destination_warehouse_id,
            len(lines),
        )
        return transfer

    # ------------------------------------------------------------------
    # Dispatch — DRAFT → IN_TRANSIT (T197)
    # ------------------------------------------------------------------

    def dispatch_transfer(
        self,
        *,
        company_id: UUID,
        transfer_id: UUID,
        actor_id: UUID | None = None,
    ) -> StockTransfer:
        """Transition DRAFT → IN_TRANSIT; creates TRANSFER_OUT movements at source.

        Raises:
            TransferNotFoundError: if the transfer doesn't exist.
            InvalidTransferStateTransitionError: if status ≠ DRAFT.
            InsufficientStockError: if source has insufficient available stock.
        """
        transfer = self._require_transfer(
            company_id=company_id, transfer_id=transfer_id
        )
        if transfer.status not in _VALID_FROM_STATUSES["dispatch"]:
            raise InvalidTransferStateTransitionError(
                f"Cannot dispatch a transfer in status '{transfer.status}'. Expected DRAFT."
            )

        src_wh = UUID(transfer.source_warehouse_id)

        for line in transfer.lines:
            qty = Decimal(str(line.quantity))
            product_id = UUID(line.product_id)
            variant_id = UUID(line.variant_id) if line.variant_id else None

            # Check available stock
            pos = self._pos_repo.get_by_product_warehouse(
                company_id=company_id,
                product_id=product_id,
                warehouse_id=src_wh,
                variant_id=variant_id,
            )
            available = Decimal("0")
            if pos:
                available = (
                    Decimal(str(pos.qty_on_hand))
                    - Decimal(str(pos.qty_reserved))
                    - Decimal(str(pos.qty_damaged))
                )
            if qty > available:
                raise InsufficientStockError(
                    f"Insufficient stock for product {product_id}: "
                    f"available={available}, requested={qty}"
                )

            # Create TRANSFER_OUT movement
            movement, _ = self._ledger.record_transfer_movement(
                company_id=company_id,
                product_id=product_id,
                warehouse_id=src_wh,
                movement_type="TRANSFER_OUT",
                quantity=qty,
                unit_cost=Decimal(str(line.unit_cost)) if line.unit_cost else None,
                currency_code=line.currency_code,
                variant_id=variant_id,
                reference_type="TRANSFER",
                reference_id=transfer_id,
                actor_id=actor_id,
            )

            # Record movement id on line
            self._transfer_repo.update_line(
                line_id=line.id,
                source_movement_id=str(movement.id),
            )

        # Transition to IN_TRANSIT
        updated = self._transfer_repo.update_status(
            transfer_id=transfer_id,
            company_id=company_id,
            expected_version=transfer.version,
            new_status="IN_TRANSIT",
            dispatched_at=utcnow(),
        )
        # Missing-commit defect fixed during pre-Epic-9 hardening audit
        # (2026-08-14) — commits the TRANSFER_OUT movement(s), line updates,
        # and status transition atomically. See warehouse_service.py::
        # create_warehouse's comment for the full root-cause explanation.
        self._db.commit()
        get_event_bus().publish(
            StockTransferDispatched(
                aggregate_id=transfer_id,
                company_id=company_id,
                transfer_id=str(transfer_id),
                from_warehouse_id=transfer.source_warehouse_id,
                to_warehouse_id=transfer.destination_warehouse_id,
            )
        )
        logger.info(
            "Transfer dispatched: company=%s transfer=%s", company_id, transfer_id
        )
        return updated

    # ------------------------------------------------------------------
    # Receive — IN_TRANSIT → COMPLETED (T198)
    # ------------------------------------------------------------------

    def receive_transfer(
        self,
        *,
        company_id: UUID,
        transfer_id: UUID,
        actor_id: UUID | None = None,
    ) -> StockTransfer:
        """Transition IN_TRANSIT → COMPLETED; creates TRANSFER_IN movements at destination.

        Raises:
            TransferNotFoundError: if the transfer doesn't exist.
            InvalidTransferStateTransitionError: if status ≠ IN_TRANSIT.
        """
        transfer = self._require_transfer(
            company_id=company_id, transfer_id=transfer_id
        )
        if transfer.status not in _VALID_FROM_STATUSES["receive"]:
            raise InvalidTransferStateTransitionError(
                f"Cannot receive a transfer in status '{transfer.status}'. Expected IN_TRANSIT."
            )

        dst_wh = UUID(transfer.destination_warehouse_id)

        for line in transfer.lines:
            qty = Decimal(str(line.quantity))
            product_id = UUID(line.product_id)
            variant_id = UUID(line.variant_id) if line.variant_id else None

            movement, _ = self._ledger.record_transfer_movement(
                company_id=company_id,
                product_id=product_id,
                warehouse_id=dst_wh,
                movement_type="TRANSFER_IN",
                quantity=qty,
                unit_cost=Decimal(str(line.unit_cost)) if line.unit_cost else None,
                currency_code=line.currency_code,
                variant_id=variant_id,
                reference_type="TRANSFER",
                reference_id=transfer_id,
                actor_id=actor_id,
            )

            self._transfer_repo.update_line(
                line_id=line.id,
                destination_movement_id=str(movement.id),
            )

        updated = self._transfer_repo.update_status(
            transfer_id=transfer_id,
            company_id=company_id,
            expected_version=transfer.version,
            new_status="COMPLETED",
            received_at=utcnow(),
        )
        self._db.commit()
        get_event_bus().publish(
            StockTransferReceived(
                aggregate_id=transfer_id,
                company_id=company_id,
                transfer_id=str(transfer_id),
                from_warehouse_id=transfer.source_warehouse_id,
                to_warehouse_id=transfer.destination_warehouse_id,
            )
        )
        logger.info(
            "Transfer received: company=%s transfer=%s", company_id, transfer_id
        )
        return updated

    # ------------------------------------------------------------------
    # Cancel (T199)
    # ------------------------------------------------------------------

    def cancel_transfer(
        self,
        *,
        company_id: UUID,
        transfer_id: UUID,
        cancelled_reason: str,
        actor_id: UUID | None = None,
    ) -> StockTransfer:
        """Cancel a DRAFT or IN_TRANSIT transfer.

        - DRAFT → CANCELLED: no stock change.
        - IN_TRANSIT → CANCELLED: reversal TRANSFER_IN at source per line.

        Raises:
            TransferNotFoundError: if the transfer doesn't exist.
            InvalidTransferStateTransitionError: if status ∉ {DRAFT, IN_TRANSIT}.
        """
        transfer = self._require_transfer(
            company_id=company_id, transfer_id=transfer_id
        )
        if transfer.status not in _VALID_FROM_STATUSES["cancel"]:
            raise InvalidTransferStateTransitionError(
                f"Cannot cancel a transfer in status '{transfer.status}'."
            )

        if transfer.status == "IN_TRANSIT":
            # Reversal: TRANSFER_IN at source to restore stock
            src_wh = UUID(transfer.source_warehouse_id)
            for line in transfer.lines:
                qty = Decimal(str(line.quantity))
                product_id = UUID(line.product_id)
                variant_id = UUID(line.variant_id) if line.variant_id else None

                reversal, _ = self._ledger.record_transfer_movement(
                    company_id=company_id,
                    product_id=product_id,
                    warehouse_id=src_wh,
                    movement_type="TRANSFER_IN",
                    quantity=qty,
                    unit_cost=Decimal(str(line.unit_cost)) if line.unit_cost else None,
                    currency_code=line.currency_code,
                    variant_id=variant_id,
                    reference_type="TRANSFER_REVERSAL",
                    reference_id=transfer_id,
                    actor_id=actor_id,
                )
                self._transfer_repo.update_line(
                    line_id=line.id,
                    reversal_movement_id=str(reversal.id),
                )

        updated = self._transfer_repo.update_status(
            transfer_id=transfer_id,
            company_id=company_id,
            expected_version=transfer.version,
            new_status="CANCELLED",
            cancelled_at=utcnow(),
            cancelled_reason=cancelled_reason,
        )
        self._db.commit()
        get_event_bus().publish(
            StockTransferCancelled(
                aggregate_id=transfer_id,
                company_id=company_id,
                transfer_id=str(transfer_id),
                reason=cancelled_reason,
            )
        )
        logger.info(
            "Transfer cancelled: company=%s transfer=%s", company_id, transfer_id
        )
        return updated

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def get_transfer(
        self,
        *,
        company_id: UUID,
        transfer_id: UUID,
    ) -> StockTransfer:
        """Return a transfer with lines. Raises TransferNotFoundError if missing."""
        return self._require_transfer(company_id=company_id, transfer_id=transfer_id)

    def list_transfers(
        self,
        *,
        company_id: UUID,
        status: str | None = None,
        source_warehouse_id: UUID | None = None,
        destination_warehouse_id: UUID | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[StockTransfer]:
        return self._transfer_repo.list_for_company(
            company_id=company_id,
            status=status,
            source_warehouse_id=source_warehouse_id,
            destination_warehouse_id=destination_warehouse_id,
            limit=limit,
            offset=offset,
        )

    # ------------------------------------------------------------------
    # Stock reservation (T200-T201)
    # ------------------------------------------------------------------

    def reserve_stock(
        self,
        *,
        company_id: UUID,
        product_id: UUID,
        warehouse_id: UUID,
        quantity: Decimal,
        variant_id: UUID | None = None,
        reference_type: str | None = None,
        reference_id: str | None = None,
    ) -> None:
        """Increment qty_reserved on StockPosition.

        Validates that available_quantity (on_hand − reserved − damaged) ≥ requested.

        Raises:
            InvalidStockQuantityError: if quantity ≤ 0.
            InsufficientStockError: if available stock is insufficient.
        """
        if quantity <= 0:
            raise InvalidStockQuantityError("Reservation quantity must be positive.")

        pos, _ = self._pos_repo.get_or_create(
            company_id=company_id,
            product_id=product_id,
            warehouse_id=warehouse_id,
            variant_id=variant_id,
        )

        available = (
            Decimal(str(pos.qty_on_hand))
            - Decimal(str(pos.qty_reserved))
            - Decimal(str(pos.qty_damaged))
        )
        if quantity > available:
            raise InsufficientStockError(
                f"Cannot reserve {quantity}: only {available} available."
            )

        pos.qty_reserved = Decimal(str(pos.qty_reserved)) + quantity
        self._db.flush()
        self._db.commit()
        logger.info(
            "Stock reserved: company=%s product=%s wh=%s qty=%s",
            company_id,
            product_id,
            warehouse_id,
            quantity,
        )

    def release_stock(
        self,
        *,
        company_id: UUID,
        product_id: UUID,
        warehouse_id: UUID,
        quantity: Decimal,
        variant_id: UUID | None = None,
    ) -> None:
        """Decrement qty_reserved on StockPosition.

        Raises:
            InvalidStockQuantityError: if quantity ≤ 0.
            InsufficientStockError: if reserved < quantity (cannot release more than reserved).
        """
        if quantity <= 0:
            raise InvalidStockQuantityError("Release quantity must be positive.")

        pos, _ = self._pos_repo.get_or_create(
            company_id=company_id,
            product_id=product_id,
            warehouse_id=warehouse_id,
            variant_id=variant_id,
        )

        reserved = Decimal(str(pos.qty_reserved))
        if quantity > reserved:
            raise InsufficientStockError(
                f"Cannot release {quantity}: only {reserved} is reserved."
            )

        pos.qty_reserved = reserved - quantity
        self._db.flush()
        self._db.commit()
        logger.info(
            "Stock released: company=%s product=%s wh=%s qty=%s",
            company_id,
            product_id,
            warehouse_id,
            quantity,
        )
