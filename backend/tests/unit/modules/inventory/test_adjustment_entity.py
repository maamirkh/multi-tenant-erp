"""Unit tests for InventoryAdjustment model and AdjustmentService logic.

Tests:
  - Model structure (T184)
  - Valid state transitions
  - Invalid transition guards
  - Self-approval invariant
  - Optimistic lock version handling
  - AdjustmentService create / submit / approve / reject via mocks

Spec ref: specs/005-inventory-management/spec.md §15 / FR-IO-012
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, cast
from unittest.mock import MagicMock

import pytest
from sqlalchemy import Table

from modules.inventory.exceptions import (
    AdjustmentNotFoundError,
    InvalidAdjustmentStateTransitionError,
    InvalidStockQuantityError,
    WarehouseNotFoundError,
)
from modules.inventory.models.adjustment import InventoryAdjustment
from modules.inventory.services.adjustment_service import AdjustmentService

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_adj(**kwargs) -> MagicMock:
    """Return a MagicMock that simulates an InventoryAdjustment instance.

    Uses MagicMock rather than InventoryAdjustment.__new__() to avoid
    SQLAlchemy instrumentation errors when accessing mapped attributes
    outside of a session context.
    """
    defaults: dict[str, Any] = {
        "id": uuid.uuid4(),
        "company_id": uuid.uuid4(),
        "product_id": str(uuid.uuid4()),
        "warehouse_id": str(uuid.uuid4()),
        "movement_type": "ADJUSTMENT_IN",
        "quantity": Decimal("10"),
        "unit_cost": None,
        "currency_code": None,
        "variant_id": None,
        "notes": None,
        "status": "DRAFT",
        "version": 1,
        "submitted_by": None,
        "approved_by": None,
        "rejected_by": None,
    }
    all_attrs = {**defaults, **kwargs}
    mock = MagicMock()
    for k, v in all_attrs.items():
        setattr(mock, k, v)
    return mock


@dataclass
class _ServiceUnderTest:
    """Bundles the real ``AdjustmentService`` with its own constructor
    mocks, so tests assert against the mocks directly (``m.wh_repo...``)
    rather than through ``svc._wh_repo...`` — the latter is statically
    typed as the real repository class regardless of what was actually
    passed at construction, so MagicMock-only members like
    ``.return_value``/``.assert_called_once()`` don't type-check on it."""

    service: AdjustmentService
    db: MagicMock
    adj_repo: MagicMock
    ledger: MagicMock
    pos_repo: MagicMock
    wh_repo: MagicMock
    flag_service: MagicMock


def _make_service(approval_enabled: bool = False) -> _ServiceUnderTest:
    db = MagicMock()
    adj_repo = MagicMock()
    stock_ledger = MagicMock()
    pos_repo = MagicMock()
    wh_repo = MagicMock()
    flag_service = MagicMock()
    flag_service.is_enabled.return_value = approval_enabled

    svc = AdjustmentService(
        db=db,
        adjustment_repo=adj_repo,
        stock_ledger=stock_ledger,
        position_repo=pos_repo,
        warehouse_repo=wh_repo,
        flag_service=flag_service,
    )
    return _ServiceUnderTest(
        service=svc,
        db=db,
        adj_repo=adj_repo,
        ledger=stock_ledger,
        pos_repo=pos_repo,
        wh_repo=wh_repo,
        flag_service=flag_service,
    )


# ---------------------------------------------------------------------------
# Model: structure
# ---------------------------------------------------------------------------


