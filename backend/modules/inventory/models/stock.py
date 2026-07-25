"""Stock ORM models — StockPosition, StockMovement, FIFOCostLayer, InventorySnapshot.

Phase 5 of Epic 5: Inventory Core & Stock Ledger.

Design decisions:
  - StockPosition: mutable aggregate tracking current quantities per product+warehouse
  - StockMovement: IMMUTABLE ledger — INSERT only, never UPDATE or DELETE
  - FIFOCostLayer: cost queue for FIFO valuation (enabled via feature flag)
  - InventorySnapshot: point-in-time capture of all positions (immutable once COMPLETED)

Spec ref: specs/005-inventory-management/spec.md §15
Data model: specs/005-inventory-management/data-model.md §stock
"""

from __future__ import annotations

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from core.database.models.tenant_base import TenantBaseModel

_MOVEMENT_TYPES = (
    "'OPENING', 'PURCHASE_RECEIPT', 'SALES_ISSUE', 'ADJUSTMENT_IN', 'ADJUSTMENT_OUT', "
    "'TRANSFER_IN', 'TRANSFER_OUT', 'RETURN_IN', 'RETURN_OUT', 'DAMAGE', 'WRITE_OFF', 'SNAPSHOT'"
)
_DIRECTION = "'IN', 'OUT'"
_SNAPSHOT_STATUSES = "'PENDING', 'COMPLETED', 'FAILED'"


# =============================================================================
# StockPosition — mutable aggregate root
# =============================================================================


class StockPosition(TenantBaseModel):
    """Real-time stock position for a product+variant+warehouse combination.

    One row per (company_id, product_id, variant_id, warehouse_id).
    Quantities track: on_hand, reserved, damaged.
    available = on_hand − reserved − damaged.

    Invariants (enforced in service):
    - qty_on_hand ≥ 0 (under STRICT negative stock policy)
    - qty_reserved ≤ qty_on_hand
    - qty_damaged ≤ qty_on_hand
    """

    __tablename__ = "inventory_stock_positions"
    __table_args__ = (
        UniqueConstraint(
            "company_id",
            "product_id",
            "warehouse_id",
            "variant_id",
            name="uq_inv_stock_pos_product_wh",
        ),
        Index("ix_inv_stock_pos_company_id", "company_id"),
        Index("ix_inv_stock_pos_product_id", "product_id"),
        Index("ix_inv_stock_pos_warehouse_id", "warehouse_id"),
        {
            "comment": "Real-time stock position per product + warehouse, scoped per company"
        },
    )

    product_id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        ForeignKey("inventory_products.id", ondelete="RESTRICT"),
        nullable=False,
        doc="FK to the product",
    )

    variant_id: Mapped[str | None] = mapped_column(
        PG_UUID(as_uuid=False),
        ForeignKey("inventory_product_variants.id", ondelete="RESTRICT"),
        nullable=True,
        doc="FK to the variant (null = base product, no variant)",
    )

    warehouse_id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        ForeignKey("inventory_warehouses.id", ondelete="RESTRICT"),
        nullable=False,
        doc="FK to the warehouse holding this stock",
    )

    # Quantities (stored as Numeric for precision; service validates invariants)
    qty_on_hand: Mapped[float] = mapped_column(
        Numeric(18, 4),
        nullable=False,
        server_default="0",
        doc="Total quantity physically on hand (including reserved and damaged)",
    )

    qty_reserved: Mapped[float] = mapped_column(
        Numeric(18, 4),
        nullable=False,
        server_default="0",
        doc="Quantity reserved for pending sales orders",
    )

    qty_damaged: Mapped[float] = mapped_column(
        Numeric(18, 4),
        nullable=False,
        server_default="0",
        doc="Quantity identified as damaged",
    )

    # Cost (WAC updated on each stock-in movement)
    unit_cost: Mapped[float | None] = mapped_column(
        Numeric(18, 4),
        nullable=True,
        doc="Current weighted-average or FIFO unit cost",
    )

    currency_code: Mapped[str | None] = mapped_column(
        String(3),
        nullable=True,
        doc="ISO 4217 currency code for unit_cost (e.g. 'AED', 'USD')",
    )

    # Stock level thresholds
    safety_stock: Mapped[float] = mapped_column(
        Numeric(18, 4),
        nullable=False,
        server_default="0",
        doc="Safety stock level — alert when qty_on_hand falls below this",
    )

    minimum_stock: Mapped[float] = mapped_column(
        Numeric(18, 4),
        nullable=False,
        server_default="0",
        doc="Minimum stock level",
    )

    maximum_stock: Mapped[float | None] = mapped_column(
        Numeric(18, 4),
        nullable=True,
        doc="Maximum stock level (optional cap)",
    )

    reorder_level: Mapped[float] = mapped_column(
        Numeric(18, 4),
        nullable=False,
        server_default="0",
        doc="Trigger a reorder when qty_on_hand falls to this level",
    )


