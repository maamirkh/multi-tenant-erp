"""Delivery Note application service — Phase 5.

Services:
  DeliveryService — lifecycle management: create (DRAFT), dispatch, deliver, cancel
                    with inventory integration (Epic 5) and SO status auto-update.

State machine (DeliveryNote.status):
  DRAFT → DISPATCHED | CANCELLED
  DISPATCHED → DELIVERED
  DELIVERED → (terminal)
  CANCELLED → (terminal)

Inventory integration (Epic 5):
  - DN creation: reserves stock via TransferService.reserve_stock()
  - DN dispatch: releases reservation + deducts stock (SALES_ISSUE OUT movement)
  - DN cancellation: releases reservation via TransferService.release_stock()
  - All operations are best-effort when product_id is present; skip if no warehouse found.

SO status auto-update (T142):
  After dispatch, compute cumulative delivered quantities:
    - All lines fully delivered → SO → DELIVERED
    - Some lines partially delivered → SO → PARTIALLY_DELIVERED

Spec ref: specs/007-sales-management/spec.md §Order Fulfilment
Task: T137, T138, T139, T140, T141, T142, T143
"""

from __future__ import annotations

import logging
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from core.exceptions.base import ConflictException, NotFoundException
from modules.sales.events import get_event_bus
from modules.sales.events.delivery_events import (
    DeliveryNoteCancelled,
    DeliveryNoteCreated,
    DeliveryNoteDelivered,
    DeliveryNoteDispatched,
)
from modules.sales.models.delivery import DeliveryNote, DeliveryNoteLine
from modules.sales.models.order import OrderLine, SalesOrder
from modules.sales.repositories.delivery import (
    DeliveryNoteLineRepository,
    DeliveryNoteRepository,
)
from modules.sales.repositories.order import OrderLineRepository, SalesOrderRepository
from modules.sales.schemas.delivery import DeliveryNoteCreate, DeliveryNoteDispatch
from modules.sales.services.sequence_service import SalesSequenceService

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# State machine
# ---------------------------------------------------------------------------

_VALID_TRANSITIONS: dict[str, list[str]] = {
    "DRAFT": ["DISPATCHED", "CANCELLED"],
    "DISPATCHED": ["DELIVERED"],
    "DELIVERED": [],
    "CANCELLED": [],
}

_TERMINAL_STATUSES = {"DELIVERED", "CANCELLED"}

# Orders that can have a Delivery Note created against them
_ELIGIBLE_ORDER_STATUSES = {"APPROVED", "PARTIALLY_DELIVERED"}


def _assert_dn_transition(current: str, target: str) -> None:
    """Raise ConflictException if the DN status transition is invalid."""
    allowed = _VALID_TRANSITIONS.get(current, [])
    if target not in allowed:
        raise ConflictException(
            f"Invalid delivery note status transition: {current!r} → {target!r}. "
            f"Allowed: {allowed}"
        )


# ---------------------------------------------------------------------------
# DeliveryService
# ---------------------------------------------------------------------------


