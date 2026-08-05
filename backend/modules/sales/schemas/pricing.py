"""Pricing schemas — Phase 2.

Request/response schemas for:
  PriceList          — CRUD schemas
  PriceEntry         — CRUD schemas
  CustomerSpecificPrice — CRUD schemas
  DiscountRule       — CRUD schemas
  PriceResolution    — price resolution response

Spec ref: specs/007-sales-management/plan.md §Phase 3
Task: T070
"""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from pydantic import Field, field_validator

from modules.sales.schemas.base import SalesBaseSchema

# ---------------------------------------------------------------------------
# PriceEntry schemas (nested within PriceList)
# ---------------------------------------------------------------------------


class PriceEntryCreate(SalesBaseSchema):
    product_id: str = Field(..., description="Epic 5 Product UUID")
    unit_price: Decimal = Field(
        ..., ge=0, description="Unit price for this quantity break"
    )
    minimum_quantity: Decimal = Field(
        default=Decimal("1"), gt=0, description="Minimum quantity for this price break"
    )
    unit_of_measure: str = Field(
        default="EA", max_length=20, description="Unit of measure"
    )

    @field_validator("unit_of_measure")
    @classmethod
    def uom_upper(cls, v: str) -> str:
        return v.upper()


class PriceEntryUpdate(SalesBaseSchema):
    unit_price: Decimal | None = Field(None, ge=0)
    minimum_quantity: Decimal | None = Field(None, gt=0)
    unit_of_measure: str | None = Field(None, max_length=20)


class PriceEntryRead(SalesBaseSchema):
    id: UUID
    company_id: UUID
    price_list_id: str
    product_id: str
    unit_price: Decimal
    minimum_quantity: Decimal
    unit_of_measure: str
    is_deleted: bool


# ---------------------------------------------------------------------------
# PriceList schemas
# ---------------------------------------------------------------------------


class PriceListCreate(SalesBaseSchema):
    name: str = Field(
        ..., max_length=200, description="Price list name (unique per company)"
    )
    description: str | None = Field(None, description="Optional description")
    currency_code: str = Field(
        default="USD", max_length=3, description="ISO 4217 currency code"
    )
    effective_from: str = Field(..., description="Effective start date (YYYY-MM-DD)")
    effective_to: str | None = Field(
        None, description="Effective end date (YYYY-MM-DD); NULL = no expiry"
    )
    is_default: bool = Field(
        default=False, description="Set as company default price list"
    )
    is_active: bool = Field(default=True)
    priority: int = Field(
        default=0, ge=0, description="Resolution priority (higher = first)"
    )
    customer_group_id: str | None = Field(
        None, description="Scope to a customer group (level 3 resolution)"
    )
    customer_category_id: str | None = Field(
        None, description="Scope to a customer category (level 4 resolution)"
    )

    @field_validator("currency_code")
    @classmethod
    def currency_upper(cls, v: str) -> str:
        return v.upper()


class PriceListUpdate(SalesBaseSchema):
    name: str | None = Field(None, max_length=200)
    description: str | None = None
    currency_code: str | None = Field(None, max_length=3)
    effective_from: str | None = None
    effective_to: str | None = None
    is_default: bool | None = None
    is_active: bool | None = None
    priority: int | None = Field(None, ge=0)
    customer_group_id: str | None = None
    customer_category_id: str | None = None


class PriceListRead(SalesBaseSchema):
    id: UUID
    company_id: UUID
    name: str
    description: str | None
    currency_code: str
    effective_from: str
    effective_to: str | None
    is_default: bool
    is_active: bool
    priority: int
    customer_group_id: str | None
    customer_category_id: str | None
    version: int
    is_deleted: bool
    entries: list[PriceEntryRead] = Field(default_factory=list)


class PriceListListItem(SalesBaseSchema):
    id: UUID
    company_id: UUID
    name: str
    currency_code: str
    effective_from: str
    effective_to: str | None
    is_default: bool
    is_active: bool
    priority: int
    customer_group_id: str | None
    customer_category_id: str | None


# ---------------------------------------------------------------------------
# CustomerSpecificPrice schemas
# ---------------------------------------------------------------------------


class CustomerSpecificPriceCreate(SalesBaseSchema):
    customer_id: str = Field(..., description="Customer UUID")
    product_id: str = Field(..., description="Epic 5 Product UUID")
    unit_price: Decimal = Field(..., ge=0, description="Override unit price")
    effective_from: str = Field(..., description="Effective start date (YYYY-MM-DD)")
    effective_to: str | None = Field(
        None, description="Effective end date; NULL = no expiry"
    )
    minimum_quantity: Decimal = Field(
        default=Decimal("1"), gt=0, description="Minimum quantity for this price"
    )


class CustomerSpecificPriceUpdate(SalesBaseSchema):
    unit_price: Decimal | None = Field(None, ge=0)
    effective_from: str | None = None
    effective_to: str | None = None
    minimum_quantity: Decimal | None = Field(None, gt=0)


class CustomerSpecificPriceRead(SalesBaseSchema):
    id: UUID
    company_id: UUID
    customer_id: str
    product_id: str
    unit_price: Decimal
    effective_from: str
    effective_to: str | None
    minimum_quantity: Decimal
    is_deleted: bool


# ---------------------------------------------------------------------------
# DiscountRule schemas
# ---------------------------------------------------------------------------


_RULE_TYPES = {"PERCENTAGE", "FIXED_AMOUNT", "VOLUME", "PROMOTIONAL"}
_APPLICABILITIES = {
    "ALL_CUSTOMERS",
    "SPECIFIC_CATEGORY",
    "SPECIFIC_GROUP",
    "SPECIFIC_CUSTOMER",
}
_PRODUCT_SCOPES = {"ALL_PRODUCTS", "SPECIFIC_CATEGORY", "SPECIFIC_PRODUCT"}


