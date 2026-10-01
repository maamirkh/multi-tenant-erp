"""ReorderRule, LowStockAlert, and ReorderSuggestion ORM models — Phase 8.

State machine (LowStockAlert):
  OPEN → ACKNOWLEDGED → RESOLVED
  OPEN → RESOLVED          (auto-resolve on restock)

Alert types:
  OUT_OF_STOCK       — qty_on_hand == 0
  SAFETY_STOCK_BREACH — qty_on_hand < safety_stock
  LOW_STOCK          — qty_on_hand <= reorder_level
  OVERSTOCK          — qty_on_hand > maximum_stock  (gated by feature flag)

Deduplication invariant:
  Only one OPEN alert of the same alert_type per (company_id, product_id,
  warehouse_id) may exist at a time — enforced by a partial unique index.

Spec ref: specs/005-inventory-management/spec.md §15 / FR-IO-016
"""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Index,
    Numeric,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from core.database.models.tenant_base import TenantBaseModel

_ALERT_TYPES = "'OUT_OF_STOCK', 'SAFETY_STOCK_BREACH', 'LOW_STOCK', 'OVERSTOCK'"
_ALERT_STATUSES = "'OPEN', 'ACKNOWLEDGED', 'RESOLVED'"
_SUGGESTION_STATUSES = "'PENDING', 'ACKNOWLEDGED', 'CONVERTED'"


class ReorderRule(TenantBaseModel):
    """Per-product (and optionally per-warehouse) reorder configuration.

    If ``warehouse_id`` is NULL the rule applies globally across all warehouses
    for that product.  Warehouse-specific rules take precedence over global ones.
    """

    __tablename__ = "inventory_reorder_rules"
    __table_args__ = (
        CheckConstraint(
            "reorder_level >= 0",
            name="ck_reorder_rule_reorder_level_non_negative",
        ),
        CheckConstraint(
            "reorder_quantity > 0",
            name="ck_reorder_rule_reorder_qty_positive",
        ),
        Index("ix_inv_reorder_rules_company_product", "company_id", "product_id"),
        Index("ix_inv_reorder_rules_company_id", "company_id"),
        {"comment": "Per-product reorder rules for automatic reorder suggestions"},
    )

    product_id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        nullable=False,
        doc="FK to the product this rule applies to",
    )

    variant_id: Mapped[str | None] = mapped_column(
        PG_UUID(as_uuid=False),
        nullable=True,
        doc="FK to the specific variant (null = all variants)",
    )

    warehouse_id: Mapped[str | None] = mapped_column(
        PG_UUID(as_uuid=False),
        nullable=True,
        doc="FK to the warehouse (null = applies to all warehouses)",
    )

    reorder_level: Mapped[Decimal] = mapped_column(
        Numeric(18, 4),
        nullable=False,
        server_default="0",
        doc="Trigger a reorder suggestion when qty_on_hand falls to this level",
    )

    reorder_quantity: Mapped[Decimal] = mapped_column(
        Numeric(18, 4),
        nullable=False,
        server_default="1",
        doc="Suggested quantity to order when the reorder level is reached",
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="true",
        doc="Whether this rule is currently active",
    )


