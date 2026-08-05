"""Pricing aggregate ORM models — Phase 2.

Phase 2 entities:
  PriceList              — aggregate root; price list header with effective dates
  PriceEntry             — product prices within a price list (quantity breaks)
  CustomerSpecificPrice  — per-customer price overrides with effective dates
  DiscountRule           — flexible discount rules by applicability and product scope

7-level Price Resolution (service-layer, not stored):
  1. Manual Override      — explicit price provided by caller
  2. Customer-Specific    — active CustomerSpecificPrice for customer + product
  3. Customer Group       — PriceList scoped to customer's group
  4. Customer Category    — PriceList scoped to customer's category
  5. Active Price List     — highest-priority active PriceList (no scope restriction)
  6. Default Price List    — price list marked is_default=True
  7. Product Base Price    — fallback (0.0 when no price found)

Spec ref: specs/007-sales-management/data-model.md §Pricing Aggregate
"""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
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

# ---------------------------------------------------------------------------
# Constants for CHECK constraints
# ---------------------------------------------------------------------------

_RULE_TYPES = "('PERCENTAGE', 'FIXED_AMOUNT', 'VOLUME', 'PROMOTIONAL')"
_APPLICABILITIES = (
    "('ALL_CUSTOMERS', 'SPECIFIC_CATEGORY', 'SPECIFIC_GROUP', 'SPECIFIC_CUSTOMER')"
)
_PRODUCT_SCOPES = "('ALL_PRODUCTS', 'SPECIFIC_CATEGORY', 'SPECIFIC_PRODUCT')"


# ---------------------------------------------------------------------------
# PriceList aggregate root
# ---------------------------------------------------------------------------


class PriceList(TenantBaseModel):
    """Price list aggregate root.

    A price list defines a set of prices for products, optionally scoped
    to a customer group or customer category. The 7-level price resolution
    service consults price lists in priority order.

    Invariants (enforced at service layer):
      - Exactly one price list per company has is_default=True.
      - Setting is_default=True clears the previous default.
      - Scoped price lists (group/category) are consulted before general lists.

    Spec ref: specs/007-sales-management/data-model.md §PriceList
    """

    __tablename__ = "price_lists"
    __table_args__ = (
        UniqueConstraint(
            "company_id",
            "name",
            name="uq_price_lists_company_name",
        ),
        Index("ix_price_lists_company_active", "company_id", "is_active"),
        Index("ix_price_lists_company_default", "company_id", "is_default"),
        Index("ix_price_lists_company_group", "company_id", "customer_group_id"),
        Index("ix_price_lists_company_category", "company_id", "customer_category_id"),
        CheckConstraint("priority >= 0", name="ck_price_lists_priority"),
        CheckConstraint("version >= 1", name="ck_price_lists_version"),
        {"comment": "Sales price lists — pricing aggregate root"},
    )

    # ---- Identity ----

    name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        doc="Price list name (unique per company)",
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        doc="Optional description",
    )

    # ---- Currency ----

    currency_code: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
        server_default="USD",
        doc="ISO 4217 currency code",
    )

    # ---- Effective Dates ----

    effective_from: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        doc="Effective start date (ISO 8601: YYYY-MM-DD)",
    )

    effective_to: Mapped[str | None] = mapped_column(
        String(10),
        nullable=True,
        doc="Effective end date (ISO 8601: YYYY-MM-DD); NULL = no expiry",
    )

    # ---- Flags ----

    is_default: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="false",
        doc="Whether this is the company default price list",
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="true",
        doc="Whether this price list is currently active",
    )

    # ---- Priority ----

    priority: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="0",
        doc="Resolution priority (higher = consulted first in level 5)",
    )

    # ---- Scope (for levels 3 and 4 of resolution) ----

    customer_group_id: Mapped[str | None] = mapped_column(
        PG_UUID(as_uuid=False),
        nullable=True,
        doc="If set: this price list is specific to a customer group (level 3)",
    )

    customer_category_id: Mapped[str | None] = mapped_column(
        PG_UUID(as_uuid=False),
        nullable=True,
        doc="If set: this price list is specific to a customer category (level 4)",
    )

    # ---- Optimistic Locking ----

    version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="1",
        doc="Optimistic concurrency version counter",
    )


# ---------------------------------------------------------------------------
# PriceEntry
# ---------------------------------------------------------------------------


class PriceEntry(TenantBaseModel):
    """A product price entry within a price list.

    Supports quantity breaks: multiple entries for the same product_id with
    different minimum_quantity thresholds. The entry with the highest
    min_quantity that is <= the ordered quantity is selected.

    Spec ref: specs/007-sales-management/data-model.md §PriceEntry
    """

    __tablename__ = "price_entries"
    __table_args__ = (
        Index(
            "ix_price_entries_lookup",
            "company_id",
            "price_list_id",
            "product_id",
        ),
        CheckConstraint("unit_price >= 0", name="ck_price_entries_unit_price"),
        CheckConstraint("minimum_quantity > 0", name="ck_price_entries_min_qty"),
        {"comment": "Product prices within a price list"},
    )

    # ---- Foreign Keys ----

    price_list_id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        nullable=False,
        doc="FK to PriceList (parent aggregate)",
    )

    product_id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        nullable=False,
        doc="FK to Epic 5 Product (not enforced at DB level for cross-module FK)",
    )

    # ---- Price ----

    unit_price: Mapped[Decimal] = mapped_column(
        Numeric(15, 4),
        nullable=False,
        doc="Unit price for this price break",
    )

    minimum_quantity: Mapped[Decimal] = mapped_column(
        Numeric(12, 3),
        nullable=False,
        server_default="1",
        doc="Minimum quantity to qualify for this price break",
    )

    unit_of_measure: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default="EA",
        doc="Unit of measure code (e.g. EA, KG, LTR)",
    )


