"""Inventory module exception hierarchy.

All exceptions inherit from ``ApplicationException`` via the module-level
``InventoryException`` base so the global FastAPI exception handler converts
them to typed ``ErrorResponse`` JSON automatically.

No imports from SQLAlchemy, FastAPI, or Starlette — this module is pure Python.

Spec ref: specs/005-inventory-management/spec.md
"""

from __future__ import annotations

from core.exceptions.base import ApplicationException


class InventoryException(ApplicationException):
    """Base exception for all Inventory module errors."""

    def __init__(
        self,
        message: str,
        code: str = "INVENTORY_ERROR",
        details: dict[str, object] | None = None,
        http_status: int = 500,
    ) -> None:
        super().__init__(
            message=message,
            code=code,
            details=details,
            http_status=http_status,
        )


# ── 400 Bad Request ──────────────────────────────────────────────────────────


class InvalidSkuError(InventoryException):
    """SKU format is invalid or contains forbidden characters."""

    def __init__(
        self,
        message: str = "SKU format is invalid.",
        details: dict[str, object] | None = None,
    ) -> None:
        super().__init__(
            message=message, code="INVALID_SKU", details=details, http_status=400
        )


class InvalidBarcodeError(InventoryException):
    """Barcode format is invalid or unsupported."""

    def __init__(
        self,
        message: str = "Barcode format is invalid.",
        details: dict[str, object] | None = None,
    ) -> None:
        super().__init__(
            message=message, code="INVALID_BARCODE", details=details, http_status=400
        )


class InvalidStockQuantityError(InventoryException):
    """Stock quantity is negative when negative stock is not permitted."""

    def __init__(
        self,
        message: str = "Stock quantity cannot be negative.",
        details: dict[str, object] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            code="INVALID_STOCK_QUANTITY",
            details=details,
            http_status=400,
        )


class InvalidAdjustmentReasonError(InventoryException):
    """Adjustment reason code is not recognised."""

    def __init__(
        self,
        message: str = "Adjustment reason code is not recognised.",
        details: dict[str, object] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            code="INVALID_ADJUSTMENT_REASON",
            details=details,
            http_status=400,
        )


class InvalidTransferError(InventoryException):
    """Transfer source and destination warehouse are the same."""

    def __init__(
        self,
        message: str = "Source and destination warehouse must differ.",
        details: dict[str, object] | None = None,
    ) -> None:
        super().__init__(
            message=message, code="INVALID_TRANSFER", details=details, http_status=400
        )


# ── 403 Forbidden ────────────────────────────────────────────────────────────


class InventoryFeatureDisabledError(InventoryException):
    """The requested feature is disabled for this company."""

    def __init__(
        self,
        feature_key: str,
        message: str | None = None,
        details: dict[str, object] | None = None,
    ) -> None:
        super().__init__(
            message=message
            or f"Feature '{feature_key}' is not enabled for this company.",
            code="FEATURE_DISABLED",
            details=details or {"feature_key": feature_key},
            http_status=403,
        )


class InsufficientStockError(InventoryException):
    """Available stock is insufficient to fulfil the requested operation."""

    def __init__(
        self,
        message: str = "Insufficient stock to complete this operation.",
        details: dict[str, object] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            code="INSUFFICIENT_STOCK",
            details=details,
            http_status=409,
        )


# ── 404 Not Found ────────────────────────────────────────────────────────────


class ProductNotFoundError(InventoryException):
    """Requested product does not exist or belongs to a different company."""

    def __init__(
        self,
        message: str = "Product not found.",
        details: dict[str, object] | None = None,
    ) -> None:
        super().__init__(
            message=message, code="PRODUCT_NOT_FOUND", details=details, http_status=404
        )


class CategoryNotFoundError(InventoryException):
    """Requested product category does not exist."""

    def __init__(
        self,
        message: str = "Category not found.",
        details: dict[str, object] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            code="CATEGORY_NOT_FOUND",
            details=details,
            http_status=404,
        )


class BrandNotFoundError(InventoryException):
    """Requested brand does not exist."""

    def __init__(
        self,
        message: str = "Brand not found.",
        details: dict[str, object] | None = None,
    ) -> None:
        super().__init__(
            message=message, code="BRAND_NOT_FOUND", details=details, http_status=404
        )


