"""StockTransfer + StockTransferLine ORM models — Phase 7 Stock Operations.

State machine (StockTransfer):
  DRAFT      → IN_TRANSIT   (dispatch — creates TRANSFER_OUT per line at source)
  IN_TRANSIT → COMPLETED    (receive  — creates TRANSFER_IN per line at destination)
  DRAFT      → CANCELLED    (no stock change)
  IN_TRANSIT → CANCELLED    (reversal TRANSFER_IN at source to restore stock)

Invariants (enforced in service layer):
  - source_warehouse_id ≠ destination_warehouse_id
  - at least one line required
  - quantity per line must be positive
  - optimistic locking via ``version`` (incremented on each transition)

Spec ref: specs/005-inventory-management/spec.md §16 / FR-IO-013
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
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.database.models.tenant_base import TenantBaseModel

_TRANSFER_STATUSES = "'DRAFT', 'IN_TRANSIT', 'COMPLETED', 'CANCELLED'"


class StockTransfer(TenantBaseModel):
    """Two-step warehouse transfer aggregate root.

    A transfer begins as DRAFT.  On dispatch the service creates TRANSFER_OUT
    StockMovements at the source warehouse (reducing source stock) and
    transitions the transfer to IN_TRANSIT.  On receipt the service creates
    TRANSFER_IN StockMovements at the destination warehouse (increasing
    destination stock) and marks the transfer COMPLETED.

    Cancellation from IN_TRANSIT creates a reversal TRANSFER_IN at the source
    to restore the stock that was reduced on dispatch.

    The ``version`` column implements optimistic locking so that two concurrent
    state transitions cannot both succeed.
    """

    __tablename__ = "inventory_stock_transfers"
    __table_args__ = (
        CheckConstraint(
            f"status IN ({_TRANSFER_STATUSES})",
            name="ck_inv_transfer_status",
        ),
        Index("ix_inv_transfer_company_id", "company_id"),
        Index("ix_inv_transfer_source_wh", "source_warehouse_id"),
        Index("ix_inv_transfer_dest_wh", "destination_warehouse_id"),
        Index("ix_inv_transfer_status", "status"),
        {"comment": "Inter-warehouse stock transfer header, scoped per company"},
    )

    # -- State --
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default="DRAFT",
        doc="Transfer lifecycle status",
    )

    version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="1",
        doc="Optimistic lock counter — incremented on every status transition",
    )

    # -- Warehouses --
    source_warehouse_id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        ForeignKey("inventory_warehouses.id", ondelete="RESTRICT"),
        nullable=False,
        doc="Warehouse from which stock is dispatched",
    )

    destination_warehouse_id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        ForeignKey("inventory_warehouses.id", ondelete="RESTRICT"),
        nullable=False,
        doc="Warehouse to which stock is received",
    )

    # -- Optional metadata --
    reference_no: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        doc="External reference number (e.g. GRN or PO number)",
    )

    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        doc="Free-text notes or reason for the transfer",
    )

    # -- Audit timestamps for each lifecycle event --
    dispatched_at: Mapped[object | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        doc="UTC timestamp when the transfer was dispatched",
    )

    received_at: Mapped[object | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        doc="UTC timestamp when the transfer was received",
    )

    cancelled_at: Mapped[object | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        doc="UTC timestamp when the transfer was cancelled",
    )

    cancelled_reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        doc="Mandatory reason when status = CANCELLED",
    )

    # -- Lines relationship --
    lines: Mapped[list[StockTransferLine]] = relationship(
        "StockTransferLine",
        back_populates="transfer",
        cascade="all, delete-orphan",
        lazy="select",
    )


class StockTransferLine(TenantBaseModel):
    """One line in a StockTransfer — one product+warehouse+quantity combination.

    company_id on each line mirrors the parent transfer's company_id to allow
    direct queries without always joining to the header.

    StockMovement IDs are recorded here once the movements are created so that
    there is a full audit trail linking line → ledger entry.
    """

    __tablename__ = "inventory_stock_transfer_lines"
    __table_args__ = (
        Index("ix_inv_trf_line_transfer_id", "transfer_id"),
        Index("ix_inv_trf_line_company_id", "company_id"),
        Index("ix_inv_trf_line_product_id", "product_id"),
        {"comment": "Line items for inter-warehouse stock transfers"},
    )

    # -- Parent --
    transfer_id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        ForeignKey("inventory_stock_transfers.id", ondelete="CASCADE"),
        nullable=False,
        doc="FK to the parent StockTransfer",
    )

    transfer: Mapped[StockTransfer] = relationship(
        "StockTransfer",
        back_populates="lines",
    )

    # -- Product identity --
    product_id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        ForeignKey("inventory_products.id", ondelete="RESTRICT"),
        nullable=False,
        doc="FK to the product being transferred",
    )

    variant_id: Mapped[str | None] = mapped_column(
        PG_UUID(as_uuid=False),
        ForeignKey("inventory_product_variants.id", ondelete="RESTRICT"),
        nullable=True,
        doc="FK to the variant (null = base product, no variant)",
    )

    # -- Quantity --
    quantity: Mapped[float] = mapped_column(
        Numeric(18, 4),
        nullable=False,
        doc="Quantity to transfer (must be positive)",
    )

    unit_cost: Mapped[float | None] = mapped_column(
        Numeric(18, 4),
        nullable=True,
        doc="Unit cost at the time of transfer (optional)",
    )

    currency_code: Mapped[str | None] = mapped_column(
        String(3),
        nullable=True,
        doc="ISO 4217 currency code for unit_cost",
    )

    # -- Movement references (populated after dispatch/receive) --
    source_movement_id: Mapped[str | None] = mapped_column(
        PG_UUID(as_uuid=False),
        nullable=True,
        doc="FK to the TRANSFER_OUT StockMovement created on dispatch",
    )

    destination_movement_id: Mapped[str | None] = mapped_column(
        PG_UUID(as_uuid=False),
        nullable=True,
        doc="FK to the TRANSFER_IN StockMovement created on receive",
    )

    reversal_movement_id: Mapped[str | None] = mapped_column(
        PG_UUID(as_uuid=False),
        nullable=True,
        doc="FK to the reversal TRANSFER_IN StockMovement created on IN_TRANSIT → CANCELLED",
    )
