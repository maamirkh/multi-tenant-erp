"""AdjustmentService — inventory adjustment workflow with approval state machine.

Workflow (feature flag ``inventory.adjustment_approval``):

  Flag DISABLED (default):
    create  → DRAFT
    submit  → DRAFT → APPROVED  (immediate; calls StockLedgerService)

  Flag ENABLED:
    create  → DRAFT
    submit  → DRAFT → PENDING_APPROVAL
    approve → PENDING_APPROVAL → APPROVED  (calls StockLedgerService)
    reject  → PENDING_APPROVAL → REJECTED  (no stock change)

Business invariants enforced here:
  - quantity must be positive
  - warehouse must exist and be ACTIVE
  - approver ≠ submitter (self-approval forbidden)
  - optimistic lock prevents double-approval

Spec ref: specs/005-inventory-management/spec.md §15 / FR-IO-012
"""

from __future__ import annotations

import logging
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from modules.inventory.domain_events import (
    InventoryAdjustmentApproved,
    InventoryAdjustmentRejected,
    InventoryAdjustmentSubmitted,
)
from modules.inventory.events import get_event_bus
from modules.inventory.exceptions import (
    AdjustmentNotFoundError,
    InvalidAdjustmentStateTransitionError,
    InvalidStockQuantityError,
    WarehouseNotFoundError,
)
from modules.inventory.models.adjustment import InventoryAdjustment
from modules.inventory.models.stock import StockMovement, StockPosition
from modules.inventory.repositories.adjustment_repository import AdjustmentRepository
from modules.inventory.repositories.stock_repository import StockPositionRepository
from modules.inventory.repositories.warehouse_repository import WarehouseRepository
from modules.inventory.services.feature_flag_service import FeatureFlagService
from modules.inventory.services.stock_service import StockLedgerService

logger = logging.getLogger(__name__)

_APPROVAL_FLAG = "inventory.adjustment_approval"


