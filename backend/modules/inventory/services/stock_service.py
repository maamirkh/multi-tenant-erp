"""StockLedgerService — atomic stock movement writes with WAC costing.

Design contracts:
  - Every stock change = one StockMovement INSERT + one StockPosition upsert
  - Both writes happen in the same DB transaction (caller controls commit)
  - WAC (Weighted Average Cost) is the default costing strategy
  - Negative stock is rejected under STRICT policy (qty_on_hand must remain ≥ 0)
  - Snapshot capture copies all current positions into snapshot lines

Spec ref: specs/005-inventory-management/spec.md §15
"""

from __future__ import annotations

import logging
from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from core.utils.datetime import utcnow
from modules.inventory.domain_events import (
    OpeningStockRecorded,
    OutOfStockDetected,
    StockIncreased,
    StockReduced,
)
from modules.inventory.events import get_event_bus
from modules.inventory.exceptions import (
    InsufficientStockError,
    InvalidStockQuantityError,
    StockPositionNotFoundError,
    WarehouseNotFoundError,
)
from modules.inventory.models.stock import (
    InventorySnapshot,
    InventorySnapshotLine,
    StockMovement,
    StockPosition,
)
from modules.inventory.repositories.stock_repository import (
    SnapshotRepository,
    StockMovementRepository,
    StockPositionRepository,
)
from modules.inventory.repositories.warehouse_repository import WarehouseRepository

logger = logging.getLogger(__name__)

_DIRECTION_FOR_TYPE: dict[str, str] = {
    "OPENING": "IN",
    "PURCHASE_RECEIPT": "IN",
    "SALES_ISSUE": "OUT",
    "ADJUSTMENT_IN": "IN",
    "ADJUSTMENT_OUT": "OUT",
    "TRANSFER_IN": "IN",
    "TRANSFER_OUT": "OUT",
    "RETURN_IN": "IN",
    "RETURN_OUT": "OUT",
    "DAMAGE": "OUT",
    "WRITE_OFF": "OUT",
    "SNAPSHOT": "IN",
}

_VALID_MOVEMENT_TYPES = frozenset(_DIRECTION_FOR_TYPE.keys())


def _compute_wac(
    current_qty: Decimal,
    current_cost: Decimal | None,
    incoming_qty: Decimal,
    incoming_cost: Decimal,
) -> Decimal:
    """Return new weighted average cost after receiving ``incoming_qty`` units."""
    if current_qty <= 0 or current_cost is None:
        return incoming_cost
    total_value = (current_qty * current_cost) + (incoming_qty * incoming_cost)
    new_qty = current_qty + incoming_qty
    return total_value / new_qty