class UomNotFoundError(InventoryException):
    """Requested unit of measure does not exist."""

    def __init__(
        self,
        message: str = "Unit of measure not found.",
        details: dict[str, object] | None = None,
    ) -> None:
        super().__init__(
            message=message, code="UOM_NOT_FOUND", details=details, http_status=404
        )


class TagNotFoundError(InventoryException):
    """Requested tag does not exist."""

    def __init__(
        self,
        message: str = "Tag not found.",
        details: dict[str, object] | None = None,
    ) -> None:
        super().__init__(
            message=message, code="TAG_NOT_FOUND", details=details, http_status=404
        )


class ReasonCodeNotFoundError(InventoryException):
    """Requested reason code does not exist."""

    def __init__(
        self,
        message: str = "Reason code not found.",
        details: dict[str, object] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            code="REASON_CODE_NOT_FOUND",
            details=details,
            http_status=404,
        )


class CustomFieldNotFoundError(InventoryException):
    """Requested custom field definition does not exist."""

    def __init__(
        self,
        message: str = "Custom field definition not found.",
        details: dict[str, object] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            code="CUSTOM_FIELD_NOT_FOUND",
            details=details,
            http_status=404,
        )


class AttributeNotFoundError(InventoryException):
    """Requested attribute definition does not exist."""

    def __init__(
        self,
        message: str = "Attribute definition not found.",
        details: dict[str, object] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            code="ATTRIBUTE_NOT_FOUND",
            details=details,
            http_status=404,
        )


class AttributeSetNotFoundError(InventoryException):
    """Requested attribute set does not exist."""

    def __init__(
        self,
        message: str = "Attribute set not found.",
        details: dict[str, object] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            code="ATTRIBUTE_SET_NOT_FOUND",
            details=details,
            http_status=404,
        )


class WarehouseNotFoundError(InventoryException):
    """Requested warehouse does not exist."""

    def __init__(
        self,
        message: str = "Warehouse not found.",
        details: dict[str, object] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            code="WAREHOUSE_NOT_FOUND",
            details=details,
            http_status=404,
        )


class StockPositionNotFoundError(InventoryException):
    """No stock position record exists for the given product/warehouse combination."""

    def __init__(
        self,
        message: str = "Stock position not found.",
        details: dict[str, object] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            code="STOCK_POSITION_NOT_FOUND",
            details=details,
            http_status=404,
        )


class AdjustmentNotFoundError(InventoryException):
    """Requested stock adjustment does not exist."""

    def __init__(
        self,
        message: str = "Stock adjustment not found.",
        details: dict[str, object] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            code="ADJUSTMENT_NOT_FOUND",
            details=details,
            http_status=404,
        )


class TransferNotFoundError(InventoryException):
    """Requested stock transfer does not exist."""

    def __init__(
        self,
        message: str = "Stock transfer not found.",
        details: dict[str, object] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            code="TRANSFER_NOT_FOUND",
            details=details,
            http_status=404,
        )


# ── 409 Conflict ─────────────────────────────────────────────────────────────


class SkuAlreadyExistsError(InventoryException):
    """SKU is already in use within this company."""

    def __init__(
        self,
        message: str = "A product with this SKU already exists.",
        details: dict[str, object] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            code="SKU_ALREADY_EXISTS",
            details=details,
            http_status=409,
        )


class BarcodeAlreadyExistsError(InventoryException):
    """Barcode is already assigned to another product in this company."""

    def __init__(
        self,
        message: str = "This barcode is already assigned to another product.",
        details: dict[str, object] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            code="BARCODE_ALREADY_EXISTS",
            details=details,
            http_status=409,
        )


class CategoryNameConflictError(InventoryException):
    """Category name already exists under the same parent in this company."""

    def __init__(
        self,
        message: str = "A category with this name already exists.",
        details: dict[str, object] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            code="CATEGORY_NAME_CONFLICT",
            details=details,
            http_status=409,
        )


class BrandCodeConflictError(InventoryException):
    """Brand code already exists within this company."""

    def __init__(
        self,
        message: str = "A brand with this code already exists.",
        details: dict[str, object] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            code="BRAND_CODE_CONFLICT",
            details=details,
            http_status=409,
        )