# =============================================================================
# StockMovement — immutable stock ledger entry
# =============================================================================


class StockMovement(TenantBaseModel):
    """Immutable stock ledger entry.

    CRITICAL: This entity must NEVER be updated or deleted.
    The repository exposes only INSERT operations.
    Every stock change is recorded as a new movement.

    movement_type values:
        OPENING           — Initial stock entry
        PURCHASE_RECEIPT  — Stock received from purchase order
        SALES_ISSUE       — Stock issued for a sale
        ADJUSTMENT_IN     — Manual positive adjustment
        ADJUSTMENT_OUT    — Manual negative adjustment
        TRANSFER_IN       — Stock received from warehouse transfer
        TRANSFER_OUT      — Stock sent to warehouse transfer
        RETURN_IN         — Customer return (stock back in)
        RETURN_OUT        — Return to supplier (stock back out)
        DAMAGE            — Stock written off as damaged
        WRITE_OFF         — Stock written off (expired, lost)
        SNAPSHOT          — Virtual entry for snapshot baseline

    direction: IN (increases qty_on_hand) | OUT (decreases qty_on_hand)
    """

    __tablename__ = "inventory_stock_movements"
    __table_args__ = (
        Index("ix_inv_stock_mov_company_id", "company_id"),
        Index("ix_inv_stock_mov_product_id", "product_id"),
        Index("ix_inv_stock_mov_warehouse_id", "warehouse_id"),
        Index("ix_inv_stock_mov_performed_at", "performed_at"),
        CheckConstraint(
            f"movement_type IN ({_MOVEMENT_TYPES})",
            name="ck_inv_stock_mov_type",
        ),
        CheckConstraint(
            f"direction IN ({_DIRECTION})",
            name="ck_inv_stock_mov_direction",
        ),
        {"comment": "Immutable stock ledger — INSERT only, never UPDATE or DELETE"},
    )

    product_id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        ForeignKey("inventory_products.id", ondelete="RESTRICT"),
        nullable=False,
    )

    variant_id: Mapped[str | None] = mapped_column(
        PG_UUID(as_uuid=False),
        nullable=True,
        doc="FK to variant (null = base product)",
    )

    warehouse_id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        ForeignKey("inventory_warehouses.id", ondelete="RESTRICT"),
        nullable=False,
    )

    movement_type: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        doc="Type of stock movement",
    )

    direction: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
        doc="IN = stock increases; OUT = stock decreases",
    )

    quantity: Mapped[float] = mapped_column(
        Numeric(18, 4),
        nullable=False,
        doc="Quantity moved (always positive)",
    )

    unit_cost: Mapped[float | None] = mapped_column(
        Numeric(18, 4),
        nullable=True,
        doc="Unit cost at time of movement",
    )

    currency_code: Mapped[str | None] = mapped_column(
        String(3),
        nullable=True,
    )

    total_cost: Mapped[float | None] = mapped_column(
        Numeric(18, 4),
        nullable=True,
        doc="quantity × unit_cost at time of movement",
    )

    reference_type: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        doc="Type of source document (ADJUSTMENT, TRANSFER, PURCHASE_ORDER, SALE_ORDER)",
    )

    reference_id: Mapped[str | None] = mapped_column(
        PG_UUID(as_uuid=False),
        nullable=True,
        doc="UUID of the source document",
    )

    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    performed_at: Mapped[object] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        doc="When the movement occurred (may differ from created_at for backdating)",
    )


