"""Tenant isolation tests for master data repositories.

Ensures that Company A cannot see Company B's categories, brands, UOMs,
tags, reason codes, custom fields, or attributes.

Task: T052
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy.orm import Session

from modules.inventory.models.attribute import AttributeDefinition, AttributeSet
from modules.inventory.models.brand import Brand
from modules.inventory.models.category import Category
from modules.inventory.models.custom_field import CustomFieldDefinition
from modules.inventory.models.reason_code import ReasonCode
from modules.inventory.models.tag import Tag
from modules.inventory.models.uom import UOM
from modules.inventory.repositories.attribute_repository import (
    AttributeDefinitionRepository,
    AttributeSetRepository,
)
from modules.inventory.repositories.brand_repository import BrandRepository
from modules.inventory.repositories.category_repository import CategoryRepository
from modules.inventory.repositories.custom_field_repository import (
    CustomFieldDefinitionRepository,
)
from modules.inventory.repositories.reason_code_repository import ReasonCodeRepository
from modules.inventory.repositories.tag_repository import TagRepository
from modules.inventory.repositories.uom_repository import UOMRepository

# =============================================================================
# Category isolation
# =============================================================================


class TestCategoryTenantIsolation:
    def test_get_tree_only_returns_own_company_categories(
        self, db_session: Session
    ) -> None:
        repo = CategoryRepository(db_session)
        cid_a, cid_b = uuid.uuid4(), uuid.uuid4()
        repo.create(
            Category(
                company_id=cid_a,
                code="A1",
                name="A Root",
                sort_order=0,
                status="active",
            )
        )
        repo.create(
            Category(
                company_id=cid_b,
                code="B1",
                name="B Root",
                sort_order=0,
                status="active",
            )
        )

        tree_a = repo.get_tree(company_id=cid_a)
        tree_b = repo.get_tree(company_id=cid_b)

        assert len(tree_a) == 1
        assert len(tree_b) == 1
        # Check company isolation
        assert all(str(c.company_id) == str(cid_a) for c in tree_a)
        assert all(str(c.company_id) == str(cid_b) for c in tree_b)

    def test_get_by_code_does_not_cross_company(self, db_session: Session) -> None:
        repo = CategoryRepository(db_session)
        cid_a, cid_b = uuid.uuid4(), uuid.uuid4()
        repo.create(
            Category(
                company_id=cid_a, code="SHARED", name="A", sort_order=0, status="active"
            )
        )
        result = repo.get_by_code(company_id=cid_b, code="SHARED")
        assert result is None

    def test_get_by_id_does_not_cross_company(self, db_session: Session) -> None:
        repo = CategoryRepository(db_session)
        cid_a = uuid.uuid4()
        cat = repo.create(
            Category(
                company_id=cid_a, code="X", name="X", sort_order=0, status="active"
            )
        )
        result = repo.get_by_id_or_none(id=cat.id, company_id=uuid.uuid4())
        assert result is None

    def test_soft_delete_does_not_affect_other_company(
        self, db_session: Session
    ) -> None:
        repo = CategoryRepository(db_session)
        cid_a, cid_b = uuid.uuid4(), uuid.uuid4()
        cat_a = repo.create(
            Category(
                company_id=cid_a,
                code="DEL",
                name="A Del",
                sort_order=0,
                status="active",
            )
        )
        repo.create(
            Category(
                company_id=cid_b,
                code="DEL",
                name="B Del",
                sort_order=0,
                status="active",
            )
        )
        repo.soft_delete(id=cat_a.id, company_id=cid_a)
        result_b = repo.get_by_code(company_id=cid_b, code="DEL")
        assert result_b is not None


# =============================================================================
# Brand isolation
# =============================================================================


class TestBrandTenantIsolation:
    def test_list_brands_only_returns_own_company(self, db_session: Session) -> None:
        repo = BrandRepository(db_session)
        cid_a, cid_b = uuid.uuid4(), uuid.uuid4()
        repo.create(
            Brand(company_id=cid_a, code="BRAND_A", name="Brand A", status="active")
        )
        repo.create(
            Brand(company_id=cid_b, code="BRAND_B", name="Brand B", status="active")
        )

        items_a, total_a = repo.list(company_id=cid_a)
        assert all(str(b.company_id) == str(cid_a) for b in items_a)
        assert total_a == 1

    def test_get_by_code_does_not_cross_company(self, db_session: Session) -> None:
        repo = BrandRepository(db_session)
        cid_a, cid_b = uuid.uuid4(), uuid.uuid4()
        repo.create(Brand(company_id=cid_a, code="SAME", name="Same", status="active"))
        assert repo.get_by_code(company_id=cid_b, code="SAME") is None

    def test_get_by_id_does_not_cross_company(self, db_session: Session) -> None:
        repo = BrandRepository(db_session)
        cid_a = uuid.uuid4()
        brand = repo.create(
            Brand(company_id=cid_a, code="B1", name="B1", status="active")
        )
        from core.exceptions.base import NotFoundException

        with pytest.raises(NotFoundException):
            repo.get_by_id(id=brand.id, company_id=uuid.uuid4())


# =============================================================================
# UOM isolation
# =============================================================================


class TestUOMTenantIsolation:
    def test_list_uoms_only_returns_own_company(self, db_session: Session) -> None:
        repo = UOMRepository(db_session)
        cid_a, cid_b = uuid.uuid4(), uuid.uuid4()
        repo.create(
            UOM(
                company_id=cid_a,
                code="KGA",
                name="KG A",
                uom_type="WEIGHT",
                status="active",
            )
        )
        repo.create(
            UOM(
                company_id=cid_b,
                code="KGB",
                name="KG B",
                uom_type="WEIGHT",
                status="active",
            )
        )

        items_a, _ = repo.list(company_id=cid_a)
        assert all(str(u.company_id) == str(cid_a) for u in items_a)

    def test_get_by_code_does_not_cross_company(self, db_session: Session) -> None:
        repo = UOMRepository(db_session)
        cid_a, cid_b = uuid.uuid4(), uuid.uuid4()
        repo.create(
            UOM(
                company_id=cid_a,
                code="KGS",
                name="KG",
                uom_type="WEIGHT",
                status="active",
            )
        )
        assert repo.get_by_code(company_id=cid_b, code="KGS") is None


# =============================================================================
# Tag isolation
# =============================================================================


class TestTagTenantIsolation:
    def test_list_tags_only_returns_own_company(self, db_session: Session) -> None:
        repo = TagRepository(db_session)
        cid_a, cid_b = uuid.uuid4(), uuid.uuid4()
        repo.create(Tag(company_id=cid_a, name="TagA", usage_count=0))
        repo.create(Tag(company_id=cid_b, name="TagB", usage_count=0))

        tags_a = repo.list_all(company_id=cid_a)
        assert all(str(t.company_id) == str(cid_a) for t in tags_a)
        assert len(tags_a) == 1

    def test_get_by_name_does_not_cross_company(self, db_session: Session) -> None:
        repo = TagRepository(db_session)
        cid_a, cid_b = uuid.uuid4(), uuid.uuid4()
        repo.create(Tag(company_id=cid_a, name="SharedTag", usage_count=0))
        assert repo.get_by_name(company_id=cid_b, name="SharedTag") is None


# =============================================================================
# ReasonCode isolation
# =============================================================================


class TestReasonCodeTenantIsolation:
    def test_list_reason_codes_scoped_to_company(self, db_session: Session) -> None:
        repo = ReasonCodeRepository(db_session)
        cid_a, cid_b = uuid.uuid4(), uuid.uuid4()
        repo.create(
            ReasonCode(
                company_id=cid_a,
                code="RC_A",
                label="A",
                applies_to="DAMAGE",
                is_active=True,
            )
        )
        repo.create(
            ReasonCode(
                company_id=cid_b,
                code="RC_B",
                label="B",
                applies_to="DAMAGE",
                is_active=True,
            )
        )

        items_a, _ = repo.list(company_id=cid_a)
        assert all(str(r.company_id) == str(cid_a) for r in items_a)

    def test_get_by_code_does_not_cross_company(self, db_session: Session) -> None:
        repo = ReasonCodeRepository(db_session)
        cid_a, cid_b = uuid.uuid4(), uuid.uuid4()
        repo.create(
            ReasonCode(
                company_id=cid_a,
                code="SAME",
                label="Same",
                applies_to="RETURN",
                is_active=True,
            )
        )
        assert repo.get_by_code(company_id=cid_b, code="SAME") is None


# =============================================================================
# CustomField isolation
# =============================================================================


class TestCustomFieldTenantIsolation:
    def test_list_for_entity_type_scoped_to_company(self, db_session: Session) -> None:
        repo = CustomFieldDefinitionRepository(db_session)
        cid_a, cid_b = uuid.uuid4(), uuid.uuid4()
        repo.create(
            CustomFieldDefinition(
                company_id=cid_a,
                entity_type="PRODUCT",
                field_key="f_a",
                field_label="F A",
                data_type="TEXT",
                is_required=False,
                sort_order=0,
            )
        )
        repo.create(
            CustomFieldDefinition(
                company_id=cid_b,
                entity_type="PRODUCT",
                field_key="f_b",
                field_label="F B",
                data_type="TEXT",
                is_required=False,
                sort_order=0,
            )
        )
        fields_a = repo.list_for_entity_type(company_id=cid_a, entity_type="PRODUCT")
        assert all(str(f.company_id) == str(cid_a) for f in fields_a)
        assert len(fields_a) == 1

    def test_get_by_field_key_does_not_cross_company(self, db_session: Session) -> None:
        repo = CustomFieldDefinitionRepository(db_session)
        cid_a, cid_b = uuid.uuid4(), uuid.uuid4()
        repo.create(
            CustomFieldDefinition(
                company_id=cid_a,
                entity_type="PRODUCT",
                field_key="shared_key",
                field_label="Shared",
                data_type="TEXT",
                is_required=False,
                sort_order=0,
            )
        )
        result = repo.get_by_field_key(
            company_id=cid_b, entity_type="PRODUCT", field_key="shared_key"
        )
        assert result is None


# =============================================================================
# Attribute isolation
# =============================================================================


class TestAttributeTenantIsolation:
    def test_list_active_attributes_scoped_to_company(
        self, db_session: Session
    ) -> None:
        repo = AttributeDefinitionRepository(db_session)
        cid_a, cid_b = uuid.uuid4(), uuid.uuid4()
        repo.create(
            AttributeDefinition(
                company_id=cid_a, name="Color", data_type="TEXT", is_required=False
            )
        )
        repo.create(
            AttributeDefinition(
                company_id=cid_b, name="Size", data_type="TEXT", is_required=False
            )
        )

        attrs_a = repo.list_active(company_id=cid_a)
        assert all(str(a.company_id) == str(cid_a) for a in attrs_a)
        assert len(attrs_a) == 1

    def test_attribute_set_isolation(self, db_session: Session) -> None:
        repo = AttributeSetRepository(db_session)
        cid_a, cid_b = uuid.uuid4(), uuid.uuid4()
        repo.create(AttributeSet(company_id=cid_a, name="Set A", scope="CATEGORY"))
        repo.create(AttributeSet(company_id=cid_b, name="Set B", scope="CATEGORY"))

        result = repo.get_by_name(company_id=cid_a, name="Set B")
        assert result is None