class StockLedgerService:
    """Orchestrates atomic writes of stock movements + position upserts.

    All public methods flush to the session but do NOT commit — the caller
    (or FastAPI dependency) controls the transaction boundary.

    ``alert_svc`` is optional — when provided, alert thresholds are evaluated
    after every stock write within the same transaction.
    """

    def __init__(
        self,
        db: Session,
        position_repo: StockPositionRepository,
        movement_repo: StockMovementRepository,
        snapshot_repo: SnapshotRepository,
        warehouse_repo: WarehouseRepository,
        alert_svc: object | None = None,
    ) -> None:
        self._db = db
        self._pos_repo = position_repo
        self._mov_repo = movement_repo
        self._snap_repo = snapshot_repo
        self._wh_repo = warehouse_repo
        self._alert_svc = alert_svc  # AlertEvaluationService | None

    # ------------------------------------------------------------------
    # Opening stock
    # ------------------------------------------------------------------

    def record_opening_stock(
        self,
        *,
        company_id: UUID,
        product_id: UUID,
        warehouse_id: UUID,
        quantity: Decimal,
        unit_cost: Decimal | None = None,
        currency_code: str | None = None,
        variant_id: UUID | None = None,
        notes: str | None = None,
        performed_at: datetime | None = None,
        actor_id: UUID | None = None,
    ) -> tuple[StockMovement, StockPosition]:
        """Record an OPENING stock movement.

        Creates or updates the stock position.  Applies WAC costing when
        ``unit_cost`` is provided.  Quantity must be positive.
        """
        if quantity <= 0:
            raise InvalidStockQuantityError("Opening stock quantity must be positive.")

        self._validate_warehouse(company_id=company_id, warehouse_id=warehouse_id)

        pos, _ = self._pos_repo.get_or_create(
            company_id=company_id,
            product_id=product_id,
            warehouse_id=warehouse_id,
            variant_id=variant_id,
        )

        new_cost = pos.unit_cost
        if unit_cost is not None:
            new_cost = _compute_wac(
                current_qty=Decimal(str(pos.qty_on_hand)),
                current_cost=(
                    Decimal(str(pos.unit_cost)) if pos.unit_cost is not None else None
                ),
                incoming_qty=quantity,
                incoming_cost=unit_cost,
            )

        now = performed_at or utcnow()
        movement = StockMovement(
            id=uuid4(),
            company_id=company_id,
            product_id=str(product_id),
            variant_id=str(variant_id) if variant_id else None,
            warehouse_id=str(warehouse_id),
            movement_type="OPENING",
            direction="IN",
            quantity=quantity,
            unit_cost=unit_cost,
            currency_code=currency_code,
            total_cost=quantity * unit_cost if unit_cost is not None else None,
            notes=notes,
            performed_at=now,
            created_by=actor_id,
        )
        self._mov_repo.append(movement)

        pos.qty_on_hand = Decimal(str(pos.qty_on_hand)) + quantity
        if new_cost is not None:
            pos.unit_cost = new_cost
        if currency_code is not None:
            pos.currency_code = currency_code
        self._db.flush()

        if self._alert_svc is not None:
            self._alert_svc.evaluate(company_id=company_id, position=pos)

        get_event_bus().publish(
            OpeningStockRecorded(
                aggregate_id=product_id,
                company_id=company_id,
                product_id=str(product_id),
                warehouse_id=str(warehouse_id),
                quantity=str(quantity),
                unit_cost=str(unit_cost) if unit_cost is not None else None,
            )
        )

        logger.info(
            "Opening stock recorded: company=%s product=%s wh=%s qty=%s",
            company_id,
            product_id,
            warehouse_id,
            quantity,
        )
        return movement, pos

    # ------------------------------------------------------------------
    # Adjustment (in / out)
    # ------------------------------------------------------------------

    def record_adjustment(
        self,
        *,
        company_id: UUID,
        product_id: UUID,
        warehouse_id: UUID,
        movement_type: str,
        quantity: Decimal,
        unit_cost: Decimal | None = None,
        currency_code: str | None = None,
        variant_id: UUID | None = None,
        reference_type: str | None = None,
        reference_id: UUID | None = None,
        notes: str | None = None,
        performed_at: datetime | None = None,
        actor_id: UUID | None = None,
    ) -> tuple[StockMovement, StockPosition]:
        """Record a manual adjustment (ADJUSTMENT_IN or ADJUSTMENT_OUT).

        Enforces STRICT negative stock policy on OUT movements.
        """
        if movement_type not in {"ADJUSTMENT_IN", "ADJUSTMENT_OUT"}:
            raise ValueError(
                f"movement_type must be ADJUSTMENT_IN or ADJUSTMENT_OUT, got: {movement_type}"
            )
        if quantity <= 0:
            raise InvalidStockQuantityError("Adjustment quantity must be positive.")

        self._validate_warehouse(company_id=company_id, warehouse_id=warehouse_id)

        pos, _ = self._pos_repo.get_or_create(
            company_id=company_id,
            product_id=product_id,
            warehouse_id=warehouse_id,
            variant_id=variant_id,
        )

        direction = _DIRECTION_FOR_TYPE[movement_type]
        if direction == "OUT":
            available = Decimal(str(pos.qty_on_hand)) - Decimal(str(pos.qty_reserved))
            if quantity > available:
                raise InsufficientStockError(
                    f"Insufficient stock: available={available}, requested={quantity}"
                )

        new_cost = pos.unit_cost
        if direction == "IN" and unit_cost is not None:
            new_cost = _compute_wac(
                current_qty=Decimal(str(pos.qty_on_hand)),
                current_cost=(
                    Decimal(str(pos.unit_cost)) if pos.unit_cost is not None else None
                ),
                incoming_qty=quantity,
                incoming_cost=unit_cost,
            )

        now = performed_at or utcnow()
        movement = StockMovement(
            id=uuid4(),
            company_id=company_id,
            product_id=str(product_id),
            variant_id=str(variant_id) if variant_id else None,
            warehouse_id=str(warehouse_id),
            movement_type=movement_type,
            direction=direction,
            quantity=quantity,
            unit_cost=unit_cost,
            currency_code=currency_code,
            total_cost=quantity * unit_cost if unit_cost is not None else None,
            reference_type=reference_type,
            reference_id=str(reference_id) if reference_id else None,
            notes=notes,
            performed_at=now,
            created_by=actor_id,
        )
        self._mov_repo.append(movement)

        if direction == "IN":
            pos.qty_on_hand = Decimal(str(pos.qty_on_hand)) + quantity
            if new_cost is not None:
                pos.unit_cost = new_cost
            if currency_code is not None:
                pos.currency_code = currency_code
        else:
            pos.qty_on_hand = Decimal(str(pos.qty_on_hand)) - quantity

        self._db.flush()

        if self._alert_svc is not None:
            self._alert_svc.evaluate(company_id=company_id, position=pos)

        _event_cls = StockIncreased if direction == "IN" else StockReduced
        get_event_bus().publish(
            _event_cls(
                aggregate_id=product_id,
                company_id=company_id,
                product_id=str(product_id),
                warehouse_id=str(warehouse_id),
                quantity=str(quantity),
                movement_type=movement_type,
                reference_id=str(reference_id) if reference_id else None,
            )
        )
        if direction == "OUT" and Decimal(str(pos.qty_on_hand)) <= 0:
            get_event_bus().publish(
                OutOfStockDetected(
                    aggregate_id=product_id,
                    company_id=company_id,
                    product_id=str(product_id),
                    warehouse_id=str(warehouse_id),
                )
            )

        return movement, pos

    # ------------------------------------------------------------------
    # Transfer movements (TRANSFER_IN / TRANSFER_OUT)
    # ------------------------------------------------------------------

    def record_transfer_movement(
        self,
        *,
        company_id: UUID,
        product_id: UUID,
        warehouse_id: UUID,
        movement_type: str,
        quantity: Decimal,
        unit_cost: Decimal | None = None,
        currency_code: str | None = None,
        variant_id: UUID | None = None,
        reference_type: str | None = None,
        reference_id: UUID | None = None,
        notes: str | None = None,
        performed_at: datetime | None = None,
        actor_id: UUID | None = None,
    ) -> tuple[StockMovement, StockPosition]:
        """Record a TRANSFER_IN or TRANSFER_OUT movement.

        TRANSFER_OUT enforces STRICT negative stock policy.
        TRANSFER_IN applies WAC costing when unit_cost is provided.
        """
        if movement_type not in {"TRANSFER_IN", "TRANSFER_OUT"}:
            raise ValueError(
                f"movement_type must be TRANSFER_IN or TRANSFER_OUT, got: {movement_type}"
            )
        if quantity <= 0:
            raise InvalidStockQuantityError("Transfer quantity must be positive.")

        self._validate_warehouse(company_id=company_id, warehouse_id=warehouse_id)

        pos, _ = self._pos_repo.get_or_create(
            company_id=company_id,
            product_id=product_id,
            warehouse_id=warehouse_id,
            variant_id=variant_id,
        )

        direction = _DIRECTION_FOR_TYPE[movement_type]
        if direction == "OUT":
            available = (
                Decimal(str(pos.qty_on_hand))
                - Decimal(str(pos.qty_reserved))
                - Decimal(str(pos.qty_damaged))
            )
            if quantity > available:
                raise InsufficientStockError(
                    f"Insufficient stock: available={available}, requested={quantity}"
                )

        new_cost = pos.unit_cost
        if direction == "IN" and unit_cost is not None:
            new_cost = _compute_wac(
                current_qty=Decimal(str(pos.qty_on_hand)),
                current_cost=(
                    Decimal(str(pos.unit_cost)) if pos.unit_cost is not None else None
                ),
                incoming_qty=quantity,
                incoming_cost=unit_cost,
            )

        now = performed_at or utcnow()
        movement = StockMovement(
            id=uuid4(),
            company_id=company_id,
            product_id=str(product_id),
            variant_id=str(variant_id) if variant_id else None,
            warehouse_id=str(warehouse_id),
            movement_type=movement_type,
            direction=direction,
            quantity=quantity,
            unit_cost=unit_cost,
            currency_code=currency_code,
            total_cost=quantity * unit_cost if unit_cost is not None else None,
            reference_type=reference_type,
            reference_id=str(reference_id) if reference_id else None,
            notes=notes,
            performed_at=now,
            created_by=actor_id,
        )
        self._mov_repo.append(movement)

        if direction == "IN":
            pos.qty_on_hand = Decimal(str(pos.qty_on_hand)) + quantity
            if new_cost is not None:
                pos.unit_cost = new_cost
            if currency_code is not None:
                pos.currency_code = currency_code
        else:
            pos.qty_on_hand = Decimal(str(pos.qty_on_hand)) - quantity

        self._db.flush()

        if self._alert_svc is not None:
            self._alert_svc.evaluate(company_id=company_id, position=pos)

        return movement, pos

    # ------------------------------------------------------------------
    # Position reads
    # ------------------------------------------------------------------

    def get_position(
        self,
        *,
        company_id: UUID,
        product_id: UUID,
        warehouse_id: UUID,
        variant_id: UUID | None = None,
    ) -> StockPosition:
        """Return a stock position; raise StockPositionNotFoundError if missing."""
        pos = self._pos_repo.get_by_product_warehouse(
            company_id=company_id,
            product_id=product_id,
            warehouse_id=warehouse_id,
            variant_id=variant_id,
        )
        if pos is None:
            raise StockPositionNotFoundError(
                f"No stock position for product={product_id} warehouse={warehouse_id}"
            )
        return pos

    def list_positions_for_warehouse(
        self,
        *,
        company_id: UUID,
        warehouse_id: UUID,
    ) -> list[StockPosition]:
        return self._pos_repo.list_by_warehouse(
            company_id=company_id, warehouse_id=warehouse_id
        )

    def list_positions_for_product(
        self,
        *,
        company_id: UUID,
        product_id: UUID,
    ) -> list[StockPosition]:
        return self._pos_repo.list_by_product(
            company_id=company_id, product_id=product_id
        )

    def list_positions_for_company(
        self,
        *,
        company_id: UUID,
    ) -> list[StockPosition]:
        return self._pos_repo.list_for_company(company_id=company_id)

    # ------------------------------------------------------------------
    # Movement reads
    # ------------------------------------------------------------------

    def list_movements(
        self,
        *,
        company_id: UUID,
        product_id: UUID | None = None,
        warehouse_id: UUID | None = None,
        movement_type: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[StockMovement]:
        return self._mov_repo.list_by_product_warehouse(
            company_id=company_id,
            product_id=product_id,
            warehouse_id=warehouse_id,
            movement_type=movement_type,
            limit=limit,
            offset=offset,
        )

    def count_movements(
        self,
        *,
        company_id: UUID,
        product_id: UUID | None = None,
        warehouse_id: UUID | None = None,
    ) -> int:
        return self._mov_repo.count(
            company_id=company_id,
            product_id=product_id,
            warehouse_id=warehouse_id,
        )

    # ------------------------------------------------------------------
    # Snapshot
    # ------------------------------------------------------------------

    def create_snapshot(
        self,
        *,
        company_id: UUID,
        snapshot_name: str | None = None,
        actor_id: UUID | None = None,
    ) -> InventorySnapshot:
        """Capture all current stock positions into an immutable snapshot."""
        positions = self._pos_repo.list_for_company(company_id=company_id)

        snapshot = InventorySnapshot(
            id=uuid4(),
            company_id=company_id,
            snapshot_name=snapshot_name,
            status="PENDING",
            total_products=0,
            total_warehouses=0,
            created_by=actor_id,
        )
        self._db.add(snapshot)
        self._db.flush()

        products_seen: set[str] = set()
        warehouses_seen: set[str] = set()

        for pos in positions:
            line = InventorySnapshotLine(
                id=uuid4(),
                company_id=company_id,
                snapshot_id=str(snapshot.id),
                product_id=pos.product_id,
                variant_id=pos.variant_id,
                warehouse_id=pos.warehouse_id,
                qty_on_hand=pos.qty_on_hand,
                qty_reserved=pos.qty_reserved,
                qty_damaged=pos.qty_damaged,
                unit_cost=pos.unit_cost,
                currency_code=pos.currency_code,
                created_by=actor_id,
            )
            self._db.add(line)
            products_seen.add(pos.product_id)
            warehouses_seen.add(pos.warehouse_id)

        snapshot.total_products = len(products_seen)
        snapshot.total_warehouses = len(warehouses_seen)
        snapshot.status = "COMPLETED"
        self._db.flush()

        logger.info(
            "Snapshot created: %s — %d positions captured",
            snapshot.id,
            len(positions),
        )
        return snapshot

    def list_snapshots(self, *, company_id: UUID) -> list[InventorySnapshot]:
        return self._snap_repo.list_for_company(company_id=company_id)

    def get_snapshot_lines(
        self, *, company_id: UUID, snapshot_id: UUID
    ) -> list[InventorySnapshotLine]:
        return self._snap_repo.list_lines(
            company_id=company_id, snapshot_id=snapshot_id
        )

    # ------------------------------------------------------------------
    # Update stock thresholds
    # ------------------------------------------------------------------

    def update_thresholds(
        self,
        *,
        company_id: UUID,
        product_id: UUID,
        warehouse_id: UUID,
        variant_id: UUID | None = None,
        safety_stock: Decimal | None = None,
        minimum_stock: Decimal | None = None,
        maximum_stock: Decimal | None = None,
        reorder_level: Decimal | None = None,
    ) -> StockPosition:
        """Update stock threshold parameters on an existing position."""
        pos = self.get_position(
            company_id=company_id,
            product_id=product_id,
            warehouse_id=warehouse_id,
            variant_id=variant_id,
        )
        if safety_stock is not None:
            pos.safety_stock = safety_stock
        if minimum_stock is not None:
            pos.minimum_stock = minimum_stock
        if maximum_stock is not None:
            pos.maximum_stock = maximum_stock
        if reorder_level is not None:
            pos.reorder_level = reorder_level
        self._db.flush()
        return pos

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _validate_warehouse(self, *, company_id: UUID, warehouse_id: UUID) -> None:
        """Ensure the warehouse exists, belongs to this company, and is ACTIVE."""
        wh = self._wh_repo.get_by_id_or_none(company_id=company_id, id=warehouse_id)
        if not wh or wh.is_deleted:
            raise WarehouseNotFoundError(
                f"Warehouse {warehouse_id} not found for company {company_id}"
            )
        if wh.status != "ACTIVE":
            raise WarehouseNotFoundError(
                f"Warehouse {warehouse_id} is not ACTIVE (status={wh.status})"
            )