class TestInventoryAdjustmentModel:
    def test_tablename(self):
        assert InventoryAdjustment.__tablename__ == "inventory_adjustments"

    def test_has_version_column(self):
        cols = {c.name for c in InventoryAdjustment.__table__.columns}
        assert "version" in cols

    def test_has_status_column(self):
        cols = {c.name for c in InventoryAdjustment.__table__.columns}
        assert "status" in cols

    def test_has_submitted_by_and_approved_by(self):
        cols = {c.name for c in InventoryAdjustment.__table__.columns}
        assert "submitted_by" in cols
        assert "approved_by" in cols
        assert "rejected_by" in cols

    def test_has_old_and_new_quantity(self):
        cols = {c.name for c in InventoryAdjustment.__table__.columns}
        assert "old_quantity" in cols
        assert "new_quantity" in cols

    def test_has_reference_movement_id(self):
        cols = {c.name for c in InventoryAdjustment.__table__.columns}
        assert "reference_movement_id" in cols

    def test_has_rejection_reason(self):
        cols = {c.name for c in InventoryAdjustment.__table__.columns}
        assert "rejection_reason" in cols

    def test_status_check_constraint_exists(self):
        table = cast(Table, InventoryAdjustment.__table__)
        constraints = {c.name for c in table.constraints}
        assert "ck_inv_adj_status" in constraints

    def test_movement_type_check_constraint_exists(self):
        table = cast(Table, InventoryAdjustment.__table__)
        constraints = {c.name for c in table.constraints}
        assert "ck_inv_adj_movement_type" in constraints


# ---------------------------------------------------------------------------
# Service: create_adjustment
# ---------------------------------------------------------------------------


class TestCreateAdjustment:
    def test_invalid_quantity_raises(self):
        m = _make_service()
        m.wh_repo.get_by_id_or_none.return_value = MagicMock(
            is_deleted=False, status="ACTIVE"
        )
        with pytest.raises(InvalidStockQuantityError):
            m.service.create_adjustment(
                company_id=uuid.uuid4(),
                product_id=uuid.uuid4(),
                warehouse_id=uuid.uuid4(),
                movement_type="ADJUSTMENT_IN",
                quantity=Decimal("0"),
            )

    def test_negative_quantity_raises(self):
        m = _make_service()
        m.wh_repo.get_by_id_or_none.return_value = MagicMock(
            is_deleted=False, status="ACTIVE"
        )
        with pytest.raises(InvalidStockQuantityError):
            m.service.create_adjustment(
                company_id=uuid.uuid4(),
                product_id=uuid.uuid4(),
                warehouse_id=uuid.uuid4(),
                movement_type="ADJUSTMENT_IN",
                quantity=Decimal("-5"),
            )

    def test_invalid_movement_type_raises(self):
        m = _make_service()
        m.wh_repo.get_by_id_or_none.return_value = MagicMock(
            is_deleted=False, status="ACTIVE"
        )
        with pytest.raises(ValueError):
            m.service.create_adjustment(
                company_id=uuid.uuid4(),
                product_id=uuid.uuid4(),
                warehouse_id=uuid.uuid4(),
                movement_type="OPENING",
                quantity=Decimal("10"),
            )

    def test_warehouse_not_found_raises(self):
        m = _make_service()
        m.wh_repo.get_by_id_or_none.return_value = None
        with pytest.raises(WarehouseNotFoundError):
            m.service.create_adjustment(
                company_id=uuid.uuid4(),
                product_id=uuid.uuid4(),
                warehouse_id=uuid.uuid4(),
                movement_type="ADJUSTMENT_IN",
                quantity=Decimal("10"),
            )

    def test_inactive_warehouse_raises(self):
        m = _make_service()
        m.wh_repo.get_by_id_or_none.return_value = MagicMock(
            is_deleted=False, status="INACTIVE"
        )
        with pytest.raises(WarehouseNotFoundError):
            m.service.create_adjustment(
                company_id=uuid.uuid4(),
                product_id=uuid.uuid4(),
                warehouse_id=uuid.uuid4(),
                movement_type="ADJUSTMENT_IN",
                quantity=Decimal("10"),
            )

    def test_create_sets_draft_status(self):
        m = _make_service()
        m.wh_repo.get_by_id_or_none.return_value = MagicMock(
            is_deleted=False, status="ACTIVE"
        )
        m.pos_repo.get_by_product_warehouse.return_value = None
        m.db.add = MagicMock()
        m.db.flush = MagicMock()

        result = m.service.create_adjustment(
            company_id=uuid.uuid4(),
            product_id=uuid.uuid4(),
            warehouse_id=uuid.uuid4(),
            movement_type="ADJUSTMENT_IN",
            quantity=Decimal("50"),
        )
        assert result.status == "DRAFT"
        assert result.version == 1

    def test_old_quantity_captured_from_position(self):
        m = _make_service()
        m.wh_repo.get_by_id_or_none.return_value = MagicMock(
            is_deleted=False, status="ACTIVE"
        )
        mock_pos = MagicMock()
        mock_pos.qty_on_hand = Decimal("75")
        m.pos_repo.get_by_product_warehouse.return_value = mock_pos
        m.db.add = MagicMock()
        m.db.flush = MagicMock()

        result = m.service.create_adjustment(
            company_id=uuid.uuid4(),
            product_id=uuid.uuid4(),
            warehouse_id=uuid.uuid4(),
            movement_type="ADJUSTMENT_OUT",
            quantity=Decimal("25"),
        )
        assert result.old_quantity is not None
        assert float(result.old_quantity) == pytest.approx(75.0)

    def test_old_quantity_zero_when_no_position(self):
        m = _make_service()
        m.wh_repo.get_by_id_or_none.return_value = MagicMock(
            is_deleted=False, status="ACTIVE"
        )
        m.pos_repo.get_by_product_warehouse.return_value = None
        m.db.add = MagicMock()
        m.db.flush = MagicMock()

        result = m.service.create_adjustment(
            company_id=uuid.uuid4(),
            product_id=uuid.uuid4(),
            warehouse_id=uuid.uuid4(),
            movement_type="ADJUSTMENT_IN",
            quantity=Decimal("20"),
        )
        assert result.old_quantity is not None
        assert float(result.old_quantity) == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# Service: submit_adjustment
