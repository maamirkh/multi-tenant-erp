"""Inventory models package — exports all ORM models for Alembic discovery."""

from modules.inventory.models.adjustment import InventoryAdjustment
from modules.inventory.models.alerts import (
    LowStockAlert,
    ReorderRule,
    ReorderSuggestion,
)
from modules.inventory.models.attribute import (
    AttributeDefinition,
    AttributeSet,
    AttributeSetMembership,
)
from modules.inventory.models.brand import Brand
from modules.inventory.models.category import Category
from modules.inventory.models.custom_field import CustomFieldDefinition
from modules.inventory.models.feature_flag import InventoryFeatureFlag
from modules.inventory.models.product import (
    Product,
    ProductBarcode,
    ProductImage,
    ProductVariant,
)
from modules.inventory.models.product_enrichment import (
    ImportJob,
    ProductCustomFieldValue,
    ProductInternalNote,
    ProductTag,
)
from modules.inventory.models.reason_code import ReasonCode
from modules.inventory.models.stock import (
    FIFOCostLayer,
    InventorySnapshot,
    InventorySnapshotLine,
    StockMovement,
    StockPosition,
)
from modules.inventory.models.tag import Tag
from modules.inventory.models.transfer import StockTransfer, StockTransferLine
from modules.inventory.models.uom import UOM, UOMConversion
from modules.inventory.models.warehouse import Warehouse, WarehouseLocation

__all__ = [
    "InventoryAdjustment",
    "AttributeDefinition",
    "AttributeSet",
    "AttributeSetMembership",
    "Brand",
    "Category",
    "CustomFieldDefinition",
    "ImportJob",
    "InventoryFeatureFlag",
    "Product",
    "ProductBarcode",
    "ProductCustomFieldValue",
    "ProductImage",
    "ProductInternalNote",
    "ProductTag",
    "ProductVariant",
    "ReasonCode",
    "Tag",
    "UOM",
    "UOMConversion",
    "FIFOCostLayer",
    "InventorySnapshot",
    "InventorySnapshotLine",
    "StockMovement",
    "StockPosition",
    "LowStockAlert",
    "ReorderRule",
    "ReorderSuggestion",
    "StockTransfer",
    "StockTransferLine",
    "Warehouse",
    "WarehouseLocation",
]
