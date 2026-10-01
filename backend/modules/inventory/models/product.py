"""Product ORM models — Product aggregate root with Variants, Barcodes, and Images.

Multi-tenancy: All models inherit ``company_id`` from ``TenantBaseModel``.

Product status state machine (spec §4.1):
    DRAFT → ACTIVE → INACTIVE → ACTIVE (reactivate)
    ACTIVE → DISCONTINUED
    INACTIVE → ARCHIVED
    DISCONTINUED → ARCHIVED (terminal)

Spec ref: specs/005-inventory-management/spec.md §14
Data model: specs/005-inventory-management/data-model.md §1.1 / §4.1
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.database.models.tenant_base import TenantBaseModel

# ---------------------------------------------------------------------------
# Product types and status values (mirrors spec §14 Product Types)
# ---------------------------------------------------------------------------

_PRODUCT_TYPES = "('STANDARD', 'VARIANT', 'SERVICE', 'BUNDLE', 'RAW_MATERIAL')"
_PRODUCT_STATUSES = "('DRAFT', 'ACTIVE', 'INACTIVE', 'DISCONTINUED', 'ARCHIVED')"
_BARCODE_TYPES = "('EAN13', 'EAN8', 'QR', 'CODE128', 'CUSTOM')"


# =============================================================================
# Product — aggregate root
# =============================================================================


class Product(TenantBaseModel):
    """Product catalogue entry — aggregate root for the Product domain.

    Inherits ``id``, ``created_at``, ``updated_at``, ``company_id``,
    ``created_by``, ``is_deleted``, ``deleted_at`` from ``TenantBaseModel``.

    ``product_type`` values: STANDARD, VARIANT, SERVICE, BUNDLE, RAW_MATERIAL
    ``status`` values: DRAFT, ACTIVE, INACTIVE, DISCONTINUED, ARCHIVED
    """

    __tablename__ = "inventory_products"
    __table_args__ = (
        UniqueConstraint(
            "company_id",
            "product_code",
            name="uq_inv_products_company_code",
        ),
        Index("ix_inv_products_company_id", "company_id"),
        Index("ix_inv_products_company_status", "company_id", "status"),
        Index("ix_inv_products_company_type", "company_id", "product_type"),
        Index("ix_inv_products_category", "company_id", "category_id"),
        Index("ix_inv_products_brand", "company_id", "brand_id"),
        # search_vector supports full-text-style LIKE queries and pg_trgm GIN
        Index("ix_inv_products_search_vector", "search_vector"),
        CheckConstraint(
            f"product_type IN {_PRODUCT_TYPES}",
            name="ck_inv_products_type",
        ),
        CheckConstraint(
            f"status IN {_PRODUCT_STATUSES}",
            name="ck_inv_products_status",
        ),
        {"comment": "Product catalogue entries, scoped per company"},
    )

    # ── Core fields ──────────────────────────────────────────────────────────

    product_code: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        doc="Unique product code (SKU) per company",
    )

    name: Mapped[str] = mapped_column(
        String(300),
        nullable=False,
        doc="Human-readable product name",
    )

    product_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default="STANDARD",
        doc="Product type: STANDARD, VARIANT, SERVICE, BUNDLE, RAW_MATERIAL",
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default="DRAFT",
        doc="Lifecycle status: DRAFT, ACTIVE, INACTIVE, DISCONTINUED, ARCHIVED",
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        doc="Full product description",
    )

    short_description: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        doc="Short marketing description (optional)",
    )

    # ── Foreign keys to master data ──────────────────────────────────────────

    base_uom_id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        ForeignKey("inventory_uoms.id", ondelete="RESTRICT"),
        nullable=False,
        doc="FK to base Unit of Measure (required)",
    )

    category_id: Mapped[str | None] = mapped_column(
        PG_UUID(as_uuid=False),
        ForeignKey("inventory_categories.id", ondelete="SET NULL"),
        nullable=True,
        doc="FK to product category (optional)",
    )

    brand_id: Mapped[str | None] = mapped_column(
        PG_UUID(as_uuid=False),
        ForeignKey("inventory_brands.id", ondelete="SET NULL"),
        nullable=True,
        doc="FK to product brand (optional)",
    )

    # ── Procurement / physical metadata (13 nullable fields) ─────────────────

    hs_code: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
        doc="Harmonised System tariff code for customs",
    )

    country_of_origin: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        doc="Country where the product is manufactured",
    )

    lead_time_days: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        doc="Procurement lead time in calendar days",
    )

    min_order_qty: Mapped[float | None] = mapped_column(
        Numeric(14, 4),
        nullable=True,
        doc="Minimum order quantity (in base UOM)",
    )

    max_order_qty: Mapped[float | None] = mapped_column(
        Numeric(14, 4),
        nullable=True,
        doc="Maximum order quantity (in base UOM)",
    )

    reorder_point: Mapped[float | None] = mapped_column(
        Numeric(14, 4),
        nullable=True,
        doc="Reorder level in base UOM units",
    )

    weight_kg: Mapped[float | None] = mapped_column(
        Numeric(10, 4),
        nullable=True,
        doc="Product weight in kilograms",
    )

    width_cm: Mapped[float | None] = mapped_column(
        Numeric(10, 4),
        nullable=True,
        doc="Product width in centimetres",
    )

    height_cm: Mapped[float | None] = mapped_column(
        Numeric(10, 4),
        nullable=True,
        doc="Product height in centimetres",
    )

    depth_cm: Mapped[float | None] = mapped_column(
        Numeric(10, 4),
        nullable=True,
        doc="Product depth in centimetres",
    )

    is_serialized: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
        doc="True if each unit has a unique serial number",
    )

    is_batch_tracked: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
        doc="True if stock is tracked by batch/lot numbers",
    )

    cost_price: Mapped[float | None] = mapped_column(
        Numeric(14, 4),
        nullable=True,
        doc="Standard cost price (in company default currency)",
    )

    # ── Full-text search ─────────────────────────────────────────────────────

    search_vector: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        doc=(
            "Application-computed search text: name + product_code + description. "
            "Supports LIKE/ILIKE queries; GIN pg_trgm index added via migration."
        ),
    )

    # ── Relationships ────────────────────────────────────────────────────────

    variants: Mapped[list[ProductVariant]] = relationship(
        "ProductVariant",
        back_populates="product",
        cascade="all, delete-orphan",
        lazy="select",
        foreign_keys="[ProductVariant.product_id]",
    )

    barcodes: Mapped[list[ProductBarcode]] = relationship(
        "ProductBarcode",
        cascade="all, delete-orphan",
        lazy="select",
        foreign_keys="[ProductBarcode.product_id]",
        primaryjoin="Product.id == foreign(ProductBarcode.product_id)",
    )

    images: Mapped[list[ProductImage]] = relationship(
        "ProductImage",
        cascade="all, delete-orphan",
        lazy="select",
        foreign_keys="[ProductImage.product_id]",
        primaryjoin="Product.id == foreign(ProductImage.product_id)",
    )


# =============================================================================
# ProductVariant — child entity
# =============================================================================


class ProductVariant(TenantBaseModel):
    """A specific variant of a Product (e.g. size=L, colour=Red).

    Each variant has its own SKU (variant_code), optional barcodes, images,
    and a key-value attributes dictionary.

    Invariants:
    - ``variant_code`` (SKU) unique per company
    - Must reference a valid parent Product
    """

    __tablename__ = "inventory_product_variants"
    __table_args__ = (
        UniqueConstraint(
            "company_id",
            "variant_code",
            name="uq_inv_variants_company_sku",
        ),
        Index("ix_inv_variants_product_id", "product_id"),
        Index("ix_inv_variants_company_id", "company_id"),
        {"comment": "Product variants with own SKU and attributes, per company"},
    )

    product_id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        ForeignKey("inventory_products.id", ondelete="CASCADE"),
        nullable=False,
        doc="FK to parent Product",
    )

    variant_code: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        doc="Unique SKU code per company (e.g. 'PROD-001-L-RED')",
    )

    attributes: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
        doc="Key-value attribute dictionary (e.g. {'size': 'L', 'colour': 'Red'})",
    )

    is_stock_tracked: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
        doc="Whether inventory levels are tracked for this variant",
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default="ACTIVE",
        doc="Variant status: ACTIVE or INACTIVE",
    )

    # ── Relationships ────────────────────────────────────────────────────────

    product: Mapped[Product] = relationship("Product", back_populates="variants")

    variant_barcodes: Mapped[list[ProductBarcode]] = relationship(
        "ProductBarcode",
        primaryjoin="ProductVariant.id == foreign(ProductBarcode.variant_id)",
        cascade="all, delete-orphan",
        lazy="select",
    )

    variant_images: Mapped[list[ProductImage]] = relationship(
        "ProductImage",
        primaryjoin="ProductVariant.id == foreign(ProductImage.variant_id)",
        cascade="all, delete-orphan",
        lazy="select",
    )


# =============================================================================
# ProductBarcode — value object
# =============================================================================


class ProductBarcode(TenantBaseModel):
    """Barcode value attached to a Product or ProductVariant.

    Invariant: ``barcode_value`` unique per company (across all products/variants).

    ``barcode_type`` values: EAN13, EAN8, QR, CODE128, CUSTOM
    Only one barcode per product (or variant) may have ``is_primary=True``.
    """

    __tablename__ = "inventory_product_barcodes"
    __table_args__ = (
        UniqueConstraint(
            "company_id",
            "barcode_value",
            name="uq_inv_barcodes_company_value",
        ),
        Index("ix_inv_barcodes_product_id", "product_id"),
        Index("ix_inv_barcodes_variant_id", "variant_id"),
        Index("ix_inv_barcodes_company_value", "company_id", "barcode_value"),
        CheckConstraint(
            f"barcode_type IN {_BARCODE_TYPES}",
            name="ck_inv_barcodes_type",
        ),
        {
            "comment": "Product barcodes (EAN13, QR, CODE128, CUSTOM), unique per company"
        },
    )

    product_id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        ForeignKey("inventory_products.id", ondelete="CASCADE"),
        nullable=False,
        doc="FK to owning Product",
    )

    variant_id: Mapped[str | None] = mapped_column(
        PG_UUID(as_uuid=False),
        ForeignKey("inventory_product_variants.id", ondelete="CASCADE"),
        nullable=True,
        doc="FK to specific Variant, or NULL for product-level barcode",
    )

    barcode_value: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        doc="Barcode string value (e.g. '4006381333931')",
    )

    barcode_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        doc="Barcode symbology: EAN13, EAN8, QR, CODE128, CUSTOM",
    )

    is_primary: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
        doc="True if this is the primary/default barcode for the product/variant",
    )


# =============================================================================
# ProductImage — value object
# =============================================================================


class ProductImage(TenantBaseModel):
    """Image attached to a Product or ProductVariant.

    Images are stored in S3; this model records the reference (s3_key, url).
    Only one image per product (or variant) may have ``is_primary=True``.
    """

    __tablename__ = "inventory_product_images"
    __table_args__ = (
        Index("ix_inv_images_product_id", "product_id"),
        Index("ix_inv_images_variant_id", "variant_id"),
        {"comment": "Product images referencing S3 objects, per product or variant"},
    )

    product_id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        ForeignKey("inventory_products.id", ondelete="CASCADE"),
        nullable=False,
        doc="FK to owning Product",
    )

    variant_id: Mapped[str | None] = mapped_column(
        PG_UUID(as_uuid=False),
        ForeignKey("inventory_product_variants.id", ondelete="CASCADE"),
        nullable=True,
        doc="FK to specific Variant, or NULL for product-level image",
    )

    s3_key: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        doc="S3 object key (relative path within the bucket)",
    )

    url: Mapped[str] = mapped_column(
        String(1000),
        nullable=False,
        doc="Public or pre-signed URL to access the image",
    )

    thumbnail_url: Mapped[str | None] = mapped_column(
        String(1000),
        nullable=True,
        doc="URL for the thumbnail version (optional)",
    )

    is_primary: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
        doc="True if this is the main display image for the product/variant",
    )

    sort_order: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
        doc="Display order (ascending)",
    )
