"""ProductRepository — data-access layer for the Product aggregate.

Covers: Product, ProductVariant, ProductBarcode, ProductImage.

FTS strategy: ``search_vector`` TEXT column is populated application-side
(name + product_code + description). Queries use ``ilike`` for portability
across PostgreSQL (with pg_trgm GIN) and SQLite (for tests).

Spec ref: specs/005-inventory-management/spec.md §14
Data model: specs/005-inventory-management/data-model.md §1.1
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from core.repositories.base import BaseRepository
from modules.inventory.models.product import (
    Product,
    ProductBarcode,
    ProductVariant,
)

# =============================================================================
# ProductRepository
# =============================================================================


class ProductRepository(BaseRepository[Product]):
    """Data-access layer for ``inventory_products`` table."""

    def __init__(self, db: Session) -> None:
        super().__init__(db=db, model=Product)

    # ── Lookup methods ────────────────────────────────────────────────────

    def get_by_code(self, company_id: UUID, product_code: str) -> Product | None:
        """Return the product with this code for the company, or None."""
        stmt = (
            select(Product)
            .where(Product.company_id == company_id)
            .where(func.upper(Product.product_code) == product_code.upper())
            .where(Product.is_deleted == False)  # noqa: E712
        )
        return self.db.execute(stmt).scalars().one_or_none()

    def get_by_barcode(self, company_id: UUID, barcode_value: str) -> Product | None:
        """Return the product owning this barcode, or None.

        Searches both product-level and variant-level barcodes.  Uses a
        two-step lookup (barcode → product) to avoid UUID format mismatches
        between Uuid(as_uuid=True) and PG_UUID(as_uuid=False) columns when
        running under SQLite in tests.
        """
        barcode = (
            self.db.execute(
                select(ProductBarcode)
                .where(ProductBarcode.company_id == company_id)
                .where(ProductBarcode.barcode_value == barcode_value)
                .where(ProductBarcode.is_deleted == False)  # noqa: E712
            )
            .scalars()
            .one_or_none()
        )

        if barcode is None:
            return None

        try:
            product_id = UUID(barcode.product_id)
        except (ValueError, AttributeError):
            return None

        return (
            self.db.execute(
                select(Product)
                .where(Product.id == product_id)
                .where(Product.company_id == company_id)
                .where(Product.is_deleted == False)  # noqa: E712
            )
            .scalars()
            .one_or_none()
        )

    def barcode_exists(
        self,
        company_id: UUID,
        barcode_value: str,
        exclude_product_id: UUID | None = None,
    ) -> bool:
        """Return True if the barcode value is already in use for this company."""
        stmt = (
            select(ProductBarcode.id)
            .where(ProductBarcode.company_id == company_id)
            .where(ProductBarcode.barcode_value == barcode_value)
            .where(ProductBarcode.is_deleted == False)  # noqa: E712
        )
        if exclude_product_id is not None:
            stmt = stmt.where(ProductBarcode.product_id != str(exclude_product_id))
        return self.db.execute(stmt).scalars().first() is not None

    def sku_exists(
        self, company_id: UUID, sku: str, exclude_product_id: UUID | None = None
    ) -> bool:
        """Return True if the SKU (product_code) is already in use for this company.

        Checks both product_code (on Product) and variant_code (on ProductVariant).
        """
        # Check product_code
        stmt = (
            select(Product.id)
            .where(Product.company_id == company_id)
            .where(func.upper(Product.product_code) == sku.upper())
            .where(Product.is_deleted == False)  # noqa: E712
        )
        if exclude_product_id is not None:
            stmt = stmt.where(Product.id != exclude_product_id)
        if self.db.execute(stmt).scalars().first() is not None:
            return True

        # Check variant_code
        stmt2 = (
            select(ProductVariant.id)
            .where(ProductVariant.company_id == company_id)
            .where(func.upper(ProductVariant.variant_code) == sku.upper())
            .where(ProductVariant.is_deleted == False)  # noqa: E712
        )
        return self.db.execute(stmt2).scalars().first() is not None

    def variant_sku_exists(
        self,
        company_id: UUID,
        variant_code: str,
        exclude_variant_id: UUID | None = None,
    ) -> bool:
        """Return True if a variant SKU is already in use for this company."""
        stmt = (
            select(ProductVariant.id)
            .where(ProductVariant.company_id == company_id)
            .where(func.upper(ProductVariant.variant_code) == variant_code.upper())
            .where(ProductVariant.is_deleted == False)  # noqa: E712
        )
        if exclude_variant_id is not None:
            stmt = stmt.where(ProductVariant.id != exclude_variant_id)
        return self.db.execute(stmt).scalars().first() is not None

    # ── Search & list ─────────────────────────────────────────────────────

    def search(
        self,
        company_id: UUID,
        *,
        query: str | None = None,
        status: str | None = None,
        product_type: str | None = None,
        category_id: UUID | None = None,
        brand_id: UUID | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Product], int]:
        """Search products with optional FTS query and filters.

        Returns ``(items, total_count)`` tuple.

        FTS uses ``search_vector ILIKE '%q%'`` which works on both SQLite
        (tests) and PostgreSQL (pg_trgm GIN accelerates it in production).
        """
        stmt = (
            select(Product)
            .where(Product.company_id == company_id)
            .where(Product.is_deleted == False)  # noqa: E712
        )

        if query:
            q = f"%{query}%"
            stmt = stmt.where(Product.search_vector.ilike(q))

        if status:
            stmt = stmt.where(Product.status == status)

        if product_type:
            stmt = stmt.where(Product.product_type == product_type)

        if category_id is not None:
            stmt = stmt.where(Product.category_id == str(category_id))

        if brand_id is not None:
            stmt = stmt.where(Product.brand_id == str(brand_id))

        # Total count
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = self.db.execute(count_stmt).scalar_one()

        # Paginated results
        offset = (page - 1) * page_size
        stmt = stmt.order_by(Product.name).offset(offset).limit(page_size)
        items = list(self.db.execute(stmt).scalars().all())

        return items, total

    def list_active(self, company_id: UUID) -> list[Product]:
        """Return all active, non-deleted products for a company."""
        stmt = (
            select(Product)
            .where(Product.company_id == company_id)
            .where(Product.status == "ACTIVE")
            .where(Product.is_deleted == False)  # noqa: E712
            .order_by(Product.name)
        )
        return list(self.db.execute(stmt).scalars().all())

    # ── search_vector population ──────────────────────────────────────────

    @staticmethod
    def build_search_vector(product: Product) -> str:
        """Build the application-side search vector text.

        Concatenates: name + product_code + description (truncated).
        This value is stored in ``Product.search_vector`` so ILIKE queries
        can search across all three fields.
        """
        parts = [
            product.name or "",
            product.product_code or "",
            (product.description or "")[:500],
            (product.short_description or ""),
        ]
        return " ".join(p for p in parts if p).lower()

    def refresh_search_vector(self, product: Product) -> None:
        """Recompute and store the search_vector for a product."""
        product.search_vector = self.build_search_vector(product)


# =============================================================================
# ProductVariantRepository
# =============================================================================


class ProductVariantRepository(BaseRepository[ProductVariant]):
    """Data-access layer for ``inventory_product_variants`` table."""

    def __init__(self, db: Session) -> None:
        super().__init__(db=db, model=ProductVariant)

    def list_for_product(
        self, company_id: UUID, product_id: UUID
    ) -> list[ProductVariant]:
        """Return all non-deleted variants for a product."""
        stmt = (
            select(ProductVariant)
            .where(ProductVariant.company_id == company_id)
            .where(ProductVariant.product_id == str(product_id))
            .where(ProductVariant.is_deleted == False)  # noqa: E712
            .order_by(ProductVariant.created_at)
        )
        return list(self.db.execute(stmt).scalars().all())

    def get_by_code(self, company_id: UUID, variant_code: str) -> ProductVariant | None:
        """Return the variant with this SKU for the company, or None."""
        stmt = (
            select(ProductVariant)
            .where(ProductVariant.company_id == company_id)
            .where(func.upper(ProductVariant.variant_code) == variant_code.upper())
            .where(ProductVariant.is_deleted == False)  # noqa: E712
        )
        return self.db.execute(stmt).scalars().one_or_none()

    def variant_sku_exists(
        self,
        company_id: UUID,
        variant_code: str,
        exclude_variant_id: UUID | None = None,
    ) -> bool:
        """Return True if a variant SKU is already in use for this company."""
        stmt = (
            select(ProductVariant.id)
            .where(ProductVariant.company_id == company_id)
            .where(func.upper(ProductVariant.variant_code) == variant_code.upper())
            .where(ProductVariant.is_deleted == False)  # noqa: E712
        )
        if exclude_variant_id is not None:
            stmt = stmt.where(ProductVariant.id != exclude_variant_id)
        return self.db.execute(stmt).scalars().first() is not None


# =============================================================================
# ProductBarcodeRepository
# =============================================================================


class ProductBarcodeRepository(BaseRepository[ProductBarcode]):
    """Data-access layer for ``inventory_product_barcodes`` table."""

    def __init__(self, db: Session) -> None:
        super().__init__(db=db, model=ProductBarcode)

    def list_for_product(
        self, company_id: UUID, product_id: UUID, *, variant_id: UUID | None = None
    ) -> list[ProductBarcode]:
        """Return barcodes for a product or a specific variant."""
        stmt = (
            select(ProductBarcode)
            .where(ProductBarcode.company_id == company_id)
            .where(ProductBarcode.product_id == str(product_id))
            .where(ProductBarcode.is_deleted == False)  # noqa: E712
        )
        if variant_id is not None:
            stmt = stmt.where(ProductBarcode.variant_id == str(variant_id))
        else:
            stmt = stmt.where(ProductBarcode.variant_id == None)  # noqa: E711
        return list(self.db.execute(stmt).scalars().all())

    def get_by_value(
        self, company_id: UUID, barcode_value: str
    ) -> ProductBarcode | None:
        """Return a barcode record by value within a company."""
        stmt = (
            select(ProductBarcode)
            .where(ProductBarcode.company_id == company_id)
            .where(ProductBarcode.barcode_value == barcode_value)
            .where(ProductBarcode.is_deleted == False)  # noqa: E712
        )
        return self.db.execute(stmt).scalars().one_or_none()