class AdjustmentService:
    """Orchestrates the full inventory adjustment lifecycle.

    All public methods flush but do NOT commit — the FastAPI dependency
    (via the session context manager) owns the transaction boundary.
    """

    def __init__(
        self,
        db: Session,
        adjustment_repo: AdjustmentRepository,
        stock_ledger: StockLedgerService,
        position_repo: StockPositionRepository,
        warehouse_repo: WarehouseRepository,
        flag_service: FeatureFlagService,
    ) -> None:
        self._db = db
        self._adj_repo = adjustment_repo
        self._ledger = stock_ledger
        self._pos_repo = position_repo
        self._wh_repo = warehouse_repo
        self._flags = flag_service

    # ------------------------------------------------------------------
    # Create (T175)
    # ------------------------------------------------------------------

    def create_adjustment(
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
        reason_code_id: UUID | None = None,
        notes: str | None = None,
        actor_id: UUID | None = None,
    ) -> InventoryAdjustment:
        """Create a new adjustment in DRAFT state.

        Validates:
        - quantity > 0
        - warehouse is ACTIVE

        Captures ``old_quantity`` from the current StockPosition (0 if no position).
        """
        if quantity <= 0:
            raise InvalidStockQuantityError("Adjustment quantity must be positive.")

        if movement_type not in {"ADJUSTMENT_IN", "ADJUSTMENT_OUT"}:
            raise ValueError(
                f"movement_type must be ADJUSTMENT_IN or ADJUSTMENT_OUT, got: {movement_type}"
            )

        self._validate_warehouse(company_id=company_id, warehouse_id=warehouse_id)

        # Capture current stock position for audit trail
        old_pos = self._pos_repo.get_by_product_warehouse(
            company_id=company_id,
            product_id=product_id,
            warehouse_id=warehouse_id,
            variant_id=variant_id,
        )
        old_quantity = Decimal(str(old_pos.qty_on_hand)) if old_pos else Decimal("0")

        adjustment = InventoryAdjustment(
            id=uuid4(),
            company_id=company_id,
            product_id=str(product_id),
            variant_id=str(variant_id) if variant_id else None,
            warehouse_id=str(warehouse_id),
            reason_code_id=str(reason_code_id) if reason_code_id else None,
            movement_type=movement_type,
            quantity=quantity,
            unit_cost=unit_cost,
            currency_code=currency_code,
            notes=notes,
            status="DRAFT",
            version=1,
            old_quantity=old_quantity,
            created_by=actor_id,
        )
        self._db.add(adjustment)
        self._db.flush()
        # Missing-commit defect fixed during Epic 1-8 live verification
        # (2026-08-14) — see warehouse_service.py::create_warehouse's comment
        # for the full root-cause explanation.
        self._db.commit()

        logger.info(
            "Adjustment created: id=%s company=%s product=%s wh=%s qty=%s type=%s",
            adjustment.id,
            company_id,
            product_id,
            warehouse_id,
            quantity,
            movement_type,
        )
        return adjustment

    # ------------------------------------------------------------------
    # Submit (T176)
    # ------------------------------------------------------------------

    def submit_adjustment(
        self,
        *,
        company_id: UUID,
        adjustment_id: UUID,
        actor_id: UUID | None = None,
    ) -> InventoryAdjustment:
        """Submit a DRAFT adjustment.

        If ``inventory.adjustment_approval`` flag is ENABLED → PENDING_APPROVAL.
        If flag is DISABLED (default) → APPROVED immediately + call stock ledger.
        """
        adj = self._get_or_raise(company_id=company_id, adjustment_id=adjustment_id)

        if adj.status != "DRAFT":
            raise InvalidAdjustmentStateTransitionError(
                f"Cannot submit adjustment in status '{adj.status}'. Expected DRAFT."
            )

        approval_required = self._flags.is_enabled(
            company_id=company_id, flag_key=_APPROVAL_FLAG
        )

        if approval_required:
            result = self._adj_repo.update_status(
                adjustment_id=adjustment_id,
                company_id=company_id,
                expected_version=adj.version,
                new_status="PENDING_APPROVAL",
                submitted_by=str(actor_id) if actor_id else None,
            )
            # Missing-commit defect fixed during Epic 1-8 live verification
            # (2026-08-14) — see warehouse_service.py::create_warehouse's
            # comment for the full root-cause explanation.
            self._db.commit()
            get_event_bus().publish(
                InventoryAdjustmentSubmitted(
                    aggregate_id=adjustment_id,
                    company_id=company_id,
                    adjustment_id=str(adjustment_id),
                    product_id=str(adj.product_id),
                    warehouse_id=str(adj.warehouse_id),
                    qty_delta=str(adj.quantity),
                )
            )
            return result
        else:
            # Bypass approval — approve immediately
            movement, pos = self._apply_to_ledger(adj=adj, actor_id=actor_id)
            new_qty = Decimal(str(pos.qty_on_hand))
            result = self._adj_repo.update_status(
                adjustment_id=adjustment_id,
                company_id=company_id,
                expected_version=adj.version,
                new_status="APPROVED",
                submitted_by=str(actor_id) if actor_id else None,
                approved_by=str(actor_id) if actor_id else None,
                new_quantity=new_qty,
                reference_movement_id=str(movement.id),
            )
            # Missing-commit defect fixed during Epic 1-8 live verification
            # (2026-08-14) — see warehouse_service.py::create_warehouse's
            # comment for the full root-cause explanation.
            self._db.commit()
            get_event_bus().publish(
                InventoryAdjustmentApproved(
                    aggregate_id=adjustment_id,
                    company_id=company_id,
                    adjustment_id=str(adjustment_id),
                    approved_by=str(actor_id) if actor_id else None,
                )
            )
            logger.info(
                "Adjustment auto-approved (bypass): id=%s movement=%s",
                adjustment_id,
                movement.id,
            )
            return result

    # ------------------------------------------------------------------
    # Approve (T177)
    # ------------------------------------------------------------------

    def approve_adjustment(
        self,
        *,
        company_id: UUID,
        adjustment_id: UUID,
        actor_id: UUID | None = None,
    ) -> InventoryAdjustment:
        """Approve a PENDING_APPROVAL adjustment.

        Invariant: approver must differ from submitter.
        On success: calls StockLedgerService, records new_quantity, links movement.
        """
        adj = self._get_or_raise(company_id=company_id, adjustment_id=adjustment_id)

        if adj.status != "PENDING_APPROVAL":
            raise InvalidAdjustmentStateTransitionError(
                f"Cannot approve adjustment in status '{adj.status}'. Expected PENDING_APPROVAL."
            )

        # Self-approval guard
        if actor_id and adj.submitted_by and str(actor_id) == adj.submitted_by:
            raise InvalidAdjustmentStateTransitionError(
                "Approver must differ from the submitter — self-approval is not permitted."
            )

        movement, pos = self._apply_to_ledger(adj=adj, actor_id=actor_id)
        new_qty = Decimal(str(pos.qty_on_hand))

        result = self._adj_repo.update_status(
            adjustment_id=adjustment_id,
            company_id=company_id,
            expected_version=adj.version,
            new_status="APPROVED",
            approved_by=str(actor_id) if actor_id else None,
            new_quantity=new_qty,
            reference_movement_id=str(movement.id),
        )
        get_event_bus().publish(
            InventoryAdjustmentApproved(
                aggregate_id=adjustment_id,
                company_id=company_id,
                adjustment_id=str(adjustment_id),
                approved_by=str(actor_id) if actor_id else None,
            )
        )
        logger.info(
            "Adjustment approved: id=%s approver=%s movement=%s",
            adjustment_id,
            actor_id,
            movement.id,
        )
        return result

    # ------------------------------------------------------------------
    # Reject (T178)
    # ------------------------------------------------------------------

    def reject_adjustment(
        self,
        *,
        company_id: UUID,
        adjustment_id: UUID,
        rejection_reason: str,
        actor_id: UUID | None = None,
    ) -> InventoryAdjustment:
        """Reject a PENDING_APPROVAL adjustment.  Stock is NOT modified.

        Raises InvalidAdjustmentStateTransitionError if not in PENDING_APPROVAL.
        """
        adj = self._get_or_raise(company_id=company_id, adjustment_id=adjustment_id)

        if adj.status != "PENDING_APPROVAL":
            raise InvalidAdjustmentStateTransitionError(
                f"Cannot reject adjustment in status '{adj.status}'. Expected PENDING_APPROVAL."
            )

        result = self._adj_repo.update_status(
            adjustment_id=adjustment_id,
            company_id=company_id,
            expected_version=adj.version,
            new_status="REJECTED",
            rejected_by=str(actor_id) if actor_id else None,
            rejection_reason=rejection_reason,
        )
        get_event_bus().publish(
            InventoryAdjustmentRejected(
                aggregate_id=adjustment_id,
                company_id=company_id,
                adjustment_id=str(adjustment_id),
                rejected_by=str(actor_id) if actor_id else None,
                reason=rejection_reason,
            )
        )
        logger.info(
            "Adjustment rejected: id=%s rejector=%s reason=%s",
            adjustment_id,
            actor_id,
            rejection_reason,
        )
        return result

    # ------------------------------------------------------------------
    # Read helpers
    # ------------------------------------------------------------------

    def get_adjustment(
        self, *, company_id: UUID, adjustment_id: UUID
    ) -> InventoryAdjustment:
        return self._get_or_raise(company_id=company_id, adjustment_id=adjustment_id)

    def list_adjustments(
        self,
        *,
        company_id: UUID,
        status: str | None = None,
        product_id: UUID | None = None,
        warehouse_id: UUID | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[InventoryAdjustment]:
        return self._adj_repo.list_for_company(
            company_id=company_id,
            status=status,
            product_id=product_id,
            warehouse_id=warehouse_id,
            limit=limit,
            offset=offset,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_or_raise(
        self, *, company_id: UUID, adjustment_id: UUID
    ) -> InventoryAdjustment:
        adj = self._adj_repo.get_by_id_or_none(company_id=company_id, id=adjustment_id)
        if adj is None:
            raise AdjustmentNotFoundError(
                f"Adjustment {adjustment_id} not found for company {company_id}"
            )
        return adj

    def _validate_warehouse(self, *, company_id: UUID, warehouse_id: UUID) -> None:
        wh = self._wh_repo.get_by_id_or_none(company_id=company_id, id=warehouse_id)
        if not wh or wh.is_deleted:
            raise WarehouseNotFoundError(
                f"Warehouse {warehouse_id} not found for company {company_id}"
            )
        if wh.status != "ACTIVE":
            raise WarehouseNotFoundError(
                f"Warehouse {warehouse_id} is not ACTIVE (status={wh.status})"
            )

    def _apply_to_ledger(
        self,
        *,
        adj: InventoryAdjustment,
        actor_id: UUID | None,
    ) -> tuple[StockMovement, StockPosition]:
        """Call StockLedgerService.record_adjustment and return (movement, position)."""
        from uuid import UUID as _UUID

        return self._ledger.record_adjustment(
            company_id=(
                adj.company_id
                if isinstance(adj.company_id, _UUID)
                else _UUID(str(adj.company_id))
            ),
            product_id=_UUID(adj.product_id),
            warehouse_id=_UUID(adj.warehouse_id),
            movement_type=adj.movement_type,
            quantity=Decimal(str(adj.quantity)),
            unit_cost=(
                Decimal(str(adj.unit_cost)) if adj.unit_cost is not None else None
            ),
            currency_code=adj.currency_code,
            variant_id=_UUID(adj.variant_id) if adj.variant_id else None,
            reference_type="ADJUSTMENT",
            reference_id=adj.id if isinstance(adj.id, _UUID) else _UUID(str(adj.id)),
            notes=adj.notes,
            actor_id=actor_id,
        )
