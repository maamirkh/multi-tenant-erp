"""ProductService — application service for the Product aggregate.

Combines: CreateProduct, UpdateProduct, ProductLifecycle, AddVariant,
          SearchProducts, GetProduct use cases.

Business rules enforced:
  - SKU (product_code) unique per company
  - Barcode unique per company
  - Status transitions follow spec §4.1 state machine
  - Mandatory fields (name, product_code, base_uom_id) must be present before activation
  - Archived products cannot be deleted (soft-delete is blocked once ARCHIVED)
  - Publishes domain events via EventBus

Spec ref: specs/005-inventory-management/spec.md §14
Data model: specs/005-inventory-management/data-model.md §4.1
"""

from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy.orm import Session

from modules.inventory.domain_events import (
    BarcodeAssigned,
    ProductActivated,
    ProductArchived,
    ProductCreated,
    ProductDeactivated,
    ProductDiscontinued,
    ProductUpdated,
    ProductVariantCreated,
)
from modules.inventory.events import InProcessEventBus
from modules.inventory.exceptions import (
    BarcodeAlreadyExistsError,
    InvalidProductStateTransitionError,
    ProductNotFoundError,
    SkuAlreadyExistsError,
    UomNotFoundError,
)
from modules.inventory.models.product import Product, ProductBarcode, ProductVariant
from modules.inventory.repositories.product_repository import (
    ProductBarcodeRepository,
    ProductRepository,
    ProductVariantRepository,
)
from modules.inventory.repositories.uom_repository import UOMRepository

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# State machine: allowed transitions per current status
# ---------------------------------------------------------------------------

_VALID_TRANSITIONS: dict[str, set[str]] = {
    "DRAFT": {"ACTIVE"},
    "ACTIVE": {"INACTIVE", "DISCONTINUED"},
    "INACTIVE": {"ACTIVE", "ARCHIVED"},
    "DISCONTINUED": {"ARCHIVED"},
    "ARCHIVED": set(),  # terminal state
}

_VALID_TYPES = frozenset({"STANDARD", "VARIANT", "SERVICE", "BUNDLE", "RAW_MATERIAL"})
_VALID_STATUSES = frozenset({"DRAFT", "ACTIVE", "INACTIVE", "DISCONTINUED", "ARCHIVED"})
_VALID_BARCODE_TYPES = frozenset({"EAN13", "EAN8", "QR", "CODE128", "CUSTOM"})


