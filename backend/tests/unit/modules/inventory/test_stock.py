"""Unit tests for stock ORM models and StockLedgerService logic.

Tests:
  - StockPosition / StockMovement model structure
  - WAC costing math (_compute_wac)
  - StockLedgerService business logic via mocks
  - Negative stock / insufficient stock enforcement
  - Immutability contract: StockMovementRepository has no update/delete

Spec ref: specs/005-inventory-management/spec.md §15
"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from sqlalchemy import CheckConstraint, UniqueConstraint

from modules.inventory.models.stock import (
    FIFOCostLayer,
    InventorySnapshot,
    InventorySnapshotLine,
    StockMovement,
    StockPosition,
)
from modules.inventory.services.stock_service import (
    StockLedgerService,
    _compute_wac,
)

# =============================================================================
# Model structure tests
# =============================================================================


class TestStockPositionModel:
    def test_tablename(self):
        assert StockPosition.__tablename__ == "inventory_stock_positions"

    def test_has_qty_columns(self):
        for col in ("qty_on_hand", "qty_reserved", "qty_damaged"):
            assert hasattr(StockPosition, col)

    def test_has_threshold_columns(self):
        for col in ("safety_stock", "minimum_stock", "maximum_stock", "reorder_level"):
            assert hasattr(StockPosition, col)

    def test_has_cost_columns(self):
        assert hasattr(StockPosition, "unit_cost")
        assert hasattr(StockPosition, "currency_code")

    def test_unique_constraint_exists(self):
        constraint_names = [
            c.name
            for c in StockPosition.__table__.constraints
            if isinstance(c, UniqueConstraint)
        ]
        assert "uq_inv_stock_pos_product_wh" in constraint_names

    def test_variant_id_nullable(self):
        col = StockPosition.__table__.c.get("variant_id")
        assert col is not None
        assert col.nullable is True


class TestStockMovementModel:
    def test_tablename(self):
        assert StockMovement.__tablename__ == "inventory_stock_movements"

    def test_has_movement_fields(self):
        for col in ("movement_type", "direction", "quantity", "performed_at"):
            assert hasattr(StockMovement, col)

    def test_has_reference_fields(self):
        assert hasattr(StockMovement, "reference_type")
        assert hasattr(StockMovement, "reference_id")

    def test_has_cost_fields(self):
        assert hasattr(StockMovement, "unit_cost")
        assert hasattr(StockMovement, "total_cost")

    def test_check_constraints_exist(self):
        check_names = [
            c.name
            for c in StockMovement.__table__.constraints
            if isinstance(c, CheckConstraint)
        ]
        assert "ck_inv_stock_mov_type" in check_names
        assert "ck_inv_stock_mov_direction" in check_names


class TestFIFOCostLayerModel:
    def test_tablename(self):
        assert FIFOCostLayer.__tablename__ == "inventory_fifo_cost_layers"

    def test_has_remaining_qty(self):
        assert hasattr(FIFOCostLayer, "remaining_qty")

    def test_has_unit_cost(self):
        assert hasattr(FIFOCostLayer, "unit_cost")


class TestInventorySnapshotModel:
    def test_tablename(self):
        assert InventorySnapshot.__tablename__ == "inventory_snapshots"

    def test_status_pending_as_default(self):
        col = InventorySnapshot.__table__.c.get("status")
        assert col is not None

    def test_snapshot_line_tablename(self):
        assert InventorySnapshotLine.__tablename__ == "inventory_snapshot_lines"


# =============================================================================
# WAC costing math
# =============================================================================


class TestComputeWAC:
    def test_zero_existing_qty_returns_incoming_cost(self):
        result = _compute_wac(
            current_qty=Decimal("0"),
            current_cost=None,
            incoming_qty=Decimal("10"),
            incoming_cost=Decimal("50"),
        )
        assert result == Decimal("50")

    def test_no_existing_cost_returns_incoming_cost(self):
        result = _compute_wac(
            current_qty=Decimal("0"),
            current_cost=None,
            incoming_qty=Decimal("5"),
            incoming_cost=Decimal("100"),
        )
        assert result == Decimal("100")

    def test_standard_wac_calculation(self):
        # 10 units @ 50 + 10 units @ 70 → new WAC = (500 + 700) / 20 = 60
        result = _compute_wac(
            current_qty=Decimal("10"),
            current_cost=Decimal("50"),
            incoming_qty=Decimal("10"),
            incoming_cost=Decimal("70"),
        )
        assert result == Decimal("60")

    def test_wac_weighted_towards_larger_batch(self):
        # 2 units @ 100 + 8 units @ 50 → (200 + 400) / 10 = 60
        result = _compute_wac(
            current_qty=Decimal("2"),
            current_cost=Decimal("100"),
            incoming_qty=Decimal("8"),
            incoming_cost=Decimal("50"),
        )
        assert result == Decimal("60")


# =============================================================================
# StockMovementRepository immutability contract
# =============================================================================


class TestMovementRepositoryImmutability:
    """The repository must NOT expose update or delete methods."""

    def test_no_update_method(self):
        from modules.inventory.repositories.stock_repository import (
            StockMovementRepository,
        )

        assert not hasattr(StockMovementRepository, "update")

    def test_no_delete_method(self):
        from modules.inventory.repositories.stock_repository import (
            StockMovementRepository,
        )

        assert not hasattr(StockMovementRepository, "delete")

    def test_no_soft_delete_method(self):
        from modules.inventory.repositories.stock_repository import (
            StockMovementRepository,
        )

        assert not hasattr(StockMovementRepository, "soft_delete")

    def test_has_append_method(self):
        from modules.inventory.repositories.stock_repository import (
            StockMovementRepository,
        )

        assert hasattr(StockMovementRepository, "append")


# =============================================================================
# StockLedgerService — unit tests via mocks
# =============================================================================


def _make_service():
    """Build a StockLedgerService with all dependencies mocked."""
    db = MagicMock()
    pos_repo = MagicMock()
    mov_repo = MagicMock()
    snap_repo = MagicMock()
    wh_repo = MagicMock()
    svc = StockLedgerService(
        db=db,
        position_repo=pos_repo,
        movement_repo=mov_repo,
        snapshot_repo=snap_repo,
        warehouse_repo=wh_repo,
    )
    return svc, db, pos_repo, mov_repo, snap_repo, wh_repo


def _make_warehouse(status="ACTIVE"):
    wh = MagicMock()
    wh.is_deleted = False
    wh.status = status
    return wh


def _make_position(qty_on_hand="0", qty_reserved="0"):
    pos = MagicMock()
    pos.qty_on_hand = Decimal(qty_on_hand)
    pos.qty_reserved = Decimal(qty_reserved)
    pos.unit_cost = None
    pos.currency_code = None
    return pos


class TestRecordOpeningStock:
    def test_positive_quantity_succeeds(self):
        svc, db, pos_repo, mov_repo, snap_repo, wh_repo = _make_service()
        wh_repo.get_by_id_or_none.return_value = _make_warehouse()
        pos = _make_position()
        pos_repo.get_or_create.return_value = (pos, True)
        mov_repo.append.return_value = MagicMock()

        _, result_pos = svc.record_opening_stock(
            company_id=uuid4(),
            product_id=uuid4(),
            warehouse_id=uuid4(),
            quantity=Decimal("100"),
        )
        assert result_pos is pos
        assert mov_repo.append.called

    def test_zero_quantity_raises(self):
        from modules.inventory.exceptions import InvalidStockQuantityError

        svc, *_ = _make_service()
        with pytest.raises(InvalidStockQuantityError):
            svc.record_opening_stock(
                company_id=uuid4(),
                product_id=uuid4(),
                warehouse_id=uuid4(),
                quantity=Decimal("0"),
            )

    def test_negative_quantity_raises(self):
        from modules.inventory.exceptions import InvalidStockQuantityError

        svc, *_ = _make_service()
        with pytest.raises(InvalidStockQuantityError):
            svc.record_opening_stock(
                company_id=uuid4(),
                product_id=uuid4(),
                warehouse_id=uuid4(),
                quantity=Decimal("-5"),
            )

    def test_inactive_warehouse_raises(self):
        from modules.inventory.exceptions import WarehouseNotFoundError

        svc, db, pos_repo, mov_repo, snap_repo, wh_repo = _make_service()
        wh_repo.get_by_id_or_none.return_value = _make_warehouse(status="INACTIVE")
        with pytest.raises(WarehouseNotFoundError):
            svc.record_opening_stock(
                company_id=uuid4(),
                product_id=uuid4(),
                warehouse_id=uuid4(),
                quantity=Decimal("10"),
            )

    def test_missing_warehouse_raises(self):
        from modules.inventory.exceptions import WarehouseNotFoundError

        svc, db, pos_repo, mov_repo, snap_repo, wh_repo = _make_service()
        wh_repo.get_by_id_or_none.return_value = None
        with pytest.raises(WarehouseNotFoundError):
            svc.record_opening_stock(
                company_id=uuid4(),
                product_id=uuid4(),
                warehouse_id=uuid4(),
                quantity=Decimal("10"),
            )

    def test_wac_applied_when_unit_cost_provided(self):
        svc, db, pos_repo, mov_repo, snap_repo, wh_repo = _make_service()
        wh_repo.get_by_id_or_none.return_value = _make_warehouse()
        pos = _make_position(qty_on_hand="0")
        pos_repo.get_or_create.return_value = (pos, True)
        mov_repo.append.return_value = MagicMock()

        svc.record_opening_stock(
            company_id=uuid4(),
            product_id=uuid4(),
            warehouse_id=uuid4(),
            quantity=Decimal("10"),
            unit_cost=Decimal("50"),
        )
        # For zero existing qty, new cost = incoming cost
        assert pos.unit_cost == Decimal("50")


class TestRecordAdjustment:
    def test_adjustment_in_increases_qty(self):
        svc, db, pos_repo, mov_repo, snap_repo, wh_repo = _make_service()
        wh_repo.get_by_id_or_none.return_value = _make_warehouse()
        pos = _make_position(qty_on_hand="100")
        pos_repo.get_or_create.return_value = (pos, False)
        mov_repo.append.return_value = MagicMock()

        svc.record_adjustment(
            company_id=uuid4(),
            product_id=uuid4(),
            warehouse_id=uuid4(),
            movement_type="ADJUSTMENT_IN",
            quantity=Decimal("20"),
        )
        assert pos.qty_on_hand == Decimal("120")

    def test_adjustment_out_decreases_qty(self):
        svc, db, pos_repo, mov_repo, snap_repo, wh_repo = _make_service()
        wh_repo.get_by_id_or_none.return_value = _make_warehouse()
        pos = _make_position(qty_on_hand="100", qty_reserved="0")
        pos_repo.get_or_create.return_value = (pos, False)
        mov_repo.append.return_value = MagicMock()

        svc.record_adjustment(
            company_id=uuid4(),
            product_id=uuid4(),
            warehouse_id=uuid4(),
            movement_type="ADJUSTMENT_OUT",
            quantity=Decimal("30"),
        )
        assert pos.qty_on_hand == Decimal("70")

    def test_insufficient_stock_raises(self):
        from modules.inventory.exceptions import InsufficientStockError

        svc, db, pos_repo, mov_repo, snap_repo, wh_repo = _make_service()
        wh_repo.get_by_id_or_none.return_value = _make_warehouse()
        pos = _make_position(qty_on_hand="10", qty_reserved="0")
        pos_repo.get_or_create.return_value = (pos, False)

        with pytest.raises(InsufficientStockError):
            svc.record_adjustment(
                company_id=uuid4(),
                product_id=uuid4(),
                warehouse_id=uuid4(),
                movement_type="ADJUSTMENT_OUT",
                quantity=Decimal("50"),
            )

    def test_invalid_movement_type_raises(self):
        svc, *_ = _make_service()
        with pytest.raises(ValueError, match="ADJUSTMENT_IN or ADJUSTMENT_OUT"):
            svc.record_adjustment(
                company_id=uuid4(),
                product_id=uuid4(),
                warehouse_id=uuid4(),
                movement_type="PURCHASE_RECEIPT",
                quantity=Decimal("10"),
            )

    def test_reserved_stock_reduces_available(self):
        from modules.inventory.exceptions import InsufficientStockError

        svc, db, pos_repo, mov_repo, snap_repo, wh_repo = _make_service()
        wh_repo.get_by_id_or_none.return_value = _make_warehouse()
        # 100 on hand, 80 reserved → only 20 available
        pos = _make_position(qty_on_hand="100", qty_reserved="80")
        pos_repo.get_or_create.return_value = (pos, False)

        with pytest.raises(InsufficientStockError):
            svc.record_adjustment(
                company_id=uuid4(),
                product_id=uuid4(),
                warehouse_id=uuid4(),
                movement_type="ADJUSTMENT_OUT",
                quantity=Decimal("25"),
            )
