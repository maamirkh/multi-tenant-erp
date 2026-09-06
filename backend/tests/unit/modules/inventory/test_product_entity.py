"""Unit tests for Product and ProductVariant entities.

Tests the Product domain model and ProductService business logic
without hitting the database (no DB fixtures required).

Task: T079, T080
"""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock

import pytest

from modules.inventory.exceptions import (
    BarcodeAlreadyExistsError,
    InvalidProductStateTransitionError,
    ProductNotFoundError,
    SkuAlreadyExistsError,
    UomNotFoundError,
)
from modules.inventory.models.product import Product
from modules.inventory.repositories.product_repository import (
    ProductBarcodeRepository,
    ProductRepository,
    ProductVariantRepository,
)
from modules.inventory.repositories.uom_repository import UOMRepository
from modules.inventory.services.product_service import (
    _VALID_TRANSITIONS,
    ProductService,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_company_id() -> uuid.UUID:
    return uuid.uuid4()


def _make_product(
    *,
    status: str = "DRAFT",
    product_type: str = "STANDARD",
    product_code: str = "PROD-001",
    name: str = "Test Product",
) -> Product:
    company_id = _make_company_id()
    p = Product(
        id=uuid.uuid4(),
        company_id=company_id,
        product_code=product_code,
        name=name,
        product_type=product_type,
        status=status,
        base_uom_id=str(uuid.uuid4()),
    )
    return p


def _make_service(
    *,
    product: Product | None = None,
    sku_exists: bool = False,
    barcode_exists: bool = False,
    variant_sku_exists: bool = False,
) -> tuple[ProductService, MagicMock, MagicMock, MagicMock]:
    """Build a ProductService with mocked repositories."""
    db = MagicMock()

    product_repo = MagicMock(spec=ProductRepository)
    product_repo.get_by_id.return_value = product
    product_repo.sku_exists.return_value = sku_exists
    product_repo.build_search_vector.return_value = "test product"
    product_repo.refresh_search_vector.return_value = None

    variant_repo = MagicMock(spec=ProductVariantRepository)
    variant_repo.variant_sku_exists.return_value = variant_sku_exists

    barcode_repo = MagicMock(spec=ProductBarcodeRepository)
    barcode_repo.get_by_value.return_value = None if not barcode_exists else MagicMock()

    uom_repo = MagicMock(spec=UOMRepository)
    uom_repo.get_by_id.return_value = MagicMock()  # UOM exists

    svc = ProductService(
        db=db,
        product_repo=product_repo,
        variant_repo=variant_repo,
        barcode_repo=barcode_repo,
        uom_repo=uom_repo,
    )
    return svc, product_repo, variant_repo, barcode_repo


# =============================================================================
# State machine tests (T054, T055)
# =============================================================================


class TestProductStateMachine:
    """Verify all valid and invalid status transitions."""

    def test_state_machine_allows_draft_to_active(self) -> None:
        assert "ACTIVE" in _VALID_TRANSITIONS["DRAFT"]

    def test_state_machine_allows_active_to_inactive(self) -> None:
        assert "INACTIVE" in _VALID_TRANSITIONS["ACTIVE"]

    def test_state_machine_allows_active_to_discontinued(self) -> None:
        assert "DISCONTINUED" in _VALID_TRANSITIONS["ACTIVE"]

    def test_state_machine_allows_inactive_to_active(self) -> None:
        assert "ACTIVE" in _VALID_TRANSITIONS["INACTIVE"]

    def test_state_machine_allows_inactive_to_archived(self) -> None:
        assert "ARCHIVED" in _VALID_TRANSITIONS["INACTIVE"]

    def test_state_machine_allows_discontinued_to_archived(self) -> None:
        assert "ARCHIVED" in _VALID_TRANSITIONS["DISCONTINUED"]

    def test_archived_is_terminal(self) -> None:
        assert _VALID_TRANSITIONS["ARCHIVED"] == set()

    def test_draft_cannot_go_to_discontinued(self) -> None:
        assert "DISCONTINUED" not in _VALID_TRANSITIONS["DRAFT"]

    def test_draft_cannot_go_to_archived(self) -> None:
        assert "ARCHIVED" not in _VALID_TRANSITIONS["DRAFT"]

    def test_active_cannot_go_to_archived_directly(self) -> None:
        assert "ARCHIVED" not in _VALID_TRANSITIONS["ACTIVE"]

    def test_activate_product_transitions_draft_to_active(self) -> None:
        product = _make_product(status="DRAFT")
        svc, product_repo, _, _ = _make_service(product=product)
        result = svc.activate_product(product.company_id, product.id)
        assert result.status == "ACTIVE"

    def test_activate_product_transitions_inactive_to_active(self) -> None:
        product = _make_product(status="INACTIVE")
        svc, _, _, _ = _make_service(product=product)
        result = svc.activate_product(product.company_id, product.id)
        assert result.status == "ACTIVE"

    def test_deactivate_product(self) -> None:
        product = _make_product(status="ACTIVE")
        svc, _, _, _ = _make_service(product=product)
        result = svc.deactivate_product(product.company_id, product.id)
        assert result.status == "INACTIVE"

    def test_discontinue_product(self) -> None:
        product = _make_product(status="ACTIVE")
        svc, _, _, _ = _make_service(product=product)
        result = svc.discontinue_product(product.company_id, product.id)
        assert result.status == "DISCONTINUED"

    def test_archive_from_inactive(self) -> None:
        product = _make_product(status="INACTIVE")
        svc, _, _, _ = _make_service(product=product)
        result = svc.archive_product(product.company_id, product.id)
        assert result.status == "ARCHIVED"

    def test_archive_from_discontinued(self) -> None:
        product = _make_product(status="DISCONTINUED")
        svc, _, _, _ = _make_service(product=product)
        result = svc.archive_product(product.company_id, product.id)
        assert result.status == "ARCHIVED"

    def test_invalid_transition_raises_error(self) -> None:
        product = _make_product(status="DRAFT")
        svc, _, _, _ = _make_service(product=product)
        with pytest.raises(InvalidProductStateTransitionError):
            svc.deactivate_product(product.company_id, product.id)

    def test_archived_to_active_raises_error(self) -> None:
        product = _make_product(status="ARCHIVED")
        svc, _, _, _ = _make_service(product=product)
        with pytest.raises(InvalidProductStateTransitionError):
            svc.activate_product(product.company_id, product.id)

    def test_activate_raises_when_product_not_found(self) -> None:
        svc, _, _, _ = _make_service(product=None)
        with pytest.raises(ProductNotFoundError):
            svc.activate_product(uuid.uuid4(), uuid.uuid4())


# =============================================================================
# SKU uniqueness invariant (T056)
# =============================================================================


class TestSkuUniqueness:
    def test_create_product_raises_on_duplicate_sku(self) -> None:
        svc, _, _, _ = _make_service(sku_exists=True)
        with pytest.raises(SkuAlreadyExistsError):
            svc.create_product(
                company_id=uuid.uuid4(),
                product_code="DUPE-001",
                name="Duplicate",
                product_type="STANDARD",
                base_uom_id=uuid.uuid4(),
            )

    def test_create_product_succeeds_with_unique_sku(self) -> None:
        svc, product_repo, _, _ = _make_service(sku_exists=False)
        product_repo.get_by_id.return_value = None
        svc.db.add.return_value = None
        svc.db.flush.return_value = None

        product = svc.create_product(
            company_id=uuid.uuid4(),
            product_code="NEW-001",
            name="New Product",
            product_type="STANDARD",
            base_uom_id=uuid.uuid4(),
        )
        assert product.product_code == "NEW-001"

    def test_product_code_normalised_to_uppercase(self) -> None:
        svc, _, _, _ = _make_service(sku_exists=False)
        svc.db.add.return_value = None
        svc.db.flush.return_value = None
        product = svc.create_product(
            company_id=uuid.uuid4(),
            product_code="abc-001",
            name="Test",
            product_type="STANDARD",
            base_uom_id=uuid.uuid4(),
        )
        assert product.product_code == "ABC-001"


# =============================================================================
# Barcode uniqueness invariant (T056)
# =============================================================================


class TestBarcodeUniqueness:
    def test_add_barcode_raises_on_duplicate(self) -> None:
        product = _make_product(status="ACTIVE")
        svc, _, _, _ = _make_service(product=product, barcode_exists=True)
        with pytest.raises(BarcodeAlreadyExistsError):
            svc.add_barcode(
                company_id=product.company_id,
                product_id=product.id,
                barcode_value="1234567890123",
                barcode_type="EAN13",
            )

    def test_add_barcode_succeeds_with_unique_value(self) -> None:
        product = _make_product(status="ACTIVE")
        svc, _, _, barcode_repo = _make_service(product=product, barcode_exists=False)
        svc.db.add.return_value = None
        svc.db.flush.return_value = None
        barcode = svc.add_barcode(
            company_id=product.company_id,
            product_id=product.id,
            barcode_value="1234567890123",
            barcode_type="EAN13",
        )
        assert barcode.barcode_value == "1234567890123"

    def test_add_barcode_invalid_type_raises(self) -> None:
        product = _make_product(status="ACTIVE")
        svc, _, _, _ = _make_service(product=product)
        with pytest.raises(ValueError, match="barcode_type"):
            svc.add_barcode(
                company_id=product.company_id,
                product_id=product.id,
                barcode_value="123",
                barcode_type="INVALID_TYPE",
            )


# =============================================================================
# Activation guard (T056)
# =============================================================================


class TestActivationGuard:
    def test_activate_raises_when_name_missing(self) -> None:
        product = _make_product(status="DRAFT", name="")
        svc, _, _, _ = _make_service(product=product)
        with pytest.raises(InvalidProductStateTransitionError):
            svc.activate_product(product.company_id, product.id)

    def test_activate_raises_when_product_code_missing(self) -> None:
        product = _make_product(status="DRAFT", product_code="")
        svc, _, _, _ = _make_service(product=product)
        with pytest.raises(InvalidProductStateTransitionError):
            svc.activate_product(product.company_id, product.id)


# =============================================================================
# Delete invariant — blocked for ARCHIVED (T056)
# =============================================================================


class TestDeleteGuard:
    def test_delete_blocked_for_archived_product(self) -> None:
        product = _make_product(status="ARCHIVED")
        svc, _, _, _ = _make_service(product=product)
        with pytest.raises(InvalidProductStateTransitionError, match="Archived"):
            svc.delete_product(product.company_id, product.id)

    def test_delete_allowed_for_draft_product(self) -> None:
        product = _make_product(status="DRAFT")
        svc, _, _, _ = _make_service(product=product)
        svc.db.flush.return_value = None
        svc.delete_product(product.company_id, product.id)
        assert product.is_deleted is True

    def test_update_blocked_for_archived_product(self) -> None:
        product = _make_product(status="ARCHIVED")
        svc, _, _, _ = _make_service(product=product)
        with pytest.raises(InvalidProductStateTransitionError, match="Archived"):
            svc.update_product(product.company_id, product.id, name="New Name")


# =============================================================================
# Product type validation (T054)
# =============================================================================


class TestProductTypeValidation:
    @pytest.mark.parametrize(
        "ptype", ["STANDARD", "VARIANT", "SERVICE", "BUNDLE", "RAW_MATERIAL"]
    )
    def test_valid_product_types_accepted(self, ptype: str) -> None:
        svc, _, _, _ = _make_service(sku_exists=False)
        svc.db.add.return_value = None
        svc.db.flush.return_value = None
        product = svc.create_product(
            company_id=uuid.uuid4(),
            product_code=f"{ptype}-001",
            name="Test",
            product_type=ptype,
            base_uom_id=uuid.uuid4(),
        )
        assert product.product_type == ptype

    def test_invalid_product_type_raises(self) -> None:
        svc, _, _, _ = _make_service(sku_exists=False)
        with pytest.raises(ValueError, match="product_type"):
            svc.create_product(
                company_id=uuid.uuid4(),
                product_code="BAD-001",
                name="Test",
                product_type="INVALID",
                base_uom_id=uuid.uuid4(),
            )


# =============================================================================
# UOM validation (T054)
# =============================================================================


class TestUomValidation:
    def test_create_raises_when_uom_not_found(self) -> None:
        svc, _, _, _ = _make_service(sku_exists=False)
        svc._uom_repo.get_by_id.return_value = None
        with pytest.raises(UomNotFoundError):
            svc.create_product(
                company_id=uuid.uuid4(),
                product_code="PROD-001",
                name="Test",
                product_type="STANDARD",
                base_uom_id=uuid.uuid4(),
            )


# =============================================================================
# Variant management (T057, T068, T080)
# =============================================================================


class TestVariantManagement:
    def test_add_variant_raises_on_duplicate_sku(self) -> None:
        product = _make_product(status="ACTIVE")
        svc, _, _, _ = _make_service(product=product, variant_sku_exists=True)
        with pytest.raises(SkuAlreadyExistsError):
            svc.add_variant(
                company_id=product.company_id,
                product_id=product.id,
                variant_code="DUPE-VAR-001",
            )

    def test_add_variant_succeeds_with_unique_code(self) -> None:
        product = _make_product(status="ACTIVE")
        svc, _, _, _ = _make_service(product=product, variant_sku_exists=False)
        svc.db.add.return_value = None
        svc.db.flush.return_value = None
        variant = svc.add_variant(
            company_id=product.company_id,
            product_id=product.id,
            variant_code="VAR-001",
            attributes={"size": "L", "colour": "Red"},
        )
        assert variant.variant_code == "VAR-001"
        assert variant.attributes == {"size": "L", "colour": "Red"}

    def test_add_variant_normalises_code_to_uppercase(self) -> None:
        product = _make_product(status="ACTIVE")
        svc, _, _, _ = _make_service(product=product, variant_sku_exists=False)
        svc.db.add.return_value = None
        svc.db.flush.return_value = None
        variant = svc.add_variant(
            company_id=product.company_id,
            product_id=product.id,
            variant_code="var-001",
        )
        assert variant.variant_code == "VAR-001"

    def test_add_variant_raises_when_product_not_found(self) -> None:
        svc, _, _, _ = _make_service(product=None)
        with pytest.raises(ProductNotFoundError):
            svc.add_variant(
                company_id=uuid.uuid4(),
                product_id=uuid.uuid4(),
                variant_code="VAR-001",
            )

    def test_variant_has_stock_tracking_enabled_by_default(self) -> None:
        product = _make_product(status="ACTIVE")
        svc, _, _, _ = _make_service(product=product, variant_sku_exists=False)
        svc.db.add.return_value = None
        svc.db.flush.return_value = None
        variant = svc.add_variant(
            company_id=product.company_id,
            product_id=product.id,
            variant_code="VAR-002",
        )
        assert variant.is_stock_tracked is True

    def test_variant_stock_tracking_can_be_disabled(self) -> None:
        product = _make_product(status="ACTIVE")
        svc, _, _, _ = _make_service(product=product, variant_sku_exists=False)
        svc.db.add.return_value = None
        svc.db.flush.return_value = None
        variant = svc.add_variant(
            company_id=product.company_id,
            product_id=product.id,
            variant_code="VAR-003",
            is_stock_tracked=False,
        )
        assert variant.is_stock_tracked is False


# =============================================================================
# Search vector (T064)
# =============================================================================


class TestSearchVector:
    def test_build_search_vector_includes_name(self) -> None:
        product = _make_product(name="Samsung Galaxy S24")
        from modules.inventory.repositories.product_repository import ProductRepository

        vector = ProductRepository.build_search_vector(product)
        assert "samsung" in vector
        assert "galaxy" in vector

    def test_build_search_vector_includes_product_code(self) -> None:
        product = _make_product(product_code="SAMSUNG-S24")
        vector = ProductRepository.build_search_vector(product)
        assert "samsung-s24" in vector.lower()

    def test_build_search_vector_is_lowercase(self) -> None:
        product = _make_product(name="Test PRODUCT CODE")
        vector = ProductRepository.build_search_vector(product)
        assert vector == vector.lower()

    def test_build_search_vector_handles_null_description(self) -> None:
        product = _make_product()
        product.description = None
        vector = ProductRepository.build_search_vector(product)
        assert isinstance(vector, str)