class DeliveryService:
    """Orchestrates the full Delivery Note lifecycle.

    All public methods flush to the session but do NOT commit — the caller
    (or FastAPI dependency) owns the transaction boundary.
    """

    def __init__(self, db: Session) -> None:
        self._db = db
        self._dn_repo = DeliveryNoteRepository(db)
        self._dn_line_repo = DeliveryNoteLineRepository(db)
        self._order_repo = SalesOrderRepository(db)
        self._order_line_repo = OrderLineRepository(db)
        self._seq_service = SalesSequenceService(db=db)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _get_order_or_raise(self, company_id: UUID, order_id: UUID) -> SalesOrder:
        order = self._order_repo.get_by_id_or_none(order_id, company_id)
        if order is None:
            raise NotFoundException(f"Sales order {order_id} not found.")
        return order

    def _get_dn_or_raise(self, company_id: UUID, dn_id: UUID) -> DeliveryNote:
        dn = self._dn_repo.get_by_id_or_none(dn_id, company_id)
        if dn is None:
            raise NotFoundException(f"Delivery note {dn_id} not found.")
        return dn

    def _get_order_line_or_raise(
        self,
        company_id: UUID,
        order_id: UUID,
        line_id: UUID,
    ) -> OrderLine:
        line = self._order_line_repo.get_by_id_or_none(line_id, company_id)
        if line is None or line.order_id != str(order_id):
            raise NotFoundException(
                f"Order line {line_id} not found on order {order_id}."
            )
        return line

    def _find_default_warehouse_id(self, company_id: UUID) -> UUID | None:
        """Return the company's first ACTIVE MAIN warehouse UUID, or None if not found."""
        try:
            from modules.inventory.models.warehouse import Warehouse  # noqa: PLC0415

            wh = (
                self._db.query(Warehouse)
                .filter(
                    Warehouse.company_id == company_id,
                    Warehouse.warehouse_type == "MAIN",
                    Warehouse.status == "ACTIVE",
                    Warehouse.is_deleted.is_(False),
                )
                .first()
            )
            return wh.id if wh is not None else None
        except Exception:  # noqa: BLE001
            return None

    def _reserve_stock_for_line(
        self,
        *,
        company_id: UUID,
        product_id_str: str | None,
        quantity: Decimal,
        reference_id: str,
    ) -> None:
        """Best-effort stock reservation. Skips silently if product/warehouse not found."""
        if not product_id_str:
            return
        warehouse_id = self._find_default_warehouse_id(company_id)
        if warehouse_id is None:
            logger.warning(
                "No MAIN warehouse found for company %s — skipping stock reservation",
                company_id,
            )
            return
        try:
            from modules.inventory.repositories.stock_repository import (  # noqa: PLC0415
                SnapshotRepository,
                StockMovementRepository,
                StockPositionRepository,
            )
            from modules.inventory.repositories.transfer_repository import (  # noqa: PLC0415
                TransferRepository,
            )
            from modules.inventory.repositories.warehouse_repository import (  # noqa: PLC0415
                WarehouseRepository,
            )
            from modules.inventory.services.stock_service import (
                StockLedgerService,  # noqa: PLC0415
            )
            from modules.inventory.services.transfer_service import (
                TransferService,  # noqa: PLC0415
            )

            transfer_svc = TransferService(
                db=self._db,
                transfer_repo=TransferRepository(self._db),
                stock_ledger=StockLedgerService(
                    db=self._db,
                    position_repo=StockPositionRepository(self._db),
                    movement_repo=StockMovementRepository(self._db),
                    snapshot_repo=SnapshotRepository(self._db),
                    warehouse_repo=WarehouseRepository(self._db),
                ),
                position_repo=StockPositionRepository(self._db),
                warehouse_repo=WarehouseRepository(self._db),
            )
            transfer_svc.reserve_stock(
                company_id=company_id,
                product_id=UUID(product_id_str),
                warehouse_id=warehouse_id,
                quantity=quantity,
                reference_type="DELIVERY_NOTE",
                reference_id=reference_id,
            )
        except Exception as exc:  # noqa: BLE001
            from modules.inventory.exceptions import (
                InsufficientStockError,  # noqa: PLC0415
            )

            if isinstance(exc, InsufficientStockError):
                raise ConflictException(
                    f"Insufficient stock to reserve {quantity} for product {product_id_str}: {exc}"
                ) from exc
            logger.warning(
                "Stock reservation skipped for product %s: %s", product_id_str, exc
            )

    def _deduct_stock_for_line(
        self,
        *,
        company_id: UUID,
        product_id_str: str | None,
        quantity: Decimal,
        reference_id: str,
    ) -> None:
        """Deduct stock on dispatch: release reservation then record SALES_ISSUE movement."""
        if not product_id_str:
            return
        warehouse_id = self._find_default_warehouse_id(company_id)
        if warehouse_id is None:
            logger.warning(
                "No MAIN warehouse found for company %s — skipping stock deduction",
                company_id,
            )
            return
        try:
            from modules.inventory.exceptions import (
                InsufficientStockError,  # noqa: PLC0415
            )
            from modules.inventory.repositories.stock_repository import (  # noqa: PLC0415
                SnapshotRepository,
                StockMovementRepository,
                StockPositionRepository,
            )
            from modules.inventory.repositories.transfer_repository import (  # noqa: PLC0415
                TransferRepository,
            )
            from modules.inventory.repositories.warehouse_repository import (  # noqa: PLC0415
                WarehouseRepository,
            )
            from modules.inventory.services.stock_service import (
                StockLedgerService,  # noqa: PLC0415
            )
            from modules.inventory.services.transfer_service import (
                TransferService,  # noqa: PLC0415
            )

            pos_repo = StockPositionRepository(self._db)
            mov_repo = StockMovementRepository(self._db)
            snap_repo = SnapshotRepository(self._db)
            wh_repo = WarehouseRepository(self._db)

            ledger = StockLedgerService(
                db=self._db,
                position_repo=pos_repo,
                movement_repo=mov_repo,
                snapshot_repo=snap_repo,
                warehouse_repo=wh_repo,
            )
            transfer_svc = TransferService(
                db=self._db,
                transfer_repo=TransferRepository(self._db),
                stock_ledger=ledger,
                position_repo=pos_repo,
                warehouse_repo=wh_repo,
            )

            # Release reservation first
            try:
                transfer_svc.release_stock(
                    company_id=company_id,
                    product_id=UUID(product_id_str),
                    warehouse_id=warehouse_id,
                    quantity=quantity,
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "Failed to release reservation for product %s: %s",
                    product_id_str,
                    exc,
                )

            # Deduct from on-hand via ADJUSTMENT_OUT (= SALES_ISSUE equivalent)
            try:
                ledger.record_adjustment(
                    company_id=company_id,
                    product_id=UUID(product_id_str),
                    warehouse_id=warehouse_id,
                    movement_type="ADJUSTMENT_OUT",
                    quantity=quantity,
                    reference_type="DELIVERY_NOTE",
                    reference_id=(
                        UUID(reference_id) if len(reference_id) == 36 else uuid4()
                    ),
                )
            except InsufficientStockError as exc:
                raise ConflictException(
                    f"Insufficient stock to dispatch {quantity} of product {product_id_str}: {exc}"
                ) from exc
        except ConflictException:
            raise
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Stock deduction skipped for product %s: %s", product_id_str, exc
            )

    def _release_reservation_for_line(
        self,
        *,
        company_id: UUID,
        product_id_str: str | None,
        quantity: Decimal,
    ) -> None:
        """Release stock reservation on cancellation."""
        if not product_id_str:
            return
        warehouse_id = self._find_default_warehouse_id(company_id)
        if warehouse_id is None:
            return
        try:
            from modules.inventory.repositories.stock_repository import (  # noqa: PLC0415
                SnapshotRepository,
                StockMovementRepository,
                StockPositionRepository,
            )
            from modules.inventory.repositories.transfer_repository import (  # noqa: PLC0415
                TransferRepository,
            )
            from modules.inventory.repositories.warehouse_repository import (  # noqa: PLC0415
                WarehouseRepository,
            )
            from modules.inventory.services.stock_service import (
                StockLedgerService,  # noqa: PLC0415
            )
            from modules.inventory.services.transfer_service import (
                TransferService,  # noqa: PLC0415
            )

            pos_repo = StockPositionRepository(self._db)
            wh_repo = WarehouseRepository(self._db)
            transfer_svc = TransferService(
                db=self._db,
                transfer_repo=TransferRepository(self._db),
                stock_ledger=StockLedgerService(
                    db=self._db,
                    position_repo=pos_repo,
                    movement_repo=StockMovementRepository(self._db),
                    snapshot_repo=SnapshotRepository(self._db),
                    warehouse_repo=wh_repo,
                ),
                position_repo=pos_repo,
                warehouse_repo=wh_repo,
            )
            transfer_svc.release_stock(
                company_id=company_id,
                product_id=UUID(product_id_str),
                warehouse_id=warehouse_id,
                quantity=quantity,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Reservation release skipped for product %s: %s", product_id_str, exc
            )

    def _update_order_line_delivery(
        self,
        company_id: UUID,
        order_line_id: str,
        quantity_dispatched: Decimal,
    ) -> None:
        """Increment quantity_delivered on the OrderLine and update delivery_status."""
        line = self._order_line_repo.get_by_id_or_none(UUID(order_line_id), company_id)
        if line is None:
            logger.warning(
                "OrderLine %s not found during delivery update", order_line_id
            )
            return
        new_delivered = Decimal(str(line.quantity_delivered)) + quantity_dispatched
        line.quantity_delivered = new_delivered
        ordered = Decimal(str(line.quantity_ordered))
        if new_delivered >= ordered:
            line.delivery_status = "DELIVERED"
        else:
            line.delivery_status = "PARTIALLY_DELIVERED"

    def _revert_order_line_delivery(
        self,
        company_id: UUID,
        dn_lines: list[DeliveryNoteLine],
    ) -> None:
        """Reverse quantity_delivered on OrderLines when a DISPATCHED DN is cancelled."""
        for dn_line in dn_lines:
            line = self._order_line_repo.get_by_id_or_none(
                UUID(dn_line.order_line_id), company_id
            )
            if line is None:
                continue
            new_delivered = max(
                Decimal("0"),
                Decimal(str(line.quantity_delivered))
                - Decimal(str(dn_line.quantity_dispatched)),
            )
            line.quantity_delivered = new_delivered
            if new_delivered <= 0:
                line.delivery_status = "PENDING"
            elif new_delivered < Decimal(str(line.quantity_ordered)):
                line.delivery_status = "PARTIALLY_DELIVERED"
            else:
                line.delivery_status = "DELIVERED"

    def _compute_so_delivery_status(
        self,
        company_id: UUID,
        order_id: UUID,
    ) -> str | None:
        """Compute the new SO delivery status after a DN is dispatched.

        Returns:
            'DELIVERED'          — all order lines fully delivered
            'PARTIALLY_DELIVERED' — at least one line has some delivery
            None                 — no delivery yet (should not normally occur)
        """
        lines = self._order_line_repo.list_for_order(company_id, order_id)
        if not lines:
            return None
        all_delivered = True
        any_delivered = False
        for line in lines:
            ordered = Decimal(str(line.quantity_ordered))
            delivered = Decimal(str(line.quantity_delivered))
            if delivered >= ordered:
                any_delivered = True
            elif delivered > 0:
                any_delivered = True
                all_delivered = False
            else:
                all_delivered = False
        if all_delivered:
            return "DELIVERED"
        if any_delivered:
            return "PARTIALLY_DELIVERED"
        return None

    def _update_sales_order_status(
        self,
        company_id: UUID,
        order_id: UUID,
        new_status: str,
    ) -> None:
        """Transition the SalesOrder to the given delivery status."""
        order = self._order_repo.get_by_id_or_none(order_id, company_id)
        if order is None:
            logger.warning("Order %s not found during SO status update", order_id)
            return
        order.status = new_status

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def create_delivery_note(
        self,
        company_id: UUID,
        data: DeliveryNoteCreate,
        created_by: UUID,
    ) -> DeliveryNote:
        """Create a new Delivery Note in DRAFT status.

        Validates:
          - The order exists and is APPROVED or PARTIALLY_DELIVERED
          - Each DN line references a valid, non-fully-delivered order line
          - Cumulative dispatched quantity does not exceed ordered quantity

        Raises:
            NotFoundException: order or order line not found
            ConflictException: order not in eligible status / quantity exceeded / insufficient stock
        """
        order = self._get_order_or_raise(company_id, data.order_id)
        if order.status not in _ELIGIBLE_ORDER_STATUSES:
            raise ConflictException(
                f"Delivery notes can only be created against APPROVED or "
                f"PARTIALLY_DELIVERED orders. Current status: {order.status!r}"
            )

        # Validate lines and quantities
        for line_data in data.lines:
            order_line = self._get_order_line_or_raise(
                company_id, data.order_id, line_data.order_line_id
            )
            ordered = Decimal(str(order_line.quantity_ordered))
            already_dispatched = self._dn_repo.get_total_dispatched_for_order_line(
                company_id, line_data.order_line_id
            )
            remaining = ordered - already_dispatched
            if line_data.quantity_dispatched > remaining:
                raise ConflictException(
                    f"Order line {line_data.order_line_id}: cannot dispatch "
                    f"{line_data.quantity_dispatched} — only {remaining} remaining "
                    f"(ordered={ordered}, already_dispatched={already_dispatched})."
                )

        # Generate DN number
        delivery_number = self._seq_service.generate_next_number(company_id, "DN")

        # Create DeliveryNote header
        dn = DeliveryNote(
            company_id=company_id,
            delivery_number=delivery_number,
            order_id=str(data.order_id),
            customer_id=str(order.customer_id),
            shipping_address_id=(
                str(data.shipping_address_id)
                if data.shipping_address_id
                else order.shipping_address_id
            ),
            expected_delivery_date=data.expected_delivery_date,
            carrier=data.carrier,
            tracking_number=data.tracking_number,
            status="DRAFT",
            total_packages=data.total_packages,
            total_weight=data.total_weight,
            internal_notes=data.internal_notes,
            version=1,
        )
        dn.created_by = created_by
        self._db.add(dn)
        self._db.flush()  # Get dn.id

        # Create lines + reserve stock
        for line_data in data.lines:
            order_line = self._order_line_repo.get_by_id_or_none(
                line_data.order_line_id, company_id
            )
            dn_line = DeliveryNoteLine(
                company_id=company_id,
                delivery_note_id=str(dn.id),
                order_line_id=str(line_data.order_line_id),
                product_id=(
                    str(line_data.product_id)
                    if line_data.product_id
                    else (order_line.product_id if order_line else None)
                ),
                description=line_data.description,
                quantity_dispatched=line_data.quantity_dispatched,
                unit_of_measure=line_data.unit_of_measure,
                notes=line_data.notes,
            )
            dn_line.created_by = created_by
            self._db.add(dn_line)

            # T139: Reserve stock for this line
            self._reserve_stock_for_line(
                company_id=company_id,
                product_id_str=dn_line.product_id,
                quantity=line_data.quantity_dispatched,
                reference_id=str(dn.id),
            )

        self._db.flush()

        get_event_bus().publish(
            DeliveryNoteCreated(
                aggregate_id=dn.id,
                company_id=company_id,
                delivery_note_id=dn.id,
                delivery_number=delivery_number,
                order_id=str(data.order_id),
                customer_id=str(order.customer_id),
                line_count=len(data.lines),
            )
        )
        logger.info(
            "Delivery note created: company=%s dn=%s order=%s",
            company_id,
            dn.id,
            data.order_id,
        )
        return dn

    def dispatch(
        self,
        company_id: UUID,
        delivery_note_id: UUID,
        data: DeliveryNoteDispatch,
        dispatched_by: UUID,
    ) -> DeliveryNote:
        """Transition a DRAFT Delivery Note to DISPATCHED.

        On dispatch:
          1. Release stock reservation (Epic 5)
          2. Deduct stock (ADJUSTMENT_OUT movement via Epic 5)
          3. Update OrderLine.quantity_delivered and delivery_status
          4. Auto-update SalesOrder status (PARTIALLY_DELIVERED or DELIVERED)

        Raises:
            NotFoundException: DN not found
            ConflictException: invalid transition / insufficient stock
        """
        dn = self._get_dn_or_raise(company_id, delivery_note_id)
        _assert_dn_transition(dn.status, "DISPATCHED")

        # Fetch all lines
        dn_lines = self._dn_line_repo.list_for_delivery_note(
            company_id, delivery_note_id
        )

        # T140: Deduct stock for each line (transactional with DN status update)
        for dn_line in dn_lines:
            self._deduct_stock_for_line(
                company_id=company_id,
                product_id_str=dn_line.product_id,
                quantity=Decimal(str(dn_line.quantity_dispatched)),
                reference_id=str(dn.id),
            )

        # Update OrderLine quantities
        for dn_line in dn_lines:
            self._update_order_line_delivery(
                company_id,
                dn_line.order_line_id,
                Decimal(str(dn_line.quantity_dispatched)),
            )

        # Update DN header
        dn.status = "DISPATCHED"
        dn.dispatch_date = data.dispatch_date
        dn.dispatched_by = str(dispatched_by)
        if data.carrier:
            dn.carrier = data.carrier
        if data.tracking_number:
            dn.tracking_number = data.tracking_number
        if data.total_packages is not None:
            dn.total_packages = data.total_packages
        if data.total_weight is not None:
            dn.total_weight = data.total_weight
        dn.version += 1
        self._db.flush()

        # T142: Auto-update SO status
        order_id = UUID(dn.order_id)
        new_so_status = self._compute_so_delivery_status(company_id, order_id)
        if new_so_status is not None:
            self._update_sales_order_status(company_id, order_id, new_so_status)
            self._db.flush()

        get_event_bus().publish(
            DeliveryNoteDispatched(
                aggregate_id=dn.id,
                company_id=company_id,
                delivery_note_id=dn.id,
                delivery_number=dn.delivery_number,
                order_id=dn.order_id,
                customer_id=dn.customer_id,
                dispatch_date=data.dispatch_date,
                dispatched_by=str(dispatched_by),
            )
        )
        logger.info(
            "Delivery note dispatched: company=%s dn=%s order=%s",
            company_id,
            dn.id,
            dn.order_id,
        )
        return dn

    def mark_delivered(
        self,
        company_id: UUID,
        delivery_note_id: UUID,
        updated_by: UUID,
    ) -> DeliveryNote:
        """Transition a DISPATCHED Delivery Note to DELIVERED.

        Raises:
            NotFoundException: DN not found
            ConflictException: invalid transition
        """
        dn = self._get_dn_or_raise(company_id, delivery_note_id)
        _assert_dn_transition(dn.status, "DELIVERED")

        dn.status = "DELIVERED"
        dn.version += 1
        self._db.flush()

        get_event_bus().publish(
            DeliveryNoteDelivered(
                aggregate_id=dn.id,
                company_id=company_id,
                delivery_note_id=dn.id,
                delivery_number=dn.delivery_number,
                order_id=dn.order_id,
                customer_id=dn.customer_id,
            )
        )
        logger.info("Delivery note delivered: company=%s dn=%s", company_id, dn.id)
        return dn

    def cancel(
        self,
        company_id: UUID,
        delivery_note_id: UUID,
        cancelled_by: UUID,
    ) -> DeliveryNote:
        """Cancel a Delivery Note (DRAFT or DISPATCHED → CANCELLED).

        On cancellation:
          - DRAFT: releases stock reservations
          - DISPATCHED: reverts OrderLine.quantity_delivered and releases reservations

        Raises:
            NotFoundException: DN not found
            ConflictException: invalid transition (e.g. DELIVERED cannot be cancelled)
        """
        dn = self._get_dn_or_raise(company_id, delivery_note_id)
        _assert_dn_transition(dn.status, "CANCELLED")
        previous_status = dn.status

        dn_lines = self._dn_line_repo.list_for_delivery_note(
            company_id, delivery_note_id
        )

        if previous_status == "DISPATCHED":
            # Revert order line quantities
            self._revert_order_line_delivery(company_id, dn_lines)
            # Revert SO status based on remaining deliveries
            order_id = UUID(dn.order_id)
            new_so_status = self._compute_so_delivery_status(company_id, order_id)
            order = self._order_repo.get_by_id_or_none(order_id, company_id)
            if order is not None and new_so_status is None:
                order.status = "APPROVED"
            elif order is not None and new_so_status is not None:
                order.status = new_so_status

        # T141: Release reservations for all lines
        for dn_line in dn_lines:
            self._release_reservation_for_line(
                company_id=company_id,
                product_id_str=dn_line.product_id,
                quantity=Decimal(str(dn_line.quantity_dispatched)),
            )

        dn.status = "CANCELLED"
        dn.version += 1
        self._db.flush()

        get_event_bus().publish(
            DeliveryNoteCancelled(
                aggregate_id=dn.id,
                company_id=company_id,
                delivery_note_id=dn.id,
                delivery_number=dn.delivery_number,
                order_id=dn.order_id,
                customer_id=dn.customer_id,
                previous_status=previous_status,
            )
        )
        logger.info(
            "Delivery note cancelled: company=%s dn=%s prev_status=%s",
            company_id,
            dn.id,
            previous_status,
        )
        return dn

    def get_delivery_note(
        self,
        company_id: UUID,
        delivery_note_id: UUID,
    ) -> DeliveryNote:
        """Return a single Delivery Note by ID with company isolation."""
        return self._get_dn_or_raise(company_id, delivery_note_id)

    def list_delivery_notes(
        self,
        company_id: UUID,
        *,
        order_id: UUID | None = None,
        status: str | None = None,
        customer_id: UUID | None = None,
        dispatch_date_from: str | None = None,
        dispatch_date_to: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[DeliveryNote], int]:
        """Return paginated list of Delivery Notes with filters."""
        items = self._dn_repo.list_for_company(
            company_id,
            order_id=order_id,
            status=status,
            customer_id=customer_id,
            dispatch_date_from=dispatch_date_from,
            dispatch_date_to=dispatch_date_to,
            limit=limit,
            offset=offset,
        )
        total = self._dn_repo.count_for_company(
            company_id, order_id=order_id, status=status
        )
        return items, total