# ---------------------------------------------------------------------------


class TestSubmitAdjustment:
    def test_submit_non_draft_raises(self):
        m = _make_service()
        adj = _make_adj(status="PENDING_APPROVAL")
        m.adj_repo.get_by_id_or_none.return_value = adj
        with pytest.raises(InvalidAdjustmentStateTransitionError):
            m.service.submit_adjustment(
                company_id=adj.company_id,
                adjustment_id=adj.id,
            )

    def test_submit_not_found_raises(self):
        m = _make_service()
        m.adj_repo.get_by_id_or_none.return_value = None
        with pytest.raises(AdjustmentNotFoundError):
            m.service.submit_adjustment(
                company_id=uuid.uuid4(),
                adjustment_id=uuid.uuid4(),
            )

    def test_submit_with_approval_flag_disabled_auto_approves(self):
        m = _make_service(approval_enabled=False)
        adj = _make_adj(status="DRAFT", version=1)
        m.adj_repo.get_by_id_or_none.return_value = adj
        # Mock ledger returning movement + position
        mock_movement = MagicMock()
        mock_movement.id = uuid.uuid4()
        mock_pos = MagicMock()
        mock_pos.qty_on_hand = Decimal("110")
        m.ledger.record_adjustment.return_value = (mock_movement, mock_pos)
        approved_adj = _make_adj(status="APPROVED", version=2)
        m.adj_repo.update_status.return_value = approved_adj

        result = m.service.submit_adjustment(
            company_id=adj.company_id,
            adjustment_id=adj.id,
        )
        assert result.status == "APPROVED"
        m.ledger.record_adjustment.assert_called_once()

    def test_submit_with_approval_flag_enabled_goes_pending(self):
        m = _make_service(approval_enabled=True)
        adj = _make_adj(status="DRAFT", version=1)
        m.adj_repo.get_by_id_or_none.return_value = adj
        pending_adj = _make_adj(status="PENDING_APPROVAL", version=2)
        m.adj_repo.update_status.return_value = pending_adj

        result = m.service.submit_adjustment(
            company_id=adj.company_id,
            adjustment_id=adj.id,
        )
        assert result.status == "PENDING_APPROVAL"
        m.ledger.record_adjustment.assert_not_called()


# ---------------------------------------------------------------------------
# Service: approve_adjustment
# ---------------------------------------------------------------------------


