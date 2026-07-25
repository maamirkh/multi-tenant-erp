"""Integration tests for ProductRepository, ProductVariantRepository, ProductBarcodeRepository.

Tests: FTS search, barcode lookup, SKU lookup, company isolation, soft-delete, status filter.

Task: T081
"""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from modules.inventory.models.product import Product, ProductBarcode, ProductVariant
from modules.inventory.models.uom import UOM
from modules.inventory.repositories.product_repository import (
    ProductBarcodeRepository,
    ProductRepository,
    ProductVariantRepository,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_uom(db: Session, company_id: uuid.UUID) -> UOM:
    uom = UOM(
        company_id=company_id,
        code="PCS",
        name="Pieces",
        uom_type="UNIT",
        status="active",
    )
    db.add(uom)
    db.flush()
    return uom


def _make_product(
    db: Session,
    company_id: uuid.UUID,
    uom: UOM,
    *,
    product_code: str = "PROD-001",
    name: str = "Test Product",
    status: str = "DRAFT",
    product_type: str = "STANDARD",
    description: str | None = None,
) -> Product:
    p = Product(
        company_id=company_id,
        product_code=product_code,
        name=name,
        product_type=product_type,
        status=status,
        base_uom_id=str(uom.id),
        description=description,
    )
    p.search_vector = ProductRepository.build_search_vector(p)
    db.add(p)
    db.flush()
    return p


def _make_variant(
    db: Session,
    product: Product,
    variant_code: str = "VAR-001",
) -> ProductVariant:
    v = ProductVariant(
        company_id=product.company_id,
        product_id=str(product.id),
        variant_code=variant_code,
        attributes={"size": "L"},
        is_stock_tracked=True,
        status="ACTIVE",
    )
    db.add(v)
    db.flush()
    return v


def _make_barcode(
    db: Session,
    product: Product,
    barcode_value: str = "1234567890123",
    barcode_type: str = "EAN13",
) -> ProductBarcode:
    b = ProductBarcode(
        company_id=product.company_id,
        product_id=str(product.id),
        barcode_value=barcode_value,
        barcode_type=barcode_type,
        is_primary=True,
    )
    db.add(b)
    db.flush()
    return b


# =============================================================================
# ProductRepository tests (T081)
# =============================================================================


class TestProductRepositoryCRUD:
    def test_create_and_get_by_id(self, db_session: Session) -> None:
        company_id = uuid.uuid4()
        uom = _make_uom(db_session, company_id)
        repo = ProductRepository(db_session)

        product = _make_product(db_session, company_id, uom)
        fetched = repo.get_by_id(company_id=company_id, id=product.id)

        assert fetched is not None
        assert fetched.product_code == "PROD-001"

    def test_get_by_id_wrong_company_returns_none(self, db_session: Session) -> None:
        company_id = uuid.uuid4()
        uom = _make_uom(db_session, company_id)
        repo = ProductRepository(db_session)
        product = _make_product(db_session, company_id, uom)

        other_company = uuid.uuid4()
        fetched = repo.get_by_id_or_none(company_id=other_company, id=product.id)
        assert fetched is None

    def test_get_by_code(self, db_session: Session) -> None:
        company_id = uuid.uuid4()
        uom = _make_uom(db_session, company_id)
        repo = ProductRepository(db_session)
        _make_product(db_session, company_id, uom, product_code="ABC-001")

        result = repo.get_by_code(company_id=company_id, product_code="ABC-001")
        assert result is not None
        assert result.product_code == "ABC-001"

    def test_get_by_code_case_insensitive(self, db_session: Session) -> None:
        company_id = uuid.uuid4()
        uom = _make_uom(db_session, company_id)
        repo = ProductRepository(db_session)
        _make_product(db_session, company_id, uom, product_code="UPPER-001")

        result = repo.get_by_code(company_id=company_id, product_code="upper-001")
        assert result is not None

    def test_get_by_code_unknown_returns_none(self, db_session: Session) -> None:
        company_id = uuid.uuid4()
        repo = ProductRepository(db_session)
        result = repo.get_by_code(company_id=company_id, product_code="NO-SUCH-CODE")
        assert result is None

    def test_soft_delete_hides_product(self, db_session: Session) -> None:
        company_id = uuid.uuid4()
        uom = _make_uom(db_session, company_id)
        repo = ProductRepository(db_session)
        product = _make_product(db_session, company_id, uom)

        product.is_deleted = True
        db_session.flush()

        result = repo.get_by_id_or_none(company_id=company_id, id=product.id)
        assert result is None


class TestProductRepositorySKUExists:
    def test_sku_exists_true_for_existing_product_code(
        self, db_session: Session
    ) -> None:
        company_id = uuid.uuid4()
        uom = _make_uom(db_session, company_id)
        repo = ProductRepository(db_session)
        _make_product(db_session, company_id, uom, product_code="EXIST-001")

        assert repo.sku_exists(company_id, "EXIST-001") is True

    def test_sku_exists_false_for_other_company(self, db_session: Session) -> None:
        company_a = uuid.uuid4()
        company_b = uuid.uuid4()
        uom_a = _make_uom(db_session, company_a)
        repo = ProductRepository(db_session)
        _make_product(db_session, company_a, uom_a, product_code="CROSS-001")

        assert repo.sku_exists(company_b, "CROSS-001") is False

    def test_sku_exists_false_for_unknown_code(self, db_session: Session) -> None:
        company_id = uuid.uuid4()
        repo = ProductRepository(db_session)
        assert repo.sku_exists(company_id, "NOTEXIST") is False


class TestProductRepositorySearch:
    def test_search_by_name(self, db_session: Session) -> None:
        company_id = uuid.uuid4()
        uom = _make_uom(db_session, company_id)
        repo = ProductRepository(db_session)
        _make_product(db_session, company_id, uom, name="Samsung Galaxy Phone")
        _make_product(
            db_session, company_id, uom, product_code="IPHONE-001", name="Apple iPhone"
        )

        items, total = repo.search(company_id, query="samsung")
        assert total == 1
        assert items[0].name == "Samsung Galaxy Phone"

    def test_search_by_product_code(self, db_session: Session) -> None:
        company_id = uuid.uuid4()
        uom = _make_uom(db_session, company_id)
        repo = ProductRepository(db_session)
        _make_product(db_session, company_id, uom, product_code="UNIQUE-CODE-XYZ")

        items, total = repo.search(company_id, query="UNIQUE-CODE-XYZ")
        assert total == 1
        assert items[0].product_code == "UNIQUE-CODE-XYZ"

    def test_search_filters_by_status(self, db_session: Session) -> None:
        company_id = uuid.uuid4()
        uom = _make_uom(db_session, company_id)
        repo = ProductRepository(db_session)
        _make_product(
            db_session, company_id, uom, product_code="ACTIVE-001", status="ACTIVE"
        )
        _make_product(
            db_session, company_id, uom, product_code="DRAFT-001", status="DRAFT"
        )

        items, total = repo.search(company_id, status="ACTIVE")
        assert total == 1
        assert items[0].product_code == "ACTIVE-001"

    def test_search_filters_by_product_type(self, db_session: Session) -> None:
        company_id = uuid.uuid4()
        uom = _make_uom(db_session, company_id)
        repo = ProductRepository(db_session)
        _make_product(
            db_session, company_id, uom, product_code="STD-001", product_type="STANDARD"
        )
        _make_product(
            db_session, company_id, uom, product_code="SVC-001", product_type="SERVICE"
        )

        items, total = repo.search(company_id, product_type="SERVICE")
        assert total == 1
        assert items[0].product_code == "SVC-001"

    def test_search_returns_all_when_no_filters(self, db_session: Session) -> None:
        company_id = uuid.uuid4()
        uom = _make_uom(db_session, company_id)
        repo = ProductRepository(db_session)
        for i in range(3):
            _make_product(db_session, company_id, uom, product_code=f"P{i:03d}")

        items, total = repo.search(company_id)
        assert total == 3

    def test_search_pagination(self, db_session: Session) -> None:
        company_id = uuid.uuid4()
        uom = _make_uom(db_session, company_id)
        repo = ProductRepository(db_session)
        for i in range(5):
            _make_product(db_session, company_id, uom, product_code=f"P{i:03d}")

        items, total = repo.search(company_id, page=1, page_size=2)
        assert total == 5
        assert len(items) == 2

    def test_search_excludes_deleted_products(self, db_session: Session) -> None:
        company_id = uuid.uuid4()
        uom = _make_uom(db_session, company_id)
        repo = ProductRepository(db_session)
        product = _make_product(db_session, company_id, uom, product_code="DELETED-001")
        product.is_deleted = True
        db_session.flush()

        _, total = repo.search(company_id)
        assert total == 0

    def test_search_tenant_isolation(self, db_session: Session) -> None:
        company_a = uuid.uuid4()
        company_b = uuid.uuid4()
        uom_a = _make_uom(db_session, company_a)
        uom_b = _make_uom(db_session, company_b)
        repo = ProductRepository(db_session)

        _make_product(db_session, company_a, uom_a, product_code="A-001")
        _make_product(db_session, company_b, uom_b, product_code="B-001")

        items_a, total_a = repo.search(company_a)
        items_b, total_b = repo.search(company_b)

        assert total_a == 1
        assert items_a[0].product_code == "A-001"
        assert total_b == 1
        assert items_b[0].product_code == "B-001"


# =============================================================================
# ProductVariantRepository tests (T081)
# =============================================================================


class TestProductVariantRepository:
    def test_create_and_list_variants(self, db_session: Session) -> None:
        company_id = uuid.uuid4()
        uom = _make_uom(db_session, company_id)
        repo = ProductVariantRepository(db_session)
        product = _make_product(db_session, company_id, uom)

        _make_variant(db_session, product, "VAR-001")
        _make_variant(db_session, product, "VAR-002")

        variants = repo.list_for_product(company_id, product.id)
        assert len(variants) == 2

    def test_get_variant_by_code(self, db_session: Session) -> None:
        company_id = uuid.uuid4()
        uom = _make_uom(db_session, company_id)
        repo = ProductVariantRepository(db_session)
        product = _make_product(db_session, company_id, uom)
        _make_variant(db_session, product, "VARIANT-XYZ")

        result = repo.get_by_code(company_id, "VARIANT-XYZ")
        assert result is not None
        assert result.variant_code == "VARIANT-XYZ"

    def test_variant_sku_exists(self, db_session: Session) -> None:
        company_id = uuid.uuid4()
        uom = _make_uom(db_session, company_id)
        repo = ProductVariantRepository(db_session)
        product = _make_product(db_session, company_id, uom)
        _make_variant(db_session, product, "EXIST-VAR")

        assert repo.variant_sku_exists(company_id, "EXIST-VAR") is True
        assert repo.variant_sku_exists(company_id, "NOT-EXIST") is False

    def test_variant_company_isolation(self, db_session: Session) -> None:
        company_a = uuid.uuid4()
        company_b = uuid.uuid4()
        uom_a = _make_uom(db_session, company_a)
        repo = ProductVariantRepository(db_session)
        product = _make_product(db_session, company_a, uom_a)
        _make_variant(db_session, product, "SHARED-SKU")

        # Same SKU for company B doesn't exist
        assert repo.variant_sku_exists(company_b, "SHARED-SKU") is False


# =============================================================================
# ProductBarcodeRepository tests (T081)
# =============================================================================


class TestProductBarcodeRepository:
    def test_create_and_list_barcodes(self, db_session: Session) -> None:
        company_id = uuid.uuid4()
        uom = _make_uom(db_session, company_id)
        repo = ProductBarcodeRepository(db_session)
        product = _make_product(db_session, company_id, uom)
        _make_barcode(db_session, product, "111111111111")

        barcodes = repo.list_for_product(company_id, product.id)
        assert len(barcodes) == 1
        assert barcodes[0].barcode_value == "111111111111"

    def test_get_barcode_by_value(self, db_session: Session) -> None:
        company_id = uuid.uuid4()
        uom = _make_uom(db_session, company_id)
        repo = ProductBarcodeRepository(db_session)
        product = _make_product(db_session, company_id, uom)
        _make_barcode(db_session, product, "999999999999")

        result = repo.get_by_value(company_id, "999999999999")
        assert result is not None

    def test_get_barcode_by_value_unknown_returns_none(
        self, db_session: Session
    ) -> None:
        company_id = uuid.uuid4()
        repo = ProductBarcodeRepository(db_session)
        result = repo.get_by_value(company_id, "UNKNOWN_BARCODE")
        assert result is None

    def test_barcode_company_isolation(self, db_session: Session) -> None:
        company_a = uuid.uuid4()
        company_b = uuid.uuid4()
        uom_a = _make_uom(db_session, company_a)
        repo = ProductBarcodeRepository(db_session)
        product = _make_product(db_session, company_a, uom_a)
        _make_barcode(db_session, product, "SHARED-BARCODE")

        result = repo.get_by_value(company_b, "SHARED-BARCODE")
        assert result is None
