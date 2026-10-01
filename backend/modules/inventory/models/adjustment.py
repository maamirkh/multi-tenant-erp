"""InventoryAdjustment ORM model — Phase 6 Stock Operations.

State machine:
  DRAFT → PENDING_APPROVAL  (when approval flag is enabled)
  DRAFT → APPROVED           (when approval flag is disabled — bypass)
  PENDING_APPROVAL → APPROVED
  PENDING_APPROVAL → REJECTED

Invariants (enforced in service layer):
  - quantity > 0
  - submitter_id ≠ approver_id  (cannot self-approve)
  - status transitions follow the state machine above
  - optimistic locking via ``version`` (incremented on each transition)

Spec ref: specs/005-inventory-management/spec.md §15 / FR-IO-012
Data model: specs/005-inventory-management/data-model.md §adjustment
"""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    Index,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from core.database.models.tenant_base import TenantBaseModel

_ADJUSTMENT_STATUSES = "'DRAFT', 'PENDING_APPROVAL', 'APPROVED', 'REJECTED'"
_MOVEMENT_TYPES = "'ADJUSTMENT_IN', 'ADJUSTMENT_OUT'"


class InventoryAdjustment(TenantBaseModel):
    """Stock adjustment aggregate root with optional approval workflow.

    One row is created per adjustment request (DRAFT).  On submit/approve the
    service layer calls ``StockLedgerService.record_adjustment`` which writes
    the immutable ``StockMovement`` and updates the ``StockPosition``.

    The ``version`` column implements optimistic locking so that two concurrent
    approve operations cannot both succeed.
    """

    __tablename__ = "inventory_adjustments"
    __table_args__ = (
        Index("ix_inv_adj_company_id", "company_id"),
        Index("ix_inv_adj_product_id", "product_id"),
        Index("ix_inv_adj_warehouse_id", "warehouse_id"),
        Index("ix_inv_adj_status", "status"),
        CheckConstraint(
            f"status IN ({_ADJUSTMENT_STATUSES})",
            name="ck_inv_adj_status",
        ),
        CheckConstraint(
            f"movement_type IN ({_MOVEMENT_TYPES})",
            name="ck_inv_adj_movement_type",
        ),
        {
            "comment": "Inventory adjustment aggregate — approval workflow with optimistic lock"
        },
    )

    # ── Core product / warehouse identity ────────────────────────────────────

    product_id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        nullable=False,
        doc="FK to the product being adjusted (no cascade delete guard needed — service prevents)",
    )

    variant_id: Mapped[str | None] = mapped_column(
        PG_UUID(as_uuid=False),
        nullable=True,
        doc="FK to the product variant (null = base product)",
    )

    warehouse_id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        nullable=False,
        doc="FK to the target warehouse",
    )

    reason_code_id: Mapped[str | None] = mapped_column(
        PG_UUID(as_uuid=False),
        nullable=True,
        doc="FK to inventory_reason_codes (optional, but strongly recommended)",
    )

    # ── Adjustment details ───────────────────────────────────────────────────

    movement_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        doc="ADJUSTMENT_IN (stock increase) or ADJUSTMENT_OUT (stock decrease)",
    )

    quantity: Mapped[Decimal] = mapped_column(
        Numeric(18, 4),
        nullable=False,
        doc="Adjustment quantity — always positive; direction derived from movement_type",
    )

    unit_cost: Mapped[Decimal | None] = mapped_column(
        Numeric(18, 4),
        nullable=True,
        doc="Unit cost at time of adjustment (used for WAC recalculation on IN)",
    )

    currency_code: Mapped[str | None] = mapped_column(
        String(3),
        nullable=True,
        doc="ISO 4217 currency code for unit_cost",
    )

    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        doc="Justification / notes for this adjustment",
    )

    # ── State machine ────────────────────────────────────────────────────────

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default="DRAFT",
        doc="Workflow state: DRAFT | PENDING_APPROVAL | APPROVED | REJECTED",
    )

    version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="1",
        doc="Optimistic lock counter — incremented on every status transition",
    )

    # ── Stock snapshot ───────────────────────────────────────────────────────

    old_quantity: Mapped[Decimal | None] = mapped_column(
        Numeric(18, 4),
        nullable=True,
        doc="qty_on_hand before this adjustment (captured at creation time)",
    )

    new_quantity: Mapped[Decimal | None] = mapped_column(
        Numeric(18, 4),
        nullable=True,
        doc="qty_on_hand after approval (null until the adjustment is APPROVED)",
    )

    # ── Workflow actors ──────────────────────────────────────────────────────

    submitted_by: Mapped[str | None] = mapped_column(
        PG_UUID(as_uuid=False),
        nullable=True,
        doc="User who submitted the adjustment for approval",
    )

    approved_by: Mapped[str | None] = mapped_column(
        PG_UUID(as_uuid=False),
        nullable=True,
        doc="User who approved — must differ from submitted_by (self-approval forbidden)",
    )

    rejected_by: Mapped[str | None] = mapped_column(
        PG_UUID(as_uuid=False),
        nullable=True,
        doc="User who rejected the adjustment",
    )

    rejection_reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        doc="Mandatory rejection reason when status transitions to REJECTED",
    )

    # ── Ledger link ──────────────────────────────────────────────────────────

    reference_movement_id: Mapped[str | None] = mapped_column(
        PG_UUID(as_uuid=False),
        nullable=True,
        doc="FK to inventory_stock_movements created when this adjustment was APPROVED",
    )