class TestApproveAdjustment:
    def test_approve_non_pending_raises(self):
        m = _make_service()
        adj = _make_adj(status="DRAFT")
        m.adj_repo.get_by_id_or_none.return_value = adj
        with pytest.raises(InvalidAdjustmentStateTransitionError):
            m.service.approve_adjustment(
                company_id=adj.company_id,
                adjustment_id=adj.id,
            )

    def test_self_approval_raises(self):
        actor = uuid.uuid4()
        m = _make_service()
        adj = _make_adj(status="PENDING_APPROVAL", submitted_by=str(actor))
        m.adj_repo.get_by_id_or_none.return_value = adj
        with pytest.raises(InvalidAdjustmentStateTransitionError):
            m.service.approve_adjustment(
                company_id=adj.company_id,
                adjustment_id=adj.id,
                actor_id=actor,
            )

    def test_approve_by_different_user_succeeds(self):
        submitter = uuid.uuid4()
        approver = uuid.uuid4()
        m = _make_service()
        adj = _make_adj(
            status="PENDING_APPROVAL", submitted_by=str(submitter), version=2
        )
        m.adj_repo.get_by_id_or_none.return_value = adj
        mock_movement = MagicMock()
        mock_movement.id = uuid.uuid4()
        mock_pos = MagicMock()
        mock_pos.qty_on_hand = Decimal("120")
        m.ledger.record_adjustment.return_value = (mock_movement, mock_pos)
        approved_adj = _make_adj(status="APPROVED", version=3)
        m.adj_repo.update_status.return_value = approved_adj

        result = m.service.approve_adjustment(
            company_id=adj.company_id,
            adjustment_id=adj.id,
            actor_id=approver,
        )
        assert result.status == "APPROVED"
        m.ledger.record_adjustment.assert_called_once()

    def test_approve_with_no_actor_id_allowed(self):
        """System-level approve (no actor) should succeed."""
        m = _make_service()
        adj = _make_adj(status="PENDING_APPROVAL", submitted_by=None, version=2)
        m.adj_repo.get_by_id_or_none.return_value = adj
        mock_movement = MagicMock()
        mock_movement.id = uuid.uuid4()
        mock_pos = MagicMock()
        mock_pos.qty_on_hand = Decimal("10")
        m.ledger.record_adjustment.return_value = (mock_movement, mock_pos)
        approved_adj = _make_adj(status="APPROVED", version=3)
        m.adj_repo.update_status.return_value = approved_adj

        result = m.service.approve_adjustment(
            company_id=adj.company_id,
            adjustment_id=adj.id,
            actor_id=None,
        )
        assert result.status == "APPROVED"


# ---------------------------------------------------------------------------
# Service: reject_adjustment
# ---------------------------------------------------------------------------


class TestRejectAdjustment:
    def test_reject_non_pending_raises(self):
        m = _make_service()
        adj = _make_adj(status="DRAFT")
        m.adj_repo.get_by_id_or_none.return_value = adj
        with pytest.raises(InvalidAdjustmentStateTransitionError):
            m.service.reject_adjustment(
                company_id=adj.company_id,
                adjustment_id=adj.id,
                rejection_reason="No reason",
            )

    def test_reject_approved_raises(self):
        m = _make_service()
        adj = _make_adj(status="APPROVED")
        m.adj_repo.get_by_id_or_none.return_value = adj
        with pytest.raises(InvalidAdjustmentStateTransitionError):
            m.service.reject_adjustment(
                company_id=adj.company_id,
                adjustment_id=adj.id,
                rejection_reason="Too late",
            )

    def test_reject_pending_succeeds(self):
        m = _make_service()
        adj = _make_adj(status="PENDING_APPROVAL", version=2)
        m.adj_repo.get_by_id_or_none.return_value = adj
        rejected_adj = _make_adj(status="REJECTED", version=3)
        m.adj_repo.update_status.return_value = rejected_adj

        result = m.service.reject_adjustment(
            company_id=adj.company_id,
            adjustment_id=adj.id,
            rejection_reason="Stock count incorrect",
        )
        assert result.status == "REJECTED"
        m.ledger.record_adjustment.assert_not_called()

    def test_reject_passes_reason_to_repo(self):
        m = _make_service()
        adj = _make_adj(status="PENDING_APPROVAL", version=2)
        m.adj_repo.get_by_id_or_none.return_value = adj
        m.adj_repo.update_status.return_value = _make_adj(status="REJECTED", version=3)

        m.service.reject_adjustment(
            company_id=adj.company_id,
            adjustment_id=adj.id,
            rejection_reason="Not authorised",
        )
        call_kwargs = m.adj_repo.update_status.call_args.kwargs
        assert call_kwargs["rejection_reason"] == "Not authorised"
        assert call_kwargs["new_status"] == "REJECTED"