class ProductService:
    """Application service that orchestrates all Product domain operations."""

    def __init__(
        self,
        db: Session,
        product_repo: ProductRepository,
        variant_repo: ProductVariantRepository,
        barcode_repo: ProductBarcodeRepository,
        uom_repo: UOMRepository,
        event_bus: InProcessEventBus | None = None,
    ) -> None:
        self.db = db
        self._repo = product_repo
        self._variant_repo = variant_repo
        self._barcode_repo = barcode_repo
        self._uom_repo = uom_repo
        self._bus = event_bus or InProcessEventBus()

    # =========================================================================
    # Create Product (T065)
    # =========================================================================

    def create_product(
        self,
        company_id: UUID,
        product_code: str,
        name: str,
        product_type: str,
        base_uom_id: UUID,
        *,
        description: str | None = None,
        short_description: str | None = None,
        category_id: UUID | None = None,
        brand_id: UUID | None = None,
        hs_code: str | None = None,
        country_of_origin: str | None = None,
        lead_time_days: int | None = None,
        min_order_qty: float | None = None,
        max_order_qty: float | None = None,
        reorder_point: float | None = None,
        weight_kg: float | None = None,
        width_cm: float | None = None,
        height_cm: float | None = None,
        depth_cm: float | None = None,
        is_serialized: bool = False,
        is_batch_tracked: bool = False,
        cost_price: float | None = None,
        created_by: UUID | None = None,
    ) -> Product:
        """Create a new product in DRAFT status.

        Validates:
        - product_code unique per company
        - product_type is a known value
        - base_uom_id exists for this company
        """
        product_type = product_type.upper()
        if product_type not in _VALID_TYPES:
            raise ValueError(
                f"Invalid product_type '{product_type}'. "
                f"Must be one of {sorted(_VALID_TYPES)}."
            )

        # SKU uniqueness check
        if self._repo.sku_exists(company_id, product_code):
            raise SkuAlreadyExistsError(details={"sku": product_code})

        # UOM must exist
        uom = self._uom_repo.get_by_id(company_id=company_id, id=base_uom_id)
        if uom is None:
            raise UomNotFoundError(
                message=f"Unit of measure '{base_uom_id}' not found for this company."
            )

        product = Product(
            company_id=company_id,
            product_code=product_code.upper(),
            name=name,
            product_type=product_type,
            status="DRAFT",
            description=description,
            short_description=short_description,
            base_uom_id=str(base_uom_id),
            category_id=str(category_id) if category_id else None,
            brand_id=str(brand_id) if brand_id else None,
            hs_code=hs_code,
            country_of_origin=country_of_origin,
            lead_time_days=lead_time_days,
            min_order_qty=min_order_qty,
            max_order_qty=max_order_qty,
            reorder_point=reorder_point,
            weight_kg=weight_kg,
            width_cm=width_cm,
            height_cm=height_cm,
            depth_cm=depth_cm,
            is_serialized=is_serialized,
            is_batch_tracked=is_batch_tracked,
            cost_price=cost_price,
            created_by=created_by,
        )

        self._repo.refresh_search_vector(product)
        self.db.add(product)
        self.db.flush()
        # Missing-commit defect fixed during Epic 1-8 live verification
        # (2026-08-14) — see warehouse_service.py::create_warehouse's comment
        # for the full root-cause explanation.
        self.db.commit()

        self._bus.publish(
            ProductCreated(
                aggregate_id=product.id,
                company_id=company_id,
                product_code=product.product_code,
                product_name=product.name,
                product_type=product.product_type,
                category_id=str(product.category_id) if product.category_id else None,
                brand_id=str(product.brand_id) if product.brand_id else None,
            )
        )

        logger.info(
            "Product created: %s (%s) for company %s",
            product.name,
            product.product_code,
            company_id,
        )
        return product

    # =========================================================================
    # Update Product (T066)
    # =========================================================================

    def update_product(
        self,
        company_id: UUID,
        product_id: UUID,
        *,
        name: str | None = None,
        description: str | None = None,
        short_description: str | None = None,
        category_id: UUID | None = None,
        brand_id: UUID | None = None,
        hs_code: str | None = None,
        country_of_origin: str | None = None,
        lead_time_days: int | None = None,
        min_order_qty: float | None = None,
        max_order_qty: float | None = None,
        reorder_point: float | None = None,
        weight_kg: float | None = None,
        width_cm: float | None = None,
        height_cm: float | None = None,
        depth_cm: float | None = None,
        is_serialized: bool | None = None,
        is_batch_tracked: bool | None = None,
        cost_price: float | None = None,
    ) -> Product:
        """Update mutable product fields.

        product_code and product_type are immutable after creation.
        Status changes go through the lifecycle methods.
        """
        product = self._get_or_raise(company_id, product_id)

        if product.status == "ARCHIVED":
            raise InvalidProductStateTransitionError(
                message="Archived products cannot be modified."
            )

        changed_fields: list[str] = []

        if name is not None:
            product.name = name
            changed_fields.append("name")
        if description is not None:
            product.description = description
            changed_fields.append("description")
        if short_description is not None:
            product.short_description = short_description
            changed_fields.append("short_description")
        if category_id is not None:
            product.category_id = str(category_id)
            changed_fields.append("category_id")
        if brand_id is not None:
            product.brand_id = str(brand_id)
            changed_fields.append("brand_id")
        if hs_code is not None:
            product.hs_code = hs_code
            changed_fields.append("hs_code")
        if country_of_origin is not None:
            product.country_of_origin = country_of_origin
            changed_fields.append("country_of_origin")
        if lead_time_days is not None:
            product.lead_time_days = lead_time_days
            changed_fields.append("lead_time_days")
        if min_order_qty is not None:
            product.min_order_qty = min_order_qty
            changed_fields.append("min_order_qty")
        if max_order_qty is not None:
            product.max_order_qty = max_order_qty
            changed_fields.append("max_order_qty")
        if reorder_point is not None:
            product.reorder_point = reorder_point
            changed_fields.append("reorder_point")
        if weight_kg is not None:
            product.weight_kg = weight_kg
            changed_fields.append("weight_kg")
        if width_cm is not None:
            product.width_cm = width_cm
            changed_fields.append("width_cm")
        if height_cm is not None:
            product.height_cm = height_cm
            changed_fields.append("height_cm")
        if depth_cm is not None:
            product.depth_cm = depth_cm
            changed_fields.append("depth_cm")
        if is_serialized is not None:
            product.is_serialized = is_serialized
            changed_fields.append("is_serialized")
        if is_batch_tracked is not None:
            product.is_batch_tracked = is_batch_tracked
            changed_fields.append("is_batch_tracked")
        if cost_price is not None:
            product.cost_price = cost_price
            changed_fields.append("cost_price")

        # Refresh search vector if name or description changed
        if "name" in changed_fields or "description" in changed_fields:
            self._repo.refresh_search_vector(product)

        self.db.flush()
        # Missing-commit defect fixed during pre-Epic-9 hardening audit
        # (2026-08-14) — see warehouse_service.py::create_warehouse's comment
        # for the full root-cause explanation.
        self.db.commit()

        if changed_fields:
            self._bus.publish(
                ProductUpdated(
                    aggregate_id=product.id,
                    company_id=company_id,
                    changed_fields=changed_fields,
                )
            )

        return product

    # =========================================================================
    # Product Lifecycle (T067)
    # =========================================================================

    def _transition_status(self, product: Product, target: str) -> Product:
        """Apply a lifecycle state transition, enforcing the state machine."""
        allowed = _VALID_TRANSITIONS.get(product.status, set())
        if target not in allowed:
            raise InvalidProductStateTransitionError(
                message=(
                    f"Cannot transition product from '{product.status}' to '{target}'. "
                    f"Allowed targets from '{product.status}': {sorted(allowed) or 'none (terminal state)'}."
                ),
                details={"current_status": product.status, "target_status": target},
            )
        previous = product.status
        product.status = target
        self.db.flush()
        self.db.commit()

        _EVENT_CLS = {
            "ACTIVE": ProductActivated,
            "INACTIVE": ProductDeactivated,
            "ARCHIVED": ProductArchived,
            "DISCONTINUED": ProductDiscontinued,
        }
        event_cls = _EVENT_CLS.get(target)
        if event_cls is not None:
            evt_kwargs: dict = {
                "aggregate_id": product.id,
                "company_id": product.company_id,
            }
            if target in ("ACTIVE", "ARCHIVED"):
                evt_kwargs["previous_status"] = previous
            if hasattr(event_cls, "product_code"):
                evt_kwargs["product_code"] = product.product_code
            self._bus.publish(event_cls(**evt_kwargs))
        return product

    def activate_product(self, company_id: UUID, product_id: UUID) -> Product:
        """DRAFT → ACTIVE or INACTIVE → ACTIVE (reactivate).

        Guards: name, product_code, base_uom_id must be non-empty.
        """
        product = self._get_or_raise(company_id, product_id)

        if not product.name or not product.product_code or not product.base_uom_id:
            raise InvalidProductStateTransitionError(
                message="Product cannot be activated: name, product_code, and base_uom are required."
            )

        return self._transition_status(product, "ACTIVE")

    def deactivate_product(self, company_id: UUID, product_id: UUID) -> Product:
        """ACTIVE → INACTIVE."""
        product = self._get_or_raise(company_id, product_id)
        return self._transition_status(product, "INACTIVE")

    def discontinue_product(self, company_id: UUID, product_id: UUID) -> Product:
        """ACTIVE → DISCONTINUED."""
        product = self._get_or_raise(company_id, product_id)
        return self._transition_status(product, "DISCONTINUED")

    def archive_product(self, company_id: UUID, product_id: UUID) -> Product:
        """INACTIVE → ARCHIVED or DISCONTINUED → ARCHIVED (terminal)."""
        product = self._get_or_raise(company_id, product_id)
        return self._transition_status(product, "ARCHIVED")

    # =========================================================================
    # Soft-delete (T056 invariant)
    # =========================================================================

    def delete_product(self, company_id: UUID, product_id: UUID) -> None:
        """Soft-delete a product.

        Blocked for ARCHIVED products (they must remain in history).
        """
        product = self._get_or_raise(company_id, product_id)

        if product.status == "ARCHIVED":
            raise InvalidProductStateTransitionError(
                message="Archived products cannot be deleted."
            )

        from core.utils.datetime import utcnow

        product.is_deleted = True
        product.deleted_at = utcnow()
        self.db.flush()
        self.db.commit()

    # =========================================================================
    # Add Variant (T068)
    # =========================================================================

    def add_variant(
        self,
        company_id: UUID,
        product_id: UUID,
        variant_code: str,
        *,
        attributes: dict | None = None,
        is_stock_tracked: bool = True,
        created_by: UUID | None = None,
    ) -> ProductVariant:
        """Add a variant to a product.

        Validates variant_code (SKU) uniqueness within the company.
        """
        product = self._get_or_raise(company_id, product_id)

        if self._variant_repo.variant_sku_exists(company_id, variant_code):
            raise SkuAlreadyExistsError(
                message="A variant with this SKU already exists.",
                details={"variant_code": variant_code},
            )

        variant = ProductVariant(
            company_id=company_id,
            product_id=str(product.id),
            variant_code=variant_code.upper(),
            attributes=attributes or {},
            is_stock_tracked=is_stock_tracked,
            status="ACTIVE",
            created_by=created_by,
        )
        self.db.add(variant)
        self.db.flush()
        self.db.commit()

        self._bus.publish(
            ProductVariantCreated(
                aggregate_id=product.id,
                company_id=company_id,
                variant_id=str(variant.id),
                variant_code=variant.variant_code,
                product_code=product.product_code,
            )
        )

        return variant

    # =========================================================================
    # Barcode management (T058 / T073)
    # =========================================================================

    def add_barcode(
        self,
        company_id: UUID,
        product_id: UUID,
        barcode_value: str,
        barcode_type: str,
        *,
        is_primary: bool = False,
        variant_id: UUID | None = None,
        created_by: UUID | None = None,
    ) -> ProductBarcode:
        """Attach a barcode to a product or variant.

        Validates barcode uniqueness across the entire company.
        """
        self._get_or_raise(company_id, product_id)

        barcode_type = barcode_type.upper()
        if barcode_type not in _VALID_BARCODE_TYPES:
            raise ValueError(
                f"Invalid barcode_type '{barcode_type}'. "
                f"Must be one of {sorted(_VALID_BARCODE_TYPES)}."
            )

        if self._barcode_repo.get_by_value(company_id, barcode_value) is not None:
            raise BarcodeAlreadyExistsError(details={"barcode_value": barcode_value})

        barcode = ProductBarcode(
            company_id=company_id,
            product_id=str(product_id),
            variant_id=str(variant_id) if variant_id else None,
            barcode_value=barcode_value,
            barcode_type=barcode_type,
            is_primary=is_primary,
            created_by=created_by,
        )
        self.db.add(barcode)
        self.db.flush()
        self.db.commit()

        self._bus.publish(
            BarcodeAssigned(
                aggregate_id=product_id,
                company_id=company_id,
                barcode_value=barcode_value,
                barcode_type=barcode_type,
                variant_id=str(variant_id) if variant_id else None,
            )
        )

        return barcode

    def list_barcodes(
        self, company_id: UUID, product_id: UUID, *, variant_id: UUID | None = None
    ) -> list[ProductBarcode]:
        """List barcodes for a product or variant."""
        self._get_or_raise(company_id, product_id)
        return self._barcode_repo.list_for_product(
            company_id, product_id, variant_id=variant_id
        )

    def delete_barcode(
        self, company_id: UUID, product_id: UUID, barcode_id: UUID
    ) -> None:
        """Soft-delete a barcode."""
        barcode = self._barcode_repo.get_by_id(company_id=company_id, id=barcode_id)
        if barcode is None or barcode.product_id != str(product_id):
            raise ProductNotFoundError(message="Barcode not found.")

        from core.utils.datetime import utcnow

        barcode.is_deleted = True
        barcode.deleted_at = utcnow()
        self.db.flush()
        self.db.commit()

    # =========================================================================
    # Search & list (T069, T070)
    # =========================================================================

    def search_products(
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
        """Search / list products with optional FTS and filters."""
        return self._repo.search(
            company_id,
            query=query,
            status=status,
            product_type=product_type,
            category_id=category_id,
            brand_id=brand_id,
            page=page,
            page_size=page_size,
        )

    def get_product(self, company_id: UUID, product_id: UUID) -> Product:
        """Return a product by ID, raising ProductNotFoundError if not found."""
        return self._get_or_raise(company_id, product_id)

    def get_variants(self, company_id: UUID, product_id: UUID) -> list[ProductVariant]:
        """Return all active variants for a product."""
        self._get_or_raise(company_id, product_id)
        return self._variant_repo.list_for_product(company_id, product_id)

    # =========================================================================
    # Internal helpers
    # =========================================================================

    def _get_or_raise(self, company_id: UUID, product_id: UUID) -> Product:
        """Fetch a product or raise ProductNotFoundError."""
        try:
            product = self._repo.get_by_id(company_id=company_id, id=product_id)
        except Exception:
            raise ProductNotFoundError()
        if product is None:
            raise ProductNotFoundError()
        return product