class UomCodeConflictError(InventoryException):
    """UOM code already exists within this company."""

    def __init__(
        self,
        message: str = "A unit of measure with this code already exists.",
        details: dict[str, object] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            code="UOM_CODE_CONFLICT",
            details=details,
            http_status=409,
        )


class UomConversionConflictError(InventoryException):
    """A conversion between this source/target UOM pair already exists."""

    def __init__(
        self,
        message: str = "A conversion between these units already exists.",
        details: dict[str, object] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            code="UOM_CONVERSION_CONFLICT",
            details=details,
            http_status=409,
        )


class TagNameConflictError(InventoryException):
    """Tag name already exists within this company."""

    def __init__(
        self,
        message: str = "A tag with this name already exists.",
        details: dict[str, object] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            code="TAG_NAME_CONFLICT",
            details=details,
            http_status=409,
        )


class ReasonCodeConflictError(InventoryException):
    """Reason code already exists within this company."""

    def __init__(
        self,
        message: str = "A reason code with this code already exists.",
        details: dict[str, object] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            code="REASON_CODE_CONFLICT",
            details=details,
            http_status=409,
        )


class CustomFieldKeyConflictError(InventoryException):
    """Custom field key already exists for this entity type within this company."""

    def __init__(
        self,
        message: str = "A custom field with this key already exists for this entity type.",
        details: dict[str, object] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            code="CUSTOM_FIELD_KEY_CONFLICT",
            details=details,
            http_status=409,
        )


class AttributeNameConflictError(InventoryException):
    """Attribute definition name already exists within this company."""

    def __init__(
        self,
        message: str = "An attribute with this name already exists.",
        details: dict[str, object] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            code="ATTRIBUTE_NAME_CONFLICT",
            details=details,
            http_status=409,
        )


class AttributeSetNameConflictError(InventoryException):
    """Attribute set name already exists within this company."""

    def __init__(
        self,
        message: str = "An attribute set with this name already exists.",
        details: dict[str, object] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            code="ATTRIBUTE_SET_NAME_CONFLICT",
            details=details,
            http_status=409,
        )


class WarehouseCodeConflictError(InventoryException):
    """Warehouse code already exists within this company."""

    def __init__(
        self,
        message: str = "A warehouse with this code already exists.",
        details: dict[str, object] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            code="WAREHOUSE_CODE_CONFLICT",
            details=details,
            http_status=409,
        )


class InvalidProductStateTransitionError(InventoryException):
    """Requested product lifecycle state change is not permitted."""

    def __init__(
        self,
        message: str = "This product state transition is not permitted.",
        details: dict[str, object] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            code="INVALID_PRODUCT_STATE_TRANSITION",
            details=details,
            http_status=409,
        )


class InvalidAdjustmentStateTransitionError(InventoryException):
    """Requested adjustment state change is not permitted from the current state."""

    def __init__(
        self,
        message: str = "This adjustment state transition is not permitted.",
        details: dict[str, object] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            code="INVALID_ADJUSTMENT_STATE_TRANSITION",
            details=details,
            http_status=409,
        )


class InvalidTransferStateTransitionError(InventoryException):
    """Requested transfer state change is not permitted from the current state."""

    def __init__(
        self,
        message: str = "This transfer state transition is not permitted.",
        details: dict[str, object] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            code="INVALID_TRANSFER_STATE_TRANSITION",
            details=details,
            http_status=409,
        )


# ── 422 Unprocessable Entity ─────────────────────────────────────────────────


class ReorderLevelExceedsMaxStockError(InventoryException):
    """Reorder level is set above the maximum stock level."""

    def __init__(
        self,
        message: str = "Reorder level cannot exceed maximum stock level.",
        details: dict[str, object] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            code="REORDER_LEVEL_EXCEEDS_MAX_STOCK",
            details=details,
            http_status=422,
        )


class MinStockExceedsMaxStockError(InventoryException):
    """Minimum stock level is set above the maximum stock level."""

    def __init__(
        self,
        message: str = "Minimum stock level cannot exceed maximum stock level.",
        details: dict[str, object] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            code="MIN_STOCK_EXCEEDS_MAX_STOCK",
            details=details,
            http_status=422,
        )