# =============================================================================
# FIFOCostLayer — cost queue for FIFO valuation
# =============================================================================


class FIFOCostLayer(TenantBaseModel):
    """A batch of stock received at a specific unit cost (FIFO queue entry).

    On stock-in: push a new layer with quantity and unit_cost.
    On stock-out: pop from the oldest layer(s) until quantity consumed.
    remaining_qty tracks unconsumed quantity in each layer.

    Note: FIFO costing is enabled via feature flag. WAC is the default.
    """

    __tablename__ = "inventory_fifo_cost_layers"
    __table_args__ = (
        Index("ix_inv_fifo_layers_product_wh", "product_id", "warehouse_id"),
        Index("ix_inv_fifo_layers_company_id", "company_id"),
        {
            "comment": "FIFO cost queue — ordered by created_at to implement FIFO valuation"
        },
    )

    product_id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        ForeignKey("inventory_products.id", ondelete="RESTRICT"),
        nullable=False,
    )

    variant_id: Mapped[str | None] = mapped_column(
        PG_UUID(as_uuid=False),
        nullable=True,
    )

    warehouse_id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        ForeignKey("inventory_warehouses.id", ondelete="RESTRICT"),
        nullable=False,
    )

    remaining_qty: Mapped[float] = mapped_column(
        Numeric(18, 4),
        nullable=False,
        doc="Remaining unconsumed quantity in this cost layer",
    )

    unit_cost: Mapped[float] = mapped_column(
        Numeric(18, 4),
        nullable=False,
        doc="Unit cost for this batch",
    )

    movement_id: Mapped[str | None] = mapped_column(
        PG_UUID(as_uuid=False),
        nullable=True,
        doc="FK to the stock_movement that created this layer",
    )


# =============================================================================
# InventorySnapshot / InventorySnapshotLine — point-in-time capture
# =============================================================================


class InventorySnapshot(TenantBaseModel):
    """Point-in-time capture of all stock positions.

    Immutable once status = COMPLETED. Used for inventory valuation,
    period-end reporting, and audit.
    """

    __tablename__ = "inventory_snapshots"
    __table_args__ = (
        Index("ix_inv_snapshots_company_id", "company_id"),
        CheckConstraint(
            f"status IN ({_SNAPSHOT_STATUSES})",
            name="ck_inv_snapshots_status",
        ),
        {"comment": "Point-in-time inventory snapshot headers"},
    )

    snapshot_name: Mapped[str | None] = mapped_column(
        String(200),
        nullable=True,
        doc="Optional human-readable snapshot name",
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default="PENDING",
        doc="PENDING | COMPLETED | FAILED",
    )

    total_products: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="0",
        doc="Number of products in this snapshot",
    )

    total_warehouses: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="0",
        doc="Number of warehouses in this snapshot",
    )


class InventorySnapshotLine(TenantBaseModel):
    """Single line in an inventory snapshot (one per product+warehouse).

    Immutable: created once, never updated.
    """

    __tablename__ = "inventory_snapshot_lines"
    __table_args__ = (
        Index("ix_inv_snapshot_lines_snapshot_id", "snapshot_id"),
        Index("ix_inv_snapshot_lines_company_id", "company_id"),
        {"comment": "Individual stock position lines within an inventory snapshot"},
    )

    snapshot_id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        ForeignKey("inventory_snapshots.id", ondelete="CASCADE"),
        nullable=False,
    )

    product_id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        nullable=False,
    )

    variant_id: Mapped[str | None] = mapped_column(
        PG_UUID(as_uuid=False),
        nullable=True,
    )

    warehouse_id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        nullable=False,
    )

    qty_on_hand: Mapped[float] = mapped_column(
        Numeric(18, 4), nullable=False, server_default="0"
    )
    qty_reserved: Mapped[float] = mapped_column(
        Numeric(18, 4), nullable=False, server_default="0"
    )
    qty_damaged: Mapped[float] = mapped_column(
        Numeric(18, 4), nullable=False, server_default="0"
    )

    unit_cost: Mapped[float | None] = mapped_column(Numeric(18, 4), nullable=True)
    currency_code: Mapped[str | None] = mapped_column(String(3), nullable=True)