# ---------------------------------------------------------------------------
# CustomerSpecificPrice
# ---------------------------------------------------------------------------


class CustomerSpecificPrice(TenantBaseModel):
    """Customer-specific price override.

    Overrides any price list price for a specific customer + product combination.
    Supports effective date ranges and optional minimum quantity thresholds.

    Resolution level 2 — consulted after manual override.

    Spec ref: specs/007-sales-management/data-model.md §CustomerSpecificPrice
    """

    __tablename__ = "customer_specific_prices"
    __table_args__ = (
        Index(
            "ix_customer_specific_prices_lookup",
            "company_id",
            "customer_id",
            "product_id",
        ),
        CheckConstraint("unit_price >= 0", name="ck_customer_specific_prices_price"),
        CheckConstraint(
            "minimum_quantity > 0", name="ck_customer_specific_prices_min_qty"
        ),
        {"comment": "Per-customer product price overrides"},
    )

    # ---- Foreign Keys ----

    customer_id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        nullable=False,
        doc="FK to Customer",
    )

    product_id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        nullable=False,
        doc="FK to Epic 5 Product",
    )

    # ---- Price ----

    unit_price: Mapped[Decimal] = mapped_column(
        Numeric(15, 4),
        nullable=False,
        doc="Override unit price",
    )

    minimum_quantity: Mapped[Decimal] = mapped_column(
        Numeric(12, 3),
        nullable=False,
        server_default="1",
        doc="Minimum quantity to qualify for this override",
    )

    # ---- Effective Dates ----

    effective_from: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        doc="Effective start date (ISO 8601: YYYY-MM-DD)",
    )

    effective_to: Mapped[str | None] = mapped_column(
        String(10),
        nullable=True,
        doc="Effective end date (ISO 8601: YYYY-MM-DD); NULL = no expiry",
    )


# ---------------------------------------------------------------------------
# DiscountRule
# ---------------------------------------------------------------------------


class DiscountRule(TenantBaseModel):
    """Discount rule for automatic discount calculation.

    Discount rules can target specific customers, groups, categories, or all
    customers, and can be scoped to specific products, product categories, or
    all products. Priority ordering resolves conflicts. Stackable rules can be
    combined; non-stackable rules compete and the highest priority wins.

    Spec ref: specs/007-sales-management/data-model.md §DiscountRule
    """

    __tablename__ = "discount_rules"
    __table_args__ = (
        Index("ix_discount_rules_company_active", "company_id", "is_active"),
        Index(
            "ix_discount_rules_company_active_from",
            "company_id",
            "is_active",
            "effective_from",
        ),
        CheckConstraint(
            f"rule_type IN {_RULE_TYPES}",
            name="ck_discount_rules_rule_type",
        ),
        CheckConstraint(
            f"applicability IN {_APPLICABILITIES}",
            name="ck_discount_rules_applicability",
        ),
        CheckConstraint(
            f"product_scope IN {_PRODUCT_SCOPES}",
            name="ck_discount_rules_product_scope",
        ),
        CheckConstraint("discount_value >= 0", name="ck_discount_rules_value"),
        CheckConstraint("priority >= 0", name="ck_discount_rules_priority"),
        {"comment": "Discount rules for automated discount application"},
    )

    # ---- Identity ----

    name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        doc="Discount rule name",
    )

    # ---- Rule Type ----

    rule_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        doc="PERCENTAGE / FIXED_AMOUNT / VOLUME / PROMOTIONAL",
    )

    # ---- Applicability (customer scope) ----

    applicability: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        server_default="ALL_CUSTOMERS",
        doc="ALL_CUSTOMERS / SPECIFIC_CATEGORY / SPECIFIC_GROUP / SPECIFIC_CUSTOMER",
    )

    applicability_id: Mapped[str | None] = mapped_column(
        PG_UUID(as_uuid=False),
        nullable=True,
        doc="FK to CustomerCategory/Group/Customer depending on applicability",
    )

    # ---- Product Scope ----

    product_scope: Mapped[str] = mapped_column(
        String(25),
        nullable=False,
        server_default="ALL_PRODUCTS",
        doc="ALL_PRODUCTS / SPECIFIC_CATEGORY / SPECIFIC_PRODUCT",
    )

    product_scope_id: Mapped[str | None] = mapped_column(
        PG_UUID(as_uuid=False),
        nullable=True,
        doc="FK to product category or specific product depending on product_scope",
    )

    # ---- Thresholds ----

    minimum_quantity: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 3),
        nullable=True,
        doc="Minimum order line quantity to trigger this discount",
    )

    minimum_order_value: Mapped[Decimal | None] = mapped_column(
        Numeric(15, 2),
        nullable=True,
        doc="Minimum order total value to trigger this discount",
    )

    # ---- Discount Value ----

    discount_value: Mapped[Decimal] = mapped_column(
        Numeric(15, 4),
        nullable=False,
        doc="Discount amount: percentage (0-100) for PERCENTAGE, amount for FIXED_AMOUNT",
    )

    # ---- Effective Dates ----

    effective_from: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        doc="Effective start date (ISO 8601: YYYY-MM-DD)",
    )

    effective_to: Mapped[str | None] = mapped_column(
        String(10),
        nullable=True,
        doc="Effective end date (ISO 8601: YYYY-MM-DD); NULL = no expiry",
    )

    # ---- Flags ----

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="true",
        doc="Whether this discount rule is currently active",
    )

    priority: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="0",
        doc="Resolution priority (higher priority applied first or wins non-stackable conflict)",
    )

    is_stackable: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="false",
        doc="Whether this discount can be stacked with others",
    )
