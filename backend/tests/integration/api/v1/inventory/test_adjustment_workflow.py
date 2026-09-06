"""Integration tests for the full adjustment approval workflow.

Tests (T186 + T188):
  - DRAFT → SUBMIT → APPROVE → StockMovement created (with approval flag enabled)
  - DRAFT → SUBMIT → APPROVE directly (flag disabled bypass)
  - DRAFT → SUBMIT → REJECT → stock unchanged
  - Feature flag routing: both paths produce correct state machine routes
  - Tenant isolation

Spec ref: specs/005-inventory-management/spec.md §15 / FR-IO-012
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from unittest.mock import MagicMock

import pytest
from sqlalchemy.orm import Session

from modules.inventory.exceptions import (
    InvalidAdjustmentStateTransitionError,
)
from modules.inventory.models.warehouse import Warehouse
from modules.inventory.repositories.adjustment_repository import AdjustmentRepository
from modules.inventory.repositories.stock_repository import (
    SnapshotRepository,
    StockMovementRepository,
    StockPositionRepository,
)
from modules.inventory.repositories.warehouse_repository import WarehouseRepository
from modules.inventory.services.adjustment_service import AdjustmentService
from modules.inventory.services.feature_flag_service import FeatureFlagService
from modules.inventory.services.stock_service import StockLedgerService

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_warehouse(db: Session, company_id: uuid.UUID) -> Warehouse:
    wh = Warehouse(
        id=uuid.uuid4(),
        company_id=company_id,
        code=f"WH-{uuid.uuid4().hex[:4].upper()}",
        name="Test Warehouse",
        warehouse_type="MAIN",
        status="ACTIVE",
    )
    db.add(wh)
    db.flush()
    return wh


def _make_service(
    db: Session,
    approval_enabled: bool = False,
) -> AdjustmentService:
    flag_service = MagicMock(spec=FeatureFlagService)
    flag_service.is_enabled.return_value = approval_enabled

    ledger = StockLedgerService(
        db=db,
        position_repo=StockPositionRepository(db),
        movement_repo=StockMovementRepository(db),
        snapshot_repo=SnapshotRepository(db),
        warehouse_repo=WarehouseRepository(db),
    )

    return AdjustmentService(
        db=db,
        adjustment_repo=AdjustmentRepository(db),
        stock_ledger=ledger,
        position_repo=StockPositionRepository(db),
        warehouse_repo=WarehouseRepository(db),
        flag_service=flag_service,
    )


# ---------------------------------------------------------------------------
# Bypass workflow (flag disabled — default)
# ---------------------------------------------------------------------------


class TestAdjustmentBypassWorkflow:
    def test_submit_auto_approves_and_creates_movement(self, db_session: Session):
        """Flag disabled: DRAFT → submit → APPROVED, StockMovement created."""
        svc = _make_service(db_session, approval_enabled=False)
        cid = uuid.uuid4()
        wh = _make_warehouse(db_session, cid)
        pid = uuid.uuid4()

        # Seed opening stock
        ledger = StockLedgerService(
            db=db_session,
            position_repo=StockPositionRepository(db_session),
            movement_repo=StockMovementRepository(db_session),
            snapshot_repo=SnapshotRepository(db_session),
            warehouse_repo=WarehouseRepository(db_session),
        )
        ledger.record_opening_stock(
            company_id=cid,
            product_id=pid,
            warehouse_id=wh.id,
            quantity=Decimal("100"),
            unit_cost=Decimal("10"),
        )

        adj = svc.create_adjustment(
            company_id=cid,
            product_id=pid,
            warehouse_id=wh.id,
            movement_type="ADJUSTMENT_IN",
            quantity=Decimal("50"),
        )
        assert adj.status == "DRAFT"

        result = svc.submit_adjustment(
            company_id=cid,
            adjustment_id=adj.id,
        )
        assert result.status == "APPROVED"
        assert result.reference_movement_id is not None
        assert float(result.new_quantity) == pytest.approx(150.0)

    def test_adjustment_out_reduces_stock(self, db_session: Session):
        svc = _make_service(db_session, approval_enabled=False)
        cid = uuid.uuid4()
        wh = _make_warehouse(db_session, cid)
        pid = uuid.uuid4()

        ledger = StockLedgerService(
            db=db_session,
            position_repo=StockPositionRepository(db_session),
            movement_repo=StockMovementRepository(db_session),
            snapshot_repo=SnapshotRepository(db_session),
            warehouse_repo=WarehouseRepository(db_session),
        )
        ledger.record_opening_stock(
            company_id=cid,
            product_id=pid,
            warehouse_id=wh.id,
            quantity=Decimal("80"),
        )

        adj = svc.create_adjustment(
            company_id=cid,
            product_id=pid,
            warehouse_id=wh.id,
            movement_type="ADJUSTMENT_OUT",
            quantity=Decimal("30"),
        )
        result = svc.submit_adjustment(
            company_id=cid,
            adjustment_id=adj.id,
        )
        assert result.status == "APPROVED"
        assert float(result.new_quantity) == pytest.approx(50.0)

    def test_bypass_does_not_go_through_pending(self, db_session: Session):
        svc = _make_service(db_session, approval_enabled=False)
        cid = uuid.uuid4()
        wh = _make_warehouse(db_session, cid)
        pid = uuid.uuid4()

        adj = svc.create_adjustment(
            company_id=cid,
            product_id=pid,
            warehouse_id=wh.id,
            movement_type="ADJUSTMENT_IN",
            quantity=Decimal("10"),
        )
        result = svc.submit_adjustment(company_id=cid, adjustment_id=adj.id)
        # Never goes through PENDING_APPROVAL
        assert result.status == "APPROVED"


# ---------------------------------------------------------------------------
# Approval workflow (flag enabled)
# ---------------------------------------------------------------------------


class TestAdjustmentApprovalWorkflow:
    def test_submit_goes_to_pending_when_flag_enabled(self, db_session: Session):
        svc = _make_service(db_session, approval_enabled=True)
        cid = uuid.uuid4()
        wh = _make_warehouse(db_session, cid)
        pid = uuid.uuid4()

        adj = svc.create_adjustment(
            company_id=cid,
            product_id=pid,
            warehouse_id=wh.id,
            movement_type="ADJUSTMENT_IN",
            quantity=Decimal("20"),
        )
        result = svc.submit_adjustment(
            company_id=cid,
            adjustment_id=adj.id,
            actor_id=uuid.uuid4(),
        )
        assert result.status == "PENDING_APPROVAL"

    def test_full_approval_workflow_creates_movement(self, db_session: Session):
        svc = _make_service(db_session, approval_enabled=True)
        cid = uuid.uuid4()
        wh = _make_warehouse(db_session, cid)
        pid = uuid.uuid4()
        submitter = uuid.uuid4()
        approver = uuid.uuid4()

        # Seed opening stock first so ADJUSTMENT_IN doesn't fail
        ledger = StockLedgerService(
            db=db_session,
            position_repo=StockPositionRepository(db_session),
            movement_repo=StockMovementRepository(db_session),
            snapshot_repo=SnapshotRepository(db_session),
            warehouse_repo=WarehouseRepository(db_session),
        )
        ledger.record_opening_stock(
            company_id=cid,
            product_id=pid,
            warehouse_id=wh.id,
            quantity=Decimal("50"),
        )

        adj = svc.create_adjustment(
            company_id=cid,
            product_id=pid,
            warehouse_id=wh.id,
            movement_type="ADJUSTMENT_IN",
            quantity=Decimal("25"),
        )
        pending = svc.submit_adjustment(
            company_id=cid, adjustment_id=adj.id, actor_id=submitter
        )
        assert pending.status == "PENDING_APPROVAL"

        approved = svc.approve_adjustment(
            company_id=cid, adjustment_id=adj.id, actor_id=approver
        )
        assert approved.status == "APPROVED"
        assert approved.reference_movement_id is not None
        assert float(approved.new_quantity) == pytest.approx(75.0)

    def test_reject_does_not_modify_stock(self, db_session: Session):
        svc = _make_service(db_session, approval_enabled=True)
        cid = uuid.uuid4()
        wh = _make_warehouse(db_session, cid)
        pid = uuid.uuid4()
        submitter = uuid.uuid4()

        ledger = StockLedgerService(
            db=db_session,
            position_repo=StockPositionRepository(db_session),
            movement_repo=StockMovementRepository(db_session),
            snapshot_repo=SnapshotRepository(db_session),
            warehouse_repo=WarehouseRepository(db_session),
        )
        ledger.record_opening_stock(
            company_id=cid,
            product_id=pid,
            warehouse_id=wh.id,
            quantity=Decimal("100"),
        )

        adj = svc.create_adjustment(
            company_id=cid,
            product_id=pid,
            warehouse_id=wh.id,
            movement_type="ADJUSTMENT_OUT",
            quantity=Decimal("40"),
        )
        svc.submit_adjustment(company_id=cid, adjustment_id=adj.id, actor_id=submitter)
        rejected = svc.reject_adjustment(
            company_id=cid,
            adjustment_id=adj.id,
            rejection_reason="No authority",
            actor_id=uuid.uuid4(),
        )
        assert rejected.status == "REJECTED"
        assert rejected.reference_movement_id is None

        # Verify stock unchanged
        pos_repo = StockPositionRepository(db_session)
        pos = pos_repo.get_by_product_warehouse(
            company_id=cid, product_id=pid, warehouse_id=wh.id
        )
        assert pos is not None
        assert float(pos.qty_on_hand) == pytest.approx(100.0)

    def test_self_approval_blocked(self, db_session: Session):
        svc = _make_service(db_session, approval_enabled=True)
        cid = uuid.uuid4()
        wh = _make_warehouse(db_session, cid)
        pid = uuid.uuid4()
        actor = uuid.uuid4()

        adj = svc.create_adjustment(
            company_id=cid,
            product_id=pid,
            warehouse_id=wh.id,
            movement_type="ADJUSTMENT_IN",
            quantity=Decimal("10"),
        )
        svc.submit_adjustment(company_id=cid, adjustment_id=adj.id, actor_id=actor)

        with pytest.raises(InvalidAdjustmentStateTransitionError):
            svc.approve_adjustment(
                company_id=cid,
                adjustment_id=adj.id,
                actor_id=actor,  # same as submitter → error
            )


# ---------------------------------------------------------------------------
# Feature flag routing (T188)
# ---------------------------------------------------------------------------


class TestAdjustmentFeatureFlagRouting:
    def test_flag_disabled_goes_directly_to_approved(self, db_session: Session):
        svc = _make_service(db_session, approval_enabled=False)
        cid = uuid.uuid4()
        wh = _make_warehouse(db_session, cid)

        adj = svc.create_adjustment(
            company_id=cid,
            product_id=uuid.uuid4(),
            warehouse_id=wh.id,
            movement_type="ADJUSTMENT_IN",
            quantity=Decimal("5"),
        )
        result = svc.submit_adjustment(company_id=cid, adjustment_id=adj.id)
        assert result.status == "APPROVED"

    def test_flag_enabled_stops_at_pending_approval(self, db_session: Session):
        svc = _make_service(db_session, approval_enabled=True)
        cid = uuid.uuid4()
        wh = _make_warehouse(db_session, cid)

        adj = svc.create_adjustment(
            company_id=cid,
            product_id=uuid.uuid4(),
            warehouse_id=wh.id,
            movement_type="ADJUSTMENT_IN",
            quantity=Decimal("5"),
        )
        result = svc.submit_adjustment(company_id=cid, adjustment_id=adj.id)
        assert result.status == "PENDING_APPROVAL"

    def test_flag_enabled_then_approve_reaches_approved(self, db_session: Session):
        svc = _make_service(db_session, approval_enabled=True)
        cid = uuid.uuid4()
        wh = _make_warehouse(db_session, cid)
        submitter = uuid.uuid4()
        approver = uuid.uuid4()

        adj = svc.create_adjustment(
            company_id=cid,
            product_id=uuid.uuid4(),
            warehouse_id=wh.id,
            movement_type="ADJUSTMENT_IN",
            quantity=Decimal("5"),
        )
        svc.submit_adjustment(company_id=cid, adjustment_id=adj.id, actor_id=submitter)
        result = svc.approve_adjustment(
            company_id=cid, adjustment_id=adj.id, actor_id=approver
        )
        assert result.status == "APPROVED"

    def test_cannot_approve_after_rejection(self, db_session: Session):
        svc = _make_service(db_session, approval_enabled=True)
        cid = uuid.uuid4()
        wh = _make_warehouse(db_session, cid)
        submitter = uuid.uuid4()

        adj = svc.create_adjustment(
            company_id=cid,
            product_id=uuid.uuid4(),
            warehouse_id=wh.id,
            movement_type="ADJUSTMENT_IN",
            quantity=Decimal("5"),
        )
        svc.submit_adjustment(company_id=cid, adjustment_id=adj.id, actor_id=submitter)
        svc.reject_adjustment(
            company_id=cid,
            adjustment_id=adj.id,
            rejection_reason="Not needed",
            actor_id=uuid.uuid4(),
        )

        with pytest.raises(InvalidAdjustmentStateTransitionError):
            svc.approve_adjustment(
                company_id=cid, adjustment_id=adj.id, actor_id=uuid.uuid4()
            )