class LowStockAlert(TenantBaseModel):
    """Low-stock / out-of-stock alert raised by the AlertEvaluationService.

    Lifecycle:
      OPEN → ACKNOWLEDGED  (manually by operator)
      OPEN → RESOLVED      (auto by AlertEvaluationService on restock)
      ACKNOWLEDGED → RESOLVED

    Deduplication: only one OPEN alert of the same (company_id, product_id,
    warehouse_id, alert_type) may exist.  Enforced by partial unique index
    ``uq_inv_alert_open_dedup``.
    """

    __tablename__ = "inventory_low_stock_alerts"
    __table_args__ = (
        CheckConstraint(
            f"alert_type IN ({_ALERT_TYPES})",
            name="ck_inv_alert_type",
        ),
        CheckConstraint(
            f"status IN ({_ALERT_STATUSES})",
            name="ck_inv_alert_status",
        ),
        # Partial unique index — only one OPEN alert per type × product × warehouse
        # postgresql_where and sqlite_where ensure the partial index works in both
        # PostgreSQL (production) and SQLite (test suite).
        Index(
            "uq_inv_alert_open_dedup",
            "company_id",
            "product_id",
            "warehouse_id",
            "alert_type",
            postgresql_where=text("status = 'OPEN'"),
            sqlite_where=text("status = 'OPEN'"),
            unique=True,
        ),
        Index("ix_inv_alert_company_status", "company_id", "status"),
        Index("ix_inv_alert_company_product", "company_id", "product_id"),
        {"comment": "Low-stock and overstock alerts raised by inventory intelligence"},
    )

    product_id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        nullable=False,
        doc="FK to the product this alert concerns",
    )

    variant_id: Mapped[str | None] = mapped_column(
        PG_UUID(as_uuid=False),
        nullable=True,
        doc="FK to the specific variant (null = base product)",
    )

    warehouse_id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        nullable=False,
        doc="FK to the warehouse where the low stock occurred",
    )

    alert_type: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        doc="OUT_OF_STOCK | SAFETY_STOCK_BREACH | LOW_STOCK | OVERSTOCK",
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default="OPEN",
        doc="OPEN | ACKNOWLEDGED | RESOLVED",
    )

    current_quantity: Mapped[Decimal] = mapped_column(
        Numeric(18, 4),
        nullable=False,
        doc="Stock quantity at the time the alert was raised",
    )

    threshold_quantity: Mapped[Decimal] = mapped_column(
        Numeric(18, 4),
        nullable=False,
        doc="The threshold quantity that triggered the alert",
    )

    acknowledged_at: Mapped[object | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        doc="UTC timestamp when the alert was acknowledged",
    )

    acknowledged_by: Mapped[str | None] = mapped_column(
        PG_UUID(as_uuid=False),
        nullable=True,
        doc="UUID of the user who acknowledged the alert",
    )

    resolved_at: Mapped[object | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        doc="UTC timestamp when the alert was resolved",
    )

    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        doc="Optional notes on the alert (e.g. resolution reason)",
    )


class ReorderSuggestion(TenantBaseModel):
    """A reorder suggestion created when a LOW_STOCK alert is raised.

    Does NOT create a Purchase Order — that is done by the Purchase module
    via the ``triggered_by_alert_id`` reference.

    Status:
      PENDING      — suggestion raised, awaiting review
      ACKNOWLEDGED — reviewed and noted by operator
      CONVERTED    — converted to a Purchase Order by Purchase module
    """

    __tablename__ = "inventory_reorder_suggestions"
    __table_args__ = (
        CheckConstraint(
            f"status IN ({_SUGGESTION_STATUSES})",
            name="ck_inv_suggestion_status",
        ),
        Index("ix_inv_suggestion_company_status", "company_id", "status"),
        Index("ix_inv_suggestion_company_product", "company_id", "product_id"),
        {"comment": "Reorder suggestions triggered by low-stock alerts"},
    )

    product_id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        nullable=False,
        doc="FK to the product that needs reordering",
    )

    variant_id: Mapped[str | None] = mapped_column(
        PG_UUID(as_uuid=False),
        nullable=True,
        doc="FK to the specific variant (null = base product)",
    )

    warehouse_id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        nullable=False,
        doc="FK to the warehouse that is running low",
    )

    suggested_quantity: Mapped[Decimal] = mapped_column(
        Numeric(18, 4),
        nullable=False,
        doc="Suggested order quantity (from the matching ReorderRule)",
    )

    triggered_by_alert_id: Mapped[str | None] = mapped_column(
        PG_UUID(as_uuid=False),
        nullable=True,
        doc="FK to the LowStockAlert that triggered this suggestion",
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default="PENDING",
        doc="PENDING | ACKNOWLEDGED | CONVERTED",
    )

    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        doc="Optional operator notes",
    )