class DiscountRuleCreate(SalesBaseSchema):
    name: str = Field(..., max_length=200, description="Discount rule name")
    rule_type: str = Field(
        ..., description="PERCENTAGE / FIXED_AMOUNT / VOLUME / PROMOTIONAL"
    )
    applicability: str = Field(
        default="ALL_CUSTOMERS",
        description="ALL_CUSTOMERS / SPECIFIC_CATEGORY / SPECIFIC_GROUP / SPECIFIC_CUSTOMER",
    )
    applicability_id: str | None = Field(
        None,
        description="FK to category/group/customer when applicability is SPECIFIC_*",
    )
    product_scope: str = Field(
        default="ALL_PRODUCTS",
        description="ALL_PRODUCTS / SPECIFIC_CATEGORY / SPECIFIC_PRODUCT",
    )
    product_scope_id: str | None = Field(
        None,
        description="FK to product category/product when product_scope is SPECIFIC_*",
    )
    minimum_quantity: Decimal | None = Field(
        None, gt=0, description="Minimum line quantity to trigger this discount"
    )
    minimum_order_value: Decimal | None = Field(
        None, ge=0, description="Minimum order total to trigger this discount"
    )
    discount_value: Decimal = Field(
        ...,
        ge=0,
        description="Discount value (% for PERCENTAGE, amount for FIXED_AMOUNT)",
    )
    effective_from: str = Field(..., description="Effective start date (YYYY-MM-DD)")
    effective_to: str | None = Field(
        None, description="Effective end date; NULL = no expiry"
    )
    is_active: bool = Field(default=True)
    priority: int = Field(
        default=0, ge=0, description="Priority (higher = applied first)"
    )
    is_stackable: bool = Field(
        default=False, description="Whether to combine with other discounts"
    )

    @field_validator("rule_type")
    @classmethod
    def validate_rule_type(cls, v: str) -> str:
        v = v.upper()
        if v not in _RULE_TYPES:
            raise ValueError(f"rule_type must be one of {sorted(_RULE_TYPES)}")
        return v

    @field_validator("applicability")
    @classmethod
    def validate_applicability(cls, v: str) -> str:
        v = v.upper()
        if v not in _APPLICABILITIES:
            raise ValueError(f"applicability must be one of {sorted(_APPLICABILITIES)}")
        return v

    @field_validator("product_scope")
    @classmethod
    def validate_product_scope(cls, v: str) -> str:
        v = v.upper()
        if v not in _PRODUCT_SCOPES:
            raise ValueError(f"product_scope must be one of {sorted(_PRODUCT_SCOPES)}")
        return v


class DiscountRuleUpdate(SalesBaseSchema):
    name: str | None = Field(None, max_length=200)
    rule_type: str | None = None
    applicability: str | None = None
    applicability_id: str | None = None
    product_scope: str | None = None
    product_scope_id: str | None = None
    minimum_quantity: Decimal | None = Field(None, gt=0)
    minimum_order_value: Decimal | None = Field(None, ge=0)
    discount_value: Decimal | None = Field(None, ge=0)
    effective_from: str | None = None
    effective_to: str | None = None
    is_active: bool | None = None
    priority: int | None = Field(None, ge=0)
    is_stackable: bool | None = None


class DiscountRuleRead(SalesBaseSchema):
    id: UUID
    company_id: UUID
    name: str
    rule_type: str
    applicability: str
    applicability_id: str | None
    product_scope: str
    product_scope_id: str | None
    minimum_quantity: Decimal | None
    minimum_order_value: Decimal | None
    discount_value: Decimal
    effective_from: str
    effective_to: str | None
    is_active: bool
    priority: int
    is_stackable: bool
    is_deleted: bool


# ---------------------------------------------------------------------------
# Price Resolution response schema
# ---------------------------------------------------------------------------


class PriceResolveRequest(SalesBaseSchema):
    product_id: str = Field(..., description="Product UUID to resolve price for")
    quantity: Decimal = Field(
        default=Decimal("1"), gt=0, description="Ordered quantity"
    )
    customer_id: str | None = Field(None, description="Customer UUID (for levels 2-4)")
    group_id: str | None = Field(None, description="Customer group UUID (for level 3)")
    category_id: str | None = Field(
        None, description="Customer category UUID (for level 4)"
    )
    manual_price: Decimal | None = Field(
        None, ge=0, description="Manual override price (level 1)"
    )
    as_of_date: str | None = Field(
        None, description="Effective date (YYYY-MM-DD); defaults to today"
    )


class PriceResolutionResponse(SalesBaseSchema):
    unit_price: Decimal = Field(..., description="Resolved unit price")
    price_source: str = Field(..., description="Resolution source identifier")
    resolution_level: int = Field(..., description="Resolution hierarchy level (1-7)")
    price_list_id: str | None = Field(None, description="Matching price list UUID")
    price_list_name: str | None = Field(None, description="Matching price list name")
    price_entry_id: str | None = Field(None, description="Matching price entry UUID")
    customer_specific_price_id: str | None = Field(
        None, description="Matching customer-specific price UUID"
    )


class ApplicableDiscountResponse(SalesBaseSchema):
    rule_id: str
    rule_name: str
    rule_type: str
    discount_value: Decimal
    is_stackable: bool
    priority: int


class MarginCheckRequest(SalesBaseSchema):
    unit_price: Decimal = Field(..., gt=0)
    cost_price: Decimal = Field(..., gt=0)
    min_margin_pct: Decimal | None = Field(None, ge=0, le=100)
    block_on_low_margin: bool = False


class MarginCheckResponse(SalesBaseSchema):
    margin_percentage: Decimal
    passes: bool
    action: str
    threshold_pct: Decimal
